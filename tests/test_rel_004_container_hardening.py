from pathlib import Path

from scripts.check_container_hardening import check_container_hardening


ROOT = Path(__file__).resolve().parents[1]


def test_rel_004_repository_container_hardening_has_no_findings() -> None:
    assert check_container_hardening(ROOT) == ()


def test_rel_004_checker_covers_both_runtime_images_and_network_boundary() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    control = (ROOT / "docker/Dockerfile.control-plane").read_text(encoding="utf-8")
    worker = (ROOT / "docker/Dockerfile.browser-worker").read_text(encoding="utf-8")

    assert "no-new-privileges:true" in compose
    assert compose.count("cap_drop:") >= 2
    assert "m365-internal:\n    internal: true" in compose
    assert "USER planner" in control
    assert "USER pwuser" in worker
    assert "@sha256:" in control
    assert "@sha256:" in worker
