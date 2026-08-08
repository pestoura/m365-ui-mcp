# Never enrol the personal machine

- Status: Accepted
- Date: 2026-08-08

## Context
Conditional Access may demand a compliant/managed device.

## Decision
Forbid Intune/Company Portal/Identity Broker/Entra registration/MDM/EDR/device certificates. Detect and raise BLOCKER_CONDITIONAL_ACCESS. Never bypass or spoof.

## Consequences
Some tenants will be unreachable. That is reported as a blocker, not worked around.
