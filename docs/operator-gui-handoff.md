# Operator-only GUI handoff for m365-ui-mcp

Safe, loopback-only VNC view of the already-running `browser-worker` profile for
an operator. Host-side only: it never touches the production containers' lifecycle
(the exception is restarting `browser-worker` on stop), Cloudflare, credentials,
cookies, browser data, or M365.

Companion: [`browser-worker.md` (WORKER-120…127)](browser-worker.md),
implementation [`scripts/operator_gui_handoff.py`](../scripts/operator_gui_handoff.py).

## Scope (what this does NOT do)

- It does **not** deploy, stop production containers, start GUI processes against
  production, expose ports publicly, touch Cloudflare, read/write credentials,
  cookies, browser data, or contact M365.
- It launches a **separate** host Chromium pointed at the named Docker volume
  profile, as the profile owner uid/gid `1001:1001`, with **no CDP**.
- It launches **separate** host Xvfb + x11vnc + websockify/noVNC bound to
  `127.0.0.1` only.

## Preconditions (verified host capabilities)

| Capability | Required | Found on host (verified) |
| --- | --- | --- |
| `Xvfb` | yes | `/usr/bin/Xvfb` |
| `x11vnc` | yes | `/usr/bin/x11vnc` |
| `websockify` | yes | `/usr/bin/websockify` |
| `chromium` | yes | `/usr/bin/chromium` |
| `setpriv` | yes (numeric uid launch) | `/usr/bin/setpriv` |
| noVNC web | yes | `/usr/share/novnc` |
| `docker` compose v2 | yes | `Docker Compose version 2.26.1` |
| profile uid/gid `1001:1001` | yes | Docker volume owns profile `1001:1001`; host has no such account (numeric launch) |

## Commands

```bash
# Start (fail-closed). Refuses unless every precondition holds.
python scripts/operator_gui_handoff.py start

# Status: sanitized booleans + loopback endpoint only.
python scripts/operator_gui_handoff.py status

# Stop: terminate GUI stack, then restart browser-worker and wait healthy.
python scripts/operator_gui_handoff.py stop
```

## Start contract (WORKER-121, WORKER-122)

`start` runs preflight checks in order; any failure aborts with no side effects:

1. required binaries present (`Xvfb`, `x11vnc`, `websockify`, `chromium`, `setpriv`, `docker`);
2. loopback ports `5999` (VNC) and `6080` (websockify) are free;
3. production checkout `~/services/m365-ui-mcp` is clean (no uncommitted changes);
4. `m365-ui-mcp-browser-worker-1` exists and is `healthy`;
5. profile ownership is exactly `1001:1001` (UID mismatch → reject);
6. no other live Chromium holds the profile (competing process → reject).

On success it launches **Xvfb → x11vnc → websockify → Chromium**. On any launch
failure it rolls the started processes back in reverse order and restarts
`browser-worker` to healthy (WORKER-122).

## Network exposure (WORKER-123)

- Xvfb: `-nolisten tcp` (unix socket only).
- x11vnc: `-listen 127.0.0.1 -rfbport 5999 -nopw`.
- websockify: binds `127.0.0.1:6080`, proxies to `127.0.0.1:5999`, serves `/usr/share/novnc`.
- noVNC is reachable only at `http://127.0.0.1:6080`. Nothing is exposed beyond loopback.

## Chromium launch (WORKER-124)

```text
setpriv --reuid 1001 --regid 1001 --clear-groups \
  chromium --display :99 --user-data-dir=<profile> --no-first-run \
  --no-default-browser-check --disable-background-networking \
  --disable-features=Translate,OptimizationHints,MediaRouter --disable-extensions
```

No `--remote-debugging-port`, no `--remote-debugging-pipe`, no CDP surface.
The profile is never `chown`ed; ownership is preserved.

## Stop contract (WORKER-125)

`stop` terminates the GUI stack in reverse launch order (Chromium → x11vnc →
websockify → Xvfb), then restarts **only** `browser-worker` and waits for healthy.
The control plane is never stopped, started, or referenced.

## State and secrets (WORKER-126, WORKER-127)

- State file `~/.cache/m365-gui-handoff/state.json` holds only PIDs, health
  booleans, and the loopback endpoint — never the profile path contents,
  credentials, cookies, tokens, or URLs.
- No passwords/tokens are written to files or logs. The handoff performs zero
  authentication and never contacts M365.
