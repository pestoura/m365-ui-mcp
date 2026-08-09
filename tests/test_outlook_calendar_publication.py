from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import calendar_publication, readiness
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


def test_publication_key_is_stable_opaque_and_never_a_url() -> None:
    publications, first = calendar_publication.apply_calendar_publication(
        (),
        calendar_publication.PublicationRequest(
            calendar_publication.PublicationAction.PUBLISH,
            "calendar-alpha",
        ),
        readiness=_ready(),
    )
    publications, second = calendar_publication.apply_calendar_publication(
        publications,
        calendar_publication.PublicationRequest(
            calendar_publication.PublicationAction.PUBLISH,
            "calendar-alpha",
        ),
        readiness=_ready(),
    )
    assert first.publication_key == second.publication_key
    assert second.changed is False
    key = second.publication_key
    assert key is not None
    for marker in ("://", "http", "www", ".", "/", "@"):
        assert marker not in key.lower()


def test_publication_detail_change_rotates_opaque_key_and_read_back() -> None:
    publications, first = calendar_publication.apply_calendar_publication(
        (),
        calendar_publication.PublicationRequest(
            calendar_publication.PublicationAction.PUBLISH,
            "calendar-alpha",
            calendar_publication.PublicationDetail.FREE_BUSY_ONLY,
        ),
        readiness=_ready(),
    )
    publications, changed = calendar_publication.apply_calendar_publication(
        publications,
        calendar_publication.PublicationRequest(
            calendar_publication.PublicationAction.PUBLISH,
            "calendar-alpha",
            calendar_publication.PublicationDetail.LIMITED_DETAILS,
        ),
        readiness=_ready(),
    )
    assert changed.changed is True
    assert changed.publication_key != first.publication_key
    state = calendar_publication.read_calendar_publication(
        publications,
        calendar_key="calendar-alpha",
        readiness=_ready(),
    )
    assert state.is_published is True
    assert state.detail is calendar_publication.PublicationDetail.LIMITED_DETAILS


def test_unpublish_is_idempotent_and_proves_absence() -> None:
    publications, _ = calendar_publication.apply_calendar_publication(
        (),
        calendar_publication.PublicationRequest(
            calendar_publication.PublicationAction.PUBLISH,
            "calendar-alpha",
        ),
        readiness=_ready(),
    )
    publications, removed = calendar_publication.apply_calendar_publication(
        publications,
        calendar_publication.PublicationRequest(
            calendar_publication.PublicationAction.UNPUBLISH,
            "calendar-alpha",
        ),
        readiness=_ready(),
    )
    assert removed.changed is True
    assert removed.publication_key is None
    _, absent = calendar_publication.apply_calendar_publication(
        publications,
        calendar_publication.PublicationRequest(
            calendar_publication.PublicationAction.UNPUBLISH,
            "calendar-alpha",
        ),
        readiness=_ready(),
    )
    assert absent.changed is False
    assert absent.verified is True


def test_publication_rejects_location_shaped_key() -> None:
    with pytest.raises(ValueError, match="must not encode a location"):
        calendar_publication.SyntheticPublication(
            "calendar-alpha",
            "https://example.invalid/publication",
            calendar_publication.PublicationDetail.FREE_BUSY_ONLY,
        )


def test_out097_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()


def test_out097_result_contains_no_live_or_browser_material() -> None:
    _, result = calendar_publication.apply_calendar_publication(
        (),
        calendar_publication.PublicationRequest(
            calendar_publication.PublicationAction.PUBLISH,
            "calendar-alpha",
        ),
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
