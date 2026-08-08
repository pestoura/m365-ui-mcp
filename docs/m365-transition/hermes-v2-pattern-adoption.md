# Hermes MCP Bridge v2 Pattern Adoption for m365-ui-mcp

Status: **PLANNED / CONCEPTUAL ADOPTION**

## 1. Purpose

`m365-ui-mcp` reuses architectural ideas already documented for Hermes MCP Bridge v2 without coupling the two products or making Hermes a mandatory execution dependency.

The Hermes v2 baseline remains a separate product plan. This document defines which concepts are adopted, adapted or explicitly not copied.

## 2. Core execution principle — ADOPT

```text
DETERMINISTIC WORK -> CODE
KNOWN WORKFLOW    -> RUNBOOK
REASONING         -> LLM
```

For Microsoft 365 UI automation this means:

- reading a known mailbox view is code;
- applying a known category is code;
- moving a message to a known folder is code;
- creating a calendar event from fully structured arguments is code;
- a stable repeated triage flow can become a runbook;
- interpreting an ambiguous human request may use the caller LLM;
- diagnosing an unknown UI failure may justify controlled agentic escalation;
- the actual known UI operation must not require a second LLM merely to click known controls.

## 3. Preferred execution modes — ADOPT

```text
DIRECT > BATCH > DAG/RUNBOOK > AGENTIC
```

Supported conceptual modes:

| Mode | m365-ui-mcp meaning | LLM required inside execution plane |
|---|---|---:|
| DIRECT | one typed UI/domain operation | no |
| BATCH | multiple independent typed operations in one request | no |
| DAG | typed dependencies/bindings between operations | no |
| RUNBOOK | versioned deterministic workflow | no |
| AGENTIC | unknown/new reasoning problem | yes/conditional |
| HYBRID | deterministic path first, bounded reasoning escalation if declared | conditional |

The browser profile may constrain actual parallel UI execution; BATCH/DAG still reduce MCP round-trips and allow deterministic scheduling even when browser steps serialize.

## 4. Direct Execution Plane — ADOPT

Known M365 operations should execute directly through the control plane and browser worker:

```text
MCP client
-> schema/tool registry
-> capability/policy
-> worker operation
-> UI
-> read-back
-> result
```

Do not route deterministic work through:

```text
client -> Hermes agent -> Hermes LLM -> generic skill -> browser
```

unless reasoning is explicitly required.

Benefits to measure:

- fewer LLM round-trips;
- lower token consumption;
- lower latency;
- smaller context growth;
- fewer interpretation failures;
- clearer audit provenance.

## 5. Canonical Tool Registry — ADOPT AND EXTEND

Adopt Hermes v2 registry metadata including:

```text
canonical_name
version
description
input_schema
output_schema
read_only
mutation_class
risk_class
policy_action
required_resource_scope
idempotency_semantics
timeout
retry_class
concurrency_hint
lock_hint
backend
provenance
result_shaping
cost_hint
stability
deprecated
version_added
latency_class
cost_class
rate_limit_class
llm_required
security_tier
```

Extend for UI automation with:

```text
application
surface
ui_capability_keys
ui_contract_fragments
account_scope
container/mailbox_scope
read_back_strategy
interaction_class
session_requirement
```

## 6. Capability Projection — ADOPT AND ADAPT

Hermes v2 separates registration from current capability availability. M365 must do the same.

Tool exists != tool usable.

A tool projection is calculated from:

```text
registry definition
+ account/tenant surface
+ mailbox/resource scope
+ UIContract attestation
+ runtime/browser health
+ policy
+ authentication/account context
= projected effective capability
```

Possible effective states include:

```text
AVAILABLE
DEGRADED
UNAVAILABLE
UNAUTHORIZED
UNATTESTED
BLOCKED
```

This prevents the MCP from exposing a capability as usable merely because code exists.

## 7. Credential Broker — ADAPT, DO NOT COPY LITERALLY

Hermes v2 uses a Credential Broker concept for tool-specific authenticated backends.

For `m365-ui-mcp`, credentials are deliberately not extracted from the browser. The persistent professional profile is the authentication boundary.

