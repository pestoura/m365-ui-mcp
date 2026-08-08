# planner-mcp

`planner-mcp` is an MCP control plane for Microsoft Planner Premium backed by a private Playwright/Chromium browser worker.

## Release scope

Current product version: **0.1.0**.

The 0.1.0 contract is deliberately **read-only**:

- 17 MCP read tools;
- zero public mutation tools;
- Microsoft Graph is **not** used as the functional backend;
- browser capabilities are published only from attested UI evidence;
- live browser automation fails closed when the required UIContract fragment is not attested;
- Conditional Access, device-enrolment requirements and ambiguous authentication states are blockers, never bypassed;
- MFA remains human-in-the-loop; credentials and authenticator approval are not automated.

The default runtime mode is `mock`. CI and isolated acceptance must never contact a real Planner tenant.

## Architecture

The runtime is split into two trust zones:

1. **MCP control plane** — FastMCP over Streamable HTTP, contracts, policy, state, redaction, metrics and tool registration.
2. **Private browser worker** — FastAPI + Playwright/Chromium, isolated from direct MCP clients and restricted to typed operations.

The normative architecture, security model and browser evidence rules live in [`docs/`](docs/vision.md). The canonical ADR set is [`docs/adr/ADR-001..008`](docs/adr/).

## Development

Requirements: Python 3.12+.

```bash
python -m pip install -e ".[dev]"
python -m compileall -q src tests scripts
ruff check .
mypy
pytest -q
python scripts/check_docs.py
```

Run the control plane in the default mock mode:

```bash
planner-mcp
```

Run the browser worker separately:

```bash
planner-browser-worker
```

Container definitions are in [`docker/`](docker/) and [`docker-compose.yml`](docker-compose.yml). Base images are digest-pinned and CI blocks HIGH/CRITICAL Trivy findings, validates two CycloneDX SBOMs, performs secret/dependency scanning and runs isolated acceptance.

## Governance and release gates

A capability is not considered live-supported because code exists or a mock test passes. Promotion requires the evidence and attestation states defined in:

- [`docs/planner-premium-capabilities.md`](docs/planner-premium-capabilities.md)
- [`docs/ui-contract.md`](docs/ui-contract.md)
- [`docs/acceptance.md`](docs/acceptance.md)
- [`docs/definition-of-done.md`](docs/definition-of-done.md)
- [`docs/release-process.md`](docs/release-process.md)

Backlog keys `P-001..P-074` and `EPIC-01..EPIC-10` are canonical in [`docs/backlog.md`](docs/backlog.md).
