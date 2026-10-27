"""Per-run working directories on the worker host.

<workspace_root>/<run_id>/
    repo/       pristine copy of the repository (mounted read-only into sandboxes)
    patched/    repo + approved patch, protected paths restored (read-only into sandboxes)
    deps/       third-party packages installed by the install step (GitHub repos only)
    out/<name>/ writable output directory for one sandbox invocation (JUnit XML, ...)
"""

import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.tools.patch import Edit, apply_edits

COPY_IGNORE = shutil.ignore_patterns(".git", "__pycache__", ".venv", "venv", "node_modules", "*.pyc", "*.db")
DEFAULT_TEST_COMMAND = ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml=/out/junit.xml"]
DEFAULT_PROTECTED = ["tests", "test", "bench", "benchmarks", "conftest.py", "pytest.ini", "agentp.toml"]


@dataclass(frozen=True)
class VerifyConfig:
    test_command: list[str] = field(default_factory=lambda: list(DEFAULT_TEST_COMMAND))
    benchmark_command: list[str] | None = None
    protected_paths: list[str] = field(default_factory=lambda: list(DEFAULT_PROTECTED))
    min_improvement: float = 0.10
    source: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_command": self.test_command,
            "benchmark_command": self.benchmark_command,
            "protected_paths": self.protected_paths,
            "min_improvement": self.min_improvement,
            "source": self.source,
        }


class WorkspaceError(Exception):
    pass


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.repo = root / "repo"
        self.patched = root / "patched"
        self.deps = root / "deps"

    def create(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def out_dir(self, name: str) -> Path:
        d = self.root / "out" / name
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        d.chmod(0o777)  # writable by the sandbox UID on a real Linux engine
        return d

    def copy_bundled(self, source: Path) -> None:
        if self.repo.exists():
            shutil.rmtree(self.repo)
        shutil.copytree(source, self.repo, ignore=COPY_IGNORE, symlinks=True)

    def check_limits(self, max_mb: int, max_files: int) -> dict[str, int]:
        files = 0
        size = 0
        for p in self.repo.rglob("*"):
            if p.is_file() and not p.is_symlink():
                files += 1
                size += p.stat().st_size
        if files > max_files:
            raise WorkspaceError(f"repository has {files} files (limit {max_files})")
        if size > max_mb * 1024 * 1024:
            raise WorkspaceError(f"repository is {size // (1024 * 1024)} MB (limit {max_mb} MB)")
        python_files = sum(1 for _ in self.repo.rglob("*.py"))
        return {"files": files, "bytes": size, "python_files": python_files}

    def verify_config(self) -> VerifyConfig:
        cfg_path = self.repo / "agentp.toml"
        if not cfg_path.is_file():
            return VerifyConfig()
        try:
            data = tomllib.loads(cfg_path.read_text())["verify"]
            return VerifyConfig(
                test_command=[str(x) for x in data.get("test_command", DEFAULT_TEST_COMMAND)],
                benchmark_command=[str(x) for x in data["benchmark_command"]]
                if data.get("benchmark_command")
                else None,
                protected_paths=[str(x) for x in data.get("protected_paths", DEFAULT_PROTECTED)]
                + ["agentp.toml"],
                min_improvement=float(data.get("min_improvement", 0.10)),
                source="agentp.toml",
            )
        except (KeyError, TypeError, ValueError, tomllib.TOMLDecodeError) as exc:
            raise WorkspaceError(f"invalid agentp.toml: {exc}") from exc

    def build_patched(self, edits: list[Edit], protected: list[str]) -> list[str]:
        """Build patched/ = repo/ + edits; protected paths stay original. Returns protected files touched."""
        if self.patched.exists():
            shutil.rmtree(self.patched)
        shutil.copytree(self.repo, self.patched, symlinks=True)
        files = apply_edits(self.repo, edits)
        touched_protected: list[str] = []
        for rel, (_before, after) in files.items():
            if any(rel == p or rel.startswith(p.rstrip("/") + "/") for p in protected):
                touched_protected.append(rel)
                continue  # restored below: verification always runs the original tests
            target = self.patched / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(after)
        return touched_protected

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
