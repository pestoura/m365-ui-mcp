"""Immutable bounded runbook registry/versioning for XAPP-011."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

_MAX_RUNBOOKS = 200


class RunbookLifecycle(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    RETIRED = "RETIRED"


def _token(field: str, value: str) -> None:
    invalid = (
        not value
        or value != value.strip()
        or any(char.isspace() for char in value)
        or "://" in value
    )
    if invalid:
        raise ValueError(f"{field} must be a non-empty semantic token")


def _digest(value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("definition_reference_id must be lowercase SHA-256 hex")


@dataclass(frozen=True, order=True)
class RunbookVersion:
    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        if min(self.major, self.minor, self.patch) < 0:
            raise ValueError("runbook version components must be non-negative")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class RunbookRegistration:
    runbook_key: str
    version: RunbookVersion
    definition_reference_id: str
    lifecycle: RunbookLifecycle

    def __post_init__(self) -> None:
        _token("runbook_key", self.runbook_key)
        _digest(self.definition_reference_id)

    @property
    def registry_key(self) -> tuple[str, RunbookVersion]:
        return (self.runbook_key, self.version)

    def to_projection(self) -> dict[str, object]:
        return {
            "runbook_key": self.runbook_key,
            "version": str(self.version),
            "definition_reference_id": self.definition_reference_id,
            "lifecycle": self.lifecycle.value,
        }


@dataclass(frozen=True)
class RunbookRegistry:
    registrations: tuple[RunbookRegistration, ...]

    def __post_init__(self) -> None:
        if len(self.registrations) > _MAX_RUNBOOKS:
            raise ValueError("runbook registry exceeds bounded size")
        keys = tuple(item.registry_key for item in self.registrations)
        if len(keys) != len(set(keys)):
            raise ValueError("runbook registry contains duplicate key/version")

    def resolve_exact(
        self,
        runbook_key: str,
        version: RunbookVersion,
    ) -> RunbookRegistration:
        _token("runbook_key", runbook_key)
        matches = tuple(
            item
            for item in self.registrations
            if item.runbook_key == runbook_key and item.version == version
        )
        if len(matches) != 1:
            raise ValueError("runbook key/version must resolve exactly once")
        return matches[0]

    def latest_published(self, runbook_key: str) -> RunbookRegistration:
        _token("runbook_key", runbook_key)
        matches = tuple(
            item
            for item in self.registrations
            if item.runbook_key == runbook_key
            and item.lifecycle is RunbookLifecycle.PUBLISHED
        )
        if not matches:
            raise ValueError("runbook has no published version")
        return max(matches, key=lambda item: item.version)


__all__ = [
    "RunbookLifecycle",
    "RunbookRegistration",
    "RunbookRegistry",
    "RunbookVersion",
]
