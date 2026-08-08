# Reporting

Reporting projections are read-only views over Planner state used for status packs and evidence:
plan health, task distribution per bucket, dependency chains, schedule risk.

0.1.0 ships the `planner_mcp.reporting` package skeleton and `planner_project_snapshot` as the first
composite projection. Evidence bundles are JSON, redacted, and versioned by contract version.
