"""Access to the versioned JSON contracts packaged with the wheel."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

_PACKAGED = Path(__file__).resolve().parent / "_contracts"
_REPO = Path(__file__).resolve().parents[2] / "contracts"


def contracts_dir() -> Path:
    """Return the packaged contracts directory, falling back to the repo tree."""
    if (_PACKAGED / "version.json").exists():
        return _PACKAGED
    return _REPO


@cache
def load_contract(name: str) -> dict[str, Any]:
    """Load a named contract JSON document."""
    path = contracts_dir() / f"{name}.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def version_metadata() -> dict[str, Any]:
    """Return product/schema/contract version metadata."""
    return load_contract("version")
