# CORE-038 — Idempotency and replay protection v2

Status: **PREIMPLEMENTED_STACKED_AWAITING_CORE_037**

## Objective

Generalize idempotency from the legacy Planner-only key/result-hash model into an application-neutral operation binding that uses CORE-037 state identity and makes read-back requirements explicit before retry.

## Operation binding

`m365_mcp.idempotency_v2` derives a stable idempotency key from:

- semantic operation token;
- CORE-037 `StateIdentity.identity_digest`;
- canonical SHA-256 request digest.

Request payloads and result payloads are reduced to canonical SHA-256 digests; the v2 record does not retain their original values.

`IdempotencyRecordV2` associates:

- idempotency key;
- semantic operation;
- generalized state identity digest;
- request digest;
- execution phase;
- whether read-back is mandatory;
- result digest only for a completed operation.

## Closed execution phases

- `RESERVED`
- `COMPLETED`
- `FAILED_PRE_EFFECT`
- `EFFECT_UNVERIFIED`

`INDETERMINATE` is intentionally not introduced here. The roadmap assigns that terminal execution state to CORE-042.

## Retry decisions

`resolve_retry()` returns one of:

- `EXECUTE` — no prior record exists;
- `REPLAY_RESULT` — exact operation binding already completed;
- `RETRY_SAFE` — failure is proven pre-effect or read-back proves the effect is absent;
- `READ_BACK_REQUIRED` — the external effect cannot yet be proven;
- `DO_NOT_RETRY` — the effect is present or an uncertain mutation lacks a safe read-back path;
- `DENY_BINDING_MISMATCH` — operation, state identity or request binding differs.

A completed operation is never re-executed. A mutation whose effect is unverified is never blindly retried when read-back is required. If read-back proves the effect present, retry is refused; if it proves the effect absent, retry is safe; ambiguous or missing evidence remains blocked behind `READ_BACK_REQUIRED`.

## Cross-application separation

Because the generalized state identity digest includes application/account/container/resource scope, identical external resource identifiers in Planner and Outlook cannot share an idempotency key. Likewise, identical resource identifiers under different containers remain distinct.

## Legacy boundary

The legacy SQLite v1 schema currently stores:

- `resource.external_id` as a single primary key;
- `idempotency.operation` plus optional `result_hash`.

CORE-038 does not mutate that schema. It introduces the application-neutral v2 model in parallel so later state migration can be explicit and reversible rather than silently reinterpreting historical rows.

## Security/privacy boundary

The v2 model does not retain tenant content, request payload values, result payload values, mailbox addresses, raw Microsoft identifiers, browser profile paths, cookies, tokens or storage state. Only semantic tokens and SHA-256 digests are projected.

## Acceptance coverage

Tests prove:

- deterministic binding by application identity and request payload;
- raw request values are not retained;
- completed result association and replay behavior;
- cross-identity/operation binding mismatch denial;
- pre-effect retry safety;
- no blind retry after an unverified effect;
- read-back-controlled retry decisions for present/absent/ambiguous effects;
- result digests are legal only for completed operations;
- a first operation with no existing record is executable.

## Dependency gate

This work is stacked on CORE-037. It must not merge until CORE-037 is merged and post-merge `main` is GREEN. It will then be retargeted to `main` and revalidated through the complete mandatory CI/security/image/Trivy/SBOM/documentation suite.
