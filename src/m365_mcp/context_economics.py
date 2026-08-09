"""Content-free token/context economics metrics for CORE-048.

The module accepts numeric counters produced by callers and derives reduction
metrics. It never receives prompt text, result text, tenant content, or secrets.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextEconomicsSample:
    """One bounded numeric sample for semantic result/context economics."""

    input_items: int
    output_items: int
    input_units: int
    output_units: int

    def __post_init__(self) -> None:
        for field_name in ("input_items", "output_items", "input_units", "output_units"):
            value = getattr(self, field_name)
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
        if self.output_items > self.input_items:
            raise ValueError("output_items cannot exceed input_items for reduction metrics")

    @property
    def avoided_items(self) -> int:
        return self.input_items - self.output_items

    @property
    def avoided_units(self) -> int:
        return max(0, self.input_units - self.output_units)

    @property
    def item_reduction_ratio(self) -> float:
        if self.input_items == 0:
            return 0.0
        return self.avoided_items / self.input_items

    @property
    def unit_reduction_ratio(self) -> float:
        if self.input_units == 0:
            return 0.0
        return self.avoided_units / self.input_units

    def to_metrics(self) -> dict[str, int | float]:
        """Return low-cardinality numeric values only."""
        return {
            "input_items": self.input_items,
            "output_items": self.output_items,
            "avoided_items": self.avoided_items,
            "input_units": self.input_units,
            "output_units": self.output_units,
            "avoided_units": self.avoided_units,
            "item_reduction_ratio": self.item_reduction_ratio,
            "unit_reduction_ratio": self.unit_reduction_ratio,
        }


def aggregate_context_economics(
    samples: tuple[ContextEconomicsSample, ...],
) -> ContextEconomicsSample:
    """Aggregate numeric samples without retaining per-result content."""
    return ContextEconomicsSample(
        input_items=sum(sample.input_items for sample in samples),
        output_items=sum(sample.output_items for sample in samples),
        input_units=sum(sample.input_units for sample in samples),
        output_units=sum(sample.output_units for sample in samples),
    )


__all__ = ["ContextEconomicsSample", "aggregate_context_economics"]
