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

Requirement IDs: AUTH-099 (notification), AUTH-100 (fail-closed MFA), AUTH-101
(encrypted-store operator sign-in automation, superseding "human types password").
"""

from __future__ import annotations

from dataclasses import dataclass

# The ONLY sign-in fields the worker is permitted to apply. Both must be declared
# by the ``common.auth`` UIContract fragment. No submit/locator/Graph field is
# ever accepted here.
ALLOWED_SIGNIN_FIELDS = ("email", "password")

# Declared ``common.auth`` selectors the worker may fill (memory-only values).
EMAIL_SELECTOR_NAME = "auth.login_email_input"
PASSWORD_SELECTOR_NAME = "auth.login_password_input"  # noqa: S105 - selector name, not a secret


def ui_contract_selector_value(selector_name: str) -> str | None:
    """Return the attested locator for a ``common.auth`` sign-in selector.

    Fail-closed: returns ``None`` unless the selector exists in the ``common.auth``
    fragment AND carries an attested, non-null value. Before attestation every
    selector value is ``None`` (``UNVERIFIED_LIVE``), so the worker refuses to
    guess or hardcode a locator. This intentionally never invents a CSS/XPath
    string.
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
