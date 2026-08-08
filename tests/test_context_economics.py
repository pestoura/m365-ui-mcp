import pytest

import m365_mcp.context_economics as context_economics


def test_context_economics_derives_reduction_without_content() -> None:
    sample = context_economics.ContextEconomicsSample(
        input_items=100,
        output_items=25,
        input_units=1000,
        output_units=300,
    )

    metrics = sample.to_metrics()
    assert metrics["avoided_items"] == 75
    assert metrics["avoided_units"] == 700
    assert metrics["item_reduction_ratio"] == 0.75
    assert metrics["unit_reduction_ratio"] == 0.7
    assert all(isinstance(value, int | float) for value in metrics.values())


def test_zero_inputs_produce_zero_ratios() -> None:
    sample = context_economics.ContextEconomicsSample(
        input_items=0,
        output_items=0,
        input_units=0,
        output_units=0,
    )

    assert sample.item_reduction_ratio == 0.0
    assert sample.unit_reduction_ratio == 0.0


def test_output_units_may_exceed_input_units_without_negative_savings() -> None:
    sample = context_economics.ContextEconomicsSample(
        input_items=2,
        output_items=2,
        input_units=10,
        output_units=12,
    )

    assert sample.avoided_units == 0
    assert sample.unit_reduction_ratio == 0.0


def test_output_item_expansion_is_rejected_for_reduction_metric() -> None:
    with pytest.raises(ValueError, match="output_items cannot exceed input_items"):
        context_economics.ContextEconomicsSample(
            input_items=1,
            output_items=2,
            input_units=10,
            output_units=10,
        )


def test_negative_counters_fail_closed() -> None:
    with pytest.raises(ValueError, match="input_units must be non-negative"):
        context_economics.ContextEconomicsSample(
            input_items=1,
            output_items=1,
            input_units=-1,
            output_units=0,
        )


def test_aggregation_sums_only_numeric_counters() -> None:
    first = context_economics.ContextEconomicsSample(10, 2, 100, 20)
    second = context_economics.ContextEconomicsSample(5, 3, 50, 30)

    aggregate = context_economics.aggregate_context_economics((first, second))

    assert aggregate.input_items == 15
    assert aggregate.output_items == 5
    assert aggregate.input_units == 150
    assert aggregate.output_units == 50
    assert aggregate.avoided_items == 10
    assert aggregate.avoided_units == 100
