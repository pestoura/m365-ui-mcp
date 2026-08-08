from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from m365_browser_worker.browser import BrowserConfig, PersistentBrowser
from m365_browser_worker.egress import enforce_route_egress, evaluate_browser_egress


def test_egress_allows_reviewed_microsoft_hosts_only() -> None:
    allowed = (
        "https://planner.cloud.microsoft/",
        "https://login.microsoftonline.com/common/oauth2/",
        "https://contoso.sharepoint.com/sites/test",
        "https://res.cdn.office.net/assets/app.js",
    )
    for url in allowed:
        decision = evaluate_browser_egress(url)
        assert decision.allowed is True
        assert decision.reason == "MICROSOFT_M365_ALLOWLIST"


@pytest.mark.parametrize(
    "url,reason",
    [
        ("http://office.com/", "NON_HTTPS_BLOCKED"),
        ("https://example.com/", "HOST_NOT_ALLOWLISTED"),
        ("https://office.com.evil.example/", "HOST_NOT_ALLOWLISTED"),
        ("javascript:alert(1)", "NON_HTTPS_BLOCKED"),
    ],
)
def test_egress_fails_closed(url: str, reason: str) -> None:
    decision = evaluate_browser_egress(url)
    assert decision.allowed is False
    assert decision.reason == reason


def test_local_browser_resources_do_not_count_as_network_egress() -> None:
    for url in ("about:blank", "data:text/plain,ok", "blob:https://office.com/id"):
        decision = evaluate_browser_egress(url)
        assert decision.allowed is True
        assert decision.reason == "LOCAL_BROWSER_RESOURCE"


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


async def test_route_handler_blocks_unreviewed_hosts() -> None:
    route = _Route()
    await enforce_route_egress(route, _Request("https://example.com/"))
    assert route.continued is False
    assert route.aborted_with == "blockedbyclient"


async def test_route_handler_allows_m365_hosts() -> None:
    route = _Route()
    await enforce_route_egress(route, _Request("https://planner.cloud.microsoft/"))
    assert route.continued is True
    assert route.aborted_with is None


def test_compose_keeps_worker_private_while_adding_dedicated_egress() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    worker_block, control_plane_block = compose.split("  control-plane:", maxsplit=1)

    assert "networks: [browser-internal, m365-egress]" in worker_block
    assert "\n    ports:" not in worker_block
    assert "browser-internal:\n    internal: true" in compose
    assert "m365-egress: {}" in compose
    assert "networks: [browser-internal, edge]" in control_plane_block
    assert "m365-egress" not in control_plane_block.split("networks:", maxsplit=1)[0]


def test_mock_browser_still_never_starts_chromium(tmp_path: Path) -> None:
    browser = PersistentBrowser(BrowserConfig(tmp_path / "profile", mode="mock"))
    assert browser.started is False
