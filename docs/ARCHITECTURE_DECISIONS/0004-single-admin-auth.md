# ADR-0004: Single admin token authentication for the MVP

- Status: Accepted
- Date: 2026-10-27

## Context

Running tasks consumes LLM quota and executes untrusted code, so it must be restricted. Viewing completed runs is the portfolio value and should be public. Multi-user accounts are P2.

## Decision

- Backend env holds `ADMIN_TOKEN_HASH` (argon2 hash; plaintext never stored).
- `POST /api/v1/auth/session` exchanges the token for a signed, httpOnly, `Secure`, `SameSite=None` session cookie (frontend on Vercel and backend on another domain are cross-site), short-lived with sliding renewal.
- Mutating endpoints (create task/run, cancel, approval decision, settings) require the operator role; CSRF protection via an `Origin` allowlist check plus a **synchronizer token**: a random CSRF token is stored inside the signed session cookie, returned in the body of `POST /auth/session` and `GET /auth/me`, held in memory by the SPA, and echoed in `X-CSRF-Token`.
- Anonymous users can read runs marked `public` (default: public for bundled repos, private for GitHub URL runs).
- All operator actions write an `audit_log` row.

## Consequences

- + Small, secure enough for a single-owner demo.
- − No per-user attribution; replaced by OAuth + users table in P2 (schema reserves `actor` fields now).
- Cross-site cookies require careful CORS (`allow_credentials`, explicit origins); documented in SECURITY_MODEL.md.
- A double-submit *cookie* was the first design but does not work cross-site: the SPA on the Vercel domain cannot read cookies set by the API domain. Changed to the synchronizer token during M1 (2026-10-27).
