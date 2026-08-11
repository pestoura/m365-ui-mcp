from __future__ import annotations

import json
from pathlib import Path

EVIDENCE = Path("docs/m365-transition/evidence/rel-026-before-after.json")


def _load() -> dict[str, object]:
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def test_rel_026_acceptance_evidence_is_complete() -> None:
    data = _load()
    assert data["schema"] == "m365.delivery-economics-comparison/v1"
    assert data["status"] == "ACCEPTANCE_EVIDENCE"
    acceptance = data["acceptance"]
    assert acceptance == {
        "completed_integration_wave_reconstructable": True,
        "expensive_work_count_measurable": True,
        "infra_failures_not_counted_as_code_regressions": True,
        "content_or_identity_leakage_detected": False,
        "before_after_comparison_present": True,
        "controller_tuning_evidence_available": True,
        "mandatory_gate_removed_or_weakened": False,
    }


def test_rel_026_jds_selectivity_improves_without_removing_heavy_gate() -> None:
    data = _load()
    baseline = data["baseline"]["phase_9_wave_f_integration"]
    integration = data["post_jds"]["hardening_b_integration"]
    post_merge = data["post_jds"]["hardening_b_post_merge"]

    assert (
        integration["jds_avoided_capability_percent"]
        > baseline["jds_avoided_capability_percent"]
    )
    assert (
        post_merge["jds_avoided_capability_percent"]
        > integration["jds_avoided_capability_percent"]
    )

    for sample in (baseline, integration, post_merge):
        assert sample["image_builds"] == 2
        assert sample["trivy_image_scans"] == 2
        assert sample["sboms"] == 2


def test_rel_026_result_is_not_misrepresented_as_uniform_speedup() -> None:
    comparison = _load()["comparison"]
    assert comparison["integration_vs_phase_9_wave_f"]["ci_total_seconds_delta"] < 0
    assert comparison["integration_vs_phase_10_wave_g"]["ci_total_seconds_delta"] > 0
    assert "mixed" in comparison["interpretation"].lower()
    assert "does not justify removing or weakening any gate" in comparison["interpretation"]


def test_rel_026_evidence_contains_no_identity_or_tenant_fields() -> None:
    text = EVIDENCE.read_text(encoding="utf-8").lower()
    forbidden = (
        '"branch"',
        '"user"',
        '"email"',
        '"tenant"',
        '"mailbox"',
        '"message_content"',
    )
    for token in forbidden:
        assert token not in text
