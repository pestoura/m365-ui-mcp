# Power BI UI MCP — Canonical Design Decisions

These decisions capture the current design baseline and should be challenged explicitly through ADRs rather than silently changed during implementation.

## DD-001 — Power BI is a future M365 module

Power BI is not an unrelated automation project. It is incubated separately to preserve focus, then integrated into a future version of `m365-ui-mcp` after the Planner/Outlook baseline is complete.

## DD-002 — No mandatory Graph/Dataverse/Power BI API dependency

The expected operational constraint is that Azure App Registration, Dataverse or privileged API connectors may not be available.

Therefore the product must remain useful through the normal authorized Power BI browser experience.

Official APIs may be evaluated later as optional acceleration backends, but absence of those APIs must not invalidate the core design.

## DD-003 — Dedicated Playwright isolation per application

Do not reuse a generic/shared Hermes browser session as the production runtime.

Use dedicated workers/containers and profiles for Planner, Outlook and Power BI. Hermes can still provide surrounding services such as notification/orchestration.

## DD-004 — MFA stays human-in-the-loop

For Microsoft Authenticator Number Matching:

1. Playwright reaches the MFA challenge;
2. the worker extracts the displayed number;
3. Hermes sends that number to Telegram;
4. the user enters/confirms it in Microsoft Authenticator;
5. the worker observes successful authentication and continues.

No MFA bypass or automatic Authenticator approval is permitted.

## DD-005 — Prefer developer surfaces inside the GUI

A normal user may perform an operation through dozens of clicks, but the automation should use higher-level developer surfaces whenever the authorized Power BI UI exposes them.

Priority examples:

- TMDL for model-level/bulk semantic changes;
- DAX editor for measures and calculated logic;
- Power Query M/Advanced Editor for transformations;
- keyboard/clipboard batch input for editors;
- semantic DOM/ARIA for UI controls.

This is still browser/UI-based operation; it simply uses the most efficient surface available to the user.

## DD-006 — Playwright is a domain driver, not a click recorder

Public operations express intent such as `powerbi_create_measure` or `powerbi_create_sprint_dashboard`.

LLMs should not orchestrate hundreds of raw pointer clicks. Deterministic domain workflows and internal primitives perform the low-level interaction.

## DD-007 — Capability discovery is tenant-specific

The driver must discover what the authenticated account can actually do in the target Power BI environment.

Never equate product documentation with live entitlement.

## DD-008 — Read-only first

The first live acceptance against the real report is discovery only:

- authenticate;
- identify workspace/report/page;
- enumerate pages/visuals/filter state;
- determine edit/model/developer-surface availability;
- capture evidence;
- make no content changes.

Mutation capabilities are promoted only using reversible test fixtures.

## DD-009 — Vision is fallback/validation, not the primary locator

Preferred order:

```text
ARIA/semantic DOM
stable component context
keyboard/clipboard
geometry-aware canvas
vision-assisted recovery
absolute coordinates
```

Vision is important for canvas/visual validation but should not replace deterministic semantics when they are available.

## DD-010 — Private/undocumented Power BI network APIs are not canonical backends

Browser network calls may be inspected for diagnostics, observability and understanding of state, but undocumented internal endpoints must not become the primary supported contract because they can change without notice.

## DD-011 — Compact public MCP, rich internal engine

Target approximately 40–60 high-value public Power BI tools backed by a much larger internal primitive/workflow catalogue.

Tool projection must minimize schema/token footprint without weakening policy.

## DD-012 — Evidence and fail-closed behavior are mandatory

Every mutation needs before/after evidence and independent verification.

Unknown UI state, UI drift, uncertain autosave outcome or ambiguous mutation result blocks progression.

## DD-013 — First business acceptance use case

After read-only discovery, the first meaningful build/automation scenario should reproduce a management/Sprint-style dashboard similar to the Security Technical reporting work discussed during design:

- KPI cards;
- activity status/critical/overdue measures;
- chart by owner;
- Sprint/status slicers;
- activity table;
- normalized layout and formatting.

This use case exercises model logic, visuals, formatting, slicers, interactions and validation in one controlled scenario.
