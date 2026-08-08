# CORE-030 — Worker error taxonomy expansion

Status: **IMPLEMENTED_AWAITING_GATES**

## Objective

Preserve stable semantic worker failures while preventing internal exception text or arbitrary context from crossing the private control-plane/worker boundary.

## Closed error projection

The typed worker boundary now projects failures into a bounded `WorkerErrorEnvelope` containing only:

- fixed schema version;
- request ID from the validated request;
- closed semantic operation;
- closed error code;
- curated generic message;
- retryability flag;
- application/capability scope derived from the closed operation registry.

Application and capability metadata are never accepted from exception context. Planner operation scope is derived from `WorkerOperation`, so malicious or accidental internal context cannot relabel a failure as another application/capability.

## Preserved safe codes

The current closed worker vocabulary preserves or maps the established safe codes required by the existing runtime:

- `WORKER_BUSY`
- `WORKER_UNAVAILABLE`
- `AUTH_REQUIRED`
- `BLOCKER_CONDITIONAL_ACCESS`
- `UI_CONTRACT_UNATTESTED`
- `UI_DRIFT`
- `POLICY_DENIED`
- `APPROVAL_REQUIRED`
- `PLAN_NOT_FOUND`
- `TASK_NOT_FOUND`
- `PROTOCOL_INCOMPATIBLE`
- fallback `WORKER_ERROR`

Unknown exceptions collapse to `WORKER_ERROR`; their raw text and context are discarded.

## Validation-error boundary

FastAPI request-validation failures use a sanitized 422 response and do not echo malformed request values. This is important because default validation output can include rejected input values, including browser-shaped fields that are intentionally forbidden by CORE-028.

## Protocol execution gate

CORE-030 also closes the final CORE-029 execution-path gap: `POST /operations` now fails closed with `PROTOCOL_INCOMPATIBLE` until the worker has completed a compatible protocol handshake. Readiness and actual typed execution therefore agree on protocol compatibility.

Historical compatibility routes remain available and unchanged; the handshake requirement applies to the new typed operation protocol.

## Secret/session boundary

Worker error responses never project:

- raw exception messages;
- arbitrary exception context;
- URLs;
- selectors/XPath/DOM data;
- cookies, tokens, headers or storage state;
- tenant/account/user identifiers;
- profile paths.

## Acceptance coverage

Tests prove:

- raw exception text and arbitrary context are stripped;
- application/capability scope is operation-derived;
- safe not-found codes are preserved without raw HTTP detail;
- typed operations fail closed before protocol negotiation;
- typed not-found responses do not echo resource identifiers;
- malformed browser-shaped requests do not echo rejected input.

No CI test authenticates to a real Microsoft tenant. Outlook remains `RESERVED`.
