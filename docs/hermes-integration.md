# Hermes Integration

Scope: the strictly bounded relationship between `pestoura/planner-mcp` and Hermes Agent. Companions: [privacy-boundary.md](privacy-boundary.md), [authentication-and-mfa.md](authentication-and-mfa.md), [security.md](security.md), [governance.md](governance.md), [observability.md](observability.md).

## 0. The boundary in one paragraph

Hermes is **not** part of the Planner control path. Hermes performs exactly two functions: (1) delivering notifications to the human operator, and (2) hosting human-in-the-loop (HITL) prompts that gate an operation the control plane has already decided requires human judgement. Hermes never authenticates to Planner, never receives Planner content, never receives credentials, never approves MFA, and cannot cause a Planner mutation by itself. Removing Hermes entirely degrades operator awareness and blocks HITL-gated operations; it changes nothing else.

## 1. Allowed interactions

| Direction | Interaction | Payload | Effect on Planner |
|-----------|-------------|---------|-------------------|
| planner-mcp → Hermes | Sanitized MFA challenge event | fixed 5-field schema (§3) | none |
| planner-mcp → Hermes | Operational notification (session expiry, selector drift, alert echo) | metric/alert name + severity + operation_id | none |
| planner-mcp → Hermes | HITL request | operation_id, tool name, sanitized description, options | blocks until answered |
| Hermes → planner-mcp | HITL response | operation_id, decision `approve\|reject`, optional note | unblocks a pending operation |
| Hermes → planner-mcp | Status query | operation_id | read-only |

Everything else is prohibited.

## 2. Prohibited interactions

| Prohibited | Reason |
|------------|--------|
| Sending Planner task titles, descriptions, comments, attachments or assignee names | Business content and PII stay inside the boundary ([privacy-boundary.md](privacy-boundary.md)). |
| Sending plan/bucket/task identifiers in raw form | Only salted hashes may leave, and only when strictly needed. |
| Sending screenshots or DOM excerpts | Visual content is evidence-only and stays on the host. |
| Sending credentials, cookies, tokens, or profile data | Session material never leaves the worker volume. |
| Approving MFA from Hermes or Telegram | Approval is only valid in Microsoft Authenticator. |
| Hermes invoking Planner MCP tools | Hermes is not an MCP client of this server. |
| Hermes writing to the audit store | Audit is append-only, control-plane owned. |
| Using Hermes as an alerting *source of truth* | Prometheus/Alertmanager remain authoritative; Hermes echoes. |

## 3. Sanitized MFA event

The single most sensitive integration. When the worker encounters an MFA challenge, the control plane emits an event containing **exactly** these fields and nothing else:

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `operation_id` | ULID | `01J9F...` | Correlation only. |
| `service` | string, closed set | `microsoft-planner` | Which login is being challenged. |
| `description` | string, sanitized | `Sign-in verification required for the Planner browser session` | Static template; no user data, no tenant name, no account identifier. |
| `mfa_number` | string, 2 digits | `47` | The number to match in Microsoft Authenticator. |
| `expires_at` | RFC 3339 | `2026-08-08T10:04:31Z` | Challenge deadline. |

Schema is `additionalProperties: false`. A schema test (see [testing.md](testing.md)) asserts the exact field set; adding a field is a breaking change requiring a privacy review recorded in [governance.md](governance.md).

Message rendering rules: the notification must state that approval happens **only in Microsoft Authenticator**, must not include a link, button, or reply-to-approve affordance, and must not be actionable. The MFA number is displayed solely so the human can match it in Authenticator.

| Outcome | Source of truth | Recorded as |
|---------|-----------------|-------------|
| approved | Worker observes the session becoming authenticated | `worker_mfa_events_total{outcome="approved"}` |
| expired | Deadline passed without authentication | `outcome="expired"` |
| denied | Login page reports rejection | `outcome="denied"` |

Hermes is never consulted for the MFA outcome; it is a display surface.

## 4. HITL protocol

HITL applies to operations the policy layer marks as requiring human judgement — for example, bulk mutations above a threshold, deletions, or any operation attempted while a selector fallback was used.

| Step | Actor | Detail |
|------|-------|--------|
| 1 | control plane | Computes the plan and a **dry-run diff**; marks the operation `awaiting_approval`. |
| 2 | control plane | Sends the HITL request: `operation_id`, tool, sanitized description, change *counts* and field *names* (never values), expiry. |
| 3 | human | Reviews in Hermes; may consult the host for full detail. |
| 4 | Hermes | Returns `approve` or `reject` with the `operation_id`. |
| 5 | control plane | Verifies the response signature/token, checks the operation is still pending and unexpired, then proceeds or aborts. |
| 6 | control plane | Records the decision, the responder identity, and the timestamp in the audit row. |

Safety properties: requests expire (default 15 minutes) and default to **reject** on timeout; a response for an unknown, already-decided, or expired `operation_id` is discarded and audited; approval authorizes exactly the diff that was presented — if the observed pre-state changed, the operation is re-planned and re-approved; and HITL can never *escalate* permissions, only permit an operation the role model already allows.

## 5. Transport and authentication

