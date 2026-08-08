# CORE-018 — Capability evidence persistence

## Decision

`CORE-018` persists only bounded UI capability-evidence metadata and cryptographic digests. Raw tenant/UI evidence is deliberately outside the persistent state model.

The persistence boundary is implemented by:

```text
src/m365_mcp/capability_evidence.py
```

The store is append-only at the semantic level: each distinct sanitized record receives a deterministic SHA-256 `evidence_id`; replaying the same record is idempotent through `INSERT OR IGNORE`.

## Persisted fields

The `capability_ui_evidence` table contains only:

```text
sequence
evidence_id
fragment_id
fragment_version
scope
application
surface
contract_set_digest
evidence_digest
lifecycle_state
recorded_at
```

There is no generic metadata/payload column and no storage for:

- mailbox or message content;
- subject/body/recipient data;
- calendar or contact content;
- authenticated URLs;
- screenshots;
- cookies;
- access/refresh tokens;
- browser storage state;
- account/container identifiers;
- arbitrary tenant payloads.

The persisted `evidence_digest` is a SHA-256 reference to evidence that is produced/managed outside this store. `CORE-018` does not define collection of that evidence.

## Contract binding

Every append must bind to the exact current `UIContractSet`:

1. `contract_set_digest` must equal `UIContractSet.digest()`;
2. the `fragment_id` must exist exactly once in that contract set;
3. fragment version, scope, application and surface must match the contract fragment exactly.

Evidence associated with an older/different contract-set digest is never projected into the current lifecycle overlay.

This prevents stale evidence from silently authorizing a changed UI contract.

## Lifecycle projection

The store can project the latest evidence record per fragment into the closed lifecycle model introduced by `CORE-017`:

```text
HEALTHY
STALE
DRIFTED
RE_ATTESTATION_REQUIRED
```

The latest semantic record is selected by its timezone-aware `recorded_at` timestamp, with insertion sequence only as a deterministic tie-breaker.

The existing `UIContractSet.attestation_for_capability()` remains authoritative for dependency-scoped behavior. Persisted `HEALTHY` state cannot promote an unattested contract fragment because `CORE-017` already fails that case closed.

## Explicit non-goals

`CORE-018` does **not** implement:

- live tenant discovery or attestation (`CORE-019`);
- evidence expiry, TTL or revalidation policy (`CORE-020`);
- browser/session lifecycle hardening (`CORE-021..030`);
- generalized M365 resource-state identity (`CORE-037`);
- live Microsoft 365 egress (`CORE-025` remains mandatory);
- Outlook capabilities or tools.

## Security properties

- SQLite connections use WAL, `synchronous=FULL`, foreign keys and bounded busy timeout.
- Evidence records require lowercase `sha256:<64 hex>` digests.
- Evidence timestamps must be timezone-aware and are normalized to UTC.
- Scope/application/surface metadata is validated against the closed UIContract fragment model.
- No arbitrary JSON/blob/text evidence field exists in the schema.
- Replaying the exact same record does not create duplicates.
- Evidence from a previous contract-set digest is not projected into a newer contract set.

## Acceptance coverage

`tests/test_capability_evidence.py` verifies:

- persistence round-trip;
- deterministic/idempotent evidence identity;
- latest-record lifecycle projection;
- isolation from old contract-set digests;
- rejection of digest/fragment metadata mismatch;
- rejection of unsafe/unbounded evidence values;
- timezone-aware timestamps;
- absence of raw tenant-content fields in the persistence schema.

## Compatibility

No public MCP tool, Planner capability key or selector is changed by `CORE-018`.

The following invariants remain in force:

```text
17 planner_* public tools -> PRESERVE
11 Planner capability keys -> preserved
10 historical UI selectors -> preserved
Outlook -> RESERVED / no public tools yet
CORE-025 -> required before any live M365 worker egress claim
```
