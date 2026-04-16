"""Optional Bedrock Knowledge Base integration — activated via ENABLE_KNOWLEDGE_BASE=true."""

from __future__ import annotations

import logging
import os

from .config import KNOWLEDGE_BASE_ID, KNOWLEDGE_BASE_REGION

log = logging.getLogger(__name__)


def get_retrieve_tool():
    """Return the strands_tools `retrieve` tool pre-configured with the KB id.

    Supports cross-region KB by setting the region env var.
    """
    if not KNOWLEDGE_BASE_ID:
        raise ValueError(
            "ENABLE_KNOWLEDGE_BASE=true but KNOWLEDGE_BASE_ID is not set."
        )

    os.environ["STRANDS_KNOWLEDGE_BASE_ID"] = KNOWLEDGE_BASE_ID
    os.environ["AWS_REGION_KB"] = KNOWLEDGE_BASE_REGION

    # strands_tools retrieve uses boto3 which reads AWS_DEFAULT_REGION
    # We temporarily set it for the KB region if different
    original_region = os.environ.get("AWS_DEFAULT_REGION")
    os.environ["AWS_DEFAULT_REGION"] = KNOWLEDGE_BASE_REGION

    from strands_tools import retrieve  # type: ignore[import-untyped]

    # Restore original region
    if original_region:
        os.environ["AWS_DEFAULT_REGION"] = original_region
    elif "AWS_DEFAULT_REGION" in os.environ:
        del os.environ["AWS_DEFAULT_REGION"]

    log.info("Knowledge Base enabled  kb_id=%s  region=%s", KNOWLEDGE_BASE_ID, KNOWLEDGE_BASE_REGION)
    return retrieve
