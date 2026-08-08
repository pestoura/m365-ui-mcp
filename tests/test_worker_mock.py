"""Browser worker mock-mode tests."""

from __future__ import annotations

import httpx
import pytest

from planner_browser_worker.app import create_app
from planner_browser_worker.browser import detect_conditional_access_block


@pytest.fixture()
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://worker"
    )


async def test_health(client: httpx.AsyncClient) -> None:
    async with client:
        response = await client.get("/health")
    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["mode"] == "mock"
    assert body["live_ready"] is False


async def test_plans_tasks_snapshot(client: httpx.AsyncClient) -> None:
    async with client:
        plans = (await client.get("/planner/plans")).json()["plans"]
        assert plans
        plan_id = plans[0]["id"]
        tasks = (await client.get("/planner/tasks",
                                  params={"plan_id": plan_id})).json()["tasks"]
        assert tasks
        snapshot = (await client.get(f"/planner/plans/{plan_id}/snapshot")).json()
        assert snapshot["read_only"] is True
        assert snapshot["counts"]["tasks"] == len(tasks)
        missing = await client.get("/planner/plans/nope")
        assert missing.status_code == 404


async def test_no_unapproved_mutating_routes() -> None:
    app = create_app()
    allowed_posts = {"/operations", "/protocol/negotiate"}
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        assert not ({"PUT", "PATCH", "DELETE"} & methods)
        if "POST" in methods:
            assert path in allowed_posts


async def test_session_never_exposes_secrets(client: httpx.AsyncClient) -> None:
    async with client:
        body = (await client.get("/auth/session")).json()
    assert body["secrets_stored_in_state"] is False
    assert "cookie" not in body
    assert "token" not in body


def test_conditional_access_detection() -> None:
    assert detect_conditional_access_block("Your device must be managed to access")
    assert not detect_conditional_access_block("Welcome to Planner")
