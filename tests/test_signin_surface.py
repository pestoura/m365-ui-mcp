"""Bounded, value-free classification + deterministic resolver for the
intermediate Microsoft Entra ID sign-in surface (AUTH-109).

Covers, explicitly:

* the classifier maps a bounded body-text reading to a CLOSED surface kind
  only; it never retains or returns URLs, DOM, page text, account identifiers,
  UPNs or tenant ids;
* the fixed pre-email intermediate surfaces (account chooser / use-another-
  account prompt) are recognized as forwardable to the email-entry surface;
* the resolver forces the email-entry surface ONLY via the fixed
  "use another account" action (never selecting a cached identity);
* any non-deterministic surface (pick-an-account, stay-signed-in, consent,
  method selection, error, ambiguous, unknown) fails closed and never clicks;
* the closed label set is the ONLY thing the resolver may click.
"""

from __future__ import annotations

from m365_browser_worker.bootstrap_discovery import DiscoveryResultKind
from m365_browser_worker.signin_surface import (
    USE_ANOTHER_ACCOUNT_LABELS,
    SigninSurfaceKind,
    classify_signin_surface,
    click_use_another_account,
    diagnose_signin_surface,
    resolve_signin_surface_to_email_entry,
)


def test_classify_email_entry() -> None:
    c = classify_signin_surface("Sign in\nEmail or phone\nNext")
    assert c.kind is SigninSurfaceKind.EMAIL_ENTRY
    assert c.email_entry_present is True


def test_classify_email_entry_portuguese() -> None:
    c = classify_signin_surface("Iniciar sessão\nEmail, telemóvel ou Skype\nAvançar")
    assert c.kind is SigninSurfaceKind.EMAIL_ENTRY


def test_classify_use_another_account_english() -> None:
    c = classify_signin_surface("Pick an account\nUse another account\nwork or school")
    assert c.kind in (
        SigninSurfaceKind.USE_ANOTHER_ACCOUNT_PROMPT,
        SigninSurfaceKind.ACCOUNT_CHOOSER,
    )
    assert c.email_entry_present is False


def test_classify_use_another_account_portuguese() -> None:
    c = classify_signin_surface("Selecionar uma conta\nUtilizar outra conta")
    assert c.kind in (
        SigninSurfaceKind.USE_ANOTHER_ACCOUNT_PROMPT,
        SigninSurfaceKind.ACCOUNT_CHOOSER,
    )


def test_classify_error_surface() -> None:
    c = classify_signin_surface("Something went wrong\nWe couldn't find your account")
    assert c.kind is SigninSurfaceKind.ERROR


def test_classify_consent_is_not_forwardable() -> None:
    c = classify_signin_surface("Accept\nPermissions requested by this app")
    assert c.kind is SigninSurfaceKind.CONSENT


def test_classify_stay_signed_in_is_not_forwardable() -> None:
    c = classify_signin_surface("Stay signed in\nYes\nNo")
    assert c.kind is SigninSurfaceKind.STAY_SIGNED_IN


def test_classify_method_selection_is_not_forwardable() -> None:
    c = classify_signin_surface("Sign-in options\nChoose how to verify")
    assert c.kind is SigninSurfaceKind.METHOD_SELECTION


def test_classify_empty_is_unknown() -> None:
    assert classify_signin_surface("").kind is SigninSurfaceKind.UNKNOWN
    assert classify_signin_surface("   ").kind is SigninSurfaceKind.UNKNOWN


def test_classify_unknown_microsoft_surface_is_ambiguous() -> None:
    # Looks like a Microsoft surface but no fixed marker matched.
    c = classify_signin_surface("Microsoft\nContinue\nCancel")
    assert c.kind is SigninSurfaceKind.AMBIGUOUS


class _FakeRoleLocator:
    def __init__(self, count: int, *, click_raises: bool = False) -> None:
        self._count = count
        self.clicks = 0
        self.click_raises = click_raises

    async def count(self) -> int:
        return self._count

    async def click(self, timeout: int = 5000) -> None:
        if self.click_raises:
            raise AssertionError("boom")
        self.clicks += 1


