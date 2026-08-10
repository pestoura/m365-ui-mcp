#!/usr/bin/env python3
"""Temporary fail-closed Wave Q -> R execution-index transition."""
from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")
Q = {
    "OUT-121": 494,
    "OUT-122": 495,
    "OUT-123": 496,
    "OUT-124": 497,
    "OUT-125": 498,
    "OUT-126": 499,
}
EVIDENCE = (
    '"pr:500",\n'
    '        "gha:31348499207/jds-effective-plan",\n'
    '        "main:c94399bf07387d46a34f07c9a5e84ce47adb07ab"'
)
R_ITEMS = (
    ("OUT-127", "13-security-compliance-visible", "OUT-126", "OUTBOUND_GOVERNED", "wave-r/out-127-smime-sign-encrypt"),
    ("OUT-128", "13-security-compliance-visible", "OUT-127", "SAFE_WRITE", "wave-r/out-128-retention-archive-controls"),
    ("OUT-129", "13-security-compliance-visible", "OUT-128", "READ", "wave-r/out-129-compliance-error-mapping"),
    ("OUT-130", "14-ooo-polls-groups-advanced", "OUT-129", "SAFE_WRITE", "wave-r/out-130-automatic-reply-config"),
    ("OUT-131", "14-ooo-polls-groups-advanced", "OUT-130", "SAFE_WRITE", "wave-r/out-131-ooo-message-config"),
    ("OUT-132", "14-ooo-polls-groups-advanced", "OUT-131", "SAFE_WRITE", "wave-r/out-132-ooo-schedule"),
)


def item_bounds(text: str, key: str) -> tuple[int, int]:
    marker = f'    {{\n      "key": "{key}",'
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"{key}: item start not found")
    end = text.find("\n    },", start)
    if end < 0:
        raise SystemExit(f"{key}: item end not found")
    return start, end + len("\n    },")


def transition_q(text: str, key: str, pr: int) -> str:
    start, end = item_bounds(text, key)
    block = text[start:end]
    checks = {
        '"state": "IN_PROGRESS"': '"state": "INTEGRATING"',
        '"prs": []': f'"prs": [{pr}]',
        '"evidence": []': '"evidence": [\n        ' + EVIDENCE + '\n      ]',
        '"implementationState": "SPECIFIED_ONLY"': '"implementationState": "IMPLEMENTED_MOCK_ONLY"',
    }
    if '"liveSupportState": "UNOBSERVED"' not in block:
        raise SystemExit(f"{key}: live support invariant changed")
    for old, new in checks.items():
        if block.count(old) != 1:
            raise SystemExit(f"{key}: expected exactly one {old}")
        block = block.replace(old, new, 1)
    return text[:start] + block + text[end:]


def render_r(key: str, phase: str, dep: str, risk: str, branch: str) -> str:
    return f'''    {{
      "key": "{key}",
      "releaseBand": "0.7.x-people-todo-shared",
      "phase": "{phase}",
      "dependencies": ["{dep}"],
      "state": "READY",
      "riskClass": "{risk}",
      "wave": "wave-r-out-127-132",
      "branch": "{branch}",
      "issue": null,
      "prs": [],
      "evidence": [],
      "implementationState": "SPECIFIED_ONLY",
      "liveSupportState": "UNOBSERVED",
      "blockerCode": null
    }},
'''


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    for key, pr in Q.items():
        text = transition_q(text, key, pr)
    if '"key": "OUT-127"' in text:
        raise SystemExit("Wave R already staged")
    anchor = '    {\n      "key": "REL-026",'
    pos = text.find(anchor)
    if pos < 0:
        raise SystemExit("REL-026 anchor not found")
    addition = "".join(render_r(*item) for item in R_ITEMS)
    text = text[:pos] + addition + text[pos:]
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
