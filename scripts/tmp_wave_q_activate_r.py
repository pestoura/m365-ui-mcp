#!/usr/bin/env python3
"""Temporary fail-closed Wave Q ACCEPTED / Wave R IN_PROGRESS transition."""
from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")
Q_KEYS = ("OUT-121", "OUT-122", "OUT-123", "OUT-124", "OUT-125", "OUT-126")
R_KEYS = ("OUT-127", "OUT-128", "OUT-129", "OUT-130", "OUT-131", "OUT-132")


def mutate_item(text: str, key: str, old_state: str, new_state: str) -> str:
    marker = f'    {{\n      "key": "{key}",'
    start = text.find(marker)
    end = text.find("\n    },", start)
    if start < 0 or end < 0:
        raise SystemExit(f"{key}: item boundary not found")
    end += len("\n    },")
    block = text[start:end]
    old = f'"state": "{old_state}"'
    new = f'"state": "{new_state}"'
    if block.count(old) != 1:
        raise SystemExit(f"{key}: expected one {old!r}")
    if '"liveSupportState": "UNOBSERVED"' not in block:
        raise SystemExit(f"{key}: live invariant changed")
    block = block.replace(old, new, 1)
    return text[:start] + block + text[end:]


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    for key in Q_KEYS:
        text = mutate_item(text, key, "INTEGRATING", "ACCEPTED")
    for key in R_KEYS:
        text = mutate_item(text, key, "READY", "IN_PROGRESS")
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
