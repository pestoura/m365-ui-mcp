"""Content-free minimum-context escalation shaping for XAPP-016."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.context_economics import ContextEconomicsSample

_MAX_REFERENCES = 50


def _token(field_name: str, value: str) -> None:
    invalid = (
        not value
        or value != value.strip()
        or any(char.isspace() for char in value)
        or "://" in value
        or "@" in value
    )
    if invalid:
        raise ValueError(f"{field_name} must be a non-empty semantic token")


def _digest(value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("reference_id must be lowercase SHA-256 hex")


@dataclass(frozen=True, order=True)
class MinimumContextReference:
    context_kind: str
    reference_id: str

    def __post_init__(self) -> None:
        _token("context_kind", self.context_kind)
        _digest(self.reference_id)


@dataclass(frozen=True)
class MinimumContextEnvelope:
    references: tuple[MinimumContextReference, ...]
    economics: ContextEconomicsSample
    escalation_reason: str | None = None
    content_included: bool = False

    def __post_init__(self) -> None:
        if len(self.references) > _MAX_REFERENCES:
            raise ValueError("minimum context references exceed bounded size")
        if len(self.references) != len(set(self.references)):
            raise ValueError("minimum context references must be unique")
        if self.escalation_reason is not None:
            _token("escalation_reason", self.escalation_reason)
        if self.content_included:
            raise ValueError("minimum context envelope must not include content")

    def to_projection(self) -> dict[str, object]:
        return {
            "references": [
                {
                    "context_kind": reference.context_kind,
                    "reference_id": reference.reference_id,
                }
                for reference in self.references
            ],
            "economics": self.economics.to_metrics(),
            "escalation_reason": self.escalation_reason,
            "content_included": False,
        }


def shape_minimum_context(
    references: tuple[MinimumContextReference, ...],
    economics: ContextEconomicsSample,
    *,
    escalation_reason: str | None = None,
) -> MinimumContextEnvelope:
    """Sort and validate bounded references without accepting raw content."""
    return MinimumContextEnvelope(
        references=tuple(sorted(references)),
        economics=economics,
        escalation_reason=escalation_reason,
    )


__all__ = [
    "MinimumContextEnvelope",
    "MinimumContextReference",
    "shape_minimum_context",
]
