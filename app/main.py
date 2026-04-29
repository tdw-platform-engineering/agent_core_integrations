"""AgentCore entrypoint — assembles the agent with optional modules."""

import os
import json
import logging

from dotenv import load_dotenv

load_dotenv()

from .modules.config import (
    BYPASS_TOOL_CONSENT,
    ENABLE_MCP,
    ENABLE_MULTI_AGENT,
    ENABLE_WEB_SEARCH,
    ENABLE_MEMORY,
    ENABLE_KNOWLEDGE_BASE,
    ENABLE_BROWSER,
    ENABLE_ATHENA,
    ATHENA_LAMBDA_NAME,
    ENABLE_CART,
    CONVERSATION_WINDOW_SIZE,
)

os.environ["BYPASS_TOOL_CONSENT"] = BYPASS_TOOL_CONSENT

from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from bedrock_agentcore import BedrockAgentCoreApp

from .models.bedrock import load_model
from .modules.hooks import validate_request, format_response
from .prompts import build_system_prompt

SYSTEM_PROMPT = build_system_prompt(
    enable_knowledge_base=ENABLE_KNOWLEDGE_BASE,
    enable_athena=ENABLE_ATHENA,
    enable_cart=ENABLE_CART,
    enable_browser=ENABLE_BROWSER,
)

app = BedrockAgentCoreApp()
log = app.logger

