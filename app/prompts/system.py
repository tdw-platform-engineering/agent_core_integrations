"""System prompt — loaded from system.md + sql_rules.md (legacy single-agent mode)."""

from . import load_prompt

_system = load_prompt("system")
_sql_rules = load_prompt("sql_rules")

SYSTEM_PROMPT = f"{_system}\n\n{_sql_rules}"
