# PLN-MIG-004 — Planner UIContract fragment ownership

Status: **INTEGRATED_ON_MAIN**

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

The common authentication fragments remain platform-owned. They were subsequently split into the two atomic fragments `common.auth.email` (`auth.login_email_input`, `auth.login_next_button`) and `common.auth.password` (`auth.login_password_input`, `auth.login_signin_button`) per `AUTH-107`, because the email and password surfaces never coexist on the same Microsoft Entra ID sign-in page. The previously declared `auth.mfa_number_display` selector has been removed; MFA number extraction is now the bounded live observation primitive `AUTH-103` and is no longer a `common.auth` selector placeholder.

## Compatibility invariants

The split changes ownership metadata only. Canonical selector values and attestation metadata remain stored under `contracts/ui_fragments` and continue to be loaded by `load_ui_contract_set()`.

Acceptance tests prove:

- 3/3 Planner fragments match the canonical contract set;
- 8/8 Planner-owned selector names are preserved;
- 4/4 common authentication selectors remain platform-owned;
- all 11 legacy-equivalent selectors (8 Planner-owned plus 3 sign-in progression selectors) remain present and in canonical order;
- the legacy `contracts/ui_contract.json` selector mapping remains exactly equal to the fragmented contract projection;
- no selector value is duplicated into Python application metadata.

## Live-support boundary

All existing placeholder/attestation status remains authoritative. This migration does not turn an `UNVERIFIED_LIVE` selector into an attested selector and makes no live UI support claim.

## Current integration gate

PLN-MIG-003 is merged and `main` is post-merge GREEN at `1e39c1df496dc69e9b18ab02d56381e99e400794`. This clean revision is based directly on that integration point and contains only the Planner UIContract ownership declaration, tests and evidence. Merge only after all mandatory CI/security/documentation/image/Trivy/SBOM gates are GREEN.

## Integration reconciliation

This requirement's delta is present in `main`. The mandatory CI gate set (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) was GREEN on the merged pull request, and the full gate set was re-executed on post-merge `main` at `9b4a645`.

Mock mode only: no live Microsoft tenant was contacted, no capability is promoted to SUPPORTED by this record, Outlook stays RESERVED, and the 17-tool Planner public ABI is unchanged.
