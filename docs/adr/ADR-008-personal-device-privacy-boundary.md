# ADR-008 — Personal device privacy boundary

- Status: Accepted
- Date: 2026-08-08

## Context

planner-mcp runs on the operator's **personal machine** while accessing a corporate tenant. Signing
into corporate resources on Linux commonly nudges the user toward Microsoft Identity Broker,
Company Portal, Intune enrolment, Entra device registration or device certificates. Those steps are
effectively irreversible in terms of management surface: they hand the tenant control over a
personal device. Conditional Access policies frequently push exactly in that direction.

## Decision

The personal device stays personal. The system MUST NEVER, automatically or as a side effect:

- enrol in Intune or Company Portal;
- install or register with Microsoft Identity Broker or equivalent;
- perform Entra device registration, hybrid join or Azure AD join;
- accept MDM management or install corporate EDR/antivirus;
- request, provision or store a corporate device certificate;
- install corporate root CAs into the host or browser trust store;
- enable OS-level "work or school account" integration.

Any UI path leading to these is a **fail-closed decision point** (`BLOCKER_ENROLMENT_PROMPT`), not
a step to automate. The worker detects and stops; a human decides, outside the automation.

If Conditional Access requires a compliant or managed device, the correct and **final** outcome is
`BLOCKER_CONDITIONAL_ACCESS`. Bypass, spoofing or emulation of device compliance is prohibited and
is not an acceptable contribution.

Isolation is mandatory: a dedicated professional Chromium profile in its own directory (`0700`,
non-root runtime user), sync disabled, no personal identity signed in, excluded from git and from
off-host backup; containers with no host home mount and no Docker socket; the browser zone with no
public ingress.

## Consequences

- Some tenants will simply be unreachable from this machine. That is an accepted, honest outcome;
  the remedy is organisational (e.g. a separate managed device), never technical.
- Startup asserts profile path and permissions and refuses otherwise (P-013).
- A CI gate rejects references to enrolment automation, and tests assert the refusal path (P-023).
- Telemetry and evidence rules keep device and account identifiers out of logs, metrics and Hermes.

## Related

[docs/privacy-boundary.md](../privacy-boundary.md),
[docs/authentication-and-mfa.md](../authentication-and-mfa.md),
[docs/threat-model.md](../threat-model.md); ADR-002, ADR-004; backlog P-013, P-021, P-023.
