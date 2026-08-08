# Browser worker

FastAPI service, private network only, no published port.

- Mock mode (default, used by all tests and CI) serves deterministic fixtures.
- Live mode launches a persistent Chromium context via Playwright
  (`launch_persistent_context(user_data_dir=...)`) and fails closed until the UIContract is attested.
- Runs as the official Playwright image's existing `pwuser`; no custom user is added.
- Only `GET` routes exist; a test asserts no `POST/PUT/PATCH/DELETE` route is registered.
- `/health` reports mode, version, UIContract version and `live_ready`.
