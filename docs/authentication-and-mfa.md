# Planner MCP — Authentication and MFA

Status: specification (implementation-grade). Nothing here is a claim of existing implementation;
every requirement is `PLANNED` unless a release note says otherwise (`GOV-090`).
Canonical upstream: [docs/vision.md](./vision.md)
Related: [docs/architecture.md](./architecture.md) · [docs/security.md](./security.md) · [docs/privacy-boundary.md](./privacy-boundary.md) · [docs/governance.md](./governance.md) · [docs/browser-worker.md](./browser-worker.md) · [docs/tool-catalog.md](./tool-catalog.md)

Requirement IDs (`AUTH-xxx`) are stable, never reused, never renumbered.

---

## 1. Principles

**AUTH-001 — Interactive Microsoft sign-in only.** The only supported authentication path is a
human signing in interactively, in the worker's Chromium window, against Microsoft's own login
surface. There is no programmatic credential flow, no ROPC, no device-code fallback, no cookie
import, no session transplant (`SEC-003`, `PRIV-071`).

**AUTH-002 — The password does not exist inside the system.** The Microsoft password is never
typed by automation, never accepted as a tool argument, never present in an environment variable,
a config file, the repository, the MCP state store, a log line, a metric label, an audit event, a
Hermes message, or an error string (`SEC-002`, `PRIV-070`).

**AUTH-003 — MFA is approved only in Microsoft Authenticator.** The approval act happens on the
operator's phone, in Microsoft Authenticator. Telegram, Hermes, the MCP surface and the control
plane are notification/observation channels only; none of them can approve, relay, forward or
satisfy an MFA challenge.

**AUTH-004 — No MFA material is stored.** One-time codes, push payloads, number-matching answers
entered by the human, and any challenge secret are never persisted or logged. The *displayed
number* of a number-matching challenge is not a secret and is the single exception permitted for
notification purposes (`AUTH-040`).

**AUTH-005 — Fail closed.** Any unknown, ambiguous, expired or unverifiable authentication state
is treated as unauthenticated. Absence of evidence is never treated as `AUTHENTICATED`
(`SEC-001`, `ARCH-130`).

**AUTH-006 — Authentication is a worker-side fact, a control-plane observation.** The session
lives exclusively in the worker's persistent profile. The control plane holds only the sanitized
state machine value plus non-identifying metadata.

---

## 2. Persistent professional profile lifecycle

**AUTH-010 — One profile, one professional account, one tenant.** The Chromium user-data
directory is dedicated, created empty by the worker, and bound to exactly one professional
account (`PRIV-030`, `PRIV-036`). Personal profiles are never opened, imported or copied
(`PRIV-031`).

**AUTH-011 — Location and ownership.** The profile lives in the named `browser-profile` volume,
mounted only in the worker, owned by the worker's non-root user, mode `0700`. No host home
directory, no bind mount, no Docker socket (`PRIV-050`, `ARCH-122`).

**AUTH-012 — Lifecycle states.** `ABSENT` → `CREATED` (empty, unauthenticated) → `AUTHENTICATED`
(carries a live Microsoft session) → `STALE` (session expired, profile intact) → `DESTROYED`.
Transitions are explicit operator actions or observed expiry; never silent recreation.

**AUTH-013 — Re-authentication reuses the profile.** Expiry does not destroy the profile. The
human re-authenticates in place, preserving device-recognition signals that reduce MFA prompts.

**AUTH-014 — Destruction is explicit and complete.** Destroying the profile removes the whole
volume; there is no partial cleanup and no export of profile contents anywhere, for any reason,
including debugging (`PRIV-034`).

**AUTH-015 — No extensions, no saved passwords, no sync.** The profile has no extensions, no
password manager entries, no Chrome profile sync, and no personal browsing (`PRIV-032`,
`PRIV-033`).

**AUTH-016 — Profile integrity is not authentication.** A present profile proves nothing about
session validity. Validity is established only by a live, sanitized read-back probe
(`AUTH-050`).

---

## 3. Authentication state machine

**AUTH-020** The authentication state is exactly one of these eight values. No other value is
emitted, stored or accepted:

