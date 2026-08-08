# Planner MCP — Privacy Boundary

Status: specification (implementation-grade) — **binding constraint**
Canonical upstream: [docs/vision.md](./vision.md)
Related: [docs/architecture.md](./architecture.md) · [docs/security.md](./security.md) · [docs/threat-model.md](./threat-model.md) · [docs/governance.md](./governance.md)

Requirement IDs (`PRIV-xxx`) are stable. This document defines a **hard boundary**. Unlike a
performance target or a design preference, nothing in this document may be traded away for
functionality. If a required capability cannot be delivered without crossing this boundary, the
capability is not delivered.

---

## 1. The hard boundary

**PRIV-001 — Personal device boundary.** The machine running Planner MCP is the operator's
**personal** device. It is not, and must never become, a corporate-managed endpoint. Automation
must never take, request, or facilitate any action that changes the management, compliance,
identity or trust status of this machine.

**PRIV-002** This boundary applies to automation, to scripts, to CI, to documentation
recommendations, and to any suggestion the agent makes to the operator. Suggesting a crossing is
itself a violation.

**PRIV-003** The boundary is owner-vetoed (`GOV-082`). No release, no feature request and no
Conditional Access requirement overrides it.

---

## 2. Prohibited enrolment and device-trust actions

**PRIV-010** The following are **absolutely prohibited**, automatically or semi-automatically:

| # | Prohibited action |
| --- | --- |
| 1 | Enrolling the machine in **Microsoft Intune** |
| 2 | Installing, launching or completing **Company Portal** enrolment |
| 3 | Installing or invoking **Microsoft Identity Broker** / `microsoft-identity-broker` |
| 4 | Performing **Entra ID (Azure AD) device registration**, join, or hybrid join |
| 5 | Enrolling in any **MDM** or UEM (Workspace ONE, Jamf, Kandji, or equivalent) |
| 6 | Installing or enabling **corporate EDR/XDR** agents |
| 7 | Installing **device certificates**, corporate root CAs, or client authentication certificates |
| 8 | Registering the machine as **compliant**, **managed**, **trusted** or **hybrid-joined** |
| 9 | Installing corporate configuration profiles, compliance agents or management daemons |
| 10 | Enabling WAM / SSO broker integration that registers the device with the tenant |

**PRIV-011** Prohibited both inside containers and on the host. A container is not a loophole:
device registration performed from a container still binds the operator's identity and, where the
host is exposed, the host itself.

**PRIV-012** The agent must not install packages whose purpose is device management, enrolment or
broker-based device identity, and must not recommend them as a fix.

---

## 3. Conditional Access

**PRIV-020 — Terminal blocker.** If Microsoft Conditional Access requires a **compliant** or
**managed/registered** device, the system returns `BLOCKER_CONDITIONAL_ACCESS` and **stops**. The
operation is reported as blocked. This is a correct, expected outcome — not a bug to be worked
around.

**PRIV-021 — No bypass.** No alternative authentication path, no retry loop, no different browser,
no different endpoint and no attempt to satisfy the policy by changing the device's state.

**PRIV-022 — No spoofing.** Prohibited: user-agent spoofing to impersonate a managed platform,
faking device identifiers, injecting device-claim tokens, replaying device claims, tampering with
TLS client certificates, or any technique intended to make an unmanaged device appear managed.

**PRIV-023 — No credential relocation.** Moving the sign-in to another (managed) machine and
transporting the resulting cookies/profile back is prohibited: it defeats the tenant's control
and creates a portable session credential.

**PRIV-024 — Report, do not diagnose around it.** The correct response to
`BLOCKER_CONDITIONAL_ACCESS` is a clear report to the operator stating that tenant policy requires
a managed device and that this deployment is, by design, unmanaged. The resolution path is
organisational (policy exception, or a different execution model), never technical evasion.

**PRIV-025** `BLOCKER_CONDITIONAL_ACCESS` is recorded as an audit event (`GOV-111`) with no
identity material.

---

## 4. Browser profile isolation

**PRIV-030 — Dedicated professional profile.** The Chromium profile used by the worker is created
exclusively for Planner work, lives only in the worker's named volume
(`browser-profile:/var/lib/planner-worker/profile`), and is owned by the worker container only
(`ARCH-013`, `SEC-108`).

**PRIV-031 — Never reuse a personal profile.** The worker must never open, read, copy, import
from, or point at: the operator's personal Chrome/Chromium/Edge/Firefox profile directories,
their cookie stores, their password stores, their bookmarks, their history, or their extensions.

**PRIV-032 — No personal browsing in the professional profile.** The professional profile is used
only for the Planner Premium surface and its authentication flow.

**PRIV-033 — No extensions.** No browser extensions are installed into the professional profile.

**PRIV-034 — No profile export.** The profile is never copied out of its volume — not for
debugging, not for backup, not for migration, not into an artifact, not into the repository, not
into a log. `profiles/` is git-ignored; that is a safety net, not the control.

**PRIV-035 — Profile lifecycle.** Profile creation, re-authentication and destruction are explicit
operator actions. Destruction is the correct response to suspected session compromise.

**PRIV-036 — Single tenant per profile.** A profile is bound to one professional account. Mixing
accounts in one profile creates tenant/account confusion (`THR-053`).

---

## 5. Prohibited mounts and data paths

**PRIV-050 — Prohibited container mounts.** No container in this project may mount:

