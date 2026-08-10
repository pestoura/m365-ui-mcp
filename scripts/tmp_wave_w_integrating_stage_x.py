#!/usr/bin/env python3
"""Temporary fail-closed Wave W INTEGRATING / Wave X staging transition."""
from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")
W_PRS = {
    "XAPP-013": 543,
    "XAPP-014": 544,
    "XAPP-015": 545,
    "XAPP-016": 546,
    "XAPP-020": 547,
    "XAPP-021": 548,
}
EVIDENCE = (
    '      "evidence": [\n'
    '        "pr:549",\n'
    '        "gha:31391882357/jds-effective-plan",\n'
    '        "main:59ab930cba9ed1f005795e7a67cfc255ff716578"\n'
    '      ],'
)


def item_bounds(text: str, key: str) -> tuple[int, int]:
    marker = f'    {{\n      "key": "{key}",'
    start = text.find(marker)
    end = text.find("\n    },", start)
    if start < 0 or end < 0:
        raise SystemExit(f"{key}: item boundary not found")
    return start, end + len("\n    },")


def mutate_w(text: str, key: str, pr: int) -> str:
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


def stage_wave_x(text: str) -> str:
    keys = ("XAPP-022", "XAPP-023", "XAPP-024", "XAPP-025", "XAPP-026", "XAPP-027")
    for key in keys:
        if f'"key": "{key}"' in text:
            raise SystemExit(f"{key}: already exists")
    marker = '    {\n      "key": "REL-026",'
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("REL-026 insertion marker not found")
    specs = (
        ("XAPP-022", "XAPP-021", "wave-x/xapp-022-outlook-person-context"),
        ("XAPP-023", "XAPP-022", "wave-x/xapp-023-outlook-daily-work-context"),
        ("XAPP-024", "XAPP-023", "wave-x/xapp-024-m365-batch-planner-outlook"),
        ("XAPP-025", "XAPP-024", "wave-x/xapp-025-m365-dag-planner-outlook"),
        ("XAPP-026", "XAPP-025", "wave-x/xapp-026-meeting-preparation-runbook"),
        ("XAPP-027", "XAPP-026", "wave-x/xapp-027-project-mail-follow-up-runbook"),
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
            '      "wave": "wave-x-xapp-022-027",\n'
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
    for key, pr in W_PRS.items():
        text = mutate_w(text, key, pr)
    text = stage_wave_x(text)
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
