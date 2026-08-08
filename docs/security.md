# Security

## Hard invariants
- Passwords, cookies, tokens, storage state and secrets are never committed, logged or persisted in MCP state.
- The persistent professional browser profile is the only authentication mechanism.
- The personal machine is never enrolled in Intune, Company Portal, Identity Broker, Entra device
  registration, MDM, corporate EDR, and no device certificates are installed.
- Conditional Access requiring a compliant/managed device fails closed with `BLOCKER_CONDITIONAL_ACCESS`.
  Bypass or spoofing is forbidden.
- 0.1.0 performs no mutations; policy denies every non-read tool.

## Container hardening
non-root (`pwuser` in the official Playwright image), `no-new-privileges:true`, `cap_drop: [ALL]`,
read-only root filesystem where practical, tmpfs for scratch, internal-only network for the worker,
no host Docker socket and no host home mounts, no published worker port.

## Base image pinning
Both base images are pinned by digest (`P-020`):

| Image | Reference |
| --- | --- |
| Control plane | `python:3.12-slim-bookworm@sha256:4766d8b5…58a2` |
| Browser worker | `mcr.microsoft.com/playwright/python:v1.55.0-noble@sha256:640d578a…3078` |

`scripts/check_base_image_pinning.py` runs as a **blocking** CI gate and fails the build if any
`FROM` reference loses its digest. Digests must be re-resolved and updated deliberately when the
base images are upgraded.

## Supply chain
Trivy filesystem and image scans (CRITICAL/HIGH fail), dependency scanning, secret scanning and
CycloneDX SBOMs for both images, written to the CI workspace and uploaded as artifacts.
