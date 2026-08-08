from __future__ import annotations

import pytest

import m365_mcp.result_projection as result_projection


ROWS = [
    {"id": "a", "title": "Alpha", "updated": "2026-08-01T10:00:00Z"},
    {"id": "b", "title": "Beta", "updated": "2026-08-03T10:00:00Z"},
    {"id": "c", "title": "Gamma", "updated": "2026-08-02T10:00:00Z"},
]


def test_select_reduces_fields_without_mutating_input() -> None:
    result = result_projection.project_rows(
        ROWS,
        result_projection.ProjectionRequest(
            result_projection.ProjectionKind.SELECT,
            fields=("id", "title"),
        ),
    )

    assert result.data == [
        {"id": "a", "title": "Alpha"},
        {"id": "b", "title": "Beta"},
        {"id": "c", "title": "Gamma"},
    ]
    assert result.input_count == 3
    assert result.output_count == 3
    assert ROWS[0]["updated"] == "2026-08-01T10:00:00Z"


def test_count_exists_first_and_metadata_only_are_bounded() -> None:
    count = result_projection.project_rows(
        ROWS,
        result_projection.ProjectionRequest(result_projection.ProjectionKind.COUNT),
    )
    exists = result_projection.project_rows(
        ROWS,
        result_projection.ProjectionRequest(result_projection.ProjectionKind.EXISTS),
    )
    missing = result_projection.project_rows(
        [],
        result_projection.ProjectionRequest(result_projection.ProjectionKind.EXISTS),
    )
    first = result_projection.project_rows(
        ROWS,
        result_projection.ProjectionRequest(result_projection.ProjectionKind.FIRST),
    )
    empty_first = result_projection.project_rows(
        [],
        result_projection.ProjectionRequest(result_projection.ProjectionKind.FIRST),
    )
    metadata = result_projection.project_rows(
        ROWS,
        result_projection.ProjectionRequest(result_projection.ProjectionKind.METADATA_ONLY),
    )

    assert count.data == 3
    assert exists.data is True
    assert missing.data is False
    assert first.data == ROWS[0]
    assert empty_first.data is None
    assert metadata.data == {"count": 3}


def test_latest_uses_explicit_sort_field() -> None:
    result = result_projection.project_rows(
        ROWS,
        result_projection.ProjectionRequest(
            result_projection.ProjectionKind.LATEST,
            sort_field="updated",
        ),
    )
    assert result.data == ROWS[1]


def test_top_n_and_pagination_are_bounded() -> None:
    top = result_projection.project_rows(
        ROWS,
        result_projection.ProjectionRequest(result_projection.ProjectionKind.TOP_N, top_n=2),
    )
    page = result_projection.project_rows(
        ROWS,
        result_projection.ProjectionRequest(
            result_projection.ProjectionKind.PAGINATION,
            offset=1,
            limit=1,
        ),
    )

    assert top.data == ROWS[:2]
    assert top.output_count == 2
    assert page.data == [ROWS[1]]
    assert page.output_count == 1


def test_projection_request_rejects_unbounded_or_ambiguous_shapes() -> None:
    request = result_projection.ProjectionRequest
    kind = result_projection.ProjectionKind

    with pytest.raises(ValueError, match="select projection requires fields"):
        request(kind.SELECT)
    with pytest.raises(ValueError, match="latest projection requires sort_field"):
        request(kind.LATEST)
    with pytest.raises(ValueError, match="top_n must be between"):
        request(kind.TOP_N, top_n=101)
    with pytest.raises(ValueError, match="limit must be between"):
        request(kind.PAGINATION, limit=101)
    with pytest.raises(ValueError, match="projection fields must be unique"):
        request(kind.SELECT, fields=("id", "id"))
