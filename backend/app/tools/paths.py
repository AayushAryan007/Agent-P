"""Path policy for repository tools (SECURITY_MODEL.md §4.2)."""

from pathlib import Path, PurePosixPath

from app.tools.base import PolicyViolation, ToolError

MAX_FILE_BYTES = 512 * 1024
SKIP_DIRS = frozenset(
    {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache", ".pytest_cache"}
)


def resolve_in_repo(root: Path, rel: str) -> Path:
    """Resolve a model-supplied relative path, refusing anything that escapes the repository."""
    if "\x00" in rel:
        raise PolicyViolation("path contains a NUL byte")
    pure = PurePosixPath(rel.strip() or ".")
    if pure.is_absolute():
        raise PolicyViolation(f"absolute paths are not allowed: {rel}")
    if ".git" in pure.parts:
        raise PolicyViolation(".git is not accessible")
    root_resolved = root.resolve()
    target = (root_resolved / pure).resolve()  # follows symlinks, so a link pointing outside is caught
    if not target.is_relative_to(root_resolved):
        raise PolicyViolation(f"path is outside the repository: {rel}")
    return target


def read_text_file(path: Path) -> str:
    if not path.is_file():
        raise ToolError(f"not a file: {path.name}")
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ToolError(f"file is too large ({size} bytes > {MAX_FILE_BYTES})")
    data = path.read_bytes()
    if b"\x00" in data[:8192]:
        raise ToolError("binary files are not readable")
    return data.decode("utf-8", errors="replace")


def relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()