| State | Meaning |
| --- | --- |
| `UNKNOWN` | No probe has been performed since worker/profile start. Treated as unauthenticated. |
| `READY` | Worker and profile are usable; no authentication attempt in flight; no session asserted. |
| `AUTH_REQUIRED` | A live probe determined no valid Microsoft session exists. Human sign-in needed. |
| `MFA_REQUIRED` | Microsoft has presented an MFA challenge; challenge metadata is being sanitized. |
| `WAITING_FOR_MFA` | Challenge metadata published; the system is waiting for approval in Microsoft Authenticator. |
| `AUTHENTICATED` | A live probe confirmed a valid session **and** the expected account/tenant context. |
| `SESSION_EXPIRED` | A previously authenticated session no longer validates. |
| `AUTH_FAILED` | The attempt terminated without a session (denial, timeout, cancellation, blocker). |

**AUTH-021 — Allowed transitions.** Every other transition is a bug and fails closed:

```
UNKNOWN          -> READY | AUTH_REQUIRED | AUTHENTICATED | AUTH_FAILED
READY            -> AUTH_REQUIRED | AUTHENTICATED | AUTH_FAILED
AUTH_REQUIRED    -> MFA_REQUIRED | AUTHENTICATED | AUTH_FAILED
MFA_REQUIRED     -> WAITING_FOR_MFA | AUTH_FAILED
WAITING_FOR_MFA  -> AUTHENTICATED | AUTH_FAILED
AUTHENTICATED    -> SESSION_EXPIRED | AUTH_REQUIRED | UNKNOWN
SESSION_EXPIRED  -> AUTH_REQUIRED | AUTH_FAILED
AUTH_FAILED      -> READY | AUTH_REQUIRED
```

**AUTH-022 — Terminal-for-the-attempt states.** `AUTH_FAILED` ends the current attempt. Recovery
requires a new, explicitly started attempt (`planner_auth_start`); there is no automatic retry
loop against Microsoft.

**AUTH-023 — `AUTHENTICATED` requires two proofs.** A valid session probe **and** a matching
account/tenant context (`AUTH-030`). One without the other yields `AUTH_FAILED`.

**AUTH-024 — Conditional Access blocker is not a state.** A managed/compliant-device requirement
produces `AUTH_FAILED` with error class `BLOCKER_CONDITIONAL_ACCESS`, which is terminal for the
whole capability, not merely for the attempt (`AUTH-070`).

**AUTH-025 — State is not cached across worker restarts.** After a worker restart the state is
`UNKNOWN` until a probe runs, even though the profile persists.

---

## 4. Account, tenant and session context verification

**AUTH-030 — Context verification is mandatory before any read or mutation.** Before executing a
Planner operation the worker verifies the signed-in principal and tenant match the configured
expected context. Mismatch fails closed with `ACCOUNT_CONTEXT_MISMATCH`; the operation is not
attempted and no automatic account switch occurs.

**AUTH-031 — Configured expectation.** The expected context is configuration (an account
identifier hint and a tenant identifier hint), never a caller-supplied argument. Callers cannot
select or influence the account.

**AUTH-032 — Sanitized exposure only.** `planner_account_context` returns only: a stable opaque
account handle, tenant kind (`professional`), a boolean context match, the licence-signal
observation state, and the probe timestamp. Never an e-mail address, UPN, object ID, tenant GUID
or display name (`PRIV-063`).

**AUTH-033 — Multiple accounts in the profile is a defect.** If more than one signed-in principal
is observed, the state is `AUTH_FAILED` with `ACCOUNT_CONTEXT_AMBIGUOUS`. The system never picks
one (`PRIV-036`).

**AUTH-034 — Session validity probe.** Validity is established by a minimal authenticated
navigation whose expected post-condition is described by a UIContract read-back probe
([docs/ui-contract.md](./ui-contract.md) `UI-060`). Absence of a login redirect is not sufficient
evidence.

**AUTH-035 — Probe cost and frequency are bounded.** Probes are rate-limited and reuse a cached
result within a short, configured freshness window. An expired cache yields `UNKNOWN`, never an
optimistic `AUTHENTICATED`.

---

## 5. MFA detection, number matching and notification

**AUTH-040 — Sanitized authentication event.** The only fields ever published outside the worker
for an authentication/MFA event are exactly:

| Field | Type | Notes |
| --- | --- | --- |
| `operation_id` | opaque string | Correlates the attempt; not derived from identity |
| `service` | enum | Constant `microsoft_login` for this flow |
| `description` | sanitized string | From a fixed vocabulary; never free-form page text |
| `mfa_number` | integer or null | Number-matching digits shown by Microsoft; not a secret |
| `expires_at` | timestamp | Challenge/attempt expiry |

No other field is added. No screenshot, no DOM, no URL, no account identifier, no error text from
the page (`PRIV-064`, `ARCH-112`).

