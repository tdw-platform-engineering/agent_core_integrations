"""Optional AgentCore Browser integration — activated via ENABLE_BROWSER=true.

Uses strands_tools.browser.AgentCoreBrowser with explicit session cleanup.
"""

from __future__ import annotations

import logging

from .config import AWS_REGION

log = logging.getLogger(__name__)

_browser_instance = None


def get_browser_tool():
    """Return the AgentCoreBrowser tool with managed lifecycle."""
    from strands_tools.browser import AgentCoreBrowser

    global _browser_instance
    _browser_instance = AgentCoreBrowser(region=AWS_REGION)
    log.info("Browser tool enabled (AgentCoreBrowser, region=%s)", AWS_REGION)
    return _browser_instance.browser


def close_browser():
    """Explicitly close the browser session if active."""
    global _browser_instance
    if _browser_instance is not None:
        try:
            _browser_instance.close()
            log.info("Browser session closed")
        except Exception as exc:
            log.warning("Error closing browser: %s", exc)
        finally:
            _browser_instance = None
