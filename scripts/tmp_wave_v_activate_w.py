#!/usr/bin/env python3
"""Temporary fail-closed Wave V ACCEPTED / Wave W IN_PROGRESS transition."""
from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")
V_KEYS = ("XAPP-007", "XAPP-008", "XAPP-009", "XAPP-010", "XAPP-011", "XAPP-012")
W_KEYS = ("XAPP-013", "XAPP-014", "XAPP-015", "XAPP-016", "XAPP-020", "XAPP-021")


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
    for key in V_KEYS:
        text = mutate(text, key, "INTEGRATING", "ACCEPTED")
    for key in W_KEYS:
        text = mutate(text, key, "READY", "IN_PROGRESS")
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
