from __future__ import annotations

import m365_mcp.apps.outlook.mailbox_context as mailbox_context
import m365_mcp.apps.outlook.shared_mailbox_context as shared_mailbox_context

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def _verified_primary() -> mailbox_context.PrimaryMailboxContext:
    return mailbox_context.PrimaryMailboxContext(
        state=mailbox_context.PrimaryMailboxContextState.VERIFIED,
        account_context_verified=True,
        primary_shell_verified=True,
        evidence_digest=DIGEST_A,
    )


def test_verified_shared_mailbox_context_is_identity_free() -> None:
    result = shared_mailbox_context.verify_shared_mailbox_context(
        _verified_primary(),
        shared_mailbox_context.SharedMailboxObservation(
            shared_shell_observed=True,
            scope_digest=DIGEST_A,
            evidence_digest=DIGEST_B,
        ),
    )

    assert result.state is shared_mailbox_context.SharedMailboxContextState.VERIFIED
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
    primary = mailbox_context.PrimaryMailboxContext(
        state=mailbox_context.PrimaryMailboxContextState.UNVERIFIED,
        account_context_verified=True,
        primary_shell_verified=False,
    )
    result = shared_mailbox_context.verify_shared_mailbox_context(
        primary,
        shared_mailbox_context.SharedMailboxObservation(shared_shell_observed=False),
    )

    assert (
        result.state
        is shared_mailbox_context.SharedMailboxContextState.PRIMARY_CONTEXT_INVALID
    )
    assert result.valid is False


def test_ambiguous_primary_or_reattestation_states_are_not_valid() -> None:
    ambiguous = shared_mailbox_context.verify_shared_mailbox_context(
        _verified_primary(),
        shared_mailbox_context.SharedMailboxObservation(
            shared_shell_observed=False,
            ambiguous_mailbox_context=True,
        ),
    )
    primary = shared_mailbox_context.verify_shared_mailbox_context(
        _verified_primary(),
        shared_mailbox_context.SharedMailboxObservation(
            shared_shell_observed=False,
            primary_mailbox_indicator=True,
        ),
    )
    stale = shared_mailbox_context.verify_shared_mailbox_context(
        _verified_primary(),
        shared_mailbox_context.SharedMailboxObservation(shared_shell_observed=False),
        reattestation_required=True,
    )

    assert ambiguous.state is shared_mailbox_context.SharedMailboxContextState.AMBIGUOUS
    assert (
        primary.state
        is shared_mailbox_context.SharedMailboxContextState.PRIMARY_MAILBOX_CONTEXT
    )
    assert (
        stale.state
        is shared_mailbox_context.SharedMailboxContextState.REATTESTATION_REQUIRED
    )
    assert not ambiguous.valid and not primary.valid and not stale.valid


def test_observed_shared_mailbox_requires_both_digests() -> None:
    for kwargs in (
        {"shared_shell_observed": True, "scope_digest": DIGEST_A},
        {"shared_shell_observed": True, "evidence_digest": DIGEST_B},
    ):
        try:
            shared_mailbox_context.SharedMailboxObservation(**kwargs)
        except ValueError as exc:
            assert "requires scope and evidence digests" in str(exc)
        else:
            raise AssertionError("observed shared mailbox without both digests must fail")


def test_unobserved_shared_mailbox_rejects_scope_material() -> None:
    try:
        shared_mailbox_context.SharedMailboxObservation(
            shared_shell_observed=False,
            scope_digest=DIGEST_A,
        )
    except ValueError as exc:
        assert "cannot carry scope evidence" in str(exc)
    else:
        raise AssertionError("unobserved shared mailbox cannot carry scope evidence")


def test_digest_shape_is_fail_closed() -> None:
    try:
        shared_mailbox_context.SharedMailboxObservation(
            shared_shell_observed=True,
            scope_digest="not-a-digest",
            evidence_digest=DIGEST_B,
        )
    except ValueError as exc:
        assert "scope_digest must be SHA-256 hex" in str(exc)
    else:
        raise AssertionError("malformed shared mailbox scope digest must fail")
