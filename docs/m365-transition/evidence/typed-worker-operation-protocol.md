# CORE-028 — Typed worker operation protocol

Status: **IMPLEMENTED_AWAITING_GATES**

## Objective

Replace implicit worker-operation semantics with a closed, typed application-neutral envelope without introducing a generic browser endpoint.

## Closed operation vocabulary

`WorkerOperation` currently contains only the semantic worker surface required by the preserved Planner baseline and common session/account functions:

- `auth.status`
- `auth.start`
- `auth.resume`
- `auth.session`
- `account.context`
- `account.license`
- `planner.plan.list`
- `planner.plan.get`
- `planner.task.list`
- `planner.task.get`
- `planner.project.snapshot`

Unknown operation values fail Pydantic validation before executor admission.

## Typed arguments

The request envelope uses a discriminated union:

- `NoArguments(kind="none")`
- `PlanArguments(kind="plan", plan_id=...)`
- `TaskArguments(kind="task", task_id=...)`

A model-level invariant binds each enum member to its exact argument family. Operation/argument mismatches fail closed.

All models use `extra="forbid"`. Browser-shaped command fields such as URL, selector, XPath, JavaScript/script, headers, cookies, tokens and storage state are not part of the protocol.

## Dispatch boundary

The private worker exposes `POST /operations` as a **closed semantic dispatcher**, not a browser primitive. Valid requests are admitted through the CORE-026 `ProfileSerializedExecutor` and mapped to the existing semantic worker handlers. Existing compatibility routes remain unchanged.

The worker still publishes no host port; CORE-025 network boundaries remain in force.

## Response envelope

Successful execution returns the same semantic result inside a typed envelope containing:

- fixed schema version `1`;
- opaque bounded `request_id`;
- closed operation enum;
- semantic result object.

CORE-030 remains responsible for the expanded sanitized worker error taxonomy.

## Version boundary

The envelope has a fixed schema identifier so its wire shape is deterministic, but **CORE-028 does not negotiate compatibility**. The `protocol_compatible` readiness signal remains false by default. Control-plane/worker compatibility negotiation and fail-closed readiness promotion are exclusively CORE-029.

## Acceptance coverage

Tests prove:

- exact operation-to-argument binding;
- rejection of unknown operations;
- rejection of extra/browser-shaped fields;
- closed enum equality with the current semantic surface;
- typed dispatch preserves existing mock Planner semantics;
- explicit empty arguments for no-input operations;
- CORE-028 does not prematurely promote protocol readiness.

No CI test authenticates to a real Microsoft tenant. Outlook remains `RESERVED`.
