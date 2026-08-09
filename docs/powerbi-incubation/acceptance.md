# Power BI UI MCP — Acceptance Strategy

## Principles

- begin read-only;
- use a real authorized Power BI target only after authentication gates are proven;
- mutations must be reversible and evidence-backed;
- do not promote capabilities from mock-only success;
- live tenant capability is discovered, not assumed;
- fail closed on ambiguous state or mutation outcome.

## Acceptance target A — existing report, read-only

Known target identifiers from the design session:

```text
workspace: 3ae2d9a3-b405-4152-a1c8-879a7ccb21d3
report:    7acf5f37-10ba-470b-935f-c41b72cd58c8
page:      eed2ea3adc9cb7d90157
```

### `PBI-ACCEPT-001` — Authentication and context

```text
01 dedicated Power BI worker healthy
02 target URL reachable
03 Microsoft authentication state correctly detected
04 stored session reused if valid
05 username/password flow executes locally if required
06 MFA Number Matching detected if required
07 challenge notification delivered through Telegram
08 human Authenticator approval observed
09 authenticated Power BI state proven
10 workspace/report/page context matches target
11 screenshot + semantic evidence captured
```

Expected result: `PASS` with zero report mutations.

### `PBI-ACCEPT-002` — Read-only report inventory

```text
01 report title/context
02 reading/edit mode capability
03 pages enumerated
04 current page identified
05 visuals enumerated
06 visible titles/types/geometry captured where possible
07 filters/slicers inventoried
08 panes and major UI surfaces classified
09 capability manifest persisted
10 no mutation occurred
```

### `PBI-ACCEPT-003` — Safe edit-mode probe

```text
01 enter edit mode if available
02 prove report editor state
03 detect canvas
04 enumerate page/visual editor surfaces
05 detect formatting/build panes
06 exit without intentional changes
07 prove no mutation/autosave delta
```

If edit mode is not available, classify the reason and do not fail the read-only capability set.

## Acceptance target B — reversible test report/page

A dedicated reversible fixture must be used before any write capability is promoted.

### `PBI-ACCEPT-010` — Page lifecycle

Create -> verify -> rename -> verify -> duplicate -> verify -> delete fixture(s) -> verify clean state.

### `PBI-ACCEPT-011` — Visual lifecycle

Create card/chart/table fixture -> verify -> change type -> verify -> duplicate -> verify -> delete -> verify.

### `PBI-ACCEPT-012` — Field assignments

Assign/remove category/value/legend/tooltip fields and verify rendered/configuration state.

### `PBI-ACCEPT-013` — Geometry and formatting

Move/resize/align, change title/labels/number format/word wrap and verify visual result.

### `PBI-ACCEPT-014` — Filter/slicer interactions

Create/apply/clear and verify expected page/visual state.

## Acceptance target C — model/developer surfaces

Only run if live capability discovery marks the surface available.

### `PBI-ACCEPT-020` — DAX measure

Create a uniquely named harmless test measure -> verify presence/expression -> use in fixture visual -> remove -> verify cleanup.

### `PBI-ACCEPT-021` — TMDL

Open TMDL -> script/inspect existing fixture object if supported -> preview a bounded reversible change -> apply -> independently verify in model UI -> revert -> verify cleanup.

### `PBI-ACCEPT-022` — Power Query M

Use a dedicated test query/model. Open Advanced Editor if supported -> apply bounded transformation -> validate -> apply -> verify -> revert.

## Acceptance target D — macro/spec execution

### `PBI-ACCEPT-030` — Sprint management page

Build from declarative spec:

- KPI cards;
- owner chart;
- sprint/status slicers;
- activity table;
- layout normalization;
- interaction validation.

Expected result: page matches declared structure and all operations are journalled.

## Evidence manifest

Each acceptance run should capture a sanitized manifest similar to:

```json
{
  "run_id": "...",
  "application": "powerbi",
  "capability": "...",
  "ui_contract_digest": "...",
  "entry_state": "...",
  "exit_state": "...",
  "interaction_path": "TMDL|DAX|M|DOM|CANVAS|VISION",
  "retries": 0,
  "result": "PASS",
  "evidence": ["before", "after", "semantic_state"],
  "secrets_present": false
}
```

## Promotion rule

A capability is `SUPPORTED` only when:

1. implementation exists;
2. security/static tests pass;
3. isolated acceptance passes;
4. live UI evidence exists for the target surface;
5. mutation outcome is independently verified where applicable;
6. no unresolved drift/ambiguity remains.
