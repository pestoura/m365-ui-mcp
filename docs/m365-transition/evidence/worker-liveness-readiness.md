# CORE-022 — True liveness vs readiness

## Decision

The browser worker now exposes two separate health semantics:

```text
/livez   -> process liveness only
/readyz  -> proven readiness for live Microsoft 365 work
```

Liveness intentionally does not include or imply a `ready` field. A running ASGI process is not evidence that the browser, authenticated session, UI contract or capability broker is usable.

## Live readiness gate

`/readyz` is fail closed and requires all four signals simultaneously:

```text
browser_started == true
AuthState == AUTHENTICATED
ui_contract_attested == true
broker_viable == true
```

If any signal is missing, the endpoint returns HTTP `503` with bounded reason codes:

```text
BROWSER_NOT_STARTED
AUTH_NOT_AUTHENTICATED
UI_CONTRACT_UNATTESTED
BROKER_UNAVAILABLE
```

Only when all four are proven does `/readyz` return HTTP `200` and `ready: true`.

The projection contains no tenant identifiers, account identifiers, cookies, tokens, storage state, URLs or mailbox/calendar/contact content.

## Current operational state

`CORE-022` does not pretend the next block already exists. Until `CORE-023` wires the Session/Capability Broker, the default broker viability provider is `false`. Therefore the current worker cannot accidentally claim live readiness merely because Chromium is running.

Likewise, current Planner UI fragments remain `UNVERIFIED_LIVE`, so the UI contract signal remains fail closed until real controlled attestation evidence exists.

The existing `/health` route is retained for backward compatibility during migration; it is not promoted to the canonical live-readiness contract. Docker/process liveness remains separate from semantic M365 readiness.

## Browser ownership

`browser_started` comes from the `CORE-021` process-owned `PersistentBrowser.started` state. It is not inferred from configuration, mode or the presence of a profile directory.

Mock mode deliberately launches no Chromium, so it does not satisfy live readiness. CI can still validate `/livez`, `/readyz` refusal behavior and injected positive fixtures without touching Microsoft 365.

## Authentication

Readiness accepts only the closed `AuthState.AUTHENTICATED` value. `UNKNOWN`, `MFA_REQUIRED`, `CONDITIONAL_ACCESS_BLOCKED` and all other non-authenticated states fail readiness.

`CORE-022` does not implement or bypass MFA/Conditional Access; those remain human/policy boundaries.

## Broker viability

Broker viability is an explicit signal, not an assumption based on a responsive HTTP process. `CORE-023` owns the Session/Capability Broker implementation and will become the canonical provider for this signal.

This sequencing deliberately means:

```text
CORE-022 before CORE-023
    -> readiness model exists
    -> default broker viability = false
    -> no premature live-ready claim
```

## Security properties

- `/livez` cannot overclaim readiness;
- `/readyz` requires four independent positive signals;
- absence is failure, not implicit support;
- no session secrets are returned;
- no generic browser operation is introduced;
- no real tenant access occurs in CI;
- no Outlook capability is enabled;
- `CORE-025` remains mandatory before automated live M365 egress.

## Acceptance coverage

`tests/test_worker_readiness.py` verifies:

- all four negative signals are reported deterministically;
- all four positive signals are required for readiness;
- `/livez` remains healthy while default `/readyz` correctly returns `503`;
- `/livez` contains no readiness assertion;
- an injected fully proven state returns `/readyz` `200`;
- a single negative broker signal keeps readiness failed.

## Compatibility

No public MCP tool, Planner capability key or historical UI selector changes.

```text
17 planner_* public tools -> PRESERVE
11 Planner capability keys -> preserved
10 historical selector keys -> preserved
Outlook -> RESERVED / zero public tools
```

## Next gate

After PR and post-merge `main` are GREEN:

```text
CORE-022 PASS
    ↓
CORE-023 Session/Capability Broker
```
