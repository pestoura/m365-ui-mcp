# PLN-MIG-010 / 011 / 012 — readiness assessment (no live authentication)

Status: **PREPARED_NOT_ATTESTED**

This document states exactly how far Planner parity can be evidenced without live authenticated Microsoft 365 access, and marks the dependent gates that are blocked. It makes no live-support claim and promotes no capability.

## Baseline this assessment is derived from

- preserved public ABI: 17 `planner_*` tools (`PLANNER_PUBLIC_TOOL_NAMES`), canonical order frozen in PLN-MIG-006;
- mock parity: PLN-MIG-008 (`tests/data/planner_mock_parity_baseline.json`);
- policy parity: PLN-MIG-009 (`tests/data/planner_policy_parity_baseline.json`, digest `sha256:105dd28c38b7b42fcf957b9b0622640827b0e4ea7a524ca94e0c364b4fe715bf`);
- runtime mode of every executed gate: `PLANNER_MODE=mock`, `Settings().allow_mutations is False`, no Graph API.

## PLN-MIG-010 — live read parity

Preparable without live auth (done):

- the exact read surface under test is frozen: all 17 tools are `MutationClass.READ` with `compatibility_requirement=PRESERVE`;
- the envelope/shape contract each live read must satisfy is frozen by the mock parity snapshot and by the semantic output schemas (`graph_api_used = {"const": false}`, `read_only = {"const": true}`);
- governance under which a live read may run is frozen and regression-checked (decision, security tier, capability keys, canonical policy scope);
- fail-closed behavior for unregistered names and mismatched scope is covered by tests.

Not evidenceable here:

- no live response was fetched, compared or attested. Effective capability projection with `live_evidence=False` deliberately keeps every Planner capability at `UNVERIFIED_LIVE` / `supported=false` / `LIVE_EVIDENCE_ABSENT`.

**Gate `PLN-MIG-010.live-read-attestation`: BLOCKED.**
Blocker: no authenticated Planner/Project for the web browser session is available in this lane (interactive Microsoft Entra sign-in + MFA required, plus a licensed tenant account). Until an attested live session exists, live read parity cannot be measured and must not be asserted.

## PLN-MIG-011 — mutation parity

Final baseline state: **no write/mutation tool is promoted**. The preserved surface contains 17 read tools and zero mutation tools; `Settings.allow_mutations` is `False`; the compatibility `mutation=True` path denies all 17 with `MUTATIONS_DISABLED_IN_0_1_0`; unregistered write-shaped names such as `planner_task_create` are denied `TOOL_NOT_REGISTERED`.

**Classification: N/A — not applicable in the current baseline.**
There is no mutation surface to reach parity with, so mutation parity is neither PASS nor FAIL and no mutation support is claimed or implied. This gate only becomes measurable if a future increment explicitly promotes writes into the public ABI; at that point it additionally inherits the PLN-MIG-010 live-authentication blocker.

## PLN-MIG-012 — acceptance

Achieved without live auth:

- deterministic local acceptance: `scripts/isolated_acceptance.py` GREEN;
- full local gate set GREEN (compileall, ruff, mypy, check_docs, check_contracts, pytest, isolated_acceptance, check_no_secrets);
- ABI, mock-shape and governance baselines all frozen, regenerable and byte-stable;
- no secret, token, cookie, storage-state, mailbox, tenant or filesystem material in any baseline or projection.

Not achieved:

- acceptance that depends on PLN-MIG-010 live read attestation, and any acceptance criterion phrased as "behaves identically against the live product".

**Gate `PLN-MIG-012.live-acceptance`: BLOCKED (transitively, on `PLN-MIG-010.live-read-attestation`).**
The mock/governance portion of acceptance is complete; the live portion cannot be signed off in this lane.

## Truthfulness boundary

Everything above is derived from reviewed metadata and mock-mode execution. Nothing in this document attests live Microsoft 365 behavior, and no capability state is promoted to `READ_SUPPORTED` or `MUTATION_SUPPORTED`.
