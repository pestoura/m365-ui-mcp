# OUT-002 — Outlook mock UI/test fixture foundation

Status: **IMPLEMENTED_AWAITING_CURRENT_BASE_GATES**

## Objective

Create deterministic synthetic test fixtures for the Outlook application boundary while keeping the application inactive.

## Implementation

`m365_mcp.apps.outlook.mock_ui` provides a versioned synthetic fixture with bounded folder keys and message metadata. The data is deterministic and explicitly synthetic.

## Integration boundary

OUT-001 is integrated. This clean OUT-002 branch starts directly from `main` at `3de1850ccbe067ae2c96d0cb0e5ff979f807afce`, replacing the stale stacked integration path.

Outlook remains `RESERVED`: no public Outlook tools, no worker activation, no mutation, and no live-support claim.

## Acceptance

Tests cover deterministic fixture output, bounded synthetic data, and continued absence of Outlook public-tool activation.

Merge only after fresh mandatory CI and Canonical documentation gates pass on this clean branch and the base `main` gates remain GREEN.
