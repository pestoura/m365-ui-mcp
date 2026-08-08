# CORE-015 — UI contract-set digest

## Decision

Every validated UI contract set now has a deterministic SHA-256 identity:

```text
sha256:<64 lowercase hexadecimal characters>
```

The digest identifies the exact semantic contract configuration used by control-plane and browser-worker status surfaces. It is an identity/evidence correlation primitive; it is **not** an attestation, authorization decision or proof that a live UI is healthy.

## Canonical content

The digest covers:

- UI contract-set version;
- legacy compatibility version;
- manifest fragment order;
- fragment identity and version;
- structural scope, application and surface bindings;
- explicit capability dependencies;
- fragment attestation state;
- selector names, values and selector attestation state.

Canonical JSON uses UTF-8, compact separators and sorted mapping keys. Mapping-key order therefore does not change the digest, while the manifest fragment list order remains significant.

## Exclusions

The digest payload does not include:

- absolute filesystem paths;
- runtime timestamps;
- tenant/account/user identifiers;
- browser profile/session IDs;
- cookies or tokens;
- authentication secrets;
- runtime process or host metadata.

Only repository contract content participates in the digest.

## Exposure

The same digest is exposed through:

- `planner_ui_contract_status` / `UiContractStatus`;
- Planner capability evidence output;
- browser-worker `/health`.

This allows later execution evidence to identify the exact contract set without exporting raw selector documents or session state.

## Boundary

CORE-015 introduces deterministic identity only. It does not yet change locator selection, drift lifecycle or evidence persistence. Those remain CORE-016, CORE-017 and CORE-018 respectively.
