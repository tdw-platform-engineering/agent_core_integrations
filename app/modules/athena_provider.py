"""Athena query tool — invokes the api-query-athena Lambda directly.

Activated via ENABLE_ATHENA=true.
"""

from __future__ import annotations

import json
import logging

import boto3
from strands import tool

from .config import AWS_REGION

log = logging.getLogger(__name__)

LAMBDA_FUNCTION_NAME = None
_lambda_client = None


def _get_client():
    global _lambda_client
    if _lambda_client is None:
        import os
        region = os.getenv("ATHENA_LAMBDA_REGION", AWS_REGION)
        _lambda_client = boto3.client("lambda", region_name=region)
    return _lambda_client


def get_athena_tool(function_name: str):
    """Return the Strands @tool for querying Athena via Lambda."""
    global LAMBDA_FUNCTION_NAME
    LAMBDA_FUNCTION_NAME = function_name
    log.info("Athena tool enabled  lambda=%s", function_name)
    return execute_sql_query


@tool
def execute_sql_query(query: str) -> str:
    """Run a read-only SQL SELECT on the product database (Athena). Use for prices, stock, and MBA complementary products.

    Args:
        query: SQL SELECT query. Only read operations allowed.
    """
    client = _get_client()

    try:
        payload = json.dumps({"query": query})

        response = client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType="RequestResponse",
            Payload=payload.encode(),
        )

        result = json.loads(response["Payload"].read().decode())

        # Lambda behind API Gateway wraps in statusCode/body
        if "body" in result:
            body = json.loads(result["body"]) if isinstance(result["body"], str) else result["body"]
        else:
            body = result

        if not body.get("success"):
            error_msg = body.get("error", "Unknown error")
            log.warning("Athena query failed: %s", error_msg)
            return json.dumps({"success": False, "error": error_msg})

        # Return data + minimal metadata
        return json.dumps({
            "success": True,
            "data": body.get("data", []),
            "rowCount": body.get("metadata", {}).get("rowCount", 0),
        }, ensure_ascii=False)

    except Exception as exc:
        log.error("Lambda invocation failed: %s", exc, exc_info=True)
        return json.dumps({"success": False, "error": str(exc)})
