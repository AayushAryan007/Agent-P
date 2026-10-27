"""Shared fixtures for workflow tests: scripted agent turns and a fake sandbox."""

import json
from dataclasses import dataclass, field
from typing import Any

from app.sandbox.runner import SandboxResult, SandboxSpec

FIX_SEARCH = """    result = []
    for order in orders:
        items = _items_for_order(conn, order["id"])"""
FIX_REPLACE = """    by_order: dict[int, list[dict]] = {}
    for row in conn.execute(
        "SELECT order_id, sku, quantity, unit_price_cents FROM order_items ORDER BY id"
    ):
        item = dict(row)
        by_order.setdefault(item.pop("order_id"), []).append(item)
    result = []
    for order in orders:
        items = by_order.get(order["id"], [])"""

PLAN = {
    "summary": "GET /orders is slow; check data access in list_orders.",
    "hypotheses": ["N+1 queries per order"],
    "focus_paths": ["app/repository.py", "app/main.py"],
    "analysis_goal": "Find how list_orders loads items.",
    "debugging_goal": "Remove per-order queries without changing results.",
}
ANALYSIS = {
    "entrypoint": "app/main.py:22",
    "relevant_files": ["app/repository.py"],
    "findings": [{"location": "app/repository.py:18", "observation": "one items query per order"}],
    "suspected_root_cause": "N+1 queries in list_orders",
}
DEBUG = {
    "root_cause": "list_orders issues one SELECT per order (N+1).",
    "evidence": [{"location": "app/repository.py:18", "observation": "_items_for_order inside the loop"}],
    "fix_summary": "Load all items in one query and group them by order_id.",
    "risks": [],
}
REVIEW = {
    "assessment": "Preserves ordering and empty orders.",
    "concerns": [],
    "behaviour_preserved": True,
    "recommendation": "accept",
}
NARRATIVE = {
    "problem_summary": "GET /orders was slow.",
    "root_cause": "N+1 queries.",
    "fix_summary": "Batch-load items.",
    "limitations": ["Measured on an in-memory database."],
    "next_steps": ["Add an index on order_items.order_id."],
}


def scripts(*, invalid_first: bool = True) -> dict[str, list[Any]]:
    debug_turns: list[Any] = []
    if invalid_first:
        debug_turns.append([("submit_result", {"root_cause": 42})])  # invalid → agent.output_invalid + retry
    debug_turns += [
        [
            (
                "propose_patch",
                {
                    "edits": [{"path": "app/repository.py", "search": FIX_SEARCH, "replace": FIX_REPLACE}],
                    "rationale": "batch the item query",
                },
            )
        ],
        [("submit_result", DEBUG)],
    ]
    return {
        "[role:planner]": [[("submit_result", PLAN)]],
        "[role:repo_analysis]": [
            [("search_code", {"query": "def list_orders"}), ("read_file", {"path": "../../../etc/passwd"})],
            [("read_file", {"path": "app/repository.py"}), ("run_shell", {"cmd": "id"})],
            [("submit_result", ANALYSIS)],
        ],
        "[role:debugging]": debug_turns,
        "[role:review]": [[("submit_result", REVIEW)]],
        "[role:reporter]": [[("submit_result", NARRATIVE)]],
    }


@dataclass
class FakeSandbox:
    """Writes plausible JUnit/bench output instead of running containers. For orchestration tests only."""

    image: str = "fake"
    calls: list[SandboxSpec] = field(default_factory=list)
    patched_p50: float = 9.0

    async def run(self, spec: SandboxSpec, run_id: str) -> SandboxResult:
        self.calls.append(spec)
        out = next((m.host for m in spec.mounts if m.container == "/out"), None)
        code = next((m.host for m in spec.mounts if m.container == "/workspace"), None)
        patched = code is not None and code.name == "patched"
        if spec.purpose == "test" and out is not None:
            (out / "junit.xml").write_text(
                '<testsuite tests="5">'
                + "".join(f'<testcase classname="t" name="c{i}"/>' for i in range(5))
                + "</testsuite>"
            )
            return SandboxResult(0, "5 passed", "", 10, False, False)
        if spec.purpose == "bench":
            p50 = self.patched_p50 if patched else 270.0
            line = json.dumps(
                {
                    "format": "agentp-bench-v1",
                    "name": "list_orders",
                    "unit": "ms",
                    "runs": 3,
                    "p50": p50,
                    "p95": p50,
                }
            )
            return SandboxResult(0, line, "", 10, False, False)
        return SandboxResult(0, "", "", 1, False, False)

    def cleanup_orphans(self) -> int:
        return 0
