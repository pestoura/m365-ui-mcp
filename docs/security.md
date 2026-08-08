# Security specification

Version 0.1.0. Normative. Requirement IDs `SEC-xxx` are stable and referenced from
[traceability.md](traceability.md), [threat-model.md](threat-model.md),
[governance.md](governance.md) and the pull-request template.

Related: [architecture.md](architecture.md), [privacy-boundary.md](privacy-boundary.md),
[authentication-and-mfa.md](authentication-and-mfa.md), [ui-contract.md](ui-contract.md),
[deployment.md](deployment.md), [observability.md](observability.md).

## 1. Security objectives

| ID | Objective |
| --- | --- |
| SEC-001 | The Microsoft password never exists in any artefact controlled by this system. |
| SEC-002 | Human identity assertion (sign-in, MFA) is never automated, proxied or relayed. |
| SEC-003 | The host device is never enrolled into corporate management. |
| SEC-004 | Every mutation is authorised, bounded, attributable and reversible or approved. |
| SEC-005 | Uncertainty always resolves to refusal, never to a best-effort action. |
| SEC-006 | No tenant data leaves the trust zone in which it was read, except as sanitized output. |
| SEC-007 | Every capability claim is backed by captured browser evidence. |
| SEC-008 | The supply chain of both containers is scanned, pinned and inventoried. |

## 2. Trust zones

| Zone | Members | Trusts | Never receives |
| --- | --- | --- | --- |
| Z0 Client | ChatGPT / MCP client | nothing by default | credentials, raw DOM, screenshots |
| Z1 Edge | Cloudflare MCP Server Portal | authenticated client identity | tenant data at rest |
| Z2 Control | Planner MCP control plane | Z1 identity, Z3 responses | password, cookies, session blobs |
| Z3 Worker | planner-browser-worker | Z2 requests only | outbound calls except Microsoft |
| Z4 Session | Chromium persistent profile | the human operator | any programmatic credential input |
| Z5 Tenant | Microsoft Planner Premium | Microsoft's own controls | anything this system asserts about device state |
| ZH Hermes | Hermes agent (out of band) | sanitized events only | approvals, credentials, tenant data |

Rules:

- **SEC-010** Z3 is attached to an internal-only network. It has no published port, no route
  from the public internet, and no inbound path other than from Z2.
- **SEC-011** Z2 binds to loopback. Public exposure exists only through Z1.
- **SEC-012** Z4 (the profile volume) is the only writable persistent surface in Z3 and is
  never copied, exported, committed, backed up to a shared location, or transmitted.
- **SEC-013** ZH is strictly one-way for operational events. Hermes cannot invoke a mutation,
  cannot grant an approval, and cannot influence the auth state machine.

## 3. Credential handling

- **SEC-020** The password is entered by the human, in the Chromium window, into Microsoft's
  own sign-in page. No component reads it, stores it, forwards it or types it.
- **SEC-021** Prohibited storage locations, enumerated and enforced: git-tracked files,
  environment variables, `.env` files, container images, MCP tool inputs/outputs, Hermes
  messages, log records, metric labels, state files, evidence artefacts, error strings,
  stack traces, crash dumps, HAR files, Playwright traces.
- **SEC-022** Session material (cookies, `ESTSAUTH*`, refresh tokens, storage state) lives
  only inside the profile volume, owned by the worker UID, mode `0700`.
- **SEC-023** No component may serialise the profile. `storage_state()`-style exports are
  prohibited in production code paths; `scripts/check_no_secrets.sh` and `.gitignore` enforce
  the repository half of this rule.
- **SEC-024** `planner_auth_session_info` returns only: state, session age, estimated expiry,
  and a salted hash of the profile identity. Never the identity itself in raw form.
- **SEC-025** The only secrets this system legitimately holds are its own: the Cloudflare
  service credential and the internal control-plane↔worker shared secret. Both are injected
  at runtime, never baked into an image, and are rotatable without code change.

## 4. Authentication and MFA boundary

Full specification in [authentication-and-mfa.md](authentication-and-mfa.md). Security-side
invariants:

