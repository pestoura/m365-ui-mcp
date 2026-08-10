#!/usr/bin/env python3
"""Temporary fail-closed Wave U INTEGRATING / Wave V staging transition."""
from pathlib import Path

PATH = Path("docs/m365-transition/execution-index.json")
U_PRS = {
    "XAPP-001": 525,
    "XAPP-002": 526,
    "XAPP-003": 527,
    "XAPP-004": 528,
    "XAPP-005": 529,
    "XAPP-006": 530,
}
EVIDENCE = (
    '      "evidence": [\n'
    '        "pr:531",\n'
    '        "gha:31374844743/jds-effective-plan",\n'
    '        "main:2b45338506903a9510bc3e669cffa5068bb0d303"\n'
    '      ],'
)


def item_bounds(text: str, key: str) -> tuple[int, int]:
    marker = f'    {{\n      "key": "{key}",'
    start = text.find(marker)
    end = text.find("\n    },", start)
    if start < 0 or end < 0:
        raise SystemExit(f"{key}: item boundary not found")
    return start, end + len("\n    },")


def mutate_u(text: str, key: str, pr: int) -> str:
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


def stage_wave_v(text: str) -> str:
    keys = ("XAPP-007", "XAPP-008", "XAPP-009", "XAPP-010", "XAPP-011", "XAPP-012")
    for key in keys:
        if f'"key": "{key}"' in text:
            raise SystemExit(f"{key}: already exists")
    marker = '    {\n      "key": "REL-026",'
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("REL-026 insertion marker not found")
    specs = (
        ("XAPP-007", "XAPP-006", "wave-v/xapp-007-typed-output-input-bindings"),
        ("XAPP-008", "XAPP-007", "wave-v/xapp-008-cancellation-deadline-propagation"),
        ("XAPP-009", "XAPP-008", "wave-v/xapp-009-checkpoint-resume"),
        ("XAPP-010", "XAPP-009", "wave-v/xapp-010-dead-letter-manual-intervention"),
        ("XAPP-011", "XAPP-010", "wave-v/xapp-011-runbook-registry-versioning"),
        ("XAPP-012", "XAPP-011", "wave-v/xapp-012-runbook-canonical-serialization"),
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
            '      "wave": "wave-v-xapp-007-012",\n'
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
    for key, pr in U_PRS.items():
        text = mutate_u(text, key, pr)
    text = stage_wave_v(text)
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
