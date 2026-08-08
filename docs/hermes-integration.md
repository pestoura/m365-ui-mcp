# Hermes integration

Hermes is **not** the browser execution layer and never drives Chromium for this system.

Hermes responsibilities:
- Notifications about auth state changes and blockers (sanitized only).
- Human-in-the-loop orchestration for future approval-gated mutations.

Hermes must never be used to approve MFA. MFA approval happens only in Microsoft Authenticator.
Payloads sent to Hermes are redacted and contain no credentials, cookies or tokens.
