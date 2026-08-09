#!/usr/bin/env python3
"""Collect low-cardinality JDS/M365 delivery-economics evidence.

This collector is designed for a trusted default-branch ``workflow_run`` job. It
reads GitHub Actions metadata through the read-only API and never checks out or
executes code from the triggering PR/head SHA.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

JOB_BUCKETS = {
    "fast quality / compile / lint / type / contracts": "FAST_QUALITY",
    "tests / package / isolated acceptance": "TESTS_ACCEPTANCE",
    "filesystem / dependency / secret scanning": "REPO_SECURITY",
    "build images / trivy / sbom": "HEAVY_IMAGES",
}
FAILURE_CLASSES = {
    "CODE",
    "CONTRACT",
    "INFRA",
    "STALE_BASE",
    "DETERMINISTIC_LINT",
}


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def duration_seconds(started_at: str | None, completed_at: str | None) -> int | None:
    start = _parse_time(started_at)
    end = _parse_time(completed_at)
    if start is None or end is None:
        return None
    return max(0, round((end - start).total_seconds()))


def classify_failure(jobs: list[dict[str, Any]]) -> str | None:
    """Classify only observed failed steps; do not infer stale-base failures."""
    failed_steps: list[str] = []
    failed_jobs: list[str] = []
    for job in jobs:
        if job.get("conclusion") != "failure":
            continue
        failed_jobs.append(str(job.get("name", "")).lower())
        for step in job.get("steps") or []:
            if step.get("conclusion") == "failure":
                failed_steps.append(str(step.get("name", "")).lower())

    if not failed_jobs:
        return None
    text = " ".join(failed_steps + failed_jobs)
    if any(token in text for token in ("ruff", "mypy", "compile", "shellcheck", "shell syntax")):
        return "DETERMINISTIC_LINT"
    if any(
        token in text
        for token in (
            "contract",
            "schema",
            "policy metadata",
            "canonical documentation",
            "documentation gate",
        )
    ):
        return "CONTRACT"
    if any(
        token in text
        for token in (
            "set up job",
            "actions/checkout",
            "actions/setup-python",
            "install",
            "upload-artifact",
            "setup-buildx",
        )
    ):
        return "INFRA"
    return "CODE"


def _job_metrics(jobs: list[dict[str, Any]]) -> dict[str, dict[str, object]]:
    metrics: dict[str, dict[str, object]] = {}
    for job in jobs:
        bucket = JOB_BUCKETS.get(str(job.get("name", "")))
        if bucket is None:
            continue
        metrics[bucket] = {
            "conclusion": job.get("conclusion"),
            "duration_seconds": duration_seconds(
                job.get("started_at"), job.get("completed_at")
            ),
        }
    return metrics


def _heavy_counts(jobs: list[dict[str, Any]]) -> dict[str, int]:
    result = {"image_builds": 0, "trivy_image_scans": 0, "sboms": 0}
    for job in jobs:
        if JOB_BUCKETS.get(str(job.get("name", ""))) != "HEAVY_IMAGES":
            continue
        for step in job.get("steps") or []:
            if step.get("conclusion") != "success":
                continue
            name = str(step.get("name", ""))
            if name.startswith("Build ") and name.endswith(" image"):
                result["image_builds"] += 1
            elif name.startswith("Trivy image scan - "):
                result["trivy_image_scans"] += 1
            elif name.startswith("CycloneDX SBOM - "):
                result["sboms"] += 1
    return result


def classify_run_kind(
    workflow_run: dict[str, Any],
    *,
    pr: dict[str, Any] | None = None,
    default_branch: str = "main",
) -> str:
    event = workflow_run.get("event")
    if event == "push":
        return "MAIN_PUSH" if workflow_run.get("head_branch") == default_branch else "PUSH"
    if event != "pull_request" or pr is None:
        return "OTHER"
    head_ref = str((pr.get("head") or {}).get("ref", ""))
    base_ref = str((pr.get("base") or {}).get("ref", ""))
    if head_ref.startswith("integration/") and base_ref == default_branch:
        return "INTEGRATION_PR"
    if base_ref.startswith("integration/"):
        return "FEATURE_PR"
    return "PR_TO_MAIN"


def jds_plan_metrics(plan: dict[str, Any] | None) -> dict[str, object] | None:
    if plan is None:
        return None
    effective = plan.get("effectiveCapabilities") or []
    selected = plan.get("selectedCapabilities") or []
    skipped = plan.get("skippedCapabilities") or {}
    effective_count = len(effective)
    selected_count = len(selected)
    skipped_count = len(skipped)
    avoided = (
        round((skipped_count / effective_count) * 100, 1) if effective_count else 0.0
    )
    heavy_names = {
        "container.build",
        "security.container-scan",
        "security.sbom",
    }
    heavy_skipped = sorted(name for name in skipped if name in heavy_names)
    return {
        "ambiguous_impact": bool(plan.get("ambiguousImpact", False)),
        "effective_capability_count": effective_count,
        "selected_capability_count": selected_count,
        "skipped_capability_count": skipped_count,
        "avoided_capability_percent": avoided,
        "heavy_capabilities_skipped": heavy_skipped,
    }


def collect_metrics(
    event: dict[str, Any],
    jobs: list[dict[str, Any]],
    *,
    pr: dict[str, Any] | None = None,
    jds_plan: dict[str, Any] | None = None,
) -> dict[str, object]:
    workflow_run = event["workflow_run"]
    repository = event.get("repository") or {}
    default_branch = str(repository.get("default_branch") or "main")
    completed_at = workflow_run.get("updated_at") or workflow_run.get("run_started_at")
    pr_lead_time: int | None = None
    if pr is not None:
        pr_lead_time = duration_seconds(pr.get("created_at"), completed_at)

    failure_class = classify_failure(jobs)
    if failure_class is not None and failure_class not in FAILURE_CLASSES:
        raise ValueError("unexpected failure class")

    return {
        "schema": "m365.delivery-economics/v1",
        "run_id": workflow_run.get("id"),
        "run_attempt": workflow_run.get("run_attempt", 1),
        "run_kind": classify_run_kind(
            workflow_run, pr=pr, default_branch=default_branch
        ),
        "conclusion": workflow_run.get("conclusion"),
        "duration_seconds": duration_seconds(
            workflow_run.get("run_started_at"), completed_at
        ),
        "pr_lead_time_seconds": pr_lead_time,
        "failure_class": failure_class,
        "jobs": _job_metrics(jobs),
        "heavy_work": _heavy_counts(jobs),
        "jds": jds_plan_metrics(jds_plan),
    }


def _api_json(url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "m365-delivery-economics",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub API request failed with HTTP {exc.code}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub API response must be an object")
    return payload


def _load_event(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("workflow_run"), dict):
        raise ValueError("event must contain workflow_run")
    return payload


def _matching_pr(
    event: dict[str, Any], token: str, repository: str
) -> dict[str, Any] | None:
    pull_requests = event["workflow_run"].get("pull_requests") or []
    if not pull_requests:
        return None
    number = pull_requests[0].get("number")
    if not isinstance(number, int):
        return None
    return _api_json(f"https://api.github.com/repos/{repository}/pulls/{number}", token)


def resolve_jds_run(event: dict[str, Any], token: str, repository: str) -> int:
    head_sha = event["workflow_run"].get("head_sha")
    if not isinstance(head_sha, str) or not head_sha:
        return 0
    payload = _api_json(
        f"https://api.github.com/repos/{repository}/actions/runs?head_sha={head_sha}&per_page=20",
        token,
    )
    candidates = [
        item
        for item in payload.get("workflow_runs", [])
        if item.get("name") == "JDS Audit" and item.get("conclusion") == "success"
    ]
    if not candidates:
        return 0
    return int(max(candidates, key=lambda item: int(item.get("id", 0)))["id"])


def _write_summary(path: Path, metrics: dict[str, object]) -> None:
    jobs = metrics["jobs"]
    assert isinstance(jobs, dict)
    heavy = metrics["heavy_work"]
    assert isinstance(heavy, dict)
    lines = [
        "## M365 delivery economics",
        "",
        f"- run kind: `{metrics['run_kind']}`",
        f"- conclusion: `{metrics['conclusion']}`",
        f"- CI duration: `{metrics['duration_seconds']}` seconds",
        f"- failure class: `{metrics['failure_class'] or 'NONE'}`",
        f"- heavy image builds: `{heavy['image_builds']}`",
        f"- heavy Trivy image scans: `{heavy['trivy_image_scans']}`",
        f"- heavy SBOM steps: `{heavy['sboms']}`",
    ]
    jds = metrics.get("jds")
    if isinstance(jds, dict):
        lines.extend(
            [
                f"- JDS avoided-capability percentage: `{jds['avoided_capability_percent']}%`",
                f"- JDS heavy capabilities skipped: `{len(jds['heavy_capabilities_skipped'])}`",
            ]
        )
    lines.extend(["", "No branch names, user identities, emails or tenant content are emitted."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--jds-plan", type=Path)
    parser.add_argument("--resolve-jds-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    event = _load_event(args.event)
    token = os.environ.get("GITHUB_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repository:
        raise SystemExit("GITHUB_TOKEN and GITHUB_REPOSITORY are required")

    if args.resolve_jds_run:
        print(resolve_jds_run(event, token, repository))
        return 0

    if args.output is None or args.summary is None:
        raise SystemExit("--output and --summary are required for collection")

    jobs_url = event["workflow_run"].get("jobs_url")
    if not isinstance(jobs_url, str):
        raise SystemExit("workflow_run.jobs_url is required")
    jobs_payload = _api_json(f"{jobs_url}?per_page=100", token)
    jobs = jobs_payload.get("jobs") or []
    if not isinstance(jobs, list):
        raise SystemExit("jobs response is invalid")

    pr = _matching_pr(event, token, repository)
    jds_plan = None
    if args.jds_plan is not None and args.jds_plan.is_file():
        candidate = json.loads(args.jds_plan.read_text(encoding="utf-8"))
        if isinstance(candidate, dict):
            jds_plan = candidate

    metrics = collect_metrics(event, jobs, pr=pr, jds_plan=jds_plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_summary(args.summary, metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
