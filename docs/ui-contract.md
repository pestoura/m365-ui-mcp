# Planner MCP — UI Contract

Status: specification (implementation-grade). Every requirement is `PLANNED` unless a release note
says otherwise (`GOV-090`).
Canonical upstream: [docs/vision.md](./vision.md)
Related: [docs/architecture.md](./architecture.md) · [docs/security.md](./security.md) · [docs/privacy-boundary.md](./privacy-boundary.md) · [docs/governance.md](./governance.md) · [docs/browser-worker.md](./browser-worker.md) · [docs/planner-premium-capabilities.md](./planner-premium-capabilities.md)

Requirement IDs (`UI-xxx`) are stable, never reused, never renumbered.

---

## 1. Purpose and hard rules

**UI-001 — Single centralized registry.** All knowledge about the Planner Premium UI surface lives
in one versioned artefact, `contracts/ui_contract.json`, owned by the control plane and packaged
with the distribution (`ARCH-080`). No selector exists anywhere else in the codebase.

**UI-002 — Selectors are never invented.** A locator is written into the contract only after it has
been observed resolving against the live Planner UI and the observation has been recorded as
evidence. Plausible, inferred, documentation-derived or model-generated selectors are prohibited
(`ARCH-081`, `GOV-043`).

**UI-003 — Unverified entries are explicit.** An entry that has not been observed carries
`support_state: UNVERIFIED_LIVE` and a `null` locator set. Absence of a locator is never
interpreted as "try something reasonable".

**UI-004 — Never caller-supplied.** Selectors, XPaths, CSS strings and DOM fragments are never
accepted as MCP tool arguments and never returned through the public surface (`ARCH-021`,
`ARCH-023`, `SEC-005`).

**UI-005 — Fail closed on any contract doubt.** Version mismatch, missing entry, unattested entry,
ambiguous match, or a failed read-back stops the operation (`SEC-001`, `ARCH-130`).

**UI-006 — The contract is a governed artefact.** Changing a locator, an attestation state or a
support state is a reviewed change with evidence, not a code tweak (`GOV-040`…`GOV-045`).

---

## 2. Contract structure

**UI-010 — Contract-level fields.**

| Field | Meaning |
| --- | --- |
| `contract_version` | Semantic version of the whole contract; bumping invalidates prior attestation (`GOV-045`) |
| `ui_surface` | Which Planner surface the contract describes (e.g. Planner Premium web app) |
| `ui_surface_version_evidence` | Sanitized observation of the UI build/version signal, plus when it was captured; `UNVERIFIED_LIVE` when never observed |
| `locale_assumptions` | Locales the contract was attested under, and the locale-independence strategy used |
| `entries` | Map of capability key → capability entry (`UI-011`) |
| `attested_at` | Timestamp of the most recent successful attestation of this contract version |
| `evidence_refs` | Opaque references to sanitized attestation records; never raw screenshots or DOM |

**UI-011 — Entry-level fields.** Every entry declares, at minimum:

| Field | Meaning |
| --- | --- |
| `capability_key` | Stable domain key, matching a `CAP-xxx` row ([docs/planner-premium-capabilities.md](./planner-premium-capabilities.md)) |
| `locator_strategies` | Ordered list of semantic locator strategies (`UI-020`), or `null` when unverified |
| `expected_role` | ARIA role or structural role the target must expose |
| `expected_text` | Accessible-name expectation, expressed locale-resiliently (`UI-032`) |
| `expected_structure` | Structural expectation (container, ancestry, cardinality) |
| `preconditions` | Observable state that must hold before interaction (auth state, view, selection) |
| `postconditions` | Observable state that must hold after the operation |
| `read_back_probe` | The read used to verify the postcondition (`UI-060`) |
| `attestation` | `{state, timestamp, contract_version, evidence_ref}` (`UI-040`) |
| `support_state` | Lifecycle value (`UI-041`) |
| `mutation_class` | `READ` / `SAFE_WRITE` / `GOVERNED_WRITE` / `DESTRUCTIVE` (`SEC-020`) |

**UI-012 — No free text from the page in the contract.** Expectations are declared as matchers, not
as captured tenant content. Plan names, task titles and user names never enter the contract.

---

## 3. Locator strategies

**UI-020 — Allowed strategies, in strict preference order.**

1. Role + accessible name (`get_by_role`) — preferred, stable, locale-handled via `UI-032`.
2. Stable test/automation attribute exposed by the product, when one genuinely exists.
3. Label / form-control association (`get_by_label`).
4. Structural relation anchored on 1–3 (e.g. "the row containing X, then its role=button child").
5. Text matching, only when nothing above resolves.

