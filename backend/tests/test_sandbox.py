"""The sandbox's isolation claims, checked against a real container (SECURITY_MODEL.md §4.1)."""

import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import Settings
from app.sandbox.runner import Mount, SandboxRunner, SandboxSpec, SandboxUnavailable

pytestmark = pytest.mark.sandbox

PROBE = r"""
import os, socket, sys
results = {}
results["uid"] = os.getuid()
try:
    socket.create_connection(("1.1.1.1", 53), timeout=3); results["network"] = "open"
except OSError:
    results["network"] = "blocked"
for target in ("/workspace/probe.txt", "/etc/probe.txt"):
    try:
        open(target, "w").write("x"); results[target] = "writable"
    except OSError:
        results[target] = "read-only"
open("/out/ok.txt", "w").write("ok")
results["env_secret"] = os.environ.get("GEMINI_API_KEY", "absent")
print(results)
"""


@pytest.fixture
def runner(settings: Settings) -> SandboxRunner:
    r = SandboxRunner(settings.sandbox_image, run_label="agentp-test")
    try:
        r.ensure_image()
    except SandboxUnavailable as exc:
        pytest.skip(str(exc))
    return r


@pytest.fixture
def dirs(settings: Settings) -> Iterator[tuple[Path, Path]]:
    root = settings.workspace_root / "sandbox-test" / uuid.uuid4().hex
    code, out = root / "code", root / "out"
    code.mkdir(parents=True)
    out.mkdir()
    out.chmod(0o777)
    (code / "probe.py").write_text(PROBE)
    yield code, out
    shutil.rmtree(root, ignore_errors=True)


async def test_sandbox_isolation(
    runner: SandboxRunner, dirs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "should-never-reach-the-sandbox")
    code, out = dirs
    result = await runner.run(
        SandboxSpec(
            "test",
            ["python", "/workspace/probe.py"],
            [Mount(code, "/workspace"), Mount(out, "/out", read_only=False)],
        ),
        run_id="sandbox-test",
    )
    assert result.exit_code == 0, result.stderr
    report = eval(result.stdout.strip())  # noqa: S307 - our own probe's dict literal
    assert report["uid"] == 10001
    assert report["network"] == "blocked"
    assert report["/workspace/probe.txt"] == "read-only"
    assert report["/etc/probe.txt"] == "read-only"
    assert report["env_secret"] == "absent"
    assert (out / "ok.txt").read_text() == "ok"


async def test_sandbox_timeout_kills_container(runner: SandboxRunner, dirs: tuple[Path, Path]) -> None:
    code, _ = dirs
    result = await runner.run(
        SandboxSpec(
            "test", ["python", "-c", "import time; time.sleep(60)"], [Mount(code, "/workspace")], timeout_s=2
        ),
        run_id="sandbox-test",
    )
    assert result.timed_out and result.exit_code is None
    assert result.duration_ms < 15_000
