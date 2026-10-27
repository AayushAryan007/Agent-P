"""Deterministic parsing of sandbox output: JUnit XML and AGENT-P benchmark JSON."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from defusedxml import ElementTree

MAX_FAILURES_REPORTED = 20


@dataclass
class TestOutcome:
    ran: bool  # False when the sandbox could not run the suite at all
    exit_code: int | None
    collected: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    failing_tests: list[str] = field(default_factory=list)
    timed_out: bool = False
    note: str | None = None

    @property
    def all_passed(self) -> bool:
        return (
            self.ran and self.exit_code == 0 and self.collected > 0 and self.failed == 0 and self.errors == 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "all_passed": self.all_passed}


@dataclass
class BenchOutcome:
    ran: bool
    name: str | None = None
    unit: str | None = None
    p50: float | None = None
    p95: float | None = None
    runs: int | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_junit(path: Path, exit_code: int | None, timed_out: bool) -> TestOutcome:
    if timed_out:
        return TestOutcome(ran=False, exit_code=None, timed_out=True, note="test run timed out")
    if not path.is_file():
        return TestOutcome(ran=False, exit_code=exit_code, note="no JUnit report produced")
    try:
        root = ElementTree.parse(path).getroot()
    except Exception as exc:
        return TestOutcome(
            ran=False, exit_code=exit_code, note=f"unreadable JUnit report: {type(exc).__name__}"
        )
    if root is None:
        return TestOutcome(ran=False, exit_code=exit_code, note="empty JUnit report")
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    out = TestOutcome(ran=True, exit_code=exit_code)
    for case in (c for s in suites for c in s.iter("testcase")):
        out.collected += 1
        name = f"{case.get('classname', '')}::{case.get('name', '')}".strip(":")
        if case.find("failure") is not None:
            out.failed += 1
            if len(out.failing_tests) < MAX_FAILURES_REPORTED:
                out.failing_tests.append(name)
        elif case.find("error") is not None:
            out.errors += 1
            if len(out.failing_tests) < MAX_FAILURES_REPORTED:
                out.failing_tests.append(name)
        elif case.find("skipped") is not None:
            out.skipped += 1
        else:
            out.passed += 1
    return out


def parse_bench(stdout: str, exit_code: int | None, timed_out: bool) -> BenchOutcome:
    if timed_out:
        return BenchOutcome(ran=False, note="benchmark timed out")
    if exit_code != 0:
        return BenchOutcome(ran=False, note=f"benchmark exited with {exit_code}")
    for line in reversed(stdout.strip().splitlines()):
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("format") == "agentp-bench-v1":
            try:
                return BenchOutcome(
                    ran=True,
                    name=str(data.get("name")),
                    unit=str(data.get("unit")),
                    p50=float(data["p50"]),
                    p95=float(data["p95"]) if data.get("p95") is not None else None,
                    runs=int(data["runs"]) if data.get("runs") is not None else None,
                )
            except (KeyError, TypeError, ValueError):
                return BenchOutcome(ran=False, note="benchmark output is malformed")
    return BenchOutcome(ran=False, note="no agentp-bench-v1 JSON line in benchmark output")
