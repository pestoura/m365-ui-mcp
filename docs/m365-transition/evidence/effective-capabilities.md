# CORE-012 — Effective capability projection

## Decision

A Capability Registry definition is necessary but never sufficient to declare support. Effective support is computed from the required evidence dimensions:

```text
registry definition
+ authentication/session state
+ account context
+ UI evidence
+ runtime health
+ policy
+ licence evidence
+ non-mock/live evidence boundary
```

The additional licence dimension preserves the existing Planner capability model; the `live_evidence` boundary prevents deterministic CI mocks from ever becoming evidence of live Microsoft 365 support.

## State computation

Fail-closed precedence:

1. policy denied -> `BLOCKED`;
2. runtime unhealthy -> `BLOCKED`;
3. missing auth/account/UI/licence/live evidence -> `UNVERIFIED_LIVE` with reason codes;
4. all required evidence present -> `READ_SUPPORTED`.

No mutation support is promoted by CORE-012.

## Planner integration

`planner_capabilities` now gathers sanitized evidence from the existing worker interfaces:

- auth status;
- account context;
- licence capability evidence;
- worker health;
- current UIContract attestation;
- current policy decision.

The existing 11 capability names/order and compatibility fields remain. An additive `effective_projection` exposes scoped identity, effective state, reason codes and boolean evidence only.

## Security and privacy

- registry declaration alone cannot promote support;
- mock mode cannot promote `READ_SUPPORTED`;
- policy/runtime failures block support;
- account evidence is reduced to a boolean check for work/school + isolated professional profile;
- no user, tenant, plan, mailbox or message identifiers are persisted in effective projection;
- no session secrets, cookies, tokens or storage state are included;
- current global UIContract attestation is consumed as-is; fragmentation remains CORE-013/014.

CORE-012 deliberately does not refactor the current hardcoded policy implementation; metadata-driven policy remains CORE-030. It consumes the current policy result as one evidence dimension.
