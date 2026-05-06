"""Prompt loader — reads .md files from this directory and assembles them based on active features."""

import os
import logging
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent
_AGENTS_DIR = _PROMPTS_DIR / "agents"

log = logging.getLogger(__name__)


def load_prompt(name: str) -> str:
    """Load a single prompt from ``app/prompts/<name>.md``.

    Args:
        name: File stem without extension (e.g. ``"system"``, ``"researcher"``).

    Raises:
        FileNotFoundError: If the .md file does not exist.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").strip()


def load_agent_prompt(agent_name: str) -> str:
    """Load the system prompt for a specific agent from ``app/prompts/agents/<agent_name>.md``.

    Args:
        agent_name: The agent identifier (e.g. ``"agente-ventas-carton"``).

    Raises:
        FileNotFoundError: If the agent prompt file does not exist.
    """
    path = _AGENTS_DIR / f"{agent_name}.md"
    if not path.exists():
        available = [f.stem for f in _AGENTS_DIR.glob("*.md")]
        raise FileNotFoundError(
            f"No se encontró prompt para agente '{agent_name}'. "
            f"Disponibles: {available}"
        )
    return path.read_text(encoding="utf-8").strip()


def build_system_prompt(
    *,
    agent_name: str = "",
    enable_knowledge_base: bool = False,
    enable_athena: bool = False,
    enable_cart: bool = False,
    enable_browser: bool = False,
) -> str:
    """Assemble the system prompt from modular .md files based on active features.

    If agent_name is provided, uses the agent-specific prompt instead of the
    generic system.md. This enables multi-agent deployments from a single codebase.
    """
    # Load base prompt: agent-specific or generic
    if agent_name:
        log.info("Loading agent-specific prompt: %s", agent_name)
        parts = [load_agent_prompt(agent_name)]
    else:
        parts = [load_prompt("system")]

    if enable_knowledge_base:
        parts.append(load_prompt("knowledge_base"))

    if enable_athena:
        parts.append(load_prompt("athena"))
        # SQL rules are only needed when Athena is active
        try:
            parts.append(load_prompt("sql_rules"))
        except FileNotFoundError:
            pass

    if enable_cart:
        parts.append(load_prompt("cart"))

    if enable_browser:
        parts.append(load_prompt("browser"))

    return "\n\n---\n\n".join(parts)