| # | Prohibited mount |
| --- | --- |
| 1 | The host Docker socket (`/var/run/docker.sock`) |
| 2 | The host home directory (`$HOME`, `/home/*`) or any subtree of it |
| 3 | Any personal browser profile directory (`~/.config/google-chrome`, `~/.config/chromium`, `~/.mozilla`, `~/Library/Application Support/...`) |
| 4 | Personal document, photo, download or desktop directories |
| 5 | SSH keys, GPG keys, cloud credentials (`~/.ssh`, `~/.gnupg`, `~/.aws`, `~/.config/gcloud`, `~/.kube`) |
| 6 | The operator's password manager or keyring stores |
| 7 | Host system paths (`/etc`, `/var/lib/dpkg`, `/proc` beyond default, `/sys`) beyond container defaults |
| 8 | Any Hermes profile directory, Hermes secrets directory or Hermes state |
| 9 | Corporate device-management state or certificate stores |

**PRIV-051** Permitted volumes are exactly two, both named and single-owner: `browser-profile`
(worker) and `mcp-state` (control plane).

**PRIV-052** Bind-mounting a host path for convenience or debugging is prohibited. Diagnostics are
obtained through logs, metrics and evidence, all of which are redacted.

**PRIV-053** The worker has no access to the control plane's state volume, and the control plane
has no access to the profile volume.

---

## 6. Data handling and retention

**PRIV-060 — Retention rules.**

| Data | Where | Retention |
| --- | --- | --- |
| Planner content | not persisted in the current release | n/a; any future cache requires an ADR, a retention rule and a privacy review (`ARCH-063`) |
| Control metadata (`resource`, `idempotency`, `saga`, `checkpoint`) | `mcp-state` | bounded, pruned once the operation is complete and beyond its dispute window |
| Approvals | `mcp-state` | retained for the audit window, then pruned; consumed approvals are never revived |
| Audit events | `mcp-state` | retained for the audit window; append-only |
| Evidence records | `mcp-state` / artifacts | retained while they back a capability claim; redacted at write time |
| Operational logs | log sink | short, bounded retention; redacted at emission |
| Metrics | metrics sink | aggregate only, low cardinality, no identifiers |
| Browser profile | `browser-profile` volume | lives as long as the professional session; destroyed on decommission or suspected compromise |

**PRIV-061 — Minimisation.** Only data required to make the next correct decision is stored.
"Might be useful later" is not a retention justification.

**PRIV-062 — Redaction at write time.** Personal identifiers, e-mail addresses, user IDs, tenant
identifiers, JWTs and bearer tokens are redacted before anything is written (`SEC-050`).

**PRIV-063 — Sanitized identity only.** The only identity-adjacent fields exposed are
`tenant_display`, `account_kind`, `profile` and `device_enrolment`. Raw identity is never exposed
through the MCP surface, Hermes, logs or evidence.

**PRIV-064 — No authenticated screenshots.** Screenshots of authenticated content are never
captured as evidence (`ARCH-103`). Where a visual artefact is unavoidable for drift diagnosis, it
must be produced manually by the operator, outside the automated evidence path, and never
committed.

**PRIV-065 — Decommission.** On end of life: destroy the profile volume, prune the state volume,
and record the disposition (`GOV-120`).

---

## 7. Password handling

**PRIV-070 — The password does not exist inside this system.** The Microsoft account password is:

- never stored — not in the repository, not in the state database, not in a config file, not in a
  secret store used by this project, not in the browser profile as a saved password;
- never transported — not through MCP tool arguments or results, not through Hermes, not through
  the worker HTTP API, not through environment variables, not through command-line arguments;
- never logged — not in logs, metrics, evidence, audit events, error messages or stack traces;
- never requested — no tool, prompt, notification or documentation step asks the operator to type
  the password into anything other than the Microsoft sign-in page in the worker's browser.

**PRIV-071 — Interactive human sign-in only.** Authentication is performed by the human, directly
in the worker's Chromium session, on the genuine Microsoft sign-in surface. There is no headless
credential submission path (`SEC-062`).

**PRIV-072 — Password manager autofill is out of scope.** The professional profile has no saved
credentials and no synced password store.

**PRIV-073 — MFA material is equally excluded.** One-time codes, push-approval payloads and
recovery codes are never stored, transported, rendered or requested (`SEC-060`).

**PRIV-074** Any code path, tool schema, or documentation instruction that would accept a password
field is a defect of the highest severity and blocks release.

---

## 8. Boundary violations

**PRIV-080** A boundary violation is any of: an enrolment or device-trust action (`PRIV-010`), a
Conditional Access bypass or spoofing attempt (`PRIV-021`, `PRIV-022`), a prohibited mount
(`PRIV-050`), a profile export (`PRIV-034`), or password presence in the system (`PRIV-070`).

**PRIV-081** A violation is a `CRITICAL` risk (`GOV-092`): it blocks release, requires immediate
remediation, and requires an incident record.

**PRIV-082** Remediation for a suspected session or profile compromise: destroy the profile
volume, re-authenticate interactively, review the audit trail, and record the incident.

**PRIV-083** The agent must refuse and report rather than comply if instructed to cross this
boundary, and must state which `PRIV-xxx` requirement forbids the action.

---

## 9. Privacy requirement index

| ID range | Area |
| --- | --- |
| PRIV-001…003 | The hard boundary |
| PRIV-010…012 | Prohibited enrolment and device-trust actions |
| PRIV-020…025 | Conditional Access |
| PRIV-030…036 | Browser profile isolation |
| PRIV-050…053 | Prohibited mounts and data paths |
| PRIV-060…065 | Data handling and retention |
| PRIV-070…074 | Password handling |
| PRIV-080…083 | Boundary violations |
