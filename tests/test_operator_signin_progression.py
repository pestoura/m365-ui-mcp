"""Progression tests for PersistentBrowser.submit_operator_signin.

These exercise the REAL ``submit_operator_signin`` sequential flow with fakes
and module-scoped monkeypatches. No live browser, no network, no credentials,
no runtime.

The four progression plans (email -> next -> password -> sign in) are loaded
from a monkeypatched ``common_auth_locator_plan`` and resolved through a
recording fake of ``resolve_visible_locator``. ``common_auth_attested`` is
monkeypatched at module scope. Everything else is the production method.

Proven properties (requirements):

1. exact action order: email fill -> next click -> password fill -> signin click;
2. only the provided fake email/password are applied, never retained in browser
   state beyond the recorded fill call arguments;
3. no MFA selector/action is resolved or clicked;
4. if any plan is missing, fail closed before applying credentials;
5. if the resolver fails/ambiguous at a stage, the browser converts the error to
   a sanitized ``PolicyDenied`` carrying the ``selector_key`` and ``reason``;
6. after Next, if the auth origin is no longer approved, the password is never
   filled;
7. ``common_auth_attested`` false fails before resolving/applying anything;
8. the stage timeout constant is passed to the resolver for every stage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import m365_browser_worker.browser as browser_module
from m365_browser_worker.browser import (
    AUTH_OPERATOR_SUBMIT_OPERATION,
    OPERATOR_SIGNIN_STAGE_TIMEOUT_MS,
    BrowserConfig,
    PersistentBrowser,
)
from m365_browser_worker.locator_runtime import (
    LocatorRuntimeError,
    ResolvedLocator,
)
from m365_browser_worker.operator_signin import (
    EMAIL_SELECTOR_NAME,
    NEXT_SELECTOR_NAME,
    PASSWORD_SELECTOR_NAME,
    SIGNIN_SELECTOR_NAME,
    OperatorSignInInput,
)
from m365_mcp.locators import LocatorCandidate, LocatorPlan, LocatorStrategy
from planner_mcp.errors import PolicyDenied

PROGRESSION_KEYS = (
    EMAIL_SELECTOR_NAME,
    NEXT_SELECTOR_NAME,
    PASSWORD_SELECTOR_NAME,
    SIGNIN_SELECTOR_NAME,
)

# Selector names that MUST never be resolved or clicked by this flow. The
# Microsoft Authenticator approval stays exclusively human; the worker must not
# touch any MFA control.
MFA_SELECTOR_KEYS = {
    "auth.login_mfa_approval",
    "auth.login_approve_button",
    "auth.mfa_code_input",
    "auth.login_verify_button",
    "auth.login_stay_signed_in",
}

FAKE_EMAIL = "operator@example.com"
FAKE_PASSWORD = "Sup3rSecret!2026"  # noqa: S105 - fake test credential, never real

EVIDENCE = "sha256:" + "b" * 64


# ------------------------------------------------------------------------------
# Fakes
# ------------------------------------------------------------------------------


class _FakePage:
    def __init__(self, url: str = "about:blank") -> None:
        self.url = url


class _FakeContext:
    def __init__(self, pages: list[_FakePage] | None = None) -> None:
        self.pages = pages if pages is not None else []


class _RecordingLocator:
    """Stand-in for a resolved Playwright locator that records fill/click."""

    def __init__(self, selector_key: str, actions: list[tuple]) -> None:
        self.selector_key = selector_key
        self._actions = actions

    @property
    def first(self) -> _RecordingLocator:
        return self

    def wait_for(self, *, state: str = "visible", timeout: int | None = None) -> None:
        # The recording fake bypasses the real bounded wait; the production code
        # path still passes timeout_ms, which we assert separately.
        return None

    def count(self) -> int:
        return 1

    async def fill(self, value: str) -> None:
        self._actions.append(("fill", self.selector_key, value))

    async def click(self) -> None:
        self._actions.append(("click", self.selector_key))


class _Resolver:
    """Recording monkeypatch for ``resolve_visible_locator``.

    Records every call (selector_key, timeout_ms). Optionally raises a
    ``LocatorRuntimeError`` for configured selector keys to simulate a resolver
    failure/ambiguity at a given stage.
    """

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
    candidate = LocatorCandidate(
        LocatorStrategy.ROLE, "textbox", name="signin-field"
    )
    return LocatorPlan(selector_key=selector_key, candidates=(candidate,))


# ------------------------------------------------------------------------------
# Scenario factory
# ------------------------------------------------------------------------------


class _Scenario:
    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        attested: bool = True,
        missing_plan: str | None = None,
        resolver_raises: set[str] | None = None,
        origin_after_next_lost: bool = False,
    ) -> None:
        self.actions: list[tuple] = []
        self.resolver = _Resolver(self.actions, raise_for=resolver_raises)

        plans = {}
        for key in PROGRESSION_KEYS:
            plans[key] = None if key == missing_plan else _plan_for(key)

        def _locator_plan(name: str) -> LocatorPlan | None:
            return plans.get(name)

        monkeypatch.setattr(browser_module, "common_auth_attested", lambda: attested)
        monkeypatch.setattr(browser_module, "common_auth_locator_plan", _locator_plan)
        monkeypatch.setattr(browser_module, "resolve_visible_locator", self.resolver)

        self.browser = PersistentBrowser(
            config=BrowserConfig(
                profile_dir=Path("/tmp/wt-m365-fake-profile"),  # noqa: S108 - fake path only
                headless=True,
                mode="live",
            )
        )
        # `started` requires both handles; set them without a real browser.
        self.browser._playwright = object()
        self.browser._context = _FakeContext(
            [_FakePage(url="https://login.microsoftonline.com/")]
        )
        # The dedicated-profile gate is satisfied by the test profile.
        self.browser.is_dedicated_persistent_profile = lambda: True  # type: ignore[method-assign]
        # AUTH-112: the surface latch must be set for the existing progression
        # properties to hold (submit applies credentials only after the surface
        # is resolved to EMAIL_ENTRY). The latch is exercised directly by the
        # dedicated AUTH-112 tests below.
        self.browser._signin_surface_resolved = True  # type: ignore[attr-defined]

        if origin_after_next_lost:
            state = {"calls": 0}

            def _origin() -> bool:
                state["calls"] += 1
                # Approved for the gate (1st) and lost after the Next click (2nd).
                return state["calls"] <= 1

            self.browser.auth_origin_approved = _origin  # type: ignore[method-assign]
        else:
            self.browser.auth_origin_approved = lambda: True  # type: ignore[method-assign]

    async def run(self) -> None:
        signin = OperatorSignInInput(email=FAKE_EMAIL, password=FAKE_PASSWORD)
        await self.browser.submit_operator_signin(signin)


# ------------------------------------------------------------------------------
# 1 + 8: happy-path exact order and stage timeout constant
# ------------------------------------------------------------------------------


async def test_happy_path_action_order_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    scenario = _Scenario(monkeypatch)

    await scenario.run()

    assert scenario.actions == [
        ("fill", EMAIL_SELECTOR_NAME, FAKE_EMAIL),
        ("click", NEXT_SELECTOR_NAME),
        ("fill", PASSWORD_SELECTOR_NAME, FAKE_PASSWORD),
        ("click", SIGNIN_SELECTOR_NAME),
    ]
    # Every stage resolves with the production stage timeout constant.
    assert scenario.resolver.calls == [
        (EMAIL_SELECTOR_NAME, OPERATOR_SIGNIN_STAGE_TIMEOUT_MS),
        (NEXT_SELECTOR_NAME, OPERATOR_SIGNIN_STAGE_TIMEOUT_MS),
        (PASSWORD_SELECTOR_NAME, OPERATOR_SIGNIN_STAGE_TIMEOUT_MS),
        (SIGNIN_SELECTOR_NAME, OPERATOR_SIGNIN_STAGE_TIMEOUT_MS),
    ]
    assert OPERATOR_SIGNIN_STAGE_TIMEOUT_MS == 5_000


# ------------------------------------------------------------------------------
# 2: only the provided fake credentials are applied; nothing retained
# ------------------------------------------------------------------------------


async def test_only_fake_credentials_applied_and_not_retained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = _Scenario(monkeypatch)

    await scenario.run()

    fills = [a for a in scenario.actions if a[0] == "fill"]
    assert len(fills) == 2
    assert fills[0] == ("fill", EMAIL_SELECTOR_NAME, FAKE_EMAIL)
    assert fills[1] == ("fill", PASSWORD_SELECTOR_NAME, FAKE_PASSWORD)
    # No extra/foreign value is ever filled.
    for _op, _key, value in fills:
        assert value in (FAKE_EMAIL, FAKE_PASSWORD)

    # The credentials must not leak into the browser instance state.
    state_values = [str(v) for v in scenario.browser.__dict__.values()]
    assert FAKE_EMAIL not in state_values
    assert FAKE_PASSWORD not in state_values
    assert not hasattr(scenario.browser, "email")
    assert not hasattr(scenario.browser, "password")


# ------------------------------------------------------------------------------
# 3: no MFA selector is resolved or clicked
# ------------------------------------------------------------------------------


async def test_no_mfa_selector_resolved_or_clicked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = _Scenario(monkeypatch)

    await scenario.run()

    resolved_keys = {key for key, _ in scenario.resolver.calls}
    assert resolved_keys == set(PROGRESSION_KEYS)
    assert resolved_keys.isdisjoint(MFA_SELECTOR_KEYS)

    for action in scenario.actions:
        assert action[1] in PROGRESSION_KEYS
        assert action[1] not in MFA_SELECTOR_KEYS


# ------------------------------------------------------------------------------
# 4: a missing plan fails closed before any credential is applied
# ------------------------------------------------------------------------------


@pytest.mark.parametrize("missing_plan", list(PROGRESSION_KEYS))
async def test_missing_plan_fails_closed_before_credentials(
    monkeypatch: pytest.MonkeyPatch, missing_plan: str
) -> None:
    scenario = _Scenario(monkeypatch, missing_plan=missing_plan)

    with pytest.raises(PolicyDenied) as excinfo:
        await scenario.run()

    err = excinfo.value
    assert err.context.get("operation") == AUTH_OPERATOR_SUBMIT_OPERATION
    # No credential is applied and the resolver is never reached.
    assert scenario.actions == []
    assert scenario.resolver.calls == []
    assert "guess" in err.message.lower()


# ------------------------------------------------------------------------------
# 5: a resolver failure/ambiguity at a stage converts to sanitized PolicyDenied
# ------------------------------------------------------------------------------


@pytest.mark.parametrize("failing_stage", list(PROGRESSION_KEYS))
async def test_resolver_failure_converts_to_sanitized_policy_denied(
    monkeypatch: pytest.MonkeyPatch, failing_stage: str
) -> None:
    scenario = _Scenario(monkeypatch, resolver_raises={failing_stage})

    with pytest.raises(PolicyDenied) as excinfo:
        await scenario.run()

    err = excinfo.value
    assert err.context.get("operation") == AUTH_OPERATOR_SUBMIT_OPERATION
    assert err.context.get("selector_key") == failing_stage
    # Sanitized reason category is preserved; no candidate value/DOM leaks.
    assert err.context.get("reason") == "ambiguous match"
    # The selector_key is tracked in the sanitized error context (a key, not a
    # candidate value or DOM text).

    # The failing stage was attempted, then no further credential action ran.
    assert (failing_stage, OPERATOR_SIGNIN_STAGE_TIMEOUT_MS) in scenario.resolver.calls

    if failing_stage == EMAIL_SELECTOR_NAME:
        assert scenario.actions == []
    elif failing_stage == NEXT_SELECTOR_NAME:
        assert scenario.actions == [("fill", EMAIL_SELECTOR_NAME, FAKE_EMAIL)]
    elif failing_stage == PASSWORD_SELECTOR_NAME:
        assert scenario.actions == [
            ("fill", EMAIL_SELECTOR_NAME, FAKE_EMAIL),
            ("click", NEXT_SELECTOR_NAME),
        ]
    else:  # SIGNIN stage: password was filled, sign-in never clicked
        assert scenario.actions == [
            ("fill", EMAIL_SELECTOR_NAME, FAKE_EMAIL),
            ("click", NEXT_SELECTOR_NAME),
            ("fill", PASSWORD_SELECTOR_NAME, FAKE_PASSWORD),
        ]
    # In every case the password is never filled after the failing stage.
    password_fills = [
        a for a in scenario.actions if a[0] == "fill" and a[1] == PASSWORD_SELECTOR_NAME
    ]
    if failing_stage in (EMAIL_SELECTOR_NAME, NEXT_SELECTOR_NAME):
        assert password_fills == []
    # Sign-in click must never occur when a stage fails.
    assert all(a[1] != SIGNIN_SELECTOR_NAME for a in scenario.actions)


# ------------------------------------------------------------------------------
# 6: auth origin lost after Next -> password never filled
# ------------------------------------------------------------------------------


async def test_origin_lost_after_next_password_never_filled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = _Scenario(monkeypatch, origin_after_next_lost=True)

    with pytest.raises(PolicyDenied) as excinfo:
        await scenario.run()

    err = excinfo.value
    assert err.context.get("operation") == AUTH_OPERATOR_SUBMIT_OPERATION
    # Email was filled and Next clicked, but the password was never filled.
    assert scenario.actions == [
        ("fill", EMAIL_SELECTOR_NAME, FAKE_EMAIL),
        ("click", NEXT_SELECTOR_NAME),
    ]
    password_fills = [
        a for a in scenario.actions if a[1] == PASSWORD_SELECTOR_NAME
    ]
    assert password_fills == []
    assert SIGNIN_SELECTOR_NAME not in {a[1] for a in scenario.actions}


# ------------------------------------------------------------------------------
# 7: unattested common.auth fails before resolving/applying anything
# ------------------------------------------------------------------------------


async def test_unattested_common_auth_fails_before_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = _Scenario(monkeypatch, attested=False)

    with pytest.raises(PolicyDenied) as excinfo:
        await scenario.run()

    err = excinfo.value
    assert err.context.get("operation") == AUTH_OPERATOR_SUBMIT_OPERATION
    assert "attested" in err.message.lower()
    # Nothing was resolved or applied.
    assert scenario.resolver.calls == []
    assert scenario.actions == []
