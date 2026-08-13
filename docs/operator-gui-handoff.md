# Operator-only GUI handoff for m365-ui-mcp

Safe, loopback-only VNC view of the **worker profile** for an operator to complete
an interactive Microsoft sign-in by hand. Host-side only: it never touches the
control plane, Cloudflare, credentials, cookies, browser data, or M365 beyond the
single in-process `begin-signin` worker path.

This is the **fail-closed headed-browser one-off** handoff (replaces the earlier
host-Chromium model). It launches a SEPARATE headed one-off container from the
exact currently deployed browser-worker image, never the worker itself, and never
alongside the control plane.

Companion: [`browser-worker.md` (WORKER-120…135)](browser-worker.md),
implementation [`scripts/operator_gui_handoff.py`](../scripts/operator_gui_handoff.py).

## Scope (what this does NOT do)

- It does **not** deploy, stop production containers (except restarting
  `browser-worker` on stop/rollback), start a host Chromium, expose ports publicly,
  touch Cloudflare, read/write credentials, cookies, browser data, or contact M365
  except through the single operator-only `begin-signin` endpoint.
- It launches a **separate** host Xvfb + x11vnc + websockify/noVNC bound to
  `127.0.0.1` only.
- It launches a **separate** headed one-off container (`m365-ui-mcp-gui-browser`)
  from the deployed browser-worker image, on the `*m365-egress` network only, with
  **no published ports**, the same named volume RW, the same non-root image user
  (`1001:1001`), `cap-drop ALL`, `no-new-privileges`, memory/pids limits, and the
  image default entrypoint. No CDP, no remote-debugging.
- After the headed worker reports `/health` (probed via `docker exec` loopback), it
  invokes `POST /auth/bootstrap/begin-signin` **exactly once** inside the container
  (no URL args, no credentials, no retry). No other navigation/type/click happens.

## Preconditions (verified host capabilities)

| Capability | Required | Notes |
| --- | --- | --- |
| `Xvfb` | yes | dedicated `:99`, `-nolisten tcp` |
| `x11vnc` | yes | bound `127.0.0.1:5999` |
| `websockify` | yes | bound `127.0.0.1:6080`, serves noVNC |
| `docker` compose v2 | yes | only for stop/start of `browser-worker` and the one-off container |
| noVNC web | yes | `/usr/share/novnc` |
| host `chromium` / `setpriv` | **no** | not required by this design |
| loopback ports `5999`/`6080` | free | checked at preflight |
| profile uid/gid `1001:1001` | yes | verified INSIDE the healthy normal worker via `docker exec`/`stat` (never host mountpoint, never chown) |

## Commands

```bash
# Start (fail-closed). Refuses unless every precondition holds.
python scripts/operator_gui_handoff.py start

# Status: sanitized booleans + headed container name + loopback endpoint only.
python scripts/operator_gui_handoff.py status

# Stop: remove headed container first (profile flush), terminate host stack,
# then restart browser-worker and wait healthy.
python scripts/operator_gui_handoff.py stop
```

## Start contract (WORKER-121, WORKER-122, WORKER-130, WORKER-131)

`start` runs preflight checks in order; any failure aborts with no side effects:

1. production checkout `~/services/m365-ui-mcp` is clean with ONLY the generated
   `.jarvas/attest/` subtree allowed untracked (any tracked modification or other
   untracked path is rejected);
2. required host binaries present (`Xvfb`, `x11vnc`, `websockify`, `docker`);
3. loopback ports `5999` (VNC) and `6080` (websockify) are free;
4. no stale GUI one-off container (`m365-ui-mcp-gui-browser`) and no active handoff
   state file exist;
5. the expected `m365-ui-mcp-browser-worker-1` exists and is `healthy`;
6. profile ownership inside that healthy worker is exactly `1001:1001` (verified via
   `docker exec` + `stat` on `/var/lib/planner-worker/profile` and a representative
   persistent content entry).

