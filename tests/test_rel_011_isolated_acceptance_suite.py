"""REL-011 — Mock/isolated acceptance suite assurance.

Verifies that the isolated acceptance run is itself trustworthy: it stays in
mock mode, maps every check to a canonical IA scenario from docs/acceptance.md,
covers the scenario families it claims, and fails closed on any failed check.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "isolated_acceptance.py"
ACCEPTANCE_DOC = ROOT / "docs" / "acceptance.md"

EXPECTED_SCENARIOS = {
    "IA-01",
    "IA-02",
    "IA-03",
    "IA-04",
    "IA-05",
    "IA-06",
    "IA-09",
    "IA-11",
    "IA-14",
    "IA-16",
}


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("isolated_acceptance", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_acceptance_script_runs_green_and_writes_its_artifact() -> None:
    completed = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout[-2000:] + completed.stderr[-2000:]

    artifact = ROOT / "artifacts" / "isolated-acceptance.json"
    report = json.loads(artifact.read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["requirement"] == "REL-011"
    assert report["unmapped_checks"] == []
    assert all(check["ok"] for check in report["checks"])


def test_every_check_maps_to_a_scenario_declared_in_the_acceptance_doc() -> None:
    module = _load_module()
    documented = set(re.findall(r"\bIA-\d{2}\b", ACCEPTANCE_DOC.read_text(encoding="utf-8")))
    mapped = set(module.SCENARIO_MAP.values())

    assert "UNMAPPED" not in mapped
    assert mapped <= documented, mapped - documented
    assert mapped == EXPECTED_SCENARIOS


def test_acceptance_run_is_isolated_and_never_claims_live_support() -> None:
    module = _load_module()
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'os.environ["PLANNER_MODE"] = "mock"' in source
    for token in ("IMPLEMENTED_LIVE", "live_acceptance", "graph.microsoft.com"):
        assert token not in source, token

    report = json.loads((ROOT / "artifacts" / "isolated-acceptance.json").read_text("utf-8"))
    by_check = {check["check"]: check for check in report["checks"]}
    assert by_check["mock_mode_enforced"]["ok"] is True
    assert by_check["zero_mutations"]["ok"] is True
    assert by_check["no_graph_backend"]["ok"] is True
    assert module.SCENARIO_MAP["policy_denies_unregistered_tool"] == "IA-09"


def test_critical_scenario_families_have_at_least_one_check_each() -> None:
    module = _load_module()
    report = json.loads((ROOT / "artifacts" / "isolated-acceptance.json").read_text("utf-8"))
    covered: dict[str, int] = {}
    for check in report["checks"]:
        covered[check["scenario"]] = covered.get(check["scenario"], 0) + 1

    for scenario in EXPECTED_SCENARIOS:
        assert covered.get(scenario, 0) >= 1, scenario
    assert set(covered) == set(module.SCENARIO_MAP.values())
    assert sum(covered.values()) == len(module.SCENARIO_MAP)
