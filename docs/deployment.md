# Deployment

Scope: how `pestoura/planner-mcp` and `planner-browser-worker` are deployed, isolated and hardened. Companions: [architecture.md](architecture.md), [security.md](security.md), [threat-model.md](threat-model.md), [browser-worker.md](browser-worker.md), [cloudflare-mcp-portal.md](cloudflare-mcp-portal.md), [observability.md](observability.md).

Deployment target: a single Linux host running Docker Compose, fronted by a Cloudflare Tunnel. There is no direct public port binding. The browser worker is never publicly reachable.

## 1. Topology

```
ChatGPT
  │  (HTTPS, OAuth at the Portal)
  ▼
Cloudflare MCP Server Portal
  │  (Cloudflare Tunnel, outbound-only from host)
  ▼
cloudflared          ── host container, egress only, no inbound ports
  │  (docker network: edge)
  ▼
planner-mcp          ── FastMCP Streamable HTTP, binds 127.0.0.1 only for admin,
  │                     tunnel-reachable on the edge network for MCP
  │  (docker network: worker-net, internal: true)
  ▼
planner-browser-worker ── FastAPI, binds 0.0.0.0 inside worker-net only
  │
  ▼
Chromium (Playwright, persistent profile volume) ─► Planner Premium UI (egress via proxy allowlist)
```

Sidecars: `mock-planner-ui` exists **only** in the `isolated` profile and is attached to `worker-net`; it is absent from the live profile.

## 2. Networks

| Network | Driver | `internal` | Members | Purpose |
|---------|--------|-----------|---------|---------|
| `edge` | bridge | no | `cloudflared`, `planner-mcp` | Tunnel ingress to the control plane only. |
| `worker-net` | bridge | **yes** | `planner-mcp`, `planner-browser-worker`, (`mock-planner-ui` in isolated) | Control plane ↔ worker. No route to the internet. |
| `egress` | bridge | no | `planner-browser-worker` (live profile only) | Chromium's outbound path, restricted by proxy allowlist. |

Consequences: the worker has no inbound path from the host or the internet; in the isolated profile the worker is attached only to `worker-net`, so it physically cannot reach the public internet.

## 3. Port boundaries

| Binding | Service | Exposure | Rationale |
|---------|---------|----------|-----------|
| `127.0.0.1:8791` | `planner-mcp` admin/metrics/health | loopback only | Operator and local scrape; never public. |
| container-internal `:8790` | `planner-mcp` MCP endpoint | `edge` network only | Reached exclusively via cloudflared. |
| container-internal `:9100` | `planner-browser-worker` HTTP | `worker-net` only | No host publication at all. |
| container-internal `:9101` | worker metrics | `worker-net` only | Scraped by the control plane or a local agent. |
| none | Chromium DevTools | disabled | `--remote-debugging-port` is forbidden; a startup assertion fails if set. |

Rule: no `ports:` entry in the live compose file publishes anything other than the loopback admin port. A CI check parses the compose file and fails on any `0.0.0.0` or bare-port publication.

## 4. Container hardening baseline

Applied to every service:

| Setting | Value | Notes |
|---------|-------|-------|
| `user` | non-root uid/gid (e.g. `10001:10001`) | Image builds create the user; no `USER root` at runtime. |
| `read_only` | `true` | Root filesystem immutable. |
| `cap_drop` | `["ALL"]` | No capability is added back for the control plane. |
| `security_opt` | `no-new-privileges:true` | Blocks setuid escalation. |
| `pids_limit` | set per service | Control plane 256; worker 1024 (Chromium is process-heavy). |
| `mem_limit` / `cpus` | set per service | Worker gets the larger share; OOM is observable via `worker_browser_restarts_total{reason="oom"}`. |
| `restart` | `unless-stopped` | |
| `healthcheck` | per service | Control plane `/healthz`; worker readiness includes session state. |
| `logging` | json-file, capped size+files | Log shipping reads stdout; rotation prevents disk exhaustion. |
| `init` | `true` | Reaps zombie Chromium children. |

Worker-specific: Chromium needs a larger `/dev/shm`; this is provided as a **tmpfs**, never by mounting the host's `/dev/shm`. Seccomp uses the Docker default profile; if a narrower profile is used it must be version-controlled and referenced by path, and any relaxation requires a justification recorded in [security.md](security.md).

Explicit prohibitions, all enforced by a compose-lint job:

| Prohibited | Reason |
|------------|--------|
| `/var/run/docker.sock` mount | Container escape equivalent to host root. |
| Host `$HOME` or `/` mounts | Credential and data exposure. |
| `privileged: true` | Removes all isolation. |
| `network_mode: host` | Bypasses network boundaries. |
| `cap_add` on the control plane | Not needed. |
| Tag-only image references | Non-reproducible; see §7. |
| `:latest` anywhere | Same. |
| Environment secrets in the compose file | See §8. |

## 5. Filesystem: tmpfs and volumes

Because root filesystems are read-only, every writable path is declared.

| Path | Service | Type | Size | Contents |
|------|---------|------|------|----------|
| `/tmp` | all | tmpfs (`noexec,nosuid,nodev`) | 64 MiB | Scratch. |
| `/dev/shm` | worker | tmpfs (`nosuid,nodev`) | 512 MiB | Chromium shared memory. |
| `/run` | all | tmpfs | 16 MiB | Runtime sockets/pids. |
| `/home/app/.cache` | worker | tmpfs (`noexec`) | 256 MiB | Browser caches (deliberately ephemeral). |
| `planner-profile` | worker | named volume | — | Persistent Chromium profile (cookies/session). Mode 0700, owned by the worker uid. |
| `planner-state` | control plane | named volume | — | Idempotency store, audit DB (WAL). |
| `planner-evidence` | control plane | named volume | — | Evidence bundles, isolated profile only. |

