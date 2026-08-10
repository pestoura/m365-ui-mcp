import pytest

from m365_mcp.context_economics import ContextEconomicsSample
from m365_mcp.xapp_minimum_context import (
    MinimumContextEnvelope,
    MinimumContextReference,
    shape_minimum_context,
)


def test_minimum_context_sorts_opaque_references_and_projects_metrics_only() -> None:
    economics = ContextEconomicsSample(10, 2, 1000, 120)
    envelope = shape_minimum_context(
        (
            MinimumContextReference("result", "b" * 64),
            MinimumContextReference("artifact", "a" * 64),
        ),
        economics,
        escalation_reason="AMBIGUOUS_RESULT",
    )

    assert envelope.references == (
        MinimumContextReference("artifact", "a" * 64),
        MinimumContextReference("result", "b" * 64),
    )
    projection = envelope.to_projection()
    assert projection["content_included"] is False
    assert projection["economics"]["avoided_items"] == 8
    assert projection["economics"]["avoided_units"] == 880
    assert set(projection) == {
        "references",
        "economics",
        "escalation_reason",
        "content_included",
    }


def test_minimum_context_rejects_duplicate_or_unbounded_references() -> None:
    reference = MinimumContextReference("result", "a" * 64)
    economics = ContextEconomicsSample(1, 1, 1, 1)

    with pytest.raises(ValueError, match="must be unique"):
        MinimumContextEnvelope((reference, reference), economics)

    oversized = tuple(
        MinimumContextReference(f"kind-{index}", f"{index:064x}")
        for index in range(51)
    )
    with pytest.raises(ValueError, match="bounded size"):
        MinimumContextEnvelope(oversized, economics)


def test_minimum_context_rejects_identity_or_locator_like_tokens() -> None:
    with pytest.raises(ValueError, match="semantic token"):
        MinimumContextReference("https://example.invalid", "a" * 64)

    with pytest.raises(ValueError, match="semantic token"):
        MinimumContextReference("user@example.invalid", "a" * 64)

    with pytest.raises(ValueError, match="SHA-256"):
        MinimumContextReference("result", "not-a-digest")


def test_minimum_context_can_never_claim_raw_content() -> None:
    with pytest.raises(ValueError, match="must not include content"):
        MinimumContextEnvelope(
            references=(),
            economics=ContextEconomicsSample(0, 0, 0, 0),
            content_included=True,
        )
