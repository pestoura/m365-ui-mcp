"""Persistent single-use approval consumption for CORE-036.

Approvals are bound to the exact CORE-035 approval-plan digest. The store uses
SQLite transactions so two consumers cannot successfully spend the same
approval, including when they use separate store instances or processes.
"""

from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from m365_mcp.approval_digest import ApprovalPlanDigest


class ApprovalConsumptionStatus(StrEnum):
    """Closed outcomes for one approval-consumption attempt."""

    CONSUMED = "CONSUMED"
    NOT_FOUND = "NOT_FOUND"
    DIGEST_MISMATCH = "DIGEST_MISMATCH"
    ALREADY_CONSUMED = "ALREADY_CONSUMED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class ApprovalGrant:
    """Opaque handle for one persisted approval bound to one plan digest."""

    approval_id: str
    digest: ApprovalPlanDigest
    created_at: datetime
    expires_at: datetime | None


@dataclass(frozen=True)
class ApprovalConsumption:
    """Sanitized result of attempting to consume one persisted approval."""

    status: ApprovalConsumptionStatus
    approval_id: str
    consumed_at: datetime | None = None

    @property
    def consumed(self) -> bool:
        return self.status is ApprovalConsumptionStatus.CONSUMED


def _require_aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return _require_aware(value, field_name="timestamp").isoformat(timespec="microseconds")


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    return _require_aware(parsed, field_name="stored timestamp")


def _validate_approval_id(value: str) -> None:
    if not 16 <= len(value) <= 128:
        raise ValueError("approval_id must be between 16 and 128 characters")
    if any(not (char.isascii() and (char.isalnum() or char in "-_")) for char in value):
        raise ValueError("approval_id must be opaque URL-safe ASCII")


class ApprovalStore:
    """SQLite-backed approval registry with atomic single-use consumption."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_grants (
                    approval_id TEXT PRIMARY KEY,
                    digest_schema TEXT NOT NULL,
                    digest_algorithm TEXT NOT NULL,
                    digest_value TEXT NOT NULL,
                    node_count INTEGER NOT NULL CHECK (node_count >= 2),
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    consumed_at TEXT
                )
                """
            )

    def issue(
        self,
        digest: ApprovalPlanDigest,
        *,
        approval_id: str | None = None,
        created_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> ApprovalGrant:
        """Persist one unconsumed approval for an exact immutable plan digest."""
        resolved_id = approval_id or secrets.token_urlsafe(24)
        _validate_approval_id(resolved_id)
        created = _require_aware(created_at or datetime.now(UTC), field_name="created_at")
        expires = (
            _require_aware(expires_at, field_name="expires_at") if expires_at is not None else None
        )
        if expires is not None and expires <= created:
            raise ValueError("expires_at must be later than created_at")

        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO approval_grants (
                        approval_id,
                        digest_schema,
                        digest_algorithm,
                        digest_value,
                        node_count,
                        created_at,
                        expires_at,
                        consumed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        resolved_id,
                        digest.schema_version,
                        digest.algorithm,
                        digest.value,
                        digest.node_count,
                        _timestamp(created),
                        _timestamp(expires) if expires is not None else None,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("approval_id already exists") from exc

        return ApprovalGrant(
            approval_id=resolved_id,
            digest=digest,
            created_at=created,
            expires_at=expires,
        )

    def consume(
        self,
        approval_id: str,
        digest: ApprovalPlanDigest,
        *,
        consumed_at: datetime | None = None,
    ) -> ApprovalConsumption:
        """Atomically spend one approval exactly once for the matching digest."""
        _validate_approval_id(approval_id)
        consumed = _require_aware(
            consumed_at or datetime.now(UTC),
            field_name="consumed_at",
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT
                    digest_schema,
                    digest_algorithm,
                    digest_value,
                    node_count,
                    expires_at,
                    consumed_at
                FROM approval_grants
                WHERE approval_id = ?
                """,
                (approval_id,),
            ).fetchone()

            if row is None:
                connection.rollback()
                return ApprovalConsumption(ApprovalConsumptionStatus.NOT_FOUND, approval_id)

            digest_matches = (
                row["digest_schema"] == digest.schema_version
                and row["digest_algorithm"] == digest.algorithm
                and row["digest_value"] == digest.value
                and row["node_count"] == digest.node_count
            )
            if not digest_matches:
                connection.rollback()
                return ApprovalConsumption(ApprovalConsumptionStatus.DIGEST_MISMATCH, approval_id)

            previous_consumed = _parse_timestamp(row["consumed_at"])
            if previous_consumed is not None:
                connection.rollback()
                return ApprovalConsumption(
                    ApprovalConsumptionStatus.ALREADY_CONSUMED,
                    approval_id,
                    previous_consumed,
                )

            expires = _parse_timestamp(row["expires_at"])
            if expires is not None and consumed >= expires:
                connection.rollback()
                return ApprovalConsumption(ApprovalConsumptionStatus.EXPIRED, approval_id)

            cursor = connection.execute(
                """
                UPDATE approval_grants
                SET consumed_at = ?
                WHERE approval_id = ?
                  AND consumed_at IS NULL
                  AND digest_schema = ?
                  AND digest_algorithm = ?
                  AND digest_value = ?
                  AND node_count = ?
                """,
                (
                    _timestamp(consumed),
                    approval_id,
                    digest.schema_version,
                    digest.algorithm,
                    digest.value,
                    digest.node_count,
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return ApprovalConsumption(
                    ApprovalConsumptionStatus.ALREADY_CONSUMED,
                    approval_id,
                )

            connection.commit()
            return ApprovalConsumption(
                ApprovalConsumptionStatus.CONSUMED,
                approval_id,
                consumed,
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


__all__ = [
    "ApprovalConsumption",
    "ApprovalConsumptionStatus",
    "ApprovalGrant",
    "ApprovalStore",
]
