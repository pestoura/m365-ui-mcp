# CORE-046 — Secret-aware result fields

Status: **PREIMPLEMENTED_STACKED_AWAITING_CORE_045**

## Objective

Make result-field exposure explicit so fields classified as secrets can never be projected in clear text, while unclassified schema drift fails closed instead of inheriting an accidental default exposure.

## Explicit field metadata

`m365_mcp.result_fields` defines two closed dimensions:

`FieldSensitivity`:

```text
STANDARD
SECRET
```

`FieldExposure`:

```text
VALUE
REDACTED
```

A `SECRET` field cannot be configured with `VALUE` exposure. This is validated when the schema is constructed, before any result is projected.

## Projection behavior

`project_secret_aware_fields()` requires a complete `ResultFieldSchema` for the supplied mapping:

- every input field must have an explicit definition;
- every defined field must be present in the result mapping;
- unknown/unreviewed fields fail closed;
- `VALUE` fields retain their semantic value;
- `REDACTED` fields become only `{redacted: true, present: <bool>}`;
- the raw redacted value is not hashed or projected.

Avoiding a digest for secret values is deliberate: low-entropy credentials or tokens must not become offline-comparison material merely to prove that a secret existed. Presence metadata is sufficient for result-shape semantics.

`SecretAwareProjection.redacted_fields` records the names of fields removed from clear output. `contains_clear_secret` is always false by construction.

## Non-secret redaction

A STANDARD field may also be deliberately configured as `REDACTED`, allowing application adapters to suppress identifiers or other values for privacy even when they are not credentials.

## Relationship to adjacent phases

- CORE-044 reduces/selects result content.
- CORE-045 references separately retained artifacts/evidence without exposing locators.
- CORE-046 governs whether individual result fields may be emitted in clear text.
- CORE-047 will add execution provenance without weakening these field-exposure rules.

## Security/privacy boundary

Secret-aware projection is metadata-driven rather than name-heuristic-driven. It does not inspect cookies, tokens, browser storage, authentication headers or Microsoft tenant state. A value classified as SECRET is never present in the projected result or redaction metadata.

## Acceptance coverage

Tests prove:

- secret values never appear in clear projections or representation;
- null secrets project only `present=false`;
- SECRET + VALUE is rejected at schema construction;
- unknown/unclassified fields fail closed;
- missing classified fields fail closed;
- field definitions are unique semantic tokens;
- standard non-secret fields can still be deliberately redacted.

## Dependency gate

This work is stacked on CORE-045. CORE-045 itself remains blocked behind CORE-044, and CORE-044 remains blocked until CORE-043 completes Phase 4. CORE-046 must therefore remain stacked until those predecessors are merged and post-merge GREEN.
