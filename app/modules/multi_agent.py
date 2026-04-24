"""Optional multi-agent orchestration — activated via ENABLE_MULTI_AGENT=true.

Implements a simple research workflow with three specialised agents:
  1. Researcher  — gathers information (can use web tools if enabled)
  2. Analyst     — verifies facts and extracts insights
  3. Writer      — produces the final user-facing report

The orchestrator function `run_multi_agent` is designed to be called from
the main entrypoint when multi-agent mode is active.
"""

from __future__ import annotations

import logging
from typing import Any

from strands import Agent

from ..models.bedrock import load_model
from ..prompts import load_prompt
from .config import RESEARCHER_MODEL_ID, ANALYST_MODEL_ID, WRITER_MODEL_ID

log = logging.getLogger(__name__)


def _build_researcher(tools: list | None = None) -> Agent:
    return Agent(
        model=load_model(RESEARCHER_MODEL_ID),
        system_prompt=load_prompt("researcher"),
        tools=tools or [],
        callback_handler=None,
    )


def _build_analyst() -> Agent:
    return Agent(
        model=load_model(ANALYST_MODEL_ID),
        system_prompt=load_prompt("analyst"),
        callback_handler=None,
    )


def _build_writer() -> Agent:
    return Agent(
        model=load_model(WRITER_MODEL_ID),
        system_prompt=load_prompt("writer"),
        callback_handler=None,
    )


def run_multi_agent(user_input: str, extra_tools: list | None = None) -> tuple[str, dict | None]:
    """Execute the three-agent research workflow and return the final report + aggregated token usage."""
    log.info("Multi-agent workflow started")

    researcher = _build_researcher(tools=extra_tools)
    analyst = _build_analyst()
    writer = _build_writer()

    total_usage: dict[str, int] = {
        "inputTokens": 0, "outputTokens": 0, "totalTokens": 0,
        "cacheReadInputTokens": 0, "cacheWriteInputTokens": 0,
    }

    def _accumulate(result: Any) -> None:
        metrics = getattr(result, "metrics", None)
        if not metrics or not isinstance(metrics, dict):
            return
        usage = metrics.get("usage", None)
        if not usage:
            accumulated = metrics.get("accumulated", metrics)
            usage = accumulated.get("usage", None) if isinstance(accumulated, dict) else None
        if usage:
            for key in total_usage:
                total_usage[key] += usage.get(key, 0)

    # Step 1 — Research
    research_result = researcher(
        f"Research: '{user_input}'. Use your available tools to gather information."
    )
    _accumulate(research_result)
    research_text = str(research_result)
    log.info("Researcher done (%d chars)", len(research_text))

    # Step 2 — Analysis
    analysis_result = analyst(
        f"Analyze these findings about '{user_input}':\n\n{research_text}"
    )
    _accumulate(analysis_result)
    analysis_text = str(analysis_result)
    log.info("Analyst done (%d chars)", len(analysis_text))

    # Step 3 — Report
    report_result = writer(
        f"Create a report on '{user_input}' based on this analysis:\n\n{analysis_text}"
    )
    _accumulate(report_result)
    log.info("Writer done")

    has_usage = total_usage["totalTokens"] > 0
    log.info(
        "Multi-agent tokens — input: %d, output: %d, total: %d",
        total_usage["inputTokens"], total_usage["outputTokens"], total_usage["totalTokens"],
    )

    return str(report_result), total_usage if has_usage else None
