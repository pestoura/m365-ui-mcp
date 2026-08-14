"""Tests for the reusable worker locator runtime.

Uses lightweight fakes for the Playwright ``Page`` and locator objects so the
resolution algorithm (strategy mapping, ordering/fallback, ambiguity fail-closed,
all-no-match fail-closed, bounded wait) is exercised without a browser, network,
or credentials.
"""

from __future__ import annotations

import pytest

from m365_browser_worker.locator_runtime import (
    LocatorRuntimeError,
    ResolvedLocator,
    build_locator,
    resolve_visible_locator,
)
from m365_mcp.locators import LocatorCandidate, LocatorPlan, LocatorStrategy

EVIDENCE = "sha256:" + "a" * 64

ROLE = LocatorStrategy.ROLE
LABEL = LocatorStrategy.LABEL
PLACEHOLDER = LocatorStrategy.PLACEHOLDER
TEST_ID = LocatorStrategy.TEST_ID
CSS = LocatorStrategy.CSS


class FakeLocator:
    """Minimal structural stand-in for a Playwright locator."""

    def __init__(
        self,
        *,
        wait_timeout: bool = False,
        count: int = 1,
    ) -> None:
        self._wait_timeout = wait_timeout
        self._count = count
        self.wait_calls: list[tuple[str, int | None]] = []
        self.count_calls = 0

    @property
    def first(self) -> FakeLocator:
        return self

    def wait_for(self, *, state: str = "visible", timeout: int | None = None) -> None:
        self.wait_calls.append((state, timeout))
        if self._wait_timeout:
            # Mimics a Playwright bounded-wait TimeoutError.
            raise TimeoutError("locator did not become visible within timeout")

    def count(self) -> int:
        self.count_calls += 1
        return self._count


class FakePage:
    """Minimal structural stand-in for a Playwright page.

    ``behaviors`` maps ``(strategy_value, value, name)`` to a ``FakeLocator`` or a
    zero-arg factory so each candidate can be configured independently.
    """

    def __init__(self, behaviors: dict[tuple[str, str, str | None], FakeLocator]) -> None:
        self._behaviors = behaviors
        self.calls: list[tuple[str, str, str | None]] = []

    def _resolve(self, strategy: str, value: str, name: str | None) -> FakeLocator:
        key = (strategy, value, name)
        item = self._behaviors.get(key)
        if item is None:
            return FakeLocator(count=1)
        return item() if callable(item) else item

    def get_by_role(self, role: str, *, name: str | None = None) -> FakeLocator:
        self.calls.append(("role", role, name))
        return self._resolve("role", role, name)

    def get_by_label(self, label: str) -> FakeLocator:
        self.calls.append(("label", label, None))
        return self._resolve("label", label, None)

    def get_by_placeholder(self, placeholder: str) -> FakeLocator:
        self.calls.append(("placeholder", placeholder, None))
        return self._resolve("placeholder", placeholder, None)

    def get_by_test_id(self, test_id: str) -> FakeLocator:
        self.calls.append(("test_id", test_id, None))
        return self._resolve("test_id", test_id, None)

    def locator(self, selector: str) -> FakeLocator:
        self.calls.append(("css", selector, None))
        return self._resolve("css", selector, None)


def _candidate(
    strategy: LocatorStrategy,
    value: str,
    *,
    name: str | None = None,
) -> LocatorCandidate:
    if strategy in (TEST_ID, CSS):
        return LocatorCandidate(strategy, value, evidence_digest=EVIDENCE)
    return LocatorCandidate(strategy, value, name=name)


def _plan(selector_key: str, *candidates: LocatorCandidate) -> LocatorPlan:
    return LocatorPlan(selector_key=selector_key, candidates=candidates)


# --- strategy mapping ---------------------------------------------------------


@pytest.mark.parametrize(
    ("strategy", "method", "value", "name"),
    [
        (ROLE, "role", "button", "Sign in"),
        (LABEL, "label", "Email", None),
        (PLACEHOLDER, "placeholder", "you@example.com", None),
        (TEST_ID, "test_id", "submit-btn", None),
        (CSS, "css", "[data-signin]", None),
    ],
)
async def test_all_strategies_map_to_exact_page_accessor(
    strategy: LocatorStrategy,
    method: str,
    value: str,
    name: str | None,
) -> None:
    page = FakePage({(strategy.value, value, name): FakeLocator(count=1)})
    plan = _plan("signin.submit", _candidate(strategy, value, name=name))

    result = await resolve_visible_locator(page, plan)

    assert isinstance(result, ResolvedLocator)
    assert result.candidate.strategy is strategy
    assert result.candidate.value == value
    # Exactly the mapped accessor was invoked, with the right arguments.
    assert page.calls == [(method, value, name)]


def test_build_locator_matches_each_strategy_exactly() -> None:
    page = FakePage({})
    role_candidate = _candidate(ROLE, "link", name="Home")
    assert build_locator(page, role_candidate) is not None
    assert page.calls == [("role", "link", "Home")]

    label_candidate = _candidate(LABEL, "Password")
    assert build_locator(page, label_candidate) is not None
    assert page.calls[-1] == ("label", "Password", None)


# --- ordering / fallback ------------------------------------------------------


