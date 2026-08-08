"""Auth state machine and sanitized MFA metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AuthState(StrEnum):
    """Authentication lifecycle states."""

    UNKNOWN = "UNKNOWN"
    READY = "READY"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    MFA_REQUIRED = "MFA_REQUIRED"
    WAITING_FOR_MFA = "WAITING_FOR_MFA"
    AUTHENTICATED = "AUTHENTICATED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    AUTH_FAILED = "AUTH_FAILED"


TERMINAL_STATES = frozenset({AuthState.AUTHENTICATED, AuthState.AUTH_FAILED})

_ALLOWED: dict[AuthState, frozenset[AuthState]] = {
    AuthState.UNKNOWN: frozenset(
        {AuthState.READY, AuthState.AUTH_REQUIRED, AuthState.AUTHENTICATED}
    ),
    AuthState.READY: frozenset({AuthState.AUTH_REQUIRED, AuthState.AUTHENTICATED}),
    AuthState.AUTH_REQUIRED: frozenset(
        {AuthState.MFA_REQUIRED, AuthState.AUTHENTICATED, AuthState.AUTH_FAILED}
    ),
    AuthState.MFA_REQUIRED: frozenset({AuthState.WAITING_FOR_MFA, AuthState.AUTH_FAILED}),
    AuthState.WAITING_FOR_MFA: frozenset(
        {AuthState.AUTHENTICATED, AuthState.AUTH_FAILED, AuthState.MFA_REQUIRED}
    ),
    AuthState.AUTHENTICATED: frozenset({AuthState.SESSION_EXPIRED, AuthState.AUTH_REQUIRED}),
    AuthState.SESSION_EXPIRED: frozenset({AuthState.AUTH_REQUIRED, AuthState.AUTHENTICATED}),
    AuthState.AUTH_FAILED: frozenset({AuthState.AUTH_REQUIRED}),
}


def can_transition(current: AuthState, target: AuthState) -> bool:
    """Return whether a state transition is permitted."""
    return target in _ALLOWED[current]


@dataclass(frozen=True)
class MfaChallenge:
    """Sanitized MFA number-matching metadata. Approval happens only in Authenticator."""

    number: str
    operation_id: str
    service: str
    description: str
    expires_at: str
    approval_channel: str = "microsoft_authenticator"

    def __post_init__(self) -> None:
        if not (self.number.isdigit() and len(self.number) == 2):
            raise ValueError("MFA number match must be a 2-digit string")

    def to_dict(self) -> dict[str, str]:
        return {
            "mfa_number": self.number,
            "operation_id": self.operation_id,
            "service": self.service,
            "description": self.description,
            "expires_at": self.expires_at,
            "approval_channel": self.approval_channel,
            "approve_in_telegram": "false",
        }


@dataclass
class AuthContext:
    """Mutable auth context guarded by the state machine."""

    state: AuthState = AuthState.UNKNOWN
    challenge: MfaChallenge | None = None
    history: list[str] = field(default_factory=list)

    def transition(self, target: AuthState) -> AuthState:
        """Apply a guarded transition, raising on an illegal move."""
        if not can_transition(self.state, target):
            raise ValueError(f"illegal auth transition {self.state.value} -> {target.value}")
        self.history.append(f"{self.state.value}->{target.value}")
        self.state = target
        if target is not AuthState.WAITING_FOR_MFA and target is not AuthState.MFA_REQUIRED:
            self.challenge = None
        return self.state