**AUTH-041 — Fixed description vocabulary.** `sign_in_required`, `password_entry_pending`,
`mfa_challenge_presented`, `mfa_number_matching`, `mfa_approval_pending`, `mfa_timeout`,
`mfa_denied`, `conditional_access_blocked`, `sign_in_completed`, `sign_in_failed`. Anything not in
the vocabulary is reported as `sign_in_failed`.

**AUTH-042 — Number-matching detection.** When Microsoft presents a number-matching challenge, the
worker extracts the displayed number through a UIContract-declared read probe, validates it is a
short integer, and publishes it in `mfa_number`. If the number cannot be extracted with confidence
it is published as `null` with description `mfa_approval_pending`; a number is never guessed.

**AUTH-103 — MFA number extraction is a bounded live observation, not a `common.auth` selector.** The
displayed MFA number is read exclusively through the bounded live observation primitive described
under `AUTH-042`/`AUTH-100`. It is intentionally NOT a `common.auth` selector placeholder
(`auth.mfa_number_display` was removed during the contract redesign): the value is volatile, live-only
and must never be frozen into the source-controlled selector contract. No sign-in progression selector
carries MFA state.

**AUTH-043 — Notification is one-way.** The sanitized event may be delivered to the operator via
Hermes/Telegram so the human knows which number to select. That channel carries no approval
capability, accepts no reply that affects the flow, and is never on the critical path
(`ARCH-004`).

**AUTH-044 — Approval happens only in Microsoft Authenticator.** The system never types a code,
never auto-selects a number, never interacts with an approval prompt, and never accepts an MFA
code as a tool argument (`AUTH-003`, `AUTH-004`).

**AUTH-045 — No MFA persistence.** Challenge numbers and payloads are held in memory for the
lifetime of the attempt only; they are not written to the state store, not logged, and not
retained after the attempt terminates.

**AUTH-046 — Denied or ignored approvals.** A denial or a lapsed challenge maps to `AUTH_FAILED`
with `MFA_DENIED` or `MFA_TIMEOUT`. There is no re-prompt loop; a new attempt is an explicit human
decision.

---

## 6. Resume semantics, expiry and timeouts

**AUTH-050 — Two-phase interactive flow.** `planner_auth_start` opens the interactive sign-in and
returns `operation_id` plus the current state. `planner_auth_resume` re-observes the same attempt
and returns the updated state. Neither tool transports credentials.

**AUTH-051 — Resume is idempotent and observational.** Calling `planner_auth_resume` repeatedly
does not restart sign-in, does not re-trigger MFA, and has no side effect other than an audit
event and a state refresh.

**AUTH-052 — Resume is bound to `operation_id`.** An unknown, expired or already-terminated
`operation_id` returns `AUTH_FAILED` with `AUTH_OPERATION_UNKNOWN`. Attempts are single-use and
non-replayable.

**AUTH-053 — Timeouts.** Three independent, configured bounds: challenge expiry (from Microsoft,
reflected in `expires_at`), attempt expiry (overall interactive window), and probe timeout (per
navigation). Any expiry yields `AUTH_FAILED`, never a hung tool call.

**AUTH-054 — Session expiry detection.** A previously `AUTHENTICATED` context that fails a probe
becomes `SESSION_EXPIRED` and every dependent capability is immediately unavailable until a new
attempt succeeds. In-flight operations fail closed rather than retrying.

**AUTH-055 — Concurrency.** At most one authentication attempt exists at a time per profile.
A second `planner_auth_start` while an attempt is live returns the existing `operation_id`, not a
new attempt (`WORKER-040`).

**AUTH-056 — No background reauthentication.** The system never opens a sign-in flow on its own.
Reauthentication is always operator-initiated.

---

## 7. Conditional Access

**AUTH-070 — `BLOCKER_CONDITIONAL_ACCESS` is terminal.** If Microsoft requires a managed,
compliant, enrolled or domain-joined device, the flow stops immediately, reports the blocker, and
records a sanitized audit event (`PRIV-020`, `PRIV-025`, `ARCH-131`).

**AUTH-071 — No bypass, no spoofing, no relocation.** Prohibited: user-agent or platform spoofing,
device-attribute forgery, enrolment, MDM/Intune registration, certificate installation, moving the
sign-in to a managed machine to extract a session, or trying a different browser to evade the
policy (`PRIV-021`, `PRIV-022`, `PRIV-023`).

**AUTH-072 — Report, do not engineer around it.** The correct output is a clear blocker report to
the operator, plus capability rows moving to a blocked support state
([docs/planner-premium-capabilities.md](./planner-premium-capabilities.md) `CAP-030`).

