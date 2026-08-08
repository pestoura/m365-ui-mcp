"""Shared test fixtures. Tests always run in mock mode."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("PLANNER_MODE", "mock")


@pytest.fixture()
def state_path(tmp_path: Path) -> Path:
    """Temporary SQLite state path."""
    return tmp_path / "state.sqlite3"


@pytest.fixture()
def worker_client() -> Iterator[object]:
    """In-process ASGI transport client for the worker."""
    import httpx

    from planner_browser_worker.app import create_app

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    yield httpx.AsyncClient(transport=transport, base_url="http://worker")
