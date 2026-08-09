# M365 UI MCP — backlog audit and controlled extensions

Date: 2026-08-09

Status: **BACKLOG ENGINEERING / NO ACTIVE-WAVE INTERFERENCE**

This document records a live backlog/issue audit performed while the JDS delivery controller is independently executing the Outlook roadmap. It adds governance and future capabilities without changing the current feature-wave branches.

## 1. Execution boundary

At audit entry, `main` already contained Outlook Phase 8 Wave C (`OUT-036..040`). Wave D uses `integration/wave-d-out-041-046`.

During the audit, `OUT-041`, `OUT-042`, `OUT-043` and `OUT-044` were observed merging into the Wave D integration branch while `OUT-045` and `OUT-046` remained in-flight.

Therefore:

- no Wave D source file was edited here;
- no active feature PR was retargeted;
- new product capabilities below are `DEFERRED / NOT CURRENT WIP`;
- the controller remains authoritative for selecting the next executable slice.

## 2. Issue-tracker findings

### 2.1 Legacy Planner backlog duplication

The open tracker contains multiple GitHub issues for many historical `P-001..P-074` keys. The original issue generation is associated with milestone `0.1.0` and the numbered `epic:NN-*` taxonomy, while later generations introduced another epic/mutation label family and frequently no milestone.

This is a traceability/WIP problem, not a reason for immediate destructive cleanup.

Canonical remediation: **#356 — M365-BACKLOG-001**.

Rules:

1. generate a deterministic canonical key → issue map first;
2. preserve history;
3. close confirmed later copies as `duplicate` with a canonical pointer;
4. ambiguous mapping blocks rather than guessing;
5. add a uniqueness guard so duplicate canonical keys cannot be re-created silently.

### 2.2 Roadmap != execution queue

The transition roadmap intentionally describes the complete future product. Materializing every future entry as an open GitHub issue creates artificial WIP and repeats the Planner duplication failure mode.

Canonical remediation: **#358 — M365-CONTROL-001**.

Target model:

```text
ROADMAP            complete WHAT
EXECUTION INDEX    current/next bounded slices
GITHUB ISSUE       durable tracker only when needed
PR/WAVE             implementation/integration evidence
SUPPORT STATE       independent evidence-backed runtime claim
```

### 2.3 Central JDS is procedural, not yet executable in this repo

The M365 controller follows JDS operating rules, but `main` did not contain `.jarvas/engineering.yml` or a central `jarvas-engineering-platform` planner/composite reference at audit time.

Canonical remediation: **#357 — M365-JDS-001**.

Adoption is additive first. Existing M365-specific CI remains authoritative until parity is proven.

### 2.4 Release/milestone model is stale

GitHub exposes the historical Planner `0.1.0` milestone, while the canonical M365 roadmap already defines release planning bands through `1.0.0`.

Canonical remediation: **#368 — M365-RELEASE-001**.

Milestones are release boundaries, not active-WIP generators.

### 2.5 Open PR topology needs explicit classification

The repository can contain current wave PRs, long-lived foundation PRs and deliberate incubation PRs simultaneously. They must not all look equivalent to the controller.

Canonical remediation: **#369 — REL-027**.

## 3. Product capability extensions

These items extend the existing roadmap. They are intentionally not selected into the current Wave D.

| Key | Issue | Purpose | Initial posture |
| --- | --- | --- | --- |
| `OUT-141` | #359 | persistent Focused/Other sender preference | governed write / deferred |
| `OUT-142` | #360 | Search Folder discovery + predefined lifecycle | safe write / deferred |
| `OUT-143` | #361 | To Do list lifecycle + cross-list task movement | governed/destructive sub-action / deferred |
| `OUT-144` | #362 | To Do sharing, membership + assignment governance | high-risk governed write / deferred |
| `OUT-145` | #363 | scoped Microsoft 365 Group calendar operations | high-risk governed write / deferred |
| `OUT-146` | #364 | physical mail-folder delete/recovery safety | destructive / deferred |
| `OUT-147` | #365 | draft rich-body + inline-content semantic model | safe write / before outbound promotion |

Design constraints shared by all additions:

- semantic operations only; no generic browser primitive;
- capability/surface/account scope is explicit;
- ambiguity fails closed;
- UI evidence precedes live support;
- every mutation has read-back/uncertainty semantics;
- privacy/tenant content is excluded from normal evidence and telemetry;
- synthetic/mock GREEN never implies `SUPPORTED_LIVE`.

## 4. Engineering, resilience and assurance extensions

| Key | Issue | Purpose |
| --- | --- | --- |
| `CORE-051` | #371 | bounded UI capability-probe cache + safe revalidation |
| `CORE-052` | #372 | semantic latency budgets + phase-aware timeout/retry policy |
| `XAPP-029` | #373 | safe cross-app correlation registry |
| `REL-025` | #366 | evidence-backed support-state promotion automaton |
| `REL-026` | #367 | JDS delivery economics / CI waste budget |
| `REL-027` | #369 | active-wave orphan/stale PR and branch hygiene |
| `REL-028` | #370 | browser-session contamination/cross-account fault injection |
| `REL-029` | #374 | privacy-classified evidence retention/purge verification |
| `REL-030` | #375 | locator accessibility/drift fitness benchmark |

## 5. Recommended selection order

This is a prioritization recommendation, not an instruction to exceed WIP.

### Independent governance lane

1. `M365-CONTROL-001` — executable WIP index;
2. `M365-BACKLOG-001` — canonical issue map/duplicate cleanup;
3. `M365-JDS-001` — additive central JDS adoption;
4. `REL-026` — delivery metrics baseline so subsequent optimization is measurable.

### Before live-support promotion

1. `REL-025` — support-state promotion automaton;
2. `REL-028` — session/account isolation fault injection;
3. `REL-029` — privacy retention/purge contract;
4. `REL-030` — UI locator fitness.

### Before outbound send is promoted

`OUT-147` should be reconciled with the draft/outbound body contract before `OUT-050+` is considered complete for rich content. Plain-text behavior remains valid and backward compatible.

### Later product slices

Select `OUT-141..146` according to product value, dependency readiness and live surface evidence. Do not schedule all of them merely because issues now exist.

## 6. Definition of backlog health

The repository backlog is healthy when:

- every canonical key is unique;
- roadmap, execution index, issue, PR and evidence have distinct roles;
- current WIP is small and deterministic;
- deferred work is visible without appearing active;
- every active PR maps to one canonical key;
- stale/legacy work is explicitly classified;
- support state is evidence-backed and independent from merge state;
- new issues cannot silently duplicate historical keys;
- delivery cost/lead time can be measured without weakening gates.

## 7. Non-goals

This audit does **not**:

- promote Outlook from `RESERVED`;
- claim live Microsoft evidence;
- start Power BI implementation;
- change Planner public ABI;
- replace existing M365-specific quality/security/acceptance gates;
- instruct the active controller to abandon or restart the current Wave D.
