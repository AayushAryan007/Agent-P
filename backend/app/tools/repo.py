"""Read-only repository tools: list_tree, read_file, search_code."""

import os
import re
from pathlib import Path

from pydantic import BaseModel, Field

from app.tools.base import Tool, ToolContext, ToolError, ToolOutput, bound_text
from app.tools.paths import MAX_FILE_BYTES, SKIP_DIRS, read_text_file, relative, resolve_in_repo

MAX_TREE_ENTRIES = 400
MAX_SEARCH_FILES = 5000


class ListTreeArgs(BaseModel):
    path: str = Field(".", description="Directory relative to the repository root")
    depth: int = Field(2, ge=1, le=4, description="How many directory levels to show")


async def list_tree(ctx: ToolContext, args: ListTreeArgs) -> ToolOutput:
    base = resolve_in_repo(ctx.repo_root, args.path)
    if not base.is_dir():
        raise ToolError(f"not a directory: {args.path}")
    entries: list[str] = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(base):
        current = Path(dirpath)
        level = len(current.relative_to(base).parts)
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        if level >= args.depth:
            dirnames[:] = []
        for name in [*(d + "/" for d in dirnames), *sorted(filenames)]:
            if len(entries) >= MAX_TREE_ENTRIES:
                truncated = True
                break
            entries.append(
                relative(ctx.repo_root, current / name.rstrip("/")) + ("/" if name.endswith("/") else "")
            )
    return ToolOutput(
        summary={"entries": len(entries), "path": args.path},
        model_content={"entries": entries, "truncated": truncated},
        truncated=truncated,
    )


class ReadFileArgs(BaseModel):
    path: str = Field(description="File path relative to the repository root")
    start_line: int = Field(1, ge=1)
    max_lines: int = Field(400, ge=1, le=1000)


async def read_file(ctx: ToolContext, args: ReadFileArgs) -> ToolOutput:
    path = resolve_in_repo(ctx.repo_root, args.path)
    lines = read_text_file(path).splitlines()
    chunk = lines[args.start_line - 1 : args.start_line - 1 + args.max_lines]
    numbered = "\n".join(f"{i:>5}  {line}" for i, line in enumerate(chunk, start=args.start_line))
    text, truncated = bound_text(numbered)
    more = args.start_line - 1 + len(chunk) < len(lines)
    return ToolOutput(
        summary={"path": relative(ctx.repo_root, path), "lines": len(chunk), "total_lines": len(lines)},
        model_content={
            "path": relative(ctx.repo_root, path),
            "total_lines": len(lines),
            "content": text,
            "more_lines_available": more,
        },
        truncated=truncated or more,
    )


class SearchCodeArgs(BaseModel):
    query: str = Field(min_length=1, max_length=200, description="Text to find (or a regex if regex=true)")
    regex: bool = False
    path: str = Field(".", description="Directory to search, relative to the repository root")
    max_results: int = Field(50, ge=1, le=200)


async def search_code(ctx: ToolContext, args: SearchCodeArgs) -> ToolOutput:
    base = resolve_in_repo(ctx.repo_root, args.path)
    try:
        pattern = re.compile(args.query if args.regex else re.escape(args.query))
    except re.error as exc:
        raise ToolError(f"invalid regex: {exc}") from None
    hits: list[dict[str, object]] = []
    scanned = 0
    truncated = False
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            scanned += 1
            if scanned > MAX_SEARCH_FILES:
                truncated = True
                break
            file = Path(dirpath) / name
            if file.is_symlink() or file.stat().st_size > MAX_FILE_BYTES:
                continue
            try:
                text = read_text_file(file)
            except ToolError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    hits.append(
                        {"path": relative(ctx.repo_root, file), "line": lineno, "text": line.strip()[:200]}
                    )
                    if len(hits) >= args.max_results:
                        truncated = True
                        break
            if truncated:
                break
        if truncated:
            break
    return ToolOutput(
        summary={"query": args.query, "hits": len(hits)},
        model_content={"hits": hits, "truncated": truncated},
        truncated=truncated,
    )


LIST_TREE = Tool("list_tree", "List files and folders in the repository.", ListTreeArgs, list_tree)
READ_FILE = Tool(
    "read_file", "Read a UTF-8 text file in the repository, with line numbers.", ReadFileArgs, read_file
)
SEARCH_CODE = Tool(
    "search_code", "Search repository files for text or a regular expression.", SearchCodeArgs, search_code
)
