# REL-025 — Evidence-backed capability promotion automaton

## Scope

REL-025 adds a repository-side, deterministic decision layer between sanitized live-probe
evidence and a future capability support-state promotion. It extends the existing attestation,
UIContract, capability-registry and evidence-freshness model; it does not drive a browser.

The automaton does **not**:

- expose cookies, tokens, DOM, URLs or tenant content;
- call Microsoft Graph;
- add a generic browser primitive;
- register or publish Outlook MCP tools;
- treat mock or synthetic evidence as live evidence;
- make REL-013..REL-016 optional.

## Machine-readable evidence contract

An input artifact is an exact JSON object with these required fields:

```json
{
  "application": "outlook",
  "surface": "outlook_web",
  "account_scope": "professional_session",
  "container_scope": "account",
  "capability": "mail.read",
  "environment_id": "tenant-test",
  "observed_at": "2026-08-11T18:55:00Z",
  "source": "LIVE_UI",
  "contract_set_digest": "sha256:<64-lowercase-hex>",
  "passed_gate_ids": ["REL-013", "policy", "egress", "selector", "readback"],
  "acceptance_ok": true,
  "readback_ok": true
}
```

Raw tenant/UI evidence is intentionally out of contract. The artifact carries bounded metadata
and digests only.

## Promotion decision

`src/m365_mcp/capability_promotion.py` returns one of four actions:

- `PROMOTE` — exact scope, live source, current UIContract digest, fresh evidence, all required
  gates, acceptance/readback and ordered dependencies are valid;
- `HOLD` — evidence is insufficient for promotion and there is no previously supported live
  state that must be invalidated;
- `RE_ATTESTATION_REQUIRED` — freshness or UIContract binding is invalid before promotion;
- `DEMOTE` — a previously `SUPPORTED_LIVE` capability has invalidating evidence and is moved
  fail-closed to `RE_ATTESTATION_REQUIRED`.

The only successful target state is `SUPPORTED_LIVE`. A valid evidence artifact still returns
`HOLD/LIVE_UNOBSERVED` while the ordered live acceptance dependencies are not accepted.

## Mandatory negative controls

Promotion is blocked for:

- `MOCK` or `SYNTHETIC` evidence;
- stale or future-dated evidence;
- wrong environment/tenant identifier;
- wrong capability/application/surface/account/container scope;
- UIContract digest drift;
- missing required gate IDs;
- failed acceptance or read-back;
- unmet REL-013..REL-016 acceptance dependencies;
- malformed, incomplete, duplicate-gate or ambiguous artifacts.

## CLI

`scripts/evaluate_capability_promotion.py` consumes one evidence JSON document and emits only a
sanitized decision. It exits `0` only for `PROMOTE`; all non-promotable decisions exit `3`, and
invalid input exits `4`.

Example repository-side evaluation:

```text
python scripts/evaluate_capability_promotion.py evidence.json \
  --environment tenant-test \
  --contract-set-digest sha256:<current-digest> \
  --required-gate REL-013 \
  --required-gate policy \
  --required-gate egress \
  --required-gate selector \
  --required-gate readback
```

Do not pass `--dependencies-accepted` until the canonical execution evidence proves the ordered
live acceptance dependencies. This preserves the current Outlook `LIVE_UNOBSERVED` boundary.

## Acceptance status

This lane proves the repository-side automaton and its negative controls only. REL-025 must not
be marked `ACCEPTED` from repository/mock evidence alone. End-to-end acceptance remains blocked
on genuine authenticated tenant/browser evidence from REL-013..REL-016.
