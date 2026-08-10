#!/usr/bin/env python3
"""Temporary fail-closed Wave V INTEGRATING / Wave W staging transition."""
from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")
V_PRS = {
    "XAPP-007": 534,
    "XAPP-008": 535,
    "XAPP-009": 536,
    "XAPP-010": 537,
    "XAPP-011": 538,
    "XAPP-012": 539,
}
EVIDENCE = (
    '      "evidence": [\n'
    '        "pr:540",\n'
    '        "gha:31387610590/jds-effective-plan",\n'
    '        "main:1df056cb95ab7bfa0ce5e391f5d8e09acd10dd58"\n'
    '      ],'
)


def item_bounds(text: str, key: str) -> tuple[int, int]:
    marker = f'    {{\n      "key": "{key}",'
    start = text.find(marker)
    end = text.find("\n    },", start)
    if start < 0 or end < 0:
        raise SystemExit(f"{key}: item boundary not found")
    return start, end + len("\n    },")


def mutate_v(text: str, key: str, pr: int) -> str:
    start, end = item_bounds(text, key)
    block = text[start:end]
    replacements = {
        '"state": "IN_PROGRESS"': '"state": "INTEGRATING"',
        '"prs": []': f'"prs": [{pr}]',
        '      "evidence": [],': EVIDENCE,
        '"implementationState": "SPECIFIED_ONLY"': '"implementationState": "IMPLEMENTED_MOCK_ONLY"',
    }
    for old, new in replacements.items():
        if block.count(old) != 1:
            raise SystemExit(f"{key}: expected exactly one {old}")
        block = block.replace(old, new, 1)
    if '"liveSupportState": "UNOBSERVED"' not in block:
        raise SystemExit(f"{key}: live support invariant changed")
    return text[:start] + block + text[end:]


def stage_wave_w(text: str) -> str:
    keys = ("XAPP-013", "XAPP-014", "XAPP-015", "XAPP-016", "XAPP-020", "XAPP-021")
    for key in keys:
        if f'"key": "{key}"' in text:
            raise SystemExit(f"{key}: already exists")
    marker = '    {\n      "key": "REL-026",'
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("REL-026 insertion marker not found")
    specs = (
        ("XAPP-013", "XAPP-012", "wave-w/xapp-013-runbook-promotion"),
        ("XAPP-014", "XAPP-013", "wave-w/xapp-014-hybrid-escalation-policy"),
        ("XAPP-015", "XAPP-014", "wave-w/xapp-015-agentic-budgets"),
        ("XAPP-016", "XAPP-015", "wave-w/xapp-016-minimum-context-shaping"),
        ("XAPP-020", "XAPP-016", "wave-w/xapp-020-outlook-inbox-digest"),
        ("XAPP-021", "XAPP-020", "wave-w/xapp-021-outlook-mail-triage"),
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
            '      "wave": "wave-w-xapp-013-016-020-021",\n'
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
    for key, pr in V_PRS.items():
        text = mutate_v(text, key, pr)
    text = stage_wave_w(text)
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