**UI-021 — Forbidden strategies.** Positional CSS/XPath (`nth-child`, absolute paths), generated
class names, framework-internal identifiers, coordinate clicking, and any locator whose stability
depends on layout.

**UI-022 — Fallback limits.** An entry declares at most **three** ordered strategies. Fallback is
not a search: each fallback is itself attested. Exhausting the list fails closed with
`UI_LOCATOR_UNRESOLVED`. Runtime never improvises a fourth attempt.

**UI-023 — Ambiguity rule.** A locator that resolves to more than one element is an error
(`UI_LOCATOR_AMBIGUOUS`), never "take the first". Disambiguation must be expressed in the
contract as structure, not resolved at runtime.

**UI-024 — Zero matches.** Zero matches is `UI_LOCATOR_UNRESOLVED`, distinct from "element absent
because the state is different"; the latter is a precondition failure (`UI_PRECONDITION_FAILED`).

**UI-025 — Bounded waiting.** Each strategy has a configured timeout. Waiting is bounded and never
extended adaptively to force a match.

---

## 4. Locale resilience

**UI-030 — Locale is contract metadata.** The contract records the locales under which it was
attested. Running against a non-attested locale is a drift condition unless the entry is declared
locale-independent.

**UI-031 — Prefer locale-independent anchors.** Role, structure and stable attributes are preferred
precisely because they survive locale changes. Text matching is the last resort (`UI-020`).

**UI-032 — Text expectations are declared per locale.** When text is unavoidable, the entry carries
a locale→expected-name map; a missing locale entry fails closed rather than falling back to another
locale's string.

**UI-033 — No translation at runtime.** The system never translates, normalises or guesses a
localized label. Unknown label → `UI_LOCALE_UNSUPPORTED`.

**UI-034 — Locale changes invalidate text-based attestation** for the affected entries only, not
the whole contract, unless the contract version is bumped.

---

## 5. Attestation lifecycle

**UI-040 — Attestation record.** `{contract_version, capability_key, state, timestamp, operator,
tenant_kind, locale, evidence_ref}`. It contains no tenant content and no identity fields
(`GOV-041`, `PRIV-063`).

**UI-041 — Lifecycle states and the only forward path.**

```
UNVERIFIED_LIVE -> DISCOVERED -> UI_ATTESTED -> READ_ATTESTED -> MUTATION_ATTESTED -> SUPPORTED
                                     │              │                  │
                                     └──────────────┴──────────────────┴──> UI_DRIFT (terminal)
```

| State | Evidence required to enter |
| --- | --- |
| `UNVERIFIED_LIVE` | Default. No live observation exists. |
| `DISCOVERED` | The surface/element was observed to exist; locator not yet stable. |
| `UI_ATTESTED` | A declared locator resolved uniquely, with expected role/text/structure, in a recorded read-only observation. |
| `READ_ATTESTED` | A semantic read using the entry returned structurally valid data and its read-back probe confirmed it. |
| `MUTATION_ATTESTED` | A governed mutation using the entry took effect and was confirmed by read-back, with compensation demonstrated. |
| `SUPPORTED` | `MUTATION_ATTESTED` (or `READ_ATTESTED` for read-only capabilities) plus a governance decision to publish it (`GOV-010`). |
| `UI_DRIFT` | Any observation contradicting the attested expectation. |

**UI-042 — One step at a time, forward only, evidence-justified.** Skipping a state is prohibited
(`GOV-011`). Regression to `UI_DRIFT` is automatic and immediate (`GOV-012`).

**UI-043 — `UI_DRIFT` is terminal and fail-closed.** While an entry is in `UI_DRIFT`, every
operation depending on it is refused with `UI_DRIFT`. The only exit is re-attestation from
`DISCOVERED` upward, with fresh evidence, under a reviewed change.

**UI-044 — Attestation expires.** Attestation is invalidated by: a contract version bump, an
observed UI surface version change, a locale change affecting text anchors, a drift detection, or
the configured maximum attestation age (`GOV-044`, `GOV-045`).

**UI-045 — Attestation campaigns are read-only by default** and never run in CI against a real
tenant (`GOV-042`, `ARCH-084`).

---

## 6. Read-back probes, gates and drift detection

**UI-060 — Read-back probe definition.** Every entry that can be used for a mutation declares a
probe: a locator + expected postcondition + comparison rule, executed after the action, whose
success is the only evidence of success (`ARCH-101`, `SEC-006`).

