# Contributing

## Ground rules

1. Read [docs/definition-of-done.md](docs/definition-of-done.md) before starting. An item is Done
   only when every applicable line is true.
2. Never invent a selector, a tenant fact, a license fact or a capability attestation. If it was
   not observed, it does not go in.
3. Never weaken a `SEC-*` control ([docs/security.md](docs/security.md)) without an ADR and
   maintainer sign-off.
4. Fail closed. When in doubt, refuse with a typed error rather than guess.

## Workflow

1. Pick a backlog key `P-0xx` from [docs/backlog.md](docs/backlog.md); check its dependencies are
   met.
2. Branch: `feat/P-0xx-short-slug`, `fix/…`, `docs/…`, `chore/…`.
3. Implement the smallest coherent change; keep commits atomic.
4. Commit messages: `type(P-0xx): summary` — e.g. `feat(P-014): centralized UI contract loader`.
5. Update the affected docs **in the same PR** (tool catalog, capability matrix, traceability).
6. Open a PR using the template; fill the evidence section with real command output.
7. All required checks must be green before merge. No merging around a red gate.

## Local checks

```bash
python -m compileall -q src tests
ruff check .
ruff format --check .
mypy --strict src
pytest -q
```

Browser tests run against the local mock UI only. **Never point tests at a live tenant.**

## Code rules

- Python 3.12, `src/` layout, full type annotations, `mypy --strict` on `src/`.
- Selectors live only in `src/planner_mcp/browser/selectors/`. Anywhere else is a build failure.
- No dynamic `page.evaluate` source; no user input interpolated into selectors, URLs or JS.
- Every tool declares `trust_level`, `mutation_class`, `reversible`, `idempotency_class`,
  `approval_requirement`, `attestation_status`.
- Every mutating path goes through policy → approval → lock → apply → read-back. No exceptions.
- Errors are typed codes with sanitized detail; never raw exception text or DOM.

## Documentation rules

- Capability states advance only with an evidence hash. Documentation alone never advances a
  state.
- Do not cite Microsoft Graph as evidence of support (ADR-006).
- Keep [docs/traceability.md](docs/traceability.md) in sync; the traceability lint enforces it.

## What will be rejected

Credential automation; MFA handling outside Microsoft Authenticator; device enrolment or
compliance bypass; raw browser navigation exposed as an MCP tool; live-tenant calls in CI; secrets,
screenshots, DOM dumps or tenant data committed or attached to issues/PRs; capability claims
without evidence.

## Reporting security issues

Privately — see [SECURITY.md](SECURITY.md). Never in a public issue, never with captured secrets.
