## Summary

<!-- What changed and why. Reference the backlog key. -->

Backlog key(s): P-0xx
Closes: #

## Type

- [ ] feat
- [ ] fix
- [ ] docs
- [ ] chore / CI
- [ ] security

## Checklist — Definition of Done

- [ ] Code implemented and typed (`mypy --strict src`)
- [ ] Tests added/updated for every affected layer (see docs/testing.md)
- [ ] Security-critical assertions for the touched area exist and pass
- [ ] Docs updated in this PR (tool catalog / capability matrix / state model / ADR)
- [ ] docs/traceability.md updated (requirement ⇄ backlog key ⇄ test id)
- [ ] All required CI checks green on the head commit
- [ ] No unresolved blocker (or blocker documented and item left open)

## Security checklist

- [ ] No password, token, cookie, session identifier, screenshot, DOM dump, UPN or tenant data
      added to the repo, logs, metrics, issue text or this PR
- [ ] No selector added outside `src/planner_mcp/browser/selectors/`
- [ ] No invented selector, tenant fact, license fact or capability attestation
- [ ] No mutating path can skip policy → approval → lock → apply → read-back
- [ ] No `SEC-*` control weakened (or ADR + maintainer sign-off included)
- [ ] No Microsoft Graph availability used as a functional gate (ADR-006)
- [ ] No live-tenant call introduced into CI
- [ ] Capability states advanced only with an evidence hash

## Evidence

<!-- Paste REAL command output. Do not paraphrase. Redact nothing that should not exist. -->

```
$ ruff check .
$ mypy --strict src
$ pytest -q
```

CI run: <url>

## Gates not run (and why)

<!-- Be explicit. Never claim a gate passed that did not run. -->

## Blockers

<!-- BLOCKER_CONDITIONAL_ACCESS / BLOCKER_UI_DRIFT / missing infrastructure / etc. -->
