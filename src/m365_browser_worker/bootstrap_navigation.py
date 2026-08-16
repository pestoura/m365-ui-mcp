"""OPERATOR-ONLY fixed-target authentication bootstrap navigation policy.

This module owns the single sanctioned navigation target used to bootstrap an
interactive professional Microsoft 365 sign-in, plus the loopback admission
decision for the worker-local operator endpoint.

Hard invariants (no generic browser primitive is created here):

* the navigation target is a FIXED production constant. There is no
  URL/host/path/query parameter anywhere in the call path, so no caller (agent,
  MCP client, control plane or container on the Docker network) can steer the
  browser;
* the constant is re-evaluated at runtime through the closed egress policy
  (``evaluate_browser_egress``) and navigation is refused unless that policy
  returns ALLOW. Graph/API hosts and non-HTTPS remain denied and the Playwright
  route interceptor keeps evaluating redirects and sub-resources;
* admission is a SOCKET-level loopback decision. Proxy/forwarding headers
  (``X-Forwarded-For``, ``X-Real-IP``, ``Forwarded``) are never consulted, so a
  Docker-network client cannot spoof loopback;
* nothing here returns raw URLs, DOM, page text, cookies, tokens, UPN, tenant
  IDs, Planner/mailbox data or browser handles. Only a closed target class is
  exported for sanitized responses.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from .auth_bootstrap import AuthOriginStatus, auth_origin_status
from .egress import EgressDecision, evaluate_browser_egress

# FIXED production bootstrap target. Never parameterized, never operator-supplied.
# This is the safe DEFAULT. It MAY be overridden by the explicit env var
# PLANNER_WEB_BOOTSTRAP_URL at runtime, but ONLY when that value passes the
# closed validator ``validate_planner_web_bootstrap_url`` (https only, exact
# planner.cloud.microsoft host, and an approved Planner Web path). Any
# disallowed value fails closed to this default. The plan/org GUIDs in the
# deep-link form are NOT credentials; they are surface identifiers.
PLANNER_WEB_BOOTSTRAP_URL = "https://planner.cloud.microsoft/"

# Env override key for the acceptance bootstrap target. Operator/overlay may set
# this to the accepted Planner My Plans surface or a reviewed plan deep link;
# the default above stays safe.
PLANNER_WEB_BOOTSTRAP_URL_ENV = "PLANNER_WEB_BOOTSTRAP_URL"

# Approved Planner Web path prefixes for the bootstrap target. The marketing root,
# account-wide My Plans hub and the two reviewed board routes are the only permitted
# destinations; anything else (e.g. /landing, /tasks, arbitrary sub-paths) fails
# closed.
_APPROVED_PLANNER_WEB_PATHS = (
    "/",
    "/webui/myplans/",
    "/webui/plan/",
    "/webui/premiumplan/",
)

# Closed sanitized classification returned to the operator instead of the URL.
PLANNER_WEB_TARGET_CLASS = "planner_web"

# Worker-local operation name for the narrow auth-bootstrap guard.
AUTH_BOOTSTRAP_NAVIGATE_OPERATION = "auth_bootstrap_open_planner_web"

# FIXED production Microsoft authentication bootstrap target. Never parameterized,
# never operator-supplied. Step two of the two-step operator flow: after the
# dedicated professional profile is positioned on Planner Web, navigate exactly
# once to the Microsoft identity host so the operator can complete interactive
# sign-in (including MFA) by hand.
MICROSOFT_AUTH_BOOTSTRAP_URL = "https://login.microsoftonline.com/"

# Closed sanitized classification returned to the operator instead of the URL.
MICROSOFT_AUTH_TARGET_CLASS = "microsoft_auth"

# Worker-local operation name for the dedicated begin-signin guard. The existing
# AuthBootstrapGuard is NOT reused: begin-signin applies its own closed source
# classifier and target evaluator so the Planner Web navigation path is never
# widened.
AUTH_BEGIN_SIGNIN_OPERATION = "auth_begin_signin"

# Worker-local operation name for the operator-only encrypted-store sign-in
# submit (AUTH-101). It applies ONLY the two memory-only sign-in fields to the
# already-open Microsoft authentication page; no URL, no generic DOM primitive,
# no Graph surface, no locator guessing.
AUTH_OPERATOR_SUBMIT_OPERATION = "auth_operator_submit"

# Worker-local operation name for the operator-only pre-attestation email stage
# (AUTH-106). It fills ONLY the email field and clicks ONLY the Next control to
# advance the live Microsoft authentication page to the password step so the four
# ``common.auth`` selectors become observable for attestation. It NEVER types the
# password or clicks Sign in, and it does NOT require attestation to run.
AUTH_BEGIN_EMAIL_STAGE_OPERATION = "auth_begin_email_stage"

# Worker-local operation name for the operator-only live sign-in observation
# endpoint. It reads only a bounded slice of visible body text from the single
# approved Microsoft authentication page and returns a sanitized closed state;
# no URL, DOM, page text, cookie, token, UPN, tenant id or account identifier.
AUTH_OBSERVE_OPERATION = "auth_observe"

# Socket peer addresses accepted for the operator-only endpoint. IPv4-mapped
# IPv6 loopback is included because dual-stack sockets may report that form.
_LOOPBACK_PEERS = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1"})


def is_loopback_peer(peer_host: str | None) -> bool:
    """Return True only for a loopback SOCKET peer address.

    The argument must come from the transport (``request.client.host``). Callers
    must never pass a value derived from request headers: forwarded-for headers
    are attacker-controlled and are deliberately not part of this decision.
    """
    if not peer_host:
        return False
    return peer_host.strip().lower() in _LOOPBACK_PEERS


def is_reusable_bootstrap_page(url: str) -> bool:
    """Return True when an already-open page may be reused for navigation.

    Only neutral placeholder pages (``about:blank`` / ``chrome://newtab``
    variants) are reusable: they carry no identity, no web origin and no page
    state. Any real page is left untouched and a new page is opened instead, so
    an in-flight sign-in or other context is never hijacked. The URL value is
    inspected here and never returned to a caller.
    """
    raw = (url or "").strip().lower()
    if not raw:
        return True
    if raw == "about:blank":
        return True
    return raw == "chrome://newtab" or raw.startswith("chrome://newtab/")


def validate_planner_web_bootstrap_url(url: str) -> EgressDecision:
    """Fail-closed policy for the Planner Web bootstrap target URL.

    Accepts ONLY an https URL on the exact host ``planner.cloud.microsoft`` whose
    path is one of the approved Planner Web routes (root, ``/webui/myplans/``,
    ``/webui/plan/...`` or ``/webui/premiumplan/...``). Every other scheme/host/
    path is refused. The policy is independent of and stricter than the general
    egress allowlist: it constrains the bootstrap destination to reviewed Planner
    Web surfaces and prevents arbitrary sub-paths (e.g. /landing, /tasks) from
    being used.
    """
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https":
        return EgressDecision(False, "NON_HTTPS_BLOCKED")
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if hostname != "planner.cloud.microsoft":
        return EgressDecision(False, "HOST_NOT_PLANNER_CLOUD")
    path = parsed.path or "/"
    # The root is an exact match; sub-paths must match an approved prefix.
    if path == "/":
        pass
    elif not any(path.startswith(p) for p in _APPROVED_PLANNER_WEB_PATHS if p != "/"):
        return EgressDecision(False, "PATH_NOT_APPROVED")
    # Re-confirm through the closed egress policy for defense in depth.
    return evaluate_browser_egress(url)


def resolve_planner_web_bootstrap_url() -> str:
    """Return the effective bootstrap target with fail-closed env override.

    The default ``PLANNER_WEB_BOOTSTRAP_URL`` is always safe. An operator/overlay
    may set ``PLANNER_WEB_BOOTSTRAP_URL_ENV`` to point at an approved Planner Web
    surface such as My Plans or a reviewed plan deep link. Any value that fails
    ``validate_planner_web_bootstrap_url`` is ignored and the safe default is
    returned instead — the browser can never be steered to an unapproved target.
    """
    override = os.environ.get(PLANNER_WEB_BOOTSTRAP_URL_ENV)
    if override:
        if validate_planner_web_bootstrap_url(override).allowed:
            return override
    return PLANNER_WEB_BOOTSTRAP_URL


def evaluate_bootstrap_target() -> EgressDecision:
    """Evaluate the resolved Planner Web bootstrap target against closed egress."""
    return evaluate_browser_egress(resolve_planner_web_bootstrap_url())


def evaluate_microsoft_auth_target() -> EgressDecision:
    """Evaluate the FIXED Microsoft auth target against the closed egress policy.

    The destination is the production constant ``MICROSOFT_AUTH_BOOTSTRAP_URL``.
    There is no URL input: the caller cannot pass a host/path/query, so the
    browser can never be steered elsewhere. Graph/API hosts and non-HTTPS remain
    denied by ``evaluate_browser_egress``.
    """
    return evaluate_browser_egress(MICROSOFT_AUTH_BOOTSTRAP_URL)


def _host_of(url: str) -> str:
    """Return the lowercased hostname of ``url`` without a trailing dot."""
    try:
        hostname = (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""
    return hostname


def _is_planner_web_host(hostname: str) -> bool:
    """Return True only for the exact/suffix host of the Planner Web target."""
    if not hostname:
        return False
    target_host = _host_of(PLANNER_WEB_BOOTSTRAP_URL)
    return hostname == target_host or hostname.endswith(f".{target_host}")


# Neutral placeholder pages that carry no identity, tenant or web origin and so
# may be safely reused as the current page when beginning sign-in.
_NEUTRAL_BOOTSTRAP_URLS = frozenset({"about:blank", "chrome://newtab"})
_NEUTRAL_BOOTSTRAP_PREFIXES = ("chrome://newtab/",)


def _is_neutral_bootstrap_url(url: str) -> bool:
    """Return True for a neutral bootstrap placeholder page.

    Only ``about:blank`` and the harmless ``chrome://newtab`` variants are
    recognized. This mirrors ``auth_bootstrap._is_neutral_bootstrap_url`` but
    does NOT consult the auth-origin allowlist: an arbitrary http/https page is
    never classified as neutral here, so it is denied by the source classifier.
    """
    raw = (url or "").strip().lower()
    if not raw:
        return False
    if raw in _NEUTRAL_BOOTSTRAP_URLS:
        return True
    return any(raw.startswith(prefix) for prefix in _NEUTRAL_BOOTSTRAP_PREFIXES)


class SourceClassStatus:
    """Closed classification of the live browser context for begin-signin."""

    PLANNER_WEB = "planner_web"
    NEUTRAL = "neutral"
    APPROVED_AUTH = "approved_auth"
    NON_APPROVED = "non_approved"


def classify_begin_signin_source(page_urls: tuple[str, ...]) -> str:
    """Classify the current page set as a permitted begin-signin source.

    Permitted ONLY when every open page is one of:

    * ``planner_web`` — host exactly/suffix matching the Planner Web target host;
    * ``neutral`` — an ``about:blank`` / ``chrome://newtab`` placeholder;
    * ``approved_auth`` — an existing approved Microsoft authentication origin
      per the auth-origin policy (``auth_origin_status`` returns
      ``APPROVED_AUTH_ORIGIN``).

    Any page that resolves to a non-allowed or non-approved web host fails
    closed. The raw URLs are reduced to this closed classification and the URL
    value is never returned to a caller.
    """
    if not page_urls:
        # No page opened yet: bootstrap may begin navigation from a fresh page.
        return SourceClassStatus.PLANNER_WEB
    saw_planner_web = False
    saw_approved_auth = False
    for raw in page_urls:
        if _is_neutral_bootstrap_url(raw):
            # Neutral placeholder: carries no identity/origin; does not
            # disqualify begin-signin and is not an approved auth origin.
            continue
        host = _host_of(raw)
        if _is_planner_web_host(host):
            saw_planner_web = True
            continue
        status = auth_origin_status((raw,))
        if status is AuthOriginStatus.APPROVED_AUTH_ORIGIN:
            saw_approved_auth = True
            continue
        return SourceClassStatus.NON_APPROVED
    if saw_planner_web:
        return SourceClassStatus.PLANNER_WEB
    if saw_approved_auth:
        return SourceClassStatus.APPROVED_AUTH
    # Every open page was a neutral placeholder; begin-signin may proceed.
    return SourceClassStatus.NEUTRAL


def is_permitted_begin_signin_source(page_urls: tuple[str, ...]) -> bool:
    """Return True only when the source passes the closed classifier."""
    return classify_begin_signin_source(page_urls) != SourceClassStatus.NON_APPROVED


def is_planner_web_surface_url(url: str) -> bool:
    """Return True only for the exact/suffix host of the Planner Web target.

    Exported closed predicate used by the live observation endpoint to detect
    the post-sign-in surface transition. The URL value is inspected here and
    never returned to a caller.
    """
    return _is_planner_web_host(_host_of(url))


__all__ = [
    "AUTH_BEGIN_SIGNIN_OPERATION",
    "AUTH_BOOTSTRAP_NAVIGATE_OPERATION",
    "MICROSOFT_AUTH_BOOTSTRAP_URL",
    "MICROSOFT_AUTH_TARGET_CLASS",
    "PLANNER_WEB_BOOTSTRAP_URL",
    "PLANNER_WEB_BOOTSTRAP_URL_ENV",
    "PLANNER_WEB_TARGET_CLASS",
    "SourceClassStatus",
    "classify_begin_signin_source",
    "evaluate_bootstrap_target",
    "evaluate_microsoft_auth_target",
    "is_loopback_peer",
    "is_permitted_begin_signin_source",
    "is_planner_web_surface_url",
    "is_reusable_bootstrap_page",
    "resolve_planner_web_bootstrap_url",
    "validate_planner_web_bootstrap_url",
]