**UI-061 — Read gate.** A semantic read requires the entry to be at least `UI_ATTESTED` in live
mode, with a matching `contract_version`. Otherwise `UI_CONTRACT_UNATTESTED`.

**UI-062 — Mutation gate.** A mutation additionally requires: `READ_ATTESTED` for the read-back
probe, a declared `mutation_class`, a policy `ALLOW`/consumed approval, and a verified
account/tenant context ([docs/authentication-and-mfa.md](./authentication-and-mfa.md) `AUTH-030`).
Missing any of these refuses the mutation.

**UI-063 — Unverified read-back is failure.** An unconfirmed postcondition is reported `UNVERIFIED`
and compensated where a compensation exists; it is never reported as success (`ARCH-132`).

**UI-064 — Drift detector.** Before use, and periodically, the worker validates the entry's
invariants: locator resolves uniquely, role matches, structural expectation holds, UI surface
version signal unchanged. Any violation raises `UI_DRIFT`, marks the entry, and blocks dependents.

**UI-065 — Drift is recorded as sanitized evidence** (which invariant failed, expected vs observed
*shape*), never as captured page content or a screenshot of authenticated UI (`PRIV-064`).

**UI-066 — Drift blast radius.** Drift on a shared anchor entry invalidates every entry that
depends on it. Dependency is declared in the contract, not inferred at runtime.

---

## 7. Evidence privacy

**UI-070 — No screenshots of authenticated content.** Ever, including for attestation and
debugging (`PRIV-064`).

**UI-071 — No raw DOM export.** DOM is never returned through the MCP surface, never written to
the state store, and never attached to audit events. Attestation may record a *structural digest*
(role/tag/cardinality shape) with all text and attribute values stripped.

**UI-072 — Redaction at capture time**, not at display time (`ARCH-110`, `PRIV-062`).

**UI-073 — Evidence references are opaque** and resolve only to sanitized records.

---

## 8. Selector package structure

**UI-080 — Layout.**

```
contracts/
  ui_contract.json          # the single versioned contract (UI-001)
  ui_contract.schema.json   # JSON Schema; validated in CI
  attestations/             # sanitized attestation records, append-only
```

**UI-081 — Schema validation is a blocking CI gate.** An entry missing `capability_key`,
`support_state`, `attestation` or `mutation_class` fails the build.

**UI-082 — Loading is strict.** Unknown fields, unknown states and unknown strategies are rejected
at load; the worker refuses to start with an invalid contract.

**UI-083 — Version pinning across zones.** The worker reports its loaded `contract_version` in
readiness; a mismatch with the control plane is `UI_DRIFT` (`ARCH-082`).

**UI-084 — `planner_ui_contract_status` exposes only** `contract_version`, per-capability
`support_state` and `attestation.state`, counts, and `attested_at`. Never locators.

---

## 9. Error classes

| Class | Meaning |
| --- | --- |
| `UI_CONTRACT_UNATTESTED` | Entry not attested to the level the operation requires |
| `UI_DRIFT` | Invariant violated or contract version mismatch; terminal until re-attested |
| `UI_LOCATOR_UNRESOLVED` | No declared strategy resolved within bounds |
| `UI_LOCATOR_AMBIGUOUS` | More than one match |
| `UI_PRECONDITION_FAILED` | Declared precondition not observed |
| `UI_READBACK_FAILED` | Postcondition not confirmed |
| `UI_LOCALE_UNSUPPORTED` | Locale not covered by the entry |

---

## 10. Tests

**UI-090** Schema validation of the shipped contract; every entry well-formed.
**UI-091** No selector string exists outside `contracts/` (repository-wide assertion).
**UI-092** Lifecycle transition tests: forward-only, no skipping, automatic `UI_DRIFT`.
**UI-093** Ambiguity and zero-match cases fail closed against a mock DOM.
**UI-094** Fallback cap of three is enforced.
**UI-095** Read gate and mutation gate reject under-attested entries.
**UI-096** Contract-version mismatch between zones yields `UI_DRIFT`.
**UI-097** Evidence serializer strips text, attributes and identity; screenshots impossible.
**UI-098** `planner_ui_contract_status` output contains no locator material.

---

## 11. Traceability

| ID range | Area |
| --- | --- |
| UI-001…006 | Hard rules |
| UI-010…012 | Contract structure |
| UI-020…025 | Locator strategies |
| UI-030…034 | Locale resilience |
| UI-040…045 | Attestation lifecycle |
| UI-060…066 | Read-back, gates, drift |
| UI-070…073 | Evidence privacy |
| UI-080…084 | Package structure |
| UI-090…098 | Tests |


