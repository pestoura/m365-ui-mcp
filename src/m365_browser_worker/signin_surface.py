"""Operator-only deterministic classification and resolution of the
intermediate Microsoft Entra ID sign-in surface.

This module supports AUTH-109: a minimal headless resolver that lets an
operator reach the email-entry surface when Microsoft presents a deterministic
pre-email intermediate (account chooser / "use another account" prompt) instead
of the email field. It is NOT generic browser automation:

* classification is bounded and value-free. It reads only the narrow internal
  body-text primitive plus a small closed set of surface markers; it never
  returns URLs, DOM, page text, account identifiers, UPNs or tenant ids;
* the ONLY action this module may take is the fixed ``USE_ANOTHER_ACCOUNT``
  action, which clicks a control matched from a CLOSED list of exact Microsoft
  labels. It never selects a cached identity (account tiles), never types a
  password, never clicks Sign in, and never navigates by URL or locator
  string supplied by a caller;
* it fails closed on any unrecognized / ambiguous / unknown / error / consent /
  method-selection surface — it does not guess;
* all text it touches stays memory-only and is never logged or returned.

This is an operator-only, loopback-admitted, pre-attestation primitive in the
same family as ``begin-email`` (AUTH-106): it only forces the email-entry
SURFACE so the existing ``common.auth`` email/password progression (and its
attestation) can proceed. It does not widen the path to the password step or to
credential submission.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# Worker-local operation names for the operator-only sign-in surface endpoints.
# Used only for sanitized fail-closed detail/observability. The diagnose
# operation is the READ-ONLY twin of the resolve operation: same admission and
# guard chain, no click.
AUTH_RESOLVE_OPERATION = "auth_resolve_signin_surface"
AUTH_DIAGNOSE_OPERATION = "auth_diagnose_signin_surface"


class SigninSurfaceKind(StrEnum):
    """Closed classification of the live Microsoft sign-in surface.

    Only the EMAIL_ENTRY terminal surface and the deterministic pre-email
    intermediate surfaces are modeled. Anything else fails closed to
    AMBIGUOUS / UNKNOWN / ERROR rather than being guessed.
    """

    EMAIL_ENTRY = "EMAIL_ENTRY"
    ACCOUNT_CHOOSER = "ACCOUNT_CHOOSER"
    USE_ANOTHER_ACCOUNT_PROMPT = "USE_ANOTHER_ACCOUNT_PROMPT"
    PICK_AN_ACCOUNT = "PICK_AN_ACCOUNT"
    STAY_SIGNED_IN = "STAY_SIGNED_IN"
    CONSENT = "CONSENT"
    METHOD_SELECTION = "METHOD_SELECTION"
    ERROR = "ERROR"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


# Closed, sanitizable surface markers. Substrings only; never matched against
# account values (UPNs, display names, tenant strings). The language set is
# fixed (en/pt) and reject-all by default.
_SURFACE_MARKERS: dict[SigninSurfaceKind, tuple[str, ...]] = {
    SigninSurfaceKind.ACCOUNT_CHOOSER: (
        "work or school",
        "personal",
        "school or work",
        "conta profissional",
        "conta pessoal",
    ),
    SigninSurfaceKind.USE_ANOTHER_ACCOUNT_PROMPT: (
        "use another account",
        "use a different account",
        "outra conta",
        "utilizar outra conta",
        "other user",
    ),
    SigninSurfaceKind.PICK_AN_ACCOUNT: (
        "pick an account",
        "choose an account",
        "escolher uma conta",
        "selecionar uma conta",
    ),
    SigninSurfaceKind.STAY_SIGNED_IN: (
        "stay signed in",
        "mantenha",
        "manter a sessão",
        "mantenha-me",
    ),
    SigninSurfaceKind.CONSENT: (
        "accept",
        "aceitar",
        "permissions",
        "permissões",
        "consent",
    ),
    SigninSurfaceKind.METHOD_SELECTION: (
        "choose how",
        "authentication method",
        "método de autenticação",
    ),
    SigninSurfaceKind.ERROR: (
        "something went wrong",
        "incorrect",
        "não foi possível",
        "doesn't exist",
        "não existe",
        "can't verify",
        "não foi possível verificar",
    ),
}

# Email-entry terminal surface: presence of an email/phone field label.
_EMAIL_ENTRY_MARKERS = (
    "email",
    "phone",
    "skype",
    "telemóvel",
    "telefone",
    "utilizador",
    "username",
)

# ---------------------------------------------------------------------------
# Structural email-entry control presence (fail closed).
#
# Derived ONLY from the two fixed ``bootstrap_discovery`` selector keys, counted
# via the fail-closed ``locator_runtime`` — never from page text. This lets the
# classifier prefer a uniquely present, attested email-entry control over a
# text-only ``ACCOUNT_CHOOSER`` marker (AUTH-109 hardening).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmailEntryState:
    """Closed structural presence of the fixed email-entry controls.

    ``email_input_present`` / ``next_button_present`` are True only when the
    respective fixed selector key counts to exactly one candidate.
    ``ambiguous`` is True when either key counts to more than one candidate (an
    unexpected multi-control page); callers must fail closed rather than assume
    the email-entry surface.
    """

    email_input_present: bool
    next_button_present: bool
    ambiguous: bool = False


class EmailEntryControlError(Exception):
    """Structural email-entry detection could not be resolved deterministically.

    Carries only a sanitized ``reason`` category — no locator value, DOM text,
    or count leaks. Callers map this to the fail-closed ``AMBIGUOUS`` path.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"email-entry control detection failed: {reason}")


