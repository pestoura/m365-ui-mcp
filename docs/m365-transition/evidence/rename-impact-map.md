# Rename Impact Map — `planner-mcp` -> `m365-ui-mcp`

Status: **Repository rename complete; CORE-003 Python namespace compatibility migration implemented and awaiting gates.**

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

## Controlled migration surface

| Area | Current state | Target / compatibility action |
|---|---|---|
| GitHub repository | **`pestoura/m365-ui-mcp`** | Complete. |
| Python distribution | `planner-mcp` | Retained temporarily as installer compatibility identity; future distribution cutover requires its own release/compatibility gate. |
| Canonical core namespace | `m365_mcp` facade introduced | CORE-005 extracts generic implementation behind it; `planner_mcp` remains bounded compatibility. |
| Canonical worker namespace | `m365_browser_worker` facade introduced | CORE-006 extracts generic worker implementation behind it; `planner_browser_worker` remains bounded compatibility. |
| Canonical CLI | `m365-ui-mcp`, `m365-browser-worker`, `m365-ui-mcp-healthcheck` introduced | Old Planner entry points remain operational compatibility aliases. |
| MCP tools | `planner_*` | **PRESERVE**; do not bulk-rename. Add `m365_*` and later `outlook_*`. |
| Config env | `PLANNER_*` | `M365_*` canonical under CORE-004; temporary `PLANNER_*` aliases with structured deprecation metadata/removal version. |
| Contracts | Planner-named AgentCard/manifests | Generalize core contracts; preserve/version Planner adapter contracts. |
| UIContract | single Planner global file | fragment into `common/`, `planner/`, `outlook/mail/`, `outlook/calendar/`, `outlook/people/`, `outlook/todo/`, etc. |
| Docker images | Planner naming | rename/version under M365 identity; preserve digest pinning and scan gates. |
| Compose services | Planner-specific names | migrate to M365 names; preserve private worker ingress. |
| Network | `browser-internal` with `internal: true` | redesign for private control ingress plus controlled M365 egress (`CORE-025`). |
| Profile/state paths | Planner paths | migrate carefully with compatibility/migration logic; never expose/copy session secrets. |
| SQLite identity | `external_id`-centric Planner resource model | migrate to account/application/container/resource identity; metadata only. |
| Cloudflare MCP portal | Planner endpoint/name references | update after corresponding M365 service cutover; no direct worker exposure. |
| Hermes references | Planner endpoint/tool references | update only after M365 service endpoint is ready; Hermes is optional orchestration, not auth boundary. |
| Monitoring/Grafana | Planner service/metric naming | introduce M365 low-cardinality names while preserving historical dashboard continuity where practical. |
| CI/release | Planner distribution/image/schema names | update with relevant CORE/REL gates; preserve or strengthen every security gate. |
| Consumers | callers of 17 `planner_*` tools | compatibility tests before/after; default no breaking change. |

## Cutover safeguards

1. Repository rename occurred only after Phase 0 and `CORE-001` post-merge gates were GREEN.
2. Old/new identities are recorded in the accepted M365 ADR and execution evidence.
3. Public `planner_*` tools were not renamed as a side effect of repository/package namespace migration.
4. Persistent browser profile/session state was not moved or serialized.
5. Planner mock/contract/policy parity remains required after every core extraction step.
6. Portal/deployment/monitoring references move only with the corresponding service identity and acceptance evidence.
