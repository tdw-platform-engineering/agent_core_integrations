"""Optional AgentCore Memory integration — activated via ENABLE_MEMORY=true."""

from __future__ import annotations

import logging
from datetime import datetime

from .config import AWS_REGION, MEMORY_ID, MEMORY_ACTOR_ID

log = logging.getLogger(__name__)


def build_session_manager(session_id: str):
    """Create an AgentCoreMemorySessionManager for the given session.

    Requires:
      - MEMORY_ID env var pointing to an existing AgentCore memory resource.
      - bedrock-agentcore package installed.
    """
    from bedrock_agentcore.memory.integrations.strands.config import (
        AgentCoreMemoryConfig,
    )
    from bedrock_agentcore.memory.integrations.strands.session_manager import (
        AgentCoreMemorySessionManager,
    )

    if not MEMORY_ID:
        raise ValueError("ENABLE_MEMORY=true but MEMORY_ID is not set.")

    actor_id = f"{MEMORY_ACTOR_ID}_{datetime.now():%Y%m%d}"

    config = AgentCoreMemoryConfig(
        memory_id=MEMORY_ID,
        session_id=session_id,
        actor_id=actor_id,
    )

    log.info(
        "Memory enabled  memory_id=%s  session=%s  actor=%s",
        MEMORY_ID,
        session_id,
        actor_id,
    )
    return AgentCoreMemorySessionManager(
        agentcore_memory_config=config,
        region_name=AWS_REGION,
    )