async def detect_email_entry_state(page: Any) -> EmailEntryState:
    """Structural presence of the email-entry control pair (fail closed).

    Reuses the operator-only ``bootstrap_discovery.discover_key`` primitive to
    count the CLOSED ``auth.login_email_input`` / ``auth.login_next_button``
    selector keys exactly once each. It performs NO text read, NO click, NO
    fill, NO navigation, and returns only the sanitized presence booleans.

    Returns an ``EmailEntryState`` with both controls present iff BOTH keys
    report ``UNIQUE_MATCH``. A ``NO_MATCH`` on either yields the corresponding
    flag False. Any ``AMBIGUOUS`` count (more than one candidate) sets
    ``ambiguous=True`` — the caller must fail closed, never assume the
    email-entry surface. Any detection precondition failure raises
    ``EmailEntryControlError`` (fail closed).
    """
    from m365_browser_worker.bootstrap_discovery import (
        DiscoveryResultKind,
        discover_key,
    )

    try:
        email = await discover_key(page, "auth.login_email_input")
        nxt = await discover_key(page, "auth.login_next_button")
    except Exception as exc:  # noqa: BLE001 - fail closed on any detection failure
        raise EmailEntryControlError("detection failed") from exc

    def _present(key_discovery: object) -> tuple[bool, bool]:
        kind = getattr(key_discovery, "result", None)
        if kind is DiscoveryResultKind.UNIQUE_MATCH:
            return True, False
        if kind is DiscoveryResultKind.AMBIGUOUS:
            return False, True
        return False, False

    email_present, email_ambiguous = _present(email)
    next_present, next_ambiguous = _present(nxt)
    return EmailEntryState(
        email_input_present=email_present,
        next_button_present=next_present,
        ambiguous=email_ambiguous or next_ambiguous,
    )


# Fixed, CLOSED set of exact Microsoft labels for the "use another account" control.
# No regex, no wildcard — only these precise accessible names are ever
# matched, so the resolver can never click an arbitrary or cached-identity
# (account-tile) control. This is the ONLY action the resolver may take.
USE_ANOTHER_ACCOUNT_LABELS: tuple[str, ...] = (
    "Use another account",
    "Use a different account",
    "Other user",
    "Outra conta",
    "Utilizar outra conta",
)

# Surfaces on which the fixed "use another account" action is a legitimate,
# deterministic way to reach the email-entry field (never selecting a cached
# identity). Any other surface fails closed.
_FORWARDABLE_SURFACES = (
    SigninSurfaceKind.ACCOUNT_CHOOSER,
    SigninSurfaceKind.USE_ANOTHER_ACCOUNT_PROMPT,
)


@dataclass(frozen=True)
class SurfaceClassification:
    """Sanitized classification outcome. No text or identity."""

    kind: SigninSurfaceKind
    email_entry_present: bool


