"""Application-neutral Playwright persistent-browser boundary.

This module owns the browser/profile lifecycle primitives used by Microsoft 365
application adapters. It deliberately exposes no generic click/selector/script
surface and never exports authenticated session material.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from m365_browser_worker.auth_bootstrap import (
    AuthOriginStatus,
    _is_approved_auth_origin,
    auth_origin_status,
)
from m365_browser_worker.bootstrap_navigation import (
    AUTH_BEGIN_EMAIL_STAGE_OPERATION,
    AUTH_BEGIN_SIGNIN_OPERATION,
    AUTH_BOOTSTRAP_NAVIGATE_OPERATION,
    AUTH_OBSERVE_OPERATION,
    AUTH_OPERATOR_SUBMIT_OPERATION,
    MICROSOFT_AUTH_BOOTSTRAP_URL,
    classify_begin_signin_source,
    evaluate_bootstrap_target,
    evaluate_microsoft_auth_target,
    is_permitted_begin_signin_source,
    is_planner_web_surface_url,
    is_reusable_bootstrap_page,
    resolve_planner_web_bootstrap_url,
)
from m365_browser_worker.egress import enforce_route_egress
from m365_browser_worker.locator_runtime import (
    LocatorRuntimeError,
    resolve_visible_locator,
)
from m365_browser_worker.operator_signin import (
    COMBINED_FORM_PASSWORD_ID,
    COMBINED_FORM_SUBMIT_ID,
    EMAIL_SELECTOR_NAME,
    NEXT_SELECTOR_NAME,
    PASSWORD_SELECTOR_NAME,
    SIGNIN_SELECTOR_NAME,
    OperatorSignInInput,
    common_auth_locator_plan,
    detect_combined_signin_form,
    submit_combined_signin_form,
)
from m365_browser_worker.signin_surface import (
    AUTH_DIAGNOSE_OPERATION,
    AUTH_KMSI_OPERATION,
    AUTH_METHOD_SELECTION_OPERATION,
    AUTH_RESOLVE_OPERATION,
    SigninSurfaceKind,
    SurfaceClassification,
    classify_signin_surface,
    resolve_method_selection_surface,
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

# AUTH-118 popup-aware begin-signin bounds. After a Sign In click spawns a
# popup window, the popup's URL may sit on ``about:blank`` for a moment before
# committing to a Microsoft authentication origin. We wait a SHORT bounded window
# (sum ~0.3s) polling the popup URL via the closed ``_is_approved_auth_origin``
# check — never a long poll, never an invented host, never raw text/DOM.
_POPUP_APPROVED_ORIGIN_WAIT_ITERS = 6
_POPUP_APPROVED_ORIGIN_WAIT_S = 0.05

# AUTH-118 delayed-popup stabilization after the Sign In click. A popup window
# may be created ASYNCHRONOUSLY by the browser/Planner Web only after the click
# coroutine has already resolved. Before computing new_pages we poll
# context.pages ONLY by object identity over a SHORT bounded window
# (total <=0.5s) so late popups are observed without ever reading a URL,
# text, DOM or value. No page guard is relaxed; the existing popup logic
# below is reused exactly.
_POPUP_CREATION_STABILIZE_ITERS = 10
_POPUP_CREATION_STABILIZE_WAIT_S = 0.03

# Bounded post-submit surface-transition verification for the sequential path.
# After the Microsoft form Sign-in click, the fixed password input (id=i0118)
# and submit control (id=idSIButton9) must disappear — the surface transitioned
# to the next auth step. A single non-unique sample is NOT enough: a transient
# dip (control momentarily absent then back to uniquely present) must not be
# accepted as a transition. Require a small consecutive streak of
# ``_SUBMIT_TRANSITION_ABSENCE_STREAK`` samples where EITHER control is absent or
# non-unique before concluding the surface transitioned; a return to uniquely
# present resets the streak. If the stable-absence streak is never reached, the
# sign-in did NOT progress (observed METHOD_SELECTION / reauth stall) and
# submit_operator_signin fails closed instead of reporting success. Only control
# counts are read; no text/DOM read, no field value, no URL logged. Mirrors the
# fixed control ids already used by ``detect_combined_signin_form``. Total wait is
# ~0.25s (<=1s budget).
_SUBMIT_TRANSITION_WAIT_ITERS = 5
_SUBMIT_TRANSITION_WAIT_S = 0.05
_SUBMIT_TRANSITION_ABSENCE_STREAK = 3

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

    def planner_web_surface_present(self) -> bool:
        """Return True when the dedicated profile sits on the fixed Planner Web surface.

        The ONLY positive proof that a professional session is authenticated is
        the post-MFA landing surface (the fixed Planner Web target). The raw
        page URL is reduced to the closed ``is_planner_web_surface_url``
        classification and never returned, so no URL, DOM text, cookie, token,
        UPN or tenant id leaves this method. Neutral placeholders, intermediate
        auth interstitials and unrecognized pages are reported as False (the
        absence of a login form is NOT treated as authenticated).
        """
        if not self.started:
            return False
        pages = [p for p in self._context.pages if str(p.url)]
        if len(pages) != 1:
            # Exactly one open page is required: an ambiguous multi-page
            # topology must never be accepted as the authenticated surface.
            return False
        return is_planner_web_surface_url(str(pages[0].url))

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

        # AUTH-116: deterministic page lifecycle for the dedicated operator
        # worker. The persistent professional profile RESTORES its Planner Web
        # tab on launch, so the live context commonly already holds exactly one
        # ``planner_web`` page (a worker-OWNED, process-owned persistent-profile
        # tab). Reuse that SAME page for the bootstrap navigation instead of
        # opening a second one — otherwise the context accumulates two pages and
        # the later single-page guard (``_require_single_auth_page``) fails with
        # "requires exactly one open authentication page", blocking
        # begin-signin / operator-submit / observe. A neutral placeholder page is
        # likewise reused (unchanged behaviour). Fail closed on an AMBIGUOUS
        # topology (multiple planner_web or multiple neutral pages) rather than
        # guessing which page to hijack. An arbitrary/external non-approved page
        # is NEVER closed, hijacked or selected: the worker opens its own page
        # and leaves the external page untouched, preserving fail-closed page
        # ownership. The URL is reduced to the closed host classification and is
        # never returned to a caller.
        existing_planner_web: Any = None
        existing_neutral: Any = None
        for candidate in context.pages:
            raw = str(candidate.url)
            if is_planner_web_surface_url(raw):
                if existing_planner_web is not None:
                    # Multiple distinct planner_web tabs: ambiguous, fail closed.
                    raise PolicyDenied(
                        "authentication bootstrap refuses an ambiguous "
                        "topology with multiple Planner Web pages open",
                        operation=AUTH_BOOTSTRAP_NAVIGATE_OPERATION,
                    )
                existing_planner_web = candidate
            elif is_reusable_bootstrap_page(raw):
                if existing_neutral is not None:
                    # Multiple neutral placeholders: ambiguous, fail closed.
                    raise PolicyDenied(
                        "authentication bootstrap refuses an ambiguous "
                        "topology with multiple neutral pages open",
                        operation=AUTH_BOOTSTRAP_NAVIGATE_OPERATION,
                    )
                existing_neutral = candidate

        if existing_planner_web is not None:
            page = existing_planner_web
        elif existing_neutral is not None:
            page = existing_neutral
        else:
            # No worker-owned reusable page on an approved source. Open exactly
            # one new page; an arbitrary/external page (if any) is left untouched.
            page = await context.new_page()

        # Exactly one navigation per operator call; no retry loop.
        await page.goto(resolve_planner_web_bootstrap_url())

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

        planner_web_selected = existing_planner_web is not None
        if planner_web_selected:
            page = existing_planner_web
        elif existing_neutral is not None:
            page = existing_neutral
        else:
            # No reusable page on an approved source. The source classifier
            # already accepted this context (e.g. an existing approved Microsoft
            # auth origin, or no pages yet), so open exactly one new page.
            page = await context.new_page()

        # The page the post-click landing gate / surface reset applies to.
        # Defaults to the navigated/clicked page; becomes the approved popup
        # when the source Planner Web page is closed for an approved popup.
        final_page: Any = page

        if not planner_web_selected:
            # Exactly one fixed navigation for neutral/new-page bootstrap; no retry loop.
            await page.goto(MICROSOFT_AUTH_BOOTSTRAP_URL)
        else:
            sign_in = page.get_by_role("button", name="Sign In", exact=True)
            sign_in_count = await sign_in.count()
            if sign_in_count != 1:
                raise PolicyDenied(
                    "begin sign-in requires exactly one Planner Web Sign In control",
                    operation=AUTH_BEGIN_SIGNIN_OPERATION,
                )
            # AUTH-118 popup-aware begin-signin. Snapshot the live context pages
            # by object identity BEFORE the click so we can detect ONLY the
            # pages the click actually spawns (a popup window). Pre-existing
            # pages are never closed/hijacked arbitrarily; only newly-spawned
            # pages are evaluated and closed on policy failure. The source
            # Planner Web page remains the click target throughout.
            before_pages = set(id(p) for p in context.pages)
            await sign_in.click()
            # AUTH-118 delayed-popup stabilization: after the Sign In click
            # returns, a popup window may be created ASYNCHRONOUSLY by the
            # browser/Planner Web only after the click coroutine has resolved.
            # Snapshotting context.pages synchronously here would miss a late
            # popup and misclassify the flow as same-tab. Perform a SHORT bounded
            # wait that polls context.pages ONLY by object identity (never a
            # URL/text/DOM/value read) so newly-spawned popup objects are
            # observed before new_pages is computed. Total added wait is bounded
            # (<=0.5s) and the existing popup guards below are reused exactly.
            stabilized = list(context.pages)
            for _ in range(_POPUP_CREATION_STABILIZE_ITERS):
                await asyncio.sleep(_POPUP_CREATION_STABILIZE_WAIT_S)
                current = list(context.pages)
                if set(id(p) for p in current) == set(id(p) for p in stabilized):
                    break
                stabilized = current
            after_pages = stabilized
            new_pages = [p for p in after_pages if id(p) not in before_pages]

            if len(new_pages) == 0:
                # Same-tab flow unchanged: the Sign In click performed an
                # in-place navigation on the source page. Preserve exactly the
                # existing same-tab behavior + landing gate below.
                pass
            elif len(new_pages) == 1:
                popup = new_pages[0]
                if await self._popup_reaches_approved_auth_origin(popup):
                    # Approved popup: close ONLY the source Planner Web page and
                    # leave the popup as the single page for the next steps.
                    await page.close()
                    final_page = popup
                else:
                    # Unapproved popup surface: close ONLY the new popup and
                    # fail closed; the source remains untouched.
                    await popup.close()
                    raise PolicyDenied(
                        "begin sign-in popup did not reach an approved "
                        "Microsoft authentication origin; refusing",
                        operation=AUTH_BEGIN_SIGNIN_OPERATION,
                    )
            else:
                # More than one new page spawned: ambiguous topology. Close ONLY
                # the newly-spawned pages and fail closed; the source remains.
                for np in new_pages:
                    await np.close()
                raise PolicyDenied(
                    "begin sign-in refused an ambiguous multi-popup topology",
                    operation=AUTH_BEGIN_SIGNIN_OPERATION,
                )

        # AUTH-117: once begin-signin has chosen the final landing page and
        # verified it sits on an approved Microsoft auth origin, the flow invokes
        # ``_maybe_force_reauth_on_landing`` on that page exactly once (see the
        # landing-gate block below). The native Planner Web OAuth
        # redirect_uri/state/PKCE query is preserved and only ``prompt=login`` is
        # set/replaced; the origin is re-validated after the eventual navigation.

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
        await self._require_landed_on_approved_auth_origin(final_page)

        # AUTH-117: force reauthentication on the landing page so a remembered
        # session does not bypass the combined credential form. This preserves
        # the Planner-generated OAuth redirect_uri/state/PKCE exactly and only
        # sets prompt=login. Fails closed inside the helper (no navigation on a
        # non-approved origin or an origin without a query string).
        await self._maybe_force_reauth_on_landing(final_page)

        # Re-validate the landing origin after the eventual same-page
        # reauthentication navigation; fails closed if the page left the
        # approved Microsoft auth origin.
        await self._require_landed_on_approved_auth_origin(final_page)

    async def _maybe_force_reauth_on_landing(self, page: Any) -> None:
        """Force reauthentication when the combined credential form is absent.

        AUTH-117 (minimal, fail-closed). After begin-signin lands on a Microsoft
        OAuth authorization URL, the persistent professional profile may be
        silently routed to a remembered-session surface (Sign-in options /
        passkey) instead of the credential form. We must force reauthentication
        while PRESERVING the Planner-generated OAuth redirect_uri / state / PKCE.

        Behavior:

        * first check the closed combined-form structural ids (i0116 + i0118 +
          idSIButton9) WITHOUT reading any value;
        * if all three are uniquely present -> return normally, no extra goto;
        * if they are NOT present AND the current page URL is a Microsoft OAuth
          authorization URL (an approved auth origin host with a non-empty query
          string) -> parse the CURRENT URL locally, preserve every existing
          query parameter/value exactly, set/replace ONLY
          ``prompt=login``, and
          navigate the SAME page once to that modified URL;
        * otherwise (non-approved origin, or an approved origin with no query
          string) -> fail closed: no navigation, no logging, no URL/value return;
        * never loops or retries; never uses Sign-in options; never touches
          credentials here.

        The URL and its query values are reduced to a closed host/query-shape
        decision and are never logged, returned, or placed in any error. Only
        the sanitized boolean outcome of the structural form check leaves this
        method.
        """
        from m365_browser_worker.auth_bootstrap import _is_approved_auth_origin
        from m365_browser_worker.operator_signin import (
            detect_combined_signin_form,
        )

        # Closed structural check only; never reads field values.
        form_present = await detect_combined_signin_form(page)
        if form_present:
            # Combined credential form already available: no extra navigation.
            return

        # Form absent: only force reauth on an approved Microsoft OAuth
        # authorization URL that already carries a query string (so we can
        # preserve the Planner-generated redirect_uri/state/PKCE exactly).
        raw = str(getattr(page, "url", "") or "")
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower().rstrip(".")
        if not parsed.query or not _is_approved_auth_origin(host):
            # Fail closed: non-approved origin, or an approved origin without a
            # query string. No navigation, no URL/value leak.
            return

        # Preserve every existing query parameter/value; set/replace ONLY
        # prompt=login (forces credential re-entry and interrupts SSO, ensuring
        # the combined sign-in form is presented rather than a remembered
        # session). The query string is reconstructed locally from the
        # parsed current URL; no value is logged or returned.
        params = parse_qsl(parsed.query, keep_blank_values=True)
        filtered = [(k, v) for (k, v) in params if k.lower() != "prompt"]
        filtered.append(("prompt", "login"))
        new_query = urlencode(filtered)
        rebuilt = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment)
        )
        # Exactly one same-page navigation; no retry loop.
        await page.goto(rebuilt)

    async def _popup_reaches_approved_auth_origin(self, popup: Any) -> bool:
        """Boundedly wait for a popup to attain an approved Microsoft auth origin.

        AUTH-118 (popup-aware begin-signin). A Sign In click MAY spawn a popup
        window whose URL initially is ``about:blank`` and only later commits to
        the Microsoft authentication origin. This helper performs a SHORT bounded
        wait (never a long poll) for the popup's URL to reach an auth Microsoft
        origin already approved by the existing closed ``auth_origin_status``
        function — it does NOT invent hosts and never reads raw text/DOM. If the
        popup leaves ``about:blank`` but lands on a non-approved origin, or the
        bounded wait elapses without an approved origin, it returns False so the
        caller closes ONLY the popup and fails closed.

        No wildcard origin, identity selection, credential or MFA is involved.
        The URL is reduced to the closed ``auth_origin_status`` classification
        and is never returned to a caller.
        """
        from urllib.parse import urlsplit

        # Bound the wait: a popup either commits to an auth origin quickly or it
        # never does. We never block the operator flow for long.
        for _ in range(_POPUP_APPROVED_ORIGIN_WAIT_ITERS):
            raw = str(getattr(popup, "url", "") or "")
            host = (urlsplit(raw).hostname or "").lower().rstrip(".")
            if raw.startswith("https://") and _is_approved_auth_origin(host):
                return True
            await asyncio.sleep(_POPUP_APPROVED_ORIGIN_WAIT_S)
        return False

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

    async def resolve_method_selection_surface(self) -> SigninSurfaceKind:
        """Operator-only deterministic METHOD_SELECTION -> Microsoft
        Authenticator approval resolution (AUTH-115).

        Resolves the credential-free, MFA-free Microsoft Entra ID method-
        selection interstitial by clicking ONLY the fixed Microsoft
        Authenticator approval control, and ONLY when that control is strictly
        unique (exactly one candidate across the entire CLOSED label set AND
        both button/link roles).

        Fail-closed contract:

        * guard chain identical to ``resolve_kmsi_surface`` (started live
          browser, dedicated persistent professional profile, approved Microsoft
          authentication origin, exactly one open auth page);
        * NO credential is typed, NO cached identity is selected, NO Sign in is
          clicked, NO URL/locator navigation is performed;
        * any non-``METHOD_SELECTION`` surface, or an absent/ambiguous fixed
          control (global candidate count != 1), raises ``PolicyDenied`` with
          only the sanitized closed terminal-surface enum;
        * bounded visible body text is read internally and never logged/returned.

        Returns the sanitized closed post-resolution ``SigninSurfaceKind``.
        """
        if not self.started:
            raise WorkerUnavailable(
                "METHOD_SELECTION surface resolution requires a started live browser",
                operation=AUTH_METHOD_SELECTION_OPERATION,
            )
        if not self.is_dedicated_persistent_profile():
            raise PolicyDenied(
                "METHOD_SELECTION surface resolution requires the dedicated "
                "persistent professional browser profile",
                operation=AUTH_METHOD_SELECTION_OPERATION,
            )
        if not self.auth_origin_approved():
            raise PolicyDenied(
                "METHOD_SELECTION surface resolution requires the page to be on "
                "an approved Microsoft authentication origin",
                operation=AUTH_METHOD_SELECTION_OPERATION,
            )

        page = self._require_single_auth_page()

        async def _read() -> str:
            return await self.read_visible_body_bounded(max_chars=2000)

        resolution = await resolve_method_selection_surface(page, _read)
        if not resolution.advanced:
            raise PolicyDenied(
                "sign-in surface is not a deterministic METHOD_SELECTION stage; "
                "manual operator intervention required",
                operation=AUTH_METHOD_SELECTION_OPERATION,
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

        page = self._require_single_auth_page()

        # OBSERVED combined Entra ID form (email + password + submit on one
        # page). Probe the fixed control ids deterministically; when they are
        # ALL uniquely present, submit the combined form directly. This is the
        # minimal change for the observed combined form; the incumbent
        # sequential email -> Next -> password -> Sign-in flow below remains the
        # fallback when the combined form is not uniquely present. Only the fixed
        # ids are used; no text read, no navigation, no selector guessing. Any
        # detection failure silently falls through to the sequential path.
        combined_present = False
        try:
            combined_present = await detect_combined_signin_form(page)
        except Exception:  # noqa: BLE001 - fail closed: prefer sequential fallback
            combined_present = False
        if combined_present:
            await submit_combined_signin_form(page, signin)
            # The combined submit MUST NOT be trusted blindly. Either the
            # password surface transitions away stably (success), or the
            # OBSERVED password-only surface remains/reappears (password input
            # + Sign-in uniquely present) and the SAME call continues with the
            # password tail ONLY: re-fill the fixed password id, click the fixed
            # Sign-in id once, and require the same stable transition. The
            # email/Next stage is never rerun. Only the fixed control ids and
            # locator counts are used; no text/value/URL/DOM read.
            if await self._password_surface_transitioned(page):
                return
            page_locator = getattr(page, "locator", None)
            if page_locator is None:
                raise WorkerUnavailable(
                    "operator sign-in cannot verify the combined-form password "
                    "tail without a page locator primitive",
                    operation=AUTH_OPERATOR_SUBMIT_OPERATION,
                )
            # Memory-only: the password is consumed for exactly one fill and
            # then dropped. It is never stored, logged, or returned.
            await page_locator(f"#{COMBINED_FORM_PASSWORD_ID}").fill(signin.password)
            await page_locator(f"#{COMBINED_FORM_SUBMIT_ID}").click()
            if await self._password_surface_transitioned(page):
                return
            raise PolicyDenied(
                "operator sign-in password-only tail did not advance the "
                "authentication surface; the sign-in form remained present "
                "after submission",
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

        # Post-click surface-transition verification (sequential path). Reuses
        # the SAME stable-transition helper as the combined password-only tail
        # so both paths share exactly one implementation. If the surface did not
        # transition, fail closed instead of reporting success.
        if not await self._password_surface_transitioned(page):
            raise PolicyDenied(
                "operator sign-in click did not advance the authentication "
                "surface; the sign-in form remained present after submission",
                operation=AUTH_OPERATOR_SUBMIT_OPERATION,
            )

    async def _password_surface_transitioned(self, page: Any) -> bool:
        """Return whether the fixed password surface transitioned away stably.

        Shared by the sequential Sign-in path and the combined password-only
        tail. The fixed password input (id=i0118) and submit control
        (id=idSIButton9) must be absent/non-unique for a small consecutive
        sample streak before the transition is accepted (a transient dip that
        returns to uniquely present resets the streak). Only control counts are
        read -- no text/DOM read, no field value, no URL logged or returned.
        Reuses the exact fixed combined-form control ids already imported for
        ``detect_combined_signin_form``.

        Returns ``True`` iff the stable-absence streak is reached within the
        bounded wait; ``False`` otherwise (including any count error, which is
        never accepted as a transition). A surface object lacking the
        ``locator`` primitive (non-Playwright harness) cannot be verified and is
        treated as already transitioned rather than inventing a control check.
        """
        page_locator = getattr(page, "locator", None)
        if page_locator is None:
            return True
        try:
            absent_streak = 0
            for _ in range(_SUBMIT_TRANSITION_WAIT_ITERS):
                try:
                    pw_count = await page_locator(
                        f"#{COMBINED_FORM_PASSWORD_ID}"
                    ).count()
                    sb_count = await page_locator(
                        f"#{COMBINED_FORM_SUBMIT_ID}"
                    ).count()
                except Exception:  # noqa: BLE001 - surface not provably gone
                    # A count error neither proves the surface gone nor
                    # present; do not accept a transient transition. Stop
                    # sampling and report no stable transition.
                    return False
                if pw_count != 1 or sb_count != 1:
                    # Either control is no longer uniquely present: this is a
                    # candidate transition sample. Require a small consecutive
                    # streak before concluding the surface transitioned; a
                    # return to uniquely present resets the streak so a
                    # transient dip is never accepted as a stable transition.
                    absent_streak += 1
                else:
                    # A control returned to uniquely present: the earlier
                    # absence was transient; reset the streak.
                    absent_streak = 0
                await asyncio.sleep(_SUBMIT_TRANSITION_WAIT_S)
        except Exception:  # noqa: BLE001 - any wait failure fails closed
            return False
        return absent_streak >= _SUBMIT_TRANSITION_ABSENCE_STREAK

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
