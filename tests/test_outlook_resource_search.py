from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import readiness, resource_search
from m365_mcp.tool_registry import default_tool_registry


def _ready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.DISCOVERY_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=1,
        blocked_count=0,
        reattestation_count=0,
    )


def _unready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.FOUNDATION_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=0,
        blocked_count=0,
        reattestation_count=0,
    )


def test_resource_search_filters_conjunctively_and_orders_deterministically() -> None:
    request = resource_search.ResourceSearchRequest(
        kind=resource_search.ResourceKind.ROOM,
        minimum_capacity=6,
        required_capabilities=(resource_search.ResourceCapability.ACCESSIBLE,),
    )
    result = resource_search.search_synthetic_resources(request, readiness=_ready())
    assert tuple(item.resource_key for item in result.items) == (
        "room-alpha",
        "room-charlie",
    )
    assert result.total_matching == 2
    assert result.synthetic is True


def test_resource_search_paginates_with_has_more() -> None:
    first = resource_search.search_synthetic_resources(
        resource_search.ResourceSearchRequest(
            kind=resource_search.ResourceKind.ROOM,
            offset=0,
            limit=1,
        ),
        readiness=_ready(),
    )
    second = resource_search.search_synthetic_resources(
        resource_search.ResourceSearchRequest(
            kind=resource_search.ResourceKind.ROOM,
            offset=1,
            limit=1,
        ),
        readiness=_ready(),
    )
    assert tuple(item.resource_key for item in first.items) == ("room-alpha",)
    assert tuple(item.resource_key for item in second.items) == ("room-bravo",)
    assert first.has_more is True


def test_resource_search_rejects_identity_shapes_duplicates_and_bad_bounds() -> None:
    with pytest.raises(ValueError, match="address identity"):
        resource_search.SyntheticResource(
            resource_key="room@example.invalid",
            kind=resource_search.ResourceKind.ROOM,
            capacity=4,
        )
    duplicate = (
        resource_search.SyntheticResource("room-alpha", resource_search.ResourceKind.ROOM, 4),
        resource_search.SyntheticResource("room-alpha", resource_search.ResourceKind.ROOM, 8),
    )
    with pytest.raises(ValueError, match="duplicate resource_key"):
        resource_search.search_synthetic_resources(
            resource_search.ResourceSearchRequest(),
            readiness=_ready(),
            resources=duplicate,
        )
    with pytest.raises(ValueError, match="bounded positive count"):
        resource_search.ResourceSearchRequest(limit=101)
    with pytest.raises(ValueError, match="non-negative"):
        resource_search.ResourceSearchRequest(minimum_capacity=-1)


def test_resource_search_requires_readiness() -> None:
    with pytest.raises(ValueError, match="not ready"):
        resource_search.search_synthetic_resources(
            resource_search.ResourceSearchRequest(),
            readiness=_unready(),
        )


def test_out093_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()


def test_out093_projection_contains_no_live_or_browser_material() -> None:
    result = resource_search.search_synthetic_resources(
        resource_search.ResourceSearchRequest(),
        readiness=_ready(),
    )
    rendered = repr(result).lower()
    for marker in (
        "https://",
        "http://",
        "selector",
        "xpath",
        "css=",
        "cookie",
        "token",
        "graph.microsoft",
        "@",
    ):
        assert marker not in rendered
