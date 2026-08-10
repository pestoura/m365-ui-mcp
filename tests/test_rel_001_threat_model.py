from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THREAT_MODEL = ROOT / "docs/m365-transition/hardening/rel-001-threat-model.md"


def test_rel_001_threat_model_covers_required_security_boundaries() -> None:
    text = THREAT_MODEL.read_text(encoding="utf-8")
    lowered = text.lower()

    for required in (
        "spoofed or replayed hitl approval",
        "cross-tenant",
        "browser primitive or selector injection",
        "arbitrary url",
        "secret, cookie or storage-state exfiltration",
        "synthetic results represented as live",
        "container privilege escalation",
        "observability",
    ):
        assert required in lowered


def test_rel_001_preserves_outlook_and_browser_invariants() -> None:
    text = THREAT_MODEL.read_text(encoding="utf-8")

    assert "Outlook stays `RESERVED`" in text
    assert "zero public Outlook tools" in text
    assert "No Microsoft Graph execution path" in text
    assert "No public generic browser operation" in text
    assert "REL-013" in text
