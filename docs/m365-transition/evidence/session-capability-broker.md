# CORE-023 — Session/Capability Broker

## Decision

The browser worker now binds semantic capability authorization to the existing process-owned professional browser session through `SessionCapabilityBroker`.

The broker is deliberately **not** a credential broker. It has no API for cookies, access tokens, refresh tokens, authorization headers, browser storage state or arbitrary page access.

## Authorization contract

A semantic grant requires all of the following:

```text
process-owned browser started
AND AuthState == AUTHENTICATED
AND application/capability exists uniquely in CapabilityRegistry
AND existing UIContract live guard accepts the semantic capability
```

Failure is closed:

- no browser -> `WORKER_UNAVAILABLE`;
- non-authenticated session -> `AUTH_REQUIRED`;
- unknown/ambiguous capability -> `WORKER_UNAVAILABLE`;
- unattested UI contract -> existing `UI_CONTRACT_UNATTESTED` guard.

A successful grant contains only bounded metadata:

```text
application
surface
account_scope
container_scope
capability
session_bound=true
secret_material_exported=false
```

## Worker integration

Current live Planner read surfaces bind to registered semantic capabilities:

```text
/planner/plans                    -> plans.read
/planner/plans/{plan_id}          -> plans.read
/planner/tasks                    -> tasks.read
/planner/tasks/{task_id}          -> tasks.read
/planner/plans/{plan_id}/snapshot -> project_snapshot.read
```

Authentication bootstrap and account/license discovery are not forced through a Planner capability grant. They retain their existing fail-closed live UI guard so authentication can be established before semantic application authorization.

## Readiness integration

`CORE-022` broker viability is now backed by the canonical broker by default:

```text
broker.viable == browser.started AND AuthState.AUTHENTICATED
```

This does not by itself make the worker ready. Profile, UI contract, protocol and lock signals remain independent AND-gates. In particular, protocol and lock remain fail closed until their later roadmap blocks.

## Security invariants

- no cookie/token/storage-state export;
- no arbitrary selector/click/script endpoint;
- only capabilities already present in the closed Capability Registry can be granted;
- grants are application/surface/account/container scoped;
- mock mode remains test-only and does not prove live M365 support;
- account-context correctness remains `CORE-024`;
- controlled Microsoft egress remains `CORE-025`;
- profile serialization and protocol negotiation remain `CORE-026`/`CORE-029`.

## Acceptance coverage

`tests/test_session_capability_broker.py` proves:

- browser + authenticated session are both required for broker viability;
- browser absence and non-authenticated state fail closed;
- unregistered semantic capabilities are rejected;
- a successful grant contains only bounded metadata;
- broker snapshots contain no secret session material.

## Next gate

```text
CORE-023 PR CI/security/images/SBOM GREEN
        -> merge
        -> post-merge main GREEN
        -> CORE-024 account-context enforcement
```
