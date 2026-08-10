#!/usr/bin/env python3
"""Temporary fail-closed Wave T ACCEPTED / Wave U IN_PROGRESS transition."""
from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")
U_KEYS = ("XAPP-001", "XAPP-002", "XAPP-003", "XAPP-004", "XAPP-005", "XAPP-006")


def mutate(text: str, key: str, old_state: str, new_state: str) -> str:
    marker = f'    {{\n      "key": "{key}",'
    start = text.find(marker)
    end = text.find("\n    },", start)
    if start < 0 or end < 0:
        raise SystemExit(f"{key}: item boundary not found")
    end += len("\n    },")
    block = text[start:end]
    old = f'"state": "{old_state}"'
    if block.count(old) != 1:
        raise SystemExit(f"{key}: expected one {old}")
    if '"liveSupportState": "UNOBSERVED"' not in block:
        raise SystemExit(f"{key}: live support invariant changed")
    block = block.replace(old, f'"state": "{new_state}"', 1)
    return text[:start] + block + text[end:]


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    text = mutate(text, "OUT-140", "INTEGRATING", "ACCEPTED")
    for key in U_KEYS:
        text = mutate(text, key, "READY", "IN_PROGRESS")
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
