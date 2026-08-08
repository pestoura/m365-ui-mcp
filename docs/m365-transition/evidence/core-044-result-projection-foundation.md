# CORE-044 — Result projection operators (parallel foundation)

Status: **PREIMPLEMENTED_AWAITING_DEPENDENCY_AND_GATES**

## Objective

Pre-implement the bounded result-reduction operators from CORE-044 while the governance lane continues through CORE-032..043. This work must not integrate into the execution plane or merge ahead of the CORE-043 dependency gate.

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

## Dependency boundary

This lane is intentionally developed and tested in parallel, but integration/merge remains blocked until CORE-043 is accepted. CORE-046 will later add secret-aware field classification; therefore CORE-044 does not make a claim that projection alone authorizes access to any field.

## Safety

- no browser primitive or network operation;
- no application/tool activation;
- no mutation;
- no approval bypass;
- no secret/session serialization;
- bounded `top_n` and pagination limits prevent unbounded projection expansion.

## Acceptance coverage

Tests cover select, count, exists, first, latest, top-n, pagination, metadata-only, input isolation and rejection of unbounded/ambiguous projection requests.
