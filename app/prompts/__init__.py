"""Prompt loader — reads .md files from this directory and assembles them based on active features."""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Load a single prompt from ``app/prompts/<name>.md``.

    Args:
        name: File stem without extension (e.g. ``"system"``, ``"researcher"``).

    Raises:
        FileNotFoundError: If the .md file does not exist.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").strip()


def build_system_prompt(
    *,
    enable_knowledge_base: bool = False,
    enable_athena: bool = False,
    enable_cart: bool = False,
    enable_browser: bool = False,
) -> str:
    """Assemble the system prompt from modular .md files based on active features.

    Only includes instructions for features that are actually enabled,
    reducing token usage per request.
    """
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
