"""Reusable worker locator runtime.

Consumes the closed semantic locator model from ``m365_mcp.locators`` and maps
validated candidates onto Playwright page locator primitives. The resolution is
fail-closed: it only ever returns when exactly one candidate is visible, fails
immediately on ambiguity, and falls through to the next candidate on timeout or
zero matches.

This module never runs ``page.evaluate``, never accepts caller-supplied selector
strings, and never surfaces DOM text or candidate values in error messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from m365_mcp.locators import LocatorCandidate, LocatorPlan, LocatorStrategy

_DEFAULT_TIMEOUT_MS = 5_000


class LocatorRuntimeError(Exception):
    """Fail-closed locator resolution error.

    Carries only the ``selector_key`` and a sanitized ``reason`` category. It must
    never include DOM text, selector strings, or candidate values in its message.
    """

    def __init__(self, selector_key: str, reason: str) -> None:
        self.selector_key = selector_key
        self.reason = reason
        super().__init__(f"locator resolution failed for {selector_key}")


class LocatorLike(Protocol):
    """Structural view of a Playwright locator used by the runtime."""

    @property
    def first(self) -> WaitableLocator: ...

    async def count(self) -> int: ...


class WaitableLocator(Protocol):
    """Structural view of a Playwright locator ready for ``wait_for``."""

    async def wait_for(self, *, state: str = "visible", timeout: int | None = None) -> None: ...


class PageLike(Protocol):
    """Structural view of the Playwright page primitives the runtime consumes."""

    def get_by_role(self, role: str, *, name: str | None = None) -> LocatorLike: ...

    def get_by_label(self, label: str) -> LocatorLike: ...

    def get_by_placeholder(self, placeholder: str) -> LocatorLike: ...

    def get_by_test_id(self, test_id: str) -> LocatorLike: ...

    def locator(self, selector: str) -> LocatorLike: ...


@dataclass(frozen=True)
class ResolvedLocator:
    """A single resolved candidate and its bound Playwright locator-like object."""

    candidate: LocatorCandidate
    locator: LocatorLike


def build_locator(page: PageLike, candidate: LocatorCandidate) -> LocatorLike:
    """Map one validated candidate onto the matching page locator primitive.

    The mapping is exact and closed: every strategy maps to exactly one Playwright
    accessor. No caller-supplied selector strings reach the page.
    """
    strategy = candidate.strategy
    if strategy is LocatorStrategy.ROLE:
        return page.get_by_role(candidate.value, name=candidate.name)
    if strategy is LocatorStrategy.LABEL:
        return page.get_by_label(candidate.value)
    if strategy is LocatorStrategy.PLACEHOLDER:
        return page.get_by_placeholder(candidate.value)
    if strategy is LocatorStrategy.TEST_ID:
        return page.get_by_test_id(candidate.value)
    # LocatorStrategy.CSS
    return page.locator(candidate.value)


async def resolve_visible_locator(
    page: PageLike,
    plan: LocatorPlan,
    *,
    timeout_ms: int = _DEFAULT_TIMEOUT_MS,
) -> ResolvedLocator:
    """Resolve exactly one visible locator for ``plan`` or fail closed.

    Walks ``plan.ordered_candidates()`` deterministically. For each candidate it
    waits boundedly for a visible element, then counts matches:

    * count == 1 -> return the resolved locator
    * count > 1  -> fail closed immediately (ambiguous match)
    * timeout / count == 0 -> proceed to the next candidate

    After every candidate is exhausted without a unique visible match, fail closed.
    """
    if timeout_ms < 0:
        raise LocatorRuntimeError(plan.selector_key, "negative timeout")

    last_reason = "no candidates"
    for candidate in plan.ordered_candidates():
        locator = build_locator(page, candidate)
        try:
            await locator.first.wait_for(state="visible", timeout=timeout_ms)
        except Exception:  # noqa: BLE001
            # Any bounded wait failure (including a Playwright timeout) means this
            # candidate is not provably visible; fall through to the next candidate.
            last_reason = "no visible match within timeout"
            continue
        try:
            count = await locator.count()
        except Exception:  # noqa: BLE001
            last_reason = "match count could not be determined"
            continue
        if count == 0:
            last_reason = "candidate matched no element"
            continue
        if count > 1:
            raise LocatorRuntimeError(plan.selector_key, "ambiguous match")
        return ResolvedLocator(candidate=candidate, locator=locator)

    raise LocatorRuntimeError(plan.selector_key, last_reason)


__all__ = [
    "LocatorLike",
    "LocatorRuntimeError",
    "PageLike",
    "ResolvedLocator",
    "build_locator",
    "resolve_visible_locator",
]
