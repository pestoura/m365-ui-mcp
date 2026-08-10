#!/usr/bin/env python3
"""Temporary fail-closed Wave T INTEGRATING / Wave U staging transition."""
from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")


def item_bounds(text: str, key: str) -> tuple[int, int]:
    marker = f'    {{\n      "key": "{key}",'
    start = text.find(marker)
    end = text.find("\n    },", start)
    if start < 0 or end < 0:
        raise SystemExit(f"{key}: item boundary not found")
    return start, end + len("\n    },")


def mutate_out140(text: str) -> str:
    start, end = item_bounds(text, "OUT-140")
    block = text[start:end]
    replacements = {
        '"state": "IN_PROGRESS"': '"state": "INTEGRATING"',
        '"prs": []': '"prs": [521]',
        '      "evidence": [],': (
            '      "evidence": [\n'
            '        "pr:522",\n'
            '        "gha:31371417228/jds-effective-plan",\n'
            '        "main:0208007562c2da1e74b9113a4d4130b6897e9638"\n'
            '      ],'
        ),
        '"implementationState": "SPECIFIED_ONLY"': '"implementationState": "IMPLEMENTED_MOCK_ONLY"',
    }
    for old, new in replacements.items():
        if block.count(old) != 1:
            raise SystemExit(f"OUT-140: expected exactly one {old}")
        block = block.replace(old, new, 1)
    if '"liveSupportState": "UNOBSERVED"' not in block:
        raise SystemExit("OUT-140: live support invariant changed")
    return text[:start] + block + text[end:]


def stage_wave_u(text: str) -> str:
    for key in ("XAPP-001", "XAPP-002", "XAPP-003", "XAPP-004", "XAPP-005", "XAPP-006"):
        if f'"key": "{key}"' in text:
            raise SystemExit(f"{key}: already exists")
    marker = '    {\n      "key": "REL-026",'
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("REL-026 insertion marker not found")
    specs = (
        ("XAPP-001", "OUT-140", "wave-u/xapp-001-direct-executor-contract"),
        ("XAPP-002", "XAPP-001", "wave-u/xapp-002-batch-request-contract"),
        ("XAPP-003", "XAPP-002", "wave-u/xapp-003-bounded-batch-scheduler"),
        ("XAPP-004", "XAPP-003", "wave-u/xapp-004-per-node-governance"),
        ("XAPP-005", "XAPP-004", "wave-u/xapp-005-dag-contract"),
        ("XAPP-006", "XAPP-005", "wave-u/xapp-006-dag-scheduler"),
    )
    chunks: list[str] = []
    for key, dep, branch in specs:
        chunks.append(
            "    {\n"
            f'      "key": "{key}",\n'
            '      "releaseBand": "0.8.x-execution-plane",\n'
            '      "phase": "15-composite-execution-token-reduction",\n'
            f'      "dependencies": ["{dep}"],\n'
            '      "state": "READY",\n'
            '      "riskClass": "GOVERNANCE",\n'
            '      "wave": "wave-u-xapp-001-006",\n'
            f'      "branch": "{branch}",\n'
            '      "issue": null,\n'
            '      "prs": [],\n'
            '      "evidence": [],\n'
            '      "implementationState": "SPECIFIED_ONLY",\n'
            '      "liveSupportState": "UNOBSERVED",\n'
            '      "blockerCode": null\n'
            "    },\n"
        )
    return text[:pos] + "".join(chunks) + text[pos:]


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    text = mutate_out140(text)
    text = stage_wave_u(text)
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