async def test_primary_accessible_candidate_is_used_before_fallback() -> None:
    css_locator = FakeLocator(count=1)
    page = FakePage(
        {
            (ROLE.value, "textbox", "Email"): FakeLocator(count=1),
            (CSS.value, "[data-email]", None): css_locator,
        }
    )
    plan = _plan(
        "auth.email",
        _candidate(ROLE, "textbox", name="Email"),
        _candidate(CSS, "[data-email]"),
    )

    result = await resolve_visible_locator(page, plan)

    assert result.candidate.strategy is ROLE
    # The fallback accessor must not be consulted when the primary resolves.
    assert all(call[0] != "css" for call in page.calls)


async def test_fallback_candidate_used_only_after_primary_times_out() -> None:
    page = FakePage(
        {
            (ROLE.value, "textbox", "Email"): FakeLocator(wait_timeout=True),
            (CSS.value, "[data-email]", None): FakeLocator(count=1),
        }
    )
    plan = _plan(
        "auth.email",
        _candidate(ROLE, "textbox", name="Email"),
        _candidate(CSS, "[data-email]"),
    )

    result = await resolve_visible_locator(page, plan)

    assert result.candidate.strategy is CSS


async def test_visible_zero_count_falls_through_to_next_candidate() -> None:
    # wait_for succeeds but the count is 0: the spec allows proceeding to the next
    # candidate in this state.
    page = FakePage(
        {
            (LABEL.value, "Email", None): FakeLocator(wait_timeout=False, count=0),
            (PLACEHOLDER.value, "you@example.com", None): FakeLocator(count=1),
        }
    )
    plan = _plan(
        "auth.email",
        _candidate(LABEL, "Email"),
        _candidate(PLACEHOLDER, "you@example.com"),
    )

    result = await resolve_visible_locator(page, plan)

    assert result.candidate.strategy is PLACEHOLDER


# --- ambiguity fail-closed ----------------------------------------------------


async def test_ambiguous_match_fails_closed_immediately() -> None:
    page = FakePage({(LABEL.value, "Email", None): FakeLocator(count=2)})
    plan = _plan("auth.email", _candidate(LABEL, "Email"))

    with pytest.raises(LocatorRuntimeError) as excinfo:
        await resolve_visible_locator(page, plan)

    err = excinfo.value
    assert err.selector_key == "auth.email"
    assert err.reason == "ambiguous match"
    # Sanitized: the candidate value must never leak into the message.
    assert "Email" not in str(err)


async def test_ambiguous_primary_does_not_consult_fallback() -> None:
    css_locator = FakeLocator(count=1)
    page = FakePage(
        {
            (LABEL.value, "Email", None): FakeLocator(count=3),
            (CSS.value, "[data-email]", None): css_locator,
        }
    )
    plan = _plan(
        "auth.email",
        _candidate(LABEL, "Email"),
        _candidate(CSS, "[data-email]"),
    )

    with pytest.raises(LocatorRuntimeError) as excinfo:
        await resolve_visible_locator(page, plan)

    assert excinfo.value.reason == "ambiguous match"
    # Fail closed immediately: the fallback accessor is never reached.
    assert all(call[0] != "css" for call in page.calls)


# --- all-no-match fail-closed -------------------------------------------------


async def test_all_candidates_exhausted_fails_closed() -> None:
    page = FakePage(
        {
            (ROLE.value, "textbox", "Email"): FakeLocator(wait_timeout=True),
            (CSS.value, "[data-email]", None): FakeLocator(wait_timeout=True),
        }
    )
    plan = _plan(
        "auth.email",
        _candidate(ROLE, "textbox", name="Email"),
        _candidate(CSS, "[data-email]"),
    )

    with pytest.raises(LocatorRuntimeError) as excinfo:
        await resolve_visible_locator(page, plan)

    err = excinfo.value
    assert err.selector_key == "auth.email"
    assert err.reason == "no visible match within timeout"
    assert "Email" not in str(err)


async def test_count_failure_mid_plan_fails_closed() -> None:
    page = FakePage(
        {
            (LABEL.value, "Email", None): FakeLocator(wait_timeout=False, count=0),
            (PLACEHOLDER.value, "you@example.com", None): FakeLocator(count=0),
        }
    )
    plan = _plan(
        "auth.email",
        _candidate(LABEL, "Email"),
        _candidate(PLACEHOLDER, "you@example.com"),
    )

    with pytest.raises(LocatorRuntimeError) as excinfo:
        await resolve_visible_locator(page, plan)

    assert excinfo.value.selector_key == "auth.email"


# --- bounded wait behavior ----------------------------------------------------


async def test_wait_for_is_called_with_explicit_timeout_ms() -> None:
    locator = FakeLocator(count=1)
    page = FakePage({(LABEL.value, "Email", None): locator})
    plan = _plan("auth.email", _candidate(LABEL, "Email"))

    await resolve_visible_locator(page, plan, timeout_ms=1_500)

    assert locator.wait_calls == [("visible", 1_500)]


async def test_wait_for_uses_default_timeout_when_unspecified() -> None:
    locator = FakeLocator(count=1)
    page = FakePage({(LABEL.value, "Email", None): locator})
    plan = _plan("auth.email", _candidate(LABEL, "Email"))

    await resolve_visible_locator(page, plan)

    assert locator.wait_calls == [("visible", 5_000)]


async def test_negative_timeout_fails_closed_before_any_page_call() -> None:
    page = FakePage({(LABEL.value, "Email", None): FakeLocator(count=1)})
    plan = _plan("auth.email", _candidate(LABEL, "Email"))

    with pytest.raises(LocatorRuntimeError) as excinfo:
        await resolve_visible_locator(page, plan, timeout_ms=-1)

    assert excinfo.value.reason == "negative timeout"
    assert page.calls == []
