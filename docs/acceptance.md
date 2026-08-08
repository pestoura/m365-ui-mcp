# Acceptance

Scope: what "accepted" means for `pestoura/planner-mcp`, the evidence that must exist, the isolated acceptance procedure, read-back evidence requirements, and the live read-only protocol. Companions: [testing.md](testing.md), [release-process.md](release-process.md), [observability.md](observability.md), [deployment.md](deployment.md), [ui-contract.md](ui-contract.md).

Prime directive: **acceptance is browser-evidenced**. A capability is accepted only when the browser worker demonstrably performed it and the result was read back from the UI. Microsoft Graph observations may accompany evidence as context but can never substitute for browser read-back, and their absence never blocks acceptance.

## 1. Acceptance levels

| Level | Environment | Data | Mutations | Who runs it | Gate for |
|-------|-------------|------|-----------|-------------|----------|
| A0 Structural | CI | none | none | automation | every PR |
| A1 Functional | CI, mock UI | synthetic | mock only | automation | every PR |
| A2 Isolated | compose stack, mock UI | seeded synthetic | yes (mock) | automation, nightly + pre-release | release |
| A3 Live read-only | real tenant | real | **none** | human operator | claiming live support |
| A4 Live mutating | real tenant, dedicated non-production plan | real, disposable | yes, per-operation approval | human operator | claiming live write support |

No level may be skipped, and A3 always precedes A4.

## 2. Acceptance criteria

### 2.1 Global criteria

| ID | Criterion | Verified at |
|----|-----------|-------------|
| AC-G1 | Every MCP tool in [tool-catalog.md](tool-catalog.md) is discoverable, schema-valid, and returns the documented error taxonomy. | A1 |
| AC-G2 | Every mutating tool supports `dry_run` and produces zero side effects in that mode. | A1, A2 |
| AC-G3 | Every mutating tool is idempotent under key replay. | A1, A2 |
| AC-G4 | Every mutation is followed by a read-back and fails if read-back diverges. | A2, A4 |
| AC-G5 | Every operation produces exactly one hash-chained audit row. | A2 |
| AC-G6 | No log record in the run contains credential, PII, or business-content values. | A1, A2, A3 |
| AC-G7 | Graph unavailability degrades context only; all functional scenarios pass with Graph disabled. | A2 |
| AC-G8 | The worker is unreachable from outside the internal network. | A2 |
| AC-G9 | Selector attestation reports zero misses. | A2 (mock), A3 (live) |
| AC-G10 | MFA events emitted to Hermes contain exactly the permitted sanitized fields and no approval affordance. | A2, A3 |

### 2.2 Capability criteria

Each Planner Premium capability listed in [planner-premium-capabilities.md](planner-premium-capabilities.md) carries a row in the capability matrix with an explicit status:

| Status | Meaning | Minimum evidence |
|--------|---------|------------------|
| `unsupported` | Not implemented; tool denies with `unsupported_premium`. | A1 denial test |
| `mock-verified` | Works against the mock UI. | A2 evidence bundle |
| `live-read-verified` | Reading verified on real Planner. | A3 evidence bundle |
| `live-verified` | Writing verified on real Planner with read-back. | A4 evidence bundle |

Documentation may state a capability as supported **only** at `live-verified`. Any weaker status must be rendered verbatim in user-facing docs.

## 3. Evidence formats

Evidence is a directory bundle plus a signed manifest.

```
evidence/<level>/<utc-timestamp>-<git-sha>/
  manifest.json
  scenarios/<scenario-id>/
    intent.json          # normalized tool call(s), redacted
    result.json          # tool responses
    read_back.json       # observed post-state + diff verdict
    audit.ndjson         # audit rows for this scenario
    logs.ndjson          # redacted log slice, filtered by operation_id
    metrics.prom         # metrics snapshot delta
    trace.json           # optional exported spans
    screenshots/         # A2/A3/A4 only, sanitized, opt-in
  selectors/attestation.json
  environment.json       # image digests, versions, compose hash, env label
  summary.md             # human-readable verdict per criterion
```

`manifest.json` fields:

| Field | Notes |
|-------|-------|
| `level` | `A2`, `A3`, `A4`. |
| `git_sha`, `version` | Build identity, must match `plannermcp_build_info`. |
| `image_digests` | All container images by digest, per [deployment.md](deployment.md). |
| `scenarios` | Array of `{id, criteria[], outcome, operation_ids[]}`. |
| `criteria_results` | Map criterion → `pass\|fail\|not_applicable` with justification for the last. |
| `operator` | Human name/id for A3/A4; `automation` otherwise. |
| `hashes` | sha256 of every file in the bundle. |
| `chain_head` | Audit hash-chain head at bundle close. |

Rules: bundles are immutable; a correction produces a new bundle referencing the prior one via `supersedes`. Screenshots must pass the sanitization check (no real names/e-mails visible) before inclusion, and are omitted entirely if that cannot be guaranteed.

## 4. Isolated acceptance procedure (A2)

Preconditions: clean checkout at the release candidate SHA; all A0/A1 gates green; image digests pinned; no live credentials present in the environment.

