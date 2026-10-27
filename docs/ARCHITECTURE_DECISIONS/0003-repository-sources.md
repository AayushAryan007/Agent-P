# ADR-0003: Repository sources — bundled demo repos and public GitHub URLs

- Status: Accepted
- Date: 2026-10-27

## Context

The flagship workflow needs a Python repo with a measurable performance bug. Bundled repos give deterministic demos and evaluations; arbitrary public repos make the tool genuinely useful but expand the attack surface (malicious code, huge repos, prompt injection in files).

## Decision

Support both, with different trust levels:

1. **Bundled demo repos** (in `demo-repos/`), each with a known bug, a test suite, and a benchmark script. Available to anyone the operator allows; used by the public demo and the evaluation suite.
2. **Public GitHub URLs**, **operator only**:
   - Must match `https://github.com/<owner>/<repo>(.git)?` — no other hosts, schemes, or credentials in the URL.
   - Shallow clone (`--depth 1`), no submodules, no LFS, executed in a dedicated clone container with a timeout.
   - Limits: repository size (default 50 MB) and file count (default 5,000); exceeding fails the run.
   - Dependency install runs in a separate step with network enabled but no secrets, then tests/benchmarks run with network disabled.
   - Unsupported layouts produce `Not verified` with a reason rather than guesswork.

## Consequences

- + Safe public demo; realistic operator usage.
- − Two code paths for ingestion — unified after the clone step into a single "workspace" abstraction.
- Repository content is always treated as untrusted data (see SECURITY_MODEL.md).