**AUTH-073 — The blocker is not retried.** No retry loop, no backoff schedule, no alternative
authentication path is attempted after `BLOCKER_CONDITIONAL_ACCESS`.

---

## 8. Error classes

| Error class | Trigger | Terminal |
| --- | --- | --- |
| `AUTH_REQUIRED` | No valid session | No |
| `MFA_PENDING` | Challenge open, awaiting Authenticator | No |
| `MFA_TIMEOUT` | Challenge expired | Attempt |
| `MFA_DENIED` | Human denied the push | Attempt |
| `SESSION_EXPIRED` | Probe failed for a known session | No |
| `ACCOUNT_CONTEXT_MISMATCH` | Wrong principal/tenant | Attempt |
| `ACCOUNT_CONTEXT_AMBIGUOUS` | More than one principal observed | Attempt |
| `AUTH_OPERATION_UNKNOWN` | Unknown/expired `operation_id` | Attempt |
| `BLOCKER_CONDITIONAL_ACCESS` | Managed/compliant device required | Yes, capability-wide |
| `WORKER_UNAVAILABLE` | Worker not reachable/ready | No |

**AUTH-080** Error payloads carry the class, `operation_id` and the sanitized description only.
Raw Microsoft error text, correlation IDs from the page, and URLs are never forwarded.

---

## 9. Evidence and tests

**AUTH-090 — Required evidence per attempt.** Audit record with: `operation_id`, terminal state,
error class if any, sanitized description sequence, timestamps, UIContract version used by the
probe. No identity fields.

**AUTH-091 — Required unit tests (mock only, CI never touches a real tenant, `ARCH-084`).**

1. Every allowed transition in `AUTH-021` is accepted; a representative set of disallowed
   transitions is rejected.
2. `UNKNOWN` and any unparsable state are treated as unauthenticated by the policy gate.
3. The sanitized event serializer emits exactly the five fields of `AUTH-040` and drops extras.
4. Descriptions outside the `AUTH-041` vocabulary are coerced to `sign_in_failed`.
5. A repository/log/state scan asserts no password, cookie, token, storage-state or MFA code field
   can be persisted by the auth module.
6. `planner_auth_resume` called N times produces one attempt and N observations.
7. Account/tenant mismatch and ambiguity both fail closed and never switch accounts.
8. A simulated Conditional Access managed-device page yields `BLOCKER_CONDITIONAL_ACCESS`, no
   retry, and no user-agent mutation.
9. Challenge and attempt expiry both terminate the call within the configured bound.
10. Number-matching extraction failure yields `mfa_number: null`, never a fabricated number.

**AUTH-092 — Live attestation evidence** is an operator-run, read-only campaign
([docs/governance.md](./governance.md) `GOV-042`) recording only sanitized fields.

**AUTH-093 — No test may authenticate non-interactively.** A test that supplies a password, cookie
or storage state is a governance violation, not a shortcut.

---

## 9a. Operator-only live sign-in bootstrap navigation

**AUTH-094 — Fixed-target operator navigation.** A live interactive sign-in needs the dedicated
persistent professional profile to be positioned on the Microsoft sign-in flow. The worker exposes
exactly one narrowly-scoped mechanism for that, and it is operator-only:

* Target: the reviewed production constant
  `m365_browser_worker.bootstrap_navigation.PLANNER_WEB_BOOTSTRAP_URL`
  (`https://planner.cloud.microsoft/`). There is no URL, host, path or query parameter anywhere in
  the call path, so no agent, MCP client, control plane or Docker-network peer can steer the browser.
  `target_class` is the only classification returned (`planner_web`).
* Transport: worker-local `POST /auth/bootstrap/navigate`. It is NOT an MCP tool, is absent from the
  tool registry, capability projection, agent card and the typed `/operations` dispatcher, and the
  control plane has no proxy path to it (`WorkerClient` exposes no such method).
* Admission: SOCKET-level loopback only (`127.0.0.1`, `::1`). `X-Forwarded-For`, `X-Real-IP` and
  `Forwarded` are never consulted, so a container on the Docker network cannot spoof loopback; a
  non-loopback peer receives `404`. Port 8090 remains unpublished.
* Parameters: none. Any query string or non-empty body is rejected with `400 INVALID_REQUEST`.
* Guards: the narrow `AuthBootstrapGuard` (browser started + dedicated persistent professional
  profile + neutral/approved origin) plus a runtime `evaluate_browser_egress` ALLOW decision on the
  fixed target. Both fail closed as `503`. Graph/API hosts and non-HTTPS stay denied and the
  Playwright route interceptor keeps evaluating redirects and sub-resources.