class _FakeLabelLocator:
    def __init__(self, present: bool) -> None:
        self._present = present
        self.first = _FakeRoleLocator(1 if present else 0)

    async def count(self) -> int:
        return 1 if self._present else 0


class _FakePage:
    def __init__(self, present: bool = True) -> None:
        self._present = present

    def get_by_role(self, role: str, name: str) -> _FakeLabelLocator:
        # Only the first CLOSED label is present; everything else absent.
        visible = self._present and name == USE_ANOTHER_ACCOUNT_LABELS[0]
        return _FakeLabelLocator(present=visible)


async def test_click_use_another_account_clicks_fixed_label() -> None:
    page = _FakePage(present=True)
    clicked = await click_use_another_account(page)
    assert clicked is True


async def test_click_use_another_account_absent_fails_closed() -> None:
    page = _FakePage(present=False)
    clicked = await click_use_another_account(page)
    assert clicked is False


class _RecordingPage:
    def __init__(self, readings: list[str], *, fixed_control: bool = True) -> None:
        self._readings = list(readings)
        self._idx = 0
        self._fixed_control = fixed_control
        self.clicks = 0

    def get_by_role(self, role: str, name: str) -> _FakeLabelLocator:
        visible = self._fixed_control and name == USE_ANOTHER_ACCOUNT_LABELS[0]
        return _FakeLabelLocator(present=visible)

    async def read_text(self) -> str:
        text = self._readings[min(self._idx, len(self._readings) - 1)]
        self._idx += 1
        return text


async def test_resolver_already_email_entry_no_action() -> None:
    page = _RecordingPage(["Sign in\nEmail or phone"])
    res = await resolve_signin_surface_to_email_entry(page, page.read_text)
    assert res.kind is SigninSurfaceKind.EMAIL_ENTRY
    assert res.advanced is False


async def test_resolver_forwardable_then_email_entry() -> None:
    page = _RecordingPage(
        [
            "Pick an account\nUse another account",
            "Sign in\nEmail or phone",
        ]
    )
    res = await resolve_signin_surface_to_email_entry(page, page.read_text)
    assert res.kind is SigninSurfaceKind.EMAIL_ENTRY
    assert res.advanced is True


async def test_resolver_forwardable_but_control_absent_fails_closed() -> None:
    page = _RecordingPage(["Pick an account\nUse another account"], fixed_control=False)
    res = await resolve_signin_surface_to_email_entry(page, page.read_text)
    # No fixed control found -> fail-closed to AMBIGUOUS, never guess.
    assert res.kind is SigninSurfaceKind.AMBIGUOUS
    assert res.advanced is False


async def test_resolver_non_deterministic_fails_closed() -> None:
    page = _RecordingPage(["Stay signed in\nYes\nNo"])
    res = await resolve_signin_surface_to_email_entry(page, page.read_text)
    # Non-forwardable surface: fail closed without clicking anything.
    assert res.kind is SigninSurfaceKind.AMBIGUOUS
    assert res.advanced is False
    # Observability-only: terminal surface reports the sanitized closed enum of
    # the non-forwardable kind actually encountered (no click, no identity).
    assert res.terminal_surface is SigninSurfaceKind.STAY_SIGNED_IN


async def test_resolver_error_fails_closed() -> None:
    page = _RecordingPage(["Something went wrong"])
    res = await resolve_signin_surface_to_email_entry(page, page.read_text)
    assert res.kind is SigninSurfaceKind.AMBIGUOUS
    assert res.advanced is False
    assert res.terminal_surface is SigninSurfaceKind.ERROR


async def test_resolver_forwardable_then_non_email_terminal_surface() -> None:
    # Click is allowed (CLOSED transition) but the post-forward surface is NOT
    # email-entry (e.g. consent), so the external kind stays AMBIGUOUS (fail
    # closed) while terminal_surface reports the sanitized post-forward enum.
    page = _RecordingPage(
        [
            "Pick an account\nUse another account",
            "Accept\nPermissions requested by this app",
        ]
    )
    res = await resolve_signin_surface_to_email_entry(page, page.read_text)
    assert res.kind is SigninSurfaceKind.AMBIGUOUS
    assert res.advanced is True
    assert res.terminal_surface is SigninSurfaceKind.CONSENT


