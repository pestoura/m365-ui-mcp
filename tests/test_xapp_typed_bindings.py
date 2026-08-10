from __future__ import annotations

import pytest

from m365_mcp.xapp_typed_bindings import (
    BindingValueKind,
    TypedBindingSet,
    TypedInputBinding,
    TypedOutputReference,
)


def test_typed_binding_carries_only_reference_and_matching_type() -> None:
    source = TypedOutputReference(
        producer_node_id="producer",
        output_key="summary",
        value_kind=BindingValueKind.ROW,
        reference_id="a" * 64,
    )
    binding = TypedInputBinding(
        consumer_node_id="consumer",
        input_key="context",
        expected_kind=BindingValueKind.ROW,
        source=source,
    )
    bindings = TypedBindingSet((binding,))
    projection = bindings.for_consumer("consumer")[0].to_projection()
    assert projection["reference_id"] == "a" * 64
    assert projection["expected_kind"] == "ROW"
    assert not {"payload", "locator", "url", "content"} & set(projection)


def test_typed_binding_fails_closed_on_type_mismatch_and_duplicate_target() -> None:
    source = TypedOutputReference(
        "producer",
        "summary",
        BindingValueKind.SCALAR,
        "b" * 64,
    )
    with pytest.raises(ValueError, match="does not match"):
        TypedInputBinding(
            "consumer",
            "context",
            BindingValueKind.ROW,
            source,
        )
    binding = TypedInputBinding(
        "consumer",
        "context",
        BindingValueKind.SCALAR,
        source,
    )
    with pytest.raises(ValueError, match="bound only once"):
        TypedBindingSet((binding, binding))
