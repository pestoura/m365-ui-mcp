# RB-M365-OUTLOOK-READ-001 — Outlook live read-only acceptance

Status: **PREPARED / LIVE UNOBSERVED**

Purpose: promote Outlook read capabilities only from controlled live browser evidence while preserving the current `RESERVED` application state until every required gate is satisfied.

This runbook does **not** claim that a live Microsoft 365 session has been observed. Repository/mock success is recorded separately from live acceptance.

## 1. Entry state

Required repository state before attempting a live campaign:

```text
M365 CORE               GREEN
PLANNER PARITY           GREEN
OUTLOOK READ MOCK        GREEN
OUTLOOK UICONTRACT       UNVERIFIED_LIVE
OUTLOOK APPLICATION      RESERVED
PUBLIC outlook_* TOOLS   ABSENT
```

The registered Outlook UI fragments are:

```text
outlook.account
outlook.mail-surface
outlook.calendar-surface
outlook.people-surface
outlook.todo-surface
outlook.settings-surface
```

Every locator value starts as `null`, every locator status starts as `UNVERIFIED_LIVE`, every fragment has `attested=false`, and no selector may be invented from repository knowledge.

## 2. Human/live prerequisites

A live attempt may require:

- the dedicated professional Microsoft 365 browser profile;
- successful Microsoft authentication;
- MFA/Authenticator interaction when requested;
- Conditional Access satisfaction;
- verified primary-mailbox/account context;
- controlled worker egress to the required Microsoft 365 surfaces;
- the target capability actually being present in the tenant.

If one of these cannot be satisfied, record the affected lane as `LIVE BLOCKED`. Do not weaken policy, bypass MFA/Conditional Access or convert the blocker into mock evidence.

## 3. Discovery campaign

Generate a digest-pinned `DISCOVERY` campaign for the Outlook fragments using `RB-M365-UI-ATTEST-001` tooling.

The live collector may record only sanitized structural observations. It must not persist or return:

- mailbox/calendar/contact/task content;
- raw DOM or authenticated screenshots;
- cookies, tokens or browser storage state;
- tenant/account identifiers;
- raw authenticated URLs;
- arbitrary CSS, XPath or JavaScript supplied by a caller.

A locator that cannot yet be represented by the typed contract stays `REVIEW_REQUIRED`. It is not guessed.

## 4. Capability-scoped READ acceptance

The initial candidate mapping is:

| Fragment | Candidate capability | Shell contract |
| --- | --- | --- |
| `outlook.mail-surface` | `mail.read` | `outlook.shell.mail` |
| `outlook.calendar-surface` | `calendar.read` | `outlook.shell.calendar` |
| `outlook.people-surface` | `people.read` | `outlook.shell.people` |
| `outlook.todo-surface` | `todo.read` | `outlook.shell.todo` |
| `outlook.settings-surface` | `settings.read` | `outlook.shell.settings` |

Each capability is evaluated independently. A blocker or drift in one fragment must not promote, demote or hide unrelated fragments without evidence.

For a capability to move beyond `LIVE UNOBSERVED`, all applicable UI attestation conditions must pass and the semantic read probe must produce:

```text
read_probe_ok = true
```

The probe output used as evidence is structural/sanitized only. Tenant content is not retained.

## 5. Promotion rules

Allowed state progression:

```text
IMPLEMENTED MOCK
      ↓
MOCK GREEN
      ↓
LIVE UNOBSERVED
      ↓
DISCOVERY OBSERVED
      ↓
READ ATTESTED
      ↓
SUPPORTED LIVE
```

A capability may not skip a stage merely because adjacent Outlook features were observed.

`SUPPORTED LIVE` additionally requires that the effective capability projection, account context, runtime health and policy agree with the evidence-backed state.

## 6. Failure and blocker handling

Use these explicit outcomes:

```text
MOCK GREEN
LIVE UNOBSERVED
LIVE BLOCKED
LIVE SUPPORTED
```

Examples of `LIVE BLOCKED`:

- authentication/MFA unavailable;
- Conditional Access refusal;
- wrong or ambiguous professional account context;
- required surface absent in the tenant;
- live worker egress unavailable;
- locator/structure is ambiguous;
- semantic read probe cannot be proven.

Do not retry authentication failures in an uncontrolled loop.

## 7. Mutation boundary

This runbook is read-only. It must not execute `OUT-030+` mutations.

Synthetic safe-write implementations may continue through repository CI, but production/live promotion requires the separate mutation acceptance path with policy, approval where required, idempotency, typed locks, read-back, result verification, provenance and compensation/uncertainty handling.

If a live mutation cannot prove final Microsoft state, its terminal outcome is `INDETERMINATE`, never assumed success.

## 8. Acceptance record

A completed live-read baseline must identify, without tenant content:

- exact repository/main SHA;
- exact UIContractSet digest;
- exact fragment/version;
- capability key;
- sanitized evidence digest;
- observation time;
- account-context verification result;
- semantic read-probe result;
- final capability state;
- blocker code when not supported.

Until such a record exists for Outlook, the canonical project state remains:

```text
OUTLOOK READ REPOSITORY/MOCK = GREEN
OUTLOOK READ LIVE            = UNOBSERVED
OUTLOOK APPLICATION          = RESERVED
```
