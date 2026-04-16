"""Product list tools — activated via ENABLE_CART=true.

Persistent product list per session using DynamoDB.
The agent uses this to track products discussed, build quotes, and manage budgets.
Table: agentcore_product_lists (auto-created if missing)
"""

from __future__ import annotations

import json
import logging
import os
from decimal import Decimal

import boto3
from strands import tool

from .config import AWS_REGION

log = logging.getLogger(__name__)

TABLE_NAME = os.getenv("CART_TABLE_NAME", "agentcore_product_lists")
_ddb = None


def _get_table():
    global _ddb
    if _ddb is None:
        region = os.getenv("CART_REGION", AWS_REGION)
        log.info("Connecting to DynamoDB table=%s region=%s", TABLE_NAME, region)
        resource = boto3.resource("dynamodb", region_name=region)
        _ddb = resource.Table(TABLE_NAME)
        _ensure_table(resource)
    return _ddb


def _ensure_table(resource):
    try:
        _ddb.load()
        log.info("DynamoDB table %s exists, status=%s", TABLE_NAME, _ddb.table_status)
    except resource.meta.client.exceptions.ResourceNotFoundException:
        log.info("Creating DynamoDB table %s", TABLE_NAME)
        resource.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "session_id", "KeyType": "HASH"},
                {"AttributeName": "cveproduct", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "session_id", "AttributeType": "S"},
                {"AttributeName": "cveproduct", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        _ddb.wait_until_exists()
        log.info("Table %s created", TABLE_NAME)


def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def get_cart_tools():
    """Return the list of product list tools for the agent."""
    log.info("Product list tools enabled  table=%s", TABLE_NAME)
    return [add_to_list, get_list, remove_from_list, clear_list]


@tool
def add_to_list(
    session_id: str,
    cveproduct: str,
    product_name: str,
    unit_price: float,
    quantity: int = 1,
    department: str = "",
    line: str = "",
) -> str:
    """Add a product to the session's product list or increase its quantity.

    Use this after showing search results when the customer wants to keep
    track of products, build a quote, or plan a budget.

    Args:
        session_id: Current chat session ID.
        cveproduct: Product code from the database.
        product_name: Product name.
        unit_price: Unit price in USD.
        quantity: Quantity to add (default 1). Adds to existing quantity if product already in list.
        department: Product department (optional).
        line: Product line (optional).

    Returns:
        JSON with the updated item and running total.
    """
    print(f"[CART DEBUG] add_to_list CALLED: session={session_id} code={cveproduct} price={unit_price}")
    log.info("add_to_list CALLED: session=%s code=%s name=%s price=%s qty=%s",
             session_id, cveproduct, product_name, unit_price, quantity)
    try:
        table = _get_table()
        print(f"[CART DEBUG] got table OK: {TABLE_NAME}")
        resp = table.update_item(
            Key={"session_id": session_id, "cveproduct": cveproduct},
            UpdateExpression=(
                "SET product_name = :name, unit_price = :price, "
                "department = :dept, line_name = :ln, "
                "quantity = if_not_exists(quantity, :zero) + :qty"
            ),
            ExpressionAttributeValues={
                ":name": product_name,
                ":price": Decimal(str(unit_price)),
                ":dept": department,
                ":ln": line,
                ":qty": quantity,
                ":zero": 0,
            },
            ReturnValues="ALL_NEW",
        )
        item = resp["Attributes"]
        line_total = float(item["unit_price"]) * int(item["quantity"])

        # Get running total
        all_items = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("session_id").eq(session_id)
        ).get("Items", [])
        grand_total = sum(float(i["unit_price"]) * int(i["quantity"]) for i in all_items)

        log.info("add_to_list OK: code=%s qty=%s total=%.2f items=%d",
                 cveproduct, item["quantity"], grand_total, len(all_items))

        return json.dumps({
            "success": True,
            "action": "added",
            "item": {
                "cveproduct": cveproduct,
                "product_name": product_name,
                "quantity": int(item["quantity"]),
                "unit_price": float(item["unit_price"]),
                "line_total": round(line_total, 2),
            },
            "list_total": round(grand_total, 2),
            "item_count": len(all_items),
        }, ensure_ascii=False, default=_decimal_default)
    except Exception as exc:
        print(f"[CART DEBUG] add_to_list FAILED: {type(exc).__name__}: {exc}")
        log.error("add_to_list failed: %s", exc, exc_info=True)
        return json.dumps({"success": False, "error": str(exc)})


@tool
def get_list(session_id: str) -> str:
    """Get all products in the session's product list with totals.

    Use this to recall what products the customer has selected so far,
    to build quotes, check budget usage, or summarize the session.

    Args:
        session_id: Current chat session ID.

    Returns:
        JSON with all items (code, name, qty, price, line total), count, and grand total.
    """
    log.info("get_list CALLED: session=%s", session_id)
    try:
        table = _get_table()
        log.info("get_list: got table OK")
        resp = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("session_id").eq(session_id)
        )
        items = resp.get("Items", [])
        log.info("get_list: found %d items for session=%s", len(items), session_id)

        list_items = []
        grand_total = 0.0
        for item in items:
            qty = int(item["quantity"])
            price = float(item["unit_price"])
            line_total = round(qty * price, 2)
            grand_total += line_total
            list_items.append({
                "cveproduct": item["cveproduct"],
                "product_name": item.get("product_name", ""),
                "quantity": qty,
                "unit_price": price,
                "line_total": line_total,
                "department": item.get("department", ""),
                "line": item.get("line_name", ""),
            })

        return json.dumps({
            "success": True,
            "items": list_items,
            "item_count": len(list_items),
            "grand_total": round(grand_total, 2),
        }, ensure_ascii=False, default=_decimal_default)
    except Exception as exc:
        log.error("get_list failed: %s", exc, exc_info=True)
        return json.dumps({"success": False, "error": str(exc)})


@tool
def remove_from_list(session_id: str, cveproduct: str) -> str:
    """Remove a product from the session's product list.

    Args:
        session_id: Current chat session ID.
        cveproduct: Product code to remove.

    Returns:
        JSON confirming removal and updated total.
    """
    table = _get_table()
    try:
        log.info("remove_from_list: session=%s code=%s", session_id, cveproduct)
        table.delete_item(Key={"session_id": session_id, "cveproduct": cveproduct})

        # Get updated total
        all_items = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("session_id").eq(session_id)
        ).get("Items", [])
        grand_total = sum(float(i["unit_price"]) * int(i["quantity"]) for i in all_items)

        return json.dumps({
            "success": True,
            "action": "removed",
            "cveproduct": cveproduct,
            "list_total": round(grand_total, 2),
            "item_count": len(all_items),
        })
    except Exception as exc:
        log.error("remove_from_list failed: %s", exc, exc_info=True)
        return json.dumps({"success": False, "error": str(exc)})


@tool
def clear_list(session_id: str) -> str:
    """Clear all products from the session's product list.

    Args:
        session_id: Current chat session ID.

    Returns:
        JSON confirming the list was cleared.
    """
    table = _get_table()
    try:
        log.info("clear_list: session=%s", session_id)
        resp = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("session_id").eq(session_id),
            ProjectionExpression="session_id, cveproduct",
        )
        with table.batch_writer() as batch:
            for item in resp.get("Items", []):
                batch.delete_item(Key={
                    "session_id": item["session_id"],
                    "cveproduct": item["cveproduct"],
                })
        return json.dumps({"success": True, "action": "cleared"})
    except Exception as exc:
        log.error("clear_list failed: %s", exc, exc_info=True)
        return json.dumps({"success": False, "error": str(exc)})
