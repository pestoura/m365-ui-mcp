"""Regression suite: Planner Web is an admitted source for auth bootstrap NAVIGATE only.

Confirmed bug: ``POST /auth/bootstrap/navigate`` was denied by
``AuthBootstrapGuard`` whenever the single open page of the dedicated persistent
professional profile was ``planner.cloud.microsoft`` — even though
``PersistentBrowser.navigate_auth_bootstrap()`` (AUTH-116) explicitly REUSES that
restored Planner Web tab. The guard only accepted approved Microsoft identity
origins (or a neutral/no page), so the deterministic AUTH-116 page lifecycle
could never be exercised.

The fix is operation-specific and narrow:

* ONLY ``auth_bootstrap_open_planner_web`` may be admitted from a Planner Web
  source, and only through a dedicated injected predicate;
* every other bootstrap operation (``auth_status`` / ``auth_start`` /
  ``auth_resume``) still requires an approved Microsoft authentication origin;
* ``_AUTH_ORIGIN_SUFFIXES`` and ``auth_origin_status`` are unchanged: Planner Web
  is NOT reclassified as a global auth origin;
* browser-started / dedicated-profile / full-attestation deferral invariants and
  the non-auth operation denial are unchanged.
"""

from __future__ import annotations

import pytest

from m365_browser_worker.auth_bootstrap import (
    _AUTH_ORIGIN_SUFFIXES,
    AuthBootstrapGuard,
    AuthOriginStatus,
    auth_origin_status,
)
from m365_browser_worker.bootstrap_navigation import (
    AUTH_BOOTSTRAP_NAVIGATE_OPERATION,
    PLANNER_WEB_BOOTSTRAP_URL,
)
from planner_mcp.errors import PolicyDenied, WorkerUnavailable

PLANNER_WEB_PAGE = "https://planner.cloud.microsoft/webui/myplans/"

_OTHER_BOOTSTRAP_OPERATIONS = ("auth_status", "auth_start", "auth_resume")


def _guard(
    *,
    started: bool = True,
    dedicated: bool = True,
    approved_origin: bool = False,
    planner_web_source: bool = True,
    fully_attested: bool = False,
) -> AuthBootstrapGuard:
    return AuthBootstrapGuard(
        browser_started_provider=lambda: started,
        dedicated_profile_provider=lambda: dedicated,
        approved_auth_origin_provider=lambda: approved_origin,
        fully_attested_provider=lambda: fully_attested,
        strict_live_guard=lambda _op: None,
        planner_web_bootstrap_source_provider=lambda: planner_web_source,
    )


def test_navigate_admitted_from_planner_web_source() -> None:
    # The confirmed bug: this raised PolicyDenied ("approved Microsoft
    # authentication origin") even though AUTH-116 reuses this exact page.
    _guard().guard(AUTH_BOOTSTRAP_NAVIGATE_OPERATION)  # must not raise


def test_other_bootstrap_operations_still_require_approved_auth_origin() -> None:
    guard = _guard()
    for operation in _OTHER_BOOTSTRAP_OPERATIONS:
        with pytest.raises(PolicyDenied):
            guard.guard(operation)


def test_other_bootstrap_operations_allowed_on_approved_auth_origin() -> None:
    guard = _guard(approved_origin=True, planner_web_source=False)
    for operation in _OTHER_BOOTSTRAP_OPERATIONS:
        guard.guard(operation)  # unchanged behaviour


def test_navigate_denied_when_source_is_neither_planner_web_nor_auth_origin() -> None:
    guard = _guard(approved_origin=False, planner_web_source=False)
    with pytest.raises(PolicyDenied):
        guard.guard(AUTH_BOOTSTRAP_NAVIGATE_OPERATION)


def test_navigate_still_requires_started_browser_and_dedicated_profile() -> None:
    with pytest.raises(WorkerUnavailable):
        _guard(started=False).guard(AUTH_BOOTSTRAP_NAVIGATE_OPERATION)
    with pytest.raises(PolicyDenied):
        _guard(dedicated=False).guard(AUTH_BOOTSTRAP_NAVIGATE_OPERATION)


def test_non_bootstrap_operation_still_denied_even_from_planner_web() -> None:
    with pytest.raises(PolicyDenied):
        _guard().guard("planner_plans_read")


def test_planner_web_is_not_promoted_to_global_auth_origin() -> None:
    # No suffix widening, and the closed origin classifier is untouched.
    assert "planner.cloud.microsoft" not in _AUTH_ORIGIN_SUFFIXES
    assert (
        auth_origin_status((PLANNER_WEB_PAGE,)) is AuthOriginStatus.NON_APPROVED_ORIGIN
    )
    assert (
        auth_origin_status((PLANNER_WEB_BOOTSTRAP_URL,))
        is AuthOriginStatus.NON_APPROVED_ORIGIN
    )


def test_planner_web_navigate_operation_constant_is_pinned() -> None:
    from m365_browser_worker.auth_bootstrap import _PLANNER_WEB_BOOTSTRAP_OPERATION

    assert _PLANNER_WEB_BOOTSTRAP_OPERATION == AUTH_BOOTSTRAP_NAVIGATE_OPERATION


def test_planner_web_source_provider_defaults_to_closed() -> None:
    # Omitting the provider must not widen anything: navigate stays denied.
    guard = AuthBootstrapGuard(
        browser_started_provider=lambda: True,
        dedicated_profile_provider=lambda: True,
        approved_auth_origin_provider=lambda: False,
        fully_attested_provider=lambda: False,
        strict_live_guard=lambda _op: None,
    )
    with pytest.raises(PolicyDenied):
        guard.guard(AUTH_BOOTSTRAP_NAVIGATE_OPERATION)
