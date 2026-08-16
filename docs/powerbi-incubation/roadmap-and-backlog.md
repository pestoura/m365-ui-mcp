# Power BI UI MCP — Roadmap and Backlog

Status: **PLANNED / INCUBATION**

## Advancement rule

Advance automatically while required gates are `GREEN`, `PASS`, `SUPPORTED` or `ACCEPTED`.

Stop only for a real blocker, including:

- failed CI/security gate;
- authentication or MFA that requires human action;
- Conditional Access or device-compliance blocker;
- missing UI evidence/attestation;
- ambiguous mutation result;
- destructive/high-risk action requiring explicit approval;
- capability absent from the target tenant/account;
- Microsoft service unavailable;
- UI contract drift that prevents deterministic execution.

A gate that did not execute is not green.

---

# PHASE 0 — Incubation freeze and integration preconditions

### `PBI-000` — Preserve design baseline

- retain architecture, authentication, capability catalogue and acceptance design;
- record target integration into future `m365-ui-mcp` version;
- do not disturb current Planner/Outlook delivery.

Gate: blueprint committed and reviewable.

### `PBI-001` — M365 predecessor completion gate

Before implementation begins:

- current `m365-ui-mcp` Planner/Outlook program reaches agreed acceptance baseline;
- baseline version/tag captured;
- no hidden in-flight transition work conflicts with Power BI integration.

Gate: M365 predecessor `GREEN`.

### `PBI-002` — Reconcile blueprint against final M365 core

Classify every assumption as:

```text
REUSE_AS_IS
REUSE_WITH_EXTENSION
SUPERSEDED
POWERBI_SPECIFIC
REQUIRES_REDESIGN
```

### `PBI-003` — Decide repository lifecycle

Preferred incubation repository name: `pestoura/powerbi-ui-mcp`.

Before Power BI integration begins, decide whether implementation stays temporarily standalone or is immediately imported into the future M365 version.

No duplicated long-term platform core is allowed.

---

# PHASE 1 — Dedicated Power BI worker foundation

### `PBI-010` — Power BI application registration in M365 core

Register application id `powerbi` in the shared application registry.

### `PBI-011` — Dedicated worker/container profile

Create isolated Power BI browser worker/container with independent:

- Chromium profile;
- state directory;
- evidence directory;
- screenshots;
- logs/metrics labels;
- health/readiness state.

### `PBI-012` — Power BI navigation contract

Support direct navigation to Power BI home/workspace/report/page URLs and classify resulting state.

### `PBI-013` — Power BI UI state machine

Implement and test states defined in `architecture.md`.

### `PBI-014` — Browser semantic locator baseline

ARIA/accessible role first, then stable DOM semantics, then bounded fallbacks.

### `PBI-015` — Evidence capture baseline

Before/after screenshot, DOM/semantic state, action journal and sanitized execution manifest.

Gate: worker health + navigation + state classification `PASS` in isolated test environment.

---

# PHASE 2 — Authentication and MFA

### `PBI-020` — Local credential resolver contract

Credentials remain inside trusted runtime; never exposed in MCP tool schemas/results/logs.

### `PBI-021` — Microsoft sign-in state detection

Recognize username, password, account-picker and session-reuse states.

### `PBI-022` — MFA Number Matching detection

Detect Microsoft Authenticator number-matching challenge and reliably extract the displayed number.

### `PBI-023` — Hermes Telegram notifier

Send minimal challenge notification through the existing Hermes Telegram path.

### `PBI-024` — MFA continuation observer

Remain in `MFA_PENDING` until browser evidence proves success, denial, timeout or blocker.

### `PBI-025` — Persistent bounded session

Reuse valid Power BI browser state while respecting Microsoft/tenant expiry and reauthentication requirements.

### `PBI-026` — Authentication acceptance

Prove login -> MFA notification -> human confirmation -> Power BI target loaded without storing secrets.

Gate: authentication acceptance `PASS`.

---

# PHASE 3 — Live read-only capability discovery

### `PBI-030` — Current context discovery

Return sanitized workspace/report/page ids, mode and supported surface context.

### `PBI-031` — Workspace/report/page inventory

Enumerate accessible UI resources without mutation.

### `PBI-032` — Visual inventory

Identify visible report visuals, types, titles, geometry and field/format metadata that can be safely observed.

### `PBI-033` — Filter/slicer inventory

Inspect filter and slicer state exposed through the UI.

### `PBI-034` — Edit capability probe

Determine whether edit mode exists without changing content.

### `PBI-035` — Semantic model capability probe

Determine whether model editing, DAX, TMDL, Power Query and RLS surfaces are visible/usable.

### `PBI-036` — Capability registry projection

Publish only attested Power BI capabilities with reason codes for unavailable features.

Gate: live read-only target produces complete capability/evidence manifest.

---

