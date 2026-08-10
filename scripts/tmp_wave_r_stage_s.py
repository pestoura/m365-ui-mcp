#!/usr/bin/env python3
"""Temporary fail-closed Wave R -> S execution-index transition."""
from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")
R = {
    "OUT-127": 503,
    "OUT-128": 504,
    "OUT-129": 505,
    "OUT-130": 506,
    "OUT-131": 507,
    "OUT-132": 508,
}
EVIDENCE = (
    '"pr:509",\n'
    '        "gha:31350061982/jds-effective-plan",\n'
    '        "main:86c32d2bb63f7797ffb825a8eedcd114802b8da9"'
)
S_ITEMS = (
    ("OUT-133", "OUT-132", "SAFE_WRITE", "wave-s/out-133-ooo-calendar-block"),
    ("OUT-134", "OUT-133", "OUTBOUND_GOVERNED", "wave-s/out-134-ooo-decline-new-invitations"),
    ("OUT-135", "OUT-134", "OUTBOUND_GOVERNED", "wave-s/out-135-ooo-cancel-existing-meetings"),
    ("OUT-136", "OUT-135", "OUTBOUND_GOVERNED", "wave-s/out-136-email-poll-management"),
    ("OUT-137", "OUT-136", "READ", "wave-s/out-137-m365-group-discovery"),
    ("OUT-138", "OUT-137", "READ", "wave-s/out-138-group-calendar-mail-review"),
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


def transition_r(text: str, key: str, pr: int) -> str:
    start, end = item_bounds(text, key)
    block = text[start:end]
    replacements = {
        '"state": "IN_PROGRESS"': '"state": "INTEGRATING"',
        '"prs": []': f'"prs": [{pr}]',
        '"evidence": []': '"evidence": [\n        ' + EVIDENCE + '\n      ]',
        '"implementationState": "SPECIFIED_ONLY"': '"implementationState": "IMPLEMENTED_MOCK_ONLY"',
    }
    if '"liveSupportState": "UNOBSERVED"' not in block:
        raise SystemExit(f"{key}: live support invariant changed")
    for old, new in replacements.items():
        if block.count(old) != 1:
            raise SystemExit(f"{key}: expected exactly one {old}")
        block = block.replace(old, new, 1)
    return text[:start] + block + text[end:]


def render_s(key: str, dep: str, risk: str, branch: str) -> str:
    return f'''    {{
      "key": "{key}",
      "releaseBand": "0.7.x-people-todo-shared",
      "phase": "14-ooo-polls-groups-advanced",
      "dependencies": ["{dep}"],
      "state": "READY",
      "riskClass": "{risk}",
      "wave": "wave-s-out-133-138",
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
    for key, pr in R.items():
        text = transition_r(text, key, pr)
    if '"key": "OUT-133"' in text:
        raise SystemExit("Wave S already staged")
    anchor = '    {\n      "key": "REL-026",'
    pos = text.find(anchor)
    if pos < 0:
        raise SystemExit("REL-026 anchor not found")
    addition = "".join(render_s(*item) for item in S_ITEMS)
    text = text[:pos] + addition + text[pos:]
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
