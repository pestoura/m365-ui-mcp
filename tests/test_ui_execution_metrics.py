import pytest

import m365_mcp.application_registry as application_registry
import m365_mcp.ui_execution_metrics as ui_metrics


def test_ui_execution_sample_projects_only_closed_labels_and_numbers() -> None:
    sample = ui_metrics.UIExecutionSample(
        application=application_registry.ApplicationKey.PLANNER,
        stage=ui_metrics.UIExecutionStage.READ,
        outcome=ui_metrics.UIExecutionOutcome.SUCCESS,
        duration_ms=125,
        interaction_count=2,
        retry_count=1,
        read_back_count=1,
    )

    assert sample.to_metrics() == {
        "application": "planner",
        "stage": "READ",
        "outcome": "SUCCESS",
        "duration_ms": 125,
        "interaction_count": 2,
        "retry_count": 1,
        "read_back_count": 1,
    }


def test_negative_numeric_counters_fail_closed() -> None:
    with pytest.raises(ValueError, match="duration_ms must be non-negative"):
        ui_metrics.UIExecutionSample(
            application=application_registry.ApplicationKey.PLANNER,
            stage=ui_metrics.UIExecutionStage.NAVIGATION,
            outcome=ui_metrics.UIExecutionOutcome.FAILED,
            duration_ms=-1,
        )


def test_aggregation_uses_only_low_cardinality_dimensions() -> None:
    samples = (
        ui_metrics.UIExecutionSample(
            application=application_registry.ApplicationKey.PLANNER,
            stage=ui_metrics.UIExecutionStage.READ,
            outcome=ui_metrics.UIExecutionOutcome.SUCCESS,
            duration_ms=100,
            interaction_count=1,
        ),
        ui_metrics.UIExecutionSample(
            application=application_registry.ApplicationKey.PLANNER,
            stage=ui_metrics.UIExecutionStage.READ,
            outcome=ui_metrics.UIExecutionOutcome.SUCCESS,
            duration_ms=200,
            interaction_count=2,
            retry_count=1,
        ),
    )

    aggregates = ui_metrics.aggregate_ui_execution_samples(samples)
    assert len(aggregates) == 1
    aggregate = aggregates[0]
    assert aggregate.executions == 2
    assert aggregate.total_duration_ms == 300
    assert aggregate.total_interactions == 3
    assert aggregate.total_retries == 1
    assert aggregate.average_duration_ms == 150.0


def test_different_outcomes_remain_separate_metric_series() -> None:
    samples = (
        ui_metrics.UIExecutionSample(
            application=application_registry.ApplicationKey.PLANNER,
            stage=ui_metrics.UIExecutionStage.READ,
            outcome=ui_metrics.UIExecutionOutcome.SUCCESS,
            duration_ms=10,
        ),
        ui_metrics.UIExecutionSample(
            application=application_registry.ApplicationKey.PLANNER,
            stage=ui_metrics.UIExecutionStage.READ,
            outcome=ui_metrics.UIExecutionOutcome.TIMEOUT,
            duration_ms=20,
        ),
    )

    aggregates = ui_metrics.aggregate_ui_execution_samples(samples)
    assert tuple(item.outcome for item in aggregates) == (
        ui_metrics.UIExecutionOutcome.SUCCESS,
        ui_metrics.UIExecutionOutcome.TIMEOUT,
    )
