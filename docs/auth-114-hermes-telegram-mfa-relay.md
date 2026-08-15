# AUTH-114 — Hermes/Telegram MFA relay for canonical operator sign-in

Status: implementation-grade requirement and operator contract.

Related requirements: `AUTH-003`, `AUTH-004`, `AUTH-005`, `AUTH-040`, `AUTH-043`,
`AUTH-044`, `AUTH-045`, `AUTH-053`, `AUTH-103`, `AUTH-109`, `AUTH-110`, `AUTH-111`.

## Requirement

**AUTH-114 — Canonical post-submit MFA relay and completion.** After the fixed
operator credential submit succeeds, the canonical headless sign-in conductor
MUST poll only the loopback-only sanitized `/auth/bootstrap/observe` contract.
It MUST NOT report operator-run success until that observation reaches
`AUTHENTICATED`.

When observation reports `MFA_REQUIRED`, the conductor MAY relay the displayed
number through Hermes to the operator's configured Telegram home channel only
when all of the following are true:

- `mfa_ambiguous` is `false`;
- `mfa_number` is present;
- the value is exactly two ASCII decimal digits;
- the value has not already been notified during the current run.

The relay uses the existing Hermes outbound CLI and existing Hermes-owned
Telegram configuration:

```text
hermes send --to telegram --quiet --file -
```

The message body is supplied on stdin. The challenge number is therefore not
placed in process argv, and the M365 component never receives or reads the
Telegram bot token or home-channel configuration.

## Human approval boundary

The relay is notification-only. Hermes, Telegram, the M365 MCP, browser worker
and operator runner MUST NOT approve, select, answer, forward or otherwise
satisfy the Microsoft MFA challenge. The human operator performs the approval
only in Microsoft Authenticator. The runner merely observes the resulting state
transition.

## Fail-closed outcomes

The attempt stops without claiming authentication when any of these occur:

- ambiguous MFA observation;
- `MFA_REQUIRED` without a valid two-digit number;
- malformed or unreachable observation endpoint;
- Hermes/Telegram delivery failure;
- any unsupported post-submit authentication state;
- the bounded MFA observation window expires before `AUTHENTICATED`.

`UNKNOWN` and `WAITING_FOR_MFA` are observational transient states only and may
be polled within the bounded window. No number is fabricated for either state.
A genuinely new unique two-digit challenge observed later in the same bounded
attempt may be notified once; repeated observations of the same challenge are
deduplicated.

## Data minimisation

The Telegram notification contains only a fixed M365/Microsoft Authenticator
instruction and the sanitized displayed number. It MUST NOT contain username,
password, email address, UPN, tenant/account identifiers, cookies, tokens, URL,
DOM/page text or selector data.

## Runtime bounds

The canonical conductor uses a fixed maximum of 120 observations with a fixed
2-second interval (maximum nominal approval window: four minutes). These are
implementation constants rather than caller-controlled arguments, preserving a
bounded deterministic operator flow.

## Verification

Primary regression coverage is `tests/test_operator_auth_mfa_relay.py`, covering
unique relay, duplicate suppression, new-challenge handling, ambiguity/null or
invalid challenge rejection, malformed/transport failures, Telegram delivery
failure, `WAITING_FOR_MFA`, bounded timeout, unsupported-state rejection, stdin
transport and completion only on `AUTHENTICATED`.
