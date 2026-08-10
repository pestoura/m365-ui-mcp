"""Typed output/input reference bindings for XAPP-007.

Bindings carry only semantic type metadata and opaque reference identifiers.
They never embed the referenced result payload or a storage locator.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

_MAX_BINDINGS = 100


class BindingValueKind(StrEnum):
    SCALAR = "SCALAR"
    ROW = "ROW"
    ROW_SET = "ROW_SET"
    ARTIFACT = "ARTIFACT"
    EVIDENCE = "EVIDENCE"


def _token(field: str, value: str) -> None:
    invalid = (
        not value
        or value != value.strip()
        or any(char.isspace() for char in value)
        or "://" in value
    )
    if invalid:
        raise ValueError(f"{field} must be a non-empty semantic token")


def _digest(value: str, *, field: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field} must be lowercase SHA-256 hex")


@dataclass(frozen=True)
class TypedOutputReference:
    producer_node_id: str
    output_key: str
    value_kind: BindingValueKind
    reference_id: str

    def __post_init__(self) -> None:
        _token("producer_node_id", self.producer_node_id)
        _token("output_key", self.output_key)
        _digest(self.reference_id, field="reference_id")


@dataclass(frozen=True)
class TypedInputBinding:
    consumer_node_id: str
    input_key: str
    expected_kind: BindingValueKind
    source: TypedOutputReference

    def __post_init__(self) -> None:
        _token("consumer_node_id", self.consumer_node_id)
        _token("input_key", self.input_key)
        if self.consumer_node_id == self.source.producer_node_id:
            raise ValueError("binding cannot feed a node from its own output")
        if self.expected_kind is not self.source.value_kind:
            raise ValueError("binding value kind does not match consumer expectation")

    def to_projection(self) -> dict[str, object]:
        return {
            "consumer_node_id": self.consumer_node_id,
            "input_key": self.input_key,
            "expected_kind": self.expected_kind.value,
            "producer_node_id": self.source.producer_node_id,
            "output_key": self.source.output_key,
            "reference_id": self.source.reference_id,
        }


@dataclass(frozen=True)
class TypedBindingSet:
    bindings: tuple[TypedInputBinding, ...]

    def __post_init__(self) -> None:
        if len(self.bindings) > _MAX_BINDINGS:
            raise ValueError("typed binding set exceeds bounded size")
        targets = tuple(
            (binding.consumer_node_id, binding.input_key) for binding in self.bindings
        )
        if len(targets) != len(set(targets)):
            raise ValueError("consumer input may be bound only once")

    def for_consumer(self, node_id: str) -> tuple[TypedInputBinding, ...]:
        _token("node_id", node_id)
        return tuple(
            sorted(
                (
                    binding
                    for binding in self.bindings
                    if binding.consumer_node_id == node_id
                ),
                key=lambda binding: binding.input_key,
            )
        )


__all__ = [
    "BindingValueKind",
    "TypedBindingSet",
    "TypedInputBinding",
    "TypedOutputReference",
]
