"""Optional Bedrock Knowledge Base integration — activated via ENABLE_KNOWLEDGE_BASE=true.

Supports multiple KBs via comma-separated KNOWLEDGE_BASE_IDS.
Each KB gets its own retrieve tool with a descriptive name.
"""

from __future__ import annotations

import json
import logging
import os

import boto3
from strands import tool

from .config import AWS_REGION

log = logging.getLogger(__name__)


def _parse_kb_config() -> list[dict]:
    """Parse KB config from env vars.

    Supports two formats:
    - Single: KNOWLEDGE_BASE_ID=ABC123
    - Multiple: KNOWLEDGE_BASE_IDS=name1:ID1,name2:ID2
    """
    region = os.getenv("KNOWLEDGE_BASE_REGION", AWS_REGION)

    # Multiple KBs: "ejemplos:ABC123,materiales:DEF456"
    multi = os.getenv("KNOWLEDGE_BASE_IDS", "")
    if multi:
        kbs = []
        for entry in multi.split(","):
            entry = entry.strip()
            if ":" in entry:
                name, kb_id = entry.split(":", 1)
                kbs.append({"name": name.strip(), "id": kb_id.strip(), "region": region})
            else:
                kbs.append({"name": f"kb_{len(kbs)+1}", "id": entry.strip(), "region": region})
        return kbs

    # Single KB fallback
    single = os.getenv("KNOWLEDGE_BASE_ID", "")
    if single:
        return [{"name": "knowledge_base", "id": single, "region": region}]

    return []


def _create_kb_tool(kb_name: str, kb_id: str, kb_region: str):
    """Create a retrieve tool for a specific Knowledge Base."""
    client = boto3.client("bedrock-agent-runtime", region_name=kb_region)

    @tool(name=f"retrieve_{kb_name}")
    def retrieve_kb(query: str) -> str:
        f"""Search the '{kb_name}' knowledge base for relevant information.

        Args:
            query: Search query in natural language.

        Returns:
            JSON with retrieved passages from the knowledge base.
        """
        try:
            response = client.retrieve(
                knowledgeBaseId=kb_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {
                        "numberOfResults": 10,
                    }
                },
            )

            results = []
            for item in response.get("retrievalResults", []):
                content = item.get("content", {}).get("text", "")
                score = item.get("score", 0)
                source = item.get("location", {}).get("s3Location", {}).get("uri", "")
                if content:
                    results.append({
                        "text": content,
                        "score": round(score, 4) if score else None,
                        "source": source,
                    })

            return json.dumps({
                "success": True,
                "kb_name": kb_name,
                "results": results,
                "count": len(results),
            }, ensure_ascii=False)

        except Exception as exc:
            log.error("retrieve_%s failed: %s", kb_name, exc, exc_info=True)
            return json.dumps({"success": False, "error": str(exc)})

    return retrieve_kb


def get_retrieve_tools() -> list:
    """Return retrieve tools for all configured KBs."""
    kbs = _parse_kb_config()

    if not kbs:
        raise ValueError(
            "ENABLE_KNOWLEDGE_BASE=true but no KB configured. "
            "Set KNOWLEDGE_BASE_ID or KNOWLEDGE_BASE_IDS."
        )

    tools = []
    for kb in kbs:
        t = _create_kb_tool(kb["name"], kb["id"], kb["region"])
        tools.append(t)
        log.info("KB tool enabled: retrieve_%s  id=%s  region=%s", kb["name"], kb["id"], kb["region"])

    return tools
