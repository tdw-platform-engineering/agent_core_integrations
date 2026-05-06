"""Centralized configuration — all values come from environment variables."""

import os


# ── Agent Identity ───────────────────────────────────────────────────
AGENT_NAME = os.getenv("AGENT_NAME", "")

# ── Core ─────────────────────────────────────────────────────────────
BYPASS_TOOL_CONSENT = os.getenv("BYPASS_TOOL_CONSENT", "true")
MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# ── Per-agent models (fall back to MODEL_ID if not set) ─────────────
RESEARCHER_MODEL_ID = os.getenv("RESEARCHER_MODEL_ID", "")
ANALYST_MODEL_ID = os.getenv("ANALYST_MODEL_ID", "")
WRITER_MODEL_ID = os.getenv("WRITER_MODEL_ID", "")

# ── Feature flags (set to "true" to enable) ──────────────────────────
ENABLE_MCP = os.getenv("ENABLE_MCP", "false").lower() == "true"
ENABLE_MULTI_AGENT = os.getenv("ENABLE_MULTI_AGENT", "false").lower() == "true"
ENABLE_WEB_SEARCH = os.getenv("ENABLE_WEB_SEARCH", "false").lower() == "true"
ENABLE_MEMORY = os.getenv("ENABLE_MEMORY", "false").lower() == "true"
ENABLE_KNOWLEDGE_BASE = os.getenv("ENABLE_KNOWLEDGE_BASE", "false").lower() == "true"
ENABLE_BROWSER = os.getenv("ENABLE_BROWSER", "false").lower() == "true"

# ── MCP ──────────────────────────────────────────────────────────────
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")  # "stdio" | "http"
MCP_COMMAND = os.getenv("MCP_COMMAND", "uvx")
MCP_ARGS = os.getenv("MCP_ARGS", "awslabs.aws-documentation-mcp-server@latest")
MCP_HTTP_URL = os.getenv("MCP_HTTP_URL", "http://localhost:8000/mcp")

# ── Memory (AgentCore) ──────────────────────────────────────────────
MEMORY_ID = os.getenv("MEMORY_ID", "")
MEMORY_ACTOR_ID = os.getenv("MEMORY_ACTOR_ID", "default-actor")

# ── Knowledge Base ──────────────────────────────────────────────────
KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID", "")
KNOWLEDGE_BASE_REGION = os.getenv("KNOWLEDGE_BASE_REGION", os.getenv("AWS_REGION", "us-east-1"))

# ── Browser ─────────────────────────────────────────────────────────
BROWSER_START_URL = os.getenv("BROWSER_START_URL", "https://www.google.com")

# ── Thinking ────────────────────────────────────────────────────────
ENABLE_THINKING = os.getenv("ENABLE_THINKING", "false").lower() == "true"
THINKING_BUDGET = int(os.getenv("THINKING_BUDGET", "4096"))

# ── Athena ──────────────────────────────────────────────────────────
ENABLE_ATHENA = os.getenv("ENABLE_ATHENA", "false").lower() == "true"
ATHENA_LAMBDA_NAME = os.getenv("ATHENA_LAMBDA_NAME", "")
ATHENA_LAMBDA_REGION = os.getenv("ATHENA_LAMBDA_REGION", os.getenv("AWS_REGION", "us-east-1"))

# ── Conversation Manager ────────────────────────────────────────
CONVERSATION_WINDOW_SIZE = int(os.getenv("CONVERSATION_WINDOW_SIZE", "10"))  # max messages to keep

# ── Cart ────────────────────────────────────────────────────────
ENABLE_CART = os.getenv("ENABLE_CART", "false").lower() == "true"

# ── Orchestrator (sub-agent invocation) ─────────────────────────
ENABLE_ORCHESTRATOR = os.getenv("ENABLE_ORCHESTRATOR", "false").lower() == "true"
SUB_AGENTS_JSON = os.getenv("SUB_AGENTS", "")  # JSON string with sub-agent ARNs
