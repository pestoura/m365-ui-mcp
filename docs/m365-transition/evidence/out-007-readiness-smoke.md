# OUT-007 — Outlook readiness/smoke extension

Status: **PREIMPLEMENTED_STACKED_AWAITING_OUT_006**

## Objective

Provide a bounded Outlook readiness/smoke projection that composes the inert application foundation, mailbox-context verification and capability-discovery evidence without promoting live support or enabling any public execution surface.

## Model

`m365_mcp.apps.outlook.readiness` defines a closed readiness vocabulary:

```text
FOUNDATION_READY
DISCOVERY_READY
BLOCKED
REATTESTATION_REQUIRED
```

The evaluator consumes only sanitized state from OUT-004, OUT-005 and OUT-006.

A report exposes low-cardinality fields only:

- readiness state;
- primary/shared context verification booleans;
- candidate/observed/blocked/re-attestation counts;
- whether evidence-backed read-only discovery may proceed.

## Fail-closed rules

- empty discovery candidate sets are rejected;
- duplicate capability candidates are rejected;
- invalid primary-mailbox context blocks discovery;
- BLOCKED discovery candidates block readiness;
- any re-attestation requirement dominates the result;
- no unobserved foundation state is promoted to discovery-ready.

## Safety boundary

OUT-007 does **not** assert live Outlook support.

The foundation remains:

```text
state = RESERVED
public_tools_enabled = false
browser_operations_enabled = false
```

The readiness projection contains no mailbox address, account/user/tenant identifier, scope/evidence digest, selector, URL, cookie, token, auth header, browser profile path or storage state.

## Acceptance coverage

Tests prove:

- unobserved foundation remains non-promoted;
- evidence-backed candidates can reach bounded `DISCOVERY_READY`;
- invalid primary context fails closed;
- re-attestation dominates;
- shared context is represented only as a boolean verification result;
- duplicate/empty candidate sets are rejected;
- Tool Registry and Capability Registry still expose zero Outlook operations/capabilities.

## Dependency gate

This work is stacked on OUT-006. It must not merge until OUT-006 is merged and post-merge `main` is GREEN. It will then be retargeted to `main` and fully revalidated with the mandatory CI/security/image/Trivy/SBOM/documentation gates.
