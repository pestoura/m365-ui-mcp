"""First-delivery tests for the five Planner read capabilities.

Covers:
- The capability projection grants READ_SUPPORTED to the three read-only delivery
  capabilities only when the verified professional read path is available, and
  keeps every other capability fail-closed (UNVERIFIED_LIVE) without UI attestation.
- The worker adapter performs REAL Playwright reads on the live page (no fixture),
  failing closed when no live Planner page is available.
"""

from __future__ import annotations

import pytest

from m365_mcp.apps.planner.capability_registry import planner_capability_definitions
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.effective_capabilities import (
    EffectiveCapabilityEvidence,
    project_effective_capabilities_by_capability,
)

READ_ONLY_DELIVERY = {"plans.read", "tasks.read", "project_snapshot.read"}


def _evidence(
    *,
    live_read_path: bool,
    authenticated: bool = True,
    account_valid: bool = True,
    live_evidence: bool = True,
) -> dict[str, EffectiveCapabilityEvidence]:
    registry = default_capability_registry()
    return {
        name: EffectiveCapabilityEvidence(
            authenticated=authenticated,
            account_context_valid=account_valid,
            ui_attested=False,
            runtime_healthy=True,
            policy_allowed=True,
            license_available=False,
            live_evidence=live_evidence,
            live_read_path=live_read_path,
        )
        for name in registry.capability_names("planner")
    }


def test_read_only_delivery_supported_when_live_read_path_verified() -> None:
    evidence = _evidence(live_read_path=True)
    projected = project_effective_capabilities_by_capability(
        default_capability_registry(), application="planner", evidence_by_capability=evidence
    )
    by_cap = {c.definition.capability: c for c in projected}
    for name, cap in by_cap.items():
        if name in READ_ONLY_DELIVERY:
            assert cap.state.value == "READ_SUPPORTED", name
            assert cap.supported is True
        else:
            # No UI attestation -> everything else stays fail-closed.
            assert cap.state.value == "UNVERIFIED_LIVE", name
            assert cap.supported is False


def test_read_only_delivery_unverified_without_live_read_path() -> None:
    evidence = _evidence(live_read_path=False)
    projected = project_effective_capabilities_by_capability(
        default_capability_registry(), application="planner", evidence_by_capability=evidence
    )
    by_cap = {c.definition.capability: c for c in projected}
    for name, cap in by_cap.items():
        assert cap.state.value == "UNVERIFIED_LIVE", (name, cap.reasons)
        assert cap.supported is False


def test_read_only_delivery_blocked_when_account_unverified() -> None:
    evidence = _evidence(live_read_path=True, account_valid=False)
    projected = project_effective_capabilities_by_capability(
        default_capability_registry(), application="planner", evidence_by_capability=evidence
    )
    by_cap = {c.definition.capability: c for c in projected}
    for name in READ_ONLY_DELIVERY:
        assert by_cap[name].state.value == "UNVERIFIED_LIVE", (name, by_cap[name].reasons)
        assert "ACCOUNT_CONTEXT_UNVERIFIED" in by_cap[name].reasons


def test_registry_defines_three_delivery_caps() -> None:
    names = {d.capability for d in planner_capability_definitions()}
    assert READ_ONLY_DELIVERY.issubset(names)


class _FakePage:
    """Minimal read-only page double: only page.evaluate is exercised."""

    def __init__(self, surface: dict[str, object]) -> None:
        self._surface = surface
        self.closed = False

    async def evaluate(self, _js: str) -> dict[str, object]:
        return self._surface


class _FakeReader:
    def __init__(self, page: _FakePage | None) -> None:
        self._page = page

    def __call__(self) -> _FakePage | None:
        return self._page


async def _make_adapter(reader_page: _FakePage | None):
    from m365_browser_worker.apps.planner.adapter import PlannerWorkerAdapter

    class _NoopProvider:
        PLANS: list[dict[str, object]] = []

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
        live_reader=_FakeReader(reader_page),
    )


UCS_SURFACE = {
    "surface_title": "Planner",
    "anchor_titles": ["UCS – Segurança Técnica", "Outro Plano", "Sign in"],
    "row_titles": ["Definir política", "Rever relatório", "Fechar ticket"],
    "visible_lines": ["UCS – Segurança Técnica", "Definir política", "Rever relatório"],
    "has_ucs": True,
    "has_seguranca": True,
}


