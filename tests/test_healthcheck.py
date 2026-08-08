"""Internal healthcheck tests."""

from __future__ import annotations

import ast
import inspect

from planner_mcp import healthcheck


def test_healthcheck_does_not_probe_mcp_endpoint() -> None:
    source = inspect.getsource(healthcheck)
    code = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    )
    module = ast.parse(code)
    literals = {
        node.value
        for node in ast.walk(module)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    docstrings = {(ast.get_docstring(module) or "").strip()}
    for node in ast.walk(module):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            docstrings.add((ast.get_docstring(node) or "").strip())
    probe_literals = {
        value for value in literals if "/mcp" in value and value.strip() not in docstrings
    }
    assert not probe_literals


def test_healthcheck_reports_all_three_probes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PLANNER_STATE_PATH", str(tmp_path / "s.sqlite3"))
    monkeypatch.setattr(healthcheck, "_tcp_ok", lambda *a, **k: True)
    monkeypatch.setattr(healthcheck, "_worker_ok", lambda *a, **k: True)
    report = healthcheck.check()
    assert set(report) == {"ok", "sqlite", "control_plane_tcp", "worker_health"}
    assert report["ok"] is True


def test_healthcheck_fails_closed_when_worker_down(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PLANNER_STATE_PATH", str(tmp_path / "s.sqlite3"))
    monkeypatch.setattr(healthcheck, "_tcp_ok", lambda *a, **k: True)
    monkeypatch.setattr(healthcheck, "_worker_ok", lambda *a, **k: False)
    assert healthcheck.check()["ok"] is False
