"""Content-free professional account-context enforcement for the M365 worker.

The account context is the fail-closed proof that the live browser session is a
VERIFIED professional account on the expected persistent profile. It is NEVER
synthesized from the absence of login fields: a session is only marked
``VERIFIED`` when the running browser supplies POSITIVE evidence that the
professional account is actually authenticated against the fixed Planner Web
surface (the post-MFA landing surface). Anything else — an unrecognized page, a
neutral placeholder, an intermediate auth interstitial, or a missing positive
signal — falls back to the safe ``UNVERIFIED`` default.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .browser import PersistentBrowser


class AccountContextState(StrEnum):
    """Closed account-context states used for fail-closed authorization."""

    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    AMBIGUOUS = "AMBIGUOUS"
    WRONG_ACCOUNT = "WRONG_ACCOUNT"
    WRONG_TENANT = "WRONG_TENANT"


@dataclass(frozen=True)
class AccountContext:
    """Sanitized context assertion without tenant or user identifiers."""

    state: AccountContextState
    professional: bool
    expected_profile: bool

    @property
    def valid(self) -> bool:
        return (
            self.state is AccountContextState.VERIFIED
            and self.professional
            and self.expected_profile
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "professional": self.professional,
            "expected_profile": self.expected_profile,
            "valid": self.valid,
        }


def unverified_account_context() -> AccountContext:
    """Return the safe default until live context has been explicitly proven."""
    return AccountContext(
        state=AccountContextState.UNVERIFIED,
        professional=False,
        expected_profile=False,
    )


def live_account_context(browser: PersistentBrowser) -> AccountContext:
    """Derive the professional account context from POSITIVE live evidence.

    The only signal that proves a VERIFIED professional session is the dedicated
    persistent professional profile being positioned on the fixed Planner Web
    surface (the post-MFA landing surface). This is the same positive
    classification the live observation endpoint uses to report AUTHENTICATED
    from a surface transition — no URL, DOM text, cookie, token, UPN or tenant
    id is ever read or returned.

    Absence of a login form is explicitly NOT evidence: a session that is not on
    the Planner Web surface (neutral placeholder, intermediate auth interstitial,
    or an unrecognized page) is reported as UNVERIFIED fail-closed. The raw page
    URL value is consumed only by the closed ``is_planner_web_surface_url``
    classifier and never leaves this module.

    A browser that does not expose ``planner_web_surface_present`` (e.g. a test
    double that only models the guard surface) is treated as NOT presenting the
    positive surface, so the context stays UNVERIFIED fail-closed.
    """
    if not browser.is_dedicated_persistent_profile():
        return unverified_account_context()
    surface_present = getattr(browser, "planner_web_surface_present", None)
    if surface_present is not None and surface_present():
        return AccountContext(
            state=AccountContextState.VERIFIED,
            professional=True,
            expected_profile=True,
        )
    return unverified_account_context()


__all__ = [
    "AccountContext",
    "AccountContextState",
    "unverified_account_context",
    "live_account_context",
]
