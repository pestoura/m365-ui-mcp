# Fail closed on an unattested UIContract

- Status: Accepted
- Date: 2026-08-08

## Context
Fabricated selectors would produce silently wrong reads and, later, dangerous writes.

## Decision
Centralize selectors in a versioned UIContract; mark unverified entries UNVERIFIED_LIVE; raise UI_CONTRACT_UNATTESTED / UI_DRIFT in live mode.

## Consequences
Live mode is unusable until an attestation campaign runs. This is intentional and honest.
