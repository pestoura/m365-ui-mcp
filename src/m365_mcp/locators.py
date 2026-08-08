"""Closed semantic locator model for Microsoft 365 UI contracts.

Accessible strategies are always preferred. Non-accessible fallback selectors
require explicit evidence and this module never exposes browser execution
primitives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class LocatorStrategy(StrEnum):
    """Closed locator strategies ordered from semantic to fallback."""

    ROLE = "role"
    LABEL = "label"
    PLACEHOLDER = "placeholder"
    TEST_ID = "test_id"
    CSS = "css"


_PRIORITY = {
    LocatorStrategy.ROLE: 0,
    LocatorStrategy.LABEL: 1,
    LocatorStrategy.PLACEHOLDER: 2,
    LocatorStrategy.TEST_ID: 3,
    LocatorStrategy.CSS: 4,
}
_FALLBACK = frozenset({LocatorStrategy.TEST_ID, LocatorStrategy.CSS})
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class LocatorCandidate:
    """One validated candidate; fallback candidates must carry evidence."""

    strategy: LocatorStrategy
    value: str
    name: str | None = None
    evidence_digest: str | None = None

    def __post_init__(self) -> None:
        value = self.value.strip()
        if not value or value != self.value:
            raise ValueError("locator value must be non-empty and trimmed")
        if self.strategy is LocatorStrategy.ROLE:
            if not self.name or not self.name.strip() or self.name != self.name.strip():
                raise ValueError("role locator requires a trimmed accessible name")
        elif self.name is not None:
            raise ValueError("accessible name is only valid for role locators")

        if self.strategy in _FALLBACK:
            if not self.evidence_digest or not _DIGEST_RE.fullmatch(
                self.evidence_digest
            ):
                raise ValueError("fallback locator requires sha256 evidence digest")
        elif self.evidence_digest is not None:
            raise ValueError("accessible locator must not depend on fallback evidence")

        lowered = value.lower()
        if self.strategy is LocatorStrategy.CSS and (
            lowered.startswith("xpath=")
            or lowered.startswith("//")
            or "javascript:" in lowered
        ):
            raise ValueError("unsafe locator primitive is not permitted")

    @property
    def is_accessible(self) -> bool:
        return self.strategy not in _FALLBACK

    @property
    def is_fallback(self) -> bool:
        return self.strategy in _FALLBACK

    def to_dict(self) -> dict[str, str]:
        result = {"strategy": self.strategy.value, "value": self.value}
        if self.name is not None:
            result["name"] = self.name
        if self.evidence_digest is not None:
            result["evidence_digest"] = self.evidence_digest
        return result


@dataclass(frozen=True)
class LocatorPlan:
    """Validated semantic locator plan with deterministic accessibility priority."""

    selector_key: str
    candidates: tuple[LocatorCandidate, ...]

    def __post_init__(self) -> None:
        if not self.selector_key or self.selector_key != self.selector_key.strip():
            raise ValueError("selector key must be non-empty and trimmed")
        if not self.candidates:
            raise ValueError("locator plan requires at least one candidate")
        identities = {
            (candidate.strategy, candidate.value, candidate.name)
            for candidate in self.candidates
        }
        if len(identities) != len(self.candidates):
            raise ValueError("locator plan contains duplicate candidates")

    def ordered_candidates(self) -> tuple[LocatorCandidate, ...]:
        """Return deterministic candidates with accessible semantics first."""
        indexed = enumerate(self.candidates)
        ordered = sorted(indexed, key=lambda item: (_PRIORITY[item[1].strategy], item[0]))
        return tuple(candidate for _, candidate in ordered)

    @property
    def primary(self) -> LocatorCandidate:
        return self.ordered_candidates()[0]

    def to_dict(self) -> dict[str, object]:
        return {
            "selector_key": self.selector_key,
            "candidates": [candidate.to_dict() for candidate in self.ordered_candidates()],
        }


def locator_plan_from_metadata(
    selector_key: str,
    metadata: dict[str, Any],
) -> LocatorPlan | None:
    """Parse optional structured locator metadata with a closed schema."""
    raw = metadata.get("locators")
    if raw is None:
        return None
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"selector {selector_key} locators must be a non-empty list")

    candidates: list[LocatorCandidate] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError(f"selector {selector_key} locator must be an object")
        unknown = set(item) - {"strategy", "value", "name", "evidence_digest"}
        if unknown:
            raise ValueError(f"selector {selector_key} locator contains unknown fields")
        try:
            strategy = LocatorStrategy(str(item.get("strategy", "")))
        except ValueError as exc:
            raise ValueError(f"selector {selector_key} uses unsupported locator strategy") from exc
        candidates.append(
            LocatorCandidate(
                strategy=strategy,
                value=str(item.get("value", "")),
                name=(str(item["name"]) if item.get("name") is not None else None),
                evidence_digest=(
                    str(item["evidence_digest"])
                    if item.get("evidence_digest") is not None
                    else None
                ),
            )
        )
    return LocatorPlan(selector_key=selector_key, candidates=tuple(candidates))


__all__ = [
    "LocatorCandidate",
    "LocatorPlan",
    "LocatorStrategy",
    "locator_plan_from_metadata",
]
