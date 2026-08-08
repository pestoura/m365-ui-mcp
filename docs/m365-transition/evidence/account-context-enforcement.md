# CORE-024 — Account-context enforcement

## Decision

Semantic Microsoft 365 authorization now fails closed unless the active browser session has an explicitly verified professional account context.

The runtime uses a bounded account-context assertion rather than persisting or returning raw tenant IDs, user identifiers or authenticated URLs.

## Closed states

```text
VERIFIED
UNVERIFIED
AMBIGUOUS
WRONG_ACCOUNT
WRONG_TENANT
```

An account context is valid only when all of the following are true:

```text
state == VERIFIED
professional == true
expected_profile == true
```

Every other combination is rejected for semantic capability authorization.

## Broker integration

`SessionCapabilityBroker.viable` now requires:

```text
browser.started
AND AuthState == AUTHENTICATED
AND account_context.valid
```

`authorize()` raises the existing fail-closed `POLICY_DENIED` error when the professional account context is not verified. The error carries only bounded state flags; it does not expose tenant or user identity.

Successful grants now include:

```text
account_context_verified=true
```

## Worker integration

The worker composition root accepts an account-context provider and supplies it to the canonical Session/Capability Broker.

Live `/account/context` returns only the sanitized projection:

```text
state
professional
expected_profile
valid
```

The safe default is `UNVERIFIED`, so a live worker cannot authorize application operations until another trusted runtime component has positively established the professional account context.

## Security properties

- ambiguous context fails closed;
- wrong account fails closed;
- wrong tenant fails closed;
- merely authenticated is insufficient;
- a `VERIFIED` state with a non-professional or unexpected profile also fails closed;
- no raw tenant/user identifier is required by the enforcement model;
- no generic browser primitive is introduced;
- no CI workflow accesses a real Microsoft 365 tenant.

## Boundaries

This block does not implement the mechanism that obtains external network connectivity to Microsoft 365. Controlled worker egress remains `CORE-025`.

Profile serialization, page isolation and protocol negotiation remain `CORE-026..029`.

## Next gate

```text
CORE-024 PR CI/security/images/SBOM GREEN
        -> merge
        -> post-merge main GREEN
        -> CORE-025 controlled worker egress
```
