#!/usr/bin/env python3
"""Repository-side REL-004 container-hardening parity acceptance."""

from __future__ import annotations

from pathlib import Path


REQUIRED_TMPFS_FLAGS = ("rw", "noexec", "nosuid", "nodev")


def _service_block(compose: str, service: str, next_service: str | None) -> str:
    start_marker = f"  {service}:\n"
    start = compose.find(start_marker)
    if start < 0:
        return ""
    if next_service is None:
        end = compose.find("\nnetworks:\n", start)
    else:
        end = compose.find(f"  {next_service}:\n", start + len(start_marker))
    if end < 0:
        end = len(compose)
    return compose[start:end]


def check_container_hardening(root: Path) -> tuple[str, ...]:
    """Return deterministic findings; an empty tuple means REL-004 passes."""
    compose_path = root / "docker-compose.yml"
    control_dockerfile = root / "docker/Dockerfile.control-plane"
    worker_dockerfile = root / "docker/Dockerfile.browser-worker"
    findings: list[str] = []

    for path in (compose_path, control_dockerfile, worker_dockerfile):
        if not path.is_file():
            findings.append(f"missing required file: {path.relative_to(root)}")
    if findings:
        return tuple(findings)

    compose = compose_path.read_text(encoding="utf-8")
    control = _service_block(compose, "m365-control-plane", "m365-browser-worker")
    worker = _service_block(compose, "m365-browser-worker", None)

    for name, block in (("control-plane", control), ("browser-worker", worker)):
        if not block:
            findings.append(f"missing compose service: {name}")
            continue
        if "no-new-privileges:true" not in block:
            findings.append(f"{name}: no-new-privileges is required")
        if "cap_drop:\n      - ALL" not in block:
            findings.append(f"{name}: cap_drop ALL is required")
        tmpfs_lines = tuple(
            line.strip().removeprefix("- ").strip()
            for line in block.splitlines()
            if line.strip().startswith("- /tmp:")
        )
        if len(tmpfs_lines) != 1:
            findings.append(f"{name}: exactly one /tmp tmpfs entry is required")
        elif any(flag not in tmpfs_lines[0].split(":", 1)[1].split(",") for flag in REQUIRED_TMPFS_FLAGS):
            findings.append(f"{name}: /tmp must use rw,noexec,nosuid,nodev")

    if "read_only: true" not in control:
        findings.append("control-plane: read_only filesystem is required")
    if "- /work" not in worker:
        findings.append("browser-worker: writable work state must be tmpfs-backed")

    if "m365-internal:\n    internal: true" not in compose:
        findings.append("m365-internal network must be internal:true")
    for name, block in (("control-plane", control), ("browser-worker", worker)):
        if "- m365-internal" not in block or "- m365-egress" not in block:
            findings.append(f"{name}: internal and egress networks are both required")

    for path, expected_user in (
        (control_dockerfile, "USER planner"),
        (worker_dockerfile, "USER pwuser"),
    ):
        text = path.read_text(encoding="utf-8")
        if "FROM " not in text or "@sha256:" not in text:
            findings.append(f"{path.name}: runtime/base images must be digest pinned")
        if expected_user not in text:
            findings.append(f"{path.name}: expected non-root runtime {expected_user}")

    return tuple(findings)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings = check_container_hardening(root)
    if findings:
        for finding in findings:
            print(f"REL-004 FAIL: {finding}")
        return 1
    print("REL-004 PASS: container hardening parity verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
