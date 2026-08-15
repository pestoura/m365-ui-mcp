# Changelog

## Unreleased

- AUTH-109 hardening: the pre-email sign-in surface classifier now prefers a uniquely present, attested email-entry control pair (structural detection via `bootstrap_discovery.discover_key` / `locator_runtime`) over a text-only `ACCOUNT_CHOOSER` marker, so no unnecessary chooser click is attempted when Microsoft co-presents chooser phrasing and the live email field. Ambiguous / multiple email controls fail closed; error surfaces still win; `_FORWARDABLE_SURFACES` unchanged. (CHG-M365-109)

## 0.1.0 — Foundation

- Read-only MCP control plane (FastMCP Streamable HTTP) with 17 tools.
- FastAPI browser worker with persistent Chromium profile abstraction; mock mode default.
- Auth state machine, MFA number-match detection with sanitized metadata.
- Versioned JSON contracts, evidence-based capability model, fail-closed UIContract.
- SQLite state foundation, fail-closed policy, redacted structured logging, Prometheus skeleton.
- Container hardening, CI with lint/type/tests/release contract/isolated acceptance/Trivy/SBOM.
- Full documentation set, ADR-001..005 and backlog P-001..P-074.