On success it launches the host stack **Xvfb → x11vnc → websockify**, then waits
**fail-closed and bounded** for each host-stack readiness signal BEFORE touching the
normal `browser-worker`:

1. after Xvfb `:99` launches, wait for `/tmp/.X11-unix/X99` to exist as a Unix
   socket while Xvfb stays alive (bounded timeout/poll);
2. after x11vnc launches, wait bounded for `127.0.0.1:5999` to accept TCP while
   x11vnc stays alive;
3. after websockify launches, wait bounded for `127.0.0.1:6080` to accept TCP
   while websockify stays alive.

Only after all three readiness gates are GREEN does it gracefully stop ONLY the
normal `browser-worker`, verify it is `exited`, and launch the headed one-off
container. After the headed `/health` probe succeeds, `POST
/auth/bootstrap/begin-signin` is invoked exactly once inside the container. Any
readiness failure BEFORE the worker stop terminates only the already-launched host
stack (the worker is never restarted, because it was never stopped). Any failure
AFTER the worker stop rolls back in reverse order and restarts `browser-worker` to
healthy (WORKER-122, WORKER-133, WORKER-136…138).

## Headed one-off container (WORKER-124, WORKER-128, WORKER-129)

The container is created with an exact, reviewed `docker run`:

- `--name m365-ui-mcp-gui-browser`, `--network m365-ui-mcp_m365-egress` (egress only;
  never `browser-internal`, never alias `browser-worker`);
- **no `-p`** published ports; the control plane cannot route to it;
- `--volume m365-ui-mcp_browser-profile:/var/lib/planner-worker/profile:rw` and
  `--volume /tmp/.X11-unix:/tmp/.X11-unix:rw`;
- `--user 1001:1001`, `--cap-drop ALL`, `--security-opt no-new-privileges:true`,
  `--memory=2g`, `--pids-limit=512`;
- explicit minimal env only: `M365_MODE=live` (+`PLANNER_MODE=live`),
  `M365_BROWSER_HEADLESS=0` (+`PLANNER_BROWSER_HEADLESS=0`),
  `M365_BROWSER_PROFILE_DIR=/var/lib/planner-worker/profile`
  (+`PLANNER_BROWSER_PROFILE_DIR` mirrored), worker port, `DISPLAY=:99`. No
  container env/secrets are copied;
- image default entrypoint/CMD; no remote-debugging/CDP flags.

## Network exposure (WORKER-123)

- Xvfb: `-nolisten tcp` (unix socket only).
- x11vnc: `-listen 127.0.0.1 -rfbport 5999 -nopw`.
- websockify: binds `127.0.0.1:6080`, proxies to `127.0.0.1:5999`, serves
  `/usr/share/novnc`.
- noVNC is reachable only at `http://127.0.0.1:6080`. Nothing is exposed beyond
  loopback. The headed container publishes no ports and joins only egress.

## Begin-signin (WORKER-127, WORKER-132)

After the headed worker reports `/health` (probed via `docker exec` loopback),
`POST /auth/bootstrap/begin-signin` is invoked exactly once inside the container
with no URL args, no credentials, and no retry beyond the health wait. The operator
completes the real Microsoft sign-in by hand through noVNC. No other
navigation/type/click occurs.

## Stop contract (WORKER-125, WORKER-134)

`stop` removes the headed one-off container FIRST (profile flush), then terminates
the host GUI stack in reverse launch order (websockify → x11vnc → Xvfb), then
restarts **only** `browser-worker` and waits for healthy. The control plane is never
stopped, started, or referenced.

## State and secrets (WORKER-126, WORKER-135)

- State file `~/.cache/m365-gui-handoff/state.json` holds only PIDs, health
  booleans, the headed container name, `begin_signin_ok`, and the loopback endpoint
  — never the profile path contents, Microsoft page content, credentials, cookies,
  tokens, UPN, or URLs.
- No passwords/tokens are written to files or logs. The handoff performs the single
  operator-only `begin-signin` and never otherwise contacts M365.
