"""Fail-closed bearer boundary for the Cloudflare MCP upstream origin.

The public MCP Portal authenticates users. This gate is a separate machine-to-
machine boundary between Cloudflare's MCP server connector and the private M365
origin. Secret material is loaded only from a local file and is never accepted
from an environment variable value.
"""

from __future__ import annotations

import hmac
import os
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from planner_mcp.errors import ConfigurationError

ORIGIN_AUTH_FILE_ENV = "M365_ORIGIN_AUTH_FILE"
_MIN_TOKEN_LENGTH = 32
_MAX_TOKEN_FILE_BYTES = 4096


def load_origin_bearer_token(environ: Mapping[str, str] | None = None) -> str | None:
    """Load the optional upstream bearer token from a tightly-permissioned file."""
    source = os.environ if environ is None else environ
    raw_path = source.get(ORIGIN_AUTH_FILE_ENV, "").strip()
    if not raw_path:
        return None

    path = Path(raw_path)
    if not path.is_absolute():
        raise ConfigurationError(
            "origin auth file must be an absolute path",
            variable=ORIGIN_AUTH_FILE_ENV,
        )

    try:
        info = path.lstat()
    except OSError:
        raise ConfigurationError(
            "origin auth file is unavailable",
            variable=ORIGIN_AUTH_FILE_ENV,
        ) from None

    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ConfigurationError(
            "origin auth file must be a regular non-symlink file",
            variable=ORIGIN_AUTH_FILE_ENV,
        )
    if info.st_mode & 0o077:
        raise ConfigurationError(
            "origin auth file permissions are too broad",
            variable=ORIGIN_AUTH_FILE_ENV,
        )
    if not 0 < info.st_size <= _MAX_TOKEN_FILE_BYTES:
        raise ConfigurationError(
            "origin auth file size is invalid",
            variable=ORIGIN_AUTH_FILE_ENV,
        )

    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError:
        raise ConfigurationError(
            "origin auth file could not be read",
            variable=ORIGIN_AUTH_FILE_ENV,
        ) from None

    if len(token) < _MIN_TOKEN_LENGTH or any(char.isspace() for char in token):
        raise ConfigurationError(
            "origin bearer token does not meet the runtime contract",
            variable=ORIGIN_AUTH_FILE_ENV,
        )
    return token


class OriginBearerMiddleware:
    """Require one exact bearer credential before any MCP HTTP handler executes."""

    def __init__(self, app: Any, token: str) -> None:
        if len(token) < _MIN_TOKEN_LENGTH:
            raise ValueError("origin bearer token is too short")
        self.app = app
        self._token = token

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        presented = self._bearer_from_scope(scope)
        if presented is None or not hmac.compare_digest(presented, self._token):
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"cache-control", b"no-store"),
                        (b"www-authenticate", b'Bearer realm="m365-mcp-origin"'),
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"error":"unauthorized"}',
                }
            )
            return

        await self.app(scope, receive, send)

    @staticmethod
    def _bearer_from_scope(scope: dict[str, Any]) -> str | None:
        for raw_name, raw_value in scope.get("headers", []):
            if raw_name.lower() != b"authorization":
                continue
            try:
                value = raw_value.decode("latin-1")
            except UnicodeDecodeError:
                return None
            scheme, separator, credential = value.partition(" ")
            if not separator or scheme.lower() != "bearer" or not credential:
                return None
            return credential
        return None
