"""Optional AgentCore Browser integration — activated via ENABLE_BROWSER=true.

Provides two modes:
  1. Agent tool mode (default): Exposes a @tool-decorated function that the LLM
     can invoke to run browser automation tasks via Browser-Use SDK.
  2. Direct Playwright mode: For programmatic browser control without an LLM
     (useful for scripted scraping / form-filling).

Both modes use AgentCore's managed Chrome sessions via CDP WebSocket.
"""

from __future__ import annotations

import logging

from .config import AWS_REGION, BROWSER_START_URL

log = logging.getLogger(__name__)


# ── Agent tool mode ─────────────────────────────────────────────────

def get_browser_tool():
    """Return a Strands @tool that lets the agent drive a browser session.

    The tool:
      - Starts an AgentCore Browser session
      - Connects via CDP WebSocket
      - Delegates the task to Browser-Use SDK (natural-language → actions)
      - Cleans up the session on completion
    """
    import contextlib
    from strands import tool
    from bedrock_agentcore.tools.browser_client import BrowserClient

    @tool
    async def run_browser_task(
        instruction: str,
        starting_page: str = BROWSER_START_URL,
    ) -> str:
        """Execute web automation via AgentCore Browser + Browser-Use SDK.

        Args:
            instruction: Natural-language task (e.g. "search for laptops and get the first 3 results").
            starting_page: URL to open first.
        """
        from browser_use import Agent as BrowserUseAgent
        from browser_use.browser.session import BrowserSession
        from browser_use.browser import BrowserProfile
        from langchain_aws import ChatBedrockConverse

        log.info("Browser task start: page=%s", starting_page)

        client = BrowserClient(region=AWS_REGION)
        bu_session = None
        try:
            client.start()
            ws_url, headers = client.generate_ws_headers()
            log.info("Browser CDP session created")

            profile = BrowserProfile(headers=headers, timeout=180_000)
            bu_session = BrowserSession(cdp_url=ws_url, browser_profile=profile)
            await bu_session.start()

            llm = ChatBedrockConverse(
                model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
                region_name=AWS_REGION,
            )

            task = (
                f"Navigate to {starting_page}. "
                f"Then: {instruction}. "
                "Summarise the results concisely."
            )

            agent = BrowserUseAgent(
                task=task,
                llm=llm,
                browser_session=bu_session,
            )
            result = await agent.run()
            log.info("Browser task completed")
            return str(result)

        finally:
            if bu_session:
                with contextlib.suppress(Exception):
                    await bu_session.close()
            with contextlib.suppress(Exception):
                client.stop()

    log.info("Browser tool enabled (AgentCore Browser + Browser-Use)")
    return run_browser_task


# ── Direct Playwright mode ──────────────────────────────────────────

def run_playwright_session(actions_fn):
    """Run a synchronous Playwright session against AgentCore Browser.

    Usage example::

        from app.modules.browser_provider import run_playwright_session

        def my_actions(page):
            page.goto("https://www.amazon.com")
            page.fill("input#twotabsearchtextbox", "laptop")
            page.press("input#twotabsearchtextbox", "Enter")
            page.wait_for_selector("div.s-main-slot", timeout=10000)
            page.screenshot(path="search.png")

        run_playwright_session(my_actions)

    Args:
        actions_fn: A callable that receives a Playwright ``Page`` object.
    """
    from playwright.sync_api import sync_playwright
    from bedrock_agentcore.tools.browser_client import browser_session

    with browser_session(AWS_REGION) as client:
        ws_url, headers = client.generate_ws_headers()

        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(ws_url, headers=headers)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()

            try:
                actions_fn(page)
            finally:
                page.close()
                browser.close()
