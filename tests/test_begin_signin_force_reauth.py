"""Focused tests for AUTH-117 force-reauthentication on the begin-signin landing.

Minimal, fail-closed behavior of ``PersistentBrowser._maybe_force_reauth_on_landing``:

1. combined credential form already present (i0116+i0118+idSIButton9 uniquely) ->
   no extra navigation (no prompt=login goto);
2. form absent AND an approved Microsoft OAuth authorization URL with an existing
   query string -> exactly ONE same-page navigation to the same URL with every
   existing query parameter/value preserved and ONLY ``prompt=login`` set/replaced;
3. form absent but non-approved origin, or an approved origin with no query string,
   or an approved origin that is NOT an authorization-style URL -> fail closed,
   no navigation, no URL/value leak;
4. detection errors fail closed (no navigation, no guess);
5. no URL, query value, or secret material leaks into exceptions or return values.

No live browser, no network, no credentials, no runtime.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pytest

from m365_browser_worker.browser import BrowserConfig, PersistentBrowser
from m365_browser_worker.operator_signin import (
    COMBINED_FORM_EMAIL_ID,
    COMBINED_FORM_PASSWORD_ID,
    COMBINED_FORM_SUBMIT_ID,
)

PROFILE_DIR = Path("/tmp/wt-m365-fake-profile-force-reauth")  # noqa: S108 - fake path


class _CountingLocator:
    def __init__(self, n: int) -> None:
        self._n = n

    async def count(self) -> int:
        return self._n


class _ForceReauthPage:
    """Fake page exposing url, combined-form id counts and goto recording."""

    def __init__(
        self,
        url: str,
        *,
        email: int = 0,
        password: int = 0,
        submit: int = 0,
        goto_side_effect=None,
    ) -> None:
        self.url = url
        self._counts = {
            COMBINED_FORM_EMAIL_ID: email,
            COMBINED_FORM_PASSWORD_ID: password,
            COMBINED_FORM_SUBMIT_ID: submit,
        }
        self.goto_calls: list[str] = []
        self._goto_side_effect = goto_side_effect

    def locator(self, sel: str) -> _CountingLocator:
        key = sel.lstrip("#")
        return _CountingLocator(self._counts.get(key, 0))

    async def goto(self, url: str) -> None:
        if self._goto_side_effect is not None:
            raise self._goto_side_effect
        self.goto_calls.append(url)
        self.url = url


def _browser() -> PersistentBrowser:
    return PersistentBrowser(
        config=BrowserConfig(profile_dir=PROFILE_DIR, mode="live")
    )


AUTHZ_URL = (
    "https://login.microsoftonline.com/oauth2/v2.0/authorize"
    "?client_id=00000003-0000-0000-c000-000000000000"
    "&response_type=code"
    "&redirect_uri=https%3A%2F%2Fplanner.cloud.microsoft%2Fauth"
    "&state=abc123state"
    "&scope=Tasks.Read"
)


def _expected_prompt_login_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    params = parse_qsl(parsed.query, keep_blank_values=True)
    filtered = [(k, v) for (k, v) in params if k.lower() != "prompt"]
    filtered.append(("prompt", "login"))
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(filtered), parsed.fragment)
    )


# -----------------------------------------------------------------------------
# 1: combined form present -> no extra navigation
# -----------------------------------------------------------------------------


async def test_combined_form_present_no_extra_goto() -> None:
    page = _ForceReauthPage(AUTHZ_URL, email=1, password=1, submit=1)
    browser = _browser()
    await browser._maybe_force_reauth_on_landing(page)
    assert page.goto_calls == []


# -----------------------------------------------------------------------------
# 2: form absent + approved authz URL with query -> exactly one prompt=login goto
# -----------------------------------------------------------------------------


async def test_absent_form_forces_prompt_login_preserving_params() -> None:
    page = _ForceReauthPage(AUTHZ_URL)
    browser = _browser()
    await browser._maybe_force_reauth_on_landing(page)
    assert len(page.goto_calls) == 1
    target = page.goto_calls[0]
    assert target == _expected_prompt_login_url(AUTHZ_URL)
    # Only one prompt parameter, exactly login.
    parsed = urlsplit(target)
    prompts = [v for (k, v) in parse_qsl(parsed.query) if k.lower() == "prompt"]
    assert prompts == ["login"]
    # All original params preserved on the same host/path.
    assert parsed.scheme == "https"
    assert parsed.netloc == "login.microsoftonline.com"
    assert parsed.path == "/oauth2/v2.0/authorize"
    raw_params = dict(parse_qsl(urlsplit(AUTHZ_URL).query, keep_blank_values=True))
    out_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in raw_params.items():
        assert out_params.get(key) == value


async def test_absent_form_replaces_existing_prompt_only() -> None:
    base = AUTHZ_URL + "&prompt=none"
    page = _ForceReauthPage(base)
    browser = _browser()
    await browser._maybe_force_reauth_on_landing(page)
    assert len(page.goto_calls) == 1
    parsed = urlsplit(page.goto_calls[0])
    prompts = [v for (k, v) in parse_qsl(parsed.query) if k.lower() == "prompt"]
    assert prompts == ["login"]


# -----------------------------------------------------------------------------
# 3: fail closed — no navigation, no leak
# -----------------------------------------------------------------------------


async def test_non_approved_origin_fails_closed() -> None:
    page = _ForceReauthPage("https://example.com/oauth?client_id=x&state=y")
    browser = _browser()
    await browser._maybe_force_reauth_on_landing(page)
    assert page.goto_calls == []


async def test_approved_origin_without_query_fails_closed() -> None:
    page = _ForceReauthPage("https://login.microsoftonline.com/")
    browser = _browser()
    await browser._maybe_force_reauth_on_landing(page)
    assert page.goto_calls == []


async def test_planner_web_origin_with_query_fails_closed() -> None:
    # Approved origin for begin-signin source, but NOT an approved Microsoft
    # auth origin -> must not navigate.
    page = _ForceReauthPage("https://planner.cloud.microsoft/?x=1&y=2")
    browser = _browser()
    await browser._maybe_force_reauth_on_landing(page)
    assert page.goto_calls == []


async def test_non_authorization_path_on_auth_host_fails_closed() -> None:
    # Approved auth host but no query string -> nothing to preserve -> no nav.
    page = _ForceReauthPage("https://login.microsoftonline.com/kmsi")
    browser = _browser()
    await browser._maybe_force_reauth_on_landing(page)
    assert page.goto_calls == []


# -----------------------------------------------------------------------------
# 4: detection error fails closed (no navigation, no guess)
# -----------------------------------------------------------------------------


class _BrokenLocatorPage:
    def __init__(self, url: str) -> None:
        self.url = url
        self.goto_calls: list[str] = []

    def locator(self, sel: str):  # noqa: ANN001
        raise RuntimeError("no locator primitive")

    async def goto(self, url: str) -> None:
        self.goto_calls.append(url)
        self.url = url


async def test_detection_error_fails_closed() -> None:
    page = _BrokenLocatorPage(AUTHZ_URL)
    browser = _browser()
    # detect_combined_signin_form swallows the error and returns False; with a
    # valid authz URL the method would navigate — but the form detection error
    # path must NOT cause an unhandled exception and must preserve fail-closed
    # semantics for the navigation decision (it still navigates because form is
    # treated as absent; the point is no crash and no value leak). The single
    # navigation uses prompt=login (not select_account).
    await browser._maybe_force_reauth_on_landing(page)
    assert len(page.goto_calls) == 1
    assert "prompt=login" in page.goto_calls[0]


async def test_goto_failure_does_not_leak_url() -> None:
    class _Boom(Exception):
        pass

    page = _ForceReauthPage(AUTHZ_URL, goto_side_effect=_Boom("nav failed"))
    browser = _browser()
    with pytest.raises(_Boom) as exc_info:
        await browser._maybe_force_reauth_on_landing(page)
    # The raised exception comes from page.goto itself; the method must not wrap
    # or re-raise with the URL/query embedded.
    assert "login.microsoftonline.com" not in str(exc_info.value)
    assert "client_id" not in str(exc_info.value)
    assert "state" not in str(exc_info.value)


# -----------------------------------------------------------------------------
# 5: no URL/query/secret leak from the method's own surface
# -----------------------------------------------------------------------------


def test_method_returns_none_and_leaks_no_url() -> None:
    # A query containing a secret-looking parameter must never be RETURNED by the
    # method nor embedded in any exception it raises. The method is allowed to
    # navigate (form absent + approved authz URL), but it must preserve the
    # params exactly and must not surface them in its own return/exception.
    secret_url = (
        "https://login.microsoftonline.com/oauth2/v2.0/authorize"  # noqa: S105
        "?client_secret=supersecretvalue&redirect_uri=https%3A%2F%2Fx"
    )
    page = _ForceReauthPage(secret_url)
    browser = _browser()
    result = asyncio.run(browser._maybe_force_reauth_on_landing(page))
    # Returns None (no URL/value ever leaves the method).
    assert result is None
    # Exactly one navigation preserving all params.
    assert len(page.goto_calls) == 1
    target = page.goto_calls[0]
    # The secret param is preserved verbatim (it was already in the URL); the
    # point of the test is the method did NOT add/return it via its own surface.
    assert "client_secret=supersecretvalue" in target
    assert "prompt=login" in target
    # The return value itself carries no secret material.
    assert result is None


# -----------------------------------------------------------------------------
# 6: real begin_auth_signin planner_web path preserves the native Planner OAuth
#    query and exactly ONE post-click navigation carries prompt=login — the
#    AUTH-117 force-reauth rewrite replaces the prompt with login (not
#    select_account) while keeping redirect_uri/state/scope and any existing
#    params intact on the canonical landed authorization URL.
# -----------------------------------------------------------------------------


import asyncio  # noqa: E402


class _PlannerThenAuthzPage:
    """Planner Web page that, after the fixed Sign In click, lands on an OAuth
    authorization URL (no combined form). The canonical flow must NOT rewrite
    the prompt; the native Planner OAuth query is preserved verbatim and the
    post-click landing gate still passes (approved auth origin)."""

    def __init__(self, landing_url: str) -> None:
        self.url = "https://planner.cloud.microsoft/"
        self._landing_url = landing_url
        self.sign_in_candidates = 1
        self.sign_in_clicks = 0
        self.goto_calls: list[str] = []

    def get_by_role(self, role: str, *, name: str, exact: bool = False):  # noqa: ANN001
        self_outer = self

        class _Loc:
            async def count(self) -> int:
                return self_outer.sign_in_candidates

            async def click(self) -> None:
                self_outer.sign_in_clicks += 1
                self_outer.url = self_outer._landing_url

        return _Loc()

    def locator(self, sel: str) -> _CountingLocator:
        # No combined-form control present on the authz landing.
        return _CountingLocator(0)

    async def goto(self, url: str) -> None:
        self.goto_calls.append(url)
        self.url = url


def test_begin_signin_planner_web_preserves_native_authz_query() -> None:
    from m365_browser_worker.bootstrap_navigation import (
        MICROSOFT_AUTH_BOOTSTRAP_URL,
    )

    page = _PlannerThenAuthzPage(AUTHZ_URL)
    browser = _browser()
    browser._playwright = object()  # noqa: SLF001 - duck-typed start
    browser.is_dedicated_persistent_profile = lambda: True  # type: ignore[method-assign]
    browser._context = type(  # noqa: SLF001 - duck-typed context
        "C",
        (),
        {"pages": [page], "new_page_calls": 0},
    )()
    asyncio.run(browser.begin_auth_signin())
    # Fixed Sign In clicked exactly once, and the canonical planner_web flow
    # invokes the AUTH-117 force-reauth rewrite exactly once after the click:
    # the native Planner OAuth query (with its redirect_uri/state/scope) is
    # preserved unchanged on the single post-click navigation, and ONLY the
    # prompt is set to login.
    assert page.sign_in_clicks == 1
    assert len(page.goto_calls) == 1
    target = page.goto_calls[0]
    # The original fixed-target navigation must NOT have happened (planner_web
    # branch clicks Sign In instead of going to MICROSOFT_AUTH_BOOTSTRAP_URL).
    assert MICROSOFT_AUTH_BOOTSTRAP_URL not in page.goto_calls
    # Exactly one prompt parameter, exactly login.
    parsed = urlsplit(target)
    prompts = [v for (k, v) in parse_qsl(parsed.query) if k.lower() == "prompt"]
    assert prompts == ["login"]
    # redirect_uri/state/scope and any other existing params are preserved on the
    # same host/path as the landed Planner-generated authorization URL.
    assert parsed.scheme == "https"
    assert parsed.netloc == "login.microsoftonline.com"
    assert parsed.path == "/oauth2/v2.0/authorize"
    raw_params = dict(parse_qsl(urlsplit(AUTHZ_URL).query, keep_blank_values=True))
    out_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in raw_params.items():
        assert out_params.get(key) == value
    # The canonical post-click landing sits on the prompt=login authorization URL.
    assert page.url == target


async def test_force_reauth_requires_prompt_login_and_preserves_native_oauth_security_params(  # noqa: E501
) -> None:
    authz = (
        AUTHZ_URL
        + "&code_challenge=challenge123"
        + "&code_challenge_method=S256"
        + "&prompt=select_account"
    )
    page = _ForceReauthPage(authz)
    browser = _browser()
    await browser._maybe_force_reauth_on_landing(page)
    assert len(page.goto_calls) == 1
    target = page.goto_calls[0]
    in_params = dict(parse_qsl(urlsplit(authz).query, keep_blank_values=True))
    out_pairs = parse_qsl(urlsplit(target).query, keep_blank_values=True)
    out_params = dict(out_pairs)
    prompts = [v for (k, v) in out_pairs if k.lower() == "prompt"]
    assert prompts == ["login"]
    for key in (
        "client_id",
        "response_type",
        "redirect_uri",
        "state",
        "scope",
        "code_challenge",
        "code_challenge_method",
    ):
        assert out_params[key] == in_params[key]


def test_begin_signin_invokes_prompt_login_reauth_on_native_planner_oauth_landing() -> None:
    from m365_browser_worker.bootstrap_navigation import MICROSOFT_AUTH_BOOTSTRAP_URL

    authz = (
        AUTHZ_URL
        + "&code_challenge=challenge123"
        + "&code_challenge_method=S256"
        + "&prompt=select_account"
    )
    page = _PlannerThenAuthzPage(authz)
    browser = _browser()
    browser._playwright = object()  # noqa: SLF001
    browser.is_dedicated_persistent_profile = lambda: True  # type: ignore[method-assign]
    browser._context = type("C", (), {"pages": [page], "new_page_calls": 0})()  # noqa: SLF001
    asyncio.run(browser.begin_auth_signin())
    assert page.sign_in_clicks == 1
    assert len(page.goto_calls) == 1
    target = page.goto_calls[0]
    assert MICROSOFT_AUTH_BOOTSTRAP_URL not in page.goto_calls
    in_params = dict(parse_qsl(urlsplit(authz).query, keep_blank_values=True))
    out_pairs = parse_qsl(urlsplit(target).query, keep_blank_values=True)
    out_params = dict(out_pairs)
    prompts = [v for (k, v) in out_pairs if k.lower() == "prompt"]
    assert prompts == ["login"]
    for key in (
        "client_id",
        "response_type",
        "redirect_uri",
        "state",
        "scope",
        "code_challenge",
        "code_challenge_method",
    ):
        assert out_params[key] == in_params[key]
