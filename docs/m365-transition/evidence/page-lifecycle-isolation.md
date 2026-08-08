# CORE-027 — Page lifecycle isolation

Status: **IMPLEMENTED_AWAITING_GATES**

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
