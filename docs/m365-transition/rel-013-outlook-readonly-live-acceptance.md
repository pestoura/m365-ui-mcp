# REL-013 — Outlook read-only live acceptance

## Status

Repository-side harness implemented. LIVE acceptance remains unobserved until an
explicitly controlled authenticated Outlook Web run supplies valid sanitized
`LIVE_UI` evidence. This document does not claim `SUPPORTED_LIVE`.

## Purpose

REL-013 establishes the narrow acceptance boundary for the first Outlook LIVE
capability: `mail.read` on the professional primary mailbox surface. It composes
existing account-context, primary-mailbox, UI attestation and REL-025 promotion
primitives; it does not create a second support registry or evidence store.

## Allowed evidence

The boundary accepts only content-free objects already validated by the control
plane:

- `AccountContext` must be `VERIFIED`, professional and the expected profile;
- `PrimaryMailboxContext` must be `VERIFIED` for the primary shell;
- `AttestationObservation` must be `LIVE_UI`, target `READ`, and have a confirmed
  read probe;
- `AttestationDecision` must be `PASSED`, `HEALTHY`, bound to the same fragment,
  fragment version, contract-set digest, evidence digest and timestamp;
- required gates are `REL-004`, `REL-007`, `REL-011`, account-context,
  mailbox-context and read-probe gates.

The resulting object is only REL-025 input. REL-025 remains responsible for the
final support-state decision and evidence freshness/environment checks.

## Data minimisation

REL-013 evidence must never contain mailbox address, UPN, tenant identifier,
message subject/body, attachment content, DOM, authenticated URL, cookie, token
or browser-session material. Identity is represented only by bounded verification
state; UI evidence is represented by digests and gate identifiers.

## Explicitly forbidden

- Microsoft Graph or any other API-surface substitution;
- generic public browser primitives;
- draft/send/archive/delete/category/calendar or other mutation evidence;
- calendar LIVE acceptance, which belongs to REL-016;
- converting MOCK/SYNTHETIC evidence into LIVE evidence;
- enabling Outlook public MCP tools as a side effect of this harness.

## LIVE execution gate

A real REL-013 acceptance run requires an authenticated professional Outlook Web
session in the expected tenant/profile. The controlled runner must perform only
bounded read-only shell and mailbox observations, sanitize them before evidence
persistence, and submit the resulting `LIVE_UI` attestation through this boundary.

If authentication is unavailable, account/tenant context is ambiguous, MFA is
required, the UIContract has drifted, a required gate is missing, or any mutation
would be necessary, execution stops fail-closed. Repository tests using fixtures
may validate the harness but cannot satisfy this LIVE gate.

## Acceptance state

Until that real run succeeds, Outlook remains `RESERVED / LIVE_UNOBSERVED` and
issue #588 remains open. No repository-only GREEN result may be represented as a
LIVE tenant attestation.
