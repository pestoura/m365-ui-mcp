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

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

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
        "sign-in options",
        "opções de início",
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

# Fixed, CLOSED set of exact Microsoft labels for the "use another account"
# control. No regex, no wildcard — only these precise accessible names are ever
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


def classify_signin_surface(page_text: str) -> SurfaceClassification:
    """Classify a bounded page-text reading into a closed surface kind.

    Never receives or returns identity. Returns ``EMAIL_ENTRY`` when an email/
    phone field label is present (the desired terminal surface); otherwise the
    first matching known intermediate/error kind; otherwise ``AMBIGUOUS`` (looks
    like a Microsoft surface but no fixed marker matched) or ``UNKNOWN`` (empty
    reading).
    """
    low = (page_text or "").lower()
    if not low.strip():
        return SurfaceClassification(SigninSurfaceKind.UNKNOWN, email_entry_present=False)

    email_entry_present = any(m in low for m in _EMAIL_ENTRY_MARKERS)

    # Error surfaces take precedence over intermediate prompts.
    if any(m in low for m in _SURFACE_MARKERS[SigninSurfaceKind.ERROR]):
        return SurfaceClassification(
            SigninSurfaceKind.ERROR, email_entry_present=email_entry_present
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
    return classify_signin_surface(text)


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
    classification = classify_signin_surface(text)
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


__all__ = [
    "AUTH_RESOLVE_OPERATION",
    "SigninSurfaceKind",
    "SurfaceClassification",
    "SigninSurfaceResolution",
    "USE_ANOTHER_ACCOUNT_LABELS",
    "classify_signin_surface",
    "click_use_another_account",
    "diagnose_signin_surface",
    "resolve_signin_surface_to_email_entry",
]
