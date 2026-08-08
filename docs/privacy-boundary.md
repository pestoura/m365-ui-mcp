# Privacy boundary — personal device

> **Document status:** Normative. **Basis:** [ADR-008](adr/ADR-008-personal-device-privacy-boundary.md).
> **Companion controls:** SEC-003, SEC-040..SEC-043, [security.md](security.md#5-device-and-conditional-access-boundary),
> [authentication-and-mfa.md](authentication-and-mfa.md), [threat-model.md](threat-model.md#assets) (asset A7).
> This document is normative (see ADR-008). It is the single source of truth for what the system
> MUST NEVER do to the host machine, and for how the professional browser profile is isolated.

The host running planner-mcp is a **personal machine**. It must remain personal. This document is
normative (see ADR-008).

## 1. Scope and normative status

This document governs the **host operating system and the professional browser profile**, not the
tenant. Tenant data is governed by [security.md](security.md) and
[planner-premium-capabilities.md](planner-premium-capabilities.md). The two boundaries are distinct
and both fail closed:

- If a *tenant* control is uncertain → `BLOCKER_LICENSE_UNVERIFIED` / `BLOCKER_CONDITIONAL_ACCESS`.
- If a *device* control is uncertain → refuse the path; never enrol, never spoof, never proceed.

The privacy boundary is **not negotiable for capability**. A capability that requires a managed
device is recorded as `BLOCKED_CONDITIONAL_ACCESS` and left there. There is no "almost compliant"
state. ADR-008 records the decision: we will not compromise the personal device to widen reach.

## 2. Absolute prohibitions

The system MUST NEVER, automatically or as a side effect:

- enrol the device in **Microsoft Intune** or **Company Portal**;
- install or register with **Microsoft Identity Broker** (`microsoft-identity-broker`, Linux
  broker packages, or equivalents);
- perform **Entra device registration**, hybrid join or Azure AD join;
- accept **MDM** management or install a corporate **EDR/antivirus** agent;
- provision, request or store a **device certificate** issued by the corporate PKI;
- install corporate root CAs into the host or browser trust store;
- enable OS-level "work or school account" integration.

Any UI path leading to these is a fail-closed decision point, not a step to automate.

### 2.1 Prohibition catalogue (rationale + detection)

| # | Prohibition | Why it is forbidden | How it is detected / refused |
| --- | --- | --- | --- |
| PR-1 | Intune / Company Portal enrolment | Turns a personal machine into a managed asset; defeats P6 | Worker treats any enrolment prompt as `BLOCKER_CONDITIONAL_ACCESS`; CI asserts no enrolment command exists |
| PR-2 | Identity Broker install/register | Broker brokers *all* identity on the host, not just the tenant | Package-manager guard in CI; runtime check that no broker daemon is present in the profile path |
| PR-3 | Entra / hybrid / AAD join | Joins the device to the tenant's device directory | No join API is ever called; any join UI is a blocker, never a step |
| PR-4 | MDM / corporate EDR agent | Remote management and telemetry of the host | Containers run with `cap_drop: ALL`, `no-new-privileges`; host agent install is out of process scope and forbidden by policy |
| PR-5 | Corporate device certificate | Establishes a managed-device identity usable for compliance spoofing | No PKI client; no cert request path; profile volume excludes cert stores |
| PR-6 | Corporate root CA into trust store | Allows MITM-class trust of corporate proxies | Profile is created with a clean trust store; no CA import step exists |
| PR-7 | OS "work/school account" integration | Persists a corporate identity at the OS level | Not configured; any OS prompt is a blocker |

Each prohibition is also a **code-absence** requirement: `scripts/check_no_secrets.sh` and the
repo review gate fail if any enrolment, broker, join, or CA-import command is present. A
contribution that adds such a path is rejected at review regardless of intent.

### 2.2 Allowed vs forbidden operations matrix

| Operation | Allowed? | Note |
| --- | --- | --- |
| Open a Chromium profile dedicated to tenant work | Yes | Professional profile, isolated directory |
| Sign into the tenant in that profile | Yes | Human enters password; no automation of credentials |
| Read project data needed for the current operation | Yes | Data minimisation applies |
| Persist cookies/session in the profile volume | Yes | Local only, `0700`, never exported |
| Enrol the device to satisfy Conditional Access | **No** | `BLOCKER_CONDITIONAL_ACCESS` instead |
| Install a broker/agent/EDR to "fix" auth | **No** | Out of scope; prohibited by PR-2/PR-4 |
| Copy the profile off the host for "backup" | **No** | SEC-012; profile is never exported |
| Reuse a token obtained on a managed device | **No** | SEC-042; device-compliance spoofing prohibited |

## 3. Isolation requirements

| Boundary | Requirement |
| --- | --- |
| Browser profile | A dedicated **professional** Chromium persistent profile, separate directory, never the operator's personal profile. |
| Profile data | Excluded from git, backups that leave the host, and evidence artifacts. |
| Filesystem | Profile directory permissions `0700`, owned by the runtime user. |
| Containers | No host home mount, no Docker socket, no bind mount of personal directories. |
| Network | Worker on an internal network; no public ingress to the browser zone. |
| Identity | No personal Microsoft/Google identity signed into the professional profile. |
| Sync | Chromium profile sync disabled. |

### 3.1 Container and filesystem isolation (concrete)

Enforced via `compose.yml` and [deployment.md](deployment.md), mirroring SEC-080..SEC-087:

- Both containers run as a non-root system UID (`10001` control, `10002` worker).
- Root filesystem is read-only; scratch is `tmpfs` with a size cap.
- `cap_drop: ALL`, `security_opt: no-new-privileges:true`.
- No Docker socket mount; no host home mount; only the profile volume is writable (worker).
- The worker publishes **no port** and sits on an `internal: true` network.
- The control plane publishes only to `127.0.0.1`; public exposure is via Cloudflare Portal only.

### 3.2 Profile lifecycle

1. **Creation** — a dedicated `professional` Chromium profile is created in a directory outside
   the operator's personal profile tree, mode `0700`, owned by the worker UID. Profile sync is
   disabled at creation.
2. **Use** — single-owner, serialized access (one operation at a time per profile).
3. **Rotation** — if the session is suspected compromised or the auth state machine enters
   `AUTH_FAILED` repeatedly, the profile is closed and re-authenticated; no token reuse.
4. **Revocation** — an operator-initiated "revoke session" closes the profile and discards the
   session material; Microsoft-side revocation is the operator's action in their tenant.
5. **Deletion** — removing the workload deletes the profile volume with it; no copy is left in
   backups, git, or evidence artefacts.

## 4. Data minimisation

- Only project data needed to answer the current operation is extracted.
- No mailbox, Teams chat, OneDrive or SharePoint content is read.
- Screenshots/DOM snapshots are local evidence only, referenced by hash, never returned inline,
  never sent to Hermes or the MCP client.
- No telemetry field carries account UPN, tenant name, device identifiers or IPs.

### 4.1 Minimisation rules (operational)

- **Extract by need.** A `planner_task_list` extracts the task fields required by the contract;
  it does not scrape the whole DOM "just in case."
- **No lateral surfaces.** The worker navigates only within Planner Premium for the operation in
  flight; it never opens mailbox, Teams, OneDrive or SharePoint.
- **Evidence by reference.** Screenshots/DOM are written to the local evidence store and
  referenced by `operation_id` + hash. They are never returned inline and never transmitted to
  Hermes or the MCP client (SEC-006, SEC-074).
- **Telemetry hygiene.** Metric labels are low-cardinality (tool name, mutation class, decision,
  outcome, auth state). UPN, tenant name, device id and IP are never emitted (SEC-073).

## 5. What Conditional Access means here

If tenant policy requires a managed/compliant device, the correct outcome is **blocked, not
enrolled**. `BLOCKER_CONDITIONAL_ACCESS` is a legitimate final answer. The remediation is an
organisational decision (e.g. a separate corporate-managed machine), never a technical bypass.

### 5.1 Conditional Access handling (operational)

| State observed | System behaviour | Capability state |
| --- | --- | --- |
| Sign-in proceeds normally | Continue; `AUTHENTICATED` | normal |
| Prompt offers "register this device" | Treat as blocker; never accept | `BLOCKER_CONDITIONAL_ACCESS` |
| Policy demands compliant/hybrid device | Stop; record blocker | `BLOCKED_CONDITIONAL_ACCESS` |
| Device-compliance spoofing attempt | Prohibited (SEC-042); refuse | terminal |

`BLOCKER_CONDITIONAL_ACCESS` is **terminal for that capability**, not a retry trigger
(SEC-043). Resolution is an organisational decision taken outside this system — typically "use a
separate corporate-managed machine." The product does not degrade, does not spoof user-agent for
policy evaluation, and does not reuse tokens from a managed device.

## 6. Operator rules

1. Use the professional profile only for the tenant work this MCP performs.
2. Never approve an enrolment or device-registration prompt because automation surfaced it.
3. Never paste the Microsoft password into any tool, chat, config or terminal.
4. Approve MFA only in Microsoft Authenticator, and only when a sign-in was genuinely initiated.

### 6.1 Operator runbook — enrolment prompt appears

1. **Stop.** Do not click "Register" / "Join" / "Enroll."
2. **Note the blocker.** The system should already have raised `BLOCKER_CONDITIONAL_ACCESS`.
3. **Do not work around it.** No broker install, no CA import, no "work/school account" toggle.
4. **Escalate organisationally.** If the tenant genuinely requires a managed device, perform the
   work on a separate corporate-managed machine; leave this personal host out of scope.
5. **Report.** Capture the blocker event id for the audit trail.

## 7. Enforcement layers

| Layer | Mechanism | Catches |
| --- | --- | --- |
| Runtime (worker) | Enrolment UI → `BLOCKER_CONDITIONAL_ACCESS` | PR-1, PR-3, PR-7 |
| Runtime (container) | `cap_drop`, `no-new-privileges`, no socket, no home mount | PR-4 |
| Build/CI | `check_no_secrets.sh`, gitleaks, code-absence review | all PR-* by command presence |
| Profile | Clean trust store, sync disabled, `0700` | PR-5, PR-6 |
| Network | `internal: true`, no published port | exfiltration of profile |

## 8. Verification

- P-013 asserts profile path isolation and permissions.
- P-023 asserts enrolment-prompt detection and refusal against the mock UI.
- P-062 asserts telemetry contains no prohibited fields.
- CI check: repository contains no reference to enrolment automation commands.

### 8.1 Verification matrix

| Requirement | Verified by |
| --- | --- |
| Absolute prohibitions (PR-1..PR-7) | `scripts/check_no_secrets.sh`, gitleaks, `.gitignore`, review checklist |
| Isolation (§3) | container build gate, compose review, profile permission test |
| Data minimisation (§4) | redaction unit tests, evidence-by-reference assertion, metric cardinality test |
| Conditional Access (§5) | mock-UI enrolment-prompt test → `BLOCKER_CONDITIONAL_ACCESS` |
| Operator rules (§6) | runbook review; no automated credential path exists |

## 9. Incident response — if a prohibition is violated

1. **Detect** — CI (code-absence) or runtime (blocker) flags the violation.
2. **Contain** — stop the operation; if a profile was touched, close and discard it.
3. **Record** — write a blocker/audit event with the violating path and `operation_id`.
4. **Remediate at the host** — if any enrolment/broker/CA actually landed on the personal
   machine, the operator removes it at the OS level; the product cannot and does not do this for
   them.
5. **Review** — a maintainer determines how the path appeared and tightens the gate (ADR if the
   boundary itself must change).

## 10. Worked example — enrolment prompt during sign-in

A concrete walkthrough of the privacy boundary firing in the real flow:

1. The worker opens the Microsoft sign-in surface in the professional profile (human enters the
   password; no automation reads it).
2. After credential submission, Conditional Access evaluates the device. Instead of granting, the
   tenant responds with a "Register this device / Join to Entra ID" prompt.
3. The worker's UIContract includes an enrolment-prompt detector (selector fragment attested in
   `browser/selectors/planner-premium.yaml`). The detector fires.
4. The auth state machine refuses to proceed past `WAITING_FOR_MFA`/grant and raises
   `BLOCKER_CONDITIONAL_ACCESS`; the capability under attempt moves to `BLOCKED_CONDITIONAL_ACCESS`.
5. The worker does **not** click "Register," does **not** install a broker, does **not** import a
   CA. It returns the blocker verbatim to the control plane, which returns it to the caller.
6. The operator sees a clean, explained stop — not a broken automation — and resolves the
   organisational question (use a managed machine) outside this system.

This is the *intended* outcome. A "successful" enrolment would be a critical privacy violation,
not a feature.

## 11. Privacy-boundary acceptance checklist

A contribution touching the device or profile is merged only if all hold:

- [ ] No path performs or suggests Intune/Company Portal/Identity Broker/Entra join/MDM/EDR/corporate CA.
- [ ] No code reads, stores, forwards, or types the Microsoft password.
- [ ] The professional profile is created isolated (`0700`), sync disabled, no personal identity.
- [ ] The profile volume is never exported, backed up off-host, or committed to git.
- [ ] The worker publishes no port and sits on an `internal: true` network.
- [ ] Telemetry contains no UPN, tenant name, device id or IP.
- [ ] `scripts/check_no_secrets.sh` and gitleaks pass on full history.
- [ ] The mock-UI enrolment-prompt test fails closed (`BLOCKER_CONDITIONAL_ACCESS`).
- [ ] CI asserts no live-tenant configuration is present (`assert_no_live_tenant.py`).

## 12. Interaction with the trust zones

| Zone | Privacy-boundary role |
| --- | --- |
| E (edge/public) | Never receives device state or profile material |
| C (control) | Never holds the password or profile; only references by hash |
| W (execution) | Owns the profile; enforces prohibitions; never publicly routable |
| H (human) | Owns identity and the device decision; never crossed by software |
| ZH (Hermes) | Receives sanitized events only; cannot trigger enrolment or auth |

The boundary is enforced at the **W** layer at runtime and at **CI** at build time; both must hold
for the personal device to stay personal.

## 13. References

- [ADR-008](adr/ADR-008-personal-device-privacy-boundary.md) — the decision this document enforces.
- [security.md](security.md#5-device-and-conditional-access-boundary) — SEC-040..SEC-043.
- [threat-model.md](threat-model.md#1-assets) — asset A7 (personal device integrity/privacy).
- [architecture.md](architecture.md#5-trust-zones) — Zone W (execution) and Zone H (human).
- [deployment.md](deployment.md) and `compose.yml` — container/network hardening.
