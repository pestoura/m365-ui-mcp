#!/usr/bin/env python3
"""Temporary fail-closed staging for hardening REL-001..REL-005."""
from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")
ITEMS = (
    ("REL-001", "XAPP-028", "hardening/rel-001-threat-model"),
    ("REL-002", "REL-001", "hardening/rel-002-trust-boundary"),
    ("REL-003", "REL-002", "hardening/rel-003-privacy-retention"),
    ("REL-004", "REL-003", "hardening/rel-004-container-hardening-parity"),
    ("REL-005", "REL-004", "hardening/rel-005-egress-control-acceptance"),
)


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    for key, _, _ in ITEMS:
        if f'"key": "{key}"' in text:
            raise SystemExit(f"{key}: already exists")
    marker = '    {\n      "key": "REL-026",'
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("REL-026 insertion marker not found")
    chunks = []
    for key, dependency, branch in ITEMS:
        chunks.append(
            "    {\n"
            f'      "key": "{key}",\n'
            '      "releaseBand": "0.9.x-hardening",\n'
            '      "phase": "16-acceptance-hardening-release",\n'
            f'      "dependencies": ["{dependency}"],\n'
            '      "state": "READY",\n'
            '      "riskClass": "ASSURANCE",\n'
            '      "wave": "hardening-a-rel-001-005",\n'
            f'      "branch": "{branch}",\n'
            '      "issue": null,\n'
            '      "prs": [],\n'
            '      "evidence": [],\n'
            '      "implementationState": "SPECIFIED_ONLY",\n'
            '      "liveSupportState": "NOT_APPLICABLE",\n'
            '      "blockerCode": null\n'
            "    },\n"
        )
    PATH.write_text(text[:pos] + "".join(chunks) + text[pos:], encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