| Aspect | Setting |
|--------|---------|
| Direction | planner-mcp → Hermes over HTTPS to a configured webhook; Hermes → planner-mcp over a loopback-bound or internal-network callback endpoint |
| Auth outbound | Bearer token from a compose secret |
| Auth inbound | Shared-secret HMAC over the body + timestamp; replay window 5 minutes; nonce cache |
| Failure policy | **Fail-closed for HITL** (no answer ⇒ no mutation), **fail-open for notifications** (delivery failure never blocks an operation, only logs and increments a counter) |
| Retries | Bounded, jittered; notifications are best-effort, HITL requests are re-sent until expiry |
| Rate limiting | Per-minute cap on outbound notifications; overflow is coalesced into a summary event |

## 6. Observability of the integration

| Metric | Labels | Meaning |
|--------|--------|---------|
| `plannermcp_hermes_notifications_total` | `kind`, `outcome` | `kind` ∈ `mfa`, `alert`, `session`, `summary`. |
| `plannermcp_hitl_requests_total` | `outcome` | `outcome` ∈ `approved`, `rejected`, `expired`, `discarded`. |
| `plannermcp_hitl_wait_seconds` | — | Histogram of human response latency. |

Alerts: sustained HITL expiry, notification delivery failure over 15 minutes, and any discarded response (possible replay attempt — treated as a security signal).

## 7. Threats and mitigations

| Threat | Mitigation |
|--------|------------|
| Attacker with Hermes access approves a mutation | HITL cannot exceed the role model; approval is bound to a specific, unexpired diff; every decision is audited with responder identity. |
| Phishing via a forged MFA notification | Notifications carry no links and no approval affordance; the only valid approval surface is Microsoft Authenticator. |
| Data exfiltration through notification text | Fixed schema, `additionalProperties: false`, static description templates, redaction detector applied to outbound payloads. |
| Replay of a captured HITL response | HMAC + timestamp window + nonce cache + single-use operation state. |
| Hermes outage stalls operations | HITL-gated operations fail closed and are retryable; all non-gated operations are unaffected. |
| Correlation of hashed ids across systems | Per-deployment salt, never shared with Hermes. |

## 8. Configuration

| Variable | Default | Effect |
|----------|---------|--------|
| `HERMES_ENABLED` | `false` | Master switch; when off, HITL-gated operations are denied rather than silently executed. |
| `HERMES_WEBHOOK_URL` | — | Outbound endpoint. |
| `HERMES_TOKEN_FILE` | — | Compose secret path. |
| `HITL_CALLBACK_BIND` | `127.0.0.1` | Inbound callback binding; never public. |
| `HITL_TIMEOUT_SECONDS` | `900` | Default-reject deadline. |
| `MFA_NOTIFY_ENABLED` | `true` when Hermes enabled | Sanitized MFA events. |
| `NOTIFY_RATE_LIMIT_PER_MIN` | `10` | Coalescing threshold. |

## 9. Verification checklist

| Check | Level |
|-------|-------|
| MFA event schema exactly matches the 5-field contract | schema test |
| Outbound payload passes the redaction detector | unit + isolated acceptance |
| HITL timeout defaults to reject | contract test |
| Stale/replayed HITL response is discarded and audited | contract test |
| Hermes disabled ⇒ HITL-gated tools denied, others unaffected | contract test |
| Notification failure does not fail an operation | isolated acceptance |
| No Planner content appears in any Hermes payload during a full scenario run | isolated acceptance |

## 10. Backlog mapping

| Item | Backlog keys |
|------|--------------|
| Sanitized MFA event + schema | P-037, P-038 |
| Notification transport + rate limiting | P-039, P-040 |
| HITL request/response protocol | P-041, P-042, P-043 |
| HMAC/replay protection | P-044 |
| Integration observability + alerts | P-045 |

## 11. Message templates

All outbound text is rendered from a fixed template set; free-form interpolation of Planner data is impossible by construction because the templates accept only the enumerated placeholders shown below.

| Template | Placeholders | Example rendering |
|----------|--------------|-------------------|
| `mfa.challenge` | `mfa_number`, `expires_at` | "Sign-in verification required for the Planner browser session. Number: 47. Expires 10:04 UTC. Approve only in Microsoft Authenticator." |
| `session.expired` | `operation_id` | "The Planner browser session expired. Operations are paused until re-authentication." |
| `alert.echo` | `alert_name`, `severity` | "Alert SelectorMissSpike (high) is firing." |
| `hitl.request` | `tool`, `change_count`, `field_names`, `expires_at` | "Approval requested for task_update: 3 fields (due_date, priority, bucket) across 5 tasks." |
| `summary.coalesced` | `counts` | "12 notifications suppressed in the last minute." |

Templates are unit-tested to assert that no placeholder can carry business content: `field_names` is validated against the known field enumeration, and `change_count` is an integer.

## 12. Degradation matrix

| Hermes state | Notifications | HITL-gated tools | All other tools |
|--------------|--------------|------------------|-----------------|
| Enabled, healthy | delivered | operable | operable |
| Enabled, delivery failing | dropped, counted, alerted | fail closed after expiry | operable |
| Enabled, callback unreachable | delivered | fail closed | operable |
| Disabled | none | denied with `reason=hitl_unavailable` | operable |

Under no state does Hermes availability change the result of a non-gated Planner operation. This is asserted in the isolated acceptance suite by running the full scenario set with Hermes disabled.

## 13. Review requirements

Any change to the outbound payload shape, the template set, or the HITL protocol requires: a schema diff in the PR, a privacy review recorded in [governance.md](governance.md), an update to the verification checklist in §9, and a re-run of the full-scenario "no Planner content leaves the boundary" assertion in isolated acceptance.
