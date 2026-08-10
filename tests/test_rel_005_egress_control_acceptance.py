from pathlib import Path
import subprocess
import sys

from m365_browser_worker.egress import evaluate_browser_egress

ROOT = Path(__file__).resolve().parents[1]


def test_rel_005_repository_egress_acceptance_checker_passes() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_egress_acceptance.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "REL-005 PASS" in completed.stdout


def test_rel_005_allows_only_local_resources_or_https_m365_hosts() -> None:
    assert evaluate_browser_egress("https://outlook.office.com/mail").allowed is True
    assert evaluate_browser_egress("https://login.microsoftonline.com/common").allowed is True
    assert evaluate_browser_egress("data:text/plain,synthetic").allowed is True

    non_https = evaluate_browser_egress("http://outlook.office.com/mail")
    unknown = evaluate_browser_egress("https://evil.example/path")
    userinfo_spoof = evaluate_browser_egress("https://office.com@evil.example/path")

    assert non_https.allowed is False
    assert non_https.reason == "NON_HTTPS_BLOCKED"
    assert unknown.allowed is False
    assert unknown.reason == "HOST_NOT_ALLOWLISTED"
    assert userinfo_spoof.allowed is False
    assert userinfo_spoof.reason == "HOST_NOT_ALLOWLISTED"


def test_rel_005_worker_has_no_public_inbound_port() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    start = compose.index("  m365-browser-worker:\n")
    end = compose.index("\nnetworks:\n", start)
    worker = compose[start:end]

    assert "ports:" not in worker
    assert "- m365-internal" in worker
    assert "- m365-egress" in worker
    assert "m365-internal:\n    internal: true" in compose
