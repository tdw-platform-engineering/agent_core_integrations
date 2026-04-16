"""Optional AgentCore Browser integration — activated via ENABLE_BROWSER=true.

Uses the official strands_tools.browser.AgentCoreBrowser which handles
session lifecycle, CDP connection, and cleanup automatically.
"""

from __future__ import annotations

import logging

from .config import AWS_REGION

log = logging.getLogger(__name__)


def get_browser_tool():
    """Return the AgentCoreBrowser tool for the agent."""
    from strands_tools.browser import AgentCoreBrowser

    agentcore_browser = AgentCoreBrowser(region=AWS_REGION)
    log.info("Browser tool enabled (AgentCoreBrowser, region=%s)", AWS_REGION)
    return agentcore_browser.browser