@dataclass(frozen=True)
class SigninSurfaceResolution:
    """Sanitized resolver outcome. No text or identity.

    ``terminal_surface`` is the closed ``SigninSurfaceKind`` of the LAST surface
    the resolver actually encountered — the initial classification, or the
    post-forward classification after the single permitted ``CLOSED`` transition.
    It is observability-only: the resolver never acts on it, never widens any
    action set, and it carries no URL/DOM/text/identity. The external ``kind``
    sentinel is unchanged (still ``AMBIGUOUS`` on fail-closed), so callers keep
    the same fail-closed contract; ``terminal_surface`` merely reports the
    sanitized closed enum the operator would otherwise have to re-derive from a
    fresh READ-ONLY diagnose call.
    """

    kind: SigninSurfaceKind
    advanced: bool
    terminal_surface: SigninSurfaceKind = SigninSurfaceKind.UNKNOWN


def classify_signin_surface(
    page_text: str, email_entry_state: EmailEntryState | None = None
) -> SurfaceClassification:
    """Classify a bounded page-text reading into a closed surface kind.

    Never receives or returns identity. Returns ``EMAIL_ENTRY`` when an email/
    phone field label is present (the desired terminal surface); otherwise the
    first matching known intermediate/error kind; otherwise ``AMBIGUOUS`` (looks
    like a Microsoft surface but no fixed marker matched) or ``UNKNOWN`` (empty
    reading).

    When ``email_entry_state`` is supplied (the structural presence of the fixed
    email-entry control pair, derived from the ``bootstrap_discovery`` selector
    counts — never from text), a uniquely present, attested email-entry control
    pair classifies as ``EMAIL_ENTRY`` BEFORE the text-only ``ACCOUNT_CHOOSER`` /
    intermediate markers, so no unnecessary chooser click is attempted. Ambiguous
    / multiple email controls are NOT a signal (callers fail closed). Text
    markers still win on ``ERROR`` surfaces (an error page is not the email
    surface regardless of a coincidentally present field).
    """
    low = (page_text or "").lower()
    if not low.strip():
        return SurfaceClassification(SigninSurfaceKind.UNKNOWN, email_entry_present=False)

    email_entry_present = any(m in low for m in _EMAIL_ENTRY_MARKERS)

    # Error surfaces take precedence over intermediate prompts AND over any
    # coincidental structural email control (an error page is not the surface).
    if any(m in low for m in _SURFACE_MARKERS[SigninSurfaceKind.ERROR]):
        return SurfaceClassification(
            SigninSurfaceKind.ERROR, email_entry_present=email_entry_present
        )

    # Structural email-entry control presence WINS over text-only intermediate
    # markers (e.g. ``ACCOUNT_CHOOSER`` phrasing that co-exists with the live
    # email field). Only a uniquely present, attested control pair qualifies; an
    # ambiguous/multiple result is NOT used as a signal (callers fail closed).
    if (
        email_entry_state is not None
        and not email_entry_state.ambiguous
        and email_entry_state.email_input_present
        and email_entry_state.next_button_present
    ):
        return SurfaceClassification(
            SigninSurfaceKind.EMAIL_ENTRY, email_entry_present=True
        )

    for kind, markers in _SURFACE_MARKERS.items():
        if kind is SigninSurfaceKind.ERROR:
            continue
        if any(m in low for m in markers):
            return SurfaceClassification(kind, email_entry_present=email_entry_present)

    if email_entry_present:
        return SurfaceClassification(SigninSurfaceKind.EMAIL_ENTRY, email_entry_present=True)
    return SurfaceClassification(SigninSurfaceKind.AMBIGUOUS, email_entry_present=False)


async def click_use_another_account(page: Any) -> bool:
    """Click the fixed "use another account" control at most once.

    Iterates the CLOSED label set; for each label tries an accessible ``link``
    then ``button`` role and clicks the first unique match. Returns True if a
    control was clicked, False if no fixed control exists. Never clicks an
    account tile or any caller-supplied selector. Any interaction error is
    swallowed and treated as "not found" so the caller fails closed.
    """
    for label in USE_ANOTHER_ACCOUNT_LABELS:
        for role in ("link", "button"):
            try:
                locator = page.get_by_role(role, name=label)
                if await locator.count() >= 1:  # type: ignore[attr-defined]
                    await locator.first.click(timeout=5000)  # type: ignore[attr-defined]
                    return True
            except Exception:  # noqa: BLE001, S112 - fail closed, never echo
                continue
    return False


