# CORE-013 — Fragmented UIContract storage

## Decision

The previous single `contracts/ui_contract.json` selector document is now represented by a validated contract-set manifest plus deterministic fragments. The legacy document remains temporarily as a compatibility snapshot and is checked for exact selector equivalence in CI.

## Storage layout

```text
contracts/ui_contract_set.json
contracts/ui_fragments/common/auth.json
contracts/ui_fragments/apps/planner/account.json
contracts/ui_fragments/surfaces/planner-premium-web/plan.json
contracts/ui_fragments/surfaces/planner-premium-web/task.json
```

The manifest owns fragment ordering. Each fragment declares its identity, version, structural scope, application/surface binding where applicable, current attestation metadata and selectors.

## Invariants

- all 10 pre-CORE-013 selectors are preserved exactly;
- every selector has exactly one fragment owner;
- fragment IDs are unique and must match the manifest;
- fragment paths cannot escape `contracts/ui_fragments/`;
- common fragments cannot bind an application or surface;
- application fragments require an application and no surface;
- surface fragments require both application and surface;
- malformed, empty or duplicate fragment data fails closed;
- Planner `load_status()` remains a global compatibility aggregation in CORE-013;
- no fragment-specific support/attestation semantics are enabled yet;
- Outlook receives no selectors or runtime capability in this block.

## Deliberate boundary

`CORE-013` changes storage structure only. `CORE-014` will determine attestation independently per fragment and degrade only dependent capabilities. `CORE-015` will introduce a digest for the exact fragment set used by an execution.
