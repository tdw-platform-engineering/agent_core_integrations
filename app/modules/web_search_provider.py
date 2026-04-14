"""Optional web search capability — activated via ENABLE_WEB_SEARCH=true."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def get_web_tools() -> list:
    """Return the http_request tool from strands-agents-tools.

    This gives the agent the ability to make HTTP requests to any URL,
    enabling web search and API consumption.
    """
    from strands_tools import http_request  # type: ignore[import-untyped]

    log.info("Web search tools enabled (http_request)")
    return [http_request]
