"""Verification label rules: computed only from recorded execution results, never from model text."""

from dataclasses import dataclass
from typing import Literal

from app.evaluations.results import BenchOutcome, TestOutcome

Label = Literal["verified", "partially_verified", "not_verified"]


@dataclass(frozen=True)
class VerificationInput:
    approved: bool
    tests_after: TestOutcome | None
    bench_before: BenchOutcome | None
    bench_after: BenchOutcome | None
    benchmark_defined: bool
    min_improvement: float
    patch_touches_protected: bool


@dataclass(frozen=True)
class VerificationResult:
    label: Label
    reasons: list[str]
    improvement: float | None  # relative p50 improvement, e.g. 0.42 = 42% faster


def decide(v: VerificationInput) -> VerificationResult:
    if not v.approved:
        return VerificationResult("not_verified", ["The proposed patch was rejected by the operator."], None)

    t = v.tests_after
    if t is None or not t.ran:
        why = t.note if t and t.note else "the test suite could not be run"
        return VerificationResult("not_verified", [f"Tests did not run after the patch: {why}."], None)
    if t.collected == 0:
        return VerificationResult("not_verified", ["No tests were collected, so nothing was verified."], None)
    if not t.all_passed:
        failing = ", ".join(t.failing_tests[:5]) or f"exit code {t.exit_code}"
        return VerificationResult(
            "not_verified",
            [f"{t.failed + t.errors} of {t.collected} tests failed after the patch ({failing})."],
            None,
        )

    reasons = [f"All {t.passed} tests passed after the patch ({t.skipped} skipped)."]
    label: Label = "verified"
    improvement: float | None = None

    if not v.benchmark_defined:
        label = "partially_verified"
        reasons.append("The repository defines no benchmark, so the performance claim is not measured.")
    elif not (v.bench_before and v.bench_before.ran and v.bench_after and v.bench_after.ran):
        label = "partially_verified"
        note = (v.bench_after.note if v.bench_after and not v.bench_after.ran else None) or (
            v.bench_before.note if v.bench_before and not v.bench_before.ran else None
        )
        reasons.append(f"Benchmark results are incomplete{f': {note}' if note else ''}.")
    else:
        before, after = v.bench_before.p50, v.bench_after.p50
        assert before is not None and after is not None
        improvement = (before - after) / before if before > 0 else None
        if improvement is not None and improvement >= v.min_improvement:
            reasons.append(
                f"Benchmark p50 improved {improvement:.0%} ({before:g} → {after:g} {v.bench_after.unit}), "
                f"above the {v.min_improvement:.0%} threshold."
            )
        else:
            label = "partially_verified"
            pct = f"{improvement:.0%}" if improvement is not None else "n/a"
            reasons.append(
                f"Benchmark p50 changed by {pct} ({before:g} → {after:g}), "
                f"below the {v.min_improvement:.0%} threshold."
            )

    if v.patch_touches_protected:
        if label == "verified":
            label = "partially_verified"
        reasons.append(
            "The patch modifies test or benchmark files; originals were restored for verification, "
            "and the result is capped at partially verified."
        )
    return VerificationResult(label, reasons, improvement)
