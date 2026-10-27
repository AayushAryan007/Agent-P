"""Step implementations for the slow-endpoint-v1 template.

Agent steps call the model through `run_agent`. System steps are deterministic: they never call
the model, and the verification label is computed only from sandbox results.
"""

import asyncio
import json
import shutil
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select, update

from app.agents.definitions import DEBUGGER, PLANNER, REPO_ANALYST, REPORTER, REVIEWER
from app.evaluations.results import BenchOutcome, TestOutcome, parse_bench, parse_junit
from app.evaluations.verification import VerificationInput, decide
from app.orchestrator.agent_loop import AgentFailed, run_agent, untrusted
from app.orchestrator.context import RunContext, StepInfo
from app.orchestrator.templates import BUNDLED_REPOS
from app.orchestrator.workspace import VerifyConfig, Workspace, WorkspaceError
from app.persistence.models import ApprovalRequest, Artifact
from app.sandbox.runner import Mount, SandboxSpec
from app.tools.base import ArtifactDraft, ToolContext
from app.tools.patch import Edit
from app.tools.repo import ListTreeArgs, list_tree


class StepSkipped(Exception):
    pass


class StepFailed(Exception):
    pass


StepFn = Callable[[RunContext, StepInfo], Awaitable[dict[str, Any]]]


def _tool_ctx(ctx: RunContext) -> ToolContext:
    return ToolContext(repo_root=ctx.workspace.repo)


def _verify_config(ctx: RunContext) -> VerifyConfig:
    cfg = ctx.outputs["prepare_workspace"]["verify_config"]
    return VerifyConfig(**{k: v for k, v in cfg.items()})


# ---- sandbox helpers ------------------------------------------------------------------------


async def _sandboxed(ctx: RunContext, step: StepInfo, spec: SandboxSpec) -> Any:
    await ctx.emit(
        "sandbox.started",
        {
            "purpose": spec.purpose,
            "image": ctx.sandbox.image,
            "network": spec.network,
            "limits": {"timeout_s": spec.timeout_s, "memory_mb": spec.memory_mb, "cpus": spec.cpus},
        },
        step_id=step.id,
    )
    result = await ctx.sandbox.run(spec, str(ctx.run_id))
    await ctx.emit(
        "sandbox.finished",
        {
            "purpose": spec.purpose,
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
            "timed_out": result.timed_out,
            "oom_killed": result.oom_killed,
            "stdout_tail": result.stdout[-1500:],
            "stderr_tail": result.stderr[-1500:],
        },
        step_id=step.id,
    )
    return result


def _code_mounts(ws: Workspace, code_dir: str, out: Any) -> list[Mount]:
    mounts = [Mount(ws.root / code_dir, "/workspace", read_only=True), Mount(out, "/out", read_only=False)]
    if ws.deps.exists():
        mounts.append(Mount(ws.deps, "/deps", read_only=True))
    return mounts


def _code_env(ws: Workspace) -> dict[str, str]:
    return {"PYTHONPATH": "/workspace:/deps" if ws.deps.exists() else "/workspace"}


async def _run_tests(ctx: RunContext, step: StepInfo, code_dir: str, label: str) -> tuple[TestOutcome, str]:
    cfg = _verify_config(ctx)
    out = ctx.workspace.out_dir(f"{label}-tests")
    r = await _sandboxed(
        ctx,
        step,
        SandboxSpec(
            "test",
            cfg.test_command,
            _code_mounts(ctx.workspace, code_dir, out),
            timeout_s=300,
            env=_code_env(ctx.workspace),
        ),
    )
    outcome = parse_junit(out / "junit.xml", r.exit_code, r.timed_out)
    return outcome, (r.stdout + "\n" + r.stderr)[-6000:]


async def _run_bench(ctx: RunContext, step: StepInfo, code_dir: str, label: str) -> BenchOutcome | None:
    cfg = _verify_config(ctx)
    if not cfg.benchmark_command:
        return None
    out = ctx.workspace.out_dir(f"{label}-bench")
    r = await _sandboxed(
        ctx,
        step,
        SandboxSpec(
            "bench",
            cfg.benchmark_command,
            _code_mounts(ctx.workspace, code_dir, out),
            timeout_s=180,
            env=_code_env(ctx.workspace),
        ),
    )
    return parse_bench(r.stdout, r.exit_code, r.timed_out)


# ---- steps ----------------------------------------------------------------------------------


