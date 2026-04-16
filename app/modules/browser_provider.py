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
            # Try all possible cleanup methods
            for method in ("close", "stop", "cleanup", "shutdown", "disconnect"):
                fn = getattr(_browser_instance, method, None)
                if callable(fn):
                    print(f"[BROWSER] Calling {method}()")
                    fn()
                    print(f"[BROWSER] {method}() OK")
                    break
            else:
                print(f"[BROWSER] No cleanup method found on {type(_browser_instance)}")
                print(f"[BROWSER] Available: {[m for m in dir(_browser_instance) if not m.startswith('_')]}")
        except Exception as exc:
            print(f"[BROWSER] Error closing: {exc}")
        finally:
            _browser_instance = None
