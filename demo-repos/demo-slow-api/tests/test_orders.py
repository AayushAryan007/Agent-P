import pytest
from fastapi.testclient import TestClient

from app.db import connect, init_db
from app.main import app, get_conn
from app.repository import list_orders


@pytest.fixture
def conn():
    c = connect(":memory:")
    init_db(c, orders=50, items_per_order=3)
    yield c
    c.close()


@pytest.fixture
def client(conn):
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_lists_every_order(client):
    body = client.get("/orders").json()
    assert len(body) == 50
    assert [o["id"] for o in body] == list(range(1, 51))


def test_items_are_attached_in_insertion_order(conn):
    orders = list_orders(conn)
    first = orders[0]
    expected = conn.execute(
        "SELECT sku, quantity, unit_price_cents FROM order_items WHERE order_id = 1 ORDER BY id"
    ).fetchall()
    assert first["items"] == [dict(r) for r in expected]


def test_totals_are_correct(conn):
    for order in list_orders(conn):
        assert order["total_cents"] == sum(i["quantity"] * i["unit_price_cents"] for i in order["items"])


def test_order_without_items_has_empty_list_and_zero_total(conn):
    conn.execute("INSERT INTO orders (id, customer, created_at) VALUES (999, 'x', '2026-02-01')")
    order = next(o for o in list_orders(conn) if o["id"] == 999)
    assert order["items"] == [] and order["total_cents"] == 0
