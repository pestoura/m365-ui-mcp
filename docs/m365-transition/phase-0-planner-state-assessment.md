# Phase 0 — Planner Final-State Assessment & Reconciliation

Status: **MANDATORY TRANSITION GATE**  
Purpose: establish the authoritative Planner baseline **after the currently running delivery cycle has finished**, before any repository rename or architecture migration.

## 1. Principle

This phase deliberately assumes that the Planner repository may have changed substantially between the creation of the transition blueprint and the start of migration.

No implementation decision may be based solely on the state observed when this blueprint was authored.

The first action of the future `m365-ui-mcp` transition is therefore:

```text
DISCOVER -> INVENTORY -> VERIFY -> CLASSIFY -> RECONCILE -> BASELINE -> ONLY THEN MIGRATE
```

## 2. Entry conditions

Phase 0 starts only when:

- the current autonomous Planner implementation cycle has stopped normally or reached its declared delivery boundary;
- no expected merge from that cycle is still pending;
- the operator considers the Planner state stable enough to baseline;
- `main` can be treated as the canonical integration branch.

An unrelated feature branch may remain open, but it must be explicitly inventoried and its relationship to the transition recorded.

## 3. Repository-state discovery

Capture at minimum:

- repository full name;
- default branch;
- final `main` commit SHA;
- commit timestamp;
- repository visibility;
- tags/releases;
- open PRs;
- recently merged PRs;
- active feature branches;
- branch protection / required checks where observable;
- current milestone/backlog state;
- current package/project version;
- current contract/schema versions;
- current Docker image/version naming;
- deployment references and external dependencies.

The output becomes `planner-final-state.json` plus a human-readable `planner-final-state.md` evidence record.

## 4. Implementation inventory

The assessment must distinguish **implemented code**, **mock-only behavior**, **live-attested capability**, **documentation-only specification** and **planned backlog**.

For every major subsystem record one of:

```text
IMPLEMENTED_LIVE
IMPLEMENTED_MOCK_ONLY
IMPLEMENTED_NOT_ATTESTED
SPECIFIED_ONLY
PLANNED
DEPRECATED
BLOCKED
```

Inventory:

### Core / control plane

- FastMCP server and transport;
- tool registration model;
- typed configuration;
- contract/version loader;
- AgentCard / ToolManifest / ExtendedToolManifest;
- CapabilityManifest;
- policy engine;
- approvals;
- locks;
- idempotency;
- sagas/checkpoints;
- reconciliation;
- state store and schema version;
- logging/redaction;
- metrics/tracing;
- health/readiness;
- error taxonomy;
- worker client;
- retry/circuit-breaker behavior;
- result shaping / pagination.

### Browser worker

- Playwright lifecycle;
- Chromium persistent profile;
- startup/lifespan integration;
- authentication state machine;
- MFA behavior;
- Conditional Access handling;
- account-context validation;
- licence/capability discovery;
- selector/locator resolution;
- UIContract loading;
- UI drift behavior;
- navigation model;
- concurrency/queue/locks;
- read-back primitives;
- typed operation boundary;
- error sanitization;
- live egress/network behavior.

### Planner domain

Inventory every capability currently represented in the canonical Planner matrix, including:

- plans/projects;
- tasks/WBS;
- buckets;
- assignments/resources;
- dependencies FS/SS/SF/FF;
- milestones;
- effort/duration;
- timeline/Gantt;
- critical path;
- people/workload;
- goals;
- sprints/backlog;
- custom fields;
- conditional formatting;
- working calendar;
- task history/conversations;
- portfolios/roadmaps;
- sharing/membership;
- import/export;
- reporting/analytics.

## 5. Public-tool inventory

Produce a machine-readable table for every public MCP tool:

| Field | Meaning |
|---|---|
| `name` | canonical public name |
| `version` | tool contract version |
| `domain` | platform/planner/etc. |
| `mutation_class` | READ / SAFE_WRITE / GOVERNED_WRITE / DESTRUCTIVE |
| `implementation_state` | state vocabulary above |
| `capability_keys` | backing capability rows |
| `ui_contract_fragments` | backing UI evidence |
| `read_back` | yes/no/strategy |
| `idempotency` | semantics |
| `approval` | none/configurable/required |
| `compatibility_requirement` | preserve/deprecate/new-version |

This tool inventory becomes the migration compatibility contract.

## 6. Contract and UI evidence assessment

