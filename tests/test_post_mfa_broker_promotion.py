"""Regression tests: post-MFA broker/account-context promotion (AUTH-115).

Before the fix the ``SessionCapabilityBroker`` was wired in ``create_app`` with
a HARDCODED ``AuthState.UNKNOWN`` provider and ``unverified_account_context`` —
neither derived from the live attested evidence nor from any positive post-MFA
surface signal. So ``/auth/status`` and ``/auth/resume`` correctly reported
``AUTHENTICATED`` (via ``common_auth_attested``) while ``/auth/session`` kept
reporting ``auth_state=UNKNOWN``, ``account_context.valid=false`` and
``viable=false``, even after the human approved MFA in Microsoft Authenticator.

These tests prove the broker now promotes only on POSITIVE evidence:
* the dedicated professional profile is on the fixed Planner Web surface
  (the post-MFA landing surface) AND common.auth is attested;
and that the absence of a login form is NOT treated as authenticated.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

import httpx

from m365_browser_worker.account_context import (
    AccountContextState,
    live_account_context,
)
from m365_browser_worker.browser import BrowserConfig, PersistentBrowser
from planner_browser_worker.app import create_app


class _CtxBrowser(PersistentBrowser):
    """Minimal double for ``live_account_context`` unit checks."""

    def __init__(self, *, dedicated: bool, planner_web: bool) -> None:
        super().__init__(
            BrowserConfig(profile_dir=Path.cwd() / ".ctx-browser", mode="live")
        )
        self._dedicated = dedicated
        self._planner_web = planner_web

    @property
    def started(self) -> bool:
        return True

    def is_dedicated_persistent_profile(self) -> bool:
        return self._dedicated

    def planner_web_surface_present(self) -> bool:
        return self._planner_web


def test_live_account_context_requires_positive_planner_web_surface() -> None:
    # Positive proof ONLY: dedicated profile on the fixed Planner Web surface
    # is VERIFIED. Absence of a login form is NOT evidence.
    verified = live_account_context(_CtxBrowser(dedicated=True, planner_web=True))
    assert verified.state is AccountContextState.VERIFIED
    assert verified.valid is True

    not_on_surface = live_account_context(
        _CtxBrowser(dedicated=True, planner_web=False)
    )
    assert not_on_surface.state is AccountContextState.UNVERIFIED
    assert not_on_surface.valid is False

    wrong_profile = live_account_context(
        _CtxBrowser(dedicated=False, planner_web=True)
    )
    assert wrong_profile.valid is False


class _PostMfaBrowser(PersistentBrowser):
    """Double mirroring a dedicated attested profile post-MFA."""

    def __init__(self, *, planner_web_present: bool, attested: bool = True) -> None:
        super().__init__(
            BrowserConfig(profile_dir=Path.cwd() / ".postmfa-browser", mode="live")
        )
        self._planner_web_present = planner_web_present
        self._attested = attested

    @property
    def started(self) -> bool:
        return True

    def is_dedicated_persistent_profile(self) -> bool:
        return True

    def auth_origin_approved(self) -> bool:
        return True

    def common_auth_attested(self) -> bool:
        return self._attested

    def planner_web_surface_present(self) -> bool:
        return self._planner_web_present

    def ensure_live_allowed(self, operation: str) -> None:
        return None


@contextlib.contextmanager
def _live_app(browser: PersistentBrowser):
    """Build a live-mode worker app and restore PLANNER_MODE/M365_MODE after.

    The mode is read at request time by ``_is_mock``, so it must stay 'live'
    for the duration of the request and be restored only once the app is
    discarded. Yielding a context manager avoids leaking 'live' mode into other
    test modules (which would otherwise build their apps in live mode and fail
    on live-settings ConfigurationError).
    """
    previous = {
        "PLANNER_MODE": os.environ.get("PLANNER_MODE"),
        "M365_MODE": os.environ.get("M365_MODE"),
    }
    os.environ["PLANNER_MODE"] = "live"
    os.environ["M365_MODE"] = "live"
    try:
        yield create_app(browser=browser)
    finally:
        for name in ("PLANNER_MODE", "M365_MODE"):
            if previous[name] is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous[name]


async def test_post_mfa_broker_promotes_on_planner_web_surface() -> None:
    # Regression: after common.auth is attested AND the dedicated professional
    # session sits on the fixed Planner Web surface (post-MFA landing), the
    # broker snapshot must report AUTHENTICATED + VERIFIED + viable=true.
    with _live_app(_PostMfaBrowser(planner_web_present=True)) as app:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://worker"
        ) as client:
            status = (await client.get("/auth/status")).json()
            session = (await client.get("/auth/session")).json()
    assert status["state"] == "AUTHENTICATED"
    broker = session["broker"]
    assert broker["auth_state"] == "AUTHENTICATED"
    assert broker["account_context"]["state"] == "VERIFIED"
    assert broker["account_context"]["valid"] is True
    assert broker["viable"] is True


async def test_post_mfa_broker_does_not_promote_without_planner_web_surface() -> None:
    # The absence of a login form is NOT proof of authentication. An attested
    # dedicated profile NOT on the Planner Web surface stays UNVERIFIED and the
    # broker stays non-viable.
    with _live_app(_PostMfaBrowser(planner_web_present=False)) as app:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://worker"
        ) as client:
            status = (await client.get("/auth/status")).json()
            session = (await client.get("/auth/session")).json()
    # attestation is still reflected by the auth-state signal
    assert status["state"] == "AUTHENTICATED"
    broker = session["broker"]
    assert broker["auth_state"] == "AUTHENTICATED"
    assert broker["account_context"]["state"] == "UNVERIFIED"
    assert broker["account_context"]["valid"] is False
    assert broker["viable"] is False
