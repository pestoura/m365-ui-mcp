"""Sanitized, one-way MFA challenge notifications for an external adapter.

This module is the ONLY outbound notification surface allowed to carry an MFA
challenge. It is intentionally narrow and fail-closed:

* It emits a **sanitized** MFA challenge object only. The challenge object is
  built by ``planner_mcp.auth.MfaChallenge`` and never contains a password,
  cookie, token, UPN, tenant id, session handle, browser handle or any other
  secret/credential material.
* It has **no approval capability**. MFA approval happens exclusively in
  Microsoft Authenticator (``AUTH-003`` / ADR-004). Nothing here relays,
  forwards, satisfies or proxies an MFA approval. The emitted payload carries an
  explicit ``approve_in_authenticator_only`` flag and no reply/action path.
* It contains **no Telegram credentials, no Hermes credentials, no webhook
  URLs and no secrets of any kind**. The concrete Hermes transport is an
  external adapter concern (see ``docs/hermes-integration.md``); this module
  only produces a stable, machine-readable notification contract.
* It is one-way. ``emit`` returns a normalized ``MfaNotification`` record and a
  bounded delivery result; delivery failures are reported as a notification
  degradation (never fabricated approval and never a Planner operation success).

If no safe direct adapter can be wired inside this repo, the external Hermes
adapter consumes the serialized notification over the documented CLI/JSON
contract (``MfaNotification.to_json`` / the ``emit`` stdout line), exactly as a
read-only observer. The adapter is responsible for sanitizing transport and
routing; this package never assumes one exists.

Requirement IDs: AUTH-099 (notification contract), AUTH-100 (fail-closed MFA
detection), AUTH-101 (encrypted-store operator sign-in automation, supersedes
the "human types password" rule while keeping the GUI handoff as fallback only).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from planner_mcp.auth import MfaChallenge


class MfaChallengeSource(Protocol):
    """A live probe that may resolve a sanitized MFA challenge.

    Implementations must return ``None`` when the page/auth state cannot be
    unambiguously classified as a number-matching or approval-waiting challenge
    (fail closed). They must never return a challenge built from guessed or
    inferred secret material.
    """

    def detect(self) -> MfaChallenge | None:
        """Return the sanitized challenge, or ``None`` when not resolvable."""
        ...


@dataclass(frozen=True)
class MfaNotification:
    """Closed, sanitized MFA notification record.

    The field set mirrors ``hermes-integration.md`` §2 exactly: ``mfa_number``,
    ``operation_id``, ``service``, ``description``, ``expires_at`` plus the
    non-actionable routing markers. No secret/credential field is ever added.
    """

    mfa_number: str
    operation_id: str
    service: str
    description: str
    expires_at: str
    approve_in_authenticator_only: bool = True
    approval_channel: str = "microsoft_authenticator"

    @classmethod
    def from_challenge(cls, challenge: MfaChallenge) -> MfaNotification:
        payload = challenge.to_dict()
        return cls(
            mfa_number=payload["mfa_number"],
            operation_id=payload["operation_id"],
            service=payload["service"],
            description=payload["description"],
            expires_at=payload["expires_at"],
            approve_in_authenticator_only=True,
            approval_channel=payload["approval_channel"],
        )

    def to_dict(self) -> dict[str, str]:
        approve_only = "true" if self.approve_in_authenticator_only else "false"
        return {
            "mfa_number": self.mfa_number,
            "operation_id": self.operation_id,
            "service": self.service,
            "description": self.description,
            "expires_at": self.expires_at,
            "approve_in_authenticator_only": approve_only,
            "approval_channel": self.approval_channel,
        }

    def to_json(self) -> str:
        """Stable, sorted JSON for the external Hermes adapter to consume."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class MfaNotificationResult:
    """One-way delivery outcome. Never encodes approval or secret material."""

    delivered: bool
    channel: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "delivered": "true" if self.delivered else "false",
            "channel": self.channel,
            "detail": self.detail,
        }


# External adapters register a sink here. The default sink is a no-op that only
# validates the sanitized payload (so the call path is exercised without
# requiring a live Hermes/Telegram connection). Adapters must preserve the
# fail-closed contract: a failed delivery is a notification degradation, never
# an MFA approval.
MfaSink = Callable[[MfaNotification], MfaNotificationResult]

_DEFAULT_CHANNEL = "hermes-adapter"


def _noop_sink(notification: MfaNotification) -> MfaNotificationResult:
    """Validate-only sink: proves the sanitized payload without external I/O.

    Used when no external Hermes adapter is wired. The payload is intentionally
    not transmitted anywhere; the call path and field-set are exercised only.
    """
    # Touch every field so a malformed notification fails loudly before emit.
    _ = (
        notification.mfa_number,
        notification.operation_id,
        notification.service,
        notification.description,
        notification.expires_at,
        notification.approve_in_authenticator_only,
        notification.approval_channel,
    )
    return MfaNotificationResult(
        delivered=False,
        channel=_DEFAULT_CHANNEL,
        detail="no-external-adapter-configured",
    )


def emit(
    challenge: MfaChallenge,
    *,
    sink: MfaSink | None = None,
    channel: str = _DEFAULT_CHANNEL,
) -> tuple[MfaNotification, MfaNotificationResult]:
    """Emit a sanitized MFA notification from a challenge.

    Fail closed: if the sink raises, the delivery result reports the failure and
    the function never raises a credential/approval-implied success. The returned
    notification is always the sanitized closed record; no secret material is
    touched or returned.
    """
    notification = MfaNotification.from_challenge(challenge)
    active_sink = sink or _noop_sink
    try:
        result = active_sink(notification)
    except Exception as exc:  # noqa: BLE001 - sink failures are degradations
        result = MfaNotificationResult(
            delivered=False,
            channel=channel,
            detail=f"sink-error:{type(exc).__name__}",
        )
    return notification, result


def sanitize_for_external_adapter(notification: MfaNotification) -> str:
    """Return the exact one-way JSON contract for the external Hermes adapter.

    The external adapter consumes this string from a worker/local CLI; it MUST
    NOT be treated as an approval channel. Approval occurs only in Authenticator.
    """
    return notification.to_json()
