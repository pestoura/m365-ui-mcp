import pytest

from m365_mcp.xapp_runbook_promotion import (
    RunbookPromotionAction,
    RunbookPromotionPlan,
    prepare_runbook_promotion,
)
from m365_mcp.xapp_runbook_registry import (
    RunbookLifecycle,
    RunbookRegistration,
    RunbookVersion,
)


def _registration(lifecycle: RunbookLifecycle) -> RunbookRegistration:
    return RunbookRegistration(
        runbook_key="security-review",
        version=RunbookVersion(1, 2, 3),
        definition_reference_id="a" * 64,
        lifecycle=lifecycle,
    )


def test_publish_and_retire_are_immutable_prepared_transitions() -> None:
    draft = _registration(RunbookLifecycle.DRAFT)
    publish = prepare_runbook_promotion(
        draft,
        RunbookPromotionAction.PUBLISH,
        canonical_definition_digest="a" * 64,
    )

    assert draft.lifecycle is RunbookLifecycle.DRAFT
    assert publish.after.lifecycle is RunbookLifecycle.PUBLISHED
    assert publish.after.registry_key == draft.registry_key
    assert publish.execution_performed is False

    retire = prepare_runbook_promotion(
        publish.after,
        RunbookPromotionAction.RETIRE,
        canonical_definition_digest="a" * 64,
    )
    assert retire.after.lifecycle is RunbookLifecycle.RETIRED
    assert retire.execution_performed is False


def test_promotion_fails_closed_on_digest_or_lifecycle_mismatch() -> None:
    with pytest.raises(ValueError, match="digest does not match"):
        prepare_runbook_promotion(
            _registration(RunbookLifecycle.DRAFT),
            RunbookPromotionAction.PUBLISH,
            canonical_definition_digest="b" * 64,
        )

    with pytest.raises(ValueError, match="not allowed"):
        prepare_runbook_promotion(
            _registration(RunbookLifecycle.RETIRED),
            RunbookPromotionAction.PUBLISH,
            canonical_definition_digest="a" * 64,
        )


def test_promotion_plan_cannot_change_identity_or_claim_execution() -> None:
    before = _registration(RunbookLifecycle.DRAFT)
    changed = RunbookRegistration(
        runbook_key="other-review",
        version=before.version,
        definition_reference_id=before.definition_reference_id,
        lifecycle=RunbookLifecycle.PUBLISHED,
    )
    with pytest.raises(ValueError, match="key/version identity"):
        RunbookPromotionPlan(before, changed, RunbookPromotionAction.PUBLISH)

    with pytest.raises(ValueError, match="must not execute"):
        RunbookPromotionPlan(
            before,
            RunbookRegistration(
                runbook_key=before.runbook_key,
                version=before.version,
                definition_reference_id=before.definition_reference_id,
                lifecycle=RunbookLifecycle.PUBLISHED,
            ),
            RunbookPromotionAction.PUBLISH,
            execution_performed=True,
        )
