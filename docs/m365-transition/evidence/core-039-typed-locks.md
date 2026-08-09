# CORE-039 — Typed locks

Status: **INTEGRATED_ON_MAIN**

## Objective

Generalize the historical Planner-specific lock vocabulary into application-neutral profile, account, application, container and resource lock identities that can be used consistently by future cross-application execution.

## Closed lock hierarchy

`m365_mcp.typed_locks.LockScope` defines one deterministic broad-to-narrow ordering:

1. `PROFILE`
2. `ACCOUNT`
3. `APPLICATION`
4. `CONTAINER`
5. `RESOURCE`

Every `TypedLock` exposes a canonical `order_key`. `canonical_lock_order()` deduplicates lock identities and sorts them using this hierarchy plus the stable lock digest, giving callers one global acquisition order and avoiding application-specific lock ordering conventions.

## Lock identities

The model supports:

- **profile lock** — bound to an opaque profile key digest; raw profile path/name is not retained;
- **account lock** — bound to an opaque account assertion key digest;
- **application lock** — bound to account + closed `ApplicationKey`;
- **container lock** — bound to account + application + CORE-037 container `StateIdentity` digest;
- **resource lock** — bound to account + application + CORE-037 resource `StateIdentity` digest.

Container/resource constructors reject an account-level `StateIdentity` and derive the application directly from the state identity, preventing mismatched application/resource lock metadata.

## Cross-scope separation

The canonical lock key hashes the complete bounded lock payload. Consequently:

- Planner and Outlook application locks for the same account are distinct;
- identical resources under different containers are distinct because CORE-037 state identity is container-aware;
- identical state identities under different account assertions are distinct;
- profile/account/application/container/resource levels cannot silently collapse into one lock key.

## Planner compatibility

The current legacy Planner vocabulary is:

```text
PLAN
TASK
BUCKET
SESSION
BROWSER_PROFILE
```

`legacy_planner_lock_scope()` provides a one-way string-only mapping without importing the legacy Planner package into generic M365 core:

```text
browser_profile -> PROFILE
session         -> ACCOUNT
plan            -> CONTAINER
bucket          -> RESOURCE
task            -> RESOURCE
```

The legacy runtime remains unchanged in CORE-039. A later Planner migration phase can adopt the generalized identities explicitly rather than changing existing locking behavior implicitly.

## Security/privacy boundary

Opaque profile/account inputs are immediately SHA-256-normalized. The typed lock model does not retain browser profile paths, account emails, mailbox addresses, tenant content, raw Microsoft resource identifiers, cookies, tokens or storage state.

## Acceptance coverage

Tests prove:

- raw opaque account/profile keys are not projected;
- Planner/Outlook application locks are separate;
- container/resource locks bind CORE-037 state identity;
- same resource under different parent containers is distinct;
- same state under different account assertions is distinct;
- broad-to-narrow acquisition order is deterministic and duplicate-free;
- account-level state cannot be misused as container/resource lock identity;
- every historical Planner lock type has an explicit compatibility mapping and unknown values fail closed.

## Current integration gate

CORE-038 is merged and post-merge GREEN on `main` at `a7178b3417c0907e66388115742443739b2e017e`. PR #263 is now based directly on that integration point. This revision deliberately re-triggers every mandatory CI/security/image/Trivy/SBOM/documentation gate; stacked-branch evidence is not reused for merge.

## Integration reconciliation

This requirement's delta is present in `main`. The mandatory CI gate set (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) was GREEN on the merged pull request, and the full gate set was re-executed on post-merge `main` at `9b4a645`.

Mock mode only: no live Microsoft tenant was contacted, no capability is promoted to SUPPORTED by this record, Outlook stays RESERVED, and the 17-tool Planner public ABI is unchanged.