# ── Log active features at startup ──────────────────────────────────
_features = {
    "mcp": ENABLE_MCP,
    "multi_agent": ENABLE_MULTI_AGENT,
    "web_search": ENABLE_WEB_SEARCH,
    "memory": ENABLE_MEMORY,
    "knowledge_base": ENABLE_KNOWLEDGE_BASE,
    "browser": ENABLE_BROWSER,
    "athena": ENABLE_ATHENA,
    "cart": ENABLE_CART,
}
log.info("Active features: %s", {k: v for k, v in _features.items() if v})
log.info("System prompt assembled: %d chars (~%d tokens)", len(SYSTEM_PROMPT), len(SYSTEM_PROMPT) // 4)


def _collect_tools() -> list:
    """Build the tools list based on enabled feature flags."""
    tools: list = []

    if ENABLE_WEB_SEARCH:
        from .modules.web_search_provider import get_web_tools

        tools.extend(get_web_tools())

    if ENABLE_KNOWLEDGE_BASE:
        from .modules.knowledge_base_provider import get_retrieve_tool

        tools.append(get_retrieve_tool())

    if ENABLE_MCP:
        from .modules.mcp_provider import build_mcp_client

        tools.append(build_mcp_client())

    if ENABLE_BROWSER:
        from .modules.browser_provider import get_browser_tool

        tools.append(get_browser_tool())

    if ENABLE_ATHENA:
        from .modules.athena_provider import get_athena_tool

        tools.append(get_athena_tool(ATHENA_LAMBDA_NAME))

    if ENABLE_CART:
        from .modules.cart_provider import get_cart_tools

        tools.extend(get_cart_tools())

    return tools


def _build_session_manager(session_id: str):
    """Return a session manager if memory is enabled, else None."""
    if not ENABLE_MEMORY:
        return None
    from .modules.memory_provider import build_session_manager

    return build_session_manager(session_id)


def parse_agent_output(raw: str) -> tuple[str, bool]:
    """Extract txt and end from the LLM's JSON response."""
    try:
        data = json.loads(raw)
        return str(data.get("txt", raw)), bool(data.get("end", True))
    except (json.JSONDecodeError, AttributeError):
        return raw, True


def _extract_token_usage(result) -> dict | None:
    """Extract token usage metrics from a Strands AgentResult.

    result.metrics is an EventLoopMetrics dataclass with:
      - accumulated_usage: Usage TypedDict {inputTokens, outputTokens, totalTokens, ...}
      - agent_invocations: list of AgentInvocation, each with .usage
    """
    try:
        metrics = getattr(result, "metrics", None)
        if not metrics:
            return None

        # EventLoopMetrics.accumulated_usage is a Usage TypedDict
        usage = getattr(metrics, "accumulated_usage", None)
        if usage and isinstance(usage, dict) and usage.get("totalTokens", 0) > 0:
            return {
                "inputTokens": usage.get("inputTokens", 0),
                "outputTokens": usage.get("outputTokens", 0),
                "totalTokens": usage.get("totalTokens", 0),
                "cacheReadInputTokens": usage.get("cacheReadInputTokens", 0),
                "cacheWriteInputTokens": usage.get("cacheWriteInputTokens", 0),
            }

        # Fallback: try latest agent invocation
        invocations = getattr(metrics, "agent_invocations", [])
        if invocations:
            last = invocations[-1]
            u = getattr(last, "usage", None)
            if u and isinstance(u, dict) and u.get("totalTokens", 0) > 0:
                return {
                    "inputTokens": u.get("inputTokens", 0),
                    "outputTokens": u.get("outputTokens", 0),
                    "totalTokens": u.get("totalTokens", 0),
                    "cacheReadInputTokens": u.get("cacheReadInputTokens", 0),
                    "cacheWriteInputTokens": u.get("cacheWriteInputTokens", 0),
                }

        return None
    except Exception as e:
        log.warning("Failed to extract token usage: %s", e)
        return None


@app.entrypoint
async def invoke(payload: dict, context):
    request = validate_request(payload)
    session_id = request.runtime_session_id
    user_input = request.question
    log.info(f"Session: {session_id} | Input length: {len(user_input)}")

    tools = _collect_tools()

    # ── Multi-agent path ────────────────────────────────────────────
    if ENABLE_MULTI_AGENT:
        from .modules.multi_agent import run_multi_agent

        report, token_usage = run_multi_agent(user_input, extra_tools=tools or None)
        if token_usage:
            log.info(
                "Session: %s | Tokens — input: %d, output: %d, total: %d",
                session_id,
                token_usage.get("inputTokens", 0),
                token_usage.get("outputTokens", 0),
                token_usage.get("totalTokens", 0),
            )
        response = format_response(
            session_id=session_id,
            text=report,
            end=True,
            token_usage=token_usage,
        )
        log.info(f"Session: {session_id} | multi-agent done")
        return response

    # ── Single-agent path ───────────────────────────────────────────
    agent_kwargs: dict = {
        "model": load_model(),
        "system_prompt": SYSTEM_PROMPT,
        "conversation_manager": SlidingWindowConversationManager(
            window_size=CONVERSATION_WINDOW_SIZE,
        ),
    }
    if tools:
        agent_kwargs["tools"] = tools

    session_manager = _build_session_manager(session_id)
    if session_manager:
        agent_kwargs["session_manager"] = session_manager

    agent = Agent(**agent_kwargs)
    # Inject session context so the agent can use it for cart operations
    agent_input = f"[session_id={session_id}]\n{user_input}" if ENABLE_CART else user_input

    try:
        result = agent(agent_input)
    finally:
        # Always close browser session if it was used
        if ENABLE_BROWSER:
            from .modules.browser_provider import close_browser
            close_browser()

    # ── Extract token usage metrics ─────────────────────────────────
    token_usage = _extract_token_usage(result)
    cycle_count = getattr(result.metrics, "cycle_count", 0) if hasattr(result, "metrics") else 0
    if token_usage:
        log.info(
            "Session: %s | Cycles: %d | Tokens — input: %d, output: %d, total: %d",
            session_id,
            cycle_count,
            token_usage.get("inputTokens", 0),
            token_usage.get("outputTokens", 0),
            token_usage.get("totalTokens", 0),
        )
    else:
        # Debug: log what metrics look like so we can fix extraction
        raw_metrics = getattr(result, "metrics", "NO_METRICS_ATTR")
        log.warning("Session: %s | No token usage extracted. raw metrics type=%s value=%s",
                     session_id, type(raw_metrics).__name__, str(raw_metrics)[:500])

    txt, end = parse_agent_output(str(result))

    response = format_response(
        session_id=session_id,
        text=txt,
        end=end,
        token_usage=token_usage,
    )
    log.info(f"Session: {session_id} | end={end}")
    return response


if __name__ == "__main__":
    app.run()
