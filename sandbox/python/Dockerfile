# syntax=docker/dockerfile:1
# Sandbox image for running untrusted Python test suites and benchmarks (SECURITY_MODEL.md §4.1).
# Contains no secrets and no AGENT-P code. Multi-arch base. Runs as UID 10001.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Common test dependencies pre-installed so bundled repos verify with the network fully disabled.
RUN pip install --no-cache-dir "pytest>=8" "fastapi>=0.115" "httpx>=0.27"

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin sandbox
USER 10001:10001
WORKDIR /workspace

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_INPUT=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GIT_TERMINAL_PROMPT=0