Equivalent abstraction:

```text
Session / Capability Broker
```

Responsibilities:

- verify professional profile context;
- verify authenticated state;
- verify account/tenant context;
- select application/surface;
- select mailbox/container/resource scope;
- validate capability + UI attestation;
- bind the exact authorized operation to the browser session;
- never serialize browser cookies/tokens to the control plane or client.

## 8. Least privilege — ADOPT SEMANTICALLY

Because a single Microsoft browser session can potentially access many applications, least privilege cannot rely only on OAuth scopes.

Enforce least privilege at the semantic execution layer:

```text
caller permission
+ tool policy
+ capability scope
+ application scope
+ mailbox/resource scope
+ mutation/risk class
```

A caller allowed to read Planner must not automatically gain Outlook send capability merely because the browser profile can access Outlook.

## 9. BATCH — ADOPT

One MCP request can carry multiple independent semantic operations.

Example:

```json
{
  "operations": [
    {"id": "mail", "tool": "outlook_mail_search", "args": {}},
    {"id": "calendar", "tool": "outlook_calendar_search", "args": {}},
    {"id": "tasks", "tool": "planner_task_list", "args": {}}
  ]
}
```

Each node independently retains:

- schema validation;
- capability state;
- policy;
- risk class;
- approval requirement;
- resource scope;
- quota/budget;
- lock requirement;
- retry semantics;
- audit/evidence;
- result shaping.

A batch-level approval must never silently authorize materially different child operations.

## 10. DAG — ADOPT

Use typed explicit dependencies.

Example:

```text
A: outlook_mail_search
      ↓ message_ref
B: outlook_mail_read
      ↓ sender_ref
C: outlook_people_search
```

Requirements:

- cycle detection;
- deterministic topological order;
- typed bindings only;
- bounded concurrency;
- deadline propagation;
- cancellation propagation;
- checkpoints for long execution;
- no arbitrary eval/shell/expression interpolation.

## 11. RUNBOOK — ADOPT

Stable frequently repeated procedures can be promoted from knowledge/procedure to executable runbook.

Examples:

```text
outlook-inbox-triage-v1
shared-mailbox-daily-check-v1
meeting-preparation-v1
planner-project-health-snapshot-v1
```

Promotion process:

```text
manual/reasoned procedure
-> observed stable procedure
-> typed workflow design
-> tests
-> threat review
-> policy classification
-> immutable/canonical serialization
-> versioned runbook
-> optional digest/signature
```

A runbook never becomes trusted only because an LLM has executed the same sequence several times.

## 12. Per-node policy — ADOPT

Every BATCH/DAG/RUNBOOK node executes the full governance chain:

```text
principal
-> resource scope
-> policy
-> risk/mutation class
-> budget/quota
-> approval
-> lock
-> session capability
-> execution
-> read-back
-> evidence/audit
```

There is no "trusted batch" shortcut.

## 13. Immutable plan digest — ADOPT

For multi-step mutating plans:

1. canonically serialize the planned operation graph;
2. compute `plan_digest`;
3. issue approval for that exact digest;
4. re-check digest at execution;
5. any changed node/argument invalidates the approval.

Approval metadata should bind at minimum:

```text
principal
application/resource scope
operation set
canonical arguments
plan_digest
expiry
nonce/idempotency
trust context
```

## 14. Idempotency and replay protection — ADOPT AND STRENGTHEN

UI automation increases uncertainty because the UI has no universal server-side request ID.

Mutations require:

- idempotency key where meaningful;
- persisted execution association;
- stable/opaque target identity;
- mandatory read-back;
- no blind mutation retry;
- replay-safe approval consumption.

Retries are classified:

```text
RETRY_SAFE
RETRY_CONDITIONAL
NO_RETRY
```

## 15. Sagas and compensation — ADOPT

Multi-step M365 operations use saga/checkpoint semantics.

Example:

```text
create draft
-> attach file
-> set category
-> schedule send
```

If a later step fails, compensation is capability-specific and explicit. Compensation is never assumed to exist.

Terminal/aggregate states include:

