# Rename Impact Map — `planner-mcp` -> `m365-ui-mcp`

Status: **CORE-002 repository rename executed and read-back verified; downstream identity migrations remain staged.**

## Repository cutover evidence

| Check | Result |
|---|---|
| Canonical repository | `pestoura/m365-ui-mcp` |
| Former repository route | resolves to the same renamed repository |
| GitHub repository ID | `1327254732` unchanged |
| Rename-point `main` | `24da6de7a88e18e7cc6f11b0216d91d602136816` unchanged |
| Pre-M365 baseline tag | `planner-pre-m365-0.1.0` -> `232c72632ab5c93d0bee70ac588af08422cbc42d` unchanged |
| Delete/recreate | not performed |
| Force ref update | not performed |
| Ambiguous mutation handling | bridge timeout reconciled by read-back; no blind retry |

## Remaining controlled migration surface

| Area | Current state after CORE-002 | Target / compatibility action |
|---|---|---|
| GitHub repository | **`pestoura/m365-ui-mcp`** | Complete; former route retained by GitHub redirect behavior. |
| Python project | `planner-mcp` | Introduce M365 distribution identity during CORE extraction; avoid breaking Planner consumers unnecessarily. |
| Core package | `planner_mcp` | Extract/generalize to `m365_mcp`; bounded compatibility imports only where useful. |
| Worker package | `planner_browser_worker` | Generalize to `m365_browser_worker`. |
| CLI | `planner-mcp` | Introduce canonical M365 CLI while preserving/documenting Planner compatibility path where required. |
| Worker CLI | `planner-browser-worker` | Introduce M365 worker identity. |
| Health CLI | `planner-mcp-healthcheck` | Generalize without weakening existing health behavior. |
| MCP tools | `planner_*` | **PRESERVE**; do not bulk-rename. Add `m365_*` and later `outlook_*`. |
| Config env | `PLANNER_*` | `M365_*` canonical; temporary `PLANNER_*` aliases with structured deprecation metadata/removal version. |
| Contracts | Planner-named AgentCard/manifests | Generalize core contracts; preserve/version Planner adapter contracts. |
| UIContract | single Planner global file | fragment into `common/`, `planner/`, `outlook/mail/`, `outlook/calendar/`, `outlook/people/`, `outlook/todo/`, etc. |
| Docker images | Planner naming | rename/version under M365 identity; preserve digest pinning and scan gates. |
| Compose services | Planner-specific names | migrate to M365 names; preserve private worker ingress. |
| Network | `browser-internal` with `internal: true` | redesign for private control ingress plus controlled M365 egress (`CORE-025`). |
| Profile/state paths | `/var/lib/planner-worker/...` and Planner state paths | migrate carefully with compatibility/migration logic; never expose/copy session secrets. |
| SQLite identity | `external_id`-centric Planner resource model | migrate to account/application/container/resource identity; metadata only. |
| Cloudflare MCP portal | Planner endpoint/name references | update after corresponding M365 service cutover; no direct worker exposure. |
| Hermes references | Planner endpoint/tool references | update only after M365 service endpoint is ready; Hermes is optional orchestration, not auth boundary. |
| Monitoring/Grafana | Planner service/metric naming | introduce M365 low-cardinality names while preserving historical dashboard continuity where practical. |
| CI/release | Planner package/image/schema names | update with the relevant CORE migration blocks; preserve or strengthen every security gate. |
| README/docs/ADRs | repository identity is M365; 0.1.0 runtime remains Planner compatibility baseline | distinguish immutable Planner evidence from current product identity. |
| Consumers | callers of 17 `planner_*` tools | compatibility tests before/after; default no breaking change. |

## Cutover safeguards

1. Repository rename occurred only after Phase 0 and `CORE-001` post-merge gates were GREEN.
2. Old/new identities are recorded in the accepted M365 ADR and execution evidence.
3. Public `planner_*` tools were not renamed as a side effect of the repository rename.
4. Persistent browser profile/session state was not moved or serialized by the repository rename.
5. Planner mock/contract/policy parity remains required after every core extraction step.
6. Portal/deployment/monitoring references move only with the corresponding service identity and acceptance evidence.
