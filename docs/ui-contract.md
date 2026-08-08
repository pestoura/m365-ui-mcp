# UIContract

The UIContract is the single, centralized, versioned description of the Planner Premium UI surface,
stored under `contracts/ui_contract.json` and packaged with the wheel (`browser/selectors` domain).

## Rules
- Selectors are **never fabricated**. Unverified entries carry `status: UNVERIFIED_LIVE` and a `null` value.
- Live operations against an unattested contract fail closed with `UI_CONTRACT_UNATTESTED`.
- A version mismatch between worker and control plane fails closed with `UI_DRIFT`.
- CI uses only the mock UI; it never touches real Planner.

## Current status
`ui_contract_version = 0.1.0`, `attested = false`, all selectors `UNVERIFIED_LIVE`.
Attestation is delivered by `P-045` / `P-050` in a separate live read-only campaign.
