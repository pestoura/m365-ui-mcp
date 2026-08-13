"""Narrowly-scoped authentication bootstrap guard for the M365 browser worker.

This module resolves the LIVE UIContract authentication bootstrap deadlock
without weakening the fail-closed Planner/Outlook controls.

The full-contract ``live_guard`` (``PersistentBrowser.ensure_live_allowed``)
blocks *every* live operation until the relevant UIContract fragment is
attested. That also blocked ``/auth/status``, ``/auth/start`` and
``/auth/resume``, so authentication could never begin pre-attestation and the
attestation campaign itself (which needs an authenticated professional
session) could never be collected.

The authentication bootstrap guard is the only sanctioned pre-attestation
live path. It is deliberately narrow:

* it applies ONLY to ``auth_status`` / ``auth_start`` / ``auth_resume``;
* it may operate BEFORE ``common.auth`` is attested, but ONLY when:
    - the process owns a started live browser,
    - the browser is the DEDICATED persistent professional profile, and
    - the live context is positioned on an approved Microsoft authentication
      origin (or no page has been opened yet, so bootstrap may begin);
* it never reads or returns raw DOM, page text, URLs, cookies, tokens, UPN,
  tenant IDs, mailbox content, or arbitrary navigation;
* it fails closed on wrong profile/origin/browser state;
* once the full relevant UIContract (common + application fragments) is
  legitimately attested, the normal stricter full-contract behavior applies
  again. The ``common.auth`` fragment alone drives only the LIVE auth-state
  signal, NOT the strict read gate.

No runtime endpoint here writes or promotes attestation. Source-of-truth
attestation remains PR/evidence based.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from urllib.parse import urlsplit

from planner_mcp.errors import PolicyDenied, WorkerUnavailable

from .egress import _ALLOWED_HOST_SUFFIXES

# Only authentication lifecycle operations may use the narrowed bootstrap path.
AUTH_BOOTSTRAP_OPERATIONS = frozenset(
    {"auth_status", "auth_start", "auth_resume"}
)

# Strict subset of the Microsoft 365 egress allowlist: identity entry points.
# The bootstrap guard refuses unless the live context is on one of these hosts
# (or no page is open yet, so the operator may begin navigation to one).
_AUTH_ORIGIN_SUFFIXES = (
    "login.microsoftonline.com",
    "login.live.com",
    "login.microsoft.com",
    "account.microsoft.com",
    "entra.microsoft.com",
)


class AuthOriginStatus(StrEnum):
    """Closed status of the live browser context for auth bootstrap only."""

    NO_ACTIVE_PAGE = "NO_ACTIVE_PAGE"
    APPROVED_AUTH_ORIGIN = "APPROVED_AUTH_ORIGIN"
    NON_APPROVED_ORIGIN = "NON_APPROVED_ORIGIN"


def _host_of(url: str) -> str:
    try:
        hostname = (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""
    return hostname


def _is_approved_auth_origin(hostname: str) -> bool:
    if not hostname:
        return False
    return any(
        hostname == suffix or hostname.endswith(f".{suffix}")
        for suffix in _AUTH_ORIGIN_SUFFIXES
    )


def _is_allowlisted_host(hostname: str) -> bool:
    return any(
        hostname == suffix or hostname.endswith(f".{suffix}")
        for suffix in _ALLOWED_HOST_SUFFIXES
    )


# Neutral browser placeholders that carry no identity, tenant or web origin.
# They must NOT disqualify auth bootstrap the way an arbitrary web page would.
# This set is intentionally narrow: only ``about:blank`` and the harmless
# ``chrome://newtab`` variants. It adds NO http/https origin to any allowlist
# and preserves denial of arbitrary web origins.
_NEUTRAL_BOOTSTRAP_URLS = frozenset({"about:blank", "chrome://newtab"})


def _is_neutral_bootstrap_url(url: str) -> bool:
    """Return True for a neutral bootstrap placeholder page.

    Only ``about:blank`` and ``chrome://newtab`` (including harmless trailing
    slash / query variants) are recognized. No http/https origin is ever
    treated as neutral.
    """
    raw = (url or "").strip().lower()
    if not raw:
        return False
    if raw == "about:blank":
        return True
    return raw == "chrome://newtab" or raw.startswith("chrome://newtab/")


class AuthBootstrapGuard:
    """Fail-closed pre-attestation guard for authentication bootstrap only.

    The guard is constructed with injectable providers so it can be unit
    tested without a real browser or tenant. In production ``create_app``
    wires the providers to the real ``PersistentBrowser`` and contract status.
    """

    def __init__(
        self,
        *,
        browser_started_provider: Callable[[], bool],
        dedicated_profile_provider: Callable[[], bool],
        approved_auth_origin_provider: Callable[[], bool],
        fully_attested_provider: Callable[[], bool],
        strict_live_guard: Callable[[str], None],
    ) -> None:
        self._browser_started = browser_started_provider
        self._dedicated_profile = dedicated_profile_provider
        self._approved_origin = approved_auth_origin_provider
        self._fully_attested = fully_attested_provider
        self._strict_live_guard = strict_live_guard

    def guard(self, operation: str) -> None:
        """Allow only constrained authentication bootstrap; fail closed else."""
        if operation not in AUTH_BOOTSTRAP_OPERATIONS:
            raise PolicyDenied(
                "authentication bootstrap guard covers only auth lifecycle operations",
                operation=operation,
            )

        # Once the FULL relevant UIContract (common + application fragments) is
        # legitimately attested, the normal stricter full-contract behavior
        # applies again. The ``common.auth`` fragment alone does NOT widen the
        # strict read gate (it only drives the LIVE auth-state signal), so the
        # bootstrap auth endpoints remain 503 for reads until the whole set is
        # attested. This preserves the deadlock fix: auth may bootstrap while
        # common.auth is unattested, and the strict guard only re-engages once
        # everything needed for reads is attested.
        if self._fully_attested():
            self._strict_live_guard(operation)
            return

        if not self._browser_started():
            raise WorkerUnavailable(
                "authentication bootstrap requires a started live browser",
                operation=operation,
            )

        if not self._dedicated_profile():
            raise PolicyDenied(
                "authentication bootstrap requires the dedicated persistent "
                "professional browser profile",
                operation=operation,
            )

        if not self._approved_origin():
            raise PolicyDenied(
                "authentication bootstrap requires an approved Microsoft "
                "authentication origin",
                operation=operation,
            )

        # Constrained bootstrap allowed. No content is returned by this guard.


def auth_origin_status(page_urls: tuple[str, ...]) -> AuthOriginStatus:
    """Map open page URLs to a closed bootstrap status WITHOUT exposing URLs.

    This is the only place raw page URLs are observed, and they are reduced to
    a host allowlist check. The URL value is never returned to a caller.

    Neutral placeholder pages (``about:blank`` / ``chrome://newtab`` variants)
    are ignored rather than rejected: they carry no identity or web origin, so
    they must not trip the non-approved-origin denial. Any page that resolves to
    a non-allowlisted or non-approved web host still fails closed.
    """
    if not page_urls:
        return AuthOriginStatus.NO_ACTIVE_PAGE
    saw_approved_auth_origin = False
    for raw in page_urls:
        if _is_neutral_bootstrap_url(raw):
            # Neutral placeholder: carries no identity/origin; does not
            # disqualify bootstrap and is not an approved auth origin.
            continue
        host = _host_of(raw)
        if not _is_allowlisted_host(host):
            return AuthOriginStatus.NON_APPROVED_ORIGIN
        if not _is_approved_auth_origin(host):
            return AuthOriginStatus.NON_APPROVED_ORIGIN
        saw_approved_auth_origin = True
    if saw_approved_auth_origin:
        return AuthOriginStatus.APPROVED_AUTH_ORIGIN
    # Every open page is a neutral placeholder; bootstrap may begin.
    return AuthOriginStatus.NO_ACTIVE_PAGE


__all__ = [
    "AUTH_BOOTSTRAP_OPERATIONS",
    "AuthBootstrapGuard",
    "AuthOriginStatus",
    "auth_origin_status",
]
