# CORE-022 — True liveness vs readiness

## Decision

The browser worker exposes two separate health semantics:

```text
/livez   -> process liveness only
/readyz  -> proven readiness for live Microsoft 365 work
```

Liveness intentionally does not include or imply readiness. A responsive ASGI process is not evidence that browser, profile, authenticated session, UI contract, capability broker, protocol or lock subsystems are viable.

## Live readiness gate

`/readyz` is fail closed and requires every signal simultaneously:

```text
browser_started == true
profile_usable == true
AuthState == AUTHENTICATED
ui_contract_attested == true
broker_viable == true
protocol_compatible == true
lock_viable == true
```

Any missing signal returns HTTP `503` with bounded reasons:

```text
BROWSER_NOT_STARTED
PROFILE_UNAVAILABLE
AUTH_NOT_AUTHENTICATED
UI_CONTRACT_UNATTESTED
BROKER_UNAVAILABLE
PROTOCOL_INCOMPATIBLE
LOCK_UNAVAILABLE
```

Only all-positive evidence returns HTTP `200` and `ready: true`. The projection contains no tenant/account identifiers, cookies, tokens, storage state, URLs or M365 content.

## Sequencing and fail-closed placeholders

CORE-022 defines the complete readiness contract before every subsystem is implemented. Later blocks become the canonical providers:

```text
CORE-023 -> broker viability
CORE-024 -> account/profile context enforcement
CORE-026 -> serialized executor / lock viability
CORE-029 -> protocol compatibility
```

Until those blocks prove their conditions, the corresponding default providers remain `false`. This is intentional: readiness cannot be manufactured from configuration, a profile directory or a responsive route.

Current Planner UI fragments also remain `UNVERIFIED_LIVE`, so UI attestation remains fail closed until real controlled evidence exists.

The existing `/health` route is retained only for compatibility during migration and is not the canonical live-readiness contract.

## Browser and profile signals

`browser_started` comes from the CORE-021 process-owned `PersistentBrowser.started` state; it is never inferred from mode or configuration.

`profile_usable` is a separate positive signal. Merely configuring a persistent profile path does not prove that the intended professional profile is usable or correct. CORE-024 will strengthen account-context enforcement without exporting account identity.

Mock mode launches no Chromium and therefore does not satisfy live readiness. CI can validate `/livez`, refusal behavior and injected positive fixtures without contacting Microsoft 365.

## Authentication

Only `AuthState.AUTHENTICATED` is accepted. `UNKNOWN`, `MFA_REQUIRED`, `CONDITIONAL_ACCESS_BLOCKED` and other states fail readiness. CORE-022 does not implement or bypass MFA/Conditional Access.

## Broker, protocol and lock viability

Each is an explicit signal rather than an assumption:

- broker viability proves a safe Session/Capability Broker can authorize the existing professional session without exporting secrets;
- protocol compatibility proves control-plane/worker contract compatibility;
- lock viability proves the worker can enforce its serialized profile-operation boundary.

Their later implementation order does not weaken CORE-022 because absent providers remain false.

## Security properties

- `/livez` cannot overclaim readiness;
- `/readyz` represents browser/profile/protocol/contract/lock subsystems plus auth/broker viability;
- absence is failure, never implicit support;
- no session secrets or tenant content are returned;
- no generic browser operation is introduced;
- no real tenant access occurs in CI;
- no Outlook capability is enabled;
- CORE-025 remains mandatory before automated live M365 egress.

## Acceptance coverage

`tests/test_worker_readiness.py` verifies deterministic reporting of every missing subsystem, all-positive readiness, liveness/readiness separation, default fail-closed behavior and a single negative subsystem keeping readiness failed.

## Compatibility

```text
17 planner_* public tools -> PRESERVE
11 Planner capability keys -> preserved
10 historical selector keys -> preserved
Outlook -> RESERVED / zero public tools
```

## Next gate

```text
CORE-022 PR + post-merge main GREEN
    ↓
CORE-023 Session/Capability Broker
```
