# CORE-017 — UI drift lifecycle

## Decision

UI evidence now has a closed lifecycle independent of persistence:

```text
HEALTHY
STALE
DRIFTED
RE_ATTESTATION_REQUIRED
```

`CORE-017` owns deterministic lifecycle semantics and dependent-capability degradation. `CORE-018` remains responsible for persisting evidence metadata/digests; `CORE-020` will define evidence lifetime and automatic expiration/revalidation policy.

## Transition safety

A detected drift cannot jump directly back to `HEALTHY`. The accepted recovery path is:

```text
DRIFTED
  -> RE_ATTESTATION_REQUIRED
  -> HEALTHY
```

The final transition requires an explicit successful re-attestation event. Invalid shortcuts fail closed.

`STALE`, `DRIFTED` and `RE_ATTESTATION_REQUIRED` withdraw effective support only from capabilities that explicitly depend on the affected UIContract fragment. Unrelated fragments/applications remain independent.

## Promotion rule

A lifecycle overlay is degradation evidence, not authorization evidence. It can never promote an unattested fragment to `HEALTHY`; attempting to do so produces a fail-closed attestation result.

The static UIContract remains authoritative for explicit `DRIFTED` state. A runtime overlay cannot mask contract-recorded drift.

## Compatibility

- the shipped fragments remain unchanged and no live UI evidence is invented;
- current initially-unattested Planner capabilities remain `UNVERIFIED_LIVE`;
- all 17 public `planner_*` tools remain unchanged;
- all 11 Planner capability keys and 10 selectors remain unchanged;
- Outlook remains `RESERVED` with zero public capabilities/tools/selectors.

## Security boundary

Lifecycle inputs are semantic state only. They carry no tenant content, screenshots, cookies, tokens, storage state, account identifiers or arbitrary browser actions.

No persistence, real-tenant attestation, browser navigation or live Microsoft egress is introduced by this block.
