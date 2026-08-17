"""Focused tests for the OBSERVED combined Entra ID sign-in form branch.

These exercise the REAL ``submit_operator_signin`` path plus the two new
module-level helpers in ``operator_signin``. No live browser, no network, no
credentials, no runtime.

Covered properties:

1. when the combined form is uniquely present, submit_operator_signin applies
   ONLY the combined-form fill/click exactly once and never touches the
   sequential email -> Next -> password -> Sign-in plan resolution;
2. when the combined form is absent, the incumbent sequential flow runs
   unchanged (fallback);
3. when combined-form detection raises, it fails closed into the sequential
   fallback (never guesses);
4. detect_combined_signin_form is structural/closed: returns True only when
   id=i0116 / id=i0118 / id=idSIButton9 are ALL uniquely present, and False on
   any other count or on detection error (no text read);
5. submit_combined_signin_form fills the two memory-only values into the fixed
   ids and clicks the fixed submit id exactly once, in order, with no MFA
   selector touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import m365_browser_worker.browser as browser_module
from m365_browser_worker.browser import (
    OPERATOR_SIGNIN_STAGE_TIMEOUT_MS,
    BrowserConfig,
    PersistentBrowser,
)
from m365_browser_worker.locator_runtime import (
    LocatorRuntimeError,
    ResolvedLocator,
)
from m365_browser_worker.operator_signin import (
    COMBINED_FORM_EMAIL_ID,
    COMBINED_FORM_PASSWORD_ID,
    COMBINED_FORM_SUBMIT_ID,
    EMAIL_SELECTOR_NAME,
    NEXT_SELECTOR_NAME,
    PASSWORD_SELECTOR_NAME,
    SIGNIN_SELECTOR_NAME,
    OperatorSignInInput,
    detect_combined_signin_form,
    submit_combined_signin_form,
)
from m365_mcp.locators import LocatorCandidate, LocatorPlan, LocatorStrategy
from planner_mcp.errors import PolicyDenied, WorkerUnavailable

PROGRESSION_KEYS = (
    EMAIL_SELECTOR_NAME,
    NEXT_SELECTOR_NAME,
    PASSWORD_SELECTOR_NAME,
    SIGNIN_SELECTOR_NAME,
)

FAKE_EMAIL = "operator@example.com"
FAKE_PASSWORD = "Sup3rSecret!2026"  # noqa: S105 - fake test credential, never real

SEQUENTIAL_ACTION_ORDER = [
    ("fill", EMAIL_SELECTOR_NAME, FAKE_EMAIL),
    ("click", NEXT_SELECTOR_NAME),
    ("fill", PASSWORD_SELECTOR_NAME, FAKE_PASSWORD),
    ("click", SIGNIN_SELECTOR_NAME),
]


# ------------------------------------------------------------------------------
# Fakes (mirror the production-free progression test harness)
# ------------------------------------------------------------------------------


class _FakePage:
    def __init__(self, url: str = "about:blank") -> None:
        self.url = url


class _FakeContext:
    def __init__(self, pages: list[_FakePage] | None = None) -> None:
        self.pages = pages if pages is not None else []


class _RecordingLocator:
    def __init__(self, selector_key: str, actions: list[tuple]) -> None:
        self.selector_key = selector_key
        self._actions = actions

    @property
    def first(self) -> _RecordingLocator:
        return self

    def wait_for(self, *, state: str = "visible", timeout: int | None = None) -> None:
        return None

    def count(self) -> int:
        return 1

    async def fill(self, value: str) -> None:
        self._actions.append(("fill", self.selector_key, value))

    async def click(self) -> None:
        self._actions.append(("click", self.selector_key))


class _Resolver:
    """Recording monkeypatch for ``resolve_visible_locator``."""

    def __init__(self, actions: list[tuple], *, raise_for: set[str] | None = None) -> None:
        self.actions = actions
        self.calls: list[tuple[str, int]] = []
        self.raise_for = raise_for or set()

    async def __call__(self, page, plan, *, timeout_ms: int) -> ResolvedLocator:
        self.calls.append((plan.selector_key, timeout_ms))
        if plan.selector_key in self.raise_for:
            raise LocatorRuntimeError(plan.selector_key, "ambiguous match")
        locator = _RecordingLocator(plan.selector_key, self.actions)
        return ResolvedLocator(candidate=plan.primary, locator=locator)


def _plan_for(selector_key: str) -> LocatorPlan:
    candidate = LocatorCandidate(LocatorStrategy.ROLE, "textbox", name="signin-field")
    return LocatorPlan(selector_key=selector_key, candidates=(candidate,))


class _Scenario:
    """Real ``submit_operator_signin`` with fakes; combined detection swapped in."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, detect=None) -> None:
        self.actions: list[tuple] = []
        self.resolver = _Resolver(self.actions)

        plans = {key: _plan_for(key) for key in PROGRESSION_KEYS}

        def _locator_plan(name: str) -> LocatorPlan | None:
            return plans.get(name)

        monkeypatch.setattr(browser_module, "common_auth_attested", lambda: True)
        monkeypatch.setattr(browser_module, "common_auth_locator_plan", _locator_plan)
        monkeypatch.setattr(browser_module, "resolve_visible_locator", self.resolver)

        # Combined-form branch controls.
        if detect is None:
            async def _detect(page):  # noqa: ANN001
                return False
            detect = _detect
        monkeypatch.setattr(browser_module, "detect_combined_signin_form", detect)
        # Keep the REAL submit helper by default; tests that expect it to fire
        # monkeypatch it themselves before calling run().
        self.combined_submitted = {}

        async def _submit(page, signin):  # noqa: ANN001
            self.combined_submitted["email"] = signin.email
            self.combined_submitted["password"] = signin.password

        self._real_submit = submit_combined_signin_form
        monkeypatch.setattr(browser_module, "submit_combined_signin_form", _submit)

        self.browser = PersistentBrowser(
            config=BrowserConfig(
                profile_dir=Path("/tmp/wt-m365-fake-profile"),  # noqa: S108 - fake path
                headless=True,
                mode="live",
            )
        )
        self.browser._playwright = object()
        self.browser._context = _FakeContext(
            [_FakePage(url="https://login.microsoftonline.com/")]
        )
        self.browser.is_dedicated_persistent_profile = lambda: True  # type: ignore[method-assign]
        self.browser._signin_surface_resolved = True  # type: ignore[attr-defined]
        self.browser.auth_origin_approved = lambda: True  # type: ignore[method-assign]

    async def run(self) -> None:
        signin = OperatorSignInInput(email=FAKE_EMAIL, password=FAKE_PASSWORD)
        await self.browser.submit_operator_signin(signin)


