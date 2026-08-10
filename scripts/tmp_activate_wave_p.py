#!/usr/bin/env python3
"""Temporary, fail-closed Wave O acceptance / Wave P activation helper."""

from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")


def transition(text: str, key: str, old: str, new: str) -> str:
    marker = f'    {{\n      "key": "{key}",'
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"{key}: item not found")
    end = text.find("\n    },", start)
    if end < 0:
        raise SystemExit(f"{key}: item terminator not found")
    end += len("\n    },")
    block = text[start:end]
    source = f'"state": "{old}"'
    target = f'"state": "{new}"'
    if block.count(source) != 1:
        raise SystemExit(f"{key}: expected exactly one {source}")
    if '"liveSupportState": "UNOBSERVED"' not in block:
        raise SystemExit(f"{key}: live-support invariant changed unexpectedly")
    block = block.replace(source, target, 1)
    return text[:start] + block + text[end:]


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    for key in ("OUT-110", "OUT-111", "OUT-112", "OUT-113", "OUT-114", "OUT-115"):
        text = transition(text, key, "INTEGRATING", "ACCEPTED")
    for key in ("OUT-116", "OUT-117", "OUT-118", "OUT-119", "OUT-120"):
        text = transition(text, key, "READY", "IN_PROGRESS")
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
