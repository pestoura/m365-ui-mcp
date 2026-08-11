"""Regression tests for the portal-to-origin bearer boundary."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from m365_mcp.origin_auth import OriginBearerMiddleware, load_origin_bearer_token
from planner_mcp.errors import ConfigurationError

TOKEN = "A" * 48


def _secret_file(tmp_path: Path, value: str = TOKEN, mode: int = 0o600) -> Path:
    path = tmp_path / "origin-bearer"
    path.write_text(value, encoding="utf-8")
    path.chmod(mode)
    return path


def test_origin_auth_disabled_when_file_not_configured() -> None:
    assert load_origin_bearer_token({}) is None


def test_origin_auth_requires_absolute_path() -> None:
    with pytest.raises(ConfigurationError):
        load_origin_bearer_token({"M365_ORIGIN_AUTH_FILE": "relative/token"})


def test_origin_auth_rejects_broad_permissions(tmp_path: Path) -> None:
    path = _secret_file(tmp_path, mode=0o644)
    with pytest.raises(ConfigurationError):
        load_origin_bearer_token({"M365_ORIGIN_AUTH_FILE": str(path)})


def test_origin_auth_rejects_short_or_whitespace_token(tmp_path: Path) -> None:
    short = _secret_file(tmp_path, value="too-short")
    with pytest.raises(ConfigurationError):
        load_origin_bearer_token({"M365_ORIGIN_AUTH_FILE": str(short)})

    short.write_text("A" * 32 + " invalid", encoding="utf-8")
    short.chmod(0o600)
    with pytest.raises(ConfigurationError):
        load_origin_bearer_token({"M365_ORIGIN_AUTH_FILE": str(short)})


def test_origin_auth_loads_valid_token(tmp_path: Path) -> None:
    path = _secret_file(tmp_path)
    assert load_origin_bearer_token({"M365_ORIGIN_AUTH_FILE": str(path)}) == TOKEN


async def _invoke(headers: list[tuple[bytes, bytes]]) -> tuple[list[dict[str, Any]], int]:
    called = 0

    async def downstream(scope: dict[str, Any], receive: Any, send: Any) -> None:
        nonlocal called
        called += 1
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = OriginBearerMiddleware(downstream, TOKEN)
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await middleware(
        {"type": "http", "method": "POST", "path": "/mcp", "headers": headers},
        receive,
        send,
    )
    return sent, called


def test_missing_bearer_is_rejected_before_downstream() -> None:
    sent, called = asyncio.run(_invoke([]))
    assert called == 0
    assert sent[0]["status"] == 401
    assert (b"www-authenticate", b'Bearer realm="m365-mcp-origin"') in sent[0]["headers"]


def test_wrong_bearer_is_rejected_before_downstream() -> None:
    sent, called = asyncio.run(_invoke([(b"authorization", b"Bearer wrong-token")]))
    assert called == 0
    assert sent[0]["status"] == 401


def test_correct_bearer_reaches_downstream() -> None:
    sent, called = asyncio.run(
        _invoke([(b"authorization", f"Bearer {TOKEN}".encode("ascii"))])
    )
    assert called == 1
    assert sent[0]["status"] == 204
