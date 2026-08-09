# M365-JDS-001 — Phase A additive adoption evidence

Status: **IMPLEMENTED / ADDITIVE PLANNER GREEN / PARITY NOT YET CLAIMED**

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

## First real M365 planner execution

The first real M365 PR execution completed GREEN:

```text
PR:                 #390
JDS Audit run:      31306569764
head SHA:           715050e1d7780454747aef17ff68b87bfb0b024d
artifact:           jds-effective-plan
artifact id:        9036125856
artifact digest:    sha256:238ce7bd500039e1449c91082c04a12dee2017c63fd12417a35c2870b009524b
ambiguousImpact:    false
docsOnly:           false
changeSource:       git-diff
```

Changed files observed by the planner:

```text
.github/workflows/jds-audit.yml
.jarvas/engineering.yml
docs/m365-transition/evidence/m365-jds-phase-a.md
```

Selected capabilities:

```text
config.schema
docs.validate
release.evidence
security.sca
security.secret-scan
```

Selected gates:

```text
docs
evidence
sca
schema_validate
secret_scan
```

Capabilities correctly skipped for this change because their change-impact triggers were absent:

```text
browser.playwright
container.build
package.build
python.quality
runtime.isolated-acceptance
security.container-scan
security.sast
security.sbom
shell.quality
```

`security.secret-scan` was retained both by explicit capability declaration and mandatory JDS policy. `security.sast` was auto-detected into the effective capability set but remained skipped because the actual changed paths did not trigger it. The plan did not fall into ambiguous/fail-safe full-plan mode.

## Existing M365 gate evidence on the same PR

The additive planner did not replace the project pipeline. On the same head the existing checks also completed GREEN:

```text
CI run:                      31306569698
Canonical documentation:    31306569697
JDS Audit:                   31306569764
```

This proves Phase A execution without claiming central/local implementation parity.

## Preliminary Phase B classification

The first plan already supports the following evidence-backed classification of orchestration behavior:

| Concern | Classification | Evidence |
|---|---|---|
| change-aware gate selection | `CENTRAL_STRONGER` | JDS selected only docs/evidence/SCA/schema/secret for the actual three-file change while local CI still ran its complete fast feature pipeline |
| mandatory secret scanning | `EQUIVALENT_POLICY / IMPLEMENTATION_PARITY_PENDING` | both systems require a blocking repository secret invariant; implementation equivalence has not yet been benchmarked |
| M365 contracts/policy metadata | `PROJECT_STRONGER` | existing local CI includes M365-specific contract/schema and policy metadata gates not represented by the generic planner output |
| isolated acceptance | `PROJECT_STRONGER_FOR_THIS_CHANGE` | local CI executed project-specific isolated acceptance while JDS correctly skipped generic runtime acceptance for non-runtime paths |
| browser/live acceptance | `PROJECT_STRONGER / CENTRAL_PARITY_NOT_APPLICABLE_YET` | browser/live M365 controls remain project-local and Outlook remains unobserved live |

This is not authorization to retire local gates. Generic implementation parity still requires dedicated evidence before consolidation.

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

## Phase B continuation gate

Further Phase B work compares central generic implementations against existing M365 implementations and classifies each relevant gate as:

```text
EQUIVALENT
PROJECT_STRONGER
CENTRAL_STRONGER
NOT_APPLICABLE
```

No local gate is retired by Phase A or by the preliminary orchestration comparison above.
