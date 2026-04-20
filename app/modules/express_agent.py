"""Express multi-agent — minimal token usage via domain-specific mini-prompts.

Instead of loading a massive system prompt, this module:
1. Uses an ultra-light router (~300 tokens) to classify intent
2. Loads ONLY the mini-prompt for that specific domain
3. Runs the specialist with minimal context

Mini-prompts live in app/prompts/athena/<domain>.md and are designed to be
as small as possible while giving the LLM enough context to execute correctly.
"""

from __future__ import annotations

import logging
from pathlib import Path

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

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "athena"

# ── Domain constants ─────────────────────────────────────────────────
DOMAIN_PRODUCTOS = "productos"
DOMAIN_COMPLEMENTARIOS = "complementarios"
DOMAIN_PROYECTO = "proyecto"
DOMAIN_LISTA = "lista"
DOMAIN_GENERAL = "general"

_VALID_DOMAINS = {
    DOMAIN_PRODUCTOS,
    DOMAIN_COMPLEMENTARIOS,
    DOMAIN_PROYECTO,
    DOMAIN_LISTA,
    DOMAIN_GENERAL,
}

# ── Domain → model mapping ───────────────────────────────────────────
_DOMAIN_MODEL = {
    DOMAIN_PRODUCTOS: CATALOGO_MODEL_ID,
    DOMAIN_COMPLEMENTARIOS: COMPLEMENTARIOS_MODEL_ID,
    DOMAIN_PROYECTO: COMPLEMENTARIOS_MODEL_ID,
    DOMAIN_LISTA: COTIZACION_MODEL_ID,
    DOMAIN_GENERAL: GENERAL_MODEL_ID,
}


def _load_mini_prompt(domain: str) -> str:
    """Load a mini-prompt from app/prompts/athena/<domain>.md."""
    path = _PROMPTS_DIR / f"{domain}.md"
    return path.read_text(encoding="utf-8").strip()


def _get_router_prompt() -> str:
    """Load the router mini-prompt."""
    return _load_mini_prompt("router")


# ── Tool collectors per domain ───────────────────────────────────────

def _tools_for_domain(domain: str) -> list:
    """Return only the tools needed for a specific domain."""
    tools: list = []

    if domain in (DOMAIN_PRODUCTOS, DOMAIN_COMPLEMENTARIOS, DOMAIN_PROYECTO):
        if ENABLE_ATHENA:
            from .athena_provider import get_athena_tool
            tools.append(get_athena_tool(ATHENA_LAMBDA_NAME))

    if domain == DOMAIN_PRODUCTOS:
        if ENABLE_KNOWLEDGE_BASE:
            from .knowledge_base_provider import get_retrieve_tool
            tools.append(get_retrieve_tool())

    if domain == DOMAIN_LISTA:
        if ENABLE_CART:
            from .cart_provider import get_cart_tools
            tools.extend(get_cart_tools())
        if ENABLE_ATHENA:
            from .athena_provider import get_athena_tool
            tools.append(get_athena_tool(ATHENA_LAMBDA_NAME))

    if domain == DOMAIN_GENERAL:
        if ENABLE_BROWSER:
            from .browser_provider import get_browser_tool
            tools.append(get_browser_tool())

    return tools


# ── Router ───────────────────────────────────────────────────────────

def _classify_domain(user_input: str) -> str:
    """Ultra-light classification — minimal tokens."""
    router = Agent(
        model=load_model(ROUTER_MODEL_ID),
        system_prompt=_get_router_prompt(),
        callback_handler=None,
    )

    result = router(user_input)
    raw = str(result).strip().lower()
    log.info("Express router: '%s'", raw[:50])

    # Extract domain from response
    for domain in _VALID_DOMAINS:
        if domain in raw:
            return domain

    return DOMAIN_GENERAL


# ── Public API ───────────────────────────────────────────────────────

def run_express_agent(
    user_input: str,
    session_id: str = "",
    extra_tools: list | None = None,
) -> str:
    """Execute the express multi-agent workflow.

    1. Router classifies domain (~300 tokens)
    2. Load mini-prompt for that domain (~500-1500 tokens)
    3. Run specialist with minimal context
    """
    log.info("Express agent started")

    # Step 1 — Classify
    domain = _classify_domain(user_input)
    log.info("Express domain: %s", domain)

    # Step 2 — Load mini-prompt
    prompt = _load_mini_prompt(domain)

    # Step 3 — Collect tools
    tools = _tools_for_domain(domain)
    if extra_tools:
        tools.extend(extra_tools)

    # Step 4 — Build and run specialist
    model_id = _DOMAIN_MODEL.get(domain, "")
    agent_kwargs: dict = {
        "model": load_model(model_id),
        "system_prompt": prompt,
    }
    if tools:
        agent_kwargs["tools"] = tools

    agent = Agent(**agent_kwargs)

    # Inject session_id for list operations
    agent_input = user_input
    if domain == DOMAIN_LISTA and session_id:
        agent_input = f"[session_id={session_id}]\n{user_input}"

    try:
        result = agent(agent_input)
    finally:
        if domain == DOMAIN_GENERAL and ENABLE_BROWSER:
            try:
                from .browser_provider import close_browser
                close_browser()
            except Exception:
                pass

    response = str(result)
    log.info("Express agent done (domain=%s, tokens_prompt~%d, response_len=%d)",
             domain, len(prompt) // 4, len(response))
    return response