```text
SUCCESS
FAILED
PARTIAL_SUCCESS
CANCELLED
TIMED_OUT
COMPENSATED
MANUAL_INTERVENTION_REQUIRED
INDETERMINATE
```

`INDETERMINATE` is particularly important for UI operations where final remote state cannot safely be proven.

## 16. Result shaping — ADOPT

Reduce result context before it reaches the caller/LLM.

Support:

```text
select/fields
metadata_only
count
exists
first
latest
top_n
pagination/cursor
```

Example:

```text
2,000 matching emails
-> total count
-> top 10
-> selected metadata fields
```

Do not return 2,000 message bodies merely because the UI search found them.

## 17. Artifact model — ADOPT WITH PRIVACY RESTRICTIONS

Large result sets may be represented by temporary artifact/evidence references.

Minimum metadata:

```text
artifact_ref
digest
size
content_type
created_at
expires_at
classification
```

Mailbox/calendar/contact content requires stricter retention and privacy rules than generic technical artifacts. Artifact creation containing M365 content must therefore be explicit, bounded and policy-controlled.

## 18. Provenance — ADOPT

Every result should be attributable to:

```text
execution_id
tool + version
application
backend/browser worker version
capability manifest hash
UIContract-set digest
timestamp
result digest
```

No credential/session value is part of provenance.

## 19. Observability and token economics — ADOPT

Measure the reason for deterministic-first architecture.

Suggested metrics:

```text
execution_mode_total{mode}
execution_duration_seconds{mode,tool,outcome}
operations_per_request
mcp_round_trips_avoided
browser_operations_total
batch_nodes_total
runbook_runs_total
agentic_escalations_total
agentic_tokens_estimated
direct_execution_ratio
result_raw_bytes
result_returned_bytes
result_reduction_ratio
ui_drift_events_total
read_back_failures_total
indeterminate_mutations_total
approval_required_total
```

Never use mailbox address, subject, user identity, message ID, plan ID or free text as metric labels.

## 20. Agentic fallback / HYBRID — ADOPT CONSERVATIVELY

Agentic escalation is allowed only when declared conditions require reasoning, for example:

```text
UNKNOWN_INTENT
UNSUPPORTED_TOOL
DIAGNOSIS_REQUIRED
LOW_CONFIDENCE_MAPPING
UNSTRUCTURED_ANALYSIS_REQUIRED
UI_CHANGE_DIAGNOSIS_REQUIRED
```

Controls:

- maximum escalations;
- token budget;
- timeout;
- minimum necessary context;
- redaction before context transfer;
- no session secrets;
- no automatic agentic mutation authorization.

An agentic component may propose a deterministic plan; policy/approval still governs execution.

## 21. Backward compatibility — ADOPT

M365 evolution must preserve Planner consumers wherever possible.

- keep existing `planner_*` public tool names;
- version contracts explicitly;
- introduce `m365_*` platform tools separately;
- introduce `outlook_*` separately;
- provide controlled compatibility aliases for old configuration names;
- never repurpose an existing Planner tool to mean a different M365 operation.

## 22. Execution sandbox boundaries — ADOPT

No BATCH/DAG/RUNBOOK binding may become a route to generic local execution.

Forbidden:

- shell execution;
- arbitrary Python/JavaScript;
- filesystem path passthrough outside explicit artifact boundaries;
- unvalidated URLs;
- arbitrary browser scripts;
- dynamic selector injection;
- unsafe expression/eval languages.

## 23. Explicit non-adoptions

Do not copy from Hermes v2 where the model does not fit:

- no mandatory Credential Broker holding Microsoft access tokens;
- no requirement that Hermes Agent is in the execution path;
- no generic cross-provider Tool Registry backend execution inside the browser worker;
- no weakening of the stricter Planner/M365 UI evidence and read-back model;
- no assumption that API retry/idempotency semantics apply to UI interaction.

## 24. Relationship between products

`hermes-mcp-bridge` may orchestrate or call `m365-ui-mcp` in future cross-system workflows, but each product retains its own:

- repository;
- release lifecycle;
- contracts;
- policy boundary;
- state;
- threat model;
- availability.

Conceptual reuse is deliberate; runtime coupling is optional.
