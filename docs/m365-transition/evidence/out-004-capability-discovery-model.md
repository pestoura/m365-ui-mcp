# OUT-004 — Outlook capability discovery model

Status: **PREIMPLEMENTED_STACKED_AWAITING_OUT_003**

## Objective

Introduce a bounded, evidence-neutral model for discovering Outlook capabilities without treating discovery as support or activating any public Outlook execution surface.

## Model

`m365_mcp.apps.outlook.discovery` defines closed discovery states:

- `UNOBSERVED`;
- `OBSERVED`;
- `BLOCKED`;
- `REATTESTATION_REQUIRED`.

The initial candidate set maps one semantic read/discovery capability to each OUT-003 shell target:

```text
mail.read       -> outlook.shell.mail
calendar.read   -> outlook.shell.calendar
people.read     -> outlook.shell.people
todo.read       -> outlook.shell.todo
settings.read   -> outlook.shell.settings
```

Every default candidate starts `UNOBSERVED` with no evidence digest.

## Evidence rules

An `OBSERVED` candidate requires a lowercase SHA-256 evidence digest. Any non-observed state carrying an evidence digest is rejected. Shell targets must match their exact `outlook.shell.*` contract key.

This model records only the existence/state of sanitized evidence. It stores no selector, tenant content, mailbox address, account identifier, cookie, token or storage state.

## Safety boundary

Discovery is not capability promotion. Outlook remains `RESERVED`, with zero public Tool Registry entries, zero effective Capability Registry entries and zero browser-operation activation. Later Outlook phases must separately attest evidence and promote capability support through the normal registries/gates.

## Dependency boundary

This work is stacked on OUT-003 and cannot merge until OUT-003 is merged and post-merge GREEN. It will then be retargeted to `main` and revalidated with fresh mandatory gates.
