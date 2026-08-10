#!/usr/bin/env python3
"""Temporary fail-closed Wave X INTEGRATING / Wave Y staging transition."""
from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")
X_PRS = {
    "XAPP-022": 552,
    "XAPP-023": 553,
    "XAPP-024": 554,
    "XAPP-025": 555,
    "XAPP-026": 556,
    "XAPP-027": 557,
}
EVIDENCE = (
    '      "evidence": [\n'
    '        "pr:558",\n'
    '        "gha:31419349718/jds-effective-plan",\n'
    '        "main:e5a95c9b49e5db6c2ec97110df6b47cb97e9c423"\n'
    '      ],'
)


def item_bounds(text: str, key: str) -> tuple[int, int]:
    marker = f'    {{\n      "key": "{key}",'
    start = text.find(marker)
    end = text.find("\n    },", start)
    if start < 0 or end < 0:
        raise SystemExit(f"{key}: item boundary not found")
    return start, end + len("\n    },")


def mutate_x(text: str, key: str, pr: int) -> str:
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


def stage_wave_y(text: str) -> str:
    key = "XAPP-028"
    if f'"key": "{key}"' in text:
        raise SystemExit(f"{key}: already exists")
    marker = '    {\n      "key": "REL-026",'
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("REL-026 insertion marker not found")
    chunk = (
        "    {\n"
        '      "key": "XAPP-028",\n'
        '      "releaseBand": "0.8.x-execution-plane",\n'
        '      "phase": "15-composite-execution-token-reduction",\n'
        '      "dependencies": ["XAPP-027"],\n'
        '      "state": "READY",\n'
        '      "riskClass": "GOVERNANCE",\n'
        '      "wave": "wave-y-xapp-028",\n'
        '      "branch": "wave-y/xapp-028-daily-m365-context-runbook",\n'
        '      "issue": null,\n'
        '      "prs": [],\n'
        '      "evidence": [],\n'
        '      "implementationState": "SPECIFIED_ONLY",\n'
        '      "liveSupportState": "UNOBSERVED",\n'
        '      "blockerCode": null\n'
        "    },\n"
    )
    return text[:pos] + chunk + text[pos:]


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    for key, pr in X_PRS.items():
        text = mutate_x(text, key, pr)
    text = stage_wave_y(text)
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