The persistent profile volume is the single most sensitive artifact in the deployment: it holds an authenticated session. It is never backed up to shared storage unencrypted, never copied into an image, never mounted into any other container, and is excluded from log/evidence collection. Its handling is specified in [security.md](security.md) and [authentication-and-mfa.md](authentication-and-mfa.md).

## 6. Public vs loopback boundary

| Reachable from | Can reach |
|----------------|-----------|
| Internet | Cloudflare edge only. |
| Cloudflare Tunnel | `planner-mcp` MCP endpoint only, after Portal authentication. |
| Host loopback | `planner-mcp` admin/metrics only. |
| `planner-mcp` | worker HTTP on `worker-net`. |
| Worker | Planner UI hosts via the egress allowlist (live profile) or the mock UI (isolated profile). |
| Anything else | Nothing. |

The control plane authenticates and authorizes every MCP request independently of the Portal; the tunnel is treated as an untrusted transport. Access-control specifics live in [security.md](security.md) and [cloudflare-mcp-portal.md](cloudflare-mcp-portal.md).

## 7. Digest-pinned images

All `image:` references are `name@sha256:<digest>`. Build stages in Dockerfiles pin their bases the same way.

| Image | Base policy |
|-------|-------------|
| `planner-mcp` | Slim Python base, digest-pinned, multi-stage, no compilers in the final layer. |
| `planner-browser-worker` | Official Playwright base matching the pinned Playwright version, digest-pinned. |
| `cloudflared` | Vendor image, digest-pinned. |
| `mock-planner-ui` | Same Python base as the control plane, digest-pinned. |

CI enforcement:

| Check | Failure condition |
|-------|-------------------|
| `compose-digest-lint` | Any `image:` without `@sha256:`. |
| `dockerfile-digest-lint` | Any `FROM` without `@sha256:`. |
| `pin-freshness` | Pinned digest older than the policy window with a known critical CVE fixed upstream. |
| `sbom-diff` | SBOM regenerated per build and diffed; unexpected package additions block the release. |
| `provenance` | Built image digest recorded in the release record and in `environment.json` of the acceptance bundle. |

Digest updates are ordinary PRs: bump digest, regenerate SBOM, re-run isolated acceptance (see [release-process.md](release-process.md)).

## 8. Secrets handling

| Secret | Storage | Delivered as | Rotation |
|--------|---------|--------------|----------|
| Cloudflare tunnel token | Host file, mode 0600, root-owned, mounted read-only to `cloudflared` | file | On compromise or annually |
| Portal/OAuth client credentials | Docker/compose secret file | file path in env var | Annually |
| Log/audit hashing salt | Compose secret | file | On any redaction incident |
| Hermes notification webhook token | Compose secret | file | On compromise |
| Graph client credentials (optional, contextual) | Compose secret | file | Annually; absence must be tolerated |
| Planner user credentials | **Not stored** | — | Interactive login only; session lives in the profile volume |

Rules: secrets are mounted as files, never baked into images, never present in `docker inspect` output as values, never echoed in logs (the redaction detector covers secret shapes), and the deployment refuses to start if a required secret file is world-readable. `.env` files hold non-secret configuration only, and a CI check greps them for secret-shaped values.

## 9. Configuration surface

| Variable | Values | Effect |
|----------|--------|--------|
| `PLANNER_ENV` | `dev\|ci\|isolated\|live` | Log strictness, navigation allowlist, profile availability. |
| `PLANNER_MODE` | `read_only\|dry_run\|full` | `read_only` does not register mutating tools at all. |
| `WORKER_URL` | internal URL | Must resolve on `worker-net`. |
| `GRAPH_CONTEXT_ENABLED` | bool | Default `false`; enabling never changes functional behaviour. |
| `MFA_NOTIFY_ENABLED` | bool | Sanitized events to Hermes. |
| `EVIDENCE_DIR` | path | Isolated profile only. |
| `MAX_CONCURRENCY` | int | Worker queue bound. |

Startup assertions (fail-closed): `live` requires the egress allowlist to be non-empty and the mock UI to be absent; `ci` forbids any non-loopback navigation target; `read_only` asserts zero mutating handlers registered; any unknown variable prefixed `PLANNER_` aborts startup.

## 10. Operational procedures

| Procedure | Summary |
|-----------|---------|
| Deploy | Pull by digest → `compose up -d` with the live profile → health checks → smoke read-only tool call → record digests. |
| Rollback | Re-point to the previous digests → `compose up -d` → verify health → record in the release log. State volumes are backward-compatible within a minor version. |
| Session re-auth | Stop mutating traffic → run interactive login flow → approve in Microsoft Authenticator → confirm `worker_session_state{state="ready"}`. |
| Profile reset | Stop worker → snapshot (encrypted) → remove volume → re-auth. Required after suspected profile corruption. |
| Upgrade Playwright/Chromium | Bump pinned versions and base digest together → re-run selector attestation → isolated acceptance → release. |
| Incident: selector drift | Freeze mutating tools (`PLANNER_MODE=read_only`) → attest selectors → patch registry → re-accept. |
| Backup | Audit DB and state volume, encrypted at rest; profile volume excluded unless encrypted and access-controlled. |

## 11. Backlog mapping

| Area | Backlog keys |
|------|--------------|
| Compose topology + networks | P-061, P-062 |
| Hardening + compose lint | P-063, P-064 |
| Digest pinning + SBOM in CI | P-065, P-066 |
| Secrets handling | P-067 |
| Tunnel/Portal wiring | P-031, P-050 |