| Step | Action | Pass condition |
|------|--------|----------------|
| 1 | Bring up the compose stack in `isolated` profile with fresh volumes. | All services healthy within 120 s. |
| 2 | Record `environment.json` (digests, versions, compose file hash). | All images referenced by digest. |
| 3 | Seed the mock Planner dataset from `tests/fixtures/seed/planner_seed.json`. | Seed checksum matches. |
| 4 | Assert isolation: worker port unreachable from host; egress to public internet blocked. | Both assertions fail-closed. |
| 5 | Run selector attestation against the mock UI. | Zero misses. |
| 6 | Execute the scenario suite through the MCP endpoint exactly as a client would. | 100 % scenarios pass. |
| 7 | Re-run every mutating scenario with the same idempotency key. | `outcome=replayed`, no additional state change. |
| 8 | Re-run the suite with the Graph client disabled. | Identical functional results. |
| 9 | Run the redaction detector over the full log stream. | Zero findings. |
| 10 | Verify audit hash chain end to end. | Chain valid, one row per operation. |
| 11 | Export the evidence bundle and compute hashes. | Manifest complete, all criteria mapped. |
| 12 | Tear down; assert volumes removed. | No residue. |

Scenario suite must include at minimum: plan/bucket/task read; task create; task update (title, dates, assignments); premium field update; checklist add/complete; bucket move; task complete; task delete; conflict/duplicate handling; session expiry mid-operation; selector fallback path; read-back mismatch injection (must fail loudly); worker restart mid-queue.

## 5. Read-back evidence

Read-back is the verification step that re-reads the mutated resource *from the UI* after the write and compares it to the intended post-state.

| Element | Requirement |
|---------|-------------|
| Source | Fresh UI read, not the write response, not a cached DOM node. |
| Timing | After the UI settles; bounded wait with explicit timeout; no fixed sleep. |
| Scope | Every field the operation intended to change, plus a guard set of fields it must **not** change. |
| Comparison | Normalized per [state-model.md](state-model.md); comparison of hashes for content fields, exact for enumerations and dates. |
| Verdict | `match`, `mismatch`, `indeterminate`. `indeterminate` is treated as failure. |
| Record | `read_back.json` with `expected_hashes`, `observed_hashes`, `changed_fields`, `guard_fields_unchanged`, `verdict`, `attempts`, `duration_ms`. |
| Failure handling | Operation reported `failed`; audit row records the divergence; no automatic rollback is attempted unless the tool declares a compensating action. |

`read_back.json` example:

```json
{
  "operation_id": "01J...",
  "resource": {"kind": "task", "id_hash": "9f2a1c4b7d0e5a63"},
  "expected_hashes": {"due_date": "2f0c...", "priority": "8ab1..."},
  "observed_hashes": {"due_date": "2f0c...", "priority": "8ab1..."},
  "guard_fields_unchanged": ["bucket", "assignments"],
  "changed_fields": ["due_date", "priority"],
  "verdict": "match",
  "attempts": 1,
  "duration_ms": 1840
}
```

## 6. Live read-only protocol (A3)

Purpose: prove the UI contract holds against the real Planner Premium surface without any risk of data change.

| Guard | Implementation |
|-------|----------------|
| Mode | Worker started with `PLANNER_MODE=read_only`; mutating tool handlers are not registered at all, not merely refused. |
| Interaction allowlist | Only navigation, scroll, expand, and read actions permitted; the action dispatcher rejects click targets not present in the read-only allowlist. |
| Human presence | An operator must be present for the whole session and named in the manifest. |
| Session | Uses the persistent profile; MFA approval happens exclusively in Microsoft Authenticator (see [authentication-and-mfa.md](authentication-and-mfa.md)). |
| Scope | A named, pre-agreed plan; the operator confirms scope before start. |
| Duration | Time-boxed; the worker exits on the configured deadline. |
| Evidence | Selector attestation report, redacted logs, screenshots only after sanitization review. |
| Abort | Any unexpected modal, write-capable dialog, or selector miss aborts the session and is recorded. |

Post-session checklist: confirm zero mutating operations in the audit export, confirm no write-capable code path executed (assertion counter `worker_operations_total{outcome}` shows only read tools), sanitize and attach evidence, then update the capability matrix to `live-read-verified` only for the capabilities actually exercised.

## 7. Live mutating protocol (A4)

Allowed only after A3 passes with zero selector misses. Requirements: a dedicated non-production plan; per-operation human approval recorded in the audit row; `dry_run` executed and reviewed first for each operation; read-back mandatory; a documented manual undo for each operation before it is attempted; and a hard stop on the first unexpected divergence. A4 is never scheduled, never automated, and never run from CI.

## 8. Rejection conditions

Acceptance fails outright — regardless of other results — on any of: a redaction finding, a broken audit chain, a selector miss at the level being claimed, a read-back mismatch not deliberately injected, a mutation observed during A3, worker reachability from outside the internal network, an image referenced by tag instead of digest, or an evidence bundle whose hashes do not verify.

## 9. Backlog mapping

| Item | Backlog keys |
|------|--------------|
| Evidence bundle format + manifest signing | P-070, P-071 |
| Isolated acceptance harness | P-071, P-072 |
| Read-back verifier | P-026, P-027 |
| Live read-only mode + allowlist | P-073 |
| Capability matrix automation | P-074 |
