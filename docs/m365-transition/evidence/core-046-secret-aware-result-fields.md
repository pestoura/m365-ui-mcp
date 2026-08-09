# CORE-046 — Secret-aware result fields

Status: **IMPLEMENTED_AWAITING_CURRENT_BASE_GATES**

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
- CORE-047 adds execution provenance without weakening these field-exposure rules.

## Security/privacy boundary

Secret-aware projection is metadata-driven rather than name-heuristic-driven. It does not inspect cookies, tokens, browser storage, authentication headers or Microsoft tenant state. A value classified as SECRET is never present in the projected result or redaction metadata.

The enum value `SECRET` is a classification label, not credential material; the local S105 suppression documents this distinction without weakening Bandit/Ruff globally.

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

CORE-045 is merged at `34968a01d06d1ae5ef2c5315d417d3c884d6e029` and its post-merge CI/documentation gates are fully GREEN, including both image Trivy scans and CycloneDX SBOM validation.

CORE-046 is therefore unblocked for integration. This revision re-triggers all mandatory gates against the current `main`; historical stacked or preventive runs are not accepted as merge evidence.
