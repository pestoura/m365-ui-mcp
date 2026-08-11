"""Regression gates for the browser-worker Playwright runtime contract."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
DOCKERFILE = ROOT / "docker" / "Dockerfile.browser-worker"


def _worker_playwright_version() -> str:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    dependencies = project["project"]["optional-dependencies"]["worker"]
    pins = [dependency for dependency in dependencies if dependency.startswith("playwright==")]
    assert len(pins) == 1, "worker extra must contain exactly one exact Playwright pin"
    return pins[0].split("==", 1)[1]


def test_browser_worker_installs_worker_extra() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "install --no-cache-dir '.[worker]'" in dockerfile


def test_playwright_python_package_matches_pinned_browser_image() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    package_version = _worker_playwright_version()
    match = re.search(
        r"^FROM mcr\.microsoft\.com/playwright/python:v(?P<version>\d+\.\d+\.\d+)-noble@sha256:",
        dockerfile,
        flags=re.MULTILINE,
    )
    assert match is not None, "browser-worker must use a digest-pinned Playwright Noble image"
    assert match.group("version") == package_version
