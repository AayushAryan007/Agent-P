# syntax=docker/dockerfile:1
# Multi-arch (arm64 for Colima/OCI A1, amd64 for CI). Runs as a non-root user.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv

WORKDIR /srv/agentp
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 10001 --no-create-home agentp
USER agentp

EXPOSE 8000
CMD ["agentp", "api", "--host", "0.0.0.0", "--port", "8000"]
