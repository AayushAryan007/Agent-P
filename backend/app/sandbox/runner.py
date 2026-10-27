"""Hardened, short-lived containers for untrusted code (SECURITY_MODEL.md §4.1).

The engine is chosen by DOCKER_HOST / the active Docker context (Colima locally, a Linux engine in prod).
The Docker socket is used only by this process and is never mounted into a sandbox.
"""

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import docker
import structlog
from docker.errors import DockerException, ImageNotFound
from docker.models.containers import Container

log = structlog.get_logger(__name__)

Purpose = Literal["clone", "install", "test", "bench"]

# Variables a sandbox may see. Nothing else from the worker's environment is passed through.
BASE_ENV = {
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONUNBUFFERED": "1",
    "PIP_NO_INPUT": "1",
    "GIT_TERMINAL_PROMPT": "0",
    "HOME": "/tmp",  # noqa: S108 - path inside the container (tmpfs), not on the host
}
MAX_LOG_BYTES = 256 * 1024


class SandboxUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Mount:
    host: Path
    container: str
    read_only: bool = True


@dataclass(frozen=True)
class SandboxSpec:
    purpose: Purpose
    command: list[str]
    mounts: list[Mount]
    network: bool = False
    timeout_s: int = 300
    memory_mb: int = 1024
    cpus: float = 1.0
    pids: int = 256
    workdir: str = "/workspace"
    env: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    oom_killed: bool


class SandboxRunner:
    def __init__(self, image: str, run_label: str = "agentp") -> None:
        self.image = image
        self.run_label = run_label
        self._client: docker.DockerClient | None = None

    def _docker(self) -> docker.DockerClient:
        if self._client is None:
            try:
                self._client = docker.from_env()
                self._client.ping()
            except DockerException as exc:
                raise SandboxUnavailable(
                    f"Docker engine not reachable (check DOCKER_HOST / colima): {exc}"
                ) from exc
        return self._client

    def ensure_image(self) -> None:
        try:
            self._docker().images.get(self.image)
        except ImageNotFound:
            raise SandboxUnavailable(
                f"sandbox image {self.image!r} not found; build it with: "
                f"docker build -t {self.image} sandbox/python"
            ) from None

    async def run(self, spec: SandboxSpec, run_id: str) -> SandboxResult:
        return await asyncio.to_thread(self._run_sync, spec, run_id)

    def _run_sync(self, spec: SandboxSpec, run_id: str) -> SandboxResult:
        client = self._docker()
        self.ensure_image()
        container: Container = client.containers.create(
            self.image,
            command=spec.command,
            working_dir=spec.workdir,
            user="10001:10001",
            environment={**BASE_ENV, **spec.env},
            network_mode="bridge" if spec.network else "none",
            read_only=True,
            tmpfs={"/tmp": "rw,size=256m,mode=1777"},  # noqa: S108 - container path, not host
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            mem_limit=f"{spec.memory_mb}m",
            memswap_limit=f"{spec.memory_mb}m",
            nano_cpus=int(spec.cpus * 1e9),
            pids_limit=spec.pids,
            volumes={
                str(m.host): {"bind": m.container, "mode": "ro" if m.read_only else "rw"} for m in spec.mounts
            },
            labels={"agentp.run_id": run_id, "agentp.purpose": spec.purpose, "agentp": self.run_label},
            init=True,
        )
        start = time.monotonic()
        timed_out = False
        try:
            container.start()
            try:
                status = container.wait(timeout=spec.timeout_s)
                exit_code: int | None = int(status.get("StatusCode", -1))
            except Exception:  # requests ReadTimeout when the deadline passes
                timed_out = True
                exit_code = None
                with contextlib.suppress(DockerException):
                    container.kill()
            duration_ms = int((time.monotonic() - start) * 1000)
            stdout = container.logs(stdout=True, stderr=False)[-MAX_LOG_BYTES:].decode("utf-8", "replace")
            stderr = container.logs(stdout=False, stderr=True)[-MAX_LOG_BYTES:].decode("utf-8", "replace")
            container.reload()
            oom = bool(container.attrs.get("State", {}).get("OOMKilled"))
        finally:
            with contextlib.suppress(DockerException):
                container.remove(force=True)
        log.info(
            "sandbox.finished",
            purpose=spec.purpose,
            exit_code=exit_code,
            duration_ms=duration_ms,
            timed_out=timed_out,
            oom=oom,
        )
        return SandboxResult(exit_code, stdout, stderr, duration_ms, timed_out, oom)

    def cleanup_orphans(self) -> int:
        """Remove sandbox containers left behind by a crashed worker."""
        try:
            client = self._docker()
        except SandboxUnavailable:
            return 0
        removed = 0
        for c in client.containers.list(all=True, filters={"label": f"agentp={self.run_label}"}):
            with contextlib.suppress(DockerException):
                c.remove(force=True)
                removed += 1
        return removed
