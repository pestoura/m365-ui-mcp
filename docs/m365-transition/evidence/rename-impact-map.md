# Rename Impact Map — `planner-mcp` -> `m365-ui-mcp`

Status: Phase 0 preflight. No rename is executed by this document.

| Area | Current baseline | Target / compatibility action |
|---|---|---|
| GitHub repository | `pestoura/planner-mcp` | Rename to `pestoura/m365-ui-mcp` only after Phase 0 merge/gates. Preserve GitHub redirect but update canonical references. |
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
| Cloudflare MCP portal | Planner endpoint/name references | update after repository/service cutover; no direct worker exposure. |
| Hermes references | Planner endpoint/tool references | update only after M365 service endpoint is ready; Hermes is optional orchestration, not auth boundary. |
| Monitoring/Grafana | Planner service/metric naming | introduce M365 low-cardinality names while preserving historical dashboard continuity where practical. |
| CI/release | Planner package/image/schema names | update after core extraction; preserve or strengthen every security gate. |
| README/docs/ADRs | Planner product references | distinguish historical Planner baseline from new M365 product. |
| Consumers | callers of 17 `planner_*` tools | compatibility test before/after; default no breaking change. |

## Cutover safeguards

1. Do not rename the repository before the reconciled Phase 0 PR is GREEN and merged.
2. Record old/new identities in an ADR and release notes.
3. Do not rename public `planner_*` tools as a side effect of package/repository rename.
4. Do not move/copy the persistent browser profile in a way that serializes cookies, tokens or storage state outside the worker boundary.
5. Run Planner mock/contract parity and policy parity after every core extraction step.
6. Update portal/deployment/monitoring references only when the corresponding service identity exists.
