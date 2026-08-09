# CORE-048 — Token/context economics metrics

Status: **IMPLEMENTED_AWAITING_CURRENT_BASE_GATES**

## Objective

Measure the economics of semantic result/context reduction using numeric counters only, without collecting prompt text, result text, Microsoft tenant content, or secret-bearing payloads.

## Numeric sample

`m365_mcp.context_economics.ContextEconomicsSample` accepts four non-negative counters supplied by the caller:

- `input_items`;
- `output_items`;
- `input_units`;
- `output_units`.

The unit is deliberately caller-defined so the same bounded metric model can represent measured tokens when available or another documented context-unit counter without introducing a tokenizer dependency into the control plane.

Derived metrics are:

- avoided items;
- avoided units, floored at zero;
- item reduction ratio;
- unit reduction ratio.

Zero-input samples produce zero ratios rather than division errors. Output item expansion is rejected because this metric specifically represents reduction operators; output units may exceed input units but never produce negative savings.

## Aggregation

`aggregate_context_economics()` sums only the four numeric counters and derives aggregate ratios from the resulting totals. It does not retain per-result content, tool arguments, prompts, completion text, resource identifiers, or labels with unbounded cardinality.

## Relationship to adjacent phases

- CORE-044 provides result projection/reduction operators.
- CORE-047 provides bounded execution provenance.
- CORE-048 measures reduction economics without inspecting content.
- CORE-049 adds UI execution metrics.
- CORE-050 adds drift/read-back/indeterminate metrics.

## Security/privacy boundary

The metrics API has no field for text, prompt content, result content, mailbox/account identity, Microsoft resource id, browser state, cookie, token, authorization header, or storage state. Metric projection contains numeric values only.

## Acceptance coverage

Tests prove:

- reduction counts and ratios are derived correctly;
- zero inputs are safe;
- unit expansion never produces negative savings;
- item expansion fails closed for this reduction metric;
- negative counters are rejected;
- aggregation retains only numeric totals.

## Dependency gate

CORE-047 is merged at `7816bbd97828ad960b79c6981bd594cb926d080e` and its complete post-merge `main` suite is GREEN, including functional gates, filesystem/dependency/secret scanning, both image builds, Trivy HIGH/CRITICAL scans and CycloneDX SBOM validation.

CORE-048 is therefore formally unblocked for integration. This revision creates a fresh head and re-triggers the complete mandatory gate suite against the current `main`; historical stacked/preventive runs are invalid as merge evidence.
