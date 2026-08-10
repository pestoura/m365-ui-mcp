#!/usr/bin/env python3
"""Repository-side REL-005 browser-worker egress acceptance."""

from __future__ import annotations

from pathlib import Path

_REQUIRED_POLICY_MARKERS = (
    'if scheme != "https":',
    'return EgressDecision(False, "NON_HTTPS_BLOCKED")',
    'return EgressDecision(False, "HOST_NOT_ALLOWLISTED")',
    'await route.abort("blockedbyclient")',
)


def _worker_block(compose: str) -> str:
    marker = "  m365-browser-worker:\n"
    start = compose.find(marker)
    if start < 0:
        return ""
    end = compose.find("\nnetworks:\n", start)
    if end < 0:
        end = len(compose)
    return compose[start:end]


def check_egress_acceptance(root: Path) -> tuple[str, ...]:
    """Return deterministic findings; empty means REL-005 repository acceptance passes."""
    compose_path = root / "docker-compose.yml"
    egress_path = root / "src/m365_browser_worker/egress.py"
    findings: list[str] = []

    for path in (compose_path, egress_path):
        if not path.is_file():
            findings.append(f"missing required file: {path.relative_to(root)}")
    if findings:
        return tuple(findings)

    compose = compose_path.read_text(encoding="utf-8")
    worker = _worker_block(compose)
    policy = egress_path.read_text(encoding="utf-8")

    if not worker:
        findings.append("browser-worker compose service is missing")
    else:
        if "- m365-internal" not in worker or "- m365-egress" not in worker:
            findings.append("browser-worker must attach to internal and egress networks")
        if "ports:" in worker:
            findings.append("browser-worker must not publish inbound ports")

    if "m365-internal:\n    internal: true" not in compose:
        findings.append("m365-internal network must be internal:true")
    if "m365-egress:" not in compose:
        findings.append("m365-egress network is required")

    for marker in _REQUIRED_POLICY_MARKERS:
        if marker not in policy:
            findings.append(f"egress policy missing fail-closed marker: {marker}")

    if "_ALLOWED_HOST_SUFFIXES = (" not in policy:
        findings.append("egress policy requires a closed in-code host allowlist")
    if "generic\nnavigation primitive" not in policy:
        findings.append("egress policy must explicitly deny a generic navigation surface")

    return tuple(findings)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings = check_egress_acceptance(root)
    if findings:
        for finding in findings:
            print(f"REL-005 FAIL: {finding}")
        return 1
    print("REL-005 PASS: browser-worker egress acceptance verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
