from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    contact_preferences,
    mock_ui,
    people_reads,
    readiness,
)
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


def _contacts() -> tuple[people_reads.SyntheticContact, ...]:
    return (people_reads.SyntheticContact("person-alpha", "Alex Example"),)


def test_contact_categories_and_favorite_are_independent_and_read_back() -> None:
    fixture = mock_ui.default_outlook_fixture()
    preferences: tuple[contact_preferences.ContactPreference, ...] = ()
    preferences, categories = contact_preferences.apply_contact_preference(
        fixture,
        _contacts(),
        preferences,
        contact_preferences.ContactPreferenceRequest(
            contact_preferences.ContactPreferenceAction.SET_CATEGORIES,
            "person-alpha",
            category_keys=("category-security", "category-architecture"),
        ),
        readiness=_ready(),
    )
    assert categories.read_back.category_keys == (
        "category-architecture",
        "category-security",
    )
    preferences, favorite = contact_preferences.apply_contact_preference(
        fixture,
        _contacts(),
        preferences,
        contact_preferences.ContactPreferenceRequest(
            contact_preferences.ContactPreferenceAction.SET_FAVORITE,
            "person-alpha",
            favorite=True,
        ),
        readiness=_ready(),
    )
    assert favorite.read_back.favorite is True
    assert favorite.read_back.category_keys == categories.read_back.category_keys
    assert favorite.verified is True


def test_contact_preference_is_idempotent_and_requires_existing_contact() -> None:
    fixture = mock_ui.default_outlook_fixture()
    existing = (
        contact_preferences.ContactPreference(
            "person-alpha",
            ("category-security",),
            True,
        ),
    )
    updated, result = contact_preferences.apply_contact_preference(
        fixture,
        _contacts(),
        existing,
        contact_preferences.ContactPreferenceRequest(
            contact_preferences.ContactPreferenceAction.SET_FAVORITE,
            "person-alpha",
            favorite=True,
        ),
        readiness=_ready(),
    )
    assert updated == existing
    assert result.changed is False
    with pytest.raises(ValueError, match="not found"):
        contact_preferences.apply_contact_preference(
            fixture,
            (),
            (),
            contact_preferences.ContactPreferenceRequest(
                contact_preferences.ContactPreferenceAction.SET_FAVORITE,
                "person-alpha",
                favorite=True,
            ),
            readiness=_ready(),
        )


def test_contact_preferences_reject_duplicate_or_identity_shaped_categories() -> None:
    with pytest.raises(ValueError, match="unique"):
        contact_preferences.ContactPreference(
            "person-alpha",
            ("category-a", "category-a"),
        )
    with pytest.raises(ValueError, match="opaque semantic token"):
        contact_preferences.ContactPreference(
            "person-alpha",
            ("category@example.invalid",),
        )


def test_out101_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
