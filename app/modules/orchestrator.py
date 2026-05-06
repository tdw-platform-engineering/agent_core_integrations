"""Orchestrator module — allows an agent to invoke other Agent Core runtimes.

This enables the orchestrator pattern where one agent (e.g. agente-orquestador-papel-carton)
can call sub-agents (agente-ventas-papel, agente-ventas-carton) that are deployed as
separate, isolated runtimes.

Each sub-agent is invoked via its ARN, ensuring complete logical separation.
A prompt injection in one sub-agent cannot affect the other.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
from strands.tools import tool

log = logging.getLogger(__name__)

# ── Sub-agent registry (loaded from AGENT_NAME config) ───────────────
# Format: {"alias": {"arn": "arn:aws:bedrock-agentcore:...", "description": "..."}}
_SUB_AGENTS: dict[str, dict[str, str]] = {}


def _get_client():
    """Get the Bedrock Agent Core runtime client."""
    region = os.getenv("AWS_REGION", "us-east-1")
    return boto3.client("bedrock-agentcore", region_name=region)


def register_sub_agents(sub_agents: dict[str, dict[str, str]]) -> None:
    """Register sub-agents that this orchestrator can invoke.

    Args:
        sub_agents: Dict mapping alias to config.
            Example: {
                "ventas_papel": {"arn": "arn:aws:...", "description": "Agente de ventas papel"},
                "ventas_carton": {"arn": "arn:aws:...", "description": "Agente de ventas cartón"}
            }
    """
    global _SUB_AGENTS
    _SUB_AGENTS = sub_agents
    log.info("Registered %d sub-agents: %s", len(sub_agents), list(sub_agents.keys()))


def invoke_sub_agent(agent_alias: str, input_text: str, session_id: str = "") -> dict[str, Any]:
    """Invoke a sub-agent runtime by its alias.

    Args:
        agent_alias: The alias of the sub-agent (must be registered).
        input_text: The text to send to the sub-agent.
        session_id: Optional session ID for conversation continuity.

    Returns:
        Dict with 'answer', 'session_id', and 'raw' response.
    """
    if agent_alias not in _SUB_AGENTS:
        available = list(_SUB_AGENTS.keys())
        return {
            "success": False,
            "error": f"Sub-agent '{agent_alias}' not registered. Available: {available}",
        }

    config = _SUB_AGENTS[agent_alias]
    arn = config["arn"]

    if not session_id:
        import uuid
        session_id = f"orch-{uuid.uuid4().hex[:12]}"

    log.info("Invoking sub-agent '%s' (ARN: %s)", agent_alias, arn)

    try:
        client = _get_client()

        payload = {
            "input": input_text,
            "runtimeSessionId": session_id,
        }

        response = client.invoke_agent_runtime(
            agentRuntimeArn=arn,
            contentType="application/json",
            accept="application/json",
            runtimeSessionId=session_id,
            payload=json.dumps(payload).encode("utf-8"),
        )

        # Parse response
        response_bytes = response.get("response", b"")
        if hasattr(response_bytes, "read"):
            response_bytes = response_bytes.read()
        elif hasattr(response_bytes, "transformToByteArray"):
            response_bytes = response_bytes.transformToByteArray()

        raw_text = response_bytes.decode("utf-8") if response_bytes else ""

        try:
            parsed = json.loads(raw_text) if raw_text else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw_text}

        # Extract answer from various response formats
        output = parsed.get("output", {})
        answer = (
            output.get("answer")
            or output.get("message")
            or parsed.get("txt")
            or raw_text
            or "Sin respuesta del sub-agente"
        )

        log.info("Sub-agent '%s' responded (%d chars)", agent_alias, len(answer))

        return {
            "success": True,
            "answer": answer,
            "session_id": session_id,
            "agent_alias": agent_alias,
            "raw": parsed,
        }

    except Exception as e:
        log.error("Error invoking sub-agent '%s': %s", agent_alias, e)
        return {
            "success": False,
            "error": str(e),
            "agent_alias": agent_alias,
        }


# ── Strands tools for the orchestrator agent ─────────────────────────

@tool
def invoke_agent(agent_name: str, query: str, session_id: str = "") -> str:
    """Invoke a sub-agent and return its response.

    Use this tool to route a query to a specialized sub-agent.

    Args:
        agent_name: Name of the sub-agent to invoke. Check available agents first.
        query: The question or instruction to send to the sub-agent.
        session_id: Optional session ID for conversation continuity.

    Returns:
        The sub-agent's response text, or an error message.
    """
    result = invoke_sub_agent(agent_name, query, session_id)
    if result.get("success"):
        return result["answer"]
    else:
        return f"Error: {result.get('error', 'Unknown error')}"


@tool
def list_available_agents() -> str:
    """List all available sub-agents that can be invoked.

    Returns:
        A formatted list of available sub-agents with their descriptions.
    """
    if not _SUB_AGENTS:
        return "No sub-agents registered."

    lines = ["Available sub-agents:"]
    for alias, config in _SUB_AGENTS.items():
        desc = config.get("description", "No description")
        lines.append(f"  - {alias}: {desc}")
    return "\n".join(lines)


def get_orchestrator_tools() -> list:
    """Return the tools that an orchestrator agent needs."""
    return [invoke_agent, list_available_agents]
