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
    return subprocess.run(command, capture_output=True, check=False, text=True)


def _write(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


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
    items = document["items"]
    outlook_item = next(item for item in items if item["key"] == "OUT-053")
    outlook_item["liveSupportState"] = "SUPPORTED_LIVE"
    index = tmp_path / "index.json"
    _write(index, document)

    result = _run(index)
    assert result.returncode != 0
    assert "SUPPORTED_LIVE" in result.stderr


def test_illegal_state_jump_is_rejected(tmp_path: Path) -> None:
    previous = _document()
    current = copy.deepcopy(previous)
    current_items = current["items"]
    item = next(entry for entry in current_items if entry["key"] == "OUT-053")
    item["state"] = "ACCEPTED"

    previous_path = tmp_path / "previous.json"
    current_path = tmp_path / "current.json"
    _write(previous_path, previous)
    _write(current_path, current)

    result = _run(current_path, previous_path)
    assert result.returncode != 0
    assert "illegal state transition" in result.stderr


def test_in_progress_to_integrating_transition_is_allowed(tmp_path: Path) -> None:
    previous = _document()
    current = copy.deepcopy(previous)
    current_items = current["items"]
    item = next(entry for entry in current_items if entry["key"] == "OUT-053")
    item["state"] = "INTEGRATING"

    previous_path = tmp_path / "previous.json"
    current_path = tmp_path / "current.json"
    _write(previous_path, previous)
    _write(current_path, current)

    result = _run(current_path, previous_path)
    assert result.returncode == 0