* Behaviour: one idempotent operator action — one navigation per call, reusing a neutral placeholder
  page or opening exactly one page in the persistent context. No retry, no credential entry, no MFA
  automation.
* Response/logs: `{ "ok": true, "target_class": "planner_web", "auth_state": "UNKNOWN|AUTHENTICATED" }`
  only. No URL, DOM, page text, cookie, token, UPN, tenant id, Planner/mailbox data or browser handle.
* Invocation: the operator wrapper `scripts/operator_auth_bootstrap_navigate.sh`, which accepts no
  arguments and reaches the endpoint through
  `docker exec m365-ui-mcp-browser-worker-1 curl -X POST http://127.0.0.1:8090/auth/bootstrap/navigate`.

**AUTH-096 — Fixed-target begin-signin (two-step operator flow).** The dedicated
persistent professional profile begins an interactive Microsoft sign-in in exactly
two operator-only steps:

1. Navigate to Planner Web (AUTH-094): position the profile on the fixed Planner
   Web target so the operator lands in the Microsoft 365 surface.
2. Begin sign-in (this requirement): a second operator-only action navigates
   exactly once to the fixed Microsoft authentication host
   `m365_browser_worker.bootstrap_navigation.MICROSOFT_AUTH_BOOTSTRAP_URL`
   (`https://login.microsoftonline.com/`). There is no URL, host, path or query
   parameter anywhere in the call path. `target_class` is the only classification
   returned (`microsoft_auth`).

Step 2 reuses the same transport, admission, parameter and catalog invariants as
AUTH-094 (loopback-only, 404 for non-loopback, no query/body, absent from MCP
tool/capability/agent-card/dispatcher/control-plane, `docker exec` wrapper with no
arguments). It does NOT relax `AuthBootstrapGuard` or the `auth_status`/`
auth_start`/`auth_resume` guards. Step 2's dedicated guard requires the existing
browser egress ALLOW on the fixed Microsoft auth target AND an existing
approved-auth-origin source class (`planner_web` host, neutral placeholder, or an
already approved Microsoft authentication origin). Arbitrary/non-approved origins,
Graph, non-HTTPS and any non-login.microsoftonline.com target are impossible and
fail closed as `503`. Exactly one navigation, no retry, no credential entry, no
MFA automation, no DOM/content exposure. Reproduction is operator-initiated only.

**AUTH-097 — No credentials/MFA automation, no public MCP exposure.** Neither step
performs, accepts, or relays credential entry or MFA approval; both steps are
worker-local operator endpoints, never MCP tools, and never published to any public
surface or MCP client.

**AUTH-098 — Two-step runbook.** Operator runs
`scripts/operator_auth_bootstrap_navigate.sh` then
`scripts/operator_auth_bootstrap_begin_signin.sh` (each no-argument, loopback
`docker exec`). No credentials/MFA automation; no public MCP exposure. The second
step hits the worker-local `POST http://127.0.0.1:8090/auth/bootstrap/begin-signin`
endpoint, which is operator-only and never exposed as an MCP tool or over the
public network.

**AUTH-099 — Sanitized one-way MFA notification contract.** The only outbound
surface permitted to carry an MFA challenge is
`planner_mcp.notifications.mfa` (see `hermes-integration.md`). It emits a
*sanitized, closed* `MfaNotification` (exactly `mfa_number`, `operation_id`,
`service`, `description`, `expires_at` plus the non-actionable
`approve_in_authenticator_only` / `approval_channel` markers) built from
`planner_mcp.auth.MfaChallenge`. It has **no MFA-approval capability** and carries
**no Telegram/Hermes credentials, webhook URLs or secrets of any kind**. Delivery
is one-way: a failed delivery is a notification degradation, never a fabricated
approval and never a Planner operation success. When no direct adapter is wired in
this repo, the external Hermes→Telegram adapter consumes the stable serialized
`MfaNotification` JSON (the documented one-way CLI/JSON contract) exactly as a
read-only observer (AUTH-003, ADR-004).

**AUTH-100 — Fail-closed live MFA state.** `MFA_REQUIRED` / `WAITING_FOR_MFA` are
*resolved* live states, not static constants. The worker wires
`planner_browser_worker.auth_flow.classify_page` / `detect_mfa_number` /
`MfaChallenge` into `planner_browser_worker.auth_state_machine`, which advances the
`AuthState` lifecycle only on a *uniquely* resolvable number-matching probe
(`resolve_mfa_number_unique`). When the number cannot be read unambiguously, or
the page is not a number-matching/approval context, the state machine fails closed
to `UNKNOWN` and emits **no** challenge value. Transitions go through the guarded
`AuthContext.transition`, so crafted text cannot push the machine into a privileged
state. Email/MFA *locators* remain evidence-gated under `common.auth`; they are
never guessed from code.

