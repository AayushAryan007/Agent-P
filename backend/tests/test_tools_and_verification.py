"""Unit tests: repository tools and path policy, patch application, result parsing, verification rules."""

import os
from pathlib import Path

import pytest

from app.evaluations.results import BenchOutcome, TestOutcome, parse_bench, parse_junit
from app.evaluations.verification import VerificationInput, decide
from app.orchestrator.budget import Budget, BudgetExceeded
from app.orchestrator.transitions import InvalidTransition, check_run, check_step
from app.tools.base import PolicyViolation, ToolContext, ToolError, json_schema_for
from app.tools.patch import Edit, ProposePatchArgs, apply_edits, propose_patch
from app.tools.paths import resolve_in_repo
from app.tools.repo import ReadFileArgs, SearchCodeArgs, read_file, search_code


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("def f():\n    return 1\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[secret]")
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("secret")
    os.symlink(outside, tmp_path / "link.txt")
    return tmp_path


@pytest.mark.parametrize("path", ["../x", "/etc/passwd", "pkg/../../x", ".git/config", "link.txt", "a\x00b"])
def test_path_policy_blocks_escapes(repo: Path, path: str) -> None:
    with pytest.raises(PolicyViolation):
        resolve_in_repo(repo, path)


async def test_read_and_search(repo: Path) -> None:
    ctx = ToolContext(repo)
    out = await read_file(ctx, ReadFileArgs(path="pkg/a.py"))
    assert "    1  def f():" in out.model_content["content"]
    hits = (await search_code(ctx, SearchCodeArgs(query="return"))).model_content["hits"]
    assert hits == [{"path": "pkg/a.py", "line": 2, "text": "return 1"}]
    with pytest.raises(ToolError):
        await read_file(ctx, ReadFileArgs(path="pkg"))


async def test_propose_patch_requires_unique_match_and_produces_diff(repo: Path) -> None:
    ctx = ToolContext(repo)
    with pytest.raises(ToolError, match="found 0 times"):
        apply_edits(repo, [Edit(path="pkg/a.py", search="nope", replace="x")])
    out = await propose_patch(
        ctx,
        ProposePatchArgs(edits=[Edit(path="pkg/a.py", search="return 1", replace="return 2")], rationale="r"),
    )
    assert out.summary == {"applies_cleanly": True, "files": ["pkg/a.py"], "additions": 1, "deletions": 1}
    assert out.artifact is not None and "-    return 1\n+    return 2" in (out.artifact.text or "")
    assert (repo / "pkg" / "a.py").read_text() == "def f():\n    return 1\n"  # nothing applied


def test_tool_schemas_are_inlined() -> None:
    schema = json_schema_for(ProposePatchArgs)
    assert "$defs" not in str(schema) and "$ref" not in str(schema)
    assert schema["properties"]["edits"]["items"]["required"] == ["path", "search", "replace"]


def test_parse_junit_and_bench(tmp_path: Path) -> None:
    junit = tmp_path / "j.xml"
    junit.write_text(
        '<testsuites><testsuite><testcase classname="t" name="ok"/><testcase classname="t" name="bad"><failure/></testcase>'
        '<testcase classname="t" name="s"><skipped/></testcase></testsuite></testsuites>'
    )
    t = parse_junit(junit, 1, False)
    assert (t.collected, t.passed, t.failed, t.skipped, t.failing_tests) == (3, 1, 1, 1, ["t::bad"])
    assert not t.all_passed
    assert parse_junit(tmp_path / "missing.xml", 0, False).ran is False
    b = parse_bench(
        'noise\n{"format":"agentp-bench-v1","name":"x","unit":"ms","p50":12.5,"p95":13,"runs":5}\n', 0, False
    )
    assert b.ran and b.p50 == 12.5
    assert not parse_bench("{}", 0, False).ran


def _passing() -> TestOutcome:
    return TestOutcome(ran=True, exit_code=0, collected=5, passed=5)


def _bench(p50: float) -> BenchOutcome:
    return BenchOutcome(ran=True, name="b", unit="ms", p50=p50)


@pytest.mark.parametrize(
    ("inp", "label"),
    [
        (dict(approved=False), "not_verified"),
        (dict(tests_after=TestOutcome(ran=False, exit_code=None, note="timeout")), "not_verified"),
        (dict(tests_after=TestOutcome(ran=True, exit_code=5, collected=0)), "not_verified"),
        (
            dict(tests_after=TestOutcome(ran=True, exit_code=1, collected=5, passed=4, failed=1)),
            "not_verified",
        ),
        (dict(), "verified"),
        (dict(bench_after=_bench(95)), "partially_verified"),  # 5% < 10% threshold
        (dict(benchmark_defined=False, bench_before=None, bench_after=None), "partially_verified"),
        (dict(bench_after=BenchOutcome(ran=False, note="crashed")), "partially_verified"),
        (dict(patch_touches_protected=True), "partially_verified"),
    ],
)
def test_verification_label_rules(inp: dict[str, object], label: str) -> None:
    base: dict[str, object] = dict(
        approved=True,
        tests_after=_passing(),
        bench_before=_bench(100),
        bench_after=_bench(10),
        benchmark_defined=True,
        min_improvement=0.10,
        patch_touches_protected=False,
    )
    assert decide(VerificationInput(**{**base, **inp})).label == label  # type: ignore[arg-type]


def test_transitions_reject_illegal_moves() -> None:
    check_run("queued", "running")
    check_step("waiting_approval", "completed")
    with pytest.raises(InvalidTransition):
        check_run("completed", "running")
    with pytest.raises(InvalidTransition):
        check_step("pending", "completed")


def test_budget_limits_and_pause() -> None:
    b = Budget.from_limits(
        {"max_minutes": 1, "max_llm_calls": 2, "max_total_tokens": 1000, "max_tool_calls": 1}
    )
    b.record_llm(100, 10)
    b.record_llm(100, 10)
    with pytest.raises(BudgetExceeded) as e:
        b.check_llm()
    assert e.value.kind == "llm_calls"
    b.tool_calls = 1
    with pytest.raises(BudgetExceeded):
        b.check_tool()
    b.pause()
    assert b._paused_at is not None
    b.resume()
    assert b._paused_at is None


def test_patch_tolerates_wrong_indentation_but_not_ambiguity(tmp_path: Path) -> None:
    src = "class A:\n    def f(self):\n        x = 1\n        return x\n"
    (tmp_path / "m.py").write_text(src)
    files = apply_edits(tmp_path, [Edit(path="m.py", search="  x = 1\n  return x", replace="  return 1")])
    assert files["m.py"][1] == "class A:\n    def f(self):\n        return 1\n"
    (tmp_path / "d.py").write_text("a = 1\nif x:\n    a = 1\n")
    with pytest.raises(ToolError, match="found 2 times"):
        apply_edits(tmp_path, [Edit(path="d.py", search="a = 1", replace="a = 2")])
    with pytest.raises(ToolError, match="line-number prefixes"):
        apply_edits(tmp_path, [Edit(path="m.py", search="    3          x = 2", replace="")])
