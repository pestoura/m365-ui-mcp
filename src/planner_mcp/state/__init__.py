"""SQLite state package foundation (WAL, FULL sync, FKs, busy timeout)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1

_DDL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS resource (
    external_id TEXT PRIMARY KEY,
    source_id TEXT,
    kind TEXT NOT NULL,
    desired_state TEXT,
    observed_state TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS resource_lock (
    lock_key TEXT PRIMARY KEY,
    lock_type TEXT NOT NULL,
    owner TEXT NOT NULL,
    acquired_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT
);
CREATE TABLE IF NOT EXISTS idempotency (
    idempotency_key TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    result_hash TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS saga (
    saga_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS checkpoint (
    checkpoint_id TEXT PRIMARY KEY,
    saga_id TEXT NOT NULL REFERENCES saga(saga_id) ON DELETE CASCADE,
    step TEXT NOT NULL,
    payload TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS approval (
    approval_id TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_at TEXT NOT NULL DEFAULT (datetime('now')),
    decided_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_event (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_resource_kind ON resource(kind);
CREATE INDEX IF NOT EXISTS ix_checkpoint_saga ON checkpoint(saga_id);
"""


def connect(path: Path) -> sqlite3.Connection:
    """Open a hardened SQLite connection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def initialise(path: Path) -> None:
    """Create the schema if needed and record the schema version."""
    with closing_connection(path) as conn:
        conn.executescript(_DDL)
        conn.execute(
            "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )


@contextmanager
def closing_connection(path: Path) -> Iterator[sqlite3.Connection]:
    """Context manager yielding a hardened connection."""
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()


def health(path: Path) -> dict[str, object]:
    """Return SQLite health evidence."""
    try:
        with closing_connection(path) as conn:
            journal = str(conn.execute("PRAGMA journal_mode").fetchone()[0])
            fk = int(conn.execute("PRAGMA foreign_keys").fetchone()[0])
            integrity = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        return {
            "ok": integrity == "ok",
            "journal_mode": journal,
            "foreign_keys": bool(fk),
            "integrity": integrity,
        }
    except sqlite3.Error as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": type(exc).__name__}


__all__ = [
    "SCHEMA_VERSION",
    "closing_connection",
    "connect",
    "health",
    "initialise",
]