- **SEC-030** `planner_auth_start` opens the sign-in surface and returns. It submits nothing.
- **SEC-031** When Microsoft number matching is detected, the system emits exactly one
  sanitized event with the fields `operation_id`, `service`, `description`, `mfa_number`,
  `expires_at`. Nothing else. No screenshot, no URL, no account name, no correlation to
  tenant data.
- **SEC-032** The MFA number is displayed for the human to type into Microsoft Authenticator.
  Emitting it is a convenience, never an authorisation. Approving in Telegram, Hermes, or any
  channel other than Microsoft Authenticator is impossible by construction and prohibited by
  policy.
- **SEC-033** `WAITING_FOR_MFA` has a hard timeout. On expiry the state moves to
  `AUTH_FAILED` and the pending operation is abandoned, not retried.
- **SEC-034** Repeated `AUTH_FAILED` transitions trip a circuit breaker that blocks further
  authentication attempts until an operator resets it. This prevents the system from
  contributing to an account lockout or an MFA-fatigue pattern.

## 5. Device and Conditional Access boundary

See [privacy-boundary.md](privacy-boundary.md) and
[ADR-008](adr/ADR-008-personal-device-privacy-boundary.md).

- **SEC-040** The host is never enrolled in Intune, Company Portal, Identity Broker, Entra
  device registration, MDM, corporate EDR, and is never issued a device certificate. No code
  path, script, container or documented procedure may perform or suggest enrolment.
- **SEC-041** If a Conditional Access policy demands a compliant, hybrid-joined or managed
  device, the system raises `BLOCKER_CONDITIONAL_ACCESS`, records the blocker, and fails
  closed. The affected capability moves to `BLOCKED_CONDITIONAL_ACCESS`.
- **SEC-042** Bypassing, spoofing, or misrepresenting device compliance state — including
  user-agent forgery aimed at policy evaluation, injected device claims, or reuse of tokens
  obtained on a managed device — is prohibited. A contribution attempting it is rejected.
- **SEC-043** A blocker is a terminal condition for that capability, not a retry trigger.
  Resolution is an organisational decision, taken outside this system.

## 6. Policy engine and approvals

- **SEC-050** Every tool invocation is evaluated by the policy engine before execution. The
  decision is one of `ALLOW`, `DENY`, `REQUIRE_APPROVAL`. Absence of a matching rule is
  `DENY` (default-deny).
- **SEC-051** Decision inputs: tool name, mutation class, trust level, attestation status of
  the underlying capability, auth state, target scope, and the current blocker set. A tool
  whose capability is not at least `READ_ATTESTED` cannot be `ALLOW`ed for reads; mutations
  require `MUTATION_ATTESTED`.
- **SEC-052** `GOVERNED_WRITE` and `DESTRUCTIVE` always resolve to at least
  `REQUIRE_APPROVAL`. Policy may raise a requirement, never lower it.
- **SEC-053** An approval record is persistent and non-replayable. It carries: `approval_id`,
  a random `nonce`, the bound `operation_id`, a hash of the exact planned change set,
  `approver`, `issued_at`, `expires_at`, and `consumed_at`.
- **SEC-054** Consumption is single-use and atomic: an approval already `consumed_at` is
  rejected; an approval whose plan hash no longer matches the recomputed plan is rejected
  (no "approve then swap"); an expired approval is rejected.
- **SEC-055** Approvals never grant a class of future actions. There is no standing approval,
  no wildcard scope, and no approval that survives a restart of the target plan's state.
- **SEC-056** All decisions and consumptions are written to the audit trail with the
  reasoning inputs, so a refusal can always be explained after the fact.

## 7. Fail-closed invariants

| ID | Condition | Behaviour |
| --- | --- | --- |
| SEC-060 | UI drift detected against the attested contract | refuse, mark `UI_DRIFT`, no fallback selector guessing |
| SEC-061 | Selector missing an attestation record | refuse before touching the page |
| SEC-062 | Ambiguous identity (multiple matching targets) | refuse; never pick the first match |
| SEC-063 | Auth state not `AUTHENTICATED` for a tenant-touching tool | refuse |
| SEC-064 | Policy undecidable or rules failed to load | refuse everything except `planner_health` |
| SEC-065 | Read-back after a mutation does not match the desired state | do not retry blindly; open a discrepancy and stop |
| SEC-066 | Worker unreachable or unhealthy | refuse; never degrade to a direct browser call from Z2 |
| SEC-067 | Circuit breaker open | refuse for the cooldown period |