Record:

- all current UIContract files/fragments;
- attestation state per entry;
- evidence timestamps;
- expiry/re-attestation rules;
- selector/locator count;
- operations depending on each contract entry;
- currently degraded/drifted entries;
- live-supported Planner capabilities;
- unsupported or unverified capabilities.

A global `attested=true` must not be assumed to remain an acceptable model. Phase 0 shall identify whether the current implementation already supports partial/fragment attestation and feed that result into the M365 migration.

## 7. Test and CI evidence

Run and record every applicable existing gate without weakening it:

- compile;
- lint;
- type checking;
- unit tests;
- contract/schema validation;
- documentation consistency;
- secret scanning;
- dependency scanning;
- container build;
- Trivy HIGH/CRITICAL gate;
- CycloneDX SBOM generation/validation;
- base-image digest pinning;
- isolated acceptance;
- live read-only acceptance when explicitly authorized and required by the existing Planner release process.

A gate that did not run is **NOT_GREEN**, not PASS.

## 8. Security baseline

Confirm that the final Planner state still enforces:

- browser session isolated from the MCP-facing process;
- no credentials/cookies/tokens in control-plane state;
- no raw browser primitives exposed publicly;
- no automatic MFA approval;
- no Conditional Access bypass;
- no personal browser profile reuse;
- fail-closed policy;
- redacted logs/errors;
- low-cardinality metrics;
- no authenticated-content screenshots persisted by default;
- mutations require the declared policy/approval posture;
- ambiguous mutation outcome is re-read before retry;
- read-back is required before success is asserted.

Any regression becomes a blocker for the M365 transition.

## 9. Network/topology assessment

Explicitly verify live browser egress.

The original Planner compose design used an `internal: true` browser network. The transition assessment must prove how the browser worker reaches Microsoft 365 in live mode without becoming externally reachable.

Target property:

```text
control-plane -> private control network -> browser-worker
browser-worker -> controlled egress -> Microsoft 365
external caller -X-> browser-worker
```

If live egress is not yet solved, record it as a mandatory CORE blocker rather than carrying the topology forward unchanged.

## 10. Baseline artifact and tag

After all applicable Planner gates are green, create a pre-transition baseline tag using the final version, for example:

```text
planner-pre-m365-0.1.0
planner-pre-m365-0.2.0
```

The exact version is discovered at execution time; this document does not assume it remains `0.1.0`.

The tag must identify the exact Planner state from which the M365 architecture is derived.

## 11. Reconcile the transition blueprint

Before implementation:

1. rebase or merge this documentation branch onto the final Planner `main`;
2. compare all architecture assumptions in this blueprint with the discovered baseline;
3. mark each migration proposal as `STILL_REQUIRED`, `ALREADY_IMPLEMENTED`, `SUPERSEDED` or `REQUIRES_REDESIGN`;
4. update target architecture/backlog accordingly;
5. run the Planner CI again;
6. only then authorize the repository rename and package migration.

## 12. Rename preflight

Before renaming `planner-mcp` -> `m365-ui-mcp`, inventory and prepare changes for:

- repository references;
- README links;
- package names;
- CLI entry points;
- Docker image names;
- Compose project/service names;
- environment-variable prefixes;
- volume names/paths;
- Cloudflare MCP portal configuration;
- deployment/runbook references;
- CI/release scripts;
- external documentation;
- Hermes integration references;
- monitoring/Grafana labels;
- consumers that call `planner_*` tools.

The repository rename must not force an immediate breaking rename of public Planner tools.

## 13. Compatibility strategy

Recommended default migration behavior:

```text
PLANNER_* environment names  -> supported temporarily as compatibility aliases
M365_* environment names     -> canonical new names
planner_* MCP tools          -> preserved
m365_* core tools            -> introduced
outlook_* tools              -> introduced
```

Deprecated compatibility aliases must emit structured deprecation metadata and have a documented removal version; they must never disappear silently.

## 14. Exit criteria

Phase 0 is complete only when all are true:

- final Planner `main` state recorded;
- current implementation/specification distinction recorded;
- capability and public-tool inventories complete;
- security invariants verified;
- CI/release evidence recorded;
- topology/egress state understood;
- pre-M365 baseline tag created;
- transition docs reconciled with final code;
- rename impact map complete;
- no unknown blocker remains hidden behind an assumption.

Only then may Phase 1 begin.
