# Security Policy

## Reporting a vulnerability

This is a private repository. Report security issues privately to the maintainer
(@pestoura) via a private channel or a GitHub security advisory on this repository.
**Do not open a public issue.**

When reporting, **never attach**: passwords, cookies, tokens, session identifiers, screenshots of
the tenant, DOM dumps, account UPNs/emails, tenant names, or any customer/project data. Describe
the issue structurally and reference file paths and code, not captured secrets.

Expect an acknowledgement within a few working days. Fixes for CRITICAL/HIGH issues are handled as
hotfixes under the normal gate model ([docs/release-process.md](docs/release-process.md)).

## Security model

The full model is documented in:

- [docs/security.md](docs/security.md) — normative `SEC-*` controls
- [docs/threat-model.md](docs/threat-model.md) — STRIDE analysis per trust boundary
- [docs/privacy-boundary.md](docs/privacy-boundary.md) — personal-device boundary
- [docs/authentication-and-mfa.md](docs/authentication-and-mfa.md) — auth and MFA handling
- [docs/governance.md](docs/governance.md) — policy, approvals, mutation classes

## Non-negotiable invariants

1. The Microsoft password never enters this system in any form.
2. MFA is approved only in Microsoft Authenticator — never via Hermes, Telegram, ChatGPT or a tool
   response.
3. No automatic enrolment of the host into Intune, Company Portal, Identity Broker, Entra device
   registration, MDM, corporate EDR or device certificates.
4. Conditional Access requiring a compliant/managed device ⇒ fail closed with
   `BLOCKER_CONDITIONAL_ACCESS`. Bypass, spoofing or emulation of compliance is prohibited.
5. UI drift, unattested selectors, ambiguous sessions or policy uncertainty ⇒ fail closed.
6. No secrets, tokens, cookies or session identifiers in logs, metrics, responses or telemetry.
7. CI never contacts or mutates a live tenant.

## Out-of-scope contributions

Pull requests that bypass device compliance, automate credential entry, extract session material,
expose raw browser navigation as an MCP tool, or weaken a `SEC-*` control without an accompanying
ADR and maintainer sign-off will be rejected.

## Supported versions

Pre-1.0: only the latest tagged version is supported.
