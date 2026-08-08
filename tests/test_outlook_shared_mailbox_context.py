from __future__ import annotations

import pytest

from m365_mcp.apps.outlook.mailbox_context import (
    PrimaryMailboxContext,
    PrimaryMailboxContextState,
)
from m365_mcp.apps.outlook.shared_mailbox_context import (
    SharedMailboxContextState,
    SharedMailboxObservation,
    verify_shared_mailbox_context,
)


DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def _verified_primary() -> PrimaryMailboxContext:
    return PrimaryMailboxContext(
        state=PrimaryMailboxContextState.VERIFIED,
        account_context_verified=True,
        primary_shell_verified=True,
        evidence_digest=DIGEST_A,
    )


def test_verified_shared_mailbox_context_is_identity_free() -> None:
    result = verify_shared_mailbox_context(
        _verified_primary(),
        SharedMailboxObservation(
            shared_shell_observed=True,
            scope_digest=DIGEST_A,
            evidence_digest=DIGEST_B,
        ),
    )

    assert result.state is SharedMailboxContextState.VERIFIED
    assert result.valid is True
    assert result.to_dict() == {
        "state": "VERIFIED",
        "primary_context_verified": True,
        "shared_shell_verified": True,
        "scope_present": True,
        "evidence_present": True,
        "valid": True,
    }


def test_invalid_primary_context_fails_closed() -> None:
    primary = PrimaryMailboxContext(
        state=PrimaryMailboxContextState.UNVERIFIED,
        account_context_verified=True,
        primary_shell_verified=False,
    )
    result = verify_shared_mailbox_context(
        primary,
        SharedMailboxObservation(shared_shell_observed=False),
    )

    assert result.state is SharedMailboxContextState.PRIMARY_CONTEXT_INVALID
    assert result.valid is False


def test_ambiguous_primary_or_reattestation_states_are_not_valid() -> None:
    ambiguous = verify_shared_mailbox_context(
        _verified_primary(),
        SharedMailboxObservation(
            shared_shell_observed=False,
            ambiguous_mailbox_context=True,
        ),
    )
    primary = verify_shared_mailbox_context(
        _verified_primary(),
        SharedMailboxObservation(
            shared_shell_observed=False,
            primary_mailbox_indicator=True,
        ),
    )
    stale = verify_shared_mailbox_context(
        _verified_primary(),
        SharedMailboxObservation(shared_shell_observed=False),
        reattestation_required=True,
    )

    assert ambiguous.state is SharedMailboxContextState.AMBIGUOUS
    assert primary.state is SharedMailboxContextState.PRIMARY_MAILBOX_CONTEXT
    assert stale.state is SharedMailboxContextState.REATTESTATION_REQUIRED
    assert not ambiguous.valid and not primary.valid and not stale.valid


def test_observed_shared_mailbox_requires_both_digests() -> None:
    with pytest.raises(ValueError, match="requires scope and evidence digests"):
        SharedMailboxObservation(shared_shell_observed=True, scope_digest=DIGEST_A)

    with pytest.raises(ValueError, match="requires scope and evidence digests"):
        SharedMailboxObservation(shared_shell_observed=True, evidence_digest=DIGEST_B)


def test_unobserved_shared_mailbox_rejects_scope_material() -> None:
    with pytest.raises(ValueError, match="cannot carry scope evidence"):
        SharedMailboxObservation(shared_shell_observed=False, scope_digest=DIGEST_A)


def test_digest_shape_is_fail_closed() -> None:
    with pytest.raises(ValueError, match="scope_digest must be SHA-256 hex"):
        SharedMailboxObservation(
            shared_shell_observed=True,
            scope_digest="not-a-digest",
            evidence_digest=DIGEST_B,
        )
