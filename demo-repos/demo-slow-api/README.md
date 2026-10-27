# demo-slow-api

A small FastAPI + SQLite orders service used as AGENT-P's bundled demo repository.

`GET /orders` is slow. The tests pass; the benchmark (`python -m bench.bench`) measures `list_orders()` over 2,000 orders.

```bash
pip install fastapi httpx pytest
python -m pytest -q
python -m bench.bench
```
