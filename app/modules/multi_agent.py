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

log = logging.getLogger(__name__)


def _build_researcher(tools: list | None = None) -> Agent:
    return Agent(
        model=load_model(),
        system_prompt=(
            "You are a Researcher Agent. "
            "1. Use your tools to gather relevant information from available sources. "
            "2. Include source references when possible. "
            "3. Keep findings under 500 words."
        ),
        tools=tools or [],
        callback_handler=None,
    )


def _build_analyst() -> Agent:
    return Agent(
        model=load_model(),
        system_prompt=(
            "You are an Analyst Agent. "
            "1. For factual claims: rate accuracy 1-5 and correct if needed. "
            "2. For research queries: identify 3-5 key insights. "
            "3. Evaluate source reliability. Keep analysis under 400 words."
        ),
        callback_handler=None,
    )


def _build_writer() -> Agent:
    return Agent(
        model=load_model(),
        system_prompt=(
            "You are a Writer Agent. "
            "1. For fact-checks: state whether claims are true or false. "
            "2. For research: present key insights in a logical structure. "
            "3. Keep reports under 500 words with brief source mentions."
        ),
        callback_handler=None,
    )


def run_multi_agent(user_input: str, extra_tools: list | None = None) -> str:
    """Execute the three-agent research workflow and return the final report."""
    log.info("Multi-agent workflow started")

    researcher = _build_researcher(tools=extra_tools)
    analyst = _build_analyst()
    writer = _build_writer()

    # Step 1 — Research
    research_result = researcher(
        f"Research: '{user_input}'. Use your available tools to gather information."
    )
    research_text = str(research_result)
    log.info("Researcher done (%d chars)", len(research_text))

    # Step 2 — Analysis
    analysis_result = analyst(
        f"Analyze these findings about '{user_input}':\n\n{research_text}"
    )
    analysis_text = str(analysis_result)
    log.info("Analyst done (%d chars)", len(analysis_text))

    # Step 3 — Report
    report_result = writer(
        f"Create a report on '{user_input}' based on this analysis:\n\n{analysis_text}"
    )
    log.info("Writer done")
    return str(report_result)
