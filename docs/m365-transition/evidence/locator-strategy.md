# CORE-016 — Locator strategy abstraction

## Decision

UI execution locators now have a closed semantic model. The priority is:

```text
role + accessible name
label
placeholder
test-id fallback
CSS fallback
```

The model is contract metadata only. It does not expose generic `click`, raw selector, JavaScript, XPath or arbitrary Playwright execution through MCP or the browser-worker API.

## Fallback evidence rule

`test_id` and `css` are fallback strategies and require an explicit evidence digest in the form:

```text
sha256:<64 lowercase hex>
```

The digest is a reference to attestation evidence. A fallback without evidence fails validation. XPath-like or JavaScript-bearing values are rejected even when an evidence digest is present.

Accessible strategies do not carry fallback evidence and are always ordered before fallback candidates. Candidate order in source metadata cannot demote an accessible locator below CSS/test-id.

## Contract integration boundary

The current shipped UI fragments remain unchanged and contain no invented live locator values. Future fragment selector metadata may add a structured `locators` list; when present it must conform to the closed model.

The same model is available to the generic browser worker through `m365_browser_worker.locators`, but CORE-016 does not yet execute those locators. Browser operation protocol and lifecycle hardening remain later CORE blocks.

## Security invariants

- no XPath strategy;
- no JavaScript strategy;
- no arbitrary browser action endpoint;
- fallback requires evidence;
- duplicate candidates fail closed;
- unknown locator fields/strategies fail closed;
- no tenant content or authenticated session material is stored in locator metadata.
