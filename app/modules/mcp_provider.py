"""Optional MCP tool provider — activated via ENABLE_MCP=true."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .config import MCP_TRANSPORT, MCP_COMMAND, MCP_ARGS, MCP_HTTP_URL

if TYPE_CHECKING:
    from strands.tools.mcp import MCPClient

log = logging.getLogger(__name__)


def build_mcp_client() -> "MCPClient":
    """Return an MCPClient configured from environment variables.

    Supports two transports:
      - stdio  → launches a local subprocess (default)
      - http   → connects to a remote Streamable-HTTP MCP server
    """
    from strands.tools.mcp import MCPClient

    if MCP_TRANSPORT == "http":
        from mcp.client.streamable_http import streamablehttp_client

        log.info("MCP transport=http  url=%s", MCP_HTTP_URL)
        return MCPClient(lambda: streamablehttp_client(MCP_HTTP_URL))

    # default: stdio
    from mcp import stdio_client, StdioServerParameters

    args = [a.strip() for a in MCP_ARGS.split(",") if a.strip()]
    log.info("MCP transport=stdio  command=%s args=%s", MCP_COMMAND, args)
    return MCPClient(
        lambda: stdio_client(
            StdioServerParameters(command=MCP_COMMAND, args=args)
        )
    )
