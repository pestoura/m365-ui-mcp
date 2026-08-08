# Privacy boundary — personal device

The host running planner-mcp is a **personal machine**. It must remain personal. This document is
normative (see ADR-008).

## Absolute prohibitions

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

## Isolation requirements

| Boundary | Requirement |
| --- | --- |
| Browser profile | A dedicated **professional** Chromium persistent profile, separate directory, never the operator's personal profile. |
| Profile data | Excluded from git, backups that leave the host, and evidence artifacts. |
| Filesystem | Profile directory permissions `0700`, owned by the runtime user. |
| Containers | No host home mount, no Docker socket, no bind mount of personal directories. |
| Network | Worker on an internal network; no public ingress to the browser zone. |
| Identity | No personal Microsoft/Google identity signed into the professional profile. |
| Sync | Chromium profile sync disabled. |

## Data minimisation

- Only project data needed to answer the current operation is extracted.
- No mailbox, Teams chat, OneDrive or SharePoint content is read.
- Screenshots/DOM snapshots are local evidence only, referenced by hash, never returned inline,
  never sent to Hermes or the MCP client.
- No telemetry field carries account UPN, tenant name, device identifiers or IPs.

## What Conditional Access means here

If tenant policy requires a managed/compliant device, the correct outcome is **blocked, not
enrolled**. `BLOCKER_CONDITIONAL_ACCESS` is a legitimate final answer. The remediation is an
organisational decision (e.g. a separate corporate-managed machine), never a technical bypass.

## Operator rules

1. Use the professional profile only for the tenant work this MCP performs.
2. Never approve an enrolment or device-registration prompt because automation surfaced it.
3. Never paste the Microsoft password into any tool, chat, config or terminal.
4. Approve MFA only in Microsoft Authenticator, and only when a sign-in was genuinely initiated.

## Verification

- P-013 asserts profile path isolation and permissions.
- P-023 asserts enrolment-prompt detection and refusal against the mock UI.
- P-062 asserts telemetry contains no prohibited fields.
- CI check: repository contains no reference to enrolment automation commands.