async def prepare_workspace(ctx: RunContext, step: StepInfo) -> dict[str, Any]:
    ws = ctx.workspace
    ws.create()
    src = ctx.task.repo_source
    if src["kind"] == "bundled":
        repo = BUNDLED_REPOS[src["key"]]
        ws.copy_bundled(ctx.settings.bundled_repos_root / repo.path.removeprefix("demo-repos/"))
    else:
        clone_dir = ws.root / "clone"
        clone_dir.mkdir(exist_ok=True)
        clone_dir.chmod(0o777)
        r = await _sandboxed(
            ctx,
            step,
            SandboxSpec(
                "clone",
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--single-branch",
                    "--no-recurse-submodules",
                    src["url"],
                    "/clone/repo",
                ],
                [Mount(clone_dir, "/clone", read_only=False)],
                network=True,
                timeout_s=90,
                workdir="/clone",
                env={"GIT_LFS_SKIP_SMUDGE": "1"},
            ),
        )
        if r.exit_code != 0:
            raise StepFailed(f"git clone failed (exit {r.exit_code}): {r.stderr[-300:]}")
        if ws.repo.exists():
            shutil.rmtree(ws.repo)
        (clone_dir / "repo").rename(ws.repo)
        shutil.rmtree(ws.repo / ".git", ignore_errors=True)
    try:
        stats = ws.check_limits(ctx.settings.repo_max_mb, ctx.settings.repo_max_files)
        cfg = ws.verify_config()
    except WorkspaceError as exc:
        raise StepFailed(str(exc)) from exc

    if src["kind"] == "github" and (ws.repo / "requirements.txt").is_file():
        ws.deps.mkdir(exist_ok=True)
        ws.deps.chmod(0o777)
        r = await _sandboxed(
            ctx,
            step,
            SandboxSpec(
                "install",
                [
                    "python",
                    "-m",
                    "pip",
                    "install",
                    "--no-cache-dir",
                    "--target",
                    "/deps",
                    "-r",
                    "/workspace/requirements.txt",
                ],
                [Mount(ws.repo, "/workspace", read_only=True), Mount(ws.deps, "/deps", read_only=False)],
                network=True,
                timeout_s=180,
                memory_mb=1536,
            ),
        )
        if r.exit_code != 0:
            raise StepFailed(f"dependency install failed (exit {r.exit_code}): {r.stderr[-300:]}")

    tree = await list_tree(_tool_ctx(ctx), ListTreeArgs(path=".", depth=3))
    return {
        "source": src["kind"],
        **stats,
        "verify_config": cfg.to_dict(),
        "layout": tree.model_content["entries"],
    }


async def plan(ctx: RunContext, step: StepInfo) -> dict[str, Any]:
    layout = "\n".join(ctx.outputs["prepare_workspace"]["layout"])
    prompt = (
        f"Task goal (from the operator):\n{ctx.task.goal}\n\n"
        f"Repository layout:\n{untrusted('repository layout', layout)}"
    )
    run = await run_agent(ctx, step, PLANNER, prompt, _tool_ctx(ctx))
    return run.output.model_dump()


async def baseline(ctx: RunContext, step: StepInfo) -> dict[str, Any]:
    tests, log = await _run_tests(ctx, step, "repo", "baseline")
    bench = await _run_bench(ctx, step, "repo", "baseline")
    await ctx.store_artifact(
        step.key,
        ArtifactDraft(
            "test_report", "baseline-tests.json", "application/json", text=log, json=tests.to_dict()
        ),
    )
    if bench:
        await ctx.store_artifact(
            step.key,
            ArtifactDraft("benchmark", "baseline-bench.json", "application/json", json=bench.to_dict()),
        )
    return {"tests": tests.to_dict(), "bench": bench.to_dict() if bench else None}


async def analyze(ctx: RunContext, step: StepInfo) -> dict[str, Any]:
    p = ctx.outputs["plan"]
    prompt = (
        f"Task goal:\n{ctx.task.goal}\n\nCoordinator instruction:\n{p['analysis_goal']}\n\n"
        f"Hypotheses to check:\n- "
        + "\n- ".join(p["hypotheses"])
        + "\n\nStart with: "
        + ", ".join(p["focus_paths"])
    )
    run = await run_agent(ctx, step, REPO_ANALYST, prompt, _tool_ctx(ctx))
    return run.output.model_dump()


async def debug(ctx: RunContext, step: StepInfo) -> dict[str, Any]:
    p = ctx.outputs["plan"]
    prompt = (
        f"Task goal:\n{ctx.task.goal}\n\nCoordinator instruction:\n{p['debugging_goal']}\n\n"
        f"Repository analysis (from the analysis agent):\n{json.dumps(ctx.outputs['analyze'], indent=2)}"
    )
    run = await run_agent(ctx, step, DEBUGGER, prompt, _tool_ctx(ctx))
    if not run.artifacts:
        raise StepFailed("the debugging agent finished without a successful propose_patch")
    return {**run.output.model_dump(), "patch_artifact_id": str(run.artifacts[-1])}


