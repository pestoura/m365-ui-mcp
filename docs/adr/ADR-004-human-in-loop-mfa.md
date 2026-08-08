# ADR-004 — Human in the loop for authentication and MFA

- Status: Accepted
- Date: 2026-08-08

## Context

The system must operate a corporate Microsoft tenant. Automating credential entry or brokering
MFA would mean holding the password, and would move the second factor's trust anchor from the
user's phone into an automated pipeline. That is both a security failure and a policy violation,
and it makes phishing through the automation channel trivially effective.

## Decision

1. **The Microsoft password never enters the system.** Not in the repo, env, config, MCP payloads,
   Hermes, logs, state DB or evidence. There is no code path that submits credentials.
2. **Authentication is interactive**, performed by the human directly in the persistent
   professional Chromium profile. The system opens the sign-in surface and then only *observes*.
3. **MFA approval happens exclusively in Microsoft Authenticator.** The system may detect number
   matching and surface a **sanitized event** containing only `operation_id`, `service`,
   `description`, `mfa_number`, `expires_at`. No approval control is ever offered in Telegram,
   Hermes, ChatGPT or a tool response.
4. Authentication has a **formal state machine** (`UNKNOWN`, `READY`, `AUTH_REQUIRED`,
   `MFA_REQUIRED`, `WAITING_FOR_MFA`, `AUTHENTICATED`, `SESSION_EXPIRED`, `AUTH_FAILED`).
   `AUTHENTICATED` is only asserted from a positive signal on the Planner surface.
5. Auth operations are **never auto-retried**. `AUTH_FAILED` and `BLOCKER_CONDITIONAL_ACCESS` are
   terminal for the attempt; the circuit opens.

## Consequences

- Unattended long-running automation is impossible across a session expiry. Accepted: a human
  re-authenticates, and the profile persists the session between restarts.
- The sanitized MFA event is deliberately not actionable — it is a nudge, not an approval channel.
  Operators are told to treat any out-of-band approval request as hostile.
- No account lockout risk from retry storms.

## Related

[docs/authentication-and-mfa.md](../authentication-and-mfa.md),
[docs/hermes-integration.md](../hermes-integration.md); backlog P-018..P-023; ADR-008.
