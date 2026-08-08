"""Bounded result projection operators for CORE-044.

The module is intentionally pure and execution-plane independent so it can be
implemented and tested in parallel. Integration remains gated on CORE-043.
Projection can only reduce or summarize an already-produced semantic result; it
cannot fetch additional data or execute browser operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, TypeAlias

Scalar: TypeAlias = str | int | float | bool | None
Row: TypeAlias = Mapping[str, Scalar]
ProjectedRow: TypeAlias = dict[str, Scalar]

_MAX_PAGE_SIZE = 100
_MAX_TOP_N = 100


class ProjectionKind(StrEnum):
    """Closed result-reduction operators."""

    SELECT = "select"
    COUNT = "count"
    EXISTS = "exists"
    FIRST = "first"
    LATEST = "latest"
    TOP_N = "top_n"
    PAGINATION = "pagination"
    METADATA_ONLY = "metadata_only"


@dataclass(frozen=True)
class ProjectionRequest:
    """Validated bounded projection request."""

    kind: ProjectionKind
    fields: tuple[str, ...] = ()
    sort_field: str | None = None
    top_n: int = 10
    offset: int = 0
    limit: int = 50

    def __post_init__(self) -> None:
        if len(set(self.fields)) != len(self.fields):
            raise ValueError("projection fields must be unique")
        if any(not field.strip() for field in self.fields):
            raise ValueError("projection fields must be non-empty")
        if not 1 <= self.top_n <= _MAX_TOP_N:
            raise ValueError(f"top_n must be between 1 and {_MAX_TOP_N}")
        if self.offset < 0:
            raise ValueError("offset must be non-negative")
        if not 1 <= self.limit <= _MAX_PAGE_SIZE:
            raise ValueError(f"limit must be between 1 and {_MAX_PAGE_SIZE}")
        if self.kind is ProjectionKind.SELECT and not self.fields:
            raise ValueError("select projection requires fields")
        if self.kind is ProjectionKind.LATEST and not self.sort_field:
            raise ValueError("latest projection requires sort_field")


@dataclass(frozen=True)
class ProjectionResult:
    """Projected data plus low-cardinality reduction metadata."""

    kind: ProjectionKind
    data: object
    input_count: int
    output_count: int


def _copy_row(row: Row) -> ProjectedRow:
    return dict(row)


def _select(row: Row, fields: tuple[str, ...]) -> ProjectedRow:
    return {field: row[field] for field in fields if field in row}


def _sortable(value: Scalar) -> tuple[int, str]:
    if value is None:
        return (0, "")
    if isinstance(value, bool):
        return (1, "1" if value else "0")
    if isinstance(value, (int, float)):
        return (2, f"{float(value):030.12f}")
    return (3, value)


def project_rows(rows: list[Row], request: ProjectionRequest) -> ProjectionResult:
    """Apply one closed projection without mutating or expanding input data."""
    input_count = len(rows)

    if request.kind is ProjectionKind.COUNT:
        return ProjectionResult(request.kind, input_count, input_count, 1)

    if request.kind is ProjectionKind.EXISTS:
        return ProjectionResult(request.kind, bool(rows), input_count, 1)

    if request.kind is ProjectionKind.METADATA_ONLY:
        metadata = {"count": input_count}
        return ProjectionResult(request.kind, metadata, input_count, 1)

    if request.kind is ProjectionKind.SELECT:
        data = [_select(row, request.fields) for row in rows]
        return ProjectionResult(request.kind, data, input_count, len(data))

    if request.kind is ProjectionKind.FIRST:
        data = _copy_row(rows[0]) if rows else None
        return ProjectionResult(request.kind, data, input_count, int(data is not None))

    if request.kind is ProjectionKind.LATEST:
        sort_field = request.sort_field
        if sort_field is None:  # constructor invariant, retained for type narrowing
            raise ValueError("latest projection requires sort_field")
        candidates = [row for row in rows if sort_field in row]
        latest = max(candidates, key=lambda row: _sortable(row[sort_field]), default=None)
        data = _copy_row(latest) if latest is not None else None
        return ProjectionResult(request.kind, data, input_count, int(data is not None))

    if request.kind is ProjectionKind.TOP_N:
        data = [_copy_row(row) for row in rows[: request.top_n]]
        return ProjectionResult(request.kind, data, input_count, len(data))

    if request.kind is ProjectionKind.PAGINATION:
        end = request.offset + request.limit
        data = [_copy_row(row) for row in rows[request.offset:end]]
        return ProjectionResult(request.kind, data, input_count, len(data))

    raise AssertionError(f"unhandled projection kind: {request.kind}")


__all__ = [
    "ProjectionKind",
    "ProjectionRequest",
    "ProjectionResult",
    "Row",
    "project_rows",
]
