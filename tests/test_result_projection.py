from __future__ import annotations

import pytest

from m365_mcp.result_projection import project_rows, ProjectionKind, ProjectionRequest


ROWS = [
    {"id": "a", "title": "Alpha", "updated": "2026-08-01T10:00:00Z"},
    {"id": "b", "title": "Beta", "updated": "2026-08-03T10:00:00Z"},
    {"id": "c", "title": "Gamma", "updated": "2026-08-02T10:00:00Z"},
]


def test_select_reduces_fields_without_mutating_input() -> None:
    result = project_rows(
        ROWS,
        ProjectionRequest(ProjectionKind.SELECT, fields=("id", "title")),
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
    assert project_rows(ROWS, ProjectionRequest(ProjectionKind.COUNT)).data == 3
    assert project_rows(ROWS, ProjectionRequest(ProjectionKind.EXISTS)).data is True
    assert project_rows([], ProjectionRequest(ProjectionKind.EXISTS)).data is False
    assert project_rows(ROWS, ProjectionRequest(ProjectionKind.FIRST)).data == ROWS[0]
    assert project_rows([], ProjectionRequest(ProjectionKind.FIRST)).data is None
    assert project_rows(ROWS, ProjectionRequest(ProjectionKind.METADATA_ONLY)).data == {
        "count": 3
    }


def test_latest_uses_explicit_sort_field() -> None:
    result = project_rows(
        ROWS,
        ProjectionRequest(ProjectionKind.LATEST, sort_field="updated"),
    )
    assert result.data == ROWS[1]


def test_top_n_and_pagination_are_bounded() -> None:
    top = project_rows(ROWS, ProjectionRequest(ProjectionKind.TOP_N, top_n=2))
    page = project_rows(
        ROWS,
        ProjectionRequest(ProjectionKind.PAGINATION, offset=1, limit=1),
    )

    assert top.data == ROWS[:2]
    assert top.output_count == 2
    assert page.data == [ROWS[1]]
    assert page.output_count == 1


def test_projection_request_rejects_unbounded_or_ambiguous_shapes() -> None:
    with pytest.raises(ValueError, match="select projection requires fields"):
        ProjectionRequest(ProjectionKind.SELECT)
    with pytest.raises(ValueError, match="latest projection requires sort_field"):
        ProjectionRequest(ProjectionKind.LATEST)
    with pytest.raises(ValueError, match="top_n must be between"):
        ProjectionRequest(ProjectionKind.TOP_N, top_n=101)
    with pytest.raises(ValueError, match="limit must be between"):
        ProjectionRequest(ProjectionKind.PAGINATION, limit=101)
    with pytest.raises(ValueError, match="projection fields must be unique"):
        ProjectionRequest(ProjectionKind.SELECT, fields=("id", "id"))
