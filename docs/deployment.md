# Deployment

This document defines the deployment, isolation and container-hardening target for the Planner MCP
control plane and private browser worker.

Companions: [`architecture.md`](architecture.md), [`security.md`](security.md),
[`privacy-boundary.md`](privacy-boundary.md), [`browser-worker.md`](browser-worker.md),
[`cloudflare-mcp-portal.md`](cloudflare-mcp-portal.md) and [`release-process.md`](release-process.md).

## 1. Target topology

```text
ChatGPT
   ↓ HTTPS / MCP
Cloudflare MCP Server Portal
   ↓ protected ingress / tunnel
Planner MCP Control Plane
   ↓ private internal channel
Planner Browser Worker
   ↓ Playwright / Chromium
Microsoft Planner Premium UI
```

Hermes is separate from the normal Planner execution path and is used only for bounded
notifications/HITL as documented in [`hermes-integration.md`](hermes-integration.md).

## 2. Exposure boundary

- browser worker has no public port;
- browser worker is reachable only from the control plane/private runtime network;
- Chromium DevTools/remote-debugging is not publicly exposed;
- control-plane public exposure is only through the approved Cloudflare MCP ingress;
- local admin/metrics endpoints are loopback/internal only;
- no Docker socket is mounted;
- no host home directory or personal credential store is mounted;
- no Hermes directory is mounted into the browser worker.

The tunnel/edge path is transport, not authorization. The control plane enforces its own policy and
request validation.

## 3. Browser-worker personal-device boundary

The worker uses one dedicated professional Chromium profile volume/path. It must not:

- use/modify a personal browser profile;
- copy cookies/tokens from another browser/device;
- mount host `$HOME`, `.ssh`, `.gnupg`, `.aws` or other personal credential directories;
- trigger Intune/Company Portal/MDM/Entra device registration/EDR installation;
- install corporate device certificates automatically;
- alter host OS security policy to satisfy tenant controls.

A managed/compliant/enrolled/certificate Conditional Access requirement returns
`BLOCKER_CONDITIONAL_ACCESS`.

## 4. Container-hardening baseline

Production services use the strongest posture compatible with the tested runtime:

- non-root user;
- `read_only: true` root filesystem where supported;
- `cap_drop: ALL`;
- `no-new-privileges`;
- bounded PID/memory/CPU resources;
- explicit healthcheck;
- explicit writable tmpfs/volumes only;
- no privileged mode;
- no host network mode;
- no Docker socket;
- no host root/home mounts;
- no tag-only or `latest` production base/image references once release pinning is resolved.

Chromium may require additional shared memory/process capacity; provide it through explicit container
resources/tmpfs, not unsafe host mounts or privilege escalation.

## 5. Writable storage

Typical writable surfaces:

| Surface | Owner | Purpose | Sensitivity |
| --- | --- | --- | --- |
| `/tmp` / `/run` tmpfs | each service | ephemeral runtime state | low/bounded |
| browser `/dev/shm` tmpfs | worker | Chromium shared memory | ephemeral |
| professional profile volume | worker only | authenticated browser session | **high** |
| control-plane state volume | control plane only | SQLite/state/audit | governed |
| evidence volume/path | acceptance/operator only | sanitized evidence bundles | governed |

The profile volume is never committed, copied into an image, exposed through telemetry or mounted
into another service merely for convenience.

## 6. Network profiles

### Live profile

- control plane receives only approved Cloudflare ingress;
- control plane can call the worker on the private network;
- worker/Chromium can reach only the network targets required for the Microsoft browser flow,
  constrained by the deployment's egress policy;
- worker is not reachable from the public edge.

### Isolated acceptance profile

- no real Planner credentials;
- browser navigation targets the mock Planner UI only;
- external Planner/login egress is blocked/guarded;
- mock UI is private to the isolated test topology;
- any mutation behavior is synthetic/mock only.

## 7. Image pinning

Production Dockerfile bases and image references must be digest-pinned using **real registry
SHA-256 digests**.

The known blocker:

```text
BLOCKER_IMAGE_DIGEST_PINNING
```

remains open until the real digest for each required production base/image is retrieved and
validated from its registry. Do not invent or placeholder a SHA-256 to make CI green.

Required release checks include:

- every production `FROM`/`image:` is pinned as required by policy;
- pinned digest corresponds to the intended image/version/platform;
- image builds succeed at the pinned digest;
- scan/SBOM evidence references the built/pinned image identity.

## 8. Supply chain

For control plane and browser worker:

