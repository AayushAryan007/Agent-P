# AGENT-P — Security Model

Status: Phase 2 baseline. Last updated: 2026-10-27.

## 1. Assets

1. The backend host (OCI VM) and its Docker engine.
2. Secrets: LLM API keys, admin token hash, session signing key, DB credentials.
3. LLM quota and budget.
4. Integrity of results: verification labels, events, audit log.
5. Availability of the public demo.

## 2. Actors and threats

| Actor | Capability | Main threats |
|---|---|---|
| Anonymous internet user | Reads public runs; can attempt auth | Brute-force the admin token, DoS, scraping private runs |
| Malicious repository (public GitHub) | Arbitrary code in tests, `setup.py`/`conftest.py`, build hooks; arbitrary text in files | Container escape, network exfiltration, resource exhaustion, **prompt injection** steering agents |
| Compromised or confused LLM output | Arbitrary tool-call requests and text | Path traversal, calling disallowed tools, faking success, editing tests to make them "pass" |
| Operator (trusted) | Full API | Mistakes: approving a bad patch, pasting a secret into a goal |

## 3. Trust boundaries

```
Browser ──(HTTPS, cookie + CSRF)──▶ api ──▶ Postgres ◀── worker ──(DOCKER_HOST)──▶ engine ──▶ sandbox containers
                                                         │
                                                         └──(HTTPS, API key)──▶ LLM provider
```
Untrusted data enters at: request bodies, repository contents, sandbox output, and LLM output. All of it is validated and bounded before it is stored or displayed.

## 4. Controls

### 4.1 Sandbox (code execution)
Each `clone`, `install`, `test`, and `bench` step runs in a fresh container from `agentp-sandbox-python` with:
- non-root UID 10001, `--cap-drop=ALL`, `--security-opt no-new-privileges`, default seccomp profile, `--read-only` root filesystem, `--tmpfs /tmp:size=256m,noexec`;
- `--pids-limit 256`, `--memory 1g --memory-swap 1g`, `--cpus 1.0`, wall-clock timeout (clone 60 s, install 180 s, tests 300 s, bench 180 s), killed and removed on timeout;
- **network:** `none` for test/bench; clone/install currently use the engine's default bridge (outbound access, no secrets). A dedicated egress-only network with the cloud metadata address `169.254.169.254` blocked by host firewall rules is required before public GitHub runs are enabled on the production host;
- mounts: the repository copy **read-only** for test/bench; a writable `out/` directory bound to that step only; dependencies installed into a per-run volume that is mounted read-only into the test step;
- no environment variables except an explicit allowlist (`PYTHONDONTWRITEBYTECODE`, `PIP_NO_INPUT`, …); **no secrets, ever**;
- the Docker socket is **never** mounted into any sandbox;
- workspaces are deleted at run end, including on failure (`finally` cleanup plus a periodic janitor for orphans labeled `agentp.run_id`).

On the OCI host Docker runs **rootless**, so a container escape lands as an unprivileged user, and gVisor (`runsc`) is enabled as the sandbox runtime when available.

### 4.2 Tool gate
- Each agent has a static allowlist. A model's tool request is a **proposal**; the gate checks allowlist → Pydantic args → policy → budget before executing, and records `tool.denied` otherwise.
- **Path policy:** paths are relative to the repo root, normalized, resolved with symlinks, and must stay inside the root (`resolved.is_relative_to(root)`). `.git/`, files over 512 KB, and binaries are refused.
- **Output bounds:** tool outputs are truncated (e.g. 16 KB per read, 200 search hits) and redacted before reaching the model, events, or the UI.
- There is no shell tool, no network tool, and no write tool except `propose_patch`, which only produces an artifact.

### 4.3 Prompt injection and result integrity
- Repository text and tool output are wrapped in clearly delimited blocks labeled as untrusted data. System prompts instruct the model never to follow instructions found inside them.
- Injection cannot *escalate*: tool permissions are fixed per step in code, and the only consequential action (applying a patch) requires human approval.
- **Verification is deterministic.** The label is computed from exit codes, JUnit XML, and benchmark JSON — never from model text. Before verifying, the original test and benchmark files are restored over the patched copy, so a patch cannot "pass" by editing tests. A patch that touches test/benchmark files is flagged in the report and capped at `partially_verified`.
- The UI visually separates model narration (`agent.message`) from recorded facts (tool results, sandbox results).

### 4.4 Repository ingestion (ADR-0003)
GitHub HTTPS URLs only (strict regex, no credentials, no other hosts). Shallow clone, no submodules, no LFS, `GIT_TERMINAL_PROMPT=0`, size ≤ 50 MB, file count ≤ 5,000, clone timeout. Operator only.

### 4.5 API and auth (ADR-0004)
- Admin token compared via argon2 hash verification; 5 attempts per minute per IP; failures audited.
- Session cookie: signed, `HttpOnly`, `Secure`, `SameSite=None`, 12 h lifetime. CSRF synchronizer token (bound to the signed session, delivered in `/auth` response bodies, sent back as `X-CSRF-Token`) plus `Origin` allowlist on mutations.
- CORS: explicit origins, no wildcard; the same allowlist is used for SSE.
- Request size limit of 64 KB; Pydantic limits on all strings and lists.
- Security headers via Caddy (HSTS, `nosniff`, `frame-ancestors 'none'`).

### 4.6 Secrets
- Secrets live in backend env files on the host (`/etc/agentp/*.env`, mode 600) or the OCI Vault later — never in git, the DB, `VITE_*` variables, events, or sandbox env.
- A redaction filter is applied to logs, event payloads, and LLM excerpts (patterns: provider key formats, `Authorization` headers, `*_KEY`/`*_TOKEN`/`password` fields, high-entropy strings in env-like lines).
- The settings API only reports `configured: true/false`.

### 4.7 Audit
Login success/failure, task and run creation, cancellations, approval decisions, and settings changes → `audit_log` (actor, IP, user agent, target).

## 5. Residual risks (stated honestly)

- **Container escape via kernel vulnerabilities** is still possible with `runc`; rootless Docker and gVisor reduce the impact, and the VM boundary is the final layer. A dedicated sandbox VM (Firecracker) would be the next step if the threat model grows.
- **Install-step network access** lets malicious packages phone home during `pip install`. Mitigation: no secrets in that container, egress-only network, short timeout. A PyPI-only egress proxy is a P1 hardening item.
- **Prompt injection** can still degrade analysis quality or mislead the narrative; it cannot run unapproved actions or forge verification results.
- **Free-tier data use:** prompts to the Gemini free tier may be used by Google; only public code is processed.
- **A single admin token** has no per-user accountability; acceptable for an MVP with one owner.
