# Rename Impact Map — `planner-mcp` -> `m365-ui-mcp`

Status: **Repository/Python namespace migration complete; CORE-004 config namespace implemented and awaiting gates.**

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

## Controlled migration surface

| Area | Current state | Target / compatibility action |
|---|---|---|
| GitHub repository | **`pestoura/m365-ui-mcp`** | Complete. |
| Python distribution | `planner-mcp` | Retained temporarily as installer compatibility identity; future distribution cutover requires a release/compatibility gate. |
| Canonical core namespace | `m365_mcp` | Present; CORE-005 extracts generic implementation behind it. |
| Canonical worker namespace | `m365_browser_worker` | Present; CORE-006 extracts generic worker implementation behind it. |
| Canonical CLI | `m365-ui-mcp`, `m365-browser-worker`, `m365-ui-mcp-healthcheck` | Present; Planner entry points retained. |
| MCP tools | `planner_*` | **PRESERVE**; add `m365_*` and later `outlook_*` without bulk-renaming Planner. |
| Config env | `M365_*` canonical; `PLANNER_*` `DEPRECATED_ALIAS` to 2.0.0 | Divergent dual definitions fail closed; state-path relocation is deliberately deferred. |
| Contracts | Planner-named AgentCard/manifests | Generalize core contracts; preserve/version Planner adapter contracts. |
| UIContract | single Planner global file | Fragment into application/surface/capability-scoped contracts. |
| Docker images | Planner naming | Rename/version under M365 identity while preserving digest pinning and scans. |
| Compose services | Planner-specific names | Migrate to M365 names; preserve private worker ingress. |
| Network | `browser-internal` with `internal: true` | Redesign for private control ingress plus controlled M365 egress (`CORE-025`). |
| Profile/state paths | Planner paths | Migrate carefully with compatibility/migration logic; never export session secrets. |
| SQLite identity | `external_id`-centric Planner resource model | Migrate to account/application/container/resource identity; metadata only. |
| Cloudflare MCP portal | Planner endpoint/name references | Update after corresponding M365 service cutover; no direct worker exposure. |
| Hermes references | Planner endpoint/tool references | Update only after M365 service endpoint is ready; Hermes remains optional orchestration. |
| Monitoring/Grafana | Planner service/metric naming | Introduce M365 low-cardinality names while preserving historical continuity where practical. |
| CI/release | Planner distribution/image/schema names | Update with relevant CORE/REL gates; preserve or strengthen every security gate. |
| Consumers | callers of 17 `planner_*` tools | Compatibility tests before/after; default no breaking change. |

## Cutover safeguards

1. Public `planner_*` tools are not renamed as a side effect of infrastructure identity migration.
2. Persistent browser profile/session state is never serialized or moved through rename/config work.
3. Planner mock/contract/policy parity remains required after every core extraction step.
4. Portal/deployment/monitoring references move only with corresponding service identity and acceptance evidence.
