"""Narrowly-scoped operator sign-in input contract for the browser worker.

This module defines the ONLY credential shape the worker may receive from the
operator-local encrypted-store helper. It is memory-only and MUST never be
persisted, logged, placed in argv/env/state, or exposed in a response.

Fail-closed invariants:

* Exactly two fields are permitted: ``email`` and ``password``. Any other key is
  rejected so a caller cannot smuggle extra credential/material fields.
* No generic DOM primitive, no arbitrary URL, and no Graph surface is reachable
  from this input. Only the two sign-in fields declared by ``common.auth``
  (``auth.login_email_input``, ``auth.login_password_input``) may be applied, and
  only when those locators are attested. Until then the worker fails closed and
  types nothing.
* Progression selector plans (email -> next -> password -> sign in) are loaded
  from the shipped ``common.auth.email`` / ``common.auth.password`` fragments
  WITHOUT requiring attestation, so bootstrap discovery can enumerate them for an
  UNVERIFIED_LIVE flow. Loading is fail-closed: only the four declared progression
  keys are accepted, and the caller remains responsible for the attestation gate
  before any fill.

Requirement IDs: AUTH-099 (notification), AUTH-100 (fail-closed MFA), AUTH-101
(encrypted-store operator sign-in automation, superseding "human types password").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from m365_browser_worker.locators import LocatorPlan, locator_plan_from_metadata

# The ONLY sign-in fields the worker is permitted to apply. Both must be declared
# by the ``common.auth`` UIContract fragments. No submit/locator/Graph field is
# ever accepted here.
ALLOWED_SIGNIN_FIELDS = ("email", "password")

# Declared ``common.auth`` selectors the worker may fill (memory-only values).
EMAIL_SELECTOR_NAME = "auth.login_email_input"
PASSWORD_SELECTOR_NAME = "auth.login_password_input"  # noqa: S105 - selector name, not a secret

# Progression selectors of the Microsoft Entra ID sign-in flow. All four are
# declared by the ``common.auth.email`` / ``common.auth.password`` fragments;
# only these may be loaded as plans.
NEXT_SELECTOR_NAME = "auth.login_next_button"
SIGNIN_SELECTOR_NAME = "auth.login_signin_button"

# ---------------------------------------------------------------------------
# OBSERVED combined Entra ID sign-in form (minimal production change).
#
# Microsoft can present the email field, password field and submit control on a
# SINGLE page (the combined form) instead of the sequential email -> Next ->
# password -> Sign-in flow. The fixed control ids of that observed form are
# used ONLY to detect and submit it deterministically. They are NOT attestation
# selectors and they do NOT widen the credential contract: the values applied
# are still exactly the two memory-only ``email`` / ``password`` fields, and the
# incumbent sequential flow remains the fallback when the combined form is not
# uniquely present. No regex, no wildcard, no caller-supplied selector.
# ---------------------------------------------------------------------------

# Email input: id=i0116, type=email, placeholder "Email or phone".
COMBINED_FORM_EMAIL_ID = "i0116"
# Password input: id=i0118, type=password.
COMBINED_FORM_PASSWORD_ID = "i0118"  # noqa: S105
# Submit control: id=idSIButton9, type=submit ("Sign in").
COMBINED_FORM_SUBMIT_ID = "idSIButton9"

# Bounded timeout for each combined-form fill/click (mirrors the sequential
# stage timeout so the submit path cannot hang against a live page).
_COMBINED_FORM_STAGE_TIMEOUT_MS = 5_000

# The two atomic ``common.auth`` UIContract fragments. Each is independently
# collectable/attestable because the email and password surfaces never coexist
# on the same Microsoft Entra ID sign-in page. AUTH-101 requires BOTH fragments
# to be effectively_attested before any credential field is applied.
COMMON_AUTH_FRAGMENT_IDS = ("common.auth.email", "common.auth.password")

# Worker-local operation name for the operator-only pre-attestation email stage
# (AUTH-106). It fills ONLY the email field and clicks ONLY the Next control to
# advance the live Microsoft authentication page to the password step so the
# ``common.auth.password`` selectors become observable for attestation. It NEVER
# types the password or clicks Sign in, and it does NOT require attestation to
# run.
AUTH_BEGIN_EMAIL_STAGE_OPERATION = "auth_begin_email_stage"

# Exactly the four progression selector keys, in flow order.
PROGRESSION_SELECTOR_KEYS = (
    EMAIL_SELECTOR_NAME,
    NEXT_SELECTOR_NAME,
    PASSWORD_SELECTOR_NAME,
    SIGNIN_SELECTOR_NAME,
)


def ui_contract_selector_value(selector_name: str) -> str | None:
    """LEGACY: return the attested scalar locator for a ``common.auth`` selector.

    Kept only because browser.py still consumes it for the attested fill path.
    New code MUST NOT use this: it depends on the scalar ``value`` field, which
    is ``None`` until attestation, and it invents no locators by design. Prefer
    ``common_auth_locator_plan`` for structured, value-independent discovery.
    """
    from m365_mcp.ui_contract_store import load_ui_contract_set

    source = load_ui_contract_set()
    for fragment in source.fragments:
        if fragment.fragment_id not in COMMON_AUTH_FRAGMENT_IDS:
            continue
        value = fragment.selectors.get(selector_name, {}).get("value")
        if isinstance(value, str) and value:
            return value
        return None
    return None


def common_auth_locator_plan(selector_name: str) -> LocatorPlan | None:
    """Load a progression selector plan from the shipped ``common.auth`` fragments.

    Fail-closed: only the four declared progression selector keys are permitted.
    Any other key raises ``ValueError`` so the caller cannot reach an arbitrary or
    hardcoded locator. The plan is derived solely from the structured ``locators``
    metadata; the scalar ``value`` is ignored. This deliberately works for
    ``UNVERIFIED_LIVE`` plans (null ``value``) because bootstrap discovery must
    enumerate them before attestation.

    The attestation gate is NOT enforced here: the caller remains responsible for
    refusing unattested plans before any fill.
    """
    if selector_name not in PROGRESSION_SELECTOR_KEYS:
        raise ValueError(
            f"common.auth progression selector required; got {selector_name!r}"
        )

    from m365_mcp.ui_contract_store import load_ui_contract_set

    source = load_ui_contract_set()
    for fragment in source.fragments:
        if fragment.fragment_id not in COMMON_AUTH_FRAGMENT_IDS:
            continue
        metadata = fragment.selectors.get(selector_name)
        if metadata is None:
            continue
        return locator_plan_from_metadata(selector_name, metadata)
    return None


@dataclass(frozen=True)
class OperatorSignInInput:
    """Memory-only operator sign-in values. Never persisted or logged.

    ``email`` and ``password`` are the only accepted fields. The values exist
    only for the duration of one submit call; they are not written to disk,
    environment, argv, logs or worker state.
    """

    email: str
    password: str

    def field_names(self) -> tuple[str, ...]:
        return ALLOWED_SIGNIN_FIELDS


def validate_signin_input(payload: dict[str, object]) -> OperatorSignInInput:
    """Validate an untrusted mapping into the closed sign-in input contract.

    Rejects unknown keys, missing keys, and non-string values so the worker can
    never receive an unexpected credential field.
    """
    if not isinstance(payload, dict):
        raise ValueError("operator sign-in payload must be an object")
    provided = set(payload.keys())
    if provided != set(ALLOWED_SIGNIN_FIELDS):
        unexpected = provided - set(ALLOWED_SIGNIN_FIELDS)
        missing = set(ALLOWED_SIGNIN_FIELDS) - provided
        raise ValueError(
            f"operator sign-in fields must be exactly {ALLOWED_SIGNIN_FIELDS}; "
            f"unexpected={sorted(unexpected)} missing={sorted(missing)}"
        )
    email = payload["email"]
    password = payload["password"]
    if not isinstance(email, str) or not isinstance(password, str):
        raise ValueError("operator sign-in email and password must be strings")
    return OperatorSignInInput(email=email, password=password)


# The ONLY field the pre-attestation email stage accepts. It is the operator's
# professional address used to advance the Microsoft sign-in page to the password
# step; it is NOT a credential secret and is never combined with the password.
ALLOWED_EMAIL_STAGE_FIELDS = ("email",)


@dataclass(frozen=True)
class OperatorEmailStageInput:
    """Memory-only operator email-stage value. Never persisted or logged.

    ``email`` exists only for the duration of one email-stage call; it is not
    written to disk, environment, argv, logs or worker state, and it is not the
    sign-in password.
    """

    email: str

    def field_names(self) -> tuple[str, ...]:
        return ALLOWED_EMAIL_STAGE_FIELDS


def validate_email_stage_input(payload: dict[str, object]) -> OperatorEmailStageInput:
    """Validate an untrusted mapping into the closed email-stage input contract.

    Rejects unknown keys, missing keys, and non-string values so the worker can
    never receive a password or any other credential field on the
    pre-attestation email stage (AUTH-106). The password is deliberately NOT an
    accepted key here.
    """
    if not isinstance(payload, dict):
        raise ValueError("operator email-stage payload must be an object")
    provided = set(payload.keys())
    if provided != set(ALLOWED_EMAIL_STAGE_FIELDS):
        unexpected = provided - set(ALLOWED_EMAIL_STAGE_FIELDS)
        missing = set(ALLOWED_EMAIL_STAGE_FIELDS) - provided
        raise ValueError(
            f"operator email-stage fields must be exactly {ALLOWED_EMAIL_STAGE_FIELDS}; "
            f"unexpected={sorted(unexpected)} missing={sorted(missing)}"
        )
    email = payload["email"]
    if not isinstance(email, str):
        raise ValueError("operator email-stage email must be a string")
    return OperatorEmailStageInput(email=email)


async def detect_combined_signin_form(page: Any) -> bool:
    """Structural presence of the OBSERVED combined Entra ID sign-in form.

    Returns True iff the three fixed controls -- email input ``id=i0116``,
    password input ``id=i0118`` and submit ``id=idSIButton9`` -- are ALL
    uniquely present (count == 1 each). Performs NO text read, NO fill, NO
    click and NO navigation. Any detection failure (including a missing
    ``.locator``/``.count`` primitive) returns False so the incumbent sequential
    email -> Next -> password -> Sign-in flow is used instead. Never logs or
    returns identity, DOM text or URL. Only the closed boolean is returned.
    """
    try:
        email_count = await page.locator(f"#{COMBINED_FORM_EMAIL_ID}").count()
        password_count = await page.locator(f"#{COMBINED_FORM_PASSWORD_ID}").count()
        submit_count = await page.locator(f"#{COMBINED_FORM_SUBMIT_ID}").count()
    except Exception:  # noqa: BLE001 - fail closed / fall through to sequential
        return False
    return (
        email_count == 1
        and password_count == 1
        and submit_count == 1
    )


async def submit_combined_signin_form(
    page: Any, signin: OperatorSignInInput
) -> None:
    """Fill and submit the OBSERVED combined Entra ID sign-in form exactly once.

    Uses ONLY the three fixed control ids. Fills ``signin.email`` into
    ``id=i0116`` and ``signin.password`` into ``id=i0118``, then clicks
    ``id=idSIButton9`` (the Microsoft form "Sign in"). Memory-only: the values
    are consumed for exactly one ``fill`` each and then dropped; they are never
    written to state, logs, argv, env or responses. No MFA control is clicked
    and no MFA state is polled here -- the human still completes MFA in
    Microsoft Authenticator. Any interaction error propagates so the caller
    fails closed.
    """
    email_locator = page.locator(f"#{COMBINED_FORM_EMAIL_ID}")
    password_locator = page.locator(f"#{COMBINED_FORM_PASSWORD_ID}")
    submit_locator = page.locator(f"#{COMBINED_FORM_SUBMIT_ID}")
    # Memory-only: the email/password are consumed for exactly one fill each and
    # then dropped. They are never stored, logged, or returned.
    await email_locator.fill(signin.email)
    await password_locator.fill(signin.password)
    await submit_locator.click(timeout=_COMBINED_FORM_STAGE_TIMEOUT_MS)
