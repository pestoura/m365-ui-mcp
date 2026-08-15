"""Application-neutral Playwright persistent-browser boundary.

This module owns the browser/profile lifecycle primitives used by Microsoft 365
application adapters. It deliberately exposes no generic click/selector/script
surface and never exports authenticated session material.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from m365_browser_worker.auth_bootstrap import AuthOriginStatus, auth_origin_status
from m365_browser_worker.bootstrap_navigation import (
    AUTH_BEGIN_EMAIL_STAGE_OPERATION,
    AUTH_BEGIN_SIGNIN_OPERATION,
    AUTH_BOOTSTRAP_NAVIGATE_OPERATION,
    AUTH_OBSERVE_OPERATION,
    AUTH_OPERATOR_SUBMIT_OPERATION,
    MICROSOFT_AUTH_BOOTSTRAP_URL,
    PLANNER_WEB_BOOTSTRAP_URL,
    classify_begin_signin_source,
    evaluate_bootstrap_target,
    evaluate_microsoft_auth_target,
    is_permitted_begin_signin_source,
    is_planner_web_surface_url,
    is_reusable_bootstrap_page,
)
from m365_browser_worker.egress import enforce_route_egress
from m365_browser_worker.locator_runtime import (
    LocatorRuntimeError,
    resolve_visible_locator,
)
from m365_browser_worker.operator_signin import (
    EMAIL_SELECTOR_NAME,
    NEXT_SELECTOR_NAME,
    PASSWORD_SELECTOR_NAME,
    SIGNIN_SELECTOR_NAME,
    OperatorSignInInput,
    common_auth_locator_plan,
)
from m365_browser_worker.signin_surface import (
    AUTH_DIAGNOSE_OPERATION,
    AUTH_KMSI_OPERATION,
    AUTH_RESOLVE_OPERATION,
    SigninSurfaceKind,
    SurfaceClassification,
    classify_signin_surface,
    resolve_signin_surface_to_email_entry,
    resolve_stay_signed_in_surface,
)
from m365_mcp.config import browser_runtime_settings
from planner_mcp.errors import (
    BlockerConditionalAccess,
    PolicyDenied,
    UiContractUnattested,
    WorkerUnavailable,
)
from planner_mcp.ui_contract import common_auth_attested, load_status


@dataclass(frozen=True)
class BrowserConfig:
    """Configuration of the isolated professional browser profile."""

    profile_dir: Path
    headless: bool = True
    mode: str = "mock"

    @classmethod
    def from_env(cls) -> BrowserConfig:
        """Build configuration through the canonical M365/legacy alias policy."""
        profile_dir, headless, mode = browser_runtime_settings()
        return cls(profile_dir=profile_dir, headless=headless, mode=mode)

    @property
    def is_mock(self) -> bool:
        return self.mode.lower() == "mock"


CONDITIONAL_ACCESS_MARKERS = (
    "your device must be managed",
    "device is not compliant",
    "enrol this device",
    "enroll this device",
    "company portal",
)

# Bounded per-stage timeout for each sequential sign-in progression locator
# resolution. Each email/next/password/sign-in stage waits at most this long for
# a unique visible match before failing closed. Keeps the operator submit path
# from hanging against a live Microsoft sign-in page.
OPERATOR_SIGNIN_STAGE_TIMEOUT_MS = 5_000

def detect_conditional_access_block(page_text: str) -> bool:
    """Detect a Conditional Access managed-device wall from page text."""
    lowered = page_text.lower()
    return any(marker in lowered for marker in CONDITIONAL_ACCESS_MARKERS)


class PersistentBrowser:
    """Persistent-profile Chromium abstraction.

    The persistent profile is the authentication boundary. Passwords, cookies,
    tokens and storage state are never copied into MCP or application state.
    Individual semantic operations use fresh operation-scoped pages so page-local
    navigation/DOM state cannot bleed into the next operation.
    """

    def __init__(self, config: BrowserConfig | None = None) -> None:
        self.config = config or BrowserConfig.from_env()
        self._playwright: Any = None
        self._context: Any = None
        # AUTH-112 surface latch. ``operator-submit`` MAY only apply the
        # credential fields after the pre-email sign-in surface has been
        # deterministically resolved to ``EMAIL_ENTRY`` via
        # ``resolve_signin_surface``. ``begin_auth_signin`` resets it because a
        # post-begin surface (account chooser / "use another account" prompt) is
        # NOT the email-entry field, and submitting against it causes an
        # email NO_MATCH. The latch is monotonically conservative: it is set
        # only by a successful resolve and cleared by any begin-signin that may
        # recreate an intermediate surface. It never carries identity/DOM/URL.
        self._signin_surface_resolved: bool = False

    @property
    def started(self) -> bool:
        """Return whether this process currently owns a live Chromium context."""
        return self._context is not None and self._playwright is not None

    def is_dedicated_persistent_profile(self) -> bool:
        """Return whether this is the dedicated persistent professional profile.

        A throwaway or wrong profile directory is rejected so authentication
        bootstrap can only proceed against the sanctioned professional context.
        Mock mode is never the dedicated live profile.
        """
        if self.config.is_mock:
            return False
        expected_profile_dir, _headless, _mode = browser_runtime_settings()
        return self.started and self.config.profile_dir == expected_profile_dir

    def auth_origin_approved(self) -> bool:
        """Return whether the live context may begin/continue auth bootstrap.

        True only when no page is open yet (bootstrap may begin navigation) or
        every open page is on an approved Microsoft authentication origin. Raw
        URLs are reduced to a closed host allowlist decision and never returned.
        """
        if not self.started:
            return False
        status = auth_origin_status(tuple(page.url for page in self._context.pages))
        return status is not AuthOriginStatus.NON_APPROVED_ORIGIN

    def begin_signin_source_permitted(self) -> bool:
        """Return whether the live context is a permitted begin-signin source.

        Delegates to the closed ``begin_signin`` source classifier. True only
        when every open page is Planner Web (exact/suffix host), a neutral
        placeholder, or an approved Microsoft authentication origin. Raw URLs
        are reduced to the closed classification and never returned.
        """
        if not self.started:
            return False
        return is_permitted_begin_signin_source(
            tuple(str(page.url) for page in self._context.pages)
        )

    def common_auth_attested(self) -> bool:
        """Return whether the ``common.auth`` UIContract fragments are attested.

        Fragment-scoped: delegates to ``planner_mcp.ui_contract.common_auth_attested``
        which inspects ONLY the two atomic ``common.auth`` fragments
        (``common.auth.email`` and ``common.auth.password``) and returns True iff
        BOTH are effectively attested. This lets LIVE auth report AUTHENTICATED
        once both ``common.auth`` fragments are legitimately attested even while
        Planner fragments remain UNVERIFIED. The stricter full-contract
        ``ensure_live_allowed`` gate is unchanged.
        """
        return common_auth_attested()

    def ensure_live_allowed(self, operation: str) -> None:
        """Fail closed for semantic live operations without an attested UIContract."""
        status = load_status()
        if not status.attested:
            raise UiContractUnattested(
                f"live browser operation '{operation}' blocked",
                ui_contract_version=status.version,
            )

    async def navigate_auth_bootstrap(self) -> None:
        """Navigate ONCE to the FIXED Planner Web bootstrap target.

        This is the only navigation primitive in the worker and it takes no
        arguments: the destination is the production constant
        ``PLANNER_WEB_BOOTSTRAP_URL``. The constant is re-evaluated through the
        closed egress policy on every call and navigation is refused unless that
        policy allows it, so the browser can never be steered elsewhere. The
        Playwright route interceptor stays installed, so redirects and
        sub-resources continue to be evaluated.

        An already-open page is reused only when it is a neutral placeholder;
        otherwise exactly ONE new page is opened in the same persistent context.
        There is no retry, no credential entry and no MFA automation, and no
        URL/DOM/page text/cookie/token is returned.
        """
        if not self.started:
            raise WorkerUnavailable(
                "authentication bootstrap navigation requires a started live browser",
                operation=AUTH_BOOTSTRAP_NAVIGATE_OPERATION,
            )

        decision = evaluate_bootstrap_target()
        if not decision.allowed:
            raise PolicyDenied(
                "authentication bootstrap navigation denied by closed egress policy",
                operation=AUTH_BOOTSTRAP_NAVIGATE_OPERATION,
                reason=decision.reason,
            )

        context = self._context
        page = None
        for candidate in context.pages:
            if is_reusable_bootstrap_page(str(candidate.url)):
                page = candidate
                break
        if page is None:
            page = await context.new_page()

        # Exactly one navigation per operator call; no retry loop.
        await page.goto(PLANNER_WEB_BOOTSTRAP_URL)

    async def begin_auth_signin(self) -> None:
        """Navigate ONCE to the FIXED Microsoft auth bootstrap target.

        Step two of the two-step operator flow. The dedicated persistent
        professional profile must already be started (guaranteed by the app
        guard wiring through the app guard/provider). The current page is
        selected/reused only when its source class is permitted for
        begin-signin — ``planner_web`` (host exactly/suffix matching the Planner
        Web target), ``neutral`` (``about:blank`` / ``chrome://newtab``) or an
        already approved Microsoft authentication origin. Any other source
        (arbitrary web origin, or a non-approved page) fails closed without
        opening or hijacking a page.

        Topology fix (no weakening of fail-closed controls): when the live
        context already holds a ``planner_web`` page, that SAME page is reused
        for the fixed-signin navigation instead of opening a second page. A
        neutral placeholder page is likewise reused. This collapses the old
        dual-page topology into one page on the approved Microsoft auth origin
        after sign-in begins, so no duplicate companion Planner page lingers and
        the operator continues the interactive sign-in (including MFA) on the
        single reused page. Exactly one navigation happens. If more than one
        distinct permitted page is open (ambiguous topology) the call fails
        closed rather than guessing which page to hijack, and arbitrary or
        non-approved sources fail closed as before.

        The destination is the production constant ``MICROSOFT_AUTH_BOOTSTRAP_URL``
        and the call takes no arguments. The constant is re-evaluated through the
        closed egress policy on every call and navigation is refused unless that
        policy ALLOWS the fixed Microsoft auth target — there is no URL input, so
        the browser can never be steered to Graph/API/non-HTTPS. The Playwright
        route interceptor stays installed, so redirects and sub-resources continue
        to be evaluated. Exactly one navigation, no retry, no credential entry,
        no MFA automation, and no URL/DOM/page text/cookie/token is returned.
        """
        if not self.started:
            raise WorkerUnavailable(
                "begin sign-in requires a started live browser",
                operation=AUTH_BEGIN_SIGNIN_OPERATION,
            )

        if not self.is_dedicated_persistent_profile():
            raise PolicyDenied(
                "begin sign-in requires the dedicated persistent professional browser profile",
                operation=AUTH_BEGIN_SIGNIN_OPERATION,
            )

        source = classify_begin_signin_source(tuple(str(page.url) for page in self._context.pages))
        if source == "non_approved":
            raise PolicyDenied(
                "begin sign-in requires the dedicated professional profile to be "
                "positioned on Planner Web, a neutral placeholder, or an approved "
                "Microsoft authentication origin",
                operation=AUTH_BEGIN_SIGNIN_OPERATION,
            )

        target_decision = evaluate_microsoft_auth_target()
        if not target_decision.allowed:
            raise PolicyDenied(
                "begin sign-in Microsoft auth target denied by closed egress policy",
                operation=AUTH_BEGIN_SIGNIN_OPERATION,
                reason=target_decision.reason,
            )

        context = self._context

        # Topology fix: reuse the SAME existing planner_web page when present,
        # so begin-signin does not open a second page and leave a duplicate
        # companion Planner page behind. A neutral placeholder page is also
        # reused. Both are closed, approved sources.
        existing_planner_web: Any = None
        existing_neutral: Any = None
        for candidate in context.pages:
            raw = str(candidate.url)
            if is_planner_web_surface_url(raw):
                # More than one planner_web page means an ambiguous topology;
                # fail closed rather than guessing which page to hijack.
                if existing_planner_web is not None:
                    raise PolicyDenied(
                        "begin sign-in refuses an ambiguous topology with "
                        "multiple Planner Web pages open",
                        operation=AUTH_BEGIN_SIGNIN_OPERATION,
                    )
                existing_planner_web = candidate
            elif is_reusable_bootstrap_page(raw):
                if existing_neutral is not None:
                    # Multiple neutral placeholders: ambiguous, fail closed.
                    raise PolicyDenied(
                        "begin sign-in refuses an ambiguous topology with "
                        "multiple neutral pages open",
                        operation=AUTH_BEGIN_SIGNIN_OPERATION,
                    )
                existing_neutral = candidate

        if existing_planner_web is not None:
            page = existing_planner_web
        elif existing_neutral is not None:
            page = existing_neutral
        else:
            # No reusable page on an approved source. The source classifier
            # already accepted this context (e.g. an existing approved Microsoft
            # auth origin, or no pages yet), so open exactly one new page.
            page = await context.new_page()

        # Exactly one navigation per operator call; no retry loop.
        await page.goto(MICROSOFT_AUTH_BOOTSTRAP_URL)

        # AUTH-112: a (re)navigation to the Microsoft auth target may recreate a
        # pre-email intermediate surface (account chooser / "use another
        # account" prompt) rather than the email-entry field. Reset the
        # surface latch so a later ``operator-submit`` cannot apply credentials
        # against a non-email-entry surface (which previously caused an email
        # NO_MATCH). The latch is only re-set by a successful
        # ``resolve_signin_surface``.
        self._signin_surface_resolved = False

        # AUTH-113: the single navigation may have resolved WITHOUT the page
        # actually establishing an approved Microsoft auth origin — an aborted /
        # blocked redirect, an offline target, or a stale dedicated page left on
        # ``about:blank``. Reporting success in that case is the navigation /
        # lifecycle correctness defect: the endpoint must NOT return
        # target_class=microsoft_auth while the actual page is still
        # about:blank / a neutral placeholder / a non-approved origin. Verify
        # the REAL landing origin on the exact page object that was navigated
        # (no stale reference) using the closed auth-origin policy. The URL is
        # reduced to a closed classification and never returned to a caller.
        await self._require_landed_on_approved_auth_origin(page)

    async def _require_landed_on_approved_auth_origin(self, page: Any) -> None:
        """Fail closed unless ``page`` now sits on an approved Microsoft auth origin.

        AUTH-113: called immediately after the single ``page.goto`` in
        ``begin_auth_signin``. The URL is read from the SAME page object that was
        navigated (never a stale reference), so a page that is still on
        ``about:blank`` / a neutral placeholder, or that landed on any
        non-allowlisted / non-approved web origin, cannot be reported as a
        successful Microsoft auth sign-in transition. The page URL is reduced to
        the closed ``auth_origin_status`` classification and is never returned to
        a caller, so no URL, DOM, cookie, token, UPN or tenant id leaves this
        method. The navigation itself has already been awaited by the caller, so
        this is a pure post-landing assertion against live page state.
        """
        raw = str(getattr(page, "url", "") or "")
        status = auth_origin_status((raw,))
        if status is not AuthOriginStatus.APPROVED_AUTH_ORIGIN:
            raise PolicyDenied(
                "begin sign-in navigation did not establish an approved "
                "Microsoft authentication origin; refusing to report success",
                operation=AUTH_BEGIN_SIGNIN_OPERATION,
            )

    async def begin_email_stage(self, email: str) -> None:
        """Pre-attestation operator email stage: fill email, click Next only.

        This is the headless-safe replacement for the removed GUI/noVNC handoff
        (PR #614). It breaks the attestation bootstrap deadlock without
        weakening the fail-closed model:

        * It runs BEFORE ``common.auth`` is attested (unlike
          ``submit_operator_signin``, which requires full attestation). This is
          the minimal fix: the password/signin selectors needed for attestation
          only appear AFTER email -> Next, and with the GUI handoff gone there
          was no headless path to reach them.
        * It applies ONLY the email field and clicks ONLY the Next control.
          It NEVER types the password and NEVER clicks Sign in, so no
          credential secret is ever placed in the browser, argv, env or state.
        * The email value is the operator's professional address supplied by the
          caller (memory-only); it is consumed for exactly one ``fill`` and
          dropped. It is NOT read from or written to the encrypted store by this
          method, and it is NOT the sign-in password.
        * Locators are resolved through the fail-closed ``locator_runtime`` from
          the shipped ``common.auth`` plans (value-independent, works for
          ``UNVERIFIED_LIVE``). A missing/ambiguous control fails closed as
          ``PolicyDenied`` with only ``selector_key``/``reason`` — never a
          candidate value or DOM text.
        * After Next, the auth origin is re-asserted: if the navigation escaped
          the approved Microsoft authentication origin the call stops before any
          further action.
        * It performs no MFA automation and exposes no URL/DOM/cookie/token.

        Guard chain (fail closed on any failure): started live browser, dedicated
        persistent professional profile, approved Microsoft authentication
        origin, single open auth page, email plan resolvable, Next plan
        resolvable.
        """
        if not self.started:
            raise WorkerUnavailable(
                "email stage requires a started live browser",
                operation=AUTH_BEGIN_EMAIL_STAGE_OPERATION,
            )
        if not self.is_dedicated_persistent_profile():
            raise PolicyDenied(
                "email stage requires the dedicated persistent professional "
                "browser profile",
                operation=AUTH_BEGIN_EMAIL_STAGE_OPERATION,
            )
        if not self.auth_origin_approved():
            raise PolicyDenied(
                "email stage requires the page to be on an approved "
                "Microsoft authentication origin",
                operation=AUTH_BEGIN_EMAIL_STAGE_OPERATION,
            )

        email_plan = common_auth_locator_plan(EMAIL_SELECTOR_NAME)
        next_plan = common_auth_locator_plan(NEXT_SELECTOR_NAME)
        if email_plan is None or next_plan is None:
            raise PolicyDenied(
                "email stage progression selectors are incomplete; refusing to "
                "guess locators",
                operation=AUTH_BEGIN_EMAIL_STAGE_OPERATION,
            )

        page = self._require_single_auth_page()
        timeout_ms = OPERATOR_SIGNIN_STAGE_TIMEOUT_MS

        try:
            email_locator = await resolve_visible_locator(
                cast("Any", page), email_plan, timeout_ms=timeout_ms
            )
        except LocatorRuntimeError as exc:
            raise PolicyDenied(
                "email stage could not resolve the email field",
                operation=AUTH_BEGIN_EMAIL_STAGE_OPERATION,
                selector_key=exc.selector_key,
                reason=exc.reason,
            ) from None
        # Memory-only: the email is consumed for exactly one fill and then
        # dropped; it is never written to state, logs, argv, env or responses.
        await cast("Any", email_locator.locator).fill(email)

        try:
            next_locator = await resolve_visible_locator(
                cast("Any", page), next_plan, timeout_ms=timeout_ms
            )
        except LocatorRuntimeError as exc:
            raise PolicyDenied(
                "email stage could not resolve the next control",
                operation=AUTH_BEGIN_EMAIL_STAGE_OPERATION,
                selector_key=exc.selector_key,
                reason=exc.reason,
            ) from None
        await cast("Any", next_locator.locator).click()

        # Re-assert the auth origin after the Next navigation. The click must
        # not have escaped the approved Microsoft authentication surface.
        if not self.auth_origin_approved():
            raise PolicyDenied(
                "email stage navigation escaped the approved Microsoft "
                "authentication origin",
                operation=AUTH_BEGIN_EMAIL_STAGE_OPERATION,
            )

    async def resolve_signin_surface(self) -> None:
        """Operator-only deterministic pre-email surface resolution (AUTH-109).

        Forces the email-entry surface when Microsoft presents a deterministic
        pre-email intermediate (account chooser / "use another account" prompt)
        instead of the email field. It is the headless-safe counterpart to
        ``begin_email_stage`` (AUTH-106): it ONLY changes which sign-in SURFACE
        is displayed, never credentials, never MFA, never account selection.

        Fail-closed contract:

        * runs BEFORE ``common.auth`` attestation (like ``begin_email_stage``),
          so the email surface can be reached for attestation headlessly;
        * guard chain: started live browser, dedicated persistent professional
          profile, approved Microsoft authentication origin, exactly one open
          auth page. Any failure fails closed with ``PolicyDenied`` and never
          clicks anything;
        * the ONLY action taken is the fixed "use another account" control,
          matched from a CLOSED set of exact Microsoft labels
          (``USE_ANOTHER_ACCOUNT_LABELS``). It NEVER selects a cached identity
          (account tile), never types, never navigates by URL/locator;
        * if the surface is not a deterministic forwardable stage
          (pick-an-account, stay-signed-in, consent, method selection, error,
          ambiguous, unknown) it fails closed — it never guesses a surface;
        * reads bounded visible body text internally (via
          ``read_visible_body_bounded``, already guard-gated) and never logs or
          returns it.
        """
        if not self.started:
            raise WorkerUnavailable(
                "sign-in surface resolution requires a started live browser",
                operation=AUTH_RESOLVE_OPERATION,
            )
        if not self.is_dedicated_persistent_profile():
            raise PolicyDenied(
                "sign-in surface resolution requires the dedicated persistent "
                "professional browser profile",
                operation=AUTH_RESOLVE_OPERATION,
            )
        if not self.auth_origin_approved():
            raise PolicyDenied(
                "sign-in surface resolution requires the page to be on an "
                "approved Microsoft authentication origin",
                operation=AUTH_RESOLVE_OPERATION,
            )

        page = self._require_single_auth_page()

        async def _read() -> str:
            return await self.read_visible_body_bounded(max_chars=2000)

        resolution = await resolve_signin_surface_to_email_entry(page, _read)
        if resolution.kind is SigninSurfaceKind.EMAIL_ENTRY:
            # AUTH-112: the email-entry surface is deterministically present, so
            # a subsequent ``operator-submit`` may apply the credential fields.
            # The latch is set ONLY here; ``begin_auth_signin`` clears it and a
            # non-email-entry resolution leaves it cleared (fail closed).
            self._signin_surface_resolved = True
            return
        if resolution.kind in (
            SigninSurfaceKind.ACCOUNT_CHOOSER,
            SigninSurfaceKind.USE_ANOTHER_ACCOUNT_PROMPT,
        ):
            # The forwarded intermediate surface is still NOT the email-entry
            # field; keep the latch cleared so submit fails closed until the
            # surface is actually EMAIL_ENTRY.
            self._signin_surface_resolved = False
            return
        # Not a deterministic forwardable surface; fail closed without
        # selecting any cached identity or guessing a control.
        self._signin_surface_resolved = False
        raise PolicyDenied(
            "sign-in surface is not a deterministic pre-email stage; "
            "manual operator intervention required",
            operation=AUTH_RESOLVE_OPERATION,
            # Observability-only: the sanitized CLOSED enum of the terminal
            # surface the resolver last encountered. No URL/DOM/text/identity.
            terminal_surface=resolution.terminal_surface.value,
        )

    async def resolve_kmsi_surface(self) -> SigninSurfaceKind:
        """Operator-only deterministic KMSI ("Stay signed in?") resolution (AUTH-114).

        Dismisses the credential-free, MFA-free post-password KMSI interstitial by
        clicking ONLY the fixed decline control, and ONLY when that control is
        strictly unique on a surface that classifies as ``STAY_SIGNED_IN``.

        Fail-closed contract:

        * guard chain identical to ``resolve_signin_surface`` (started live
          browser, dedicated persistent professional profile, approved Microsoft
          authentication origin, exactly one open auth page);
        * NO credential is typed, NO cached identity is selected, NO Sign in is
          clicked, NO URL/locator navigation is performed;
        * any non-``STAY_SIGNED_IN`` surface, or an absent/ambiguous fixed
          control, raises ``PolicyDenied`` with only the sanitized closed
          terminal-surface enum;
        * bounded visible body text is read internally and never logged/returned.

        Returns the sanitized closed post-dismissal ``SigninSurfaceKind``.
        """
        if not self.started:
            raise WorkerUnavailable(
                "KMSI surface resolution requires a started live browser",
                operation=AUTH_KMSI_OPERATION,
            )
        if not self.is_dedicated_persistent_profile():
            raise PolicyDenied(
                "KMSI surface resolution requires the dedicated persistent "
                "professional browser profile",
                operation=AUTH_KMSI_OPERATION,
            )
        if not self.auth_origin_approved():
            raise PolicyDenied(
                "KMSI surface resolution requires the page to be on an approved "
                "Microsoft authentication origin",
                operation=AUTH_KMSI_OPERATION,
            )

        page = self._require_single_auth_page()

        async def _read() -> str:
            return await self.read_visible_body_bounded(max_chars=2000)

        resolution = await resolve_stay_signed_in_surface(page, _read)
        if not resolution.advanced:
            raise PolicyDenied(
                "sign-in surface is not a deterministic KMSI stage; "
                "manual operator intervention required",
                operation=AUTH_KMSI_OPERATION,
                terminal_surface=resolution.terminal_surface.value,
            )
        return resolution.terminal_surface

    async def diagnose_signin_surface(self) -> SurfaceClassification:
        """READ-ONLY closed classification of the current sign-in surface.

        Operator-only deterministic diagnosis twin of ``resolve_signin_surface``.
        It runs the SAME guard chain (started live browser, dedicated persistent
        professional profile, approved Microsoft authentication origin, exactly
        one open auth page) but performs NO click — it reads the bounded visible
        body text once and returns only the closed ``SurfaceClassification``.
        This lets a run report the exact closed surface kind when the mutating
        resolver would fail closed, without guessing and without acting.

        Fail-closed contract (identical safety shape to the resolver, minus the
        click): any guard failure raises and returns nothing; no URL/DOM/page
        text/cookie/token/UPN/tenant/account identifier is ever returned.
        """
        if not self.started:
            raise WorkerUnavailable(
                "sign-in surface diagnosis requires a started live browser",
                operation=AUTH_DIAGNOSE_OPERATION,
            )
        if not self.is_dedicated_persistent_profile():
            raise PolicyDenied(
                "sign-in surface diagnosis requires the dedicated persistent "
                "professional browser profile",
                operation=AUTH_DIAGNOSE_OPERATION,
            )
        if not self.auth_origin_approved():
            raise PolicyDenied(
                "sign-in surface diagnosis requires the page to be on an "
                "approved Microsoft authentication origin",
                operation=AUTH_DIAGNOSE_OPERATION,
            )

        # Enforce exactly one open auth page before the bounded read.
        self._require_single_auth_page()
        # Bounded, read-only text read; never logs or returns the text.
        text = await self.read_visible_body_bounded(max_chars=2000)
        return classify_signin_surface(text)

    def signin_surface_resolved(self) -> bool:
        """Return whether the pre-email sign-in surface was resolved to EMAIL_ENTRY.

        AUTH-112 surface-latch read accessor. ``True`` only after a successful
        ``resolve_signin_surface`` (EMAIL_ENTRY); ``False`` by default and after
        any ``begin_auth_signin`` (which may recreate an intermediate surface).
        This is the gate ``operator-submit`` consults before applying the two
        memory-only credential fields. It never exposes identity/DOM/URL.
        """
        return self._signin_surface_resolved

    async def submit_operator_signin(self, signin: OperatorSignInInput) -> None:
        """Apply the operator-sign-in fields to the Microsoft sign-in page in sequence.

        This is the ONLY credential-application primitive. It receives a
        memory-only ``OperatorSignInInput`` (built by the operator-local
        encrypted-store helper) and drives the standard Microsoft Entra ID
        sign-in progression on the already-open authentication page:

        1. resolve ``auth.login_email_input`` and fill ``signin.email``;
        2. resolve ``auth.login_next_button`` and click it (the Microsoft
           "Next"/"Avançar" control advances email to the password step);
        3. re-assert the page is still on an approved Microsoft authentication
           origin (the Next navigation must not have escaped the auth surface);
        4. resolve and wait for ``auth.login_password_input`` and fill
           ``signin.password``;
        5. resolve ``auth.login_signin_button`` and click it (the Microsoft
           form "Sign in"/"Iniciar sessão" finalizes the credential submission).

        It is fail-closed:

        * the destination is never supplied — the values are applied only to the
          already-open page on an approved Microsoft authentication origin;
        * all four locators are loaded as structured plans via
          ``common_auth_locator_plan`` and resolved through the fail-closed
          ``locator_runtime``; if any plan is missing, the call raises
          ``PolicyDenied`` with no selector value or DOM surfaced;
        * a ``LocatorRuntimeError`` (ambiguous match, no visible match within
          the bounded stage timeout, negative timeout) is converted to
          ``PolicyDenied`` carrying only the ``selector_key`` and a sanitized
          ``reason`` — never a candidate value or DOM text;
        * the password value is used for exactly one ``fill`` call and is not
          stored, logged, or returned;
        * no MFA control is clicked and no MFA state is polled here — the human
          completes MFA in Microsoft Authenticator and the browser observes the
          resulting state. The Next and Microsoft form Sign-in clicks are
          permitted; MFA approval remains exclusively human.
        """
        if not self.started:
            raise WorkerUnavailable(
                "operator sign-in requires a started live browser",
                operation=AUTH_OPERATOR_SUBMIT_OPERATION,
            )
        if not self.is_dedicated_persistent_profile():
            raise PolicyDenied(
                "operator sign-in requires the dedicated persistent professional browser profile",
                operation=AUTH_OPERATOR_SUBMIT_OPERATION,
            )
        if not self.auth_origin_approved():
            raise PolicyDenied(
                "operator sign-in requires the page to be on an approved "
                "Microsoft authentication origin",
                operation=AUTH_OPERATOR_SUBMIT_OPERATION,
            )
        if not common_auth_attested():
            raise PolicyDenied(
                "operator sign-in requires the common.auth UIContract fragments "
                "(common.auth.email and common.auth.password) to be attested "
                "before any sign-in field may be applied",
                operation=AUTH_OPERATOR_SUBMIT_OPERATION,
            )

        # AUTH-112: the email-entry surface MUST have been deterministically
        # resolved BEFORE any credential field is applied. This is the minimal
        # canonical fix for the bug where a rerun reached ``operator-submit``
        # directly after ``begin-signin`` (which can recreate the account
        # chooser) and submitted against a non-email-entry surface, causing an
        # email NO_MATCH. The latch is set ONLY by a successful
        # ``resolve_signin_surface`` (EMAIL_ENTRY) and cleared by any
        # ``begin_auth_signin`` (which may recreate an intermediate surface).
        # Fail closed on any other surface — never guess, never skip the
        # resolver.
        if not self._signin_surface_resolved:
            raise PolicyDenied(
                "operator sign-in requires the pre-email sign-in surface to be "
                "resolved to EMAIL_ENTRY via resolve-signin-surface before any "
                "credential is applied",
                operation=AUTH_OPERATOR_SUBMIT_OPERATION,
            )

        # Structured progression plans are loaded only from the attested
        # common.auth fragments. If any of the four declared selectors is absent
        # the flow cannot proceed; fail closed with no selector value leaked.
        email_plan = common_auth_locator_plan(EMAIL_SELECTOR_NAME)
        next_plan = common_auth_locator_plan(NEXT_SELECTOR_NAME)
        password_plan = common_auth_locator_plan(PASSWORD_SELECTOR_NAME)
        signin_plan = common_auth_locator_plan(SIGNIN_SELECTOR_NAME)
        if email_plan is None or next_plan is None or password_plan is None or signin_plan is None:
            raise PolicyDenied(
                "operator sign-in progression selectors are incomplete; refusing to "
                "guess locators",
                operation=AUTH_OPERATOR_SUBMIT_OPERATION,
            )

        page = self._require_single_auth_page()
        timeout_ms = OPERATOR_SIGNIN_STAGE_TIMEOUT_MS

        # Stage 1 — resolve and fill the email field.
        try:
            email_locator = await resolve_visible_locator(
                cast("Any", page), email_plan, timeout_ms=timeout_ms
            )
        except LocatorRuntimeError as exc:
            raise PolicyDenied(
                "operator sign-in could not resolve the email field",
                operation=AUTH_OPERATOR_SUBMIT_OPERATION,
                selector_key=exc.selector_key,
                reason=exc.reason,
            ) from None
        # Memory-only: the email is consumed for exactly one fill and then
        # dropped. It is never written to state, logs, argv, env or responses.
        await cast("Any", email_locator.locator).fill(signin.email)

        # Stage 2 — resolve and click the Next control to advance to password.
        try:
            next_locator = await resolve_visible_locator(
                cast("Any", page), next_plan, timeout_ms=timeout_ms
            )
        except LocatorRuntimeError as exc:
            raise PolicyDenied(
                "operator sign-in could not resolve the next control",
                operation=AUTH_OPERATOR_SUBMIT_OPERATION,
                selector_key=exc.selector_key,
                reason=exc.reason,
            ) from None
        await cast("Any", next_locator.locator).click()

        # Stage 3 — re-assert the auth origin after the Next navigation. The
        # click must not have escaped the approved Microsoft authentication
        # surface; otherwise stop before typing the password.
        if not self.auth_origin_approved():
            raise PolicyDenied(
                "operator sign-in lost the approved Microsoft authentication origin "
                "after the next control",
                operation=AUTH_OPERATOR_SUBMIT_OPERATION,
            )

        # Stage 4 — resolve (waiting) and fill the password field.
        try:
            password_locator = await resolve_visible_locator(
                cast("Any", page), password_plan, timeout_ms=timeout_ms
            )
        except LocatorRuntimeError as exc:
            raise PolicyDenied(
                "operator sign-in could not resolve the password field",
                operation=AUTH_OPERATOR_SUBMIT_OPERATION,
                selector_key=exc.selector_key,
                reason=exc.reason,
            ) from None
        # Memory-only: the password is consumed for exactly one fill and then
        # dropped. It is never written to state, logs, argv, env or responses.
        await cast("Any", password_locator.locator).fill(signin.password)

        # Stage 5 — resolve and click the Microsoft form Sign-in control. MFA
        # approval stays exclusively human in Microsoft Authenticator and the
        # Telegram notification channel.
        try:
            signin_locator = await resolve_visible_locator(
                cast("Any", page), signin_plan, timeout_ms=timeout_ms
            )
        except LocatorRuntimeError as exc:
            raise PolicyDenied(
                "operator sign-in could not resolve the sign-in control",
                operation=AUTH_OPERATOR_SUBMIT_OPERATION,
                selector_key=exc.selector_key,
                reason=exc.reason,
            ) from None
        await cast("Any", signin_locator.locator).click()

    def _require_single_auth_page(self) -> Any:
        """Return the single open Microsoft auth page, or fail closed."""
        if self._context is None:
            raise WorkerUnavailable(
                "no browser context available for operator sign-in",
                operation=AUTH_OPERATOR_SUBMIT_OPERATION,
            )
        pages = [p for p in self._context.pages if str(p.url)]
        if len(pages) != 1:
            raise PolicyDenied(
                "operator sign-in requires exactly one open authentication page",
                operation=AUTH_OPERATOR_SUBMIT_OPERATION,
            )
        return pages[0]

    @asynccontextmanager
    async def operation_page(self, operation: str) -> AsyncIterator[Any]:
        """Yield one fresh page and close it deterministically after the operation.

        Authentication/session state remains intentionally shared only through the
        process-owned persistent browser context. Page-local state is never reused.
        This primitive is internal infrastructure and does not expose navigation,
        selectors, scripts or browser state through the worker API.
        """
        if not self.started:
            raise WorkerUnavailable(
                "browser context is not available for an operation-scoped page",
                operation=operation,
            )

        context = self._context
        page = await context.new_page()
        try:
            yield page
        finally:
            await page.close()

    async def start(self) -> None:
        """Launch and own Playwright plus the persistent Chromium context."""
        if self.config.is_mock:
            return
        if self.started:
            return
        if self._context is not None or self._playwright is not None:
            await self.stop()

        from playwright.async_api import async_playwright  # noqa: PLC0415

        playwright = await async_playwright().start()
        context: Any = None
        try:
            self.config.profile_dir.mkdir(parents=True, exist_ok=True)
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.config.profile_dir),
                headless=self.config.headless,
                args=["--no-first-run", "--no-default-browser-check"],
            )
            await context.route("**/*", enforce_route_egress)
        finally:
            if context is None:
                await playwright.stop()

        self._playwright = playwright
        self._context = context

    async def stop(self) -> None:
        """Close Chromium and Playwright deterministically, even after partial failure."""
        context = self._context
        playwright = self._playwright
        self._context = None
        self._playwright = None

        try:
            if context is not None:
                await context.close()
        finally:
            if playwright is not None:
                await playwright.stop()

    async def read_visible_body_bounded(self, max_chars: int = 2000) -> str:
        """Read only visible body text internally, bounded and never returned.

        Narrow operator observation primitive. It is callable ONLY when:

        * the browser is started;
        * the process owns the dedicated persistent professional profile;
        * the live context is positioned on an approved Microsoft
          authentication origin; and
        * exactly ONE page is open (the single auth page).

        Any other condition fails closed: the method raises and returns nothing,
        so no URL/DOM/page text/cookie/token can leak through this surface. The
        caller (the observation endpoint) consumes the string internally for
        classification and must never log it or return it. The returned text is
        truncated to ``max_chars`` (the visible body subset) so even accidental
        capture of a credential-shaped value is bounded.
        """
        if not self.started:
            raise WorkerUnavailable(
                "operator observation requires a started live browser",
                operation=AUTH_OBSERVE_OPERATION,
            )
        if not self.is_dedicated_persistent_profile():
            raise PolicyDenied(
                "operator observation requires the dedicated persistent "
                "professional browser profile",
                operation=AUTH_OBSERVE_OPERATION,
            )
        if self._context is None:
            raise WorkerUnavailable(
                "no browser context available for operator observation",
                operation=AUTH_OBSERVE_OPERATION,
            )
        pages = [p for p in self._context.pages if str(p.url)]
        if len(pages) != 1:
            raise PolicyDenied(
                "operator observation requires exactly one open authentication page",
                operation=AUTH_OBSERVE_OPERATION,
            )
        page = pages[0]
        # The read is permitted on an approved Microsoft authentication origin
        # (the in-progress sign-in page) or on the fixed Planner Web surface
        # (the post-sign-in transition the observation must detect). A Planner
        # Web page is a *allowed* host but NOT an approved auth origin, so the
        # closed surface check is evaluated together with the auth-origin
        # approval. Any other origin fails closed.
        if not (
            self.auth_origin_approved() or is_planner_web_surface_url(str(page.url))
        ):
            raise PolicyDenied(
                "operator observation only permits the approved Microsoft "
                "authentication origin or the fixed Planner Web surface",
                operation=AUTH_OBSERVE_OPERATION,
            )
        try:
            body_text = await page.locator("body").inner_text()
        except Exception:  # noqa: BLE001 - observation must fail closed, never echo
            raise PolicyDenied(
                "operator observation could not read the visible page surface",
                operation=AUTH_OBSERVE_OPERATION,
            ) from None
        if not isinstance(body_text, str):
            return ""
        return body_text[:max_chars]

    def guard_conditional_access(self, page_text: str) -> None:
        """Raise the fail-closed blocker when Conditional Access demands enrolment."""
        if detect_conditional_access_block(page_text):
            raise BlockerConditionalAccess(
                "Conditional Access requires a managed/compliant device; "
                "enrolment and bypass are forbidden by policy"
            )
