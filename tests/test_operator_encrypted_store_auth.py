"""Security regression suite for the operator encrypted-store sign-in path.

Covers, explicitly (AUTH-099 / AUTH-100 / AUTH-101):

* the operator-only ``POST /auth/bootstrap/operator-submit`` route admits only
  SOCKET-level loopback peers; non-loopback/Docker-network peers get ``404`` and
  never reach the browser;
* proxy headers (X-Forwarded-For / X-Real-IP / Forwarded) cannot spoof loopback;
* only the closed ``{email, password}`` body is accepted; unknown/extra keys and
  missing keys are rejected with ``400`` and never reach ``submit_operator_signin``;
* the route applies ONLY the two ``common.auth`` sign-in selectors; no URL, generic
  DOM primitive, Graph surface or locator guessing is reachable;
* the route returns only ``{ok, auth_state}``; no email/password/URL/DOM/cookie/
  token/UPN/tenant value is ever echoed;
* the live state machine resolves ``MFA_REQUIRED`` / ``WAITING_FOR_MFA`` only on a
  uniquely readable number; an ambiguous number fails closed to ``UNKNOWN`` and
  emits no challenge;
* the notifier emits a sanitized closed payload with NO approval capability and NO
  secret material;
* the credential loader keeps values memory-only and never prints/exposes them
  (mocked subprocess).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from m365_browser_worker.locators import LocatorPlan
from m365_browser_worker.operator_signin import (
    EMAIL_SELECTOR_NAME,
    NEXT_SELECTOR_NAME,
    PASSWORD_SELECTOR_NAME,
    PROGRESSION_SELECTOR_KEYS,
    SIGNIN_SELECTOR_NAME,
    OperatorSignInInput,
    common_auth_locator_plan,
    ui_contract_selector_value,
    validate_signin_input,
)
from planner_browser_worker.app import create_app
from planner_browser_worker.auth_state_machine import advance_live_auth_state, classify_live
from planner_mcp.auth import AuthContext, AuthState, MfaChallenge
from planner_mcp.notifications.mfa import (
    MfaNotification,
    MfaNotificationResult,
    emit,
    sanitize_for_external_adapter,
)
from planner_mcp.worker_client import WorkerClient

ROOT = Path(__file__).resolve().parent.parent
OPERATOR_SUBMIT_PATH = "/auth/bootstrap/operator-submit"


def _load_operator_auth_login():
    """Robustly load the operator script by absolute path (CI-proof).

    The repository-root ``scripts`` namespace is not importable in every
    pytest environment (e.g. installed-package CI runs), so we load the module
    file directly via importlib instead of ``import scripts...``. This keeps
    production code, packaging semantics and runtime behavior unchanged.
    """
    script_path = ROOT / "scripts" / "operator_auth_login.py"
    spec = importlib.util.spec_from_file_location(
        "operator_auth_login", str(script_path)
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load operator_auth_login from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_OPERATOR_AUTH_LOGIN = _load_operator_auth_login()


# --------------------------------------------------------------------------
# Browser test doubles
# --------------------------------------------------------------------------


class _FakePage:
    def __init__(self, url: str = "about:blank") -> None:
        self.url = url
        self.fill_calls: list[tuple[str, str]] = []

    async def fill(self, selector: str, value: str) -> None:
        self.fill_calls.append((selector, value))


class _FakeContext:
    def __init__(self, pages: list[_FakePage] | None = None) -> None:
        self.pages = pages if pages is not None else []

    async def new_page(self) -> _FakePage:
        page = _FakePage()
        self.pages.append(page)
        return page


class _OperatorSubmitBrowser:
    """Duck-typed PersistentBrowser exposing the operator-submit surface."""

    def __init__(
        self,
        *,
        started: bool = True,
        dedicated: bool = True,
        origin_approved: bool = True,
        auth_attested: bool = True,
        surface_resolved: bool = True,
        pages: list[_FakePage] | None = None,
    ) -> None:
        self._started = started
        self._dedicated = dedicated
        self._origin_approved = origin_approved
        self._auth_attested = auth_attested
        self._surface_resolved = surface_resolved
        self.context = _FakeContext(pages)
        self.submit_calls: list[OperatorSignInInput] = []

    @property
    def started(self) -> bool:
        return self._started

    def is_dedicated_persistent_profile(self) -> bool:
        return self._dedicated

    def auth_origin_approved(self) -> bool:
        return self._origin_approved

    def common_auth_attested(self) -> bool:
        return self._auth_attested

    def signin_surface_resolved(self) -> bool:
        # AUTH-112 surface-latch read accessor (mirrors production). Defaults
        # True so the pre-gate submit tests still exercise a resolved surface.
        return self._surface_resolved

    def ensure_live_allowed(self, operation: str) -> None:
        """No-op for the test fake; real browser enforces a live guard."""

    async def submit_operator_signin(self, signin: OperatorSignInInput) -> None:
        self.submit_calls.append(signin)
        page = None
        for candidate in self.context.pages:
            if str(candidate.url):
                page = candidate
        if page is None:
            page = await self.context.new_page()
        # Memory-only: the password reaches exactly one fill and is not retained.
        await page.fill("auth.login_email_input", signin.email)
        await page.fill("auth.login_password_input", signin.password)


@pytest.fixture()
def live_env() -> Iterator[None]:
    previous = {
        "PLANNER_MODE": os.environ.get("PLANNER_MODE"),
        "M365_MODE": os.environ.get("M365_MODE"),
    }
    os.environ["PLANNER_MODE"] = "live"
    os.environ["M365_MODE"] = "live"
    try:
        yield
    finally:
        for name in ("PLANNER_MODE", "M365_MODE"):
            if previous[name] is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous[name]


def _client(app, *, peer: tuple[str, int] = ("127.0.0.1", 4242)) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, client=peer)
    return httpx.AsyncClient(transport=transport, base_url="http://worker")


# --------------------------------------------------------------------------
# Route admission / loopback
# --------------------------------------------------------------------------


async def test_loopback_peer_accepted(live_env) -> None:
    browser = _OperatorSubmitBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(
            OPERATOR_SUBMIT_PATH, json={"email": "a@b.com", "password": "secret"}
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "auth_state": "UNKNOWN"}
    assert len(browser.submit_calls) == 1


async def test_docker_network_peer_denied(live_env) -> None:
    browser = _OperatorSubmitBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app, peer=("172.18.0.9", 5555)) as client:
        response = await client.post(
            OPERATOR_SUBMIT_PATH, json={"email": "a@b.com", "password": "secret"}
        )
    assert response.status_code == 404
    assert browser.submit_calls == []


async def test_forwarded_headers_cannot_spoof_loopback(live_env) -> None:
    browser = _OperatorSubmitBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    spoofs = (
        {"X-Forwarded-For": "127.0.0.1"},
        {"X-Real-IP": "127.0.0.1"},
        {"Forwarded": 'for="127.0.0.1"'},
    )
    async with _client(app, peer=("172.18.0.7", 6666)) as client:
        for headers in spoofs:
            response = await client.post(
                OPERATOR_SUBMIT_PATH,
                json={"email": "a@b.com", "password": "secret"},
                headers=headers,
            )
            assert response.status_code == 404
    assert browser.submit_calls == []


async def test_query_string_rejected(live_env) -> None:
    browser = _OperatorSubmitBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(
            f"{OPERATOR_SUBMIT_PATH}?x=1",
            json={"email": "a@b.com", "password": "secret"},
        )
    assert response.status_code == 400
    assert browser.submit_calls == []


async def test_submit_requires_resolved_signin_surface(live_env) -> None:
    # AUTH-112 surface gate: operator-submit must refuse when the pre-email
    # sign-in surface has NOT been resolved to EMAIL_ENTRY (a direct submit
    # after begin-signin, which can recreate the account chooser, must not apply
    # credentials against a non-email-entry surface). Codes 503 and types
    # nothing.
    browser = _OperatorSubmitBrowser(
        pages=[_FakePage("https://login.microsoftonline.com/")],
        surface_resolved=False,
    )
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(
            OPERATOR_SUBMIT_PATH, json={"email": "a@b.com", "password": "secret"}
        )
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "SIGNIN_SURFACE_NOT_RESOLVED"
    assert browser.submit_calls == []


# --------------------------------------------------------------------------
# Allowed selectors only / closed body contract
# --------------------------------------------------------------------------


def test_validate_signin_input_rejects_extra_keys() -> None:
    with pytest.raises(ValueError):
        validate_signin_input({"email": "a@b.com", "password": "x", "token": "leak"})
    with pytest.raises(ValueError):
        validate_signin_input({"email": "a@b.com"})
    with pytest.raises(ValueError):
        validate_signin_input({"password": "x", "email": 123})


def test_validate_signin_input_accepts_closed_contract() -> None:
    signin = validate_signin_input({"email": "a@b.com", "password": "x"})
    assert isinstance(signin, OperatorSignInInput)
    assert signin.field_names() == ("email", "password")


# --------------------------------------------------------------------------
# common.auth locator plan discovery (fail-closed, value-independent)
# --------------------------------------------------------------------------


def test_progression_selector_keys_are_exactly_four() -> None:
    assert PROGRESSION_SELECTOR_KEYS == (
        EMAIL_SELECTOR_NAME,
        NEXT_SELECTOR_NAME,
        PASSWORD_SELECTOR_NAME,
        SIGNIN_SELECTOR_NAME,
    )
    assert len(PROGRESSION_SELECTOR_KEYS) == 4
    assert PASSWORD_SELECTOR_NAME == "auth.login_password_input"  # noqa: S105 - selector name
    assert EMAIL_SELECTOR_NAME == "auth.login_email_input"
    assert NEXT_SELECTOR_NAME == "auth.login_next_button"
    assert SIGNIN_SELECTOR_NAME == "auth.login_signin_button"


def test_four_plans_load_from_shipped_fragment() -> None:
    for key in PROGRESSION_SELECTOR_KEYS:
        plan = common_auth_locator_plan(key)
        assert plan is not None
        assert isinstance(plan, LocatorPlan)
        assert plan.selector_key == key
        assert plan.candidates


def test_unknown_key_fails_closed() -> None:
    with pytest.raises(ValueError):
        common_auth_locator_plan("auth.login_unknown_button")
    with pytest.raises(ValueError):
        common_auth_locator_plan("http://evil.example.com")
    with pytest.raises(ValueError):
        common_auth_locator_plan("")


def test_values_may_be_null_while_plans_exist() -> None:
    # Shipped common.auth is UNVERIFIED_LIVE: scalar values are null, but the
    # structured plans must still load (bootstrap discovery needs them).
    for key in PROGRESSION_SELECTOR_KEYS:
        assert ui_contract_selector_value(key) is None
        plan = common_auth_locator_plan(key)
        assert plan is not None
        assert plan.candidates


def test_plan_ignores_scalar_value_and_uses_locators_metadata() -> None:
    plan = common_auth_locator_plan(PASSWORD_SELECTOR_NAME)
    assert plan is not None
    strategies = {candidate.strategy.value for candidate in plan.candidates}
    # The plan is built from the structured locators, not from a scalar string.
    assert "role" in strategies


async def test_unknown_key_never_reaches_browser(live_env) -> None:
    browser = _OperatorSubmitBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(
            OPERATOR_SUBMIT_PATH,
            json={"email": "a@b.com", "password": "x", "url": "https://evil.example.com"},
        )
    assert response.status_code == 400
    assert browser.submit_calls == []


async def test_applies_only_common_auth_signin_selectors(live_env) -> None:
    page = _FakePage("https://login.microsoftonline.com/")
    browser = _OperatorSubmitBrowser(pages=[page])
    app = create_app(browser=browser)
    async with _client(app) as client:
        await client.post(OPERATOR_SUBMIT_PATH, json={"email": "a@b.com", "password": "s3cr3t"})
    assert page.fill_calls == [
        ("auth.login_email_input", "a@b.com"),
        ("auth.login_password_input", "s3cr3t"),
    ]


async def test_non_attested_common_auth_fails_closed(live_env) -> None:
    page = _FakePage("https://login.microsoftonline.com/")
    browser = _OperatorSubmitBrowser(pages=[page], auth_attested=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(
            OPERATOR_SUBMIT_PATH, json={"email": "a@b.com", "password": "s3cr3t"}
        )
    assert response.status_code == 503
    assert browser.submit_calls == []


# --------------------------------------------------------------------------
# No-secret leakage in response
# --------------------------------------------------------------------------


async def test_response_leaks_no_secret_material(live_env) -> None:
    browser = _OperatorSubmitBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)

    async def _run() -> str:
        async with _client(app) as client:
            response = await client.post(
                OPERATOR_SUBMIT_PATH,
                json={"email": "operator@contoso.com", "password": "Sup3rSecret!"},
            )
        return response.text.lower()

    body = await _run()
    for forbidden in (
        "sup3rsecret",
        "operator@contoso.com",
        "login.microsoftonline.com",
        "http",
        "cookie",
        "token",
        "upn",
        "tenant",
        "bearer",
        "<html",
    ):
        assert forbidden not in body


# --------------------------------------------------------------------------
# Live state machine: fail-closed MFA resolution
# --------------------------------------------------------------------------


def test_mfa_required_resolves_only_on_unique_number() -> None:
    state, challenge, ambiguous = classify_live(
        "Enter the number 73 to approve the sign-in request in Microsoft Authenticator."
    )
    assert state is AuthState.MFA_REQUIRED
    assert challenge is not None
    assert challenge.number == "73"
    assert ambiguous is False


def test_ambiguous_mfa_number_fails_closed() -> None:
    state, challenge, ambiguous = classify_live(
        "Enter the number 12 to approve. Or enter the number 34 if prompted "
        "in Microsoft Authenticator."
    )
    assert state is AuthState.UNKNOWN
    assert challenge is None
    assert ambiguous is True


def test_waiting_for_mfa_is_resolved_live_state() -> None:
    state, challenge, ambiguous = classify_live(
        "Approve sign in request. Waiting for approval in Microsoft Authenticator."
    )
    assert state is AuthState.WAITING_FOR_MFA
    assert challenge is None
    assert ambiguous is False


def test_advance_state_machine_transitions_guarded() -> None:
    ctx = AuthContext()
    ctx.transition(AuthState.AUTH_REQUIRED)
    reading = advance_live_auth_state(
        ctx,
        "Open your Authenticator app and enter the number 42 to sign in.",
    )
    assert reading.state is AuthState.MFA_REQUIRED
    assert ctx.state is AuthState.MFA_REQUIRED
    # A subsequent ambiguous reading must NOT invent a challenge; it fails closed.
    reading2 = advance_live_auth_state(ctx, "Codes 11 and 22 both shown.")
    assert reading2.state is AuthState.UNKNOWN
    assert reading2.challenge is None


# --------------------------------------------------------------------------
# Notifier payload: sanitized, one-way, no approval
# --------------------------------------------------------------------------


def test_notifier_payload_is_closed_and_sanitized() -> None:
    challenge = MfaChallenge(
        number="42",
        operation_id="auth-live",
        service="microsoft-entra-id",
        description="Sign in to Microsoft Planner",
        expires_at="2030-01-01T00:00:00+00:00",
    )
    notification, _result = emit(challenge)
    payload = notification.to_dict()
    assert set(payload) == {
        "mfa_number",
        "operation_id",
        "service",
        "description",
        "expires_at",
        "approve_in_authenticator_only",
        "approval_channel",
    }
    assert payload["approve_in_authenticator_only"] == "true"
    assert payload["mfa_number"] == "42"
    for forbidden in ("password", "token", "cookie", "upn", "tenant", "bearer"):
        assert forbidden not in payload


def test_notifier_has_no_approval_capability_and_no_secrets() -> None:
    challenge = MfaChallenge(
        number="42",
        operation_id="auth-live",
        service="microsoft-entra-id",
        description="Sign in to Microsoft Planner",
        expires_at="2030-01-01T00:00:00+00:00",
    )
    json_line = sanitize_for_external_adapter(MfaNotification.from_challenge(challenge))
    assert "approve_in_authenticator_only" in json_line
    assert "microsoft_authenticator" in json_line


def test_notifier_delivery_failure_is_degradation_not_approval() -> None:
    challenge = MfaChallenge(
        number="42",
        operation_id="auth-live",
        service="microsoft-entra-id",
        description="Sign in to Microsoft Planner",
        expires_at="2030-01-01T00:00:00+00:00",
    )

    def _boom(_: MfaNotification) -> MfaNotificationResult:
        raise RuntimeError("adapter down")

    _notification, result = emit(challenge, sink=_boom)
    assert result.delivered is False
    assert result.detail == "sink-error:RuntimeError"


# --------------------------------------------------------------------------
# Credential loader: memory-only, no value exposure (mocked subprocess)
# --------------------------------------------------------------------------


def test_credential_loader_keeps_values_memory_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    login = _OPERATOR_AUTH_LOGIN

    # Hermetic in CI: redirect the module's credential store to an isolated
    # tmp dir and create only the dummy encrypted credential file (placeholder
    # content, never a real secret). Production source is untouched.
    monkeypatch.setattr(login, "_CREDSTORE_DIR", tmp_path)
    dummy_cred = tmp_path / "m365-ui-mcp.username.cred"
    dummy_cred.write_text("dummy-encrypted-placeholder-not-a-secret", encoding="utf-8")

    captured: dict[str, list[str]] = {}

    def _fake_run(cmd, *, capture_output, text, check):  # noqa: ANN001
        captured["cmd"] = list(cmd)
        return subprocess.CompletedProcess(list(cmd), 0, stdout="mem-only-value\n", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    value = login._decrypt_credential("m365-ui-mcp.username.cred")
    assert value == "mem-only-value"
    cmd_parts = captured["cmd"]
    canonical_store = str(login._CREDSTORE_DIR)
    assert any(canonical_store in part for part in cmd_parts)
    assert "--user" in cmd_parts


def test_credential_loader_rejects_missing_store(monkeypatch: pytest.MonkeyPatch) -> None:
    login = _OPERATOR_AUTH_LOGIN

    monkeypatch.setattr(login, "_CREDSTORE_DIR", Path("/nonexistent-credstore"))
    with pytest.raises(RuntimeError):
        login._decrypt_credential("m365-ui-mcp.username.cred")


# --------------------------------------------------------------------------
# Catalog absence (must not become an MCP tool)
# --------------------------------------------------------------------------


def test_endpoint_absent_from_mcp_tool_catalog() -> None:
    from m365_mcp.tool_registry import default_tool_registry

    names = set(default_tool_registry().names())
    assert not [n for n in names if "operator" in n or "submit" in n or "signin" in n]


def test_worker_client_has_no_operator_submit_proxy() -> None:
    attributes = dir(WorkerClient)
    assert not [a for a in attributes if "operator" in a or "submit" in a]
    source = (ROOT / "src" / "planner_mcp" / "worker_client.py").read_text(encoding="utf-8")
    assert OPERATOR_SUBMIT_PATH not in source


def test_operator_wrapper_shape() -> None:
    script = ROOT / "scripts" / "operator_auth_login.py"
    assert script.is_file()
    assert os.access(script, os.X_OK)
    text = script.read_text(encoding="utf-8")
    assert "systemd-creds decrypt --user" in text
    assert "credstore.encrypted" in text
    assert "127.0.0.1:8090/auth/bootstrap/operator-submit" in text
    # The only print-like line must be the sanitized status line; no value echo.
    assert 'sys.stdout.write(f"ok=true auth_state=' in text
    assert "print(value" not in text
    assert "print(username" not in text
    assert "print(password" not in text


def test_operator_wrapper_rejects_arguments() -> None:
    script = ROOT / "scripts" / "operator_auth_login.py"
    result = subprocess.run(  # noqa: S603, S607
        ["/usr/bin/python3", str(script), "https://example.com"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "no arguments" in result.stderr.lower()
