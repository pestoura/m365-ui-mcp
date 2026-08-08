# PLN-MIG-004 — Planner UIContract fragment ownership

Status: **PREIMPLEMENTED_STACKED_AWAITING_PLN_MIG_003**

## Objective

Make the Planner-specific portion of the fragmented UIContract an explicit Planner application-owned contract while preserving the existing canonical JSON documents, loader behavior, legacy selector parity and attestation state.

## Planner-owned fragment partition

`m365_mcp.apps.planner.ui_contracts` declares three Planner fragments in canonical manifest order:

1. `planner.plan-surface`
   - surface: `planner-premium-web`
   - capabilities: `plans.read`, `project_snapshot.read`
   - selectors: `plan.list_container`, `plan.list_item`, `plan.title`
2. `planner.task-surface`
   - surface: `planner-premium-web`
   - capabilities: `tasks.read`, `buckets.read`, `project_snapshot.read`
   - selectors: `task.list_container`, `task.list_item`, `task.title`, `task.bucket`
3. `planner.account`
   - application scope
   - selector: `account.context_menu`

The common `common.auth` fragment remains platform-owned and retains the two authentication selectors `auth.login_email_input` and `auth.mfa_number_display`.

## Compatibility invariants

The split changes ownership metadata only. Canonical selector values and attestation metadata remain stored under `contracts/ui_fragments` and continue to be loaded by `load_ui_contract_set()`.

Acceptance tests prove:

- 3/3 Planner fragments match the canonical contract set;
- 8/8 Planner-owned selector names are preserved;
- 2/2 common authentication selectors remain platform-owned;
- all 10 historical selectors remain present and in canonical order;
- the legacy `contracts/ui_contract.json` selector mapping remains exactly equal to the fragmented contract projection;
- no selector value is duplicated into Python application metadata.

## Live-support boundary

All existing placeholder/attestation status remains authoritative. This migration does not turn an `UNVERIFIED_LIVE` selector into an attested selector and makes no live UI support claim.

## Dependency gate

This work is stacked on PLN-MIG-003. It must not merge until PLN-MIG-003 is merged and post-merge `main` is GREEN. It will then be retargeted to `main` and all mandatory CI/security/image/Trivy/SBOM/documentation gates will run against the current integration base.
