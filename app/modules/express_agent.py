"""Express multi-agent — minimal token usage via domain-specific mini-prompts.

Instead of loading a massive system prompt, this module:
1. Uses an ultra-light router (~150 tokens) to classify intent
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
    ENABLE_ATHENA,
    ATHENA_LAMBDA_NAME,
)

log = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "athena"

# ── Domain constants ─────────────────────────────────────────────────
DOMAIN_PRODUCTOS = "productos"
DOMAIN_CLIENTES = "clientes"
DOMAIN_PEDIDOS = "pedidos"
DOMAIN_FACTURAS = "facturas"

_VALID_DOMAINS = {
    DOMAIN_PRODUCTOS,
    DOMAIN_CLIENTES,
    DOMAIN_PEDIDOS,
    DOMAIN_FACTURAS,
}

# Default domain when classification is ambiguous
_DEFAULT_DOMAIN = DOMAIN_PRODUCTOS


def _load_mini_prompt(domain: str) -> str:
    """Load a mini-prompt from app/prompts/athena/<domain>.md."""
    path = _PROMPTS_DIR / f"{domain}.md"
    return path.read_text(encoding="utf-8").strip()


def _get_router_prompt() -> str:
    """Load the router mini-prompt."""
    return _load_mini_prompt("router")


# ── Tool collector ───────────────────────────────────────────────────

def _tools_for_domain(domain: str) -> list:
    """All domains use Athena SQL for now."""
    tools: list = []
    if ENABLE_ATHENA:
        from .athena_provider import get_athena_tool
        tools.append(get_athena_tool(ATHENA_LAMBDA_NAME))
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

    for domain in _VALID_DOMAINS:
        if domain in raw:
            return domain

    return _DEFAULT_DOMAIN


# ── Public API ───────────────────────────────────────────────────────

def run_express_agent(
    user_input: str,
    session_id: str = "",
    extra_tools: list | None = None,
) -> str:
    """Execute the express multi-agent workflow.

    1. Router classifies domain (~150 tokens)
    2. Load mini-prompt for that domain (~200-400 tokens)
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
    agent_kwargs: dict = {
        "model": load_model(ROUTER_MODEL_ID),
        "system_prompt": prompt,
    }
    if tools:
        agent_kwargs["tools"] = tools

    agent = Agent(**agent_kwargs)
    result = agent(user_input)

    response = str(result)
    log.info("Express agent done (domain=%s, prompt_chars=%d, response_len=%d)",
             domain, len(prompt), len(response))
    return response
