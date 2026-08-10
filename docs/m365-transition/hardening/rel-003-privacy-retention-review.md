# REL-003 — Privacy and data-retention review

## Purpose

This review defines data-minimization and retention rules for mailbox, calendar, contact, task and browser-session data processed by the M365 UI MCP. It covers synthetic/isolated operation today and constrains any future LIVE Outlook acceptance. It does not itself promote LIVE support.

## Data classes and lifecycle

| Data class | Default handling | Durable evidence |
|---|---|---|
| Mail subject/body, recipients and message content | transient processing only; return only the minimum semantic projection required by the tool | opaque message key, outcome/state, bounded counters or digest when required; no body |
| Attachments and attachment content | do not persist by default; content remains outside evidence/logging | opaque attachment key and bounded metadata only when required |
| Calendar titles, attendee data and event content | transient processing; minimize returned fields to the semantic contract | opaque event/calendar key, state/read-back metadata, digest/counter where required |
| Contacts and directory identity data | transient semantic resolution; avoid raw addresses where an opaque key suffices | opaque person/contact key and low-cardinality attributes only |
| To Do / Planner content | semantic fields required by the operation; no unrelated tenant context | task/plan/project keys, lifecycle/read-back state and bounded evidence |
| Browser cookies, storage state and authenticated profile | browser-worker local only, scoped to the tenant/context profile | never copied to control-plane results, logs or generic evidence |
| Screenshots, traces and DOM/browser artifacts | disabled from ordinary evidence by default | controlled diagnostic capture only under an explicit future procedure; never a default retention path |
| Synthetic fixtures | repository/test data only with opaque identities | may be versioned when demonstrably identity-free and synthetic |

## Data-minimization rules

1. Prefer opaque semantic keys over addresses, URLs, tenant identifiers or UI internals.
2. Evidence stores low-cardinality state, hashes/digests, counters, timings and explicit read-back outcomes rather than business content.
3. Logs must not contain bodies, attachments, cookies, access tokens, storage state, raw selectors or browser handles.
4. Browser session/profile material must remain inside the browser-worker boundary and must not be replicated into control-plane persistence.
5. Read/search/context composites return only fields necessary for the declared semantic result.
6. Synthetic fixtures must not contain real tenant identities and must never be presented as LIVE observation.

## Retention and deletion responsibilities

- Transient business content exists only for the duration required to produce the semantic result and read-back; it is not a default evidence artifact.
- Browser profile/session state follows worker/profile lifecycle controls and is removed or invalidated when the scoped context is retired or re-attestation requires a new session.
- Evidence and observability records may outlive an operation only when they contain the minimized fields described above and are subject to the deployment retention policy.
- Diagnostic artifacts, if explicitly enabled in a future controlled procedure, require a defined owner, purpose, retention limit and deletion action before capture.
- Application-level delete operations do not imply deletion of unrelated evidence; evidence retention remains governed separately and must stay content-minimized.

## Privacy boundary for Outlook

Outlook remains `RESERVED`, with zero public Outlook tools and LIVE support `UNOBSERVED`. REL-013 and later live acceptance must demonstrate that these data-handling rules continue to hold against the real tenant UI before any live-support promotion.

## Review disposition

The current architecture is acceptable for synthetic/isolated acceptance provided the minimization rules remain enforced. Any future telemetry, screenshots, traces, persistent mailbox cache or cross-tenant profile reuse would require a new privacy review rather than inheriting this disposition.
