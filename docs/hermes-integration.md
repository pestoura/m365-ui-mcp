# Hermes Integration

Hermes is a bounded auxiliary integration. It is **not** part of the normal Planner execution path.

```text
Planner MCP
   ├── Browser Worker → Planner Premium
   └── Hermes → sanitized notifications / future HITL support
```

Removing or disabling Hermes must not stop ordinary read operations. It may block only an operation
that explicitly requires a Hermes-backed human decision in a later governed-write flow.

Companions: [`authentication-and-mfa.md`](authentication-and-mfa.md),
[`privacy-boundary.md`](privacy-boundary.md), [`governance.md`](governance.md),
[`security.md`](security.md), [`observability.md`](observability.md) and ADR-005.

## 1. Allowed responsibilities

Hermes may be used for:

- sanitized MFA number-matching notification;
- session-expiry/auth-required notification;
- UI drift/blocker/operational notification;
- future human-in-loop (HITL) request/response for a governed operation, if the approval protocol is
  explicitly implemented and policy permits it;
- sanitized status notification containing bounded operational metadata.

Hermes does not:

- authenticate to Microsoft Planner;
- host or copy the professional browser profile;
- receive Planner passwords/tokens/cookies;
- approve Microsoft MFA;
- invoke generic browser actions;
- bypass Planner MCP policy;
- become the source of truth for operation state/audit.

## 2. MFA notification

When Microsoft Authenticator number matching is detected, the emitted event contains only:

```text
mfa_number
operation_id
service
description
expiry
```

The schema is closed. The description is a static/sanitized template and must not include tenant,
UPN/email, plan/task or browser-session data.

The message must state that approval occurs **only in Microsoft Authenticator**. Hermes, Telegram,
ChatGPT and Planner MCP provide no “approve MFA” control.

The source of truth for MFA success is the browser observing the session becoming authenticated.

## 3. Operational notifications

Allowed notification classes include bounded events such as:

- authentication/session action required;
- `BLOCKER_CONDITIONAL_ACCESS`;
- `UI_DRIFT`;
- worker unavailable/crash loop;
- policy/configuration invalid;
- approval waiting/expired in later releases;
- audit/redaction/security alert requiring operator action.

Notification payloads use enums/counts/static descriptions where possible. Do not send raw task
content, Planner HTML, screenshots or credential/session material.

## 4. Future HITL boundary

HITL is distinct from Microsoft MFA.

A future governed operation may receive `REQUIRE_APPROVAL` from Planner MCP policy. If Hermes is used
as the operator decision surface, the approval must still be a Planner MCP approval object with these
properties:

- bound to the exact operation/diff fingerprint;
- specific to the requester/tool/scope as policy defines;
- expiring;
- single-use;
- non-replayable;
- atomically consumed;
- invalidated if the request/baseline/diff changes;
- incapable of elevating a caller beyond normal policy authorization.

Hermes transports the human decision; it does not define what is authorized.

## 5. HITL payload minimization

A future HITL request should contain only the minimum information required to make the decision, for
example:

- approval/request id;
- operation id;
- semantic tool/operation type;
- mutation class;
- sanitized summary/counts;
- changed field names from a bounded enum where sufficient;
- expiry;
- digest/fingerprint reference.

Full project data/diff details remain on the governed Planner MCP/operator interface when they cannot
be safely minimized for notification.

## 6. HITL fail-closed behavior

When an operation explicitly requires approval:

- no approval by expiry ⇒ do not execute;
- reject ⇒ do not execute;
- unknown/expired/already-consumed approval ⇒ do not execute;
- replayed response ⇒ reject and audit;
- request/diff changed ⇒ invalidate and require new approval;
- Hermes unavailable ⇒ required-HITL operation remains blocked.

Ordinary read-only tools are not blocked because Hermes is unavailable.

## 7. Transport security

The concrete Hermes transport may use existing authenticated Hermes capabilities, webhook/service
interfaces or another approved internal path. Whichever implementation is selected must provide:

- authenticated endpoint/service;
- TLS or an equivalently protected local/private channel;
- file-backed/platform-managed secrets rather than source-code secrets;
- bounded retries and rate limiting;
- HMAC/signature + timestamp/nonce replay protection where callback/webhook trust requires it;
- sanitized logging;
- no public callback unnecessarily exposed to the internet.

Transport details are implementation evidence and must not be invented in the specification before
the chosen Hermes integration is validated.

## 8. Privacy/security deny-list

Never send to Hermes:

- Microsoft password;
- access/refresh token;
- cookie/auth header;
- browser profile/session export;
- raw plan/task IDs unless a documented bounded opaque reference is strictly required;
- task titles/descriptions/comments/attachments/assignee data by default;
- screenshots/DOM excerpts;
- raw UI selectors;
- HMAC/auth secret values.

The MFA number is the explicit exception allowed only in the dedicated five-field MFA event.

## 9. Observability

Planner MCP may record bounded integration metrics/events such as:

- notification sent/failed by notification class;
- MFA notification required/expired;
- HITL request approved/rejected/expired/replay-rejected;
- Hermes integration available/degraded;
- bounded delivery latency.

Do not put operation IDs, user identity, task/plan identifiers or message text into metric labels.

Hermes delivery failure is a notification degradation; it does not fabricate a Planner operation
failure unless the operation is explicitly waiting for required HITL approval.

## 10. 0.1.0 behavior

Release 0.1.0 is read-only. Hermes use is therefore primarily notification-oriented:

- auth/MFA/session notification may be exercised;
- MFA approval remains Microsoft Authenticator-only;
- no public Planner mutation tool depends on Hermes because no mutation tool is exposed;
- future HITL approval infrastructure may be modelled/tested internally but does not create a write
  capability.

## 11. Verification

Required tests/evidence include:

- exact MFA event schema/field set;
- no forbidden field can be serialized into the MFA event;
- message contains no link/reply action that claims to approve MFA;
- Hermes disabled leaves ordinary read-only operations functional;
- notification delivery failure is bounded/sanitized;
- future HITL timeout/reject/replay cases fail closed;
- future HITL cannot override a policy `DENY`;
- no Planner credentials/session/business content appear in Hermes payloads during acceptance.

## 12. Backlog/traceability ownership

There is no Hermes EPIC in the canonical backlog. Hermes is cross-cutting:

| Concern | Canonical P-key(s) |
| --- | --- |
| MFA number-matching sanitized event | P-020 |
| auth/session blocker behavior | P-018..P-023 |
| policy engine | P-061 |
| persistent single-use approval model | P-062 |
| telemetry/privacy hygiene | P-063 |
| audit completeness | P-067 |
| isolated acceptance | P-069 |

Do not repurpose P-037..P-045 for Hermes work: those P-keys canonically belong to scheduling/project
management capabilities.
