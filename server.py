"""Business MCP tools for product and purchase-order lookups."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastmcp import FastMCP
from psycopg.rows import dict_row

from db import get_connection

mcp = FastMCP("business-mcp")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (date, datetime, UUID)):
        return value.isoformat() if not isinstance(value, UUID) else str(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


@mcp.tool
def search_products(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search product models and parts by matching database text fields."""
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")
    pattern = f"%{query}%"
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT m.id AS model_id, m.model_code, m.name AS model_name,
                   p.id AS part_id, p.part_number, p.name AS part_name,
                   p.category AS part_category
            FROM part p
            LEFT JOIN model_part mp ON mp.part_id = p.id
            LEFT JOIN product_model m ON m.id = mp.model_id
            WHERE p.part_number ILIKE %s
               OR p.name ILIKE %s
               OR p.category ILIKE %s
               OR m.model_code ILIKE %s
               OR m.name ILIKE %s
            ORDER BY p.part_number, m.model_code
            LIMIT %s
            """,
            (pattern, pattern, pattern, pattern, pattern, limit),
        )
        return _json_safe(cur.fetchall())


@mcp.tool
def get_product(identifier: str) -> list[dict[str, Any]]:
    """Get product(s) by exact serial number or model code, including model parts."""
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT pr.id AS product_id, pr.serial_number, pr.manufactured_on,
                   m.id AS model_id, m.model_code, m.name AS model_name,
                   part.id AS part_id, part.part_number, part.name AS part_name,
                   part.category AS part_category
            FROM product pr
            JOIN product_model m ON m.id = pr.model_id
            LEFT JOIN model_part mp ON mp.model_id = m.id
            LEFT JOIN part ON part.id = mp.part_id
            WHERE pr.serial_number = %s OR m.model_code = %s
            ORDER BY pr.serial_number, part.part_number
            LIMIT 100
            """,
            (identifier, identifier),
        )
        return _json_safe(cur.fetchall())


@mcp.tool
def search_past_orders(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search purchase orders by case, status, requester, or ordered part text."""
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")
    pattern = f"%{query}%"
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT DISTINCT po.id AS purchase_order_id, po.case_reference,
                   po.status, po.created_at, requester.name AS requester_name
            FROM purchase_order po
            JOIN app_user requester ON requester.id = po.requested_by
            LEFT JOIN purchase_order_item poi ON poi.order_id = po.id
            LEFT JOIN part p ON p.id = poi.part_id
            WHERE po.case_reference ILIKE %s
               OR po.status::text ILIKE %s
               OR requester.name ILIKE %s
               OR p.part_number ILIKE %s
               OR p.name ILIKE %s
               OR CAST(po.id AS text) = %s
            ORDER BY po.created_at DESC, po.id DESC
            LIMIT %s
            """,
            (pattern, pattern, pattern, pattern, pattern, query, limit),
        )
        return _json_safe(cur.fetchall())


@mcp.tool
def get_part_availability(part_id: int) -> dict[str, Any]:
    """Return exact warehouse stock and supplier/factory lead-time information."""
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, part_number, name, category
            FROM part WHERE id = %s
            """,
            (part_id,),
        )
        part = cur.fetchone()
        if part is None:
            raise ValueError(f"Unknown part_id: {part_id}")
        cur.execute(
            """
            SELECT w.id AS warehouse_id, w.name AS warehouse_name,
                   w.region, i.on_hand, i.reserved,
                   i.on_hand - i.reserved AS available
            FROM inventory i
            JOIN warehouse w ON w.id = i.warehouse_id
            WHERE i.part_id = %s
            ORDER BY w.region, w.name
            """,
            (part_id,),
        )
        warehouses = cur.fetchall()
        cur.execute(
            """
            SELECT f.id AS factory_id, f.name AS factory_name,
                   f.country, f.region, f.address, f.phone, ps.lead_days
            FROM part_supplier ps
            JOIN factory f ON f.id = ps.factory_id
            WHERE ps.part_id = %s
            ORDER BY ps.lead_days NULLS LAST, f.name
            """,
            (part_id,),
        )
        suppliers = cur.fetchall()
        return _json_safe({"part": part, "warehouses": warehouses, "suppliers": suppliers})


@mcp.tool
def create_purchase_order_draft(
    requested_by: int,
    items: list[dict[str, Any]],
    case_reference: str | None = None,
) -> dict[str, Any]:
    """Create a PENDING order draft. A quality manager must approve it."""
    if not items:
        raise ValueError("At least one order item is required")
    with get_connection() as conn, conn.transaction(), conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id FROM app_user WHERE id = %s AND active AND role = 'TECHNICIAN'",
            (requested_by,),
        )
        if cur.fetchone() is None:
            raise ValueError("requested_by must be an active TECHNICIAN user")

        request_key = uuid4()
        cur.execute(
            """
            INSERT INTO purchase_order (case_reference, request_key, requested_by)
            VALUES (%s, %s, %s)
            RETURNING id, case_reference, request_key, status, created_at
            """,
            (case_reference, request_key, requested_by),
        )
        order = cur.fetchone()
        for item in items:
            warehouse_id = item.get("warehouse_id")
            factory_id = item.get("factory_id")
            if (warehouse_id is None) == (factory_id is None):
                raise ValueError("Each item needs exactly one of warehouse_id or factory_id")
            quantity = item.get("quantity")
            if type(quantity) is not int or quantity <= 0:
                raise ValueError("Each item quantity must be a positive integer")
            part_id = item.get("part_id")
            cur.execute(
                """
                INSERT INTO purchase_order_item
                    (order_id, part_id, quantity, warehouse_id, factory_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, part_id, quantity, warehouse_id, factory_id
                """,
                (order["id"], part_id, quantity, warehouse_id, factory_id),
            )
        cur.execute(
            """
            SELECT poi.id, poi.part_id, p.part_number, p.name AS part_name,
                   poi.quantity, poi.warehouse_id, poi.factory_id
            FROM purchase_order_item poi
            JOIN part p ON p.id = poi.part_id
            WHERE poi.order_id = %s
            ORDER BY poi.id
            """,
            (order["id"],),
        )
        order["items"] = cur.fetchall()
        return _json_safe(order)


@mcp.tool
def get_purchase_order(order_id: int) -> dict[str, Any]:
    """Get a purchase order, its current approval status, and line items."""
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT po.id, po.case_reference, po.status, po.requested_by,
                   requester.name AS requester_name, po.decided_by,
                   approver.name AS approver_name, po.decision_note,
                   po.decided_at, po.created_at
            FROM purchase_order po
            JOIN app_user requester ON requester.id = po.requested_by
            LEFT JOIN app_user approver ON approver.id = po.decided_by
            WHERE po.id = %s
            """,
            (order_id,),
        )
        order = cur.fetchone()
        if order is None:
            raise ValueError(f"Unknown order_id: {order_id}")
        cur.execute(
            """
            SELECT poi.id, poi.part_id, p.part_number, p.name AS part_name,
                   poi.quantity, poi.warehouse_id, w.name AS warehouse_name,
                   poi.factory_id, f.name AS factory_name
            FROM purchase_order_item poi
            JOIN part p ON p.id = poi.part_id
            LEFT JOIN warehouse w ON w.id = poi.warehouse_id
            LEFT JOIN factory f ON f.id = poi.factory_id
            WHERE poi.order_id = %s
            ORDER BY poi.id
            """,
            (order_id,),
        )
        order["items"] = cur.fetchall()
        return _json_safe(order)


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8000,
        show_banner=False,
    )
