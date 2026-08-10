"""REL-005 — Egress-control acceptance for the browser worker.

Asserts the closed egress policy (SEC-116) end to end at the decision function
and at the Playwright route handler, including the negative controls that keep
the suite from being vacuously green. No network call is made.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path

import pytest

from m365_browser_worker import browser as browser_module
from m365_browser_worker.egress import (
    _ALLOWED_HOST_SUFFIXES,
    _DENIED_API_HOSTS,
    enforce_route_egress,
    evaluate_browser_egress,
)

ROOT = Path(__file__).resolve().parents[1]
SECURITY_DOC = ROOT / "docs" / "security.md"


@dataclass
class _Request:
    url: str


class _Route:
    def __init__(self) -> None:
        self.continued = False
        self.aborted_with: str | None = None

    async def continue_(self) -> None:
        self.continued = True

    async def abort(self, reason: str) -> None:
        self.aborted_with = reason


# --- allow path ---------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://planner.cloud.microsoft/webui/plan/x",
        "https://outlook.office.com/mail/inbox",
        "https://login.microsoftonline.com/common/oauth2/authorize",
        "https://contoso.sharepoint.com/sites/team",
        "https://res.cdn.office.net/assets/app.js",
    ],
)
def test_reviewed_microsoft_ui_hosts_are_allowed(url: str) -> None:
    decision = evaluate_browser_egress(url)
    assert decision.allowed is True
    assert decision.reason == "MICROSOFT_M365_ALLOWLIST"


# --- API-surface denial (THR-134 / ADR-008) -----------------------------------


@pytest.mark.parametrize("host", list(_DENIED_API_HOSTS))
def test_declared_api_surfaces_are_denied(host: str) -> None:
    decision = evaluate_browser_egress(f"https://{host}/v1.0/me")
    assert decision.allowed is False
    assert decision.reason == "API_SURFACE_DENIED"


def test_graph_denial_is_not_bypassable_by_case_port_or_trailing_dot() -> None:
    for url in (
        "https://GRAPH.microsoft.com/v1.0/me",
        "https://graph.microsoft.com.:443/v1.0/me",
        "https://graph.microsoft.com:443/v1.0/me",
    ):
        assert evaluate_browser_egress(url).reason == "API_SURFACE_DENIED", url


def test_denied_api_hosts_would_otherwise_have_been_allowed() -> None:
    """Negative control: the deny list must be doing real work."""
    for host in _DENIED_API_HOSTS:
        assert any(
            host == suffix or host.endswith(f".{suffix}") for suffix in _ALLOWED_HOST_SUFFIXES
        ), host


def test_graph_subdomains_are_denied_by_prefix() -> None:
    assert evaluate_browser_egress("https://graph.windows.net/me").reason == "API_SURFACE_DENIED"


# --- fail-closed path ---------------------------------------------------------


@pytest.mark.parametrize(
    "url,reason",
    [
        ("http://planner.cloud.microsoft/", "NON_HTTPS_BLOCKED"),
        ("ftp://office.com/", "NON_HTTPS_BLOCKED"),
        ("javascript:alert(1)", "NON_HTTPS_BLOCKED"),
        ("https://example.com/", "HOST_NOT_ALLOWLISTED"),
        ("https://office.com.attacker.example/", "HOST_NOT_ALLOWLISTED"),
        ("https://notmicrosoft.com/", "HOST_NOT_ALLOWLISTED"),
        ("https:///path", "HOST_MISSING"),
    ],
)
def test_everything_else_fails_closed(url: str, reason: str) -> None:
    decision = evaluate_browser_egress(url)
    assert decision.allowed is False
    assert decision.reason == reason


def test_local_browser_resources_are_not_network_egress() -> None:
    for url in ("about:blank", "data:text/plain,ok", "blob:https://office.com/id"):
        assert evaluate_browser_egress(url).reason == "LOCAL_BROWSER_RESOURCE"


# --- enforcement path ---------------------------------------------------------


async def test_route_handler_aborts_denied_api_surface() -> None:
    route = _Route()
    await enforce_route_egress(route, _Request("https://graph.microsoft.com/v1.0/me"))
    assert route.continued is False
    assert route.aborted_with == "blockedbyclient"


async def test_route_handler_aborts_unreviewed_host() -> None:
    route = _Route()
    await enforce_route_egress(route, _Request("https://example.com/"))
    assert route.continued is False
    assert route.aborted_with == "blockedbyclient"


async def test_route_handler_allows_reviewed_ui_host() -> None:
    route = _Route()
    await enforce_route_egress(route, _Request("https://planner.cloud.microsoft/"))
    assert route.continued is True
    assert route.aborted_with is None


def test_route_policy_is_installed_on_every_browser_context() -> None:
    source = inspect.getsource(browser_module)
    assert 'context.route("**/*", enforce_route_egress)' in source


def test_worker_exposes_no_proxy_or_generic_fetch_primitive() -> None:
    source = inspect.getsource(browser_module).lower()
    for token in ("proxy=", "page.evaluate", "add_init_script", "route.fulfill"):
        assert token not in source, token


def test_egress_policy_is_documented_as_sec_116() -> None:
    text = SECURITY_DOC.read_text(encoding="utf-8")
    assert "**SEC-116 — Closed browser egress policy.**" in text
    assert "API_SURFACE_DENIED" in text
    assert "ADR-008" in text