async def test_live_plan_list_extracts_real_surface() -> None:
    adapter = await _make_adapter(_FakePage(UCS_SURFACE))
    result = await adapter.plan_list()
    titles = {p["title"] for p in result["plans"]}
    assert "UCS – Segurança Técnica" in titles
    assert "Sign in" not in titles  # chrome excluded
    assert result["read_only"] is True
    assert result["source"] == "live_ui"


async def test_live_plan_get_finds_ucs() -> None:
    adapter = await _make_adapter(_FakePage(UCS_SURFACE))
    plan = await adapter.plan_get("ucs-seguranca-tecnica")
    assert plan["plan"]["title"] == "UCS – Segurança Técnica"


async def test_live_task_list_extracts_rows() -> None:
    adapter = await _make_adapter(_FakePage(UCS_SURFACE))
    tasks = (await adapter.task_list("ucs-seguranca-tecnica"))["tasks"]
    assert len(tasks) == 3
    assert tasks[0]["title"] == "Definir política"


async def test_live_project_snapshot() -> None:
    adapter = await _make_adapter(_FakePage(UCS_SURFACE))
    snap = await adapter.project_snapshot("ucs-seguranca-tecnica")
    assert snap["plan"]["title"] == "UCS – Segurança Técnica"
    assert snap["counts"]["tasks"] == 3
    assert snap["read_only"] is True


async def test_live_reads_fail_closed_without_page() -> None:
    from fastapi import HTTPException

    adapter = await _make_adapter(None)
    with pytest.raises(HTTPException):
        await adapter.plan_list()
    with pytest.raises(HTTPException):
        await adapter.task_list("x")
    with pytest.raises(HTTPException):
        await adapter.project_snapshot("x")


def test_build_capabilities_reflects_read_path() -> None:
    """build_capabilities projects READ_SUPPORTED for the three delivery caps when
    the verified read path evidence is present, and keeps all others UNVERIFIED_LIVE."""
    from planner_mcp.capabilities import build_capabilities

    out = build_capabilities(
        auth_evidence={"state": "AUTHENTICATED", "evidence_source": "live_ui"},
        account_context={
            "account_kind": "work_or_school",
            "profile": "professional-isolated",
            "valid": True,
            "evidence_source": "live_ui",
        },
        license_evidence={"premium_detected": False, "evidence_source": "live_ui"},
        runtime_ok=True,
        policy_allowed=True,
        live_evidence=True,
        live_read_path=True,
    )
    by_cap = {row["capability"]: row for row in out["capabilities"]}
    delivery = {"plans.read", "tasks.read", "project_snapshot.read"}
    for name, row in by_cap.items():
        if name in delivery:
            assert row["support_level"] == "READ_SUPPORTED", (name, row)
            assert row["read_attestation"] == "YES", name
        else:
            assert row["support_level"] == "UNVERIFIED_LIVE", (name, row)
            assert row["read_attestation"] == "NO", name
    # Projection carries the evidence dimension.
    proj = {p["capability"]: p for p in out["effective_projection"]}
    assert proj["plans.read"]["state"] == "READ_SUPPORTED"
    assert proj["plans.read"]["evidence"]["live_read_path"] is True
    assert proj["plans.read"]["evidence"]["license_available"] is False


def test_build_capabilities_fail_closed_without_read_path() -> None:
    from planner_mcp.capabilities import build_capabilities

    out = build_capabilities(
        auth_evidence={"state": "AUTHENTICATED", "evidence_source": "live_ui"},
        account_context={
            "account_kind": "work_or_school",
            "profile": "professional-isolated",
            "valid": True,
            "evidence_source": "live_ui",
        },
        license_evidence={"premium_detected": False},
        runtime_ok=True,
        policy_allowed=True,
        live_evidence=True,
        live_read_path=False,
    )
    by_cap = {row["capability"]: row for row in out["capabilities"]}
    assert by_cap["plans.read"]["support_level"] == "UNVERIFIED_LIVE"
    proj = {p["capability"]: p for p in out["effective_projection"]}
    assert "LIVE_READ_PATH_UNAVAILABLE" in proj["plans.read"]["reasons"]
