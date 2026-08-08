# ADR-004 — Human in the loop for authentication and MFA

- Status: Accepted
- Date: 2026-08-08

## Context

Planner MCP operates a browser session against a corporate Microsoft tenant. Automating credential
entry, persisting the Microsoft password or moving MFA approval into the automation channel would
collapse the authentication trust boundary and create unacceptable credential/phishing risk.

## Decision

1. **The Microsoft password never enters Planner MCP.** It is not stored in the repository,
   environment, configuration, state DB, Hermes, logs, evidence or tool payloads.
2. **Authentication is interactive in the dedicated professional Chromium profile.** The human
   performs credential entry directly in the browser; the worker observes authentication state.
3. **MFA approval occurs exclusively in Microsoft Authenticator.** The system may detect number
   matching and emit a sanitized event containing only the approved fields (`mfa_number`,
   `operation_id`, `service`, sanitized `description`, `expiry`).
4. Telegram, Hermes, ChatGPT and Planner MCP never expose an MFA-approval action.
5. Authentication follows the formal state machine documented in
   [`authentication-and-mfa.md`](../authentication-and-mfa.md).
6. `AUTHENTICATED` requires positive browser evidence, not merely absence of the login form.
7. Authentication/MFA attempts are not blindly auto-retried.
8. Conditional Access requiring a managed/compliant/enrolled/certificate-backed device results in
   `BLOCKER_CONDITIONAL_ACCESS` with no spoofing/bypass.
9. Intune/Company Portal/Identity Broker/Entra registration/MDM/EDR/device-certificate enrolment is
   never automatically accepted on the personal computer; see ADR-007.

## Consequences

- session expiry may require human re-authentication;
- unattended operation cannot override Microsoft authentication controls;
- the professional browser profile can preserve the authenticated browser session between normal
  worker restarts without exporting credentials/session material;
- the MFA notification is deliberately informational and non-actionable;
- no password-retry storm/account-lockout path exists inside the system.

## Security boundary

The profile is sensitive state but is not a password/token database owned by Planner MCP. It remains
inside the dedicated browser-worker profile boundary and is not copied into control-plane state,
logs, evidence, Hermes or another browser/device.

## Related

ADR-002, ADR-007;
[`authentication-and-mfa.md`](../authentication-and-mfa.md),
[`privacy-boundary.md`](../privacy-boundary.md),
[`hermes-integration.md`](../hermes-integration.md); backlog P-018..P-023.
