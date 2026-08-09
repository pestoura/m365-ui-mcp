# CORE-047 — Execution provenance envelope

Status: **IMPLEMENTED_AWAITING_CURRENT_BASE_GATES**

## Objective

Attach bounded, deterministic execution provenance to semantic results without exposing raw operation identifiers, Microsoft resource ids, tenant content, or browser/session secrets.

## Provenance envelope

`m365_mcp.execution_provenance.ExecutionProvenance` records:

- schema version `execution-provenance-v1`;
- SHA-256 digest of the raw operation id;
- closed application key;
- semantic tool name and exact version;
- execution mode: `MOCK`, `LIVE`, or `SIMULATION`;
- policy decision;
- CORE-032 security tier;
- timezone-aware start/completion timestamps;
- derived duration in milliseconds;
- optional CORE-037 state-identity digest;
- optional CORE-040/042 checkpoint digest;
- zero or more CORE-045 evidence reference ids.

The raw operation id is accepted only at construction time and immediately reduced to SHA-256.

## Live-evidence invariant

`LIVE` provenance requires at least one evidence reference id. A result cannot therefore label itself LIVE while carrying no reviewed evidence reference. MOCK and SIMULATION provenance do not require live evidence.

Evidence reference ids must be unique and valid lowercase SHA-256 values.

## Deterministic integrity

`provenance_digest` is SHA-256 over canonical sorted JSON from the projected bounded metadata. Semantic changes such as a different tool, mode, tier, state/checkpoint identity, timing, or evidence set change the provenance digest.

## Relationship to adjacent phases

- CORE-045 defines bounded artifact/evidence references.
- CORE-046 guarantees secret fields cannot be projected in clear text.
- CORE-047 attaches execution provenance without weakening either control.
- CORE-048/049/050 add metrics derived from these bounded execution/result signals.

## Fail-closed validation

The envelope rejects:

- unsupported schema version;
- malformed operation/state/checkpoint/evidence digests;
- invalid semantic tool names;
- empty tool versions;
- timezone-naive timestamps;
- completion before start;
- duplicate evidence references;
- LIVE provenance without evidence.

## Security/privacy boundary

The projected envelope contains no raw operation id, raw Microsoft resource id, mailbox/account address, tenant content, request/result payload, browser profile path, cookie, token, authorization header or storage state.

## Acceptance coverage

Tests prove:

- raw operation ids are not projected;
- bounded application/tool/mode/policy/tier/timing metadata is preserved;
- LIVE requires evidence;
- state/checkpoint digests are optional but validated;
- invalid timing and duplicate evidence fail closed;
- timezone-aware timestamps are mandatory;
- provenance digest changes when semantic execution context changes.

## Dependency gate

CORE-046 is merged at `a5a0e59ea005296fa532e48cea92e2f4cf11d1c8` and its post-merge `main` validation is fully GREEN, including functional gates, filesystem/dependency/secret scanning, both image builds, Trivy HIGH/CRITICAL scans and CycloneDX SBOM validation.

CORE-047 is therefore formally unblocked for integration. This revision re-triggers the complete mandatory suite against the current `main`; historical stacked/preventive runs are not accepted as merge evidence.
