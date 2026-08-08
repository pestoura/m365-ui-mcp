"""Content-free professional account-context enforcement for the M365 worker."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AccountContextState(StrEnum):
    """Closed account-context states used for fail-closed authorization."""

    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    AMBIGUOUS = "AMBIGUOUS"
    WRONG_ACCOUNT = "WRONG_ACCOUNT"
    WRONG_TENANT = "WRONG_TENANT"


@dataclass(frozen=True)
class AccountContext:
    """Sanitized context assertion without tenant or user identifiers."""

    state: AccountContextState
    professional: bool
    expected_profile: bool

    @property
    def valid(self) -> bool:
        return (
            self.state is AccountContextState.VERIFIED
            and self.professional
            and self.expected_profile
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "professional": self.professional,
            "expected_profile": self.expected_profile,
            "valid": self.valid,
        }


def unverified_account_context() -> AccountContext:
    """Return the safe default until live context has been explicitly proven."""
    return AccountContext(
        state=AccountContextState.UNVERIFIED,
        professional=False,
        expected_profile=False,
    )


__all__ = ["AccountContext", "AccountContextState", "unverified_account_context"]
