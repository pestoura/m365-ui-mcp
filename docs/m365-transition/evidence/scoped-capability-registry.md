# CORE-011 — Scoped Capability Registry

## Decision

Capability identity is no longer only a flat semantic key. The canonical definition includes all five dimensions required by the transition architecture:

```text
application
surface
account_scope
container_scope
capability
```

`m365_mcp.capability_registry` stores **scope classes**, not tenant content or concrete account/container identifiers.

## Current Planner definitions

The 11 existing Planner capability keys are preserved in their current order. Their initial scope classes are:

- application: `planner`;
- surface: `planner_web`;
- account scope: `professional_session`;
- container scope: `account` for account-level plan/portfolio discovery and `plan` for plan-scoped capabilities.

There are no Outlook capability definitions yet; Outlook remains `RESERVED` in the Application Registry.

## Boundary with CORE-012

CORE-011 defines **what a capability is and where it is scoped**. It does not decide whether that capability is effectively usable.

Effective capability state will be computed by CORE-012 from:

```text
registry definition
+ authentication/session state
+ account context
+ UI evidence
+ runtime health
+ policy
```

The existing global UIContract attestation behavior is intentionally not redesigned in this block; fragmentation and per-fragment attestation remain CORE-013/014.

## Security properties

- exact duplicate scoped identities fail closed;
- unknown applications fail closed;
- malformed/whitespace scope keys fail closed;
- the same semantic capability may exist in multiple explicit scopes without collision;
- Tool Registry capability references are tested against Capability Registry definitions;
- snapshots contain abstract scope classes only, not mailbox/account/tenant/container IDs;
- no support state is promoted to live by registry declaration alone.
