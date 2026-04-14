"""AgentCore entrypoint — assembles the agent with optional modules."""

import os
import json
import logging

from .modules.config import (
    BYPASS_TOOL_CONSENT,
    ENABLE_MCP,
    ENABLE_MULTI_AGENT,
    ENABLE_WEB_SEARCH,
    ENABLE_MEMORY,
    ENABLE_KNOWLEDGE_BASE,
    ENABLE_BROWSER,
)

os.environ["BYPASS_TOOL_CONSENT"] = BYPASS_TOOL_CONSENT

from strands import Agent
from bedrock_agentcore import BedrockAgentCoreApp

from .models.bedrock import load_model
from .modules.hooks import validate_request, format_response
from .prompts.system import SYSTEM_PROMPT

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
}
log.info("Active features: %s", {k: v for k, v in _features.items() if v})


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


@app.entrypoint
async def invoke(payload: dict, context):
    request = validate_request(payload)
    session_id = request.runtime_session_id
    log.info(f"Session: {session_id} | Input length: {len(request.input)}")

    tools = _collect_tools()

    # ── Multi-agent path ────────────────────────────────────────────
    if ENABLE_MULTI_AGENT:
        from .modules.multi_agent import run_multi_agent

        report = run_multi_agent(request.input, extra_tools=tools or None)
        response = format_response(
            session_id=session_id,
            text=report,
            end=True,
        )
        log.info(f"Session: {session_id} | multi-agent done")
        return response

    # ── Single-agent path ───────────────────────────────────────────
    agent_kwargs: dict = {
        "model": load_model(),
        "system_prompt": SYSTEM_PROMPT,
    }
    if tools:
        agent_kwargs["tools"] = tools

    session_manager = _build_session_manager(session_id)
    if session_manager:
        agent_kwargs["session_manager"] = session_manager

    agent = Agent(**agent_kwargs)
    result = agent(request.input)
    txt, end = parse_agent_output(str(result))

    response = format_response(
        session_id=session_id,
        text=txt,
        end=end,
    )
    log.info(f"Session: {session_id} | end={end}")
    return response


if __name__ == "__main__":
    app.run()
