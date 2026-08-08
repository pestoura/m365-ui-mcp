#!/usr/bin/env bash
# Fail the build if credential-shaped material appears in tracked files.
# This complements gitleaks with product-specific rules.
set -euo pipefail

cd "$(dirname "$0")/.."

patterns=(
  'MICROSOFT_PASSWORD'
  'PLANNER_PASSWORD'
  'ENTRA_PASSWORD'
  'BEGIN [A-Z ]*PRIVATE KEY'
  'refresh_token'
  'ESTSAUTH'
  'x-ms-refreshtokencredential'
  'Authorization: Bearer '
)

status=0
files=$(git ls-files -- . ':!:scripts/check_no_secrets.sh')

for pattern in "${patterns[@]}"; do
  if matches=$(printf '%s\n' "$files" | xargs -r grep -InE "$pattern" 2>/dev/null); then
    echo "FAIL forbidden pattern '${pattern}':"
    echo "$matches"
    status=1
  fi
done

# Committed browser profile or session state is always a failure.
if printf '%s\n' "$files" | grep -qE '(^|/)(browser-profile|profiles)/|\.har$|storage_state.*\.json$'; then
  echo "FAIL browser profile or session state is tracked in git"
  status=1
fi

if [ "$status" -eq 0 ]; then
  echo "no forbidden credential patterns found"
fi

exit "$status"
