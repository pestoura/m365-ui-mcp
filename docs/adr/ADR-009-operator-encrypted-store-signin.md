# ADR-009 — Operator-only encrypted-store sign-in (supersedes "human types password")

- Status: Accepted
- Date: 2026-08-14

## Context

AUTH-001 originally required a human to type the Microsoft password interactively
in the worker's Chromium window. That rule protected the authentication trust
boundary by keeping the password out of Planner MCP entirely. Operationally, it
also forced a manual step on every operator re-authentication. The password is
already provisioned as two encrypted *systemd user* credentials in a fixed local
store under `~/.local/lib/credstore.encrypted`. The question is how to let the
operator authenticate without re-introducing the password into repository, env,
argv, logs, worker state, ChatGPT or Telegram, and without creating a generic
credential-flow or MFA-automation primitive.

## Decision

1. The "human types the password" rule (AUTH-001) is **superseded for the operator
   path** by local encrypted-store automation (AUTH-101). The interactive GUI
   handoff was **removed** (PR #614, archived in
   [`../archive/ADR-ARCHIVED-gui-vnc-handoff.md`](../archive/ADR-ARCHIVED-gui-vnc-handoff.md));
   there is no headed/graphical fallback. The pre-attestation email stage
   (AUTH-106) provides the headless-only path to the password surface for
   attestation.
2. A single operator-local script (`scripts/operator_auth_login.py`) decrypts the
   two provisioned systemd-creds secrets via `systemd-creds decrypt --user`, keeps
   them **memory-only**, and forwards them over a loopback `stdin`/IPC path to the
   narrowly-scoped operator-only `POST /auth/bootstrap/operator-submit` route.
3. The worker route applies ONLY the two `common.auth` sign-in fields
   (`auth.login_email_input`, `auth.login_password_input`) to the already-open
   Microsoft authentication page. No URL, generic DOM primitive, Graph surface or
   locator guessing is reachable. The values are never printed, logged, env-stored
   or state-stored.
4. `common.auth` MUST be attested before any sign-in field is applied; otherwise the
   worker fails closed and types nothing (no guessed selectors).
5. MFA approval stays Microsoft Authenticator-only. The operator submit route clicks
   the Microsoft "Next" control to advance from the email step and the Microsoft
   form "Sign in" control to finalize credential submission; neither carries
   credentials and neither is an MFA control. MFA approval remains exclusively
   human in Microsoft Authenticator and Telegram is notification-only.
6. Preserved invariants: no plaintext persistence, no environment variable, no argv,
   no ChatGPT, no Telegram credentials, and no public MCP exposure of the route (it
   is socket-loopback admitted only).

## Consequences

- Operator re-authentication no longer requires manually typing the password, while
  the password still never enters Planner MCP state, logs or tool payloads.
- The authentication trust boundary is preserved: credential values live only in the
  operator's process memory for one loopback call, and MFA remains human-approved.
- The GUI handoff path was **removed** (PR #614); the headless-only email stage
  (AUTH-106) is the supported pre-attestation path. There is no graphical fallback.
- `AUTHENTICATED` still requires positive browser evidence, not merely absence of the
  login form.

## Related

ADR-004; [`authentication-and-mfa.md`](../authentication-and-mfa.md) (AUTH-099,
AUTH-100, AUTH-101, AUTH-103, AUTH-104); [`hermes-integration.md`](../hermes-integration.md);
`scripts/operator_auth_login.py`; `src/m365_browser_worker/operator_signin.py`.
