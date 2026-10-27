"""propose_patch: turn search/replace edits into a reviewed patch artifact.

Edits are applied as text to an in-memory copy (no code is executed), so validating that a
patch applies cleanly needs no sandbox. The patch is *only* an artifact here; it is applied to
a temporary working copy after human approval, by the verification step.
"""

import difflib
from pathlib import Path

from pydantic import BaseModel, Field

from app.tools.base import ArtifactDraft, Tool, ToolContext, ToolError, ToolOutput, bound_text
from app.tools.paths import read_text_file, relative, resolve_in_repo

MAX_EDITS = 20


class Edit(BaseModel):
    path: str = Field(description="File to change, relative to the repository root")
    search: str = Field(
        description="Exact text to replace; must occur exactly once in the file. Empty to create a new file."
    )
    replace: str = Field(description="Replacement text")


class ProposePatchArgs(BaseModel):
    edits: list[Edit] = Field(min_length=1, max_length=MAX_EDITS)
    rationale: str = Field(min_length=1, max_length=2000, description="Why this change fixes the problem")


def apply_edits(root: Path, edits: list[Edit]) -> dict[str, tuple[str, str]]:
    """Return {relative_path: (before, after)}. Raises ToolError if any edit does not apply cleanly."""
    files: dict[str, tuple[str, str]] = {}
    for i, edit in enumerate(edits, start=1):
        path = resolve_in_repo(root, edit.path)
        rel = relative(root, path)
        if rel in files:
            before, current = files[rel]
        elif path.exists():
            before = current = read_text_file(path)
        elif edit.search == "":
            before = current = ""
        else:
            raise ToolError(f"edit {i}: file does not exist: {edit.path}")
        if edit.search == "":
            if current:
                raise ToolError(f"edit {i}: empty search is only allowed when creating a new file")
            current = edit.replace
        else:
            count = current.count(edit.search)
            if count != 1:
                raise ToolError(
                    f"edit {i}: search text found {count} times in {rel}; it must match exactly once"
                )
            current = current.replace(edit.search, edit.replace, 1)
        files[rel] = (before, current)
    return files


def unified_diff(files: dict[str, tuple[str, str]]) -> tuple[str, int, int]:
    chunks: list[str] = []
    additions = deletions = 0
    for rel, (before, after) in sorted(files.items()):
        lines = list(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{rel}" if before else "/dev/null",
                tofile=f"b/{rel}",
            )
        )
        for line in lines:
            if line.startswith("+") and not line.startswith("+++"):
                additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1
        chunks.append(
            "".join(
                line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in lines
            )
        )
    return "".join(chunks), additions, deletions


async def propose_patch(ctx: ToolContext, args: ProposePatchArgs) -> ToolOutput:
    files = apply_edits(ctx.repo_root, args.edits)
    changed = {k: v for k, v in files.items() if v[0] != v[1]}
    if not changed:
        raise ToolError("the edits do not change any file")
    diff, additions, deletions = unified_diff(changed)
    preview, truncated = bound_text(diff, 8000)
    summary = {
        "applies_cleanly": True,
        "files": sorted(changed),
        "additions": additions,
        "deletions": deletions,
    }
    return ToolOutput(
        summary=summary,
        model_content={
            **summary,
            "diff": preview,
            "note": "Patch recorded. It will be applied only after human approval.",
        },
        truncated=truncated,
        artifact=ArtifactDraft(
            kind="patch",
            name="patch.diff",
            content_type="text/x-diff",
            text=diff,
            json={
                "edits": [e.model_dump() for e in args.edits],
                "rationale": args.rationale,
                **summary,
            },
        ),
    )


PROPOSE_PATCH = Tool(
    "propose_patch",
    "Propose a code change as exact search/replace edits. "
    "Records a patch for human review; nothing is applied.",
    ProposePatchArgs,
    propose_patch,
)
