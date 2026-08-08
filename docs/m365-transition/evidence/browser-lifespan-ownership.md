# CORE-021 — FastAPI lifespan browser ownership

## Decision

The browser-worker ASGI process now explicitly owns the lifetime of the canonical `PersistentBrowser` through FastAPI lifespan.

Ownership is:

```text
FastAPI startup
    ↓
PersistentBrowser.start()
    ↓
Playwright.start()
    ↓
Chromium persistent context
    ↓
worker lifetime
    ↓
FastAPI shutdown / startup failure
    ↓
PersistentBrowser.stop()
    ↓
context.close()
    ↓
Playwright.stop()
```

There is exactly one browser object per application instance. It is available internally as `app.state.browser`; no browser object, page handle, context handle or session material is exposed over HTTP or MCP.

## Canonical ownership

The lifecycle primitive is application-neutral:

```text
src/m365_browser_worker/lifecycle.py
```

The canonical browser implementation remains:

```text
src/m365_browser_worker/browser.py
```

During staged migration, `planner_browser_worker.app.create_app()` uses this canonical lifecycle while preserving the historical Planner routes and compatibility package. `m365_browser_worker.app` continues to project the same ASGI application until the later adapter migration removes that compatibility layer.

## Startup semantics

`PersistentBrowser.start()` is idempotent.

In mock mode:

```text
start -> no Playwright process
stop  -> no Playwright process
```

In live mode the process owns both:

```text
Playwright
Chromium BrowserContext
```

Both references must exist for `browser.started == true`.

A partially inconsistent prior state is closed before a new start attempt.

If Chromium launch fails after Playwright has started, Playwright is stopped before the exception is propagated. FastAPI lifespan also invokes `stop()` if startup raises, providing a second deterministic cleanup boundary.

## Shutdown semantics

Shutdown clears process ownership before external cleanup and then:

1. closes the Chromium persistent context;
2. stops Playwright in a `finally` path.

Therefore a context-close exception cannot skip Playwright cleanup.

The lifecycle is not responsible for exporting cookies, tokens, storage state or profile content. None of those objects enter MCP/application state.

## Authorization boundary

Browser process ownership and semantic UI authorization are intentionally distinct.

Starting Chromium is infrastructure lifecycle; it does **not** attest a capability, authorize a Planner/Outlook operation or promote any capability to live support.

Semantic live operations continue to call the existing fail-closed UIContract guard. Current Planner fragments remain `UNVERIFIED_LIVE` until real evidence is collected through the controlled attestation workflow.

No new public endpoint bypasses that guard.

## Controlled egress boundary

`CORE-021` does not claim controlled Microsoft 365 egress and does not execute a live tenant campaign in CI.

The later `CORE-025` gate remains mandatory before automated live Microsoft 365 navigation/revalidation is enabled. The repository implementation here only establishes deterministic process ownership and cleanup.

CI runs exclusively in mock/test conditions and does not authenticate to a tenant.

## Failure behavior

The following fail closed:

```text
Playwright startup failure
Chromium launch failure
FastAPI lifespan startup failure
Chromium shutdown failure
```

Startup exceptions prevent the ASGI lifespan from becoming ready. Shutdown still attempts to release Playwright even when context closure fails.

Readiness semantics are deliberately not expanded here; true liveness/readiness is `CORE-022`.

## Security invariants

`CORE-021` introduces no:

- `browser_exec`;
- arbitrary click/selector action;
- JavaScript execution surface;
- XPath executor;
- raw-action endpoint;
- session export;
- cookies/tokens/storage-state export;
- Outlook capability;
- live tenant CI access.

The persistent professional profile remains the authentication boundary.

## Acceptance coverage

`tests/test_browser_lifecycle.py` verifies:

- FastAPI startup calls browser start exactly once;
- FastAPI shutdown calls browser stop exactly once;
- the browser object is bound only to internal `app.state`;
- startup failure triggers cleanup and does not yield a running lifespan;
- mock lifecycle launches no Playwright work;
- live start is idempotent when ownership already exists;
- stop closes Chromium and Playwright and resets ownership;
- Playwright still stops when context close raises;
- the lifecycle module exports no generic browser primitive.

Existing Planner worker route tests remain unchanged and must stay GREEN.

## Compatibility

No public MCP tool, Planner route semantics, capability key or selector is intentionally changed.

Invariants remain:

```text
17 planner_* public tools -> PRESERVE
11 Planner capability keys -> preserved
10 historical selector keys -> preserved
Outlook -> RESERVED / zero public tools
CORE-025 -> mandatory before automated live M365 egress
```

## Next gate

After PR and post-merge `main` are GREEN:

```text
CORE-021 PASS
    ↓
CORE-022 true liveness vs readiness
```
