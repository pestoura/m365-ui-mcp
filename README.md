# m365-ui-mcp

`m365-ui-mcp` is the Microsoft 365 semantic UI MCP evolving from the hardened `planner-mcp` foundation. The control plane is backed by a private Playwright/Chromium browser worker and is being generalized in gated phases while preserving the existing Planner public contract.

## Transition status

The GitHub repository identity has moved from `pestoura/planner-mcp` to `pestoura/m365-ui-mcp` under `CORE-002`.

The current runtime compatibility baseline is still product version **0.1.0** and remains Planner-scoped until the subsequent shared-core extraction blocks complete. Therefore the Python distribution/package names, CLI entry points and `PLANNER_*` configuration documented below are intentionally still valid compatibility interfaces at this point; they are **not** silently renamed by the repository rename.

The immutable pre-M365 Planner baseline is `planner-pre-m365-0.1.0`.

## Current release scope

The 0.1.0 compatibility contract is deliberately **read-only**:

- 17 MCP read tools, all existing `planner_*` public names preserved;
- zero public mutation tools;
- Microsoft Graph is **not** used as the functional backend;
- browser capabilities are published only from attested UI evidence;
- live browser automation fails closed when the required UIContract state is not attested;
- Conditional Access, device-enrolment requirements and ambiguous authentication states are blockers, never bypassed;
- MFA remains human-in-the-loop; credentials and authenticator approval are not automated.

The default runtime mode is `mock`. CI and isolated acceptance must never contact a real Microsoft 365 tenant.

## Architecture

The runtime is split into two trust zones:

1. **MCP control plane** — FastMCP over Streamable HTTP, contracts, policy, state, redaction, metrics and semantic tool registration.
2. **Private browser worker** — FastAPI + Playwright/Chromium, isolated from direct MCP clients and restricted to typed semantic operations.

The M365 target architecture and transition backlog live under [`docs/m365-transition/`](docs/m365-transition/README.md). The immutable Planner architecture/specification remains under [`docs/`](docs/vision.md) and continues to define the 0.1.0 compatibility baseline until migrated through the `PLN-MIG-*` parity gates.

## Runtime configuration

Configuration is typed and fail-closed. `mock` mode uses safe local defaults. `live` mode currently requires both `PLANNER_WORKER_URL` and an absolute `PLANNER_STATE_PATH`; startup exits non-zero with the stable `CONFIG_INVALID` error when required or typed configuration is invalid.

Only non-secret `PLANNER_*` configuration is accepted in the current compatibility baseline. Planner-prefixed environment variable names that look like credentials — for example names containing `TOKEN`, `PASSWORD`, `SECRET`, `API_KEY`, `COOKIE` or `PRIVATE_KEY` — are rejected. Their values are never included in the configuration error response.

`CORE-004` will introduce `M365_*` as the canonical namespace and retain bounded `PLANNER_*` aliases with explicit deprecation metadata. Until that gate is merged and GREEN, the following current settings remain authoritative:

| Variable | Default | Notes |
| --- | --- | --- |
| `PLANNER_MODE` | `mock` | `mock` or `live` |
| `PLANNER_MCP_HOST` | `127.0.0.1` | Control-plane bind host |
| `PLANNER_MCP_PORT` | `8080` | Port 1–65535 |
| `PLANNER_WORKER_URL` | `http://127.0.0.1:8090` | Required explicitly in `live`; HTTP(S), no URL userinfo |
| `PLANNER_STATE_PATH` | `/var/lib/planner-mcp/state.sqlite3` | Required explicitly in `live`; must be absolute |
| `PLANNER_REQUEST_TIMEOUT_S` | `30` | Positive, maximum 300 seconds |
| `PLANNER_REQUIRE_UI_ATTESTATION` | `true` | Cannot be disabled in `live` |
| `PLANNER_ALLOW_MUTATIONS` | `false` | Must remain `false` in 0.1.0 |
| `PLANNER_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL` |

Readiness exposes only a sanitized configuration summary: host, worker URL and state path are emitted as `[REDACTED]`. Credentials, tokens, cookies and authentication material are not valid configuration fields.

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

Current compatibility entry points remain:

```bash
planner-mcp
planner-browser-worker
```

They will only change through explicit versioned CORE migration work; existing `planner_*` MCP tool names are not coupled to repository/package naming.

Container definitions are in [`docker/`](docker/) and [`docker-compose.yml`](docker-compose.yml). Base images are digest-pinned and CI blocks HIGH/CRITICAL Trivy findings, validates two CycloneDX SBOMs, performs secret/dependency scanning and runs isolated acceptance.

## Governance and release gates

A capability is not considered live-supported because code exists or a mock test passes. Promotion requires evidence and attestation. The current Planner baseline remains governed by:

- [`docs/planner-premium-capabilities.md`](docs/planner-premium-capabilities.md)
- [`docs/ui-contract.md`](docs/ui-contract.md)
- [`docs/acceptance.md`](docs/acceptance.md)
- [`docs/definition-of-done.md`](docs/definition-of-done.md)
- [`docs/release-process.md`](docs/release-process.md)

Backlog keys `P-001..P-074` and `EPIC-01..EPIC-10` remain canonical in [`docs/backlog.md`](docs/backlog.md). The M365 transition uses the separate `M365-SETUP-*`, `CORE-*`, `PLN-MIG-*`, `OUT-*`, `XAPP-*` and `REL-*` namespaces in [`docs/m365-transition/roadmap-and-backlog.md`](docs/m365-transition/roadmap-and-backlog.md).