# PHASE 4 — Report editor primitives

### `PBI-040` — Enter/exit edit mode safely

### `PBI-041` — Page lifecycle primitives

Create/duplicate/rename/reorder/hide/show/delete with reversible acceptance fixtures.

### `PBI-042` — Visual lifecycle primitives

Create/select/duplicate/change type/delete.

### `PBI-043` — Field well manipulation

Assign/remove fields, aggregation, axis, values, legend and tooltip roles.

### `PBI-044` — Geometry engine

Move, resize, align and distribute visuals using semantic/geometry-aware control.

### `PBI-045` — Formatting engine

Titles, labels, axes, legend, backgrounds, borders, number formats, word wrap and conditional formatting where attested.

### `PBI-046` — Clipboard/keyboard acceleration

Use safe batch input/focus strategies when faster and more reliable than repeated pointer actions.

Gate: reversible report-edit acceptance suite `PASS`.

---

# PHASE 5 — Filters, slicers, interactions and navigation

### `PBI-050` — Filter primitives

Visual/page/report filters.

### `PBI-051` — Slicer primitives

Create/configure/select/clear.

### `PBI-052` — Visual interaction primitives

Cross-filter, cross-highlight and disabled interaction where supported.

### `PBI-053` — Drill-down/drillthrough

### `PBI-054` — Buttons and page navigation

### `PBI-055` — Bookmark lifecycle

Gate: interaction state is deterministic and evidence-backed.

---

# PHASE 6 — Developer fast paths

### `PBI-060` — DAX surface

Create/update/delete/validate measures and supported calculated objects.

### `PBI-061` — DAX bulk operation workflow

Apply sets of related measures as one logical transaction with before/after evidence.

### `PBI-062` — TMDL surface discovery

Attest whether TMDL view is available in the target experience.

### `PBI-063` — Script-existing/model bootstrap

Use Power BI generated TMDL from existing objects as canonical editing input when available.

### `PBI-064` — TMDL preview/apply/validate

Use preview before apply; journal the exact intended semantic change.

### `PBI-065` — Power Query / M surface discovery

### `PBI-066` — Advanced Editor M application

Apply query transformations through M when available and safer/faster than GUI steps.

### `PBI-067` — Developer surface fallback policy

Every fast path must define a capability-aware fallback or explicit unsupported result.

Gate: code-surface changes can be applied and independently verified in Power BI UI.

---

# PHASE 7 — Macros and report-as-spec

### `PBI-070` — Visual style templates

### `PBI-071` — KPI card macro

### `PBI-072` — Management table macro

### `PBI-073` — Sprint/operations page macro

### `PBI-074` — Normalize page/report macro

### `PBI-075` — Build report page from declarative spec

Example input:

```yaml
page: Sprint Overview
cards:
  - Total Activities
  - Completed
  - Overdue
  - Critical
charts:
  - type: bar
    category: Owner
    value: ActivityCount
slicers:
  - Sprint
  - Status
table:
  fields:
    - Activity
    - Owner
    - Status
    - DueDate
```

Gate: deterministic macro output validates against specification.

---

# PHASE 8 — Dashboards, distribution and advanced surfaces

Only implement capabilities proven available to the target tenant/account.

### `PBI-080` — Dashboard primitives

### `PBI-081` — Tile lifecycle

### `PBI-082` — Sharing/access primitives

### `PBI-083` — App/audience primitives

### `PBI-084` — Refresh lifecycle and history through UI

Gate: capability-specific acceptance and policy approval.

---

# PHASE 9 — Reliability, vision and self-healing

### `PBI-090` — UI contract fragmentation

Separate Power BI fragments by surface/capability.

### `PBI-091` — Drift detector

### `PBI-092` — Bounded locator self-healing

Never silently promote an unverified locator.

### `PBI-093` — Vision-assisted canvas recovery

Use screenshots/vision when semantic DOM evidence is insufficient, with explicit confidence/evidence requirements.

### `PBI-094` — Ambiguous mutation detector

### `PBI-095` — Performance metrics

Track latency, retry count, UI path selected, fast-path utilization, failure class and token/tool-call efficiency.

Gate: resilience suite `PASS`.

---

# PHASE 10 — M365 VNext integration/release

### `PBI-100` — Import/reconcile incubation implementation

### `PBI-101` — `powerbi` tool profile/projection

### `PBI-102` — Cross-app Planner -> Power BI workflows

### `PBI-103` — Cross-app Outlook -> Power BI workflows where justified

### `PBI-104` — M365 shared authentication/notification contracts

Share platform contracts, not browser sessions.

### `PBI-105` — Security/threat-model review

### `PBI-106` — Full live acceptance

### `PBI-107` — Release candidate

### `PBI-108` — Production promotion

Final gate: Planner + Outlook regressions GREEN and Power BI acceptance GREEN.
