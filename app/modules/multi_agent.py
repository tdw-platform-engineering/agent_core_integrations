"""Multi-agent orchestration — activated via ENABLE_MULTI_AGENT=true.

Implements a domain-specific routing workflow with specialized agents:
  1. Router     — classifies intent and picks the right specialist
  2. Catálogo   — product search (Knowledge Base + Athena SQL)
  3. Complementarios — MBA complementary products + construction recommendations
  4. Cotización — cart/list management and budgets
  5. General    — greetings, FAQ, browser, general questions

The router agent receives the user input, returns a JSON with the target
agent name, and the orchestrator delegates to the specialist with the
appropriate tools and prompt.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from strands import Agent

from ..models.bedrock import load_model
from .config import (
    ROUTER_MODEL_ID,
    CATALOGO_MODEL_ID,
    COMPLEMENTARIOS_MODEL_ID,
    COTIZACION_MODEL_ID,
    GENERAL_MODEL_ID,
    ENABLE_KNOWLEDGE_BASE,
    ENABLE_ATHENA,
    ENABLE_CART,
    ENABLE_BROWSER,
    ATHENA_LAMBDA_NAME,
)

log = logging.getLogger(__name__)

# ── Load mini-prompts from athena/ ───────────────────────────────────
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "athena"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()

# ── Agent name constants ─────────────────────────────────────────────
AGENT_CATALOGO = "catalogo"
AGENT_COMPLEMENTARIOS = "complementarios"
AGENT_COTIZACION = "cotizacion"
AGENT_GENERAL = "general"

_VALID_AGENTS = {AGENT_CATALOGO, AGENT_COMPLEMENTARIOS, AGENT_COTIZACION, AGENT_GENERAL}


# ── Tool collectors per agent ────────────────────────────────────────

def _tools_catalogo() -> list:
    """Tools for the catalog agent: Knowledge Base + Athena SQL."""
    tools: list = []
    if ENABLE_KNOWLEDGE_BASE:
        from .knowledge_base_provider import get_retrieve_tool
        tools.append(get_retrieve_tool())
    if ENABLE_ATHENA:
        from .athena_provider import get_athena_tool
        tools.append(get_athena_tool(ATHENA_LAMBDA_NAME))
    return tools


def _tools_complementarios() -> list:
    """Tools for the complementary agent: Athena SQL (MBA queries)."""
    tools: list = []
    if ENABLE_ATHENA:
        from .athena_provider import get_athena_tool
        tools.append(get_athena_tool(ATHENA_LAMBDA_NAME))
    if ENABLE_KNOWLEDGE_BASE:
        from .knowledge_base_provider import get_retrieve_tool
        tools.append(get_retrieve_tool())
    return tools


def _tools_cotizacion() -> list:
    """Tools for the quotation agent: Cart + Athena (for budget building)."""
    tools: list = []
    if ENABLE_CART:
        from .cart_provider import get_cart_tools
        tools.extend(get_cart_tools())
    if ENABLE_ATHENA:
        from .athena_provider import get_athena_tool
        tools.append(get_athena_tool(ATHENA_LAMBDA_NAME))
    return tools


def _tools_general() -> list:
    """Tools for the general agent: Browser."""
    tools: list = []
    if ENABLE_BROWSER:
        from .browser_provider import get_browser_tool
        tools.append(get_browser_tool())
    return tools


# ── Agent config map ─────────────────────────────────────────────────

_AGENT_CONFIG = {
    AGENT_CATALOGO: {
        "model_id": CATALOGO_MODEL_ID,
        "prompt_name": "productos",
        "tools_fn": _tools_catalogo,
    },
    AGENT_COMPLEMENTARIOS: {
        "model_id": COMPLEMENTARIOS_MODEL_ID,
        "prompt_name": "complementarios",
        "tools_fn": _tools_complementarios,
    },
    AGENT_COTIZACION: {
        "model_id": COTIZACION_MODEL_ID,
        "prompt_name": "lista",
        "tools_fn": _tools_cotizacion,
    },
    AGENT_GENERAL: {
        "model_id": GENERAL_MODEL_ID,
        "prompt_name": "general",
        "tools_fn": _tools_general,
    },
}


# ── Router ───────────────────────────────────────────────────────────

def _classify_intent(user_input: str) -> str:
    """Use the router agent to classify user intent and return agent name."""
    router = Agent(
        model=load_model(ROUTER_MODEL_ID),
        system_prompt=_load_prompt("router"),
        callback_handler=None,
    )

    result = router(user_input)
    raw = str(result).strip()
    log.info("Router raw output: %s", raw[:200])

    try:
        data = json.loads(raw)
        agent_name = data.get("agent", AGENT_GENERAL)
    except (json.JSONDecodeError, AttributeError):
        # Try to extract agent name from text
        raw_lower = raw.lower()
        for name in _VALID_AGENTS:
            if name in raw_lower:
                agent_name = name
                break
        else:
            agent_name = AGENT_GENERAL

    if agent_name not in _VALID_AGENTS:
        log.warning("Router returned unknown agent '%s', falling back to general", agent_name)
        agent_name = AGENT_GENERAL

    log.info("Router classified intent → %s", agent_name)
    return agent_name


# ── Specialist execution ─────────────────────────────────────────────

def _run_specialist(agent_name: str, user_input: str, extra_tools: list | None = None) -> str:
    """Build and run the specialist agent for the given intent."""
    config = _AGENT_CONFIG[agent_name]

    tools = config["tools_fn"]()
    if extra_tools:
        tools.extend(extra_tools)

    agent_kwargs: dict = {
        "model": load_model(config["model_id"]),
        "system_prompt": _load_prompt(config["prompt_name"]),
    }
    if tools:
        agent_kwargs["tools"] = tools

    agent = Agent(**agent_kwargs)
    result = agent(user_input)
    return str(result)


# ── Public API ───────────────────────────────────────────────────────

def run_multi_agent(
    user_input: str,
    extra_tools: list | None = None,
    session_id: str = "",
) -> str:
    """Execute the multi-agent routing workflow and return the specialist's response.

    1. Router classifies the user intent
    2. Specialist agent handles the request with its specific tools and prompt
    """
    log.info("Multi-agent workflow started")

    # Step 1 — Route
    agent_name = _classify_intent(user_input)

    # Step 2 — Inject session context for cart operations
    agent_input = user_input
    if agent_name == AGENT_COTIZACION and session_id:
        agent_input = f"[session_id={session_id}]\n{user_input}"

    # Step 3 — Execute specialist
    try:
        response = _run_specialist(agent_name, agent_input, extra_tools)
    finally:
        # Always close browser session if it was used
        if agent_name == AGENT_GENERAL and ENABLE_BROWSER:
            try:
                from .browser_provider import close_browser
                close_browser()
            except Exception:
                pass

    log.info("Multi-agent workflow done (agent=%s, response_len=%d)", agent_name, len(response))
    return response
