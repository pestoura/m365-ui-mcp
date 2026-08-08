# CORE-010 — Tool profiles / projections

## Decision

The M365 control plane supports four closed exposure profiles:

```text
full
planner
outlook
read-only
```

A profile is an **exposure filter only**. It can remove tools from the MCP surface but cannot modify or weaken policy, risk class, approval requirements, idempotency semantics, implementation state or any other Tool Registry governance metadata.

## Current 0.1.0 projections

Because the current Tool Registry contains exactly 17 read-only Planner tools and no Outlook tools yet:

| Profile | Current exposed definitions |
|---|---:|
| `full` | 17 Planner tools |
| `planner` | 17 Planner tools |
| `read-only` | 17 Planner tools |
| `outlook` | 0 |

The `outlook` profile returning zero tools is intentional. Outlook remains `RESERVED` in the Application Registry until the core is stabilized and Planner parity is GREEN.

## Configuration

The canonical setting is:

```text
M365_TOOL_PROFILE
```

Default: `full`.

No `PLANNER_TOOL_PROFILE` alias is introduced because no equivalent Planner configuration existed before this migration. Legacy aliases are retained only where compatibility actually requires them.

## Security properties

- invalid profile names fail closed through typed configuration;
- projection preserves object identity/governance metadata;
- `read-only` selects only `MutationClass.READ` tools;
- profiles cannot convert a write into a read or remove approval requirements;
- application registrars still validate complete registry/binding parity before applying an exposure filter;
- no generic executor, browser primitive or session-secret surface is introduced.

Future Outlook and cross-app tools may change profile counts, but the filtering semantics remain fixed and policy is always evaluated independently of exposure.
