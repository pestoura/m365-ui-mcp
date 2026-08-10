import pytest

from m365_mcp.xapp_runbook_registry import (
    RunbookLifecycle,
    RunbookRegistration,
    RunbookRegistry,
    RunbookVersion,
)


def _registration(
    version: RunbookVersion,
    lifecycle: RunbookLifecycle,
    digest_char: str,
) -> RunbookRegistration:
    return RunbookRegistration(
        runbook_key="security-review",
        version=version,
        definition_reference_id=digest_char * 64,
        lifecycle=lifecycle,
    )


def test_registry_resolves_exact_and_latest_published_version() -> None:
    v100 = _registration(RunbookVersion(1, 0, 0), RunbookLifecycle.PUBLISHED, "a")
    v110 = _registration(RunbookVersion(1, 1, 0), RunbookLifecycle.PUBLISHED, "b")
    v200 = _registration(RunbookVersion(2, 0, 0), RunbookLifecycle.DRAFT, "c")
    registry = RunbookRegistry((v200, v100, v110))

    assert registry.resolve_exact("security-review", RunbookVersion(1, 0, 0)) is v100
    assert registry.latest_published("security-review") is v110
    assert v110.to_projection() == {
        "runbook_key": "security-review",
        "version": "1.1.0",
        "definition_reference_id": "b" * 64,
        "lifecycle": "PUBLISHED",
    }


def test_registry_does_not_promote_draft_or_retired_versions() -> None:
    published = _registration(RunbookVersion(1, 0, 0), RunbookLifecycle.PUBLISHED, "a")
    retired = _registration(RunbookVersion(9, 0, 0), RunbookLifecycle.RETIRED, "b")
    draft = _registration(RunbookVersion(10, 0, 0), RunbookLifecycle.DRAFT, "c")

    assert RunbookRegistry((retired, draft, published)).latest_published(
        "security-review"
    ) is published


def test_registry_rejects_duplicate_key_version_and_missing_resolution() -> None:
    version = RunbookVersion(1, 0, 0)
    one = _registration(version, RunbookLifecycle.PUBLISHED, "a")
    two = _registration(version, RunbookLifecycle.DRAFT, "b")

    with pytest.raises(ValueError, match="duplicate key/version"):
        RunbookRegistry((one, two))

    registry = RunbookRegistry((one,))
    with pytest.raises(ValueError, match="resolve exactly once"):
        registry.resolve_exact("security-review", RunbookVersion(2, 0, 0))


def test_registry_rejects_invalid_versions_locators_and_unbounded_size() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        RunbookVersion(-1, 0, 0)

    with pytest.raises(ValueError, match="semantic token"):
        RunbookRegistration(
            runbook_key="https://example.invalid",
            version=RunbookVersion(1, 0, 0),
            definition_reference_id="a" * 64,
            lifecycle=RunbookLifecycle.DRAFT,
        )

    item = _registration(RunbookVersion(1, 0, 0), RunbookLifecycle.PUBLISHED, "a")
    oversized = tuple(
        RunbookRegistration(
            runbook_key=f"runbook-{index}",
            version=item.version,
            definition_reference_id="a" * 64,
            lifecycle=RunbookLifecycle.DRAFT,
        )
        for index in range(201)
    )
    with pytest.raises(ValueError, match="bounded size"):
        RunbookRegistry(oversized)