# ------------------------------------------------------------------------------
# 1 + 3: combined form present -> combined submit, sequential untouched
# ------------------------------------------------------------------------------


async def test_combined_form_present_submits_combined_only(monkeypatch) -> None:
    scenario = _Scenario(monkeypatch, detect=_always_true)

    await scenario.run()

    # Combined helper fired exactly once with the memory-only values (no leak).
    assert scenario.combined_submitted == {
        "email": FAKE_EMAIL,
        "password": FAKE_PASSWORD,
    }
    # Sequential plan resolution never invoked.
    assert scenario.resolver.calls == []
    assert scenario.actions == []


async def test_combined_form_absent_falls_back_to_sequential(monkeypatch) -> None:
    scenario = _Scenario(monkeypatch, detect=_always_false)

    await scenario.run()

    assert scenario.combined_submitted == {}
    assert scenario.actions == SEQUENTIAL_ACTION_ORDER
    assert scenario.resolver.calls == [
        (EMAIL_SELECTOR_NAME, OPERATOR_SIGNIN_STAGE_TIMEOUT_MS),
        (NEXT_SELECTOR_NAME, OPERATOR_SIGNIN_STAGE_TIMEOUT_MS),
        (PASSWORD_SELECTOR_NAME, OPERATOR_SIGNIN_STAGE_TIMEOUT_MS),
        (SIGNIN_SELECTOR_NAME, OPERATOR_SIGNIN_STAGE_TIMEOUT_MS),
    ]


async def test_combined_detection_error_falls_back_to_sequential(monkeypatch) -> None:
    async def _boom(page):  # noqa: ANN001
        raise RuntimeError("detection failed")

    scenario = _Scenario(monkeypatch, detect=_boom)

    await scenario.run()

    assert scenario.combined_submitted == {}
    assert scenario.actions == SEQUENTIAL_ACTION_ORDER


# ------------------------------------------------------------------------------
# 6: combined submit must continue the password-only tail, not return early
# ------------------------------------------------------------------------------
#
# OBSERVED regression: the combined Entra ID form can transform, after the
# single combined submit (email + password + Sign in), into a PASSWORD-ONLY
# surface (email input gone; password input and Sign-in button uniquely
# present). The SAME submit_operator_signin call MUST NOT return on the first
# submit: it must re-fill the password, click Sign in once more, and accept
# success only when the password surface transitions away stably. If the
# password-only tail never transitions, it MUST fail closed with
# PolicyDenied / WorkerUnavailable.
#
# The current production returns immediately after the single combined submit,
# so both tests are RED until the tail continuation is implemented.


