"""Prompt loader — reads .md files from this directory."""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Load a prompt from ``app/prompts/<name>.md``.

    Args:
        name: File stem without extension (e.g. ``"system"``, ``"researcher"``).

    Raises:
        FileNotFoundError: If the .md file does not exist.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").strip()
