"""Auth and MFA detection helpers for the worker."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from planner_mcp.auth import AuthState, MfaChallenge

_NUMBER_MATCH = re.compile(
    r"(?:enter the number|number matching|open your authenticator[^0-9]{0,80})"
    r"[^0-9]{0,40}(\d{2})\b",
    re.IGNORECASE | re.DOTALL,
)
_BARE_TWO_DIGIT = re.compile(r"\b(\d{2})\b")


def detect_mfa_number(page_text: str) -> str | None:
    """Extract the 2-digit Authenticator number-match value from page text."""
    match = _NUMBER_MATCH.search(page_text)
    if match:
        return match.group(1)
    if "authenticator" in page_text.lower():
        bare = _BARE_TWO_DIGIT.search(page_text)
        if bare:
            return bare.group(1)
    return None


def build_challenge(
    number: str, *, operation_id: str, description: str = "Sign in to Microsoft Planner",
    ttl_seconds: int = 120,
) -> MfaChallenge:
    """Build sanitized MFA metadata. Approval only happens in Authenticator."""
    expires = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    return MfaChallenge(
        number=number,
        operation_id=operation_id,
        service="microsoft-entra-id",
        description=description,
        expires_at=expires.isoformat(),
    )


def classify_page(page_text: str) -> tuple[AuthState, dict[str, Any]]:
    """Classify an auth page into a state plus sanitized metadata."""
    lowered = page_text.lower()
    number = detect_mfa_number(page_text)
    if number:
        challenge = build_challenge(number, operation_id="auth-live")
        return AuthState.MFA_REQUIRED, challenge.to_dict()
    if "approve sign in request" in lowered or "waiting for approval" in lowered:
        return AuthState.WAITING_FOR_MFA, {}
    if "sign in" in lowered or "enter password" in lowered:
        return AuthState.AUTH_REQUIRED, {}
    if "your session has expired" in lowered:
        return AuthState.SESSION_EXPIRED, {}
    return AuthState.UNKNOWN, {}
