"""TDD for extract_plans() union-of-anchor-and-row fix (PLN-MIG-005 bug).

extract_plans() must consider the UNION of anchor_titles and row_titles, apply
_is_plan_like, deduplicate (case-insensitive) and sort case-insensitive. It must
NOT rely on visible_lines / surface_title / flags.

RED evidence the test is designed to produce before the fix:
- A plan present ONLY in row_titles is currently dropped (extract_plans reads
  anchor_titles alone), so "Plano Row Only" is missing.
- A title appearing in BOTH anchor (Title Case) and row (lowercase) currently
  yields only the anchor occurrence (no union, no cross-case dedupe).
"""

from __future__ import annotations


class _FakePage:
    """Minimal read-only page double: only page.evaluate is exercised."""

    def __init__(self, surface: dict[str, object]) -> None:
        self._surface = surface

    async def evaluate(self, _js: str) -> dict[str, object]:
        return self._surface


UNION_SURFACE = {
    "surface_title": "Planner",
    # One real plan + chrome that must be excluded.
    "anchor_titles": ["Sign in", "UCS – Segurança Técnica", "Outro Plano"],
    # Same UCS title in lowercase (must dedupe with the anchor occurrence) plus a
    # plan that exists ONLY here and must still be surfaced.
    "row_titles": ["ucs – segurança técnica", "Plano Row Only"],
    # These must NOT be consulted by extract_plans.
    "visible_lines": ["Sign in", "UCS – Segurança Técnica", "Plano Row Only", "Outro Plano"],
    "has_ucs": True,
    "has_seguranca": True,
}


async def test_extract_plans_surfaces_plan_present_only_in_rows() -> None:
    from m365_browser_worker.apps.planner.live_read import extract_plans

    plans = await extract_plans(_FakePage(UNION_SURFACE))
    titles = {p["title"] for p in plans}
    # The plan that exists only in row_titles must be surfaced (the bug).
    assert "Plano Row Only" in titles
    assert "Plano Row Only" not in UNION_SURFACE["anchor_titles"]


async def test_extract_plans_dedupes_anchor_and_row_same_title() -> None:
    from m365_browser_worker.apps.planner.live_read import extract_plans

    plans = await extract_plans(_FakePage(UNION_SURFACE))
    titles = [p["title"] for p in plans]
    # UCS appears once in anchor (Title Case) and once in row (lowercase):
    # the union must dedupe to a single plan entry, not two.
    assert titles.count("UCS – Segurança Técnica") == 1
    # chrome excluded
    assert "Sign in" not in titles
    # Unique plans: UCS, Outro Plano, Plano Row Only.
    assert len(plans) == 3


async def test_extract_plans_sorted_case_insensitive() -> None:
    from m365_browser_worker.apps.planner.live_read import extract_plans

    surface = {
        "surface_title": "Planner",
        "anchor_titles": ["Zebra Plan", "alpha plan"],
        "row_titles": ["Bravo Plan"],
        "visible_lines": [],
        "has_ucs": False,
        "has_seguranca": False,
    }
    plans = await extract_plans(_FakePage(surface))
    ordered = [p["title"] for p in plans]
    assert ordered == sorted(ordered, key=lambda s: s.lower())
    assert ordered == ["alpha plan", "Bravo Plan", "Zebra Plan"]
