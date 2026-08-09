from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

INDEX_PATH = Path("docs/m365-transition/execution-index.json")
SCRIPT_PATH = Path("scripts/check_execution_index.py")


def _document() -> dict[str, Any]:
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def _run(index: Path, previous: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT_PATH), "--index", str(index)]
    if previous is not None:
        command.extend(["--previous", str(previous)])
    # Test-only execution: no shell, fixed interpreter/script, pytest-controlled temp paths.
    return subprocess.run(  # noqa: S603
        command,
        capture_output=True,
        check=False,
        text=True,
    )


def _write(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _item(document: dict[str, Any], key: str) -> dict[str, Any]:
    items = document["items"]
    return next(entry for entry in items if entry["key"] == key)


def test_current_execution_index_is_valid(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    _write(index, _document())
    result = _run(index)
    assert result.returncode == 0
    assert "EXECUTION_INDEX_OK" in result.stdout


def test_duplicate_canonical_key_fails_closed(tmp_path: Path) -> None:
    document = _document()
    items = document["items"]
    items.append(copy.deepcopy(items[0]))
    index = tmp_path / "index.json"
    _write(index, document)

    result = _run(index)
    assert result.returncode != 0
    assert "duplicate canonical key" in result.stderr


def test_mock_only_item_cannot_claim_live_support(tmp_path: Path) -> None:
    document = _document()
    outlook_item = _item(document, "OUT-053")
    outlook_item["liveSupportState"] = "SUPPORTED_LIVE"
    index = tmp_path / "index.json"
    _write(index, document)

    result = _run(index)
    assert result.returncode != 0
    assert "SUPPORTED_LIVE" in result.stderr


def test_illegal_ready_to_accepted_jump_is_rejected(tmp_path: Path) -> None:
    previous = _document()
    current = copy.deepcopy(previous)
    previous_item = _item(previous, "OUT-060")
    current_item = _item(current, "OUT-060")
    assert previous_item["state"] == "READY"
    current_item["state"] = "ACCEPTED"

    previous_path = tmp_path / "previous.json"
    current_path = tmp_path / "current.json"
    _write(previous_path, previous)
    _write(current_path, current)

    result = _run(current_path, previous_path)
    assert result.returncode != 0
    assert "illegal state transition" in result.stderr


def test_in_progress_to_integrating_transition_is_allowed(tmp_path: Path) -> None:
    previous = _document()
    previous_item = _item(previous, "M365-CONTROL-001")
    previous_item["state"] = "IN_PROGRESS"
    previous_item["wave"] = None

    current = copy.deepcopy(previous)
    current_item = _item(current, "M365-CONTROL-001")
    current_item["state"] = "INTEGRATING"
    current_item["wave"] = "control-index-bootstrap"

    previous_path = tmp_path / "previous.json"
    current_path = tmp_path / "current.json"
    _write(previous_path, previous)
    _write(current_path, current)

    result = _run(current_path, previous_path)
    assert result.returncode == 0
