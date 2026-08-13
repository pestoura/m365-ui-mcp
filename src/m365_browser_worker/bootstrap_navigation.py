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

from .egress import EgressDecision, evaluate_browser_egress

# FIXED production bootstrap target. Never parameterized, never operator-supplied.
PLANNER_WEB_BOOTSTRAP_URL = "https://planner.cloud.microsoft/"

# Closed sanitized classification returned to the operator instead of the URL.
PLANNER_WEB_TARGET_CLASS = "planner_web"

# Worker-local operation name for the narrow auth-bootstrap guard.
AUTH_BOOTSTRAP_NAVIGATE_OPERATION = "auth_bootstrap_open_planner_web"

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


def evaluate_bootstrap_target() -> EgressDecision:
    """Evaluate the FIXED bootstrap target against the closed egress policy."""
    return evaluate_browser_egress(PLANNER_WEB_BOOTSTRAP_URL)


__all__ = [
    "AUTH_BOOTSTRAP_NAVIGATE_OPERATION",
    "PLANNER_WEB_BOOTSTRAP_URL",
    "PLANNER_WEB_TARGET_CLASS",
    "evaluate_bootstrap_target",
    "is_loopback_peer",
    "is_reusable_bootstrap_page",
]