class _PhasePage(_FakePage):
    """Fake auth page whose fixed-id counts mutate by phase.

    ``locator(id).count()`` drives combined-form detection and any
    transition verification. ``locator(id).fill`` / ``.click`` record tail
    actions ONLY (the combined submit is a monkeypatched fake that records to
    its own call list), so ``actions`` captures exactly what submit_operator_
    signin does on the page after the combined submit.
    """

    def __init__(self, counts: dict[str, int]) -> None:
        self.url = "https://login.microsoftonline.com/"
        self._counts = dict(counts)
        self.actions: list[tuple] = []

    def locator(self, sel: str) -> _PhaseLocator:
        key = sel.lstrip("#")
        return _PhaseLocator(self, key)


class _PhaseLocator:
    def __init__(self, page: _PhasePage, key: str) -> None:
        self._page = page
        self._key = key

    async def count(self) -> int:
        return self._page._counts.get(self._key, 0)

    async def fill(self, value: str) -> None:
        self._page.actions.append(("fill", self._key, value))

    async def click(self, *, timeout: int | None = None) -> None:
        self._page.actions.append(("click", self._key))


def _combined_present_counts() -> dict[str, int]:
    return {
        COMBINED_FORM_EMAIL_ID: 1,
        COMBINED_FORM_PASSWORD_ID: 1,
        COMBINED_FORM_SUBMIT_ID: 1,
    }


