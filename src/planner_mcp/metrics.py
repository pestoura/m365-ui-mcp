"""Low-cardinality Prometheus metric skeleton."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

REGISTRY = CollectorRegistry()

TOOL_CALLS = Counter(
    "planner_mcp_tool_calls_total",
    "MCP tool invocations.",
    labelnames=("tool", "outcome"),
    registry=REGISTRY,
)

TOOL_LATENCY = Histogram(
    "planner_mcp_tool_latency_seconds",
    "MCP tool latency.",
    labelnames=("tool",),
    registry=REGISTRY,
)

WORKER_UP = Gauge(
    "planner_mcp_worker_up",
    "Browser worker reachability (1/0).",
    registry=REGISTRY,
)

AUTH_STATE = Gauge(
    "planner_mcp_auth_state",
    "Current auth state as a low-cardinality gauge per state.",
    labelnames=("state",),
    registry=REGISTRY,
)

UI_CONTRACT_ATTESTED = Gauge(
    "planner_mcp_ui_contract_attested",
    "UIContract attestation status (1/0).",
    registry=REGISTRY,
)


def render() -> bytes:
    """Render the Prometheus exposition payload."""
    return generate_latest(REGISTRY)