async def diagnose_signin_surface(
    page: Any, read_text: Any
) -> SurfaceClassification:
    """READ-ONLY closed classification of the live pre-email sign-in surface.

    This is the deterministic, non-mutating twin of
    ``resolve_signin_surface_to_email_entry``: it reads the bounded visible body
    text exactly once and returns ONLY the closed ``SurfaceClassification``
    (``kind`` + ``email_entry_present``). It NEVER clicks, selects, types,
    navigates, or otherwise changes the page. It is the operator-only diagnosis
    primitive that lets a run report the exact closed surface kind when the
    mutating resolver would fail closed — without guessing and without acting.

    Security shape (mirrors the resolver, minus the click):

    * classification is bounded and value-free; it never returns URLs, DOM,
      page text, account identifiers, UPNs or tenant ids;
    * no action is taken; the only possible side effect is the bounded internal
      text read already guarded by ``read_visible_body_bounded``;
    * it fails closed on an empty reading (``UNKNOWN``) like the resolver.
    """
    text = await read_text()
    try:
        state = await detect_email_entry_state(page)
    except EmailEntryControlError:
        state = None
    return classify_signin_surface(text, email_entry_state=state)


async def resolve_signin_surface_to_email_entry(
    page: Any, read_text: Any
) -> SigninSurfaceResolution:
    """Force the email-entry surface from a deterministic pre-email stage.

    ``read_text`` is a zero-argument awaitable returning bounded visible body
    text (the browser's ``read_visible_body_bounded`` primitive, already guarded
    for started browser + dedicated profile + approved origin + exactly one
    auth page). ``page`` is the single open auth page.

    Flow (fail closed on anything not deterministic):

    1. classify the current surface;
    2. if already ``EMAIL_ENTRY`` -> no action (advanced=False);
    3. if ``ACCOUNT_CHOOSER`` / ``USE_ANOTHER_ACCOUNT_PROMPT`` -> perform the
       fixed "use another account" action once, re-read, re-classify;
    4. any other surface (pick-an-account, stay-signed-in, consent, method
       selection, error, ambiguous, unknown) -> return a fail-closed sentinel so
       the caller raises ``PolicyDenied`` (never guess).

    Returns a sanitized resolution. Never returns text or identity.
    """
    text = await read_text()
    # Structural email-entry control presence (fail closed). Three outcomes:
    # * detection unavailable (error) -> fall back to the original text-only
    #   logic so the prior deterministic click path is preserved exactly;
    # * ambiguous/multiple email controls -> fail closed, never click, never
    #   guess (cannot assume the email-entry surface);
    # * uniquely present control pair -> classify as EMAIL_ENTRY (no click).
    structural_email = False
    try:
        state = await detect_email_entry_state(page)
    except EmailEntryControlError:
        state = None
    else:
        if state is not None and state.ambiguous:
            # Multiple/ambiguous email controls: cannot assume the surface.
            # Fail closed without guessing or clicking; report the text
            # classification as the observability-only terminal surface.
            text_classification = classify_signin_surface(text)
            return SigninSurfaceResolution(
                SigninSurfaceKind.AMBIGUOUS,
                advanced=False,
                terminal_surface=text_classification.kind,
            )
        structural_email = bool(
            state is not None
            and state.email_input_present
            and state.next_button_present
        )
    classification = classify_signin_surface(
        text, email_entry_state=state if structural_email else None
    )
    if classification.kind is SigninSurfaceKind.EMAIL_ENTRY:
        return SigninSurfaceResolution(
            classification.kind, advanced=False, terminal_surface=classification.kind
        )
    if classification.kind in _FORWARDABLE_SURFACES:
        clicked = await click_use_another_account(page)
        if not clicked:
            # The expected fixed control was absent: do NOT guess or fall back
            # to selecting a cached identity. Signal fail-closed. The terminal
            # surface observed is still the initial forwardable intermediate.
            return SigninSurfaceResolution(
                SigninSurfaceKind.AMBIGUOUS,
                advanced=False,
                terminal_surface=classification.kind,
            )
        text2 = await read_text()
        classification2 = classify_signin_surface(text2)
        # Post-forward classification: the LAST surface encountered. It is
        # observability-only and deliberately neutralized to AMBIGUOUS for the
        # external `kind` sentinel when it is not the email-entry field, so the
        # fail-closed contract (and surface-latch) is unchanged.
        external_kind = (
            classification2.kind
            if classification2.kind is SigninSurfaceKind.EMAIL_ENTRY
            else SigninSurfaceKind.AMBIGUOUS
        )
        return SigninSurfaceResolution(
            external_kind, advanced=True, terminal_surface=classification2.kind
        )
    # Not a deterministic forwardable surface: caller fails closed. The terminal
    # surface observed is the non-forwardable kind (sanitized closed enum only).
    return SigninSurfaceResolution(
        SigninSurfaceKind.AMBIGUOUS,
        advanced=False,
        terminal_surface=classification.kind,
    )


