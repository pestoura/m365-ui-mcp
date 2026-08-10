"""Closed outbound policy for the Microsoft 365 browser worker.

The worker may reach only explicitly declared Microsoft 365 web origins. The
control plane remains on the private worker network and no browser-worker port
is published. This module intentionally exposes no proxy, fetch or generic
navigation primitive.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

# Deliberately bounded to Microsoft/M365 identity, shell and content domains.
# New domains require reviewed evidence and a policy change.
_ALLOWED_HOST_SUFFIXES = (
    "cloud.microsoft",
    "microsoft.com",
    "microsoft365.com",
    "microsoftonline.com",
    "microsoftonline-p.com",
    "office.com",
    "office.net",
    "office365.com",
    "sharepoint.com",
    "live.com",
    "msauth.net",
    "msftauth.net",
    "windows.net",
    "azureedge.net",
)

# Denied even though their parent suffix is allowlisted: these are API surfaces,
# not the reviewed Microsoft 365 web UI. Graph is a non-dependency (ADR-008) and
# must never silently become the execution substrate (THR-134, SEC-116).
_DENIED_API_HOSTS = (
    "graph.microsoft.com",
    "api.office.com",
)
_DENIED_API_HOST_PREFIXES = (
    "graph.",
)


@dataclass(frozen=True)
class EgressDecision:
    """Sanitized decision for one browser request URL."""

    allowed: bool
    reason: str


def _host_matches(hostname: str, suffix: str) -> bool:
    return hostname == suffix or hostname.endswith(f".{suffix}")


def evaluate_browser_egress(url: str) -> EgressDecision:
    """Return a fail-closed decision for a browser request URL."""
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()

    # Chromium-internal/data URLs do not leave the process/network namespace.
    if scheme in {"about", "blob", "data"}:
        return EgressDecision(True, "LOCAL_BROWSER_RESOURCE")

    if scheme != "https":
        return EgressDecision(False, "NON_HTTPS_BLOCKED")

    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname:
        return EgressDecision(False, "HOST_MISSING")

    if any(_host_matches(hostname, suffix) for suffix in _ALLOWED_HOST_SUFFIXES):
        if hostname in _DENIED_API_HOSTS or hostname.startswith(_DENIED_API_HOST_PREFIXES):
            return EgressDecision(False, "API_SURFACE_DENIED")
        return EgressDecision(True, "MICROSOFT_M365_ALLOWLIST")

    return EgressDecision(False, "HOST_NOT_ALLOWLISTED")


async def enforce_route_egress(route: Any, request: Any) -> None:
    """Playwright route handler that aborts any request outside the closed policy."""
    decision = evaluate_browser_egress(str(request.url))
    if decision.allowed:
        await route.continue_()
        return
    await route.abort("blockedbyclient")
