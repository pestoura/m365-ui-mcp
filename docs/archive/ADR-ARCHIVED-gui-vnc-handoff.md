# Archived decision — GUI/VNC/noVNC/X11 headed handoff is rejected

Status: ARCHIVED / REJECTED. Superseded by the canonical headless path.

## Canonical authentication path

The canonical and only supported operator authentication path is:

- a private Chromium instance running **headless**,
- driven by **Playwright** through the worker's closed, fail-closed primitives,
- against the dedicated **persistent professional browser profile**,
- with credentials held in the local **encrypted credential store** (memory-only at use),
- and **MFA approval strictly out-of-band** in Microsoft Authenticator.

## Rejected alternative

An interactive **headed** handoff based on a graphical desktop surface
(GUI / VNC / noVNC / X11) was explored as a way to let a human complete the
Microsoft sign-in visually. It was evaluated and **explicitly rejected**:
it widened the runtime and network surface, depended on host graphical
components outside the worker trust boundary, and added supervision and
readiness failure modes without improving the authentication guarantees the
headless path already provides.

The active implementation, its tests and its operating documentation have been
removed from the repository. This record deliberately contains **no operating
instructions, no ports, no commands and no display/X11 setup**.

## Consequence

The GUI/VNC/noVNC/X11 headed handoff **MUST NOT** be used, reintroduced, or
referenced as an implementation path. Any authentication work continues on the
canonical headless Chromium + Playwright path described above.
