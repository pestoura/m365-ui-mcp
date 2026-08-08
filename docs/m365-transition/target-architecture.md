# m365-ui-mcp — Target Architecture

Status: **PLANNED / IMPLEMENTATION TARGET**

## 1. Architectural objective

Build a secure Microsoft 365 UI execution control plane that preserves the Planner safety model, removes Planner-specific coupling from the platform core, and supports multiple semantic application adapters over one isolated authenticated browser profile.

The primary backend remains Playwright/Chromium. Microsoft Graph is optional and may only be introduced behind an existing semantic capability as an optimization or alternate implementation path.

## 2. Target topology

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Zone P — MCP clients / untrusted callers                           │
│ ChatGPT · Codex · other authorized MCP clients                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ MCP Streamable HTTP
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Zone E — Portal / edge                                               │
│ authentication · authorization · TLS · WAF · rate limiting          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Zone C — m365-ui-mcp Control Plane                                  │
│                                                                      │
│ Tool Registry                                                        │
│ Capability Registry                                                  │
│ Session/Capability Broker                                            │
│ Policy / Approvals / Quotas                                          │
│ DIRECT / BATCH / DAG / RUNBOOK execution planner                    │
│ State / Locks / Idempotency / Sagas / Checkpoints                   │
│ Evidence / Provenance / Result Shaping / Artifacts                  │
│ Observability                                                        │
│                                                                      │
│ NO browser profile · NO credentials · NO raw browser primitives     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ typed private operation protocol
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Zone W — m365-browser-worker                                         │
│                                                                      │
│ Playwright / Chromium lifecycle                                      │
│ persistent isolated professional profile                             │
│ application navigation                                               │
│ per-app UIContract fragments                                         │
│ typed UI executor                                                     │
│ structural extractor                                                  │
│ read-back verifier                                                     │
│ auth / MFA / Conditional Access detector                             │
│ bounded queue / profile lock                                         │
│                                                                      │
│ no public MCP surface · no generic browser execution endpoint        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ controlled HTTPS egress
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Zone M — Microsoft 365                                               │
│ Entra ID · Planner · Outlook · Calendar · People · To Do            │
└─────────────────────────────────────────────────────────────────────┘

                 optional sanitized side-channel
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Zone H — Hermes                                                      │
│ notifications · approvals UX · operational summaries                │
│ not browser authority · not mandatory execution hop                 │
└─────────────────────────────────────────────────────────────────────┘
```

## 3. Core rule: semantic surface only

Public MCP operations express Microsoft 365 intent, never UI mechanics.

Allowed examples:

```text
planner_task_get
outlook_mail_search
outlook_message_manage_categories
outlook_followup_manage
outlook_calendar_event_manage
m365_batch_execute
```

Forbidden examples:

```text
browser_click
browser_type
browser_navigate
browser_eval
browser_screenshot
raw_action
run_script
```

The caller never supplies selectors, page URLs, DOM fragments, keyboard scripts or JavaScript.

## 4. Application adapter model

The platform core must know nothing about the internal semantics of a Planner task or Outlook category beyond generic registry/policy metadata.

```text
src/m365_mcp/
├── core/
├── control_plane/
├── policy/
├── state/
├── execution/
├── evidence/
├── observability/
├── apps/
│   ├── planner/
│   └── outlook/
└── worker_client/

src/m365_browser_worker/
├── core/
└── apps/
    ├── planner/
    └── outlook/
```

Each app owns:

- semantic schemas;
- capability definitions;
- tool definitions;
- internal typed operations;
- UIContract fragments;
- extraction rules;
- read-back strategies;
- app-specific error mapping;
- app-specific mock surfaces/fixtures.

## 5. Canonical Tool Registry

The registry becomes authoritative. Static tool-name allowlists in policy are replaced by validated metadata.

Minimum metadata per tool:

```text
canonical_name
version
application
surface
summary
input_schema
output_schema
capability_keys
trust_level
read_only
mutation_class
risk_class
security_tier
reversible
idempotency_class
approval_requirement
policy_action
resource_scope
session_scope
timeout
retry_class
concurrency_hint
lock_hint
result_shaping
llm_required
stability
deprecated
version_added
```

Suggested security tiers:

- `T0` — non-sensitive harmless read;
- `T1` — sensitive read / mailbox-content access;
- `T2` — low-risk reversible mutation;
- `T3` — externally visible or privileged mutation;
- `T4` — destructive/admin/access-control mutation.

Registration does not imply usability. Runtime health is separate:

```text
AVAILABLE
DEGRADED
UNAVAILABLE
UNAUTHORIZED
UNATTESTED
BLOCKED
```

Every execution records a hash/snapshot identifier of the effective registry surface.

## 6. Capability Registry

Capabilities become scoped rather than globally flat.

Canonical identity should support at least:

```text
application
surface
account_scope
container_scope
capability
```

Examples:

```text
outlook.mail.primary.categories.manage
outlook.mail.shared.rules.manage
outlook.calendar.primary.events.read
planner.projects.tasks.read
```

Evidence dimensions:

- tenant/account availability;
- surface observed;
- UIContract fragment status;
- read attestation;
- mutation attestation;
- runtime health;
- policy availability;
- account/mailbox/resource scope;
- evidence timestamp/expiry.

Support states remain evidence-based:

```text
UNVERIFIED_LIVE
DISCOVERED
READ_SUPPORTED
MUTATION_SUPPORTED
DEGRADED
BLOCKED
OUT_OF_SCOPE
```

A capability may be supported for one mailbox/scope and unsupported for another.

## 7. Fragmented UIContract

A single global contract must not become a global availability switch.

Target layout:

```text
contracts/ui/
├── common/
│   ├── auth.json
│   ├── account.json
│   └── shell.json
├── planner/
│   ├── plans.json
│   ├── tasks.json
│   ├── buckets.json
│   ├── scheduling.json
│   └── ...
└── outlook/
    ├── mail/
    │   ├── message-list.json
    │   ├── message-read.json
    │   ├── compose.json
    │   ├── categories.json
    │   ├── flags.json
    │   ├── folders.json
    │   ├── rules.json
    │   ├── quick-steps.json
    │   └── security.json
    ├── calendar/
    ├── people/
    ├── todo/
    ├── shared-mailboxes/
    └── settings/