class _CombinedTailScenario:
    """Real submit_operator_signin with fakes; combined submit swapped in."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, advance) -> None:
        self.actions: list[tuple] = []
        self.resolver = _Resolver(self.actions)
        self.combined_calls: list[dict] = []

        plans = {key: _plan_for(key) for key in PROGRESSION_KEYS}

        def _locator_plan(name: str) -> LocatorPlan | None:
            return plans.get(name)

        async def _detect(page):  # noqa: ANN001
            return True

        async def _submit(page, signin):  # noqa: ANN001
            self.combined_calls.append(
                {"email": signin.email, "password": signin.password}
            )
            advance()

        monkeypatch.setattr(browser_module, "common_auth_attested", lambda: True)
        monkeypatch.setattr(browser_module, "common_auth_locator_plan", _locator_plan)
        monkeypatch.setattr(browser_module, "resolve_visible_locator", self.resolver)
        monkeypatch.setattr(browser_module, "detect_combined_signin_form", _detect)
        monkeypatch.setattr(browser_module, "submit_combined_signin_form", _submit)

        self.page = _PhasePage(_combined_present_counts())
        self.browser = PersistentBrowser(
            config=BrowserConfig(
                profile_dir=Path("/tmp/wt-m365-fake-profile"),  # noqa: S108
                headless=True,
                mode="live",
            )
        )
        self.browser._playwright = object()
        self.browser._context = _FakeContext([self.page])
        self.browser.is_dedicated_persistent_profile = lambda: True  # type: ignore[method-assign]
        self.browser._signin_surface_resolved = True  # type: ignore[attr-defined]
        self.browser.auth_origin_approved = lambda: True  # type: ignore[method-assign]

    async def run(self) -> None:
        signin = OperatorSignInInput(email=FAKE_EMAIL, password=FAKE_PASSWORD)
        await self.browser.submit_operator_signin(signin)


async def test_combined_submit_continues_password_only_tail_before_success(
    monkeypatch,
) -> None:
    # Combined submit lands; the page becomes password-only (email gone,
    # password + signin uniquely present).
    def _advance() -> None:
        counts = _combined_present_counts()
        counts[COMBINED_FORM_EMAIL_ID] = 0
        monkeypatch_scenario.page._counts = counts

    scenario = _CombinedTailScenario(monkeypatch, advance=_advance)
    monkeypatch_scenario = scenario  # exposed for the closure above

    # Model the REAL transition: the tail Sign-in click makes the password
    # surface permanently absent, so the stable-transition helper observes
    # permanent absence (counts 0) on every subsequent sample.
    page = scenario.page
    _base_locator = page.locator

    def _locator(sel: str):  # noqa: ANN202
        loc = _base_locator(sel)
        if sel.lstrip("#") == COMBINED_FORM_SUBMIT_ID:
            _orig_click = loc.click

            async def _click(*, timeout: int | None = None) -> None:
                await _orig_click(timeout=timeout)
                page._counts = {
                    COMBINED_FORM_EMAIL_ID: 0,
                    COMBINED_FORM_PASSWORD_ID: 0,
                    COMBINED_FORM_SUBMIT_ID: 0,
                }

            loc.click = _click  # type: ignore[method-assign]
        return loc

    page.locator = _locator  # type: ignore[method-assign]

    await scenario.run()

    # The combined submit fired exactly once with the memory-only values.
    assert scenario.combined_calls == [
        {"email": FAKE_EMAIL, "password": FAKE_PASSWORD}
    ]
    # The SAME call must NOT have returned: it re-filled the password on the
    # password-only tail and clicked Sign in once more before accepting success.
    tail_fills = [
        a
        for a in scenario.page.actions
        if a[0] == "fill" and a[1] == COMBINED_FORM_PASSWORD_ID
    ]
    tail_clicks = [
        a
        for a in scenario.page.actions
        if a[0] == "click" and a[1] == COMBINED_FORM_SUBMIT_ID
    ]
    assert tail_fills, "password-only tail must re-fill the password"
    assert tail_fills[-1] == ("fill", COMBINED_FORM_PASSWORD_ID, FAKE_PASSWORD)
    assert tail_clicks, "password-only tail must click Sign in once more"
    assert tail_clicks[-1] == ("click", COMBINED_FORM_SUBMIT_ID)
    # The tail Sign in click is the final action (not an early return).
    assert scenario.page.actions[-1] == ("click", COMBINED_FORM_SUBMIT_ID)


async def test_combined_submit_fails_closed_if_password_only_tail_does_not_transition(
    monkeypatch,
) -> None:
    # Combined submit lands password-only; the second Sign in still leaves the
    # password surface present (no stable transition).
    def _advance() -> None:
        counts = _combined_present_counts()
        counts[COMBINED_FORM_EMAIL_ID] = 0
        monkeypatch_scenario.page._counts = counts

    scenario = _CombinedTailScenario(monkeypatch, advance=_advance)
    monkeypatch_scenario = scenario  # exposed for the closure above

    with pytest.raises((PolicyDenied, WorkerUnavailable)):
        await scenario.run()

    # The combined submit did land (password-only), but the tail stall must
    # fail closed rather than report success.
    assert scenario.combined_calls == [
        {"email": FAKE_EMAIL, "password": FAKE_PASSWORD}
    ]


# ------------------------------------------------------------------------------
# 4: detect_combined_signin_form is structural/closed
# ------------------------------------------------------------------------------


class _CountingLocator:
    def __init__(self, n: int) -> None:
        self._n = n

    async def count(self) -> int:
        return self._n


class _IdPage:
    def __init__(self, *, email: int, password: int, submit: int) -> None:
        self._counts = {
            COMBINED_FORM_EMAIL_ID: email,
            COMBINED_FORM_PASSWORD_ID: password,
            COMBINED_FORM_SUBMIT_ID: submit,
        }

    def locator(self, sel: str) -> _CountingLocator:
        key = sel.lstrip("#")
        return _CountingLocator(self._counts.get(key, 0))


@pytest.mark.parametrize(
    "email,password,submit,expected",
    [
        (1, 1, 1, True),
        (0, 1, 1, False),
        (1, 0, 1, False),
        (1, 1, 0, False),
        (2, 1, 1, False),
        (1, 2, 1, False),
        (1, 1, 2, False),
    ],
)
async def test_detect_combined_form_structure(email, password, submit, expected) -> None:
    page = _IdPage(email=email, password=password, submit=submit)
    assert await detect_combined_signin_form(page) is expected


async def test_detect_combined_form_error_returns_false() -> None:
    class _BrokenPage:
        def locator(self, sel: str):  # noqa: ANN001
            raise RuntimeError("no locator primitive")

    assert await detect_combined_signin_form(_BrokenPage()) is False


# ------------------------------------------------------------------------------
# 5: submit_combined_signin_form fills + clicks exactly once, in order
# ------------------------------------------------------------------------------


class _CmdLocator:
    def __init__(self, actions: list[tuple]) -> None:
        self._actions = actions

    async def fill(self, value: str) -> None:
        self._actions.append(("fill", value))

    async def click(self, *, timeout: int | None = None) -> None:
        self._actions.append(("click",))


class _CmdPage:
    def __init__(self, actions: list[tuple]) -> None:
        self._actions = actions
        self._by_id: dict[str, _CmdLocator] = {}

    def locator(self, sel: str) -> _CmdLocator:
        key = sel.lstrip("#")
        if key not in self._by_id:
            self._by_id[key] = _CmdLocator(self._actions)
        return self._by_id[key]


async def test_submit_combined_form_fills_and_clicks_in_order() -> None:
    actions: list[tuple] = []
    page = _CmdPage(actions)
    signin = OperatorSignInInput(email=FAKE_EMAIL, password=FAKE_PASSWORD)

    await submit_combined_signin_form(page, signin)

    assert actions == [
        ("fill", FAKE_EMAIL),
        ("fill", FAKE_PASSWORD),
        ("click",),
    ]
    # Exactly the three fixed ids were addressed.
    assert set(page._by_id.keys()) == {
        COMBINED_FORM_EMAIL_ID,
        COMBINED_FORM_PASSWORD_ID,
        COMBINED_FORM_SUBMIT_ID,
    }


async def _always_true(page):  # noqa: ANN001
    return True


async def _always_false(page):  # noqa: ANN001
    return False
