# ADR-005 — hermes-mcp-bridge as pattern baseline, not a fork

- Status: Accepted
- Date: 2026-08-08

## Context

`pestoura/hermes-mcp-bridge` is an existing, hardened MCP integration with proven patterns:
envelope validation, redaction discipline, health/readiness split, container hardening, credential
rotation procedures and a CI gate layout. planner-mcp needs the same operational rigour but has a
different purpose, a different trust topology (a browser holding a corporate session) and a
different lifecycle.

## Decision

Treat `hermes-mcp-bridge` as a **golden baseline of patterns**, adopted at **equal or higher
strictness**, and:

- **Do not fork it.** planner-mcp is an independent repository and implementation.
- **Do not rename, absorb or repurpose it.** It keeps its identity and its own release cycle.
- **Do not degrade its controls** as a side effect of anything done here. No change to that
  repository is required or permitted by this block.

Patterns explicitly adopted: strict schema-validated envelopes with `additionalProperties: false`;
sink-level log redaction with key deny-list plus value patterns; low-cardinality metric label
allow-lists; health vs readiness separation; non-root, read-only, `cap_drop ALL`,
`no-new-privileges` containers with no Docker socket; CI gate layout (compile, lint, type, test,
schema, secret scan, dependency scan, Trivy CRITICAL/HIGH fail, SBOM); isolated acceptance in
containers; credential material kept outside the repository.

Where planner-mcp's risk is higher (a live corporate browser session), the control is made
stricter, never looser — for example default-deny policy for governed mutations and mandatory
read-back, which the bridge does not need.

## Consequences

- Two codebases share conventions without coupling; a change in one does not force the other.
- Reviewers can check planner-mcp against a known-good reference.
- Duplication of some infrastructure code is accepted in exchange for independence. Extraction
  into a shared library may be revisited later in its own ADR.

## Related

[docs/security.md](../security.md), [docs/architecture.md](../architecture.md);
backlog P-063, P-064, P-065, P-068.