**AUTH-101 — Encrypted-store operator sign-in automation (supersedes "human types
password").** AUTH-001's "human types the password interactively" obligation is
superseded for the operator path by local encrypted-store automation: the
operator-local `scripts/operator_auth_login.py` decrypts two already-provisioned
*systemd user* credentials from the fixed store under
`~/.local/lib/credstore.encrypted` via `systemd-creds decrypt --user`, keeps them
**memory-only**, and forwards them through a loopback `stdin`/IPC path to the
narrowly-scoped operator-only `POST /auth/bootstrap/operator-submit` route. That
route applies ONLY the two `common.auth` sign-in fields (`auth.login_email_input`,
`auth.login_password_input`) to the already-open Microsoft authentication page;
no URL, generic DOM primitive, Graph surface or locator guessing is reachable, and
the worker never prints, logs, env-stores or state-stores the values. There is no
headed/graphical fallback: the canonical path is headless Chromium + Playwright over
the persistent professional profile (see
[`archive/ADR-ARCHIVED-gui-vnc-handoff.md`](archive/ADR-ARCHIVED-gui-vnc-handoff.md)).
Preserved invariants from AUTH-002 / ADR-004: no plaintext persistence, no
environment variable, no argv, no ChatGPT, and no Telegram credentials are ever
involved. The operator submit route clicks the Microsoft "Next" control to advance
from the email step and the Microsoft form "Sign in" control to finalize credential
submission; neither carries credentials and neither is an MFA control. MFA approval
is still Microsoft Authenticator-only, and BOTH `common.auth` fragments
(`common.auth.email` and `common.auth.password`, see `AUTH-107`) must be attested
before any sign-in field is applied (fail closed otherwise).

**AUTH-104 — Source-controlled sign-in progression selectors.** The `common.auth` fragments declare
four sign-in progression selectors: `auth.login_email_input`, `auth.login_next_button`,
`auth.login_password_input` and `auth.login_signin_button`. All four remain `UNVERIFIED_LIVE` value-null
placeholders. `auth.login_next_button` and `auth.login_signin_button` are progression-only selectors
(the "Next" and "Sign in"/"Iniciar sessão" controls); neither carries credentials. The operator submit
route applies `auth.login_email_input` and `auth.login_password_input` and additionally clicks
`auth.login_next_button` and `auth.login_signin_button` to drive the standard Microsoft Entra ID
progression; none of the four is an MFA control (`AUTH-101`, `ADR-009`). These are contract/metadata
declarations only; this step introduces no runtime browser behavior beyond the click sequence above.

**AUTH-105 — Operator-only read-only live attestation observation (per-fragment `common.auth`).** A complete,
evaluator-compatible `AttestationObservation` (`source=LIVE_UI`, current `contract_set_digest`/campaign
binding, selector order exactly matching the fragment) must be producible from the ALREADY-RUNNING dedicated
professional browser context, observing EXACTLY one atomic `common.auth` fragment's progression selectors —
`common.auth.email` (`auth.login_email_input` -> `auth.login_next_button`) or `common.auth.password`
(`auth.login_password_input` -> `auth.login_signin_button`) — and emitting per-selector result + value-free
`structural_digest` only. Any other fragment id fails closed. The
primitive is a GET on `POST`-free `/auth/bootstrap/collect-observation` with SOCKET-level loopback admission
only (404 for non-loopback, no query string, no body), reuses `collect_structural_observation` so the output
is byte-compatible with `scripts/collect_live_attestation_observation.py` and consumable by
`attest_ui_contract.py evaluate`, and never fills/clicks/types/navigates/evaluates or returns DOM/URL/value/
credential. It MUST NOT weaken the fail-closed evaluator or attestation gate: the observation is emitted at
`target_level=DISCOVERY`, so evaluation can only yield `REVIEW_REQUIRED`; promotion stays PR/evidence based.
It fails closed (503, no exception text) when the running context is unusable or any selector cannot be
deterministically counted. It does NOT replace the per-stage `discover-email`/`discover-password` routes
(AUTH bootstrapping); it is the evidence primitive that lets a per-fragment UNIQUE_MATCH observation be
collected and evaluated in one step.

**AUTH-106 — Operator-only pre-attestation email stage (headless-safe deadlock break).** With the
GUI/noVNC/X11 headed handoff removed (PR #614) there was no headless way to reach the password surface for
`common.auth` attestation: the password/signin selectors only appear AFTER email -> Next, and
`submit_operator_signin` requires full attestation. The `POST /auth/bootstrap/begin-email` route (operator-only,
socket-loopback admitted, no query/extra body keys — the password is NOT an accepted key) fills ONLY the
operator's professional email and clicks ONLY the Microsoft "Next" control to advance the live Microsoft
authentication page to the password step, so the four `common.auth` selectors become observable for
attestation (see AUTH-105). It does NOT require `common.auth` to be attested (intentional), it NEVER types the
password and NEVER clicks Sign in, and it does NOT widen the attested `submit_operator_signin` path (which still
requires full attestation before any password is applied). All fail-closed invariants from AUTH-094/096/101 are
preserved: dedicated persistent professional profile, approved Microsoft authentication origin, memory-only
email value, no URL/DOM/cookie/token/UPN/tenant exposure. Canonical auth path remains private Chromium headless +
Playwright + persistent professional profile + operator-only fixed-target bootstrap + encrypted credential
store + out-of-band MFA approval.

**AUTH-107 — Atomic `common.auth` fragment split (email / password surfaces).** The single `common.auth`
UIContract fragment was structurally impossible to attest: `_validate_observation_binding` demands the exact
SET AND ORDER of the fragment's selectors, `effectively_attested` is all-or-nothing, and the email and
password surfaces never coexist on the same Microsoft Entra ID sign-in page (the password/sign-in selectors
only appear AFTER email -> Next, at which point the email selectors are gone). `common.auth` is therefore
split into TWO atomic fragments, each independently collectable on its REAL surface:
`common.auth.email` = {`auth.login_email_input`, `auth.login_next_button`} and
`common.auth.password` = {`auth.login_password_input`, `auth.login_signin_button`}. The authentication gate
`common_auth_attested()` returns True ONLY when BOTH fragments exist and are `effectively_attested`; a missing
fragment or a single attested fragment fails closed. AUTH-101 therefore requires BOTH. The evaluator, the
binding validation, and the fail-closed attestation semantics are UNCHANGED — no union-of-stages relaxation is
introduced; the fix is contract granularity, not gate weakening. The legacy flat `contracts/ui_contract.json`
continues to declare all four `auth.*` selectors so the legacy projection and the frozen mock-parity baseline
remain byte-consistent. Promotion of each fragment to `ATTESTED` stays PR/evidence based with human review,
per fragment, on fresh live UNIQUE_MATCH evidence for exactly that fragment's two selectors.

**AUTH-108 — `/health` reports the full-set contract digest bound by observations.** Live attestation
observations bind `load_ui_contract_set().digest()` — the SHA-256 of the COMPLETE UIContract set (every
fragment). The compatibility `load_status()` view projects to Planner scope and digests only common + Planner
fragments, so its digest differs by construction once other application fragments exist. Reporting the
projection digest on the worker `/health` endpoint made every operator digest comparison mismatch and was the
real origin of the `CONTRACT_SET_DIGEST_MISMATCH` class of failures. `/health` and every operator
digest-comparison path MUST therefore report the FULL-SET digest via
`planner_mcp.ui_contract.full_contract_set_digest()`. The planner-projection digest is retained ONLY where the
legacy-projection contract and the frozen parity baseline require it (`planner_readiness`,
`planner_ui_contract_status`). This is explicitly NOT a relaxation: `_validate_observation_binding` still
requires an exact digest match, and observations still bind the full set.

**AUTH-109 — Operator-only deterministic pre-email sign-in surface resolver.** When Microsoft presents a
deterministic intermediate surface **before** the email-entry field (account chooser / "use another account"
prompt), the `begin-email` (AUTH-106) and `discover-email` paths cannot proceed because the email input does
not yet exist on the page. This resolver is the headless-safe answer: an OPERATOR-ONLY, loopback-admitted,
pre-attestation `POST /auth/bootstrap/resolve-signin-surface` that forces the email-entry surface by clicking
ONLY the fixed "use another account" control (matched from a CLOSED set of exact Microsoft labels), never
selecting a cached identity (account tile), never typing, never navigating by URL/locator. It is bounded and
value-free: it classifies the live surface into a CLOSED kind from a bounded body-text reading and fails closed
(`PolicyDenied`) on any non-deterministic surface (pick-an-account, stay-signed-in, consent, method selection,
error, ambiguous, unknown) — it never guesses a surface or an identity. It does NOT require `common.auth` to be
attested (intentional, so the email surface can be reached for attestation) and does NOT widen the attested
`submit_operator_signin` path. All fail-closed invariants from AUTH-094/096/101/106 apply; the response carries
only `{ok, auth_state, surface}` (closed `EMAIL_ENTRY` / `ACCOUNT_CHOOSER` / `USE_ANOTHER_ACCOUNT_PROMPT`
classification) — no URL, DOM, cookie, token, UPN, tenant id or account identifier. AUTH-109 never weakens the
attestation/evaluator/fail-closed semantics and is not a generic browser primitive.

**AUTH-110 — Deterministic, phrase-bound Authenticator number-match extraction.** The post-password MFA number-match value is extracted ONLY when the page carries the fixed explicit number-matching semantic context (e.g. "enter the number", "number matching", "the number shown on your") immediately preceding a 2-digit code, within a bounded no-newline-nearby window. A date, countdown, request id or other generic 2-digit value elsewhere on the page is NEVER a candidate, so a stray year/timestamp can never be mis-extracted. Extraction is fail-closed: exactly one phrase-bound candidate yields the number; zero candidates (no number-match prompt) or more than one distinct candidate (ambiguous surface) yields `None` and the state machine never guesses or synthesizes a challenge value. This is the determinism guarantee for the `AUTH-103` observe path: when `observe` returns a unique `mfa_number`, that sanitized value is the single authorized out-of-band notification payload (Hermes → Telegram; no approval capability). When `mfa_number` is `null`/`mfa_ambiguous:true`, the runner STOPs for human Authenticator approval and emits NO challenge value.

**AUTH-111 — Operator-only deterministic canonical sign-in run orchestration.** The host-side `scripts/operator_auth_run.py` conductor encodes the exact once-only sequence `navigate → begin-signin → resolve-signin-surface (AUTH-109) → require surface EMAIL_ENTRY / discover-email UNIQUE_MATCH → operator-submit (AUTH-101)`, with NO human browser interaction. It is NOT an MCP tool and is NOT network-exposed. It (1) runs each operator-only loopback route exactly once in order; (2) enforces the deterministic surface gate after the resolver — the email-entry surface MUST be present (2× `UNIQUE_MATCH` on the email keys) before submit is allowed, probing `discover-email` a bounded number of times with a short sleep to absorb page-load timing (a first NO_MATCH probe is NOT the fail-closed STOP); (3) refuses operator-submit on any other surface (account chooser still showing, device enrolment / Conditional Access / unsupported method, ambiguous, unknown) — it never guesses, never clicks an identity, never proceeds; (4) drives `operator-submit` via the VERIFIED in-container loopback transport (host `urllib` to the published `127.0.0.1:8090` port is rejected `404` by socket-peer admission; the two provisioned credentials are decrypted host-side and handed to an in-container client over `docker exec` **stdin**, which POSTs from the container's own loopback). All fail-closed invariants from AUTH-005/094/096/101/106/109 apply; the script reports ONLY sanitized, value-free status and asserts NO authentication (the human still completes MFA in Microsoft Authenticator).

---

## 10. Traceability

| ID range | Area |
| --- | --- |
| AUTH-001…006 | Principles |
| AUTH-010…016 | Profile lifecycle |
| AUTH-020…025 | State machine |
| AUTH-030…035 | Account/tenant/session context |
| AUTH-040…046 | MFA detection and notification |
| AUTH-050…056 | Resume, expiry, timeouts |
| AUTH-070…073 | Conditional Access |
| AUTH-080 | Error classes |
| AUTH-090…093 | Evidence and tests |
| AUTH-094…095 | Operator-only fixed-target bootstrap navigation |
| AUTH-096…098 | Two-step operator begin-signin flow |
| AUTH-099…101 | Encrypted-store operator sign-in + sanitized MFA notification |
| AUTH-105 | Operator-only read-only live attestation observation (per-fragment) |
| AUTH-106 | Operator-only pre-attestation email stage (headless deadlock break) |
| AUTH-107 | Atomic `common.auth` fragment split (email / password surfaces) |
| AUTH-108 | `/health` reports the full-set contract digest bound by observations |
| AUTH-109 | Operator-only deterministic pre-email sign-in surface resolver |
| AUTH-110 | Deterministic, phrase-bound Authenticator number-match extraction |
| AUTH-111 | Operator-only deterministic canonical sign-in run orchestration |



