from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "docs/m365-transition/hardening/rel-002-trust-boundary-review.md"


def test_rel_002_documents_all_required_trust_zones_and_flows() -> None:
    text = REVIEW.read_text(encoding="utf-8")
    lowered = text.lower()

    for required in (
        "client / llm",
        "mcp front door",
        "control plane",
        "browser worker",
        "m365 tenant ui",
        "observability / evidence",
        "hitl approval",
        "public caller → browser worker direct network access",
        "cross-tenant",
    ):
        assert required in lowered


def test_rel_002_denies_browser_and_session_leakage() -> None:
    text = REVIEW.read_text(encoding="utf-8")

    assert "raw selector" in text.lower()
    assert "cookie or storage state" in text.lower()
    assert "Session-state reuse across tenant contexts is forbidden" in text
    assert "Outlook remains `RESERVED`" in text
    assert "REL-013" in text
