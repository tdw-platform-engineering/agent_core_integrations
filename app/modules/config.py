"""Centralized configuration — all values come from environment variables."""

import os


# ── Core ─────────────────────────────────────────────────────────────
BYPASS_TOOL_CONSENT = os.getenv("BYPASS_TOOL_CONSENT", "true")
MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

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

# ── Browser ─────────────────────────────────────────────────────────
BROWSER_START_URL = os.getenv("BROWSER_START_URL", "https://www.google.com")
