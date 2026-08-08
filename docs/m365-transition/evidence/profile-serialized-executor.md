# CORE-026 — Profile-level serialized executor

## Decision

Each isolated professional browser profile now owns a bounded serialized executor. At most one admitted operation may actively use the profile at a time. Additional work waits only up to the configured queue capacity; excess work fails closed with the typed `WORKER_BUSY` error.

## Concurrency boundary

`ProfileSerializedExecutor` separates admission from execution:

- one operation lock protects the profile from overlapping browser work;
- a bounded admission counter prevents unbounded memory/work accumulation;
- rejected work is represented by a callable factory, so no side effect starts before admission;
- cancellation and exceptions release admission state in `finally` blocks;
- `asyncio.Lock` preserves waiter fairness for admitted operations.

The default worker owns one executor instance for its one persistent professional profile. The executor is stored only on internal FastAPI application state; no public generic executor/browser endpoint is exposed.

## Readiness integration

The previously conservative `lock_viable` readiness signal is now backed by the real executor subsystem instead of a hard-coded false default. This does not make the worker globally ready: browser/profile/auth/UI contract/broker/protocol signals must still all pass independently.

The executor health projection contains only bounded operational metadata (`active`, `queued`, `max_queue`, `viable`). It does not contain profile paths, account identifiers, tenant identifiers, URLs, selectors, cookies, tokens or storage state.

## Failure semantics

Queue exhaustion raises `WORKER_BUSY` with only the semantic operation name and queue capacity in the error context. Browser/session secret material is never added to errors.

## Evidence

Automated tests prove:

- concurrent operations never overlap on one profile;
- admitted operations retain FIFO lock ordering;
- queue overflow fails immediately with `WORKER_BUSY`;
- cancellation of a waiter releases capacity;
- an operation exception releases the executor for subsequent work;
- invalid negative queue capacity is rejected;
- default worker readiness now receives the real positive lock/executor viability signal while remaining fail-closed on the other unresolved live subsystems.

## Explicit boundaries

CORE-026 does not implement page lifecycle isolation (CORE-027), a public or generic worker operation endpoint (forbidden), typed worker protocol envelopes (CORE-028), or protocol negotiation (CORE-029). Mock mode remains mock evidence only.
