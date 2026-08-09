from __future__ import annotations

from scripts.collect_delivery_metrics import (
    classify_failure,
    collect_metrics,
    duration_seconds,
    jds_plan_metrics,
)


def _event(*, event: str = "pull_request", head_branch: str = "feature") -> dict:
    return {
        "repository": {"default_branch": "main"},
        "workflow_run": {
            "id": 123,
            "run_attempt": 1,
            "event": event,
            "head_branch": head_branch,
            "head_sha": "abc123",
            "conclusion": "success",
            "run_started_at": "2026-08-09T10:00:00Z",
            "updated_at": "2026-08-09T10:01:40Z",
            "pull_requests": [{"number": 77}] if event == "pull_request" else [],
        },
    }


def _jobs() -> list[dict]:
    return [
        {
            "name": "fast quality / compile / lint / type / contracts",
            "conclusion": "success",
            "started_at": "2026-08-09T10:00:00Z",
            "completed_at": "2026-08-09T10:00:30Z",
            "steps": [],
        },
        {
            "name": "tests / package / isolated acceptance",
            "conclusion": "success",
            "started_at": "2026-08-09T10:00:30Z",
            "completed_at": "2026-08-09T10:01:00Z",
            "steps": [],
        },
        {
            "name": "filesystem / dependency / secret scanning",
            "conclusion": "success",
            "started_at": "2026-08-09T10:00:30Z",
            "completed_at": "2026-08-09T10:00:50Z",
            "steps": [],
        },
        {
            "name": "build images / trivy / sbom",
            "conclusion": "success",
            "started_at": "2026-08-09T10:01:00Z",
            "completed_at": "2026-08-09T10:01:40Z",
            "steps": [
                {"name": "Build control plane image", "conclusion": "success"},
                {"name": "Build browser worker image", "conclusion": "success"},
                {"name": "Trivy image scan - control plane", "conclusion": "success"},
                {"name": "Trivy image scan - browser worker", "conclusion": "success"},
                {"name": "CycloneDX SBOM - control plane", "conclusion": "success"},
                {"name": "CycloneDX SBOM - browser worker", "conclusion": "success"},
            ],
        },
    ]


def _jds_plan() -> dict:
    return {
        "ambiguousImpact": False,
        "effectiveCapabilities": [f"cap-{index}" for index in range(10)],
        "selectedCapabilities": [f"cap-{index}" for index in range(6)],
        "skippedCapabilities": {
            "container.build": "change-impact-not-triggered",
            "security.container-scan": "change-impact-not-triggered",
            "security.sbom": "change-impact-not-triggered",
            "cap-9": "change-impact-not-triggered",
        },
    }


def test_duration_and_jds_avoidance_are_deterministic() -> None:
    assert duration_seconds("2026-08-09T10:00:00Z", "2026-08-09T10:01:40Z") == 100
    metrics = jds_plan_metrics(_jds_plan())
    assert metrics is not None
    assert metrics["avoided_capability_percent"] == 40.0
    assert metrics["heavy_capabilities_skipped"] == [
        "container.build",
        "security.container-scan",
        "security.sbom",
    ]


def test_failure_classification_is_bounded() -> None:
    lint_jobs = [
        {
            "name": "fast quality / compile / lint / type / contracts",
            "conclusion": "failure",
            "steps": [{"name": "Ruff", "conclusion": "failure"}],
        }
    ]
    contract_jobs = [
        {
            "name": "fast quality / compile / lint / type / contracts",
            "conclusion": "failure",
            "steps": [{"name": "Contract/schema validation gate", "conclusion": "failure"}],
        }
    ]
    infra_jobs = [
        {
            "name": "tests / package / isolated acceptance",
            "conclusion": "failure",
            "steps": [{"name": "Install", "conclusion": "failure"}],
        }
    ]
    code_jobs = [
        {
            "name": "tests / package / isolated acceptance",
            "conclusion": "failure",
            "steps": [{"name": "Pytest", "conclusion": "failure"}],
        }
    ]
    assert classify_failure(lint_jobs) == "DETERMINISTIC_LINT"
    assert classify_failure(contract_jobs) == "CONTRACT"
    assert classify_failure(infra_jobs) == "INFRA"
    assert classify_failure(code_jobs) == "CODE"


def test_collector_emits_low_cardinality_metrics_only() -> None:
    pr = {
        "created_at": "2026-08-09T09:55:00Z",
        "head": {"ref": "secret-feature-branch"},
        "base": {"ref": "integration/wave-private"},
        "user": {"login": "sensitive-user"},
        "title": "Sensitive tenant title",
    }
    metrics = collect_metrics(_event(), _jobs(), pr=pr, jds_plan=_jds_plan())
    assert metrics["run_kind"] == "FEATURE_PR"
    assert metrics["duration_seconds"] == 100
    assert metrics["pr_lead_time_seconds"] == 400
    assert metrics["heavy_work"] == {
        "image_builds": 2,
        "trivy_image_scans": 2,
        "sboms": 2,
    }
    serialized = str(metrics)
    assert "secret-feature-branch" not in serialized
    assert "wave-private" not in serialized
    assert "sensitive-user" not in serialized
    assert "Sensitive tenant title" not in serialized


def test_main_push_is_classified_without_branch_name_output() -> None:
    metrics = collect_metrics(
        _event(event="push", head_branch="main"),
        _jobs(),
        jds_plan=None,
    )
    assert metrics["run_kind"] == "MAIN_PUSH"
    assert "head_branch" not in metrics
