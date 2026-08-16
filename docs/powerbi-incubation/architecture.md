# Power BI UI MCP — Architecture

## 1. Architectural principles

1. **Browser-first, not API-dependent.** The product must operate with the capabilities exposed to a normal authorized Power BI user through the browser.
2. **Dedicated isolation.** Power BI gets its own browser worker/container and browser profile; no shared cookies or runtime state with Planner/Outlook.
3. **Developer fast paths before GUI repetition.** TMDL, DAX and Power Query M are preferred when exposed by the user's Power BI experience.
4. **Semantic operations, not raw clicks.** Public MCP tools represent Power BI intents and resources; low-level Playwright primitives remain private.
5. **Capability discovery before mutation.** Never assume a feature is available because Power BI supports it globally; attest what this tenant/account/report exposes.
6. **Fail closed on ambiguity.** Unknown UI state, drift, MFA ambiguity or uncertain mutation outcome is a blocker.
7. **Evidence-backed execution.** Every mutation records before/after state and evidence sufficient to prove the intended effect.

## 2. Logical components

```text
+---------------------+
| ChatGPT / Codex     |
+----------+----------+
           |
           v
+-------------------------------+
| m365-ui-mcp control plane     |
| - tool registry               |
| - policy                      |
| - capability projection       |
| - audit/redaction             |
+---------------+---------------+
                |
                v
+-------------------------------------------+
| Power BI domain adapter                   |
| - intent orchestration                    |
| - state machine                           |
| - macro/workflow engine                   |
| - validation/recovery                     |
+----------------+--------------------------+
                 |
       +---------+---------+
       |                   |
       v                   v
+--------------+   +------------------------+
| Fast paths   |   | UI automation engine   |
| TMDL         |   | ARIA/DOM               |
| DAX          |   | keyboard/clipboard     |
| Power Query M|   | canvas/geometry        |
+------+-------+   | vision fallback        |
       |           +-----------+------------+
       +-----------------------+
                               v
                  +-------------------------+
                  | Dedicated Power BI      |
                  | Playwright/Chromium     |
                  | worker + browser profile|
                  +------------+------------+
                               |
                               v
                        Power BI Service
```

## 3. Interaction hierarchy

For each operation choose the highest safe level available:

```text
FAST-1  TMDL / model scripting
FAST-2  DAX code editor
FAST-3  Power Query M / Advanced Editor
FAST-4  direct semantic DOM/ARIA operation
FAST-5  keyboard + clipboard batch operation
UI-1    structured pane/menu interaction
UI-2    geometry-aware canvas operation
REC-1   screenshot/vision-assisted recovery
LAST    absolute coordinates
```

Absolute coordinates must never be the primary locator strategy for a supported capability.

## 4. UI state machine

Minimum states:

```text
UNAUTHENTICATED
AUTHENTICATING
MFA_PENDING
AUTHENTICATED
POWERBI_HOME
WORKSPACE
REPORT_READING
REPORT_EDITING
MODEL_READING
MODEL_EDITING
TMDL_VIEW
POWER_QUERY
DASHBOARD
APP_EDITOR
DIALOG
BLOCKED
```

Every semantic operation declares accepted entry states, expected transitions and terminal success evidence.

## 5. Recovery model

```text
ACTION
  -> VERIFY
      -> PASS: continue
      -> FAIL: classify
          -> retryable transient: bounded retry
          -> recoverable state mismatch: recover + retry
          -> UI drift: mark capability stale/drifted
          -> auth/MFA: authentication workflow
          -> ambiguous mutation: stop/fail closed
          -> tenant/policy blocker: BLOCKED
```

## 6. Isolation

Recommended runtime layout:

```text
m365-control-plane
planner-browser-worker
outlook-browser-worker
powerbi-browser-worker
```

Power BI worker isolation includes:

- independent container/process;
- independent browser user-data directory/profile;
- independent cookie/session persistence;
- independent state/evidence directory;
- independent screenshots;
- independent logs and metrics labels;
- bounded network egress;
- no direct public ingress;
- secrets resolved locally and never returned to MCP clients.

## 7. High-level public surface

The external MCP surface should remain compact while internal primitives can be extensive.

Example public families:

```text
powerbi_session_*
powerbi_discover_*
powerbi_workspace_*
powerbi_report_*
powerbi_page_*
powerbi_visual_*
powerbi_filter_*
powerbi_slicer_*
powerbi_interaction_*
powerbi_bookmark_*
powerbi_model_*
powerbi_dax_*
powerbi_tmdl_*
powerbi_query_*
powerbi_rls_*
powerbi_refresh_*
powerbi_validate_*
```

Internally these may map to 100+ typed primitives and reusable macros.

## 8. Macro layer

Examples:

```text
powerbi_macro_create_kpi_card
powerbi_macro_create_management_table
powerbi_macro_create_sprint_page
powerbi_macro_normalize_page
powerbi_macro_apply_visual_style
powerbi_macro_build_report_from_spec
```

Macros are deterministic orchestrations over typed primitives; they are not free-form coordinate scripts.
