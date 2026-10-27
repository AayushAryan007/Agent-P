"""Workflow templates: fixed DAGs that the coordinator fills in (ADR-0001, ARCHITECTURE.md §2.3)."""

from dataclasses import dataclass, field
from typing import Literal

StepKind = Literal["agent", "system", "approval"]
AgentRole = Literal["coordinator", "repo_analysis", "debugging", "verification", "review"]


@dataclass(frozen=True)
class StepSpec:
    key: str
    kind: StepKind
    title: str
    role: AgentRole | None = None
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolInfo:
    name: str
    description: str
    runs_in: Literal["api_worker", "sandbox"]


@dataclass(frozen=True)
class Template:
    key: str
    title: str
    description: str
    steps: tuple[StepSpec, ...]
    tools: tuple[ToolInfo, ...] = field(default=())

    def __post_init__(self) -> None:
        keys = [s.key for s in self.steps]
        if len(keys) != len(set(keys)):
            raise ValueError(f"duplicate step keys in template {self.key}")
        seen: set[str] = set()
        for s in self.steps:  # steps must be listed in topological order
            missing = [d for d in s.depends_on if d not in seen]
            if missing:
                raise ValueError(f"step {s.key} depends on unknown or later steps {missing}")
            seen.add(s.key)


SLOW_ENDPOINT_V1 = Template(
    key="slow-endpoint-v1",
    title="Investigate a slow endpoint",
    description=(
        "Find the root cause of a slow API endpoint, propose a patch, "
        "and verify it with tests and a benchmark."
    ),
    steps=(
        StepSpec("prepare_workspace", "system", "Prepare workspace"),
        StepSpec("plan", "agent", "Coordinator · plan", "coordinator", ("prepare_workspace",)),
        StepSpec("baseline", "system", "Baseline tests + bench", None, ("prepare_workspace",)),
        StepSpec("analyze", "agent", "Repository analysis", "repo_analysis", ("plan",)),
        StepSpec("debug", "agent", "Debugging · patch", "debugging", ("analyze",)),
        StepSpec("approve_patch", "approval", "Approve patch", None, ("debug",)),
        StepSpec("verify", "agent", "Test & verification", "verification", ("approve_patch", "baseline")),
        StepSpec("review", "agent", "Review", "review", ("verify",)),
        StepSpec("report", "agent", "Coordinator · report", "coordinator", ("review",)),
    ),
    tools=(
        ToolInfo("list_tree", "List files and folders in the repository", "api_worker"),
        ToolInfo("read_file", "Read a text file inside the repository (≤ 512 KB)", "api_worker"),
        ToolInfo("search_code", "Search the repository for text or a pattern", "api_worker"),
        ToolInfo(
            "propose_patch", "Prepare a patch as an artifact; never applied without approval", "sandbox"
        ),
        ToolInfo("run_tests", "Run the repository's test suite", "sandbox"),
        ToolInfo("run_benchmark", "Run the repository's benchmark script", "sandbox"),
        ToolInfo("git_diff", "Show the diff of the patched copy", "api_worker"),
    ),
)

TEMPLATES: dict[str, Template] = {t.key: t for t in (SLOW_ENDPOINT_V1,)}


@dataclass(frozen=True)
class BundledRepo:
    key: str
    title: str
    description: str
    path: str  # relative to the repository root


BUNDLED_REPOS: dict[str, BundledRepo] = {
    r.key: r
    for r in (
        BundledRepo(
            "demo-slow-api",
            "demo-slow-api",
            "FastAPI + SQLite orders service with a slow listing endpoint",
            "demo-repos/demo-slow-api",
        ),
    )
}
