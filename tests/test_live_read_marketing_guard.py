"""Live read must not confuse the Planner marketing landing with a plan list.

The SPA may render the marketing landing (Get Planner For Android/iOS, Sign in)
instead of the board when the bootstrap target is not the board hub. The read
layer must never present that landing as a plan list.
"""

from __future__ import annotations


class _FakePage:
    def __init__(self, surface: dict[str, object]) -> None:
        self._surface = surface

    async def evaluate(self, _js: str) -> dict[str, object]:
        return self._surface


def _reader(page):
    return lambda: page


MARKETING_SURFACE = {
    "surface_title": "Microsoft Planner",
    "anchor_titles": [
        "Sign in",
        "Get Planner For Android",
        "Get Planner For iOS",
        "A simple, visual way to organize teamwork",
    ],
    "row_titles": [],
    "visible_lines": [
        "Microsoft Planner",
        "A simple, visual way to organize teamwork",
        "Get Planner For Android",
        "Get Planner For iOS",
    ],
    "has_ucs": False,
    "has_seguranca": False,
}


async def test_marketing_landing_yields_no_plans() -> None:
    adapter = await _make_adapter(_FakePage(MARKETING_SURFACE))
    result = await adapter.plan_list()
    titles = {p["title"] for p in result["plans"]}
    assert "Get Planner For Android" not in titles
    assert "Get Planner For iOS" not in titles
    assert "Sign in" not in titles
    assert result["plans"] == []


async def test_real_board_plan_is_surfaced() -> None:
    ucs = {
        "surface_title": "Planner",
        "anchor_titles": ["UCS – Segurança Técnica", "Outro Plano", "Sign in"],
        "row_titles": ["Definir política"],
        "visible_lines": ["UCS – Segurança Técnica"],
        "has_ucs": True,
        "has_seguranca": True,
    }
    adapter = await _make_adapter(_FakePage(ucs))
    result = await adapter.plan_list()
    titles = {p["title"] for p in result["plans"]}
    assert "UCS – Segurança Técnica" in titles
    assert "Sign in" not in titles


async def _make_adapter(reader_page):
    from m365_browser_worker.apps.planner.adapter import PlannerWorkerAdapter

    class _NoopProvider:
        def plan(self, plan_id: str):
            return None

        def tasks_for(self, plan_id: str):
            return []

        def task(self, task_id: str):
            return None

    return PlannerWorkerAdapter(
        is_mock=lambda: False,
        capability_guard=lambda capability: None,
        data_provider=_NoopProvider(),
        live_reader=_reader(reader_page),
    )
