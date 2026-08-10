"""REL-001..REL-003 — threat model, trust boundary and privacy/retention assurance.

These tests keep the security documentation honest against the code that is
actually in the repository. They assert structure and consistency, never live
behaviour: no tenant is contacted and no support claim is produced here.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THREAT_MODEL = ROOT / "docs" / "threat-model.md"
ARCHITECTURE = ROOT / "docs" / "architecture.md"
PRIVACY = ROOT / "docs" / "privacy-boundary.md"
SECURITY = ROOT / "docs" / "security.md"

M365_SCOPE_THREATS = ("THR-130", "THR-131", "THR-132", "THR-133", "THR-134", "THR-135", "THR-136")
CONTENT_CLASS_ROWS = (
    "Message content",
    "Message participants",
    "Attachment content",
    "Calendar content",
    "Attendee data",
    "Contact data",
    "Folder/category structure",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- REL-001 -----------------------------------------------------------------


def test_threat_model_covers_the_m365_application_scope() -> None:
    text = _text(THREAT_MODEL)
    assert "### 4.14 Microsoft 365 application scope" in text
    for threat in M365_SCOPE_THREATS:
        assert f"**{threat}**" in text, threat


def test_new_threats_declare_status_and_residual_risk() -> None:
    text = _text(THREAT_MODEL)
    allowed_status = {"IMPLEMENTED", "PARTIAL", "PLANNED"}
    for threat in M365_SCOPE_THREATS:
        row = next(line for line in text.splitlines() if line.startswith(f"| **{threat}**"))
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        # id | stride | threat | controls | status | residual
        assert len(cells) == 6, (threat, len(cells))
        assert cells[4] in allowed_status, (threat, cells[4])
        assert cells[5], threat


def test_threat_ids_are_unique_across_the_threat_model() -> None:
    ids = re.findall(r"^\|\s\*\*(THR-\d{3})\*\*", _text(THREAT_MODEL), flags=re.MULTILINE)
    assert len(ids) == len(set(ids)), sorted({i for i in ids if ids.count(i) > 1})


def test_threat_model_does_not_claim_live_outlook_support() -> None:
    text = _text(THREAT_MODEL).lower()
    for phrase in ("supported_live", "live outlook support", "outlook is supported"):
        assert phrase not in text, phrase


# --- REL-002 -----------------------------------------------------------------


def test_architecture_declares_supply_chain_and_application_boundaries() -> None:
    text = _text(ARCHITECTURE)
    assert "**TB-6 / ARCH-057**" in text
    assert "**TB-7 / ARCH-058**" in text
    assert "**ARCH-059 — Application boundary invariants (TB-7).**" in text


def test_application_boundary_invariants_match_enforced_reality() -> None:
    text = _text(ARCHITECTURE)
    section = text.split("**ARCH-059", maxsplit=1)[1].split("**ARCH-055", maxsplit=1)[0]
    assert "17 Planner `READ`" in section
    assert "zero** public tools" in section
    assert "mergeImpliesLiveSupport = false" in section
    assert "most restrictive" in section


def test_public_projection_still_matches_the_declared_boundary() -> None:
    from planner_mcp.tools import TOOL_NAMES

    assert len(TOOL_NAMES) == 17
    assert all(name.startswith("planner_") for name in TOOL_NAMES)
    assert not any("outlook" in name for name in TOOL_NAMES)


def test_trust_boundary_index_covers_the_new_identifiers() -> None:
    assert "| ARCH-050…059 | Trust boundaries |" in _text(ARCHITECTURE)


# --- REL-003 -----------------------------------------------------------------


def test_privacy_boundary_declares_every_m365_content_class() -> None:
    text = _text(PRIVACY)
    assert "**PRIV-066" in text
    for row in CONTENT_CLASS_ROWS:
        assert f"| {row} |" in text, row


def test_every_content_class_declares_no_persistence() -> None:
    text = _text(PRIVACY)
    for row in CONTENT_CLASS_ROWS:
        line = next(line for line in text.splitlines() if line.startswith(f"| {row} |"))
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert cells[2] == "none", (row, cells[2])


def test_retention_rules_are_extensible_and_cache_free() -> None:
    text = _text(PRIVACY)
    assert "**PRIV-067" in text
    assert "**PRIV-068" in text
    assert "**PRIV-069" in text
    assert "PRIV-066…069" in text


def test_state_store_persists_no_message_or_calendar_content() -> None:
    """The privacy claim must hold in code, not only in prose."""
    forbidden = ("body", "subject", "attendee", "recipient", "mail_address", "contact_name")
    sources = sorted((ROOT / "src" / "m365_mcp").glob("*.py"))
    offenders: list[tuple[str, str]] = []
    for path in sources:
        if "sqlite" not in path.read_text(encoding="utf-8").lower():
            continue
        lowered = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            if f'"{token}"' in lowered or f"'{token}'" in lowered:
                offenders.append((path.name, token))
    assert offenders == [], offenders


def test_security_and_privacy_docs_stay_cross_consistent() -> None:
    assert "PRIV-066" in _text(THREAT_MODEL)
    assert "SEC-116" in _text(THREAT_MODEL)
    assert "ADR-008" in _text(SECURITY)
