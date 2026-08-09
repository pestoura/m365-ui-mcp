import pytest

import m365_mcp.application_registry as application_registry
import m365_mcp.operational_outcome_metrics as operational_metrics


def test_valid_operational_signal_outcome_pairs_project_low_cardinality_metrics() -> None:
    sample = operational_metrics.OperationalOutcomeSample(
        application=application_registry.ApplicationKey.PLANNER,
        signal=operational_metrics.OperationalSignal.READ_BACK,
        outcome=operational_metrics.OperationalOutcome.EFFECT_PRESENT,
        occurrences=2,
    )

    assert sample.to_metrics() == {
        "application": "planner",
        "signal": "READ_BACK",
        "outcome": "EFFECT_PRESENT",
        "occurrences": 2,
    }


def test_invalid_signal_outcome_pair_fails_closed() -> None:
    with pytest.raises(ValueError, match="invalid for operational signal"):
        operational_metrics.OperationalOutcomeSample(
            application=application_registry.ApplicationKey.PLANNER,
            signal=operational_metrics.OperationalSignal.DRIFT,
            outcome=operational_metrics.OperationalOutcome.EFFECT_PRESENT,
        )


def test_occurrences_must_be_positive() -> None:
    with pytest.raises(ValueError, match="occurrences must be positive"):
        operational_metrics.OperationalOutcomeSample(
            application=application_registry.ApplicationKey.PLANNER,
            signal=operational_metrics.OperationalSignal.INDETERMINATE,
            outcome=operational_metrics.OperationalOutcome.DETECTED,
            occurrences=0,
        )


def test_aggregation_groups_only_application_signal_and_outcome() -> None:
    samples = (
        operational_metrics.OperationalOutcomeSample(
            application=application_registry.ApplicationKey.PLANNER,
            signal=operational_metrics.OperationalSignal.DRIFT,
            outcome=operational_metrics.OperationalOutcome.DETECTED,
            occurrences=2,
        ),
        operational_metrics.OperationalOutcomeSample(
            application=application_registry.ApplicationKey.PLANNER,
            signal=operational_metrics.OperationalSignal.DRIFT,
            outcome=operational_metrics.OperationalOutcome.DETECTED,
            occurrences=3,
        ),
    )

    aggregate = operational_metrics.aggregate_operational_outcomes(samples)

    assert len(aggregate) == 1
    assert aggregate[0].occurrences == 5


def test_indeterminate_resolved_is_separate_from_detected() -> None:
    samples = (
        operational_metrics.OperationalOutcomeSample(
            application=application_registry.ApplicationKey.OUTLOOK,
            signal=operational_metrics.OperationalSignal.INDETERMINATE,
            outcome=operational_metrics.OperationalOutcome.DETECTED,
        ),
        operational_metrics.OperationalOutcomeSample(
            application=application_registry.ApplicationKey.OUTLOOK,
            signal=operational_metrics.OperationalSignal.INDETERMINATE,
            outcome=operational_metrics.OperationalOutcome.RESOLVED,
        ),
    )

    aggregate = operational_metrics.aggregate_operational_outcomes(samples)
    assert tuple(item.outcome for item in aggregate) == (
        operational_metrics.OperationalOutcome.DETECTED,
        operational_metrics.OperationalOutcome.RESOLVED,
    )
