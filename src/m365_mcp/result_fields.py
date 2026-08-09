"""Metadata-driven secret-aware result fields for CORE-046.

Field exposure is explicit rather than inferred from names. Secret fields are
never projected in clear text and are reduced to presence metadata only. This
module is pure and does not inspect browser/session state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class FieldSensitivity(StrEnum):
    """Closed result-field sensitivity classes."""

    STANDARD = "STANDARD"
    SECRET = "SECRET"  # noqa: S105 - classification label, not credential material


class FieldExposure(StrEnum):
    """Closed projection behavior for one result field."""

    VALUE = "VALUE"
    REDACTED = "REDACTED"


@dataclass(frozen=True)
class ResultFieldDefinition:
    """Explicit sensitivity/exposure metadata for one semantic result field."""

    name: str
    sensitivity: FieldSensitivity
    exposure: FieldExposure

    def __post_init__(self) -> None:
        normalized = self.name.strip()
        if not normalized or any(char.isspace() for char in normalized):
            raise ValueError("result field name must be a non-empty semantic token")
        if self.sensitivity is FieldSensitivity.SECRET and self.exposure is FieldExposure.VALUE:
            raise ValueError("secret result field cannot use VALUE exposure")


@dataclass(frozen=True)
class ResultFieldSchema:
    """Complete field metadata for a bounded semantic result mapping."""

    fields: tuple[ResultFieldDefinition, ...]

    def __post_init__(self) -> None:
        names = tuple(field.name for field in self.fields)
        if len(set(names)) != len(names):
            raise ValueError("result field definitions must be unique")

    def by_name(self) -> dict[str, ResultFieldDefinition]:
        return {field.name: field for field in self.fields}


@dataclass(frozen=True)
class SecretAwareProjection:
    """Projected fields plus explicit record of which fields were redacted."""

    fields: dict[str, object]
    redacted_fields: tuple[str, ...]

    @property
    def contains_clear_secret(self) -> bool:
        return False


def project_secret_aware_fields(
    values: Mapping[str, object],
    schema: ResultFieldSchema,
) -> SecretAwareProjection:
    """Project a result mapping using explicit metadata and fail closed on drift."""
    definitions = schema.by_name()
    unknown = tuple(name for name in values if name not in definitions)
    missing = tuple(name for name in definitions if name not in values)
    if unknown:
        raise ValueError(f"unclassified result fields: {','.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"missing classified result fields: {','.join(sorted(missing))}")

    projected: dict[str, object] = {}
    redacted: list[str] = []
    for definition in schema.fields:
        value = values[definition.name]
        if definition.exposure is FieldExposure.VALUE:
            projected[definition.name] = value
            continue

        projected[definition.name] = {
            "redacted": True,
            "present": value is not None,
        }
        redacted.append(definition.name)

    return SecretAwareProjection(
        fields=projected,
        redacted_fields=tuple(redacted),
    )


__all__ = [
    "FieldExposure",
    "FieldSensitivity",
    "ResultFieldDefinition",
    "ResultFieldSchema",
    "SecretAwareProjection",
    "project_secret_aware_fields",
]
