# Observability

## Logging
Structured JSON, one object per record, redacted through `planner_mcp.redaction` before emission.

## Metrics (low cardinality)
| Metric | Type | Labels |
| --- | --- | --- |
| `planner_mcp_tool_calls_total` | counter | `tool`, `outcome` |
| `planner_mcp_tool_latency_seconds` | histogram | `tool` |
| `planner_mcp_worker_up` | gauge | - |
| `planner_mcp_auth_state` | gauge | `state` |
| `planner_mcp_ui_contract_attested` | gauge | - |

No plan ids, task ids, user identifiers or tenant names are ever used as label values.