# ---------------------------------------------------------------------------
# AUTH-114 — deterministic post-password "Stay signed in?" (KMSI) resolution.
#
# The KMSI interstitial is a credential-free, MFA-free deterministic surface that
# Microsoft can present AFTER a successful password submit. It blocks the
# post-sign-in progression while carrying no identity choice. The ONLY action
# permitted here is a single click on ONE fixed control matched from a CLOSED set
# of exact Microsoft labels, and ONLY when that control is STRICTLY UNIQUE.
# ---------------------------------------------------------------------------

AUTH_KMSI_OPERATION = "auth_resolve_kmsi_surface"

# CLOSED set of exact Microsoft labels for the KMSI decline/dismiss control.
# No regex, no wildcard, no partial match. The decline ("No") path is preferred
# so no persistent-session preference is silently established.
KMSI_DECLINE_LABELS: tuple[str, ...] = (
    "No",
    "Não",
)

_KMSI_STAGE_TIMEOUT_MS = 5_000


async def click_kmsi_decline(page: Any) -> bool:
    """Click the fixed KMSI decline control at most once, strictly uniquely.

    Iterates the CLOSED label set; for each label tries the accessible ``button``
    then ``checkbox``-free ``link`` role and clicks ONLY when the control counts
    to EXACTLY ONE candidate. A count of zero (absent) or more than one
    (ambiguous) is never clicked — the caller fails closed. It never fills, never
    navigates, never selects an identity, and never clicks Sign in. Any
    interaction error is swallowed and treated as "not found".
    """
    for label in KMSI_DECLINE_LABELS:
        for role in ("button", "link"):
            try:
                locator = page.get_by_role(role, name=label)
                if await locator.count() != 1:
                    continue
                await locator.first.click(timeout=_KMSI_STAGE_TIMEOUT_MS)
                return True
            except Exception:  # noqa: BLE001, S112 - fail closed, never echo
                continue
    return False


async def resolve_stay_signed_in_surface(
    page: Any, read_text: Any
) -> SigninSurfaceResolution:
    """Dismiss the deterministic KMSI surface, or fail closed untouched.

    ``read_text`` is a zero-argument awaitable returning bounded visible body
    text (already guard-gated). Flow:

    1. classify the current surface (text only, value-free);
    2. if it is NOT ``STAY_SIGNED_IN`` -> return a fail-closed sentinel and take
       NO action whatsoever (never guess, never click);
    3. otherwise perform the fixed decline action once. If the strictly unique
       fixed control is absent -> fail closed without acting;
    4. re-read and re-classify; report the sanitized closed terminal surface.

    Returns only sanitized closed enums; never text, URL, or identity.
    """
    text = await read_text()
    classification = classify_signin_surface(text)
    if classification.kind is not SigninSurfaceKind.STAY_SIGNED_IN:
        return SigninSurfaceResolution(
            SigninSurfaceKind.AMBIGUOUS,
            advanced=False,
            terminal_surface=classification.kind,
        )

    clicked = await click_kmsi_decline(page)
    if not clicked:
        return SigninSurfaceResolution(
            SigninSurfaceKind.AMBIGUOUS,
            advanced=False,
            terminal_surface=SigninSurfaceKind.STAY_SIGNED_IN,
        )

    text2 = await read_text()
    classification2 = classify_signin_surface(text2)
    return SigninSurfaceResolution(
        classification2.kind, advanced=True, terminal_surface=classification2.kind
    )


