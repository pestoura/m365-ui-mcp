# Foundation 0.1.0 is read-only

- Status: Accepted
- Date: 2026-08-08

## Context
Mutations on a UI-driven backend need idempotency, locks, sagas and approvals that are not yet built.

## Decision
Ship 17 read-only tools; policy denies every non-read tool; the worker exposes no mutating HTTP method.

## Consequences
Slower time to value, far lower blast radius; mutation readiness is gated by P-074.
