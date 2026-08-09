# M365-JDS-001 — Phase A additive adoption evidence

Status: **IMPLEMENTED / PARITY NOT YET CLAIMED**

## Central platform pin

The consumer is pinned to the accepted immutable Jarvas Engineering Platform baseline:

```text
pestoura/jarvas-engineering-platform
9ee1147ea85bbb5bbb733d252bab9ccbb113f5ef
JDS-1.0
```

No mutable `main` reference is used by the M365 consumer workflow.

## Additive scope

Phase A adds:

- `.jarvas/engineering.yml` for `m365-ui-mcp`;
- explicit M365 capabilities covering documentation, Python, shell/config, repository security, packaging, containers, SBOM, isolated acceptance, browser automation and release evidence;
- `.github/workflows/jds-audit.yml` executing only the central change-aware planner and persisting its plan as evidence.

## Authority boundary

The existing `.github/workflows/ci.yml` remains authoritative.

No existing M365 job/check name is removed, renamed or relaxed. In particular the project-local controls remain mandatory until explicit Phase B parity evidence exists:

- Outlook/Planner contract validation;
- zero-public-Outlook-tool invariant while Outlook is `RESERVED`;
- no generic browser primitive/session-secret exposure;
- UIContract/capability consistency;
- isolated acceptance;
- mutation read-back/idempotency/policy tests;
- integration-wave Docker/Trivy/SBOM boundary;
- M365 privacy/session/identity invariants.

## Support-state boundary

JDS adoption does not alter product support state.

```text
OUTLOOK IMPLEMENTATION: MOCK/SYNTHETIC
OUTLOOK APPLICATION STATE: RESERVED
OUTLOOK LIVE ACCEPTANCE: UNOBSERVED
PUBLIC OUTLOOK TOOLS: 0
```

## Phase B entry gate

Phase B may begin only after the JDS planner executes successfully on a real M365 PR and its selected/skipped gates are captured. Central/local equivalence must then be classified per gate as one of:

```text
EQUIVALENT
PROJECT_STRONGER
CENTRAL_STRONGER
NOT_APPLICABLE
```

No local gate is retired by this Phase A change.
