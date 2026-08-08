# CORE-037 — Generalized state identity

Status: **PREIMPLEMENTED_STACKED_AWAITING_CORE_036**

## Objective

Replace the implicit Planner-only `external_id` state model with an application-neutral identity that distinguishes account, container and resource state across Microsoft 365 applications.

## Canonical identity hierarchy

`m365_mcp.state_identity.StateIdentity` carries reviewed semantic scope only:

- application (`planner` or `outlook` from the closed Application Registry);
- abstract account scope;
- identity level: `ACCOUNT`, `CONTAINER` or `RESOURCE`;
- semantic container kind;
- SHA-256 digest of the external container identifier;
- semantic resource kind where applicable;
- SHA-256 digest of the external resource identifier where applicable.

Raw external Microsoft identifiers are normalized into SHA-256 immediately and are never returned by `canonical_payload()`.

## Separation properties

The identity digest is computed from canonical sorted JSON over the full scoped identity. Therefore:

- identical external identifiers in different applications remain different state identities;
- identical resource identifiers under different containers remain different identities;
- account/container/resource levels cannot collide semantically;
- account scope is part of state identity;
- changing container or resource kind changes identity.

## Planner compatibility bridge

`planner_external_id_identity()` represents historical Planner plan/task identifiers through the new model without changing the existing Planner state store yet.

- a Planner plan-like external id becomes a Planner container identity;
- a task-like external id with a parent plan becomes a Planner resource identity scoped through that plan;
- original ids are not retained in the generalized projection.

This is a one-way compatibility bridge. CORE-038 will use generalized identity when upgrading idempotency/replay protection; it is deliberately not mixed into the legacy store in CORE-037.

## Fail-closed validation

The model rejects:

- empty account scopes;
- whitespace-bearing semantic scope/kind tokens;
- empty external identifiers;
- invalid digest representations;
- account identities carrying container/resource state;
- container identities carrying resource fields;
- resource identities missing either parent-container or resource identity.

## Security/privacy boundary

No tenant content, mailbox address, account email, browser profile path, cookie, token or storage state is introduced. New persistence consumers can index by `identity_digest` without persisting raw Microsoft resource identifiers.

## Dependency gate

This work is stacked on CORE-036. It must not merge until CORE-036 is merged and post-merge `main` is GREEN. It will then be retargeted to `main` and revalidated through the full mandatory CI/security/image/Trivy/SBOM/documentation suite.
