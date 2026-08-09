# CORE-033 — Scope-aware policy

Status: **INTEGRATED_ON_MAIN**

## Objective

Make application, mailbox and resource scope first-class policy context without exposing Microsoft tenant identifiers, mailbox addresses, browser profile paths or session secrets.

## Typed scope model

`m365_mcp.policy_scope` defines closed semantic scope classes:

- account: `product_context` or `professional_session`;
- mailbox: `none`, `primary`, `shared`;
- resource granularity: `account`, `container`, `resource`;
- reviewed container classes: account, plan, mailbox, folder, calendar and task-list.

A `PolicyScope` contains only these semantic classes plus application and surface labels. It contains no raw resource identifier or credential-shaped value.

## Registry-driven derivation

The policy engine derives the canonical scope from Tool Registry and Capability Registry metadata. Matching capability scope must belong to the same application and surface as the tool. Where multiple matching capability definitions exist, the narrowest reviewed container class is selected.

The preserved Planner 0.1 surface may omit an explicit scope temporarily. In that compatibility path, policy derives the exact canonical scope and records:

```text
scope_reason = CANONICAL_SCOPE_DERIVED
scope_derived = true
```

This keeps all 17 existing Planner tools compatible while making scope visible in every policy result. New callers can supply an explicit `PolicyScope`; explicit scope is then verified and cannot be widened silently.

## Fail-closed behavior

An explicit mismatch denies the operation with a typed reason:

- `SCOPE_APPLICATION_MISMATCH`;
- `SCOPE_SURFACE_MISMATCH`;
- `SCOPE_ACCOUNT_MISMATCH`;
- `SCOPE_CONTAINER_MISMATCH`;
- `SCOPE_MAILBOX_MISMATCH`;
- `SCOPE_RESOURCE_MISMATCH`.

Unknown container classes are rejected before evaluation. Inconsistent canonical registry metadata collapses to `SCOPE_METADATA_INVALID`.

## Governance composition

Scope validation occurs before mutation/approval evaluation and can only make the decision stricter. A valid scope does not lower the CORE-032 security tier, enable mutations or bypass approval requirements.

Outlook remains `RESERVED`. Mailbox scope vocabulary exists so later Outlook policy can use the same typed model, but CORE-033 does not expose or activate an Outlook tool or browser operation.

## Planner compatibility

Tests prove:

- canonical Planner task/plan scope derivation;
- explicit matching scope verification;
- application/account/container/resource mismatch denial;
- mailbox scope rejected for Planner;
- unknown container classes rejected;
- scope cannot weaken mutation disablement;
- all 17 preserved Planner tools continue to receive bounded policy scope and remain compatible.

## Integration reconciliation

This requirement's delta is present in `main`. The mandatory CI gate set (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) was GREEN on the merged pull request, and the full gate set was re-executed on post-merge `main` at `9b4a645`.

Mock mode only: no live Microsoft tenant was contacted, no capability is promoted to SUPPORTED by this record, Outlook stays RESERVED, and the 17-tool Planner public ABI is unchanged.
