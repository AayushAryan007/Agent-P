"""SQLite storage for the orders service."""

import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "orders.db"


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection, orders: int = 2000, items_per_order: int = 5, seed: int = 7) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            sku TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price_cents INTEGER NOT NULL
        );
        """
    )
    rng = random.Random(seed)
    conn.executemany(
        "INSERT INTO orders (id, customer, created_at) VALUES (?, ?, ?)",
        [(i, f"customer-{i % 97}", f"2026-01-{(i % 28) + 1:02d}") for i in range(1, orders + 1)],
    )
    conn.executemany(
        "INSERT INTO order_items (order_id, sku, quantity, unit_price_cents) VALUES (?, ?, ?, ?)",
        [
            (o, f"SKU-{rng.randint(1, 500):04d}", rng.randint(1, 4), rng.randint(199, 9999))
            for o in range(1, orders + 1)
            for _ in range(items_per_order)
        ],
    )
    conn.commit()
