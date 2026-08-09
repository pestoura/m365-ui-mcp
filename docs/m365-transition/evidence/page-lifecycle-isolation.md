# CORE-027 — Page lifecycle isolation

Status: **INTEGRATED_ON_MAIN**

## Objective

Prevent page-local browser state from bleeding between semantic Microsoft 365 operations while preserving the authenticated professional session inside the process-owned persistent browser context.

## Implementation

`PersistentBrowser.operation_page(operation)` is an internal async context manager that:

1. fails closed with `WORKER_UNAVAILABLE` when the process does not own a started browser context;
2. creates a fresh Playwright page for the admitted semantic operation;
3. yields that page only to internal application-adapter code;
4. closes the page deterministically on normal completion, operation failure or cancellation.

The persistent browser context remains the intentional authentication boundary. Cookies/session material are neither copied nor exported. Only page-local navigation/DOM/runtime state is isolated per operation.

## Security boundary

This block does **not** add any public or generic browser primitive. It exposes no URL navigation, selector, XPath, script execution, cookies, tokens, headers or storage state through MCP or the worker API.

The existing context-wide controlled-egress route policy from CORE-025 continues to apply to every new page. Profile-level serialization from CORE-026 remains a separate admission/locking concern.

## Acceptance coverage

Repository tests prove:

- sequential operations receive distinct pages;
- page-local state written by one operation is absent from the next page;
- every operation page closes after success;
- every operation page closes after an exception;
- every operation page closes after cancellation;
- page acquisition fails closed when the browser context is unavailable.

No CI test authenticates to a real Microsoft tenant and this block does not promote any Planner UI fragment to live support.

## Deferred boundaries

- closed typed worker operation envelopes: CORE-028;
- protocol version negotiation: CORE-029;
- expanded sanitized worker error mapping: CORE-030;
- Outlook remains `RESERVED`.

## Integration reconciliation

This requirement's delta is present in `main`. The mandatory CI gate set (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) was GREEN on the merged pull request, and the full gate set was re-executed on post-merge `main` at `9b4a645`.

Mock mode only: no live Microsoft tenant was contacted, no capability is promoted to SUPPORTED by this record, Outlook stays RESERVED, and the 17-tool Planner public ABI is unchanged.