async def test_resolver_forwardable_control_absent_terminal_surface() -> None:
    page = _RecordingPage(["Pick an account\nUse another account"], fixed_control=False)
    res = await resolve_signin_surface_to_email_entry(page, page.read_text)
    # No fixed control found -> fail-closed to AMBIGUOUS, never guess.
    assert res.kind is SigninSurfaceKind.AMBIGUOUS
    assert res.advanced is False
    # Terminal surface is still the initial forwardable intermediate.
    assert res.terminal_surface in (
        SigninSurfaceKind.ACCOUNT_CHOOSER,
        SigninSurfaceKind.USE_ANOTHER_ACCOUNT_PROMPT,
    )


class _ReadOnlyPage:
    """A fake page that records whether any click was attempted."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.clicks = 0

    def get_by_role(self, role: str, name: str) -> _FakeLabelLocator:
        # Any locator access would indicate a mutation attempt; surface it.
        raise AssertionError("diagnose must not query controls")

    async def read_text(self) -> str:
        return self._text


async def test_diagnose_is_read_only_and_returns_kind() -> None:
    page = _ReadOnlyPage("Pick an account\nUse another account")
    classification = await diagnose_signin_surface(page, page.read_text)
    assert classification.kind in (
        SigninSurfaceKind.USE_ANOTHER_ACCOUNT_PROMPT,
        SigninSurfaceKind.ACCOUNT_CHOOSER,
    )
    assert classification.email_entry_present is False
    # No control was queried/clicked; diagnosis is purely a bounded read.
    assert page.clicks == 0


async def test_diagnose_email_entry_reports_terminal_surface() -> None:
    page = _ReadOnlyPage("Sign in\nEmail or phone")
    classification = await diagnose_signin_surface(page, page.read_text)
    assert classification.kind is SigninSurfaceKind.EMAIL_ENTRY
    assert classification.email_entry_present is True


async def test_diagnose_unknown_on_empty_reading() -> None:
    page = _ReadOnlyPage("")
    classification = await diagnose_signin_surface(page, page.read_text)
    assert classification.kind is SigninSurfaceKind.UNKNOWN
    assert classification.email_entry_present is False


# -------------------------------------------------------------------------
# AUTH-109 hardening: structural email-entry control presence WINS over a
# text-only ACCOUNT_CHOOSER marker, so no unnecessary chooser click is attempted.
# Ambiguous/multiple controls and detection failures fail closed (no click).
# -------------------------------------------------------------------------


class _FakeKeyDiscovery:
    def __init__(self, result: DiscoveryResultKind) -> None:
        self.result = result


class _StatePage:
    """A fake page for ``detect_email_entry_state`` whose locator counts are
    injected directly (no real UI contract fragment required)."""

    def __init__(self, *, email: str = "NO_MATCH", nxt: str = "NO_MATCH") -> None:
        self._email = email
        self._nxt = nxt
        self.queries = 0

    def get_by_role(self, role: str, name: str):  # pragma: no cover
        raise AssertionError("detect_email_entry_state must not use get_by_role")

    async def read_text(self) -> str:  # pragma: no cover
        raise AssertionError("detect_email_entry_state must not read text")


async def _install_state_double(monkeypatch, email: str, nxt: str) -> None:
    """Patch the worker-local discovery primitives so ``detect_email_entry_state``
    returns a controlled outcome without real UI contract fragments."""
    from m365_browser_worker.bootstrap_discovery import DiscoveryResultKind

    _map = {
        "UNIQUE_MATCH": DiscoveryResultKind.UNIQUE_MATCH,
        "NO_MATCH": DiscoveryResultKind.NO_MATCH,
        "AMBIGUOUS": DiscoveryResultKind.AMBIGUOUS,
    }

    async def _fake_discover_key(page, selector_key: str):
        if selector_key == "auth.login_email_input":
            return _FakeKeyDiscovery(_map[email])
        if selector_key == "auth.login_next_button":
            return _FakeKeyDiscovery(_map[nxt])
        raise AssertionError(f"unexpected selector key: {selector_key}")

    # ``build_locator`` is imported inside discover_key; stub it so no real
    # locator plan resolution is required.
    class _FakeLocator:
        async def count(self) -> int:
            return 0

    def _fake_build_locator(page, candidate):  # noqa: ANN001
        return _FakeLocator()

    import m365_browser_worker.bootstrap_discovery as bd

    monkeypatch.setattr(bd, "discover_key", _fake_discover_key)
    monkeypatch.setattr(bd, "build_locator", _fake_build_locator)


async def test_structural_email_entry_wins_over_text_account_chooser(
    monkeypatch,
) -> None:
    # Page text says ACCOUNT_CHOOSER but the email control pair is uniquely
    # present structurally -> EMAIL_ENTRY, no chooser click.
    page = _StatePage(email="UNIQUE_MATCH", nxt="UNIQUE_MATCH")
    await _install_state_double(monkeypatch, "UNIQUE_MATCH", "UNIQUE_MATCH")
    classification = await diagnose_signin_surface(
        page, lambda: _coro("work or school\nUse another account")
    )
    assert classification.kind is SigninSurfaceKind.EMAIL_ENTRY


async def test_structural_email_entry_not_present_still_chooser(
    monkeypatch,
) -> None:
    # No structural email control: text ACCOUNT_CHOOSER still classifies as the
    # forwardable intermediate (controls the click path unchanged).
    page = _StatePage(email="NO_MATCH", nxt="NO_MATCH")
    await _install_state_double(monkeypatch, "NO_MATCH", "NO_MATCH")
    classification = await diagnose_signin_surface(
        page, lambda: _coro("work or school\nUse another account")
    )
    assert classification.kind is SigninSurfaceKind.ACCOUNT_CHOOSER


async def test_structural_ambiguous_email_fails_closed(monkeypatch) -> None:
    # Multiple email controls detected: NOT a signal; resolver must fail closed.
    page = _StatePage(email="AMBIGUOUS", nxt="UNIQUE_MATCH")
    await _install_state_double(monkeypatch, "AMBIGUOUS", "UNIQUE_MATCH")
    resolution = await resolve_signin_surface_to_email_entry(
        page, lambda: _coro("work or school\nUse another account")
    )
    assert resolution.kind is SigninSurfaceKind.AMBIGUOUS
    assert resolution.advanced is False


async def test_classifier_prefers_structural_state_arg() -> None:
    from m365_browser_worker.signin_surface import EmailEntryState

    c = classify_signin_surface(
        "work or school\nUse another account",
        email_entry_state=EmailEntryState(
            email_input_present=True, next_button_present=True
        ),
    )
    assert c.kind is SigninSurfaceKind.EMAIL_ENTRY
    assert c.email_entry_present is True


async def test_classifier_structural_state_ambiguity_not_a_signal() -> None:
    from m365_browser_worker.signin_surface import EmailEntryState

    c = classify_signin_surface(
        "work or school\nUse another account",
        email_entry_state=EmailEntryState(
            email_input_present=True, next_button_present=True, ambiguous=True
        ),
    )
    # Ambiguous structural result must NOT force EMAIL_ENTRY.
    assert c.kind is SigninSurfaceKind.ACCOUNT_CHOOSER


async def test_classifier_error_still_wins_over_structural_email() -> None:
    from m365_browser_worker.signin_surface import EmailEntryState

    c = classify_signin_surface(
        "Something went wrong\nWe couldn't find your account",
        email_entry_state=EmailEntryState(
            email_input_present=True, next_button_present=True
        ),
    )
    assert c.kind is SigninSurfaceKind.ERROR


async def test_classifier_structural_state_none_is_text_only() -> None:
    # Backwards-compatible call without the structural argument.
    assert classify_signin_surface("work or school").kind is (
        SigninSurfaceKind.ACCOUNT_CHOOSER
    )


def _coro(value: str):  # type: ignore[no-untyped-def]
    async def _inner() -> str:
        return value

    return _inner()
