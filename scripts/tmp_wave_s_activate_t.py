#!/usr/bin/env python3
"""Temporary fail-closed Wave S ACCEPTED / Wave T IN_PROGRESS transition."""
from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")
S_KEYS = ("OUT-133", "OUT-134", "OUT-135", "OUT-136", "OUT-137", "OUT-138")


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
    for key in S_KEYS:
        text = mutate(text, key, "INTEGRATING", "ACCEPTED")
    text = mutate(text, "OUT-140", "READY", "IN_PROGRESS")
    start = text.find('    {\n      "key": "OUT-139",')
    end = text.find("\n    },", start)
    if start < 0 or end < 0:
        raise SystemExit("OUT-139: item boundary not found")
    block = text[start : end + len("\n    },")]
    if '"state": "SUPERSEDED"' not in block:
        raise SystemExit("OUT-139: must remain SUPERSEDED")
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
