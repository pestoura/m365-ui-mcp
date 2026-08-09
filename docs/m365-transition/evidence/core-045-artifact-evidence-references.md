# CORE-045 — Artifact/evidence references

Status: **INTEGRATED_ON_MAIN**

## Objective

Allow semantic results to refer to separately retained artifacts/evidence without embedding large payloads, storage locations, tenant content, or credentials in the control-plane result.

## Reference model

`m365_mcp.result_references.ArtifactReference` carries bounded metadata only:

- role: `ARTIFACT` or `EVIDENCE`;
- semantic artifact type;
- SHA-256 digest of the hidden storage locator;
- SHA-256 content digest;
- MIME type;
- optional non-negative size.

`make_artifact_reference()` accepts the storage locator only at construction time and immediately reduces it to SHA-256. `to_projection()` intentionally omits both the raw locator and its locator digest, exposing only an opaque `reference_id`, role, artifact type, content digest, MIME type and optional size.

The opaque `reference_id` is deterministic over the bounded metadata and permits deduplication/linking without making the underlying storage path part of the semantic result contract.

## Result attachment

`ReferencedResult` wraps an already-produced semantic result and a tuple of references. It does not rewrite or expand the semantic result. Duplicate references are rejected by opaque reference identity.

This keeps CORE-045 separate from:

- CORE-044 projection/reduction operators;
- CORE-046 secret-aware field semantics;
- CORE-047 execution provenance envelopes.

## Fail-closed validation

References reject:

- empty storage locators;
- malformed content or locator digests;
- empty/whitespace semantic artifact types;
- invalid MIME-type shapes;
- negative sizes;
- duplicate references on one result.

## Security/privacy boundary

The projection does not expose the storage locator, mailbox/account identity, tenant content, raw Microsoft resource identifier, browser profile path, cookie, token, storage state or other execution secret. Content integrity is represented only by SHA-256.

## Acceptance coverage

Tests prove:

- raw locators are discarded from projected references;
- deterministic reference identity and sensitivity to content changes;
- artifact and evidence roles remain distinct;
- duplicate references fail closed;
- wrapping preserves the original semantic result object;
- invalid locator/digest/media metadata is rejected.

## Dependency gate

CORE-044 is merged at `3b0560d2c6eff7a8d7f11ce6bded086727fd3add` and its post-merge CI plus canonical documentation gates are GREEN. CORE-045 is therefore unblocked for integration.

This revision re-triggers the complete mandatory gate suite against the current `main`; no historical stacked run is accepted as merge evidence.

## Integration reconciliation

This requirement's delta is present in `main`. The mandatory CI gate set (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) was GREEN on the merged pull request, and the full gate set was re-executed on post-merge `main` at `9b4a645`.

Mock mode only: no live Microsoft tenant was contacted, no capability is promoted to SUPPORTED by this record, Outlook stays RESERVED, and the 17-tool Planner public ABI is unchanged.
