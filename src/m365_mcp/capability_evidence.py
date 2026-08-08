"""Sanitized, append-only persistence for UI capability evidence metadata."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from m365_mcp.ui_contract_store import UIContractSet
from m365_mcp.ui_drift import UILifecycleState

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_ALLOWED_SCOPES = frozenset({"common", "application", "surface"})

_DDL = """
CREATE TABLE IF NOT EXISTS capability_ui_evidence (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_id TEXT NOT NULL UNIQUE,
    fragment_id TEXT NOT NULL,
    fragment_version TEXT NOT NULL,
    scope TEXT NOT NULL CHECK(scope IN ('common', 'application', 'surface')),
    application TEXT,
    surface TEXT,
    contract_set_digest TEXT NOT NULL,
    evidence_digest TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK(
        lifecycle_state IN ('HEALTHY', 'STALE', 'DRIFTED', 'RE_ATTESTATION_REQUIRED')
    ),
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_capability_ui_evidence_fragment
    ON capability_ui_evidence(fragment_id, contract_set_digest, sequence DESC);
"""


@dataclass(frozen=True)
class CapabilityEvidenceRecord:
    """One bounded evidence record containing no raw tenant/UI evidence."""

    fragment_id: str
    fragment_version: str
    scope: str
    application: str | None
    surface: str | None
    contract_set_digest: str
    evidence_digest: str
    lifecycle_state: UILifecycleState | str
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not _IDENTIFIER_RE.fullmatch(self.fragment_id):
            raise ValueError("invalid evidence fragment id")
        if not self.fragment_version.strip() or any(
            char.isspace() for char in self.fragment_version
        ):
            raise ValueError("invalid evidence fragment version")
        if self.scope not in _ALLOWED_SCOPES:
            raise ValueError("invalid evidence scope")
        if self.application is not None and not _IDENTIFIER_RE.fullmatch(self.application):
            raise ValueError("invalid evidence application")
        if self.surface is not None and not _IDENTIFIER_RE.fullmatch(self.surface):
            raise ValueError("invalid evidence surface")
        if self.scope == "common" and (self.application is not None or self.surface is not None):
            raise ValueError("common evidence cannot bind application or surface")
        if self.scope == "application" and (not self.application or self.surface is not None):
            raise ValueError("application evidence requires application and no surface")
        if self.scope == "surface" and (not self.application or not self.surface):
            raise ValueError("surface evidence requires application and surface")
        if not _DIGEST_RE.fullmatch(self.contract_set_digest):
            raise ValueError("invalid contract-set evidence digest")
        if not _DIGEST_RE.fullmatch(self.evidence_digest):
            raise ValueError("invalid capability evidence digest")
        try:
            state = UILifecycleState(self.lifecycle_state)
        except ValueError as exc:
            raise ValueError("invalid capability evidence lifecycle state") from exc
        object.__setattr__(self, "lifecycle_state", state)
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("capability evidence timestamp must be timezone-aware")
        object.__setattr__(self, "recorded_at", self.recorded_at.astimezone(timezone.utc))

    @property
    def evidence_id(self) -> str:
        """Return deterministic identity for this exact sanitized evidence record."""
        encoded = json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    def canonical_payload(self) -> dict[str, object]:
        """Return the bounded metadata used for persistence and hashing."""
        state = UILifecycleState(self.lifecycle_state)
        return {
            "fragment_id": self.fragment_id,
            "fragment_version": self.fragment_version,
            "scope": self.scope,
            "application": self.application,
            "surface": self.surface,
            "contract_set_digest": self.contract_set_digest,
            "evidence_digest": self.evidence_digest,
            "lifecycle_state": state.value,
            "recorded_at": _format_timestamp(self.recorded_at),
        }

    def to_dict(self) -> dict[str, object]:
        """Return persisted metadata plus deterministic record identity."""
        return {"evidence_id": self.evidence_id, **self.canonical_payload()}


class CapabilityEvidenceStore:
    """SQLite store that persists only validated metadata/digests, never raw evidence."""

    def __init__(self, path: Path) -> None:
        if not path.is_absolute():
            raise ValueError("capability evidence state path must be absolute")
        self.path = path

    def initialise(self) -> None:
        """Create the isolated evidence table without changing Planner resource identity."""
        with self._connect() as conn:
            conn.executescript(_DDL)

    def append(
        self,
        record: CapabilityEvidenceRecord,
        *,
        contract_set: UIContractSet,
    ) -> str:
        """Append one idempotent record after binding it to the exact contract fragment."""
        self._validate_contract_binding(record, contract_set)
        self.initialise()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO capability_ui_evidence(
                    evidence_id,
                    fragment_id,
                    fragment_version,
                    scope,
                    application,
                    surface,
                    contract_set_digest,
                    evidence_digest,
                    lifecycle_state,
                    recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.evidence_id,
                    record.fragment_id,
                    record.fragment_version,
                    record.scope,
                    record.application,
                    record.surface,
                    record.contract_set_digest,
                    record.evidence_digest,
                    UILifecycleState(record.lifecycle_state).value,
                    _format_timestamp(record.recorded_at),
                ),
            )
        return record.evidence_id

    def latest_records(self, contract_set: UIContractSet) -> tuple[CapabilityEvidenceRecord, ...]:
        """Return at most one latest record per fragment for this exact contract-set digest."""
        fragment_ids = tuple(fragment.fragment_id for fragment in contract_set.fragments)
        if not fragment_ids:
            return ()
        self.initialise()
        placeholders = ",".join("?" for _ in fragment_ids)
        query = f"""
            SELECT fragment_id, fragment_version, scope, application, surface,
                   contract_set_digest, evidence_digest, lifecycle_state, recorded_at
            FROM capability_ui_evidence
            WHERE contract_set_digest = ? AND fragment_id IN ({placeholders})
            ORDER BY sequence DESC
        """
        with self._connect() as conn:
            rows = conn.execute(query, (contract_set.digest(), *fragment_ids)).fetchall()

        latest: dict[str, CapabilityEvidenceRecord] = {}
        for row in rows:
            fragment_id = str(row["fragment_id"])
            if fragment_id in latest:
                continue
            latest[fragment_id] = _record_from_row(row)

        return tuple(
            latest[fragment.fragment_id]
            for fragment in contract_set.fragments
            if fragment.fragment_id in latest
        )

    def lifecycle_overlay(self, contract_set: UIContractSet) -> dict[str, UILifecycleState]:
        """Project persisted lifecycle metadata for only the current contract-set digest."""
        return {
            record.fragment_id: UILifecycleState(record.lifecycle_state)
            for record in self.latest_records(contract_set)
        }

    def _validate_contract_binding(
        self,
        record: CapabilityEvidenceRecord,
        contract_set: UIContractSet,
    ) -> None:
        if record.contract_set_digest != contract_set.digest():
            raise ValueError("capability evidence contract-set digest mismatch")
        matches = tuple(
            fragment
            for fragment in contract_set.fragments
            if fragment.fragment_id == record.fragment_id
        )
        if len(matches) != 1:
            raise ValueError("capability evidence references unknown contract fragment")
        fragment = matches[0]
        expected = (
            fragment.fragment_version,
            fragment.scope,
            fragment.application,
            fragment.surface,
        )
        actual = (
            record.fragment_version,
            record.scope,
            record.application,
            record.surface,
        )
        if actual != expected:
            raise ValueError("capability evidence fragment metadata mismatch")

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path), timeout=30.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn


def _format_timestamp(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _record_from_row(row: sqlite3.Row) -> CapabilityEvidenceRecord:
    return CapabilityEvidenceRecord(
        fragment_id=str(row["fragment_id"]),
        fragment_version=str(row["fragment_version"]),
        scope=str(row["scope"]),
        application=None if row["application"] is None else str(row["application"]),
        surface=None if row["surface"] is None else str(row["surface"]),
        contract_set_digest=str(row["contract_set_digest"]),
        evidence_digest=str(row["evidence_digest"]),
        lifecycle_state=str(row["lifecycle_state"]),
        recorded_at=_parse_timestamp(str(row["recorded_at"])),
    )


__all__ = ["CapabilityEvidenceRecord", "CapabilityEvidenceStore"]
