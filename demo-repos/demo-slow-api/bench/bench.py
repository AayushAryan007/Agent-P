"""Benchmark for list_orders(). Prints one JSON object to stdout (AGENT-P benchmark format v1)."""

import json
import statistics
import time

from app.db import connect, init_db
from app.repository import list_orders

RUNS = 15
WARMUP = 2


def main() -> None:
    conn = connect(":memory:")
    init_db(conn, orders=2000, items_per_order=5)
    samples = []
    for i in range(WARMUP + RUNS):
        start = time.perf_counter()
        rows = list_orders(conn)
        elapsed = (time.perf_counter() - start) * 1000
        if i >= WARMUP:
            samples.append(elapsed)
    assert len(rows) == 2000
    samples.sort()
    print(
        json.dumps(
            {
                "format": "agentp-bench-v1",
                "name": "list_orders",
                "unit": "ms",
                "runs": RUNS,
                "p50": round(statistics.median(samples), 3),
                "p95": round(samples[int(0.95 * (len(samples) - 1))], 3),
                "min": round(samples[0], 3),
            }
        )
    )


if __name__ == "__main__":
    main()
