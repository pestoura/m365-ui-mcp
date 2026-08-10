# REL-002 — M365 trust-boundary review

## Boundary model

The reviewed flow is client/LLM → MCP front door → control plane → private browser worker → Microsoft 365 tenant UI. Observability/evidence is a sanitized sink, not an execution hop. HITL approval is an authorization boundary between semantic intent and governed mutation/outbound execution.

## Zone responsibilities

| Zone | May hold | Must not expose across the boundary |
|---|---|---|
| Client / LLM | semantic request and bounded semantic result | cookies, storage state, raw browser handles/selectors |
| MCP front door | validated semantic input/output envelopes | browser primitives, tenant session material |
| Control plane | policy, lifecycle, typed references, approvals, provenance | cookies, Playwright objects, raw DOM/selector state |
| Browser worker | isolated authenticated profile, browser runtime, UI contract adapter | session material to callers/logs; public inbound browser surface |
| M365 tenant UI | tenant application state | direct Graph execution path through this product |
| Observability / evidence | low-cardinality state, opaque IDs, digests, counters | mail bodies, attachments, cookies, tokens, selectors, screenshots by default |

## Allowed flows

- Client/front door exchange semantic tool input/output only.
- Control plane sends internal semantic execution instructions to the private worker over the internal network.
- Worker accesses M365 UI only through governed egress and UI-contract semantics.
- Worker returns normalized semantic results/read-back, never browser objects.
- HITL approval is scoped to the specific operation/run/node that consumes it.
- Observability receives sanitized evidence after redaction/minimization.

## Denied flows

- Public caller → browser worker direct network access.
- Control plane or public tool → arbitrary URL, raw selector, DOM handle, cookie or storage state.
- Browser worker session/profile → logs, result payloads or evidence store.
- One tenant/profile → another tenant/run without explicit isolated context binding.
- One approval token → unrelated operation/node or aggregate BATCH/DAG authority.
- Synthetic fixture → claim of observed tenant capability or Outlook LIVE support.

## Cross-tenant and session isolation

Each authenticated browser profile is scoped to its tenant/context and kept inside the worker boundary. Session-state reuse across tenant contexts is forbidden. Context mismatches, missing binding, ambiguous mailbox identity, or invalid approval state fail closed rather than selecting an implicit default.

## Outlook boundary

Outlook remains `RESERVED`. Its internal synthetic/readiness models do not create public tools or browser operations. LIVE support remains `UNOBSERVED` until the dedicated live acceptance gates beginning at REL-013 are satisfied.

## Review disposition

The target architecture is consistent with the required trust boundaries provided the regression invariants above remain enforced by tests, policy and deployment configuration. This review does not authorize a new execution surface and does not weaken any existing gate.