```

Each semantic operation declares exactly the fragments it requires.

If `outlook/mail/categories` drifts:

```text
outlook category mutations -> DEGRADED/BLOCKED
mail reads                 -> unaffected when their contracts are healthy
planner operations         -> unaffected
```

Attestation must be granular enough to prevent unrelated UI drift from taking down the entire M365 product.

## 8. Locator strategy

Locator priority:

1. accessibility role + accessible name;
2. stable semantic/data attributes when verified;
3. scoped text/labels;
4. documented keyboard shortcut when deterministic and safely scoped;
5. stable structural CSS selector as controlled fallback;
6. coordinate-based interaction is prohibited by default.

No locator is invented. Every live locator starts unverified and requires attestation evidence.

## 9. Internal worker operation protocol

Replace a growing set of ad-hoc REST paths with a closed typed operation envelope.

Conceptual request:

```json
{
  "protocol_version": "1",
  "operation": "outlook.mail.categories.apply",
  "application": "outlook",
  "capability_key": "outlook.mail.primary.categories.manage",
  "arguments": {
    "message_ref": "opaque:...",
    "category": "Arquitetura"
  },
  "correlation_id": "...",
  "contract_set_digest": "...",
  "authorization_digest": "..."
}
```

`operation` is a closed registry enum. It must never accept `click`, `navigate`, selector or script passthrough.

Response contains structured data, typed status, provenance and read-back evidence only.

## 10. Browser/session lifecycle

The browser worker owns one persistent professional Microsoft 365 profile unless a later ADR explicitly introduces multiple profiles.

Startup:

```text
validate config
-> load contract registry
-> initialize lock/queue subsystem
-> start Playwright
-> attach persistent Chromium profile
-> verify browser process
-> probe session state
-> expose readiness
```

Liveness is process health only.

Readiness requires at least:

```text
browser_up
persistent_profile_attached
contract_registry_loaded
worker_protocol_ready
lock_subsystem_ready
```

Authentication is reported separately and may be `AUTH_REQUIRED` while the worker itself remains ready.

## 11. Session/Capability Broker

The browser profile is the authentication mechanism. The core must not import cookies/tokens into the control plane.

The broker resolves whether an operation may use the session based on:

```text
professional profile
account context
application
resource/mailbox scope
capability availability
UI attestation
policy decision
approval state
operation authorization digest
```

The worker receives only the minimum authorization metadata necessary to prove that the control plane approved the exact typed operation.

## 12. Policy chain

Every operation, including every node inside BATCH/DAG/RUNBOOK, independently executes:

```text
principal
-> application/resource scope
-> tool manifest
-> capability evidence
-> risk/mutation class
-> budget/quota
-> policy
-> approval
-> lock
-> session capability
-> execution
-> read-back
-> evidence/audit
```

Decisions:

```text
ALLOW
DENY
REQUIRE_APPROVAL
```

Policy simulation / dry-run must return decisions without external mutation.

## 13. Mutation classes

Preserve the Planner model:

```text
READ
SAFE_WRITE
GOVERNED_WRITE
DESTRUCTIVE
```

Examples for Outlook:

- read/search/list: `READ`;
- mark read, category apply, flag: normally `SAFE_WRITE`;
- send mail, create attendee meeting, change rule, send-as shared mailbox: normally `GOVERNED_WRITE`;
- permanent delete, cancel meeting, remove delegation/access: `DESTRUCTIVE` or highest governed class.

Classification is contractual and reviewed; it is not inferred at runtime from tool names.

## 14. Read-back and mutation uncertainty

No UI mutation may report success because a click completed.

Success requires:

```text
APPLY
-> RE-READ
-> VERIFY POSTCONDITION
-> READ_BACK_OK
```

On timeout/ambiguity:

```text
DO NOT RETRY BLINDLY
-> RE-READ TARGET
-> classify LANDED / NOT_LANDED / INDETERMINATE
```

Only `NOT_LANDED` may permit a policy-approved retry.

Examples:

- category apply -> reopen/re-read category assignment;
- flag -> re-read follow-up state;
- move message -> locate message in destination and confirm source absence where feasible;
- create draft -> verify draft identity/fields;
- send -> verify Sent Items / expected message identity before any retry;
- create event -> verify calendar event identity/attendees/time;
- rule change -> re-read rule definition/order/state.

## 15. State model

Generalize state identity beyond Planner `external_id`.

Recommended logical key:

```text
account_scope
application
container_scope
resource_kind
external_ref
```

State stores control metadata, not a shadow mailbox.

Do not persist by default:

- email bodies;
- attachment contents;
- recipient lists;
- message subjects;
- raw calendar descriptions;
- contact details;
- raw DOM/screenshots;
- session identifiers/cookies/tokens.

Persist only what is necessary for:

- operation identity;
- hashes/digests;
- idempotency;
- read-back evidence;
- approvals;
- locks;
- saga/checkpoint state;
- capability/evidence metadata;
- audit provenance.

Any content cache requires explicit retention, encryption, redaction and privacy design.

## 16. Execution modes

### DIRECT

One typed deterministic operation. Preferred whenever one operation is sufficient.

### BATCH

Multiple independent typed operations in one MCP request. Each node has its own policy/capability/read-back context. Browser execution remains bounded by profile concurrency constraints; non-browser operations or future independent profiles may run in parallel where safe.

### DAG

Typed dependency graph with explicit output-to-input bindings. No arbitrary expression language/eval.

Example:

```text
search email
   ↓ message_ref
