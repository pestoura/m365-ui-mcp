from __future__ import annotations

import inspect

import m365_browser_worker.account_context as account_context
import m365_mcp.apps.outlook.mailbox_context as mailbox_context


EVIDENCE = "a" * 64


def _verified_account() -> account_context.AccountContext:
    return account_context.AccountContext(
        state=account_context.AccountContextState.VERIFIED,
        professional=True,
        expected_profile=True,
    )


def test_primary_mailbox_verification_requires_verified_professional_account() -> None:
    result = mailbox_context.verify_primary_mailbox_context(
        account_context.AccountContext(
            state=account_context.AccountContextState.UNVERIFIED,
            professional=False,
            expected_profile=False,
        ),
        mailbox_context.PrimaryMailboxObservation(
            primary_shell_observed=True,
            evidence_digest=EVIDENCE,
        ),
    )

    assert result.state is mailbox_context.PrimaryMailboxContextState.ACCOUNT_CONTEXT_INVALID
    assert result.valid is False


def test_primary_mailbox_verifies_only_with_shell_evidence() -> None:
    result = mailbox_context.verify_primary_mailbox_context(
        _verified_account(),
        mailbox_context.PrimaryMailboxObservation(
            primary_shell_observed=True,
            evidence_digest=EVIDENCE,
        ),
    )

    assert result.state is mailbox_context.PrimaryMailboxContextState.VERIFIED
    assert result.valid is True
    assert result.to_dict() == {
        "state": "VERIFIED",
        "account_context_verified": True,
        "primary_shell_verified": True,
        "evidence_present": True,
        "valid": True,
    }


def test_shared_mailbox_indicator_cannot_be_accepted_as_primary_mailbox() -> None:
    result = mailbox_context.verify_primary_mailbox_context(
        _verified_account(),
        mailbox_context.PrimaryMailboxObservation(
            primary_shell_observed=True,
            shared_mailbox_indicator=True,
            evidence_digest=EVIDENCE,
        ),
    )

    assert result.state is mailbox_context.PrimaryMailboxContextState.SHARED_MAILBOX_CONTEXT
    assert result.valid is False


def test_ambiguous_or_stale_context_fails_closed() -> None:
    ambiguous = mailbox_context.verify_primary_mailbox_context(
        _verified_account(),
        mailbox_context.PrimaryMailboxObservation(
            primary_shell_observed=True,
            ambiguous_mailbox_context=True,
            evidence_digest=EVIDENCE,
        ),
    )
    stale = mailbox_context.verify_primary_mailbox_context(
        _verified_account(),
        mailbox_context.PrimaryMailboxObservation(
            primary_shell_observed=True,
            evidence_digest=EVIDENCE,
        ),
        reattestation_required=True,
    )

    assert ambiguous.state is mailbox_context.PrimaryMailboxContextState.AMBIGUOUS
    assert stale.state is mailbox_context.PrimaryMailboxContextState.REATTESTATION_REQUIRED
    assert ambiguous.valid is stale.valid is False


def test_unobserved_mailbox_remains_unverified() -> None:
    result = mailbox_context.verify_primary_mailbox_context(
        _verified_account(),
        mailbox_context.PrimaryMailboxObservation(primary_shell_observed=False),
    )

    assert result.state is mailbox_context.PrimaryMailboxContextState.UNVERIFIED
    assert result.valid is False


def test_observation_rejects_missing_or_malformed_evidence() -> None:
    try:
        mailbox_context.PrimaryMailboxObservation(primary_shell_observed=True)
    except ValueError as exc:
        assert "requires evidence digest" in str(exc)
    else:
        raise AssertionError("observed primary mailbox without evidence must fail")

    try:
        mailbox_context.PrimaryMailboxObservation(
            primary_shell_observed=True,
            evidence_digest="bad",
        )
    except ValueError as exc:
        assert "SHA-256" in str(exc)
    else:
        raise AssertionError("malformed evidence digest must fail")


def test_model_has_no_identity_bearing_mailbox_parameters_or_fields() -> None:
    signature = inspect.signature(mailbox_context.verify_primary_mailbox_context)
    forbidden = {"email", "mailbox_address", "tenant_id", "user_id", "url"}

    assert forbidden.isdisjoint(signature.parameters)
    assert forbidden.isdisjoint(
        mailbox_context.PrimaryMailboxObservation.__dataclass_fields__
    )
