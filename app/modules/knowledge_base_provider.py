"""Optional Bedrock Knowledge Base integration — activated via ENABLE_KNOWLEDGE_BASE=true."""

from __future__ import annotations

import logging
import os

from .config import KNOWLEDGE_BASE_ID

log = logging.getLogger(__name__)


def get_retrieve_tool():
    """Return the strands_tools `retrieve` tool pre-configured with the KB id.

    The `retrieve` tool uses the STRANDS_KNOWLEDGE_BASE_ID env var internally,
    so we ensure it is set before importing.
    """
    if not KNOWLEDGE_BASE_ID:
        raise ValueError(
            "ENABLE_KNOWLEDGE_BASE=true but KNOWLEDGE_BASE_ID is not set."
        )

    os.environ["STRANDS_KNOWLEDGE_BASE_ID"] = KNOWLEDGE_BASE_ID

    from strands_tools import retrieve  # type: ignore[import-untyped]

    log.info("Knowledge Base enabled  kb_id=%s", KNOWLEDGE_BASE_ID)
    return retrieve