read email
   ↓ sender
find contact
```

### RUNBOOK

Versioned deterministic workflow promoted from repeated stable procedures after tests/threat review.

Example future runbook:

```text
triage-mail-v1
search -> classify -> categorize -> flag -> move -> verify
```

### AGENTIC

Used only when reasoning itself is required, not merely to perform known UI actions.

### HYBRID

Deterministic first; controlled reasoning escalation only for declared conditions and within a token/runtime budget.

## 17. Batch/DAG budgets

Support bounded budgets such as:

```text
max_nodes
max_external_calls
max_ui_operations
max_parallelism
max_runtime_ms
max_result_bytes
max_artifacts
max_retries
max_agentic_escalations
max_agentic_tokens
```

Mutations may not continue blindly merely because `continue_on_error=true` was requested.

## 18. Result shaping

A core objective is to minimize unnecessary context transfer.

Semantic reads should support bounded projections:

```text
fields/select
metadata_only
exists
count
first
latest
top_n
pagination/cursor
```

Example:

```text
search 2,000 messages
-> return count + top 10 + sender/subject/date only
```

Large results become controlled artifacts/evidence references rather than being injected wholesale into LLM context.

Every result includes provenance such as:

```text
tool/tool version
application/backend
execution_id
timestamp
contract-set digest
capability-manifest hash
result digest
raw/returned byte counts
```

Secret-aware field classes:

```text
PUBLIC
INTERNAL
SENSITIVE
SECRET
```

`SECRET` is never serialized to MCP clients.

## 19. Tool-surface compression

Internal UI capability breadth and public MCP tool count are intentionally different.

Target principle:

```text
~hundreds of typed UI operations/capabilities
               ↓
~50-80 coherent public semantic tools
               ↓
DIRECT/BATCH/DAG/RUNBOOK composition
```

Do not create one MCP tool for every button.

Grouped tools may use closed enums and strict schemas, for example:

```text
outlook_categories_manage(operation=list|create|delete|apply|remove)
outlook_followup_manage(operation=flag|unflag|complete|reminder)
outlook_folder_manage(operation=list|create|rename|move|delete|favorite)
```

This remains safe because operation enums and argument schemas are closed and mapped to specific capability/policy metadata.

## 20. Network architecture

The worker must remain unreachable from outside the control plane while retaining controlled Microsoft egress.

Required design property:

```text
Internet/client -> control plane only
control plane -> worker via private control network
worker -> Microsoft 365 via controlled egress
worker <-X- public ingress
```

The original single `internal: true` worker network must not be copied blindly if it prevents Chromium from reaching Microsoft 365.

## 21. Hermes integration

Hermes is a side-channel and optional orchestration/approval surface, not a mandatory LLM hop for deterministic M365 work.

Preferred path:

```text
ChatGPT/client
-> m365-ui-mcp
-> typed deterministic execution
-> browser worker
-> Microsoft 365
```

Hermes may participate in:

- HITL approval prompts;
- operational notifications;
- execution summaries;
- agentic escalation when reasoning is explicitly required;
- higher-level cross-system runbooks/orchestration.

It must not receive browser cookies/session material or unredacted mailbox content by default.

## 22. Compatibility

The architecture transition must preserve existing Planner semantics.

Recommended compatibility sequence:

```text
planner-mcp internals -> generalized core
planner_* tools       -> unchanged public names
PLANNER_* config      -> temporary aliases
M365_* config         -> canonical
planner-browser-worker-> m365-browser-worker after compatibility gate
```

No breaking rename is allowed merely for aesthetic consistency.
