#!/usr/bin/env python3
"""Temporary, fail-closed Wave O -> P execution-index transition helper."""

from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")
EVIDENCE = '''"evidence": [
        "pr:483",
        "gha:31343439935/jds-effective-plan",
        "main:030ea78bd3febc6ed8c1195fd2700cf8b1d69ad6"
      ]'''
LANE_PRS = {
    "OUT-110": 477,
    "OUT-111": 478,
    "OUT-112": 479,
    "OUT-113": 480,
    "OUT-114": 481,
    "OUT-115": 482,
}


def once(block: str, old: str, new: str, key: str) -> str:
    count = block.count(old)
    if count != 1:
        raise SystemExit(f"{key}: expected exactly one {old!r}, found {count}")
    return block.replace(old, new, 1)


def mutate_item(text: str, key: str, pr: int) -> str:
    marker = f'    {{\n      "key": "{key}",'
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"{key}: controller item not found")
    end = text.find("\n    },", start)
    if end < 0:
        raise SystemExit(f"{key}: controller item terminator not found")
    end += len("\n    },")
    block = text[start:end]
    block = once(block, '"state": "IN_PROGRESS"', '"state": "INTEGRATING"', key)
    block = once(block, '"prs": []', f'"prs": [{pr}]', key)
    block = once(block, '"evidence": []', EVIDENCE, key)
    block = once(
        block,
        '"implementationState": "SPECIFIED_ONLY"',
        '"implementationState": "IMPLEMENTED_MOCK_ONLY"',
        key,
    )
    if '"liveSupportState": "UNOBSERVED"' not in block:
        raise SystemExit(f"{key}: live-support invariant changed unexpectedly")
    return text[:start] + block + text[end:]


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    for key, pr in LANE_PRS.items():
        text = mutate_item(text, key, pr)

    new_keys = ("OUT-116", "OUT-117", "OUT-118", "OUT-119", "OUT-120")
    for key in new_keys:
        if f'"key": "{key}"' in text:
            raise SystemExit(f"{key}: already exists; refusing duplicate staging")

    new_items = '''    {
      "key": "OUT-116",
      "releaseBand": "0.7.x-people-todo-shared",
      "phase": "12-people-todo-shared",
      "dependencies": ["OUT-115"],
      "state": "READY",
      "riskClass": "OUTBOUND_GOVERNED",
      "wave": "wave-p-out-116-120",
      "branch": "wave-p/out-116-shared-mailbox-send-as",
      "issue": null,
      "prs": [],
      "evidence": [],
      "implementationState": "SPECIFIED_ONLY",
      "liveSupportState": "UNOBSERVED",
      "blockerCode": null
    },
    {
      "key": "OUT-117",
      "releaseBand": "0.7.x-people-todo-shared",
      "phase": "12-people-todo-shared",
      "dependencies": ["OUT-116"],
      "state": "READY",
      "riskClass": "OUTBOUND_GOVERNED",
      "wave": "wave-p-out-116-120",
      "branch": "wave-p/out-117-shared-mailbox-send-on-behalf",
      "issue": null,
      "prs": [],
      "evidence": [],
      "implementationState": "SPECIFIED_ONLY",
      "liveSupportState": "UNOBSERVED",
      "blockerCode": null
    },
    {
      "key": "OUT-118",
      "releaseBand": "0.7.x-people-todo-shared",
      "phase": "12-people-todo-shared",
      "dependencies": ["OUT-117"],
      "state": "READY",
      "riskClass": "READ",
      "wave": "wave-p-out-116-120",
      "branch": "wave-p/out-118-shared-calendar-linkage",
      "issue": null,
      "prs": [],
      "evidence": [],
      "implementationState": "SPECIFIED_ONLY",
      "liveSupportState": "UNOBSERVED",
      "blockerCode": null
    },
    {
      "key": "OUT-119",
      "releaseBand": "0.7.x-people-todo-shared",
      "phase": "12-people-todo-shared",
      "dependencies": ["OUT-118"],
      "state": "READY",
      "riskClass": "READ",
      "wave": "wave-p-out-116-120",
      "branch": "wave-p/out-119-capability-difference-reporting",
      "issue": null,
      "prs": [],
      "evidence": [],
      "implementationState": "SPECIFIED_ONLY",
      "liveSupportState": "UNOBSERVED",
      "blockerCode": null
    },
    {
      "key": "OUT-120",
      "releaseBand": "0.7.x-people-todo-shared",
      "phase": "13-security-compliance-visible",
      "dependencies": ["OUT-119"],
      "state": "READY",
      "riskClass": "OUTBOUND_GOVERNED",
      "wave": "wave-p-out-116-120",
      "branch": "wave-p/out-120-junk-not-junk-reporting",
      "issue": null,
      "prs": [],
      "evidence": [],
      "implementationState": "SPECIFIED_ONLY",
      "liveSupportState": "UNOBSERVED",
      "blockerCode": null
    },
'''
    anchor = '    {\n      "key": "REL-026",'
    if text.count(anchor) != 1:
        raise SystemExit("REL-026 anchor must occur exactly once")
    PATH.write_text(text.replace(anchor, new_items + anchor, 1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
