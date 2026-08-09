"""REL-008 — Policy metadata completeness gate assurance tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from m365_mcp.config import Settings
from m365_mcp.policy import Decision, MetadataPolicyEngine
from m365_mcp.tool_registry import MutationClass, default_tool_registry

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "check_policy_metadata.py"


def test_gate_script_passes_on_the_current_registry() -> None:
    completed = subprocess.run(  # noqa: S603
        [sys.executable, str(GATE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout)
    assert report["status"] == "PASS"
    assert report["requirement"] == "REL-008"
    assert report["violations"] == []
    assert report["tools_checked"] == len(default_tool_registry().names())


def test_every_registered_tool_receives_a_closed_decision_and_tier() -> None:
    engine = MetadataPolicyEngine()
    settings = Settings(mode="mock")
    registry = default_tool_registry()

    for name in registry.names():
        result = engine.evaluate(name, settings)
        assert result.decision in set(Decision)
        assert result.reason
        assert result.security_tier is not None
        assert result.scope is not None
        assert result.application == registry.get(name).application


def test_allow_decisions_are_only_possible_for_read_metadata() -> None:
    engine = MetadataPolicyEngine()
    settings = Settings(mode="mock")
    registry = default_tool_registry()

    for name in registry.names():
        result = engine.evaluate(name, settings)
        if result.decision is Decision.ALLOW:
            assert registry.get(name).mutation_class is MutationClass.READ


def test_unregistered_tool_is_denied_and_produces_no_metadata() -> None:
    result = MetadataPolicyEngine().evaluate("planner_delete_everything", Settings(mode="mock"))
    assert result.decision is Decision.DENY
    assert result.reason == "TOOL_NOT_REGISTERED"
    assert result.security_tier is None
    assert result.capability_keys == ()
