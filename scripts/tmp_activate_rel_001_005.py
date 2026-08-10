#!/usr/bin/env python3
"""Temporary fail-closed activation for hardening REL-001..REL-005."""
from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")
KEYS = ("REL-001", "REL-002", "REL-003", "REL-004", "REL-005")


def mutate(text: str, key: str) -> str:
    marker = f'    {{\n      "key": "{key}",'
    start = text.find(marker)
    end = text.find("\n    },", start)
    if start < 0 or end < 0:
        raise SystemExit(f"{key}: item boundary not found")
    end += len("\n    },")
    block = text[start:end]
    old = '"state": "READY"'
    if block.count(old) != 1:
        raise SystemExit(f"{key}: expected READY exactly once")
    if '"liveSupportState": "NOT_APPLICABLE"' not in block:
        raise SystemExit(f"{key}: live-support state changed")
    return text[:start] + block.replace(old, '"state": "IN_PROGRESS"', 1) + text[end:]


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    for key in KEYS:
        text = mutate(text, key)
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
