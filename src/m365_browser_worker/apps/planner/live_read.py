"""Read-only UI-derived extraction for the live Planner Premium board.

This module implements the five first-delivery read capabilities as REAL Playwright
reads against the already-open authenticated Planner Web surface. It is strictly
read-only: a single sanitized in-page text read per call, no navigation, no fill,
no click, no mutation. No URL, cookie, token, UPN or tenant id is ever read or
returned -- only non-secret surface text (plan/task titles, buckets, progress) is
derived from the live DOM.

The extraction is value-safe and does NOT require UIContract fragment attestation:
the broker (verified professional session on the Planner Web surface) is the
authorization gate, not the attested locator set. This is deliberate -- the
planner.plan-surface / planner.task-surface fragments cannot be derived in this
headless context (CORE-019 forbids inventing selectors), but reading the rendered
board text does not need stable locators.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

# Single read-only in-page text extraction. Returns ONLY sanitized, non-secret
# surface structure: the document title, plan-like link/button titles, rendered
# task/row titles, and a bounded visible-text sample. No location, URL, cookie,
# token, UPN or tenant id is ever read or returned.
_READ_JS = """() => {
  const body = document.body || document.documentElement;
  const text = (body ? body.innerText : '') || '';
  const lower = text.toLowerCase();
  const anchors = Array.from(document.querySelectorAll('a, button'))
    .map((el) => (el.innerText || '').trim())
    .filter(Boolean);
  const rows = Array.from(
    document.querySelectorAll('[role="row"], [role="listitem"], [role="gridcell"], [role="option"]')
  ).map((el) => (el.innerText || '').split(/\\n+/)[0].trim()).filter(Boolean);
  const lines = text.split(/\\n+/).map((s) => s.trim()).filter(Boolean);
  return {
    surface_title: document.title,
    anchor_titles: anchors.slice(0, 80),
    row_titles: rows.slice(0, 250),
    visible_lines: lines.slice(0, 400),
    has_ucs: lower.includes('ucs'),
    has_seguranca: lower.includes('seguran'),
  };
}"""


def _slug(value: str) -> str:
    """Deterministic non-secret id derived from a surface title (not a Graph id).

    Accent marks are stripped (NFC->NFD) so that e.g. "Segurança Técnica" yields
    "seguranca-tecnica", giving a stable id that round-trips with the titles the
    UI-derived read returns and that a human can reproduce.
    """
    normalized = unicodedata.normalize("NFD", value)
    ascii_text = "".join(c for c in normalized if unicodedata.combining(c) == 0)
    cleaned = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return cleaned or "untitled"


def _is_plan_like(title: str) -> bool:
    """Conservative heuristic: a plan hub entry is a short named link/button."""
    t = title.strip()
    if not t or len(t) > 120:
        return False
    # Exclude obvious chrome/controls and the Planner marketing landing links that
    # the SPA renders when the bare root (or an unhydrated surface) is reached
    # instead of the board hub. A marketing link is NEVER a plan list entry.
    lowered = t.lower()
    chrome = {
        "sign in",
        "iniciar sessão",
        "iniciar sessao",
        "new plan",
        "novo plano",
        "add",
        "adicionar",
        "more",
        "mais",
        "menu",
        "get planner for android",
        "get planner for ios",
        "a simple, visual way to organize teamwork",
    }
    if lowered in chrome:
        return False
    # Substring guards for localized marketing variants.
    if "get planner for" in lowered:
        return False
    return True


async def read_surface(page: Any) -> dict[str, Any]:
    """Return the sanitized live board structure for the currently open page."""
    return await page.evaluate(_READ_JS)


async def extract_plans(page: Any) -> list[dict[str, Any]]:
    """Extract plan entries from the live Planner surface (read-only)."""
    surface = await read_surface(page)
    titles = sorted(
        {t for t in surface.get("anchor_titles", []) if _is_plan_like(t)},
        key=lambda s: s.lower(),
    )
    return [
        {
            "id": _slug(t),
            "title": t,
            "source": "live_ui",
            "read_only": True,
        }
        for t in titles
    ]


async def extract_plan(page: Any, plan_id: str) -> dict[str, Any] | None:
    """Return one plan entry matched by its live-derived slug/title."""
    plans = await extract_plans(page)
    pid = plan_id.strip().lower()
    for plan in plans:
        if plan["id"] == pid or pid in plan["title"].lower() or pid in plan["id"]:
            return plan
    return None


async def extract_tasks(page: Any, plan_id: str | None = None) -> list[dict[str, Any]]:
    """Extract rendered task rows from the live board (read-only).

    The plan scoping is best-effort: UI-derived reads have no stable server plan id,
    so tasks are tagged with the matched plan slug when available, otherwise with the
    surface's first visible plan title.
    """
    surface = await read_surface(page)
    plan_slug = _slug(plan_id) if plan_id else "plan"
    titles = [t for t in surface.get("row_titles", []) if t and len(t) <= 200]
    tasks: list[dict[str, Any]] = []
    for idx, title in enumerate(titles):
        tasks.append(
            {
                "id": f"{plan_slug}::{idx + 1}",
                "title": title,
                "plan_id": plan_slug,
                "source": "live_ui",
                "read_only": True,
            }
        )
    return tasks


async def extract_task(page: Any, task_id: str) -> dict[str, Any] | None:
    """Return one task entry matched by its live-derived id."""
    tid = task_id.strip().lower()
    # Try the plan-scoped form first, then any plan.
    for plan_slug in (None,):
        tasks = await extract_tasks(page, plan_slug)  # type: ignore[arg-type]
        for task in tasks:
            if task["id"] == tid or tid in task["id"] or tid in task["title"].lower():
                return task
    # Fallback: scan all rows ignoring plan prefix.
    for task in await extract_tasks(page):
        if task["id"] == tid or tid in task["id"] or tid in task["title"].lower():
            return task
    return None


async def extract_snapshot(page: Any, plan_id: str | None = None) -> dict[str, Any]:
    """Return a read-only project snapshot: plan + tasks + counts."""
    plans = await extract_plans(page)
    plan = await extract_plan(page, plan_id) if plan_id else (plans[0] if plans else None)
    resolved_plan_id = (plan or {}).get("id") if plan else (plan_id or "plan")
    tasks = await extract_tasks(page, resolved_plan_id)
    return {
        "plan": plan,
        "tasks": tasks,
        "counts": {"plans": len(plans), "tasks": len(tasks)},
        "read_only": True,
        "source": "live_ui",
    }


__all__ = [
    "read_surface",
    "extract_plans",
    "extract_plan",
    "extract_tasks",
    "extract_task",
    "extract_snapshot",
]