# ---------------------------------------------------------------------------
# AUTH-115 — deterministic METHOD_SELECTION -> Microsoft Authenticator approval.
#
# The METHOD_SELECTION interstitial is a credential-free, MFA-free deterministic
# surface that Microsoft can present when it asks the operator to choose a
# verification method. It blocks progression while carrying no identity choice.
# The ONLY action permitted here is a single click on ONE fixed Microsoft
# Authenticator approval control matched from a CLOSED set of exact Microsoft
# labels, and ONLY when that control is STRICTLY UNIQUE across the entire closed
# set of labels AND roles (button + link).
# ---------------------------------------------------------------------------

AUTH_METHOD_SELECTION_OPERATION = "auth_resolve_method_selection_surface"

# CLOSED set of exact Microsoft labels for the Microsoft Authenticator approval
# control across en-US / pt-BR / pt-PT. No regex, no wildcard, no partial match.
# The fourth English variant is a DISTINCT closed member (the longer
# "Microsoft Authenticator" phrasing the live 503 surface can render), not a
# duplicate of the shorter en-US label.
AUTHENTICATOR_METHOD_LABELS: tuple[str, ...] = (
    "Approve a request on my Authenticator app",
    "Aprovar uma solicitação no meu aplicativo Authenticator",
    "Aprovar um pedido na minha aplicação de Microsoft Authenticator",
    "Approve a request on my Microsoft Authenticator app",
    "Send notification",
    "Enviar notificação",
)


async def click_authenticator_method(page: Any) -> bool:
    """Click the fixed Microsoft Authenticator approval control at most once.

    STRICTER-than-KMSI global uniqueness: every candidate control across the
    entire CLOSED label set is counted via
    ``page.get_by_text(label, exact=True).count()`` (awaited for every label),
    and the candidate TOTAL across the entire closed set must equal EXACTLY one.
    A single label that itself counts to exactly one is NOT sufficient if any
    other closed label also matches (a ``1 + 1`` split yields a global total of
    2 and is rejected, as is any per-label count of 2 or more).

    The control is matched ONLY by exact text — never by ARIA role
    (button/link) — per the deployed contract. Only when the global total
    equals exactly one is the sole locator clicked exactly once. Zero or
    more-than-one candidates never clicks. No regex, wildcard,
    ``first``-of-many, or caller-supplied selector. Any locator/count exception
    fails closed (returns False); nothing is ever logged/echoed. It performs no
    fill/type/goto/press.
    """
    total = 0
    sole_locator = None
    try:
        for label in AUTHENTICATOR_METHOD_LABELS:
            locator = page.get_by_text(label, exact=True)
            try:
                count = await locator.count()
            except Exception:  # noqa: BLE001 - fail closed on any count error
                return False
            if count:
                total += count
                if total == 1 and count == 1:
                    sole_locator = locator
    except Exception:  # noqa: BLE001 - fail closed on any iteration error
        return False

    if total != 1 or sole_locator is None:
        return False
    try:
        await sole_locator.first.click(timeout=5000)
    except Exception:  # noqa: BLE001 - fail closed, never echo
        return False
    return True


# CLOSED set of exact Microsoft labels for the "Sign-in options" reveal control
# on the initial METHOD_SELECTION surface that renders ONLY "Sign in" +
# "Sign-in options" (no directly visible Authenticator control). Exact text
# only — no regex, no wildcard, no partial match. The pt-PT variant is the
# label the verified live surface renders.
SIGNIN_OPTIONS_LABELS: tuple[str, ...] = (
    "Sign-in options",
    "Other ways to sign in",
    "Sign in another way",
    "Use a different verification option",
    "Opções de início de sessão",
)


async def click_signin_options(page: Any) -> bool:
    """Click the fixed "Sign-in options" reveal control at most once.

    STRICT global uniqueness (same guarantee as ``click_authenticator_method``):
    every candidate control across the entire CLOSED label set is counted via
    ``page.get_by_text(label, exact=True)`` (awaited for every label) and the
    global TOTAL across the entire closed set must equal EXACTLY one. A single
    label counting to exactly one is NOT sufficient if the other closed label
    also matches (a ``1 + 1`` split yields a global total of 2 and is rejected,
    as is any per-label count of 2 or more).

    Matched ONLY by exact text — never by ARIA role (button/link). Only when the
    global total equals exactly one is the sole locator clicked exactly once.
    Zero or more-than-one candidates never clicks. No regex, wildcard,
    ``first``-of-many, or caller-supplied selector. Any locator/count exception
    fails closed (returns False); nothing is ever logged/echoed. It performs no
    fill/type/goto/press.
    """
    total = 0
    sole_locator = None
    try:
        for label in SIGNIN_OPTIONS_LABELS:
            locator = page.get_by_text(label, exact=True)
            try:
                count = await locator.count()
            except Exception:  # noqa: BLE001 - fail closed on any count error
                return False
            if count:
                total += count
                if total == 1 and count == 1:
                    sole_locator = locator
    except Exception:  # noqa: BLE001 - fail closed on any iteration error
        return False

    if total != 1 or sole_locator is None:
        return False
    try:
        await sole_locator.first.click(timeout=5000)
    except Exception:  # noqa: BLE001 - fail closed, never echo
        return False
    return True