- build production image;
- run Trivy image scanning;
- apply HIGH/CRITICAL failure policy;
- generate CycloneDX SBOM;
- validate SBOM format;
- ensure SBOM components are not empty;
- retain SBOM + scan output as release evidence.

Additionally run Trivy filesystem/dependency/secret checks according to the CI baseline.

`ignore-unfixed` is used only if explicitly approved by the repository security baseline and never to
hide a fixed high-risk vulnerability.

## 9. Secrets

Microsoft Planner user credentials are **not deployment secrets** because the password must not exist
inside the system. Authentication is interactive through the professional browser profile.

Other infrastructure secrets, where needed, are:

- file-backed or platform secret-mounted;
- least-privilege;
- excluded from repo/config logs;
- permission-checked at startup;
- rotatable without embedding them into images.

Examples may include Cloudflare tunnel/auth material, HMAC signing secrets or Hermes notification
authentication. Exact secret values never appear in Compose files, CI output or evidence bundles.

## 10. Configuration

Configuration is typed and fail-closed. Representative non-secret settings include:

```text
PLANNER_ENV
PLANNER_MODE
WORKER_URL
STATE_PATH
POLICY_PATH
PROFILE_PATH
LOG_LEVEL
METRICS_BIND
```

For 0.1.0, `PLANNER_MODE=read_only` (or equivalent product mode) must result in exactly the canonical
17 `READ` tools being registered. Mutation handlers are absent from the public registry, not merely
hidden behind UI conventions.

Unknown/inconsistent production-critical configuration prevents readiness.

## 11. Health/readiness

The deployment distinguishes:

- process liveness;
- configuration/policy/state readiness;
- worker reachability;
- browser/auth readiness for live read work;
- UIContract/capability blockers.

Health/readiness payloads are sanitized and do not expose tokens/cookies/user content.

A healthy service can still report an operation-specific blocker such as `AUTH_REQUIRED`,
`UI_DRIFT` or `BLOCKER_CONDITIONAL_ACCESS`.

## 12. Cloudflare ingress

The final exposure path is:

```text
ChatGPT → Cloudflare → Planner MCP
```

Document and enforce:

- TLS;
- MCP Streamable HTTP endpoint;
- client/service authentication;
- origin protection;
- authorization/policy at the control plane;
- request/payload/time limits;
- rate limiting/backpressure;
- health/readiness separation;
- no browser-worker exposure.

See [`cloudflare-mcp-portal.md`](cloudflare-mcp-portal.md).

## 13. Deployment procedure

A production-candidate deployment is by exact version/digest:

1. verify required release gates/evidence;
2. resolve/pull exact pinned image digests;
3. start/update services using the hardened topology;
4. verify health/readiness;
5. verify private-worker network boundary;
6. perform a read-only MCP smoke call through the supported ingress;
7. record running commit/image/config hashes without recording secret values;
8. retain rollback references to the previous known-good release/digests.

## 14. Rollback

Rollback restores known-good application/image digests and validates health/readiness again. State
migration compatibility is documented per release.

Potential triggers include:

- failed post-deploy health/readiness;
- newly discovered HIGH/CRITICAL supply-chain issue;
- browser/worker crash regression;
- UI drift affecting supported capability;
- audit/state integrity problem.

A rollback does not attempt to bypass tenant Conditional Access or restore an exported browser
session from another device.

## 15. CI deployment-posture checks

Automated checks reject:

- `privileged: true`;
- host networking;
- Docker socket mounts;
- host root/home/personal credential mounts;
- browser-worker public `ports:` exposure;
- missing non-root/no-new-privileges/cap-drop posture where required;
- mutable/unpinned production images at release gate;
- secret-shaped values committed in deployment config;
- worker configurations capable of reaching the real tenant in CI isolated mode.

## 16. Backlog mapping

Deployment/security ownership is primarily:

| Concern | Canonical P-key(s) |
| --- | --- |
| Browser profile isolation | P-013 |
| Conditional Access/enrolment refusal | P-021, P-023 |
| Secret/telemetry hygiene | P-063 |
| Container hardening/Compose posture | P-064 |
| SBOM/vulnerability/digest gates | P-065 |
| Circuit/retry operational hardening | P-066 |
| Complete CI | P-068 |
| Isolated acceptance | P-069 |
| Release process / 0.1.0 | P-073, P-074 |

Cloudflare exposure is a deployment concern documented here, but it must not reuse P-031..P-036 as
transport work: those P-keys are canonically owned by EPIC-05 Mutations.
