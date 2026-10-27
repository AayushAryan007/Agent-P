"""Orders API. GET /orders is reported as slow in production."""

import sqlite3

from fastapi import Depends, FastAPI

from app.db import connect, init_db
from app.repository import list_orders

app = FastAPI(title="orders")
_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = connect()
        init_db(_conn)
    return _conn


@app.get("/orders")
def get_orders(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return list_orders(conn)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
