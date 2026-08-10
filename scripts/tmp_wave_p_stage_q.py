#!/usr/bin/env python3
"""Temporary fail-closed Wave P -> Q execution-index transition."""
from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")
EVIDENCE = '''"evidence": [
        "pr:491",
        "gha:31345056692/jds-effective-plan",
        "main:275714c0a818443cf11b737a28295c7a6bd9383a"
      ]'''
PRS = {"OUT-116": 486, "OUT-117": 487, "OUT-118": 488, "OUT-119": 489, "OUT-120": 490}


def one(block: str, old: str, new: str, key: str) -> str:
    count = block.count(old)
    if count != 1:
        raise SystemExit(f"{key}: expected one {old!r}, found {count}")
    return block.replace(old, new, 1)


def mutate(text: str, key: str, pr: int) -> str:
    marker = f'    {{\n      "key": "{key}",'
    start = text.find(marker)
    end = text.find("\n    },", start)
    if start < 0 or end < 0:
        raise SystemExit(f"{key}: item boundary not found")
    end += len("\n    },")
    block = text[start:end]
    block = one(block, '"state": "IN_PROGRESS"', '"state": "INTEGRATING"', key)
    block = one(block, '"prs": []', f'"prs": [{pr}]', key)
    block = one(block, '"evidence": []', EVIDENCE, key)
    block = one(block, '"implementationState": "SPECIFIED_ONLY"', '"implementationState": "IMPLEMENTED_MOCK_ONLY"', key)
    if '"liveSupportState": "UNOBSERVED"' not in block:
        raise SystemExit(f"{key}: live invariant changed")
    return text[:start] + block + text[end:]


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    for key, pr in PRS.items():
        text = mutate(text, key, pr)
    for key in ("OUT-121", "OUT-122", "OUT-123", "OUT-124", "OUT-125", "OUT-126"):
        if f'"key": "{key}"' in text:
            raise SystemExit(f"{key}: duplicate staging refused")
    items = '''    {
      "key": "OUT-121",
      "releaseBand": "0.7.x-people-todo-shared",
      "phase": "13-security-compliance-visible",
      "dependencies": ["OUT-120"],
      "state": "READY",
      "riskClass": "OUTBOUND_GOVERNED",
      "wave": "wave-q-out-121-126",
      "branch": "wave-q/out-121-phishing-reporting",
      "issue": null,
      "prs": [],
      "evidence": [],
      "implementationState": "SPECIFIED_ONLY",
      "liveSupportState": "UNOBSERVED",
      "blockerCode": null
    },
    {
      "key": "OUT-122",
      "releaseBand": "0.7.x-people-todo-shared",
      "phase": "13-security-compliance-visible",
      "dependencies": ["OUT-121"],
      "state": "READY",
      "riskClass": "SAFE_WRITE",
      "wave": "wave-q-out-121-126",
      "branch": "wave-q/out-122-sender-safety-management",
      "issue": null,
      "prs": [],
      "evidence": [],
      "implementationState": "SPECIFIED_ONLY",
      "liveSupportState": "UNOBSERVED",
      "blockerCode": null
    },
    {
      "key": "OUT-123",
      "releaseBand": "0.7.x-people-todo-shared",
      "phase": "13-security-compliance-visible",
      "dependencies": ["OUT-122"],
      "state": "READY",
      "riskClass": "SAFE_WRITE",
      "wave": "wave-q-out-121-126",
      "branch": "wave-q/out-123-domain-safety-management",
      "issue": null,
      "prs": [],
      "evidence": [],
      "implementationState": "SPECIFIED_ONLY",
      "liveSupportState": "UNOBSERVED",
      "blockerCode": null
    },
    {
      "key": "OUT-124",
      "releaseBand": "0.7.x-people-todo-shared",
      "phase": "13-security-compliance-visible",
      "dependencies": ["OUT-123"],
      "state": "READY",
      "riskClass": "READ",
      "wave": "wave-q-out-121-126",
      "branch": "wave-q/out-124-security-status-reads",
      "issue": null,
      "prs": [],
      "evidence": [],
      "implementationState": "SPECIFIED_ONLY",
      "liveSupportState": "UNOBSERVED",
      "blockerCode": null
    },
    {
      "key": "OUT-125",
      "releaseBand": "0.7.x-people-todo-shared",
      "phase": "13-security-compliance-visible",
      "dependencies": ["OUT-124"],
      "state": "READY",
      "riskClass": "OUTBOUND_GOVERNED",
      "wave": "wave-q-out-121-126",
      "branch": "wave-q/out-125-purview-encryption-options",
      "issue": null,
      "prs": [],
      "evidence": [],
      "implementationState": "SPECIFIED_ONLY",
      "liveSupportState": "UNOBSERVED",
      "blockerCode": null
    },
    {
      "key": "OUT-126",
      "releaseBand": "0.7.x-people-todo-shared",
      "phase": "13-security-compliance-visible",
      "dependencies": ["OUT-125"],
      "state": "READY",
      "riskClass": "READ",
      "wave": "wave-q-out-121-126",
      "branch": "wave-q/out-126-smime-capability-status",
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
        raise SystemExit("REL-026 anchor mismatch")
    PATH.write_text(text.replace(anchor, items + anchor, 1), encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
