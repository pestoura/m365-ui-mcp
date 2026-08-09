# CORE-044 — Result projection operators

Status: **INTEGRATED_ON_MAIN**

## Objective

Implement the bounded result-reduction operators from CORE-044 after completion of the governance/execution foundation through CORE-043.

## Implemented operators

The pure `m365_mcp.result_projection` module defines a closed projection vocabulary:

- `select` — retain only explicitly requested fields;
- `count` — return input cardinality;
- `exists` — return whether any row exists;
- `first` — return at most one first row;
- `latest` — return at most one row using an explicit sort field;
- `top_n` — return at most 100 rows;
- `pagination` — bounded offset/limit window, maximum page size 100;
- `metadata_only` — return count metadata without row values.

Projection is pure: it receives already-produced semantic rows, cannot fetch more data and has no browser/session dependency.

## Dependency gate

CORE-043 is merged and post-merge GREEN on `main` at `4e732e7c5758559c9fbb8c56edcc43d985e48531`. CORE-044 is therefore formally unblocked for integration.

This revision intentionally re-triggers the complete mandatory CI/security/image/Trivy/SBOM/documentation suite against the current integration base. Historical stacked CI is not reused as merge evidence.

CORE-046 adds secret-aware field classification; CORE-044 therefore does not claim that projection alone authorizes access to any field.

## Safety

- no browser primitive or network operation;
- no application/tool activation;
- no mutation;
- no approval bypass;
- no secret/session serialization;
- bounded `top_n` and pagination limits prevent unbounded projection expansion.

## Acceptance coverage

Tests cover select, count, exists, first, latest, top-n, pagination, metadata-only, input isolation and rejection of unbounded/ambiguous projection requests.

## Integration reconciliation

This requirement's delta is present in `main`. The mandatory CI gate set (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) was GREEN on the merged pull request, and the full gate set was re-executed on post-merge `main` at `9b4a645`.

Mock mode only: no live Microsoft tenant was contacted, no capability is promoted to SUPPORTED by this record, Outlook stays RESERVED, and the 17-tool Planner public ABI is unchanged.
