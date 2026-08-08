# m365-ui-mcp

`m365-ui-mcp` is the Microsoft 365 semantic UI MCP evolving from the hardened `planner-mcp` foundation. The control plane is backed by a private Playwright/Chromium browser worker and is being generalized in gated phases while preserving the existing Planner public contract.

## Transition status

The GitHub repository identity is `pestoura/m365-ui-mcp`. Canonical Python/CLI namespaces are now `m365_mcp`, `m365_browser_worker`, `m365-ui-mcp` and `m365-browser-worker`; the Planner package/CLI surfaces remain compatibility interfaces while shared-core extraction continues.

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

Configuration is typed and fail-closed. `M365_*` is the canonical namespace. The equivalent `PLANNER_*` names remain bounded compatibility aliases with status `DEPRECATED_ALIAS` and planned removal at major version `2.0.0`.

When canonical and legacy aliases are both present they must contain the same literal value. Divergent definitions fail with `CONFIG_INVALID`; error context contains variable names only and never their values. Credential-shaped variable names under either namespace — for example names containing `TOKEN`, `PASSWORD`, `SECRET`, `API_KEY`, `COOKIE` or `PRIVATE_KEY` — are rejected.

`live` mode requires an explicit worker URL and absolute state path through either canonical or legacy aliases. The existing default state location is intentionally unchanged during `CORE-004`; state-path migration is a separate controlled change.

| Canonical variable | Legacy alias | Default | Notes |
| --- | --- | --- | --- |
| `M365_MODE` | `PLANNER_MODE` | `mock` | `mock` or `live` |
| `M365_MCP_HOST` | `PLANNER_MCP_HOST` | `127.0.0.1` | Control-plane bind host |
| `M365_MCP_PORT` | `PLANNER_MCP_PORT` | `8080` | Port 1–65535 |
| `M365_WORKER_URL` | `PLANNER_WORKER_URL` | `http://127.0.0.1:8090` | Required explicitly in `live`; HTTP(S), no URL userinfo |
| `M365_STATE_PATH` | `PLANNER_STATE_PATH` | `/var/lib/planner-mcp/state.sqlite3` | Required explicitly in `live`; must be absolute |
| `M365_REQUEST_TIMEOUT_S` | `PLANNER_REQUEST_TIMEOUT_S` | `30` | Positive, maximum 300 seconds |
| `M365_REQUIRE_UI_ATTESTATION` | `PLANNER_REQUIRE_UI_ATTESTATION` | `true` | Cannot be disabled in `live` |
| `M365_ALLOW_MUTATIONS` | `PLANNER_ALLOW_MUTATIONS` | `false` | Must remain `false` in 0.1.0 |
| `M365_LOG_LEVEL` | `PLANNER_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL` |
| `M365_WORKER_HOST` | `PLANNER_WORKER_HOST` | `127.0.0.1` | Private worker bind host |
| `M365_WORKER_PORT` | `PLANNER_WORKER_PORT` | `8090` | Private worker bind port |

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

Canonical entry points:

```bash
m365-ui-mcp
m365-browser-worker
m365-ui-mcp-healthcheck
```

Compatibility entry points remain:

```bash
planner-mcp
planner-browser-worker
planner-mcp-healthcheck
```

Existing `planner_*` MCP tool names are not coupled to repository/package naming and remain `PRESERVE`.

Container definitions are in [`docker/`](docker/) and [`docker-compose.yml`](docker-compose.yml). Base images are digest-pinned and CI blocks HIGH/CRITICAL Trivy findings, validates two CycloneDX SBOMs, performs secret/dependency scanning and runs isolated acceptance.

## Governance and release gates

A capability is not considered live-supported because code exists or a mock test passes. Promotion requires evidence and attestation. The current Planner baseline remains governed by:

- [`docs/planner-premium-capabilities.md`](docs/planner-premium-capabilities.md)
- [`docs/ui-contract.md`](docs/ui-contract.md)
- [`docs/acceptance.md`](docs/acceptance.md)
- [`docs/definition-of-done.md`](docs/definition-of-done.md)
- [`docs/release-process.md`](docs/release-process.md)

Backlog keys `P-001..P-074` and `EPIC-01..EPIC-10` remain canonical in [`docs/backlog.md`](docs/backlog.md). The M365 transition uses the separate `M365-SETUP-*`, `CORE-*`, `PLN-MIG-*`, `OUT-*`, `XAPP-*` and `REL-*` namespaces in [`docs/m365-transition/roadmap-and-backlog.md`](docs/m365-transition/roadmap-and-backlog.md).
