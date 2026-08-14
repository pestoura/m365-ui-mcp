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
  from the shipped ``common.auth`` fragment WITHOUT requiring attestation, so
  bootstrap discovery can enumerate them for an UNVERIFIED_LIVE flow. Loading is
  fail-closed: only the four declared progression keys are accepted, and the
  caller remains responsible for the attestation gate before any fill.

Requirement IDs: AUTH-099 (notification), AUTH-100 (fail-closed MFA), AUTH-101
(encrypted-store operator sign-in automation, superseding "human types password").
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_browser_worker.locators import LocatorPlan, locator_plan_from_metadata

# The ONLY sign-in fields the worker is permitted to apply. Both must be declared
# by the ``common.auth`` UIContract fragment. No submit/locator/Graph field is
# ever accepted here.
ALLOWED_SIGNIN_FIELDS = ("email", "password")

# Declared ``common.auth`` selectors the worker may fill (memory-only values).
EMAIL_SELECTOR_NAME = "auth.login_email_input"
PASSWORD_SELECTOR_NAME = "auth.login_password_input"  # noqa: S105 - selector name, not a secret

# Progression selectors of the Microsoft Entra ID sign-in flow. All four are
# declared by the ``common.auth`` fragment; only these may be loaded as plans.
NEXT_SELECTOR_NAME = "auth.login_next_button"
SIGNIN_SELECTOR_NAME = "auth.login_signin_button"

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
        if fragment.fragment_id != "common.auth":
            continue
        value = fragment.selectors.get(selector_name, {}).get("value")
        if isinstance(value, str) and value:
            return value
        return None
    return None


def common_auth_locator_plan(selector_name: str) -> LocatorPlan | None:
    """Load a progression selector plan from the shipped ``common.auth`` fragment.

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
        if fragment.fragment_id != "common.auth":
            continue
        metadata = fragment.selectors.get(selector_name)
        if metadata is None:
            return None
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
