# REL-001 — M365 threat model update

## Scope

This review covers the broadened M365 control plane, private browser worker, HITL approval boundary, evidence/observability plane, Planner semantics, and the reserved Outlook application surface. Microsoft Graph is not an execution path. Outlook remains `RESERVED`; synthetic or isolated acceptance never promotes LIVE support.

## Protected assets

- browser session/profile material, cookies and storage state;
- tenant and mailbox context binding;
- HITL approvals and per-operation authorization decisions;
- semantic requests, result references, checkpoints and evidence digests;
- mailbox, calendar, contact and task content processed transiently;
- policy metadata, capability/UI-contract bindings and execution provenance.

## Trust and attack surfaces

The relevant boundary chain is client/LLM → MCP front door → control plane → private browser worker → Microsoft 365 tenant UI, with observability as a sanitized sink. Browser handles, selectors, cookies and raw session objects must not cross from the worker into the public semantic interface.

## Threat catalogue and required controls

| Threat | Security objective | Required control |
|---|---|---|
| Spoofed or replayed HITL approval | Authorization integrity | approval scoped to operation/run/node; no aggregate authorization; fail closed on missing or mismatched approval |
| Cross-tenant or cross-mailbox context mix-up | Tenant isolation | explicit context binding; isolated browser profiles; opaque synthetic identities in fixtures |
| Browser primitive or selector injection | Interface integrity | semantic tools only; no public generic browser operation, raw selector or browser object |
| Arbitrary URL / SSRF-style browser egress | Network containment | HTTPS-only closed allowlist; denied requests aborted before Playwright navigation |
| Secret, cookie or storage-state exfiltration | Credential confidentiality | worker-local session state; no logging or control-plane projection of cookies/tokens/storage state |
| Mail/calendar/contact body leakage through evidence | Data minimization | evidence uses bounded IDs, digests, counters and state; raw bodies/attachments excluded by default |
| Synthetic results represented as LIVE | Assurance integrity | explicit synthetic/live-support state; Outlook public registry remains empty until genuine live acceptance |
| Cross-run checkpoint/result confusion | Execution integrity | typed references, provenance, lifecycle validation and checkpoint-chain validation |
| Unbounded batch/DAG authority | Blast-radius control | bounded node counts/parallelism and independent per-node policy/approval decisions |
| Runtime/container privilege escalation | Execution containment | non-root runtime, no-new-privileges, dropped capabilities, read-only/tmpfs boundaries and digest-pinned images |

## Residual risk and acceptance boundary

Browser automation necessarily processes authenticated tenant UI state inside the worker. Residual risk is contained by worker isolation, egress controls, policy/HITL and sanitized evidence, but cannot be treated as eliminated. Any claim of Outlook LIVE support requires REL-013 and later live acceptance evidence; this document alone provides no LIVE attestation.

## Regression invariants

1. No Microsoft Graph execution path.
2. No public generic browser operation, selector or browser handle.
3. Outlook stays `RESERVED` with zero public Outlook tools until live acceptance.
4. Synthetic fixtures use opaque identities and must never imply tenant observation.
5. Approval, policy and evidence remain scoped to individual operations/nodes.
6. Secrets and session state remain outside logs and semantic result projections.