Retries are permitted only for transient transport errors, only for `READ` and
`NATURALLY_IDEMPOTENT`/`KEYED_IDEMPOTENT` operations, and only after a read-back
confirms the prior attempt had no effect. See [idempotency.md](idempotency.md).

## 8. Redaction

- **SEC-070** Logs are structured JSON and pass through a redaction filter before emission.
- **SEC-071** Deny-list by key: `password`, `passwd`, `secret`, `token`, `authorization`,
  `cookie`, `set-cookie`, `session`, `state`, `code`, `id_token`, `refresh_token`,
  `client_secret`, `mfa_number` (outside the single sanitized event).
- **SEC-072** Allow-list by value shape for identifiers: plan/task identifiers are logged as
  stable opaque IDs; human-readable titles, names, e-mail addresses and tenant names are
  hashed or omitted.
- **SEC-073** Metric labels are low cardinality only: tool name, mutation class, decision,
  outcome, auth state. Never an identifier, title, user or tenant.
- **SEC-074** Evidence artefacts (screenshots, DOM captures) are redacted at capture time and
  stored outside git. Raw captures never enter the repository or a PR.
- **SEC-075** Error messages returned to the MCP client are sanitized: a stable error code and
  a human-readable reason, never a raw exception, DOM fragment or URL with tokens.

## 9. Container and network hardening

Enforced in [deployment.md](deployment.md) and `compose.yml`:

- **SEC-080** Both containers run as a non-root, system UID (`10001`, `10002`).
- **SEC-081** Root filesystem is read-only; scratch space is `tmpfs` with a size cap.
- **SEC-082** `cap_drop: ALL` and `security_opt: no-new-privileges:true` on every service.
- **SEC-083** No Docker socket is mounted anywhere, ever. No host home directory is mounted.
- **SEC-084** The worker publishes no port and sits on an `internal: true` network.
- **SEC-085** The control plane publishes only to `127.0.0.1`.
- **SEC-086** The only writable persistent volume is the profile volume in the worker.
- **SEC-087** Egress from the worker is limited to Microsoft endpoints required by the UI.

## 10. Supply chain

- **SEC-090** Base images are digest-pinned; `scripts/check_image_pinning.py` fails CI on any
  `FROM` without `@sha256:`.
- **SEC-091** Trivy scans both images; `CRITICAL` and `HIGH` fail the build.
- **SEC-092** `pip-audit --strict` gates Python dependencies.
- **SEC-093** A CycloneDX SBOM is generated for the Python environment and for each image,
  validated by `scripts/validate_sbom.py`, and published as a build artefact.
- **SEC-094** Secret scanning runs on full history (gitleaks) plus the product-specific
  pattern check in `scripts/check_no_secrets.sh`.
- **SEC-095** Dependabot proposes updates for pip, GitHub Actions and Docker weekly.
- **SEC-096** CI never authenticates to a live tenant; `scripts/assert_no_live_tenant.py`
  asserts the absence of tenant configuration before the acceptance job runs.

## 11. Verification matrix

| Requirement | Verified by |
| --- | --- |
| SEC-001, SEC-021, SEC-023 | `scripts/check_no_secrets.sh`, gitleaks, `.gitignore`, review |
| SEC-002, SEC-030..SEC-034 | auth state machine tests, catalogue tests, review |
| SEC-003, SEC-040..SEC-043 | policy tests, review checklist, absence of enrolment code paths |
| SEC-005, SEC-060..SEC-067 | fail-closed unit tests, mock-UI drift tests |
| SEC-007 | `scripts/validate_contracts.py`, UIContract attestation tests |
| SEC-050..SEC-056 | policy engine and approval tests (replay, expiry, plan-hash mismatch) |
| SEC-070..SEC-075 | redaction unit tests, metric cardinality test |
| SEC-080..SEC-087 | container build gate, compose review |
| SEC-090..SEC-096 | CI jobs `images`, `dependencies`, `secrets`, `acceptance` |
