"""REL-004 — Container hardening parity with the Planner/Hermes baseline.

Every row of the parity matrix in docs/security.md §9a is asserted against the
actual compose file and Dockerfiles, so hardening drift fails CI instead of
being discovered in deployment. Nothing here builds or runs a container.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"
CONTROL_PLANE_DOCKERFILE = ROOT / "docker" / "Dockerfile.control-plane"
WORKER_DOCKERFILE = ROOT / "docker" / "Dockerfile.browser-worker"
SECURITY_DOC = ROOT / "docs" / "security.md"
SCRATCH_MOUNT = "/tmp" + ":"  # noqa: S108 - a compose mount target, not a host path

PROHIBITED_MOUNT_TOKENS = (
    "/var/run/docker.sock",
    "${HOME}",
    "$HOME",
    "~/",
    "/home/",
    ".config/google-chrome",
    ".config/chromium",
    ".mozilla",
    ".ssh",
    ".gnupg",
    ".aws",
    ".kube",
    "/etc:",
    "/proc:",
    "/sys:",
)


def _compose() -> str:
    return COMPOSE.read_text(encoding="utf-8")


def _service_blocks() -> dict[str, str]:
    text = _compose()
    services = text.split("services:", maxsplit=1)[1].split("\nnetworks:", maxsplit=1)[0]
    blocks: dict[str, str] = {}
    current = ""
    for line in services.splitlines():
        match = re.match(r"^  ([a-z0-9-]+):\s*$", line)
        if match:
            current = match.group(1)
            blocks[current] = ""
            continue
        if current:
            blocks[current] += line + "\n"
    return blocks


def test_both_services_are_present_and_parity_is_evaluated_on_both() -> None:
    assert set(_service_blocks()) == {"browser-worker", "control-plane"}


def test_every_service_drops_capabilities_and_forbids_privilege_escalation() -> None:
    for name, block in _service_blocks().items():
        assert "no-new-privileges:true" in block, name
        assert "cap_drop: [ALL]" in block, name


def test_every_service_declares_memory_and_pid_limits() -> None:
    for name, block in _service_blocks().items():
        assert re.search(r"^\s*mem_limit:\s*\S+", block, flags=re.MULTILINE), name
        assert re.search(r"^\s*pids_limit:\s*\d+", block, flags=re.MULTILINE), name


def test_tmpfs_scratch_is_noexec_and_nosuid_everywhere() -> None:
    for name, block in _service_blocks().items():
        tmpfs_lines = [line for line in block.splitlines() if SCRATCH_MOUNT in line]
        assert tmpfs_lines, name
        for line in tmpfs_lines:
            assert "noexec" in line, (name, line)
            assert "nosuid" in line, (name, line)


def test_control_plane_is_read_only_and_worker_exception_is_explicit() -> None:
    blocks = _service_blocks()
    assert "read_only: true" in blocks["control-plane"]
    assert "read_only: false" in blocks["browser-worker"]
    assert "profile" in blocks["browser-worker"]


def test_worker_publishes_no_port_and_control_plane_binds_loopback_only() -> None:
    blocks = _service_blocks()
    worker_directives = [
        line for line in blocks["browser-worker"].splitlines() if not line.lstrip().startswith("#")
    ]
    assert not any(line.strip() == "ports:" for line in worker_directives)
    published = re.findall(r'^\s*-\s*"([^"]+)"', blocks["control-plane"], flags=re.MULTILINE)
    assert published, "control plane must publish exactly one reviewed port"
    for mapping in published:
        assert mapping.startswith("127.0.0.1:"), mapping


def test_no_prohibited_host_mount_exists_anywhere_in_the_deployment() -> None:
    text = _compose()
    for token in PROHIBITED_MOUNT_TOKENS:
        assert token not in text, token


def test_named_volumes_are_single_owner() -> None:
    blocks = _service_blocks()
    assert "browser-profile:" in blocks["browser-worker"]
    assert "browser-profile" not in blocks["control-plane"]
    assert "mcp-state:" in blocks["control-plane"]
    assert "mcp-state" not in blocks["browser-worker"]


def test_both_base_images_are_pinned_by_digest() -> None:
    for dockerfile in (CONTROL_PLANE_DOCKERFILE, WORKER_DOCKERFILE):
        images = re.findall(r"^FROM\s+(\S+)", dockerfile.read_text(encoding="utf-8"), re.MULTILINE)
        assert images, dockerfile.name
        for image in images:
            assert "@sha256:" in image, (dockerfile.name, image)


def test_runtime_images_run_as_a_non_root_user() -> None:
    control_plane = CONTROL_PLANE_DOCKERFILE.read_text(encoding="utf-8")
    worker = WORKER_DOCKERFILE.read_text(encoding="utf-8")
    assert re.search(r"^USER planner\s*$", control_plane, flags=re.MULTILINE)
    assert control_plane.rstrip().splitlines()[-1].startswith("ENTRYPOINT")
    users = re.findall(r"^USER\s+(\S+)", worker, flags=re.MULTILINE)
    assert users[-1] == "pwuser", users


def test_runtime_images_drop_the_installer_toolchain() -> None:
    for dockerfile in (CONTROL_PLANE_DOCKERFILE, WORKER_DOCKERFILE):
        text = dockerfile.read_text(encoding="utf-8")
        assert re.search(r"pip\S*\"?\s+uninstall -y pip setuptools wheel", text), dockerfile.name


def test_parity_matrix_is_documented_and_references_this_suite() -> None:
    text = SECURITY_DOC.read_text(encoding="utf-8")
    assert "## 9a. Container hardening parity matrix (REL-004)" in text
    assert "tests/test_rel_004_container_hardening_parity.py" in text
    assert "*(PLANNED)*" not in text.split("**SEC-109**", maxsplit=1)[1].split("---")[0]
