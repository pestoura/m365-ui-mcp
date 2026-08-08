# Deployment

Two containers on a Docker network:

- `planner-mcp` (control plane) — publishes only the MCP port to the local host/tunnel.
- `planner-browser-worker` — attached to an **internal** network, no published port.

Hardening applied in `docker-compose.yml`: `no-new-privileges:true`, `cap_drop: [ALL]`,
`read_only: true` for the control plane, tmpfs for scratch, named volumes for state and browser
profile, no host Docker socket, no host home mounts.

Healthcheck uses `planner-mcp-healthcheck` (SQLite + control-plane TCP + worker `/health`).
It deliberately does not probe `GET /mcp`.

## Base images
Both images are pinned by digest and validated by the blocking `base-image-digest-pinning` CI gate.
The browser worker uses `mcr.microsoft.com/playwright/python:v1.55.0-noble`, which ships Python 3.12
(required by this project) and the non-root `pwuser`.
