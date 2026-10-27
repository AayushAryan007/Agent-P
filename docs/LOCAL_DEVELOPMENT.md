# Local Development

AGENT-P runs locally on macOS with **Colima** (no Docker Desktop), `uv` for Python, and Node for the frontend.

## Prerequisites

```bash
brew install colima docker docker-compose docker-buildx uv node
mkdir -p ~/.docker/cli-plugins
ln -sfn "$(brew --prefix)/opt/docker-compose/bin/docker-compose" ~/.docker/cli-plugins/docker-compose
ln -sfn "$(brew --prefix)/opt/docker-buildx/bin/docker-buildx" ~/.docker/cli-plugins/docker-buildx
colima start --cpu 4 --memory 8 --disk 60 --vm-type vz
```

## First run

```bash
# 1. Database (host port 5433, so a Homebrew PostgreSQL on 5432 does not clash)
docker compose up -d postgres

# 2. Backend
cd backend
cp .env.example .env
uv run agentp hash-token          # prints a new admin token and its ADMIN_TOKEN_HASH
#   → paste the ADMIN_TOKEN_HASH='…' line into backend/.env, keep the token for signing in
#   → add GEMINI_API_KEY from https://aistudio.google.com/apikey to enable runs
uv run alembic upgrade head
uv run agentp api --reload        # http://localhost:8000/api/v1/docs

# 3. Frontend (another terminal)
cd frontend
cp .env.example .env.local
npm install
npm run dev                       # http://localhost:5173
```

Alternatively, run the API in a container too: `docker compose up -d --build` (it applies migrations on start).

## Checks

| | Command |
|---|---|
| Backend tests (needs `docker compose up -d postgres`) | `cd backend && uv run pytest` |
| Backend lint / format / types | `uv run ruff check . && uv run ruff format --check . && uv run mypy` |
| Frontend | `cd frontend && npm run lint && npm run typecheck && npm test && npm run build` |
| Migration drift | `cd backend && uv run alembic check` |

Backend tests use the separate `agentp_test` database (created by `backend/scripts/init-test-db.sql` on first Postgres start) and never touch dev data.

## Colima behaviour (verified 2026-10-27, Colima 0.10.1, Docker 28.4, arm64)

| Check | Result | Consequence for the design |
|---|---|---|
| Bind mount from `~/Desktop/agent-p`, read + write | Works | Sandbox workspaces can live under the project/home directory |
| `:ro` bind mount | Writes fail with "Read-only file system" | Read-only repository mounts are enforced |
| Container running as UID 10001 writing to a host dir it doesn't own | **Succeeds**; files appear owned by the macOS user | Colima's file sharing does not enforce Linux ownership. Never rely on file permissions for isolation locally; always use `:ro` mounts |
| `host.docker.internal` | Resolves (192.168.5.2) | Available, but we use Compose service names instead |
| `--network none` | Outbound traffic blocked | Network-less test execution works as designed |

Engine socket for programmatic access (sandbox, from M4): `DOCKER_HOST=unix://$HOME/.colima/default/docker.sock`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Cannot connect to the Docker daemon` | `colima start`, then `docker context use colima` |
| Frontend shows "Backend unreachable" | API not running on `VITE_API_URL` (default `http://localhost:8000`) |
| `/readyz` reports `migrations: behind` | `uv run alembic upgrade head` |
| New Task says no provider configured | Set `GEMINI_API_KEY` in `backend/.env` and restart the API |
