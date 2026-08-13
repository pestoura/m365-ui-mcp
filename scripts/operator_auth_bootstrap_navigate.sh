#!/usr/bin/env bash
# OPERATOR-ONLY authentication bootstrap navigation wrapper.
#
# Triggers exactly ONE navigation of the dedicated persistent professional
# browser profile to the FIXED Planner Web bootstrap target so that an operator
# can complete an interactive Microsoft sign-in (including MFA) by hand.
#
# Hard invariants:
#   * this script is NOT an MCP tool and is NOT exposed over HTTP;
#   * it accepts NO arguments at all — in particular no URL, host, path or query.
#     The destination lives in the reviewed production constant
#     m365_browser_worker.bootstrap_navigation.PLANNER_WEB_BOOTSTRAP_URL;
#   * it reaches the worker endpoint only through `docker exec` on the worker
#     container's own loopback interface (127.0.0.1:8090). Port 8090 is never
#     published to the host or to the Docker network;
#   * it sends an empty body and no query string, as the endpoint requires;
#   * the response is sanitized by the worker: {ok,target_class,auth_state} only.
#     No URL, DOM, cookie, token, UPN or tenant id is ever printed.
#
# Usage (no arguments accepted):
#   scripts/operator_auth_bootstrap_navigate.sh
set -euo pipefail

CONTAINER="m365-ui-mcp-browser-worker-1"
ENDPOINT="http://127.0.0.1:8090/auth/bootstrap/navigate"

if [ "$#" -ne 0 ]; then
  echo "ERROR: this operator wrapper accepts no arguments (no URL input)." >&2
  exit 2
fi

exec docker exec "${CONTAINER}" \
  curl -sS -o - -w '\n' -X POST \
  -H 'Content-Length: 0' \
  --fail-with-body \
  "${ENDPOINT}"
