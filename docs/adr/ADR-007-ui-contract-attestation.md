# ADR-007 — Centralized UI contract with attestation

- Status: Accepted
- Date: 2026-08-08

## Context

Selectors scattered through automation code are the classic failure mode of browser agents: they
rot silently, they get duplicated with subtle differences, they get invented from guesswork, and
when the UI changes the agent starts doing *something else* rather than stopping. Against a
corporate project tool, "something else" can mean deleting or rescheduling real work.

## Decision

1. **One contract.** Every selector, wait condition and extraction rule lives in
   `src/planner_mcp/browser/selectors/`. No selector may appear anywhere else in the codebase; a
   CI lint enforces this.
2. **No invented selectors.** A fragment's anchor values start empty and are filled only from a
   recorded observation of the live UI. A fragment whose `attestation_status` is
   `UNVERIFIED_LIVE` cannot be used: operations depending on it fail with `UNATTESTED_FRAGMENT`.
3. **Attestation with evidence.** Advancing a fragment requires an append-only record with
   operator id, locale, structure hash and evidence hashes (DOM snapshot, screenshot). Artifacts
   stay local; only hashes are committed.
4. **Drift fails closed.** Before each use, required anchors and the anchor-subtree structure hash
   are verified. Mismatch ⇒ `BLOCKER_UI_DRIFT`: the operation refuses, the capability drops to
   `UI_DRIFT`, the circuit opens. **No fallback selector is ever attempted.**
5. **Versioned.** The contract carries its own semantic version, returned on every UI-derived
   response and pinned for the duration of a reconciliation run.

## Consequences

- Availability is traded for safety: a Microsoft UI change stops the affected capability instead
  of misbehaving. This is the intended bias.
- Recovery is a human re-attestation plus a new contract version — deliberately not a hot patch in
  production.
- Selector strategy is constrained to accessible roles/names, stable test ids and structural
  anchors, which are more durable than class chains.
- Testing can assert the refusal path for unattested fragments, so the mock UI never has to
  fabricate capability that has not been observed.

## Related

[docs/ui-contract.md](../ui-contract.md), [docs/browser-worker.md](../browser-worker.md),
[docs/planner-premium-capabilities.md](../planner-premium-capabilities.md);
backlog P-014, P-015, P-016, P-017.
