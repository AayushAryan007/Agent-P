"""HTTP API behavior: health, auth/CSRF, task + run creation, idempotency, visibility, cancel, metrics."""

import uuid

import httpx

from tests.conftest import ORIGIN, task_body


async def test_health_and_readiness(anon: httpx.AsyncClient) -> None:
    assert (await anon.get("/healthz")).json() == {"status": "ok"}
    r = await anon.get("/readyz")
    assert r.status_code == 200, r.text
    assert r.json()["checks"] == {"database": "ok", "migrations": "ok"}


async def test_meta_never_exposes_keys(anon: httpx.AsyncClient) -> None:
    r = await anon.get("/api/v1/meta")
    assert r.status_code == 200
    body = r.json()
    assert body["templates"][0]["key"] == "slow-endpoint-v1"
    assert {p["name"]: p["configured"] for p in body["providers"]} == {"gemini": True, "groq": False}
    assert "test-key-not-used" not in r.text


async def test_login_rejects_bad_token_with_problem_json(anon: httpx.AsyncClient) -> None:
    r = await anon.post("/api/v1/auth/session", json={"token": "wrong"})
    assert r.status_code == 401
    assert r.headers["content-type"] == "application/problem+json"
    assert r.json()["title"] == "Unauthorized"
    assert (await anon.get("/api/v1/auth/me")).json() == {"role": "anonymous", "csrf_token": None}


async def test_mutations_require_operator_and_csrf(
    anon: httpx.AsyncClient, operator: httpx.AsyncClient
) -> None:
    assert (await anon.post("/api/v1/tasks", json=task_body())).status_code == 401

    csrf = operator.headers.pop("X-CSRF-Token")
    r = await operator.post("/api/v1/tasks", json=task_body())
    assert r.status_code == 403 and r.json()["type"].endswith("/csrf")

    operator.headers["X-CSRF-Token"] = csrf
    r = await operator.post("/api/v1/tasks", json=task_body(), headers={"Origin": "https://evil.example"})
    assert r.status_code == 403

    assert (await operator.post("/api/v1/tasks", json=task_body())).status_code == 201


async def test_task_validation(operator: httpx.AsyncClient) -> None:
    cases = [
        task_body(repo_source={"kind": "github", "url": "https://gitlab.com/a/b"}),
        task_body(repo_source={"kind": "github", "url": "https://user:pw@github.com/a/b"}),
        task_body(repo_source={"kind": "bundled", "key": "nope"}),
        task_body(model="gpt-unknown"),
        task_body(
            limits={"max_minutes": 999, "max_llm_calls": 1, "max_total_tokens": 1, "max_tool_calls": 1}
        ),
        task_body(goal="too short"),
    ]
    for body in cases:
        r = await operator.post("/api/v1/tasks", json=body)
        assert r.status_code == 422, (body, r.text)


async def test_github_tasks_are_forced_private(operator: httpx.AsyncClient, anon: httpx.AsyncClient) -> None:
    r = await operator.post(
        "/api/v1/tasks",
        json=task_body(repo_source={"kind": "github", "url": "https://github.com/encode/httpx"}),
    )
    assert r.status_code == 201 and r.json()["visibility"] == "private"
    assert (await anon.get(f"/api/v1/tasks/{r.json()['id']}")).status_code == 404


async def test_start_run_is_idempotent(operator: httpx.AsyncClient) -> None:
    task_id = (await operator.post("/api/v1/tasks", json=task_body())).json()["id"]
    assert (await operator.post(f"/api/v1/tasks/{task_id}/runs")).status_code == 400  # key required

    key = str(uuid.uuid4())
    first = await operator.post(f"/api/v1/tasks/{task_id}/runs", headers={"Idempotency-Key": key})
    again = await operator.post(f"/api/v1/tasks/{task_id}/runs", headers={"Idempotency-Key": key})
    assert first.status_code == again.status_code == 202
    assert first.json()["id"] == again.json()["id"]
    assert first.json()["status"] == "queued"

    runs = (await operator.get("/api/v1/runs", params={"task_id": task_id})).json()["items"]
    assert len(runs) == 1


async def test_run_snapshot_events_and_cancel(operator: httpx.AsyncClient, anon: httpx.AsyncClient) -> None:
    task_id = (await operator.post("/api/v1/tasks", json=task_body())).json()["id"]
    run = (
        await operator.post(f"/api/v1/tasks/{task_id}/runs", headers={"Idempotency-Key": str(uuid.uuid4())})
    ).json()

    detail = (await anon.get(f"/api/v1/runs/{run['id']}")).json()
    assert detail["last_sequence"] == 1
    assert [s["key"] for s in detail["steps"]][-1] == "report"
    assert all(s["status"] == "pending" for s in detail["steps"])

    assert (await anon.post(f"/api/v1/runs/{run['id']}/cancel")).status_code == 401
    r = await operator.post(f"/api/v1/runs/{run['id']}/cancel")
    assert r.status_code == 202 and r.json()["status"] == "cancelled"
    assert (await operator.post(f"/api/v1/runs/{run['id']}/cancel")).status_code == 409

    events = (await anon.get(f"/api/v1/runs/{run['id']}/events")).json()
    assert [e["event_type"] for e in events["items"]] == [
        "workflow.created",
        "workflow.cancel_requested",
        "workflow.cancelled",
    ]
    assert [e["sequence_number"] for e in events["items"]] == [1, 2, 3]

    page = (await anon.get(f"/api/v1/runs/{run['id']}/events", params={"after_seq": 1, "limit": 1})).json()
    assert [e["sequence_number"] for e in page["items"]] == [2] and page["next_after_seq"] == 2


async def test_metrics_are_derived_from_runs(operator: httpx.AsyncClient) -> None:
    empty = (await operator.get("/api/v1/metrics/summary")).json()
    assert empty["runs_total"] == 0 and empty["success_rate"] is None and empty["verified_runs"] == 0

    task_id = (await operator.post("/api/v1/tasks", json=task_body())).json()["id"]
    for _ in range(2):
        await operator.post(f"/api/v1/tasks/{task_id}/runs", headers={"Idempotency-Key": str(uuid.uuid4())})
    m = (await operator.get("/api/v1/metrics/summary", params={"window": "7d"})).json()
    assert m["runs_total"] == 2 and m["runs_by_status"] == {"queued": 2}
    assert m["success_rate"] is None  # nothing finished yet — never invent a rate
    assert (await operator.get("/api/v1/metrics/summary", params={"window": "1y"})).status_code == 422


async def test_cors_allows_only_configured_origin(anon: httpx.AsyncClient) -> None:
    ok = await anon.options(
        "/api/v1/meta", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET"}
    )
    assert ok.headers.get("access-control-allow-origin") == ORIGIN
    bad = await anon.options(
        "/api/v1/meta", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"}
    )
    assert "access-control-allow-origin" not in bad.headers
