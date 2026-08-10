#!/usr/bin/env python3
"""Temporary fail-closed Wave S INTEGRATING / Wave T staging transition."""
from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")
S_PRS = {
    "OUT-133": 512,
    "OUT-134": 513,
    "OUT-135": 514,
    "OUT-136": 515,
    "OUT-137": 516,
    "OUT-138": 517,
}
EVIDENCE = (
    '      "evidence": [\n'
    '        "pr:518",\n'
    '        "gha:31369288470/jds-effective-plan",\n'
    '        "main:ed72a1373e6af6e2df28197a76b1a4f3cf604ed3"\n'
    '      ],'
)


def item_bounds(text: str, key: str) -> tuple[int, int]:
    marker = f'    {{\n      "key": "{key}",'
    start = text.find(marker)
    end = text.find("\n    },", start)
    if start < 0 or end < 0:
        raise SystemExit(f"{key}: item boundary not found")
    return start, end + len("\n    },")


def mutate_s(text: str, key: str, pr: int) -> str:
    start, end = item_bounds(text, key)
    block = text[start:end]
    required = {
        '"state": "IN_PROGRESS"': '"state": "INTEGRATING"',
        '"prs": []': f'"prs": [{pr}]',
        '      "evidence": [],': EVIDENCE,
        '"implementationState": "SPECIFIED_ONLY"': '"implementationState": "IMPLEMENTED_MOCK_ONLY"',
    }
    for old, new in required.items():
        if block.count(old) != 1:
            raise SystemExit(f"{key}: expected exactly one {old}")
        block = block.replace(old, new, 1)
    if '"liveSupportState": "UNOBSERVED"' not in block:
        raise SystemExit(f"{key}: live support invariant changed")
    return text[:start] + block + text[end:]


def stage_t(text: str) -> str:
    if '"key": "OUT-139"' in text or '"key": "OUT-140"' in text:
        raise SystemExit("Wave T keys already exist")
    marker = '    {\n      "key": "REL-026",'
    position = text.find(marker)
    if position < 0:
        raise SystemExit("REL-026 insertion marker not found")
    items = '''    {
      "key": "OUT-139",
      "releaseBand": "0.7.x-people-todo-shared",
      "phase": "14-ooo-polls-groups-advanced",
      "dependencies": ["OUT-138"],
      "state": "SUPERSEDED",
      "riskClass": "GOVERNANCE",
      "wave": "wave-t-out-139-140",
      "branch": null,
      "issue": null,
      "prs": [],
      "evidence": [],
      "implementationState": "PLANNED",
      "liveSupportState": "UNOBSERVED",
      "blockerCode": null
    },
    {
      "key": "OUT-140",
      "releaseBand": "0.7.x-people-todo-shared",
      "phase": "14-ooo-polls-groups-advanced",
      "dependencies": ["OUT-139"],
      "state": "READY",
      "riskClass": "GOVERNANCE",
      "wave": "wave-t-out-139-140",
      "branch": "wave-t/out-140-specific-addin-framework",
      "issue": null,
      "prs": [],
      "evidence": [],
      "implementationState": "SPECIFIED_ONLY",
      "liveSupportState": "UNOBSERVED",
      "blockerCode": null
    },
'''
    return text[:position] + items + text[position:]


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    for key, pr in S_PRS.items():
        text = mutate_s(text, key, pr)
    text = stage_t(text)
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
