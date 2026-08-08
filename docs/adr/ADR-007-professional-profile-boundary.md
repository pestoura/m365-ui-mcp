# ADR-007 — Dedicated professional profile and personal-device privacy boundary

- Status: Accepted
- Date: 2026-08-08

## Context

`planner-browser-worker` runs on the operator's personal computer while accessing a corporate Microsoft tenant. The solution needs a persistent professional Chromium profile for session continuity, but that requirement must not turn a personal device into a tenant-managed endpoint or expose personal browser/session material to the worker.

Corporate sign-in flows may present Microsoft Identity Broker, Company Portal, Intune enrolment, Entra device registration, MDM, device-certificate or other managed-device paths. Conditional Access may also require a managed/compliant/enrolled/certificate-backed device.

## Decision

The personal device stays personal and the professional browser profile is a deliberately isolated application boundary.

The system MUST NEVER automatically or as a side effect:

- enrol the computer in Intune or install Company Portal;
- install or use an Identity Broker to register the device;
- perform Entra Device Registration, Azure AD/Entra join or hybrid join;
- accept MDM enrolment or install corporate EDR/endpoint-management software;
- request, install or persist corporate device certificates on the host;
- change host operating-system policy to satisfy tenant controls;
- use or modify the operator's personal browser profile;
- copy tokens, cookies or session material from another browser or managed device;
- mount the operator's home, Docker socket, `.ssh`, `.gnupg`, `.aws` or Hermes directories into the worker.

The browser worker uses only a dedicated professional Chromium profile in an explicitly configured directory, owned by the non-root runtime identity and excluded from source control and telemetry. The profile is persistent only to support the browser session; it is not a credential export mechanism.

If an authentication path attempts device enrolment, the worker stops with a typed blocker such as `BLOCKER_ENROLMENT_PROMPT`. If Conditional Access requires a managed, compliant, enrolled or certificate-backed device, the final result is `BLOCKER_CONDITIONAL_ACCESS`.

Bypass is prohibited: no User-Agent spoofing to simulate compliance, no claim fabrication, no device-identity emulation and no export/reuse of a session from another managed device.

## Consequences

- Some tenants may be inaccessible from the personal computer. That is an accepted product outcome, not a defect to bypass.
- Authentication remains browser-mediated and human-in-loop where required.
- Container/runtime checks must enforce the host-mount and private-network boundary.
- Logs, metrics, evidence and Hermes notifications must not contain browser session secrets, tokens or personal profile material.

## Enforcement

- Startup validates the configured professional profile path and runtime ownership/permissions.
- Container definitions prohibit Docker socket, host-home and personal credential mounts.
- CI/security tests reject enrolment/bypass automation and unsafe host mounts.
- Conditional Access and enrolment prompts are tested as fail-closed scenarios in the mock/acceptance harness.

## Related

[docs/privacy-boundary.md](../privacy-boundary.md),
[docs/authentication-and-mfa.md](../authentication-and-mfa.md),
[docs/browser-worker.md](../browser-worker.md),
[docs/threat-model.md](../threat-model.md), [docs/vision.md](../vision.md);
ADR-002, ADR-004; backlog P-013, P-021, P-023.
