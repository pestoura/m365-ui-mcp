from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "docs/m365-transition/hardening/rel-003-privacy-retention-review.md"


def test_rel_003_covers_sensitive_m365_data_classes() -> None:
    text = REVIEW.read_text(encoding="utf-8").lower()

    for required in (
        "mail subject/body",
        "attachments and attachment content",
        "calendar titles",
        "contacts and directory identity data",
        "browser cookies, storage state",
        "screenshots, traces",
        "synthetic fixtures",
    ):
        assert required in text


def test_rel_003_enforces_minimization_and_retention_invariants() -> None:
    text = REVIEW.read_text(encoding="utf-8")

    assert "Prefer opaque semantic keys" in text
    assert "must not contain bodies, attachments, cookies, access tokens" in text
    assert "must remain inside the browser-worker boundary" in text
    assert "not a default evidence artifact" in text
    assert "Outlook remains `RESERVED`" in text
    assert "zero public Outlook tools" in text
    assert "REL-013" in text