# ---------------------------------------------------------------------------
# TEMPORARY AUTH-115 diagnostics (remove after root-cause is confirmed).
#
# Minimal, value-free instrumentation to diagnose a METHOD_SELECTION surface
# that does not resolve to the expected Authenticator control. It never logs
# the raw page body: only closed authentication-candidate lines survive, and
# those are redacted of emails / URLs / GUIDs / long digit runs.
# ---------------------------------------------------------------------------

# Closed authentication terms (EN/PT) used to keep only candidate lines.
_METHOD_SELECTION_CANDIDATE_TERMS: tuple[str, ...] = (
    "authenticator",
    "notification",
    "notificação",
    "approve",
    "aprovar",
    "request",
    "pedido",
    "solicitação",
    "verification",
    "verificação",
    "sign",
    "início",
    "method",
    "método",
)

async def resolve_method_selection_surface(
    page: Any, read_text: Any
) -> SigninSurfaceResolution:
    """Resolve a closed Microsoft Authenticator method-selection flow."""
    text = await read_text()
    classification = classify_signin_surface(text)

    if classification.kind is SigninSurfaceKind.METHOD_SELECTION:
        clicked_direct = await click_authenticator_method(page)
        if clicked_direct:
            final_text = await read_text()
            final_classification = classify_signin_surface(final_text)
            return SigninSurfaceResolution(
                final_classification.kind,
                advanced=True,
                terminal_surface=final_classification.kind,
            )
    elif classification.kind is not SigninSurfaceKind.AMBIGUOUS:
        return SigninSurfaceResolution(
            SigninSurfaceKind.AMBIGUOUS,
            advanced=False,
            terminal_surface=classification.kind,
        )

    clicked_options = await click_signin_options(page)
    if not clicked_options:
        return SigninSurfaceResolution(
            SigninSurfaceKind.AMBIGUOUS,
            advanced=False,
            terminal_surface=classification.kind,
        )

    await page.wait_for_timeout(1000)
    text2 = await read_text()
    classification2 = classify_signin_surface(text2)
    if classification2.kind is not SigninSurfaceKind.METHOD_SELECTION:
        return SigninSurfaceResolution(
            SigninSurfaceKind.AMBIGUOUS,
            advanced=False,
            terminal_surface=classification2.kind,
        )

    clicked = await click_authenticator_method(page)
    if not clicked:
        return SigninSurfaceResolution(
            SigninSurfaceKind.AMBIGUOUS,
            advanced=False,
            terminal_surface=classification2.kind,
        )

    text3 = await read_text()
    classification3 = classify_signin_surface(text3)
    return SigninSurfaceResolution(
        classification3.kind,
        advanced=True,
        terminal_surface=classification3.kind,
    )


__all__ = [
    "AUTH_KMSI_OPERATION",
    "AUTH_METHOD_SELECTION_OPERATION",
    "AUTH_RESOLVE_OPERATION",
    "AUTHENTICATOR_METHOD_LABELS",
    "SIGNIN_OPTIONS_LABELS",
    "KMSI_DECLINE_LABELS",
    "click_authenticator_method",
    "click_signin_options",
    "click_kmsi_decline",
    "resolve_method_selection_surface",
    "resolve_stay_signed_in_surface",
    "SigninSurfaceKind",
    "SurfaceClassification",
    "SigninSurfaceResolution",
    "USE_ANOTHER_ACCOUNT_LABELS",
    "classify_signin_surface",
    "click_use_another_account",
    "diagnose_signin_surface",
    "resolve_signin_surface_to_email_entry",
    "EmailEntryState",
    "EmailEntryControlError",
    "detect_email_entry_state",
]