async def approve_patch(ctx: RunContext, step: StepInfo) -> dict[str, Any]:
    d = ctx.outputs["debug"]
    artifact_id = uuid.UUID(d["patch_artifact_id"])
    async with ctx.db.sessionmaker() as s:
        approval = ApprovalRequest(
            run_id=ctx.run_id,
            step_id=step.id,
            kind="apply_patch",
            artifact_id=artifact_id,
            summary=d["fix_summary"][:2000],
        )
        s.add(approval)
        await s.flush()
        approval_id = approval.id
        await s.commit()
    await ctx.set_step_status(
        step.key,
        "waiting_approval",
        "approval.requested",
        {
            "approval_id": str(approval_id),
            "kind": "apply_patch",
            "artifact_id": str(artifact_id),
            "summary": d["fix_summary"][:500],
        },
    )
    await ctx.set_run_status(
        "waiting_approval", "workflow.waiting_approval", {"approval_id": str(approval_id)}
    )

    ctx.budget.pause()
    deadline = time.monotonic() + ctx.settings.approval_timeout_s
    try:
        while True:
            async with ctx.db.sessionmaker() as s:
                a = await s.scalar(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
            assert a is not None
            if a.status in ("approved", "rejected"):
                decision, comment = a.status, a.comment
                break
            if a.status == "cancelled":
                raise StepFailed("approval was cancelled")
            if time.monotonic() > deadline:
                async with ctx.db.sessionmaker() as s:
                    await s.execute(
                        update(ApprovalRequest)
                        .where(ApprovalRequest.id == approval_id, ApprovalRequest.status == "pending")
                        .values(status="cancelled")
                    )
                    await s.commit()
                raise StepFailed("approval timed out")
            await asyncio.sleep(1.0)
    finally:
        ctx.budget.resume()

    await ctx.set_run_status(
        "running", "workflow.resumed", {"approval_id": str(approval_id), "decision": decision}
    )
    return {"approval_id": str(approval_id), "decision": decision, "comment": comment}


async def verify(ctx: RunContext, step: StepInfo) -> dict[str, Any]:
    if ctx.outputs["approve_patch"]["decision"] != "approved":
        raise StepSkipped("patch was rejected")
    cfg = _verify_config(ctx)
    async with ctx.db.sessionmaker() as s:
        patch = await s.scalar(
            select(Artifact).where(Artifact.id == uuid.UUID(ctx.outputs["debug"]["patch_artifact_id"]))
        )
    assert patch is not None and patch.inline_json is not None
    edits = [Edit(**e) for e in patch.inline_json["edits"]]
    touched = ctx.workspace.build_patched(edits, cfg.protected_paths)

    tests, log = await _run_tests(ctx, step, "patched", "patched")
    bench_after = await _run_bench(ctx, step, "patched", "patched") if tests.all_passed else None
    base = ctx.outputs["baseline"]
    bench_before = BenchOutcome(**base["bench"]) if base.get("bench") else None

    result = decide(
        VerificationInput(
            approved=True,
            tests_after=tests,
            bench_before=bench_before,
            bench_after=bench_after,
            benchmark_defined=cfg.benchmark_command is not None,
            min_improvement=cfg.min_improvement,
            patch_touches_protected=bool(touched),
        )
    )
    await ctx.store_artifact(
        step.key,
        ArtifactDraft(
            "test_report", "patched-tests.json", "application/json", text=log, json=tests.to_dict()
        ),
    )
    if bench_after:
        await ctx.store_artifact(
            step.key,
            ArtifactDraft("benchmark", "patched-bench.json", "application/json", json=bench_after.to_dict()),
        )
    return {
        "label": result.label,
        "reasons": result.reasons,
        "improvement": result.improvement,
        "tests_before": base["tests"],
        "tests_after": tests.to_dict(),
        "bench_before": base.get("bench"),
        "bench_after": bench_after.to_dict() if bench_after else None,
        "touched_protected": touched,
    }


async def review(ctx: RunContext, step: StepInfo) -> dict[str, Any]:
    if "verify" in ctx.skipped:
        raise StepSkipped("nothing to review: the patch was not applied")
    async with ctx.db.sessionmaker() as s:
        patch = await s.scalar(
            select(Artifact).where(Artifact.id == uuid.UUID(ctx.outputs["debug"]["patch_artifact_id"]))
        )
    assert patch is not None
    v = ctx.outputs["verify"]
    prompt = (
        f"Task goal:\n{ctx.task.goal}\n\n"
        f"Debugging agent's explanation:\n{json.dumps(ctx.outputs['debug'], indent=2)}\n\n"
        f"Proposed patch:\n{untrusted('patch', (patch.inline_text or '')[:12000])}\n\n"
        f"Recorded verification results (from the sandbox, authoritative):\n"
        + json.dumps(
            {
                k: v[k]
                for k in (
                    "label",
                    "reasons",
                    "tests_after",
                    "bench_before",
                    "bench_after",
                    "touched_protected",
                )
            },
            indent=2,
        )
    )
    run = await run_agent(ctx, step, REVIEWER, prompt, _tool_ctx(ctx))
    return run.output.model_dump()


async def report(ctx: RunContext, step: StepInfo) -> dict[str, Any]:
    decision = ctx.outputs.get("approve_patch", {}).get("decision")
    if "verify" in ctx.outputs:
        label, reasons = ctx.outputs["verify"]["label"], ctx.outputs["verify"]["reasons"]
    else:
        label = "not_verified"
        reasons = (
            ["The proposed patch was rejected by the operator."]
            if decision == "rejected"
            else ["Verification did not run."]
        )

    recorded = {
        "goal": ctx.task.goal,
        "verification": {"label": label, "reasons": reasons},
        "plan": ctx.outputs.get("plan"),
        "analysis": ctx.outputs.get("analyze"),
        "debugging": ctx.outputs.get("debug"),
        "approval": ctx.outputs.get("approve_patch"),
        "verify": ctx.outputs.get("verify"),
        "review": ctx.outputs.get("review"),
    }
    try:
        run = await run_agent(
            ctx,
            step,
            REPORTER,
            "Recorded step outputs:\n" + json.dumps(recorded, indent=2, default=str)[:30000],
            _tool_ctx(ctx),
        )
        narrative = run.output.model_dump()
    except AgentFailed as exc:
        # The report must exist even if the narrative cannot be generated; facts come from the record.
        narrative = {
            "problem_summary": ctx.task.goal,
            "root_cause": ctx.outputs.get("debug", {}).get("root_cause", ""),
            "fix_summary": ctx.outputs.get("debug", {}).get("fix_summary", ""),
            "limitations": [f"Narrative generation failed: {exc}"],
            "next_steps": [],
        }

    report_json = {
        "verification_label": label,
        "verification_reasons": reasons,
        "narrative": narrative,  # model-written
        "recorded": {k: v for k, v in recorded.items() if k in ("verify", "approval")},  # from execution
        "patch_artifact_id": ctx.outputs.get("debug", {}).get("patch_artifact_id"),
        "review": ctx.outputs.get("review"),
    }
    artifact_id = await ctx.store_artifact(
        step.key,
        ArtifactDraft(
            "report",
            "report.md",
            "text/markdown",
            text=_markdown(ctx, report_json),
            json=report_json,
        ),
    )
    return {"verification_label": label, "reasons": reasons, "report_artifact_id": str(artifact_id)}


def _markdown(ctx: RunContext, r: dict[str, Any]) -> str:
    n = r["narrative"]
    v = (r["recorded"] or {}).get("verify") or {}
    lines = [
        f"# {ctx.task.title}",
        "",
        f"**Verification: {r['verification_label'].replace('_', ' ').title()}**",
        *[f"- {x}" for x in r["verification_reasons"]],
        "",
        "## Problem",
        n["problem_summary"],
        "",
        "## Root cause",
        n["root_cause"],
        "",
        "## Fix",
        n["fix_summary"],
        "",
    ]
    if v:
        ta = v.get("tests_after") or {}
        lines += [
            "## Recorded results",
            f"- Tests after patch: {ta.get('passed')} passed, {ta.get('failed')} failed, "
            f"{ta.get('errors')} errors of {ta.get('collected')}",
        ]
        if v.get("bench_before") and v.get("bench_after"):
            before, after = v["bench_before"], v["bench_after"]
            lines.append(f"- Benchmark p50: {before['p50']} → {after['p50']} {after.get('unit') or ''}")
        lines.append("")
    if n.get("limitations"):
        lines += ["## Limitations", *[f"- {x}" for x in n["limitations"]], ""]
    if n.get("next_steps"):
        lines += ["## Next steps", *[f"- {x}" for x in n["next_steps"]], ""]
    lines.append(
        "_Narrative sections are model-written; verification and recorded results come from "
        "sandbox execution._"
    )
    return "\n".join(lines)


STEPS: dict[str, StepFn] = {
    "prepare_workspace": prepare_workspace,
    "plan": plan,
    "baseline": baseline,
    "analyze": analyze,
    "debug": debug,
    "approve_patch": approve_patch,
    "verify": verify,
    "review": review,
    "report": report,
}
