"""Data access for orders."""

import sqlite3


def _items_for_order(conn: sqlite3.Connection, order_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT sku, quantity, unit_price_cents FROM order_items WHERE order_id = ? ORDER BY id",
        (order_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_orders(conn: sqlite3.Connection) -> list[dict]:
    """Return every order with its line items and total."""
    orders = conn.execute("SELECT id, customer, created_at FROM orders ORDER BY id").fetchall()
    result = []
    for order in orders:
        items = _items_for_order(conn, order["id"])
        total = sum(i["quantity"] * i["unit_price_cents"] for i in items)
        result.append({**dict(order), "items": items, "total_cents": total})
    return result
