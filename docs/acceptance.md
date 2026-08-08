# Acceptance

## Isolated acceptance (mandatory, runs in CI)
`scripts/isolated_acceptance.py` starts the worker in mock mode in-process, exercises all 17 tools
through the control-plane implementation, and asserts:
- 17 tools present, all read-only
- readiness true, SQLite healthy
- UIContract unattested and fail-closed
- MFA metadata sanitized and Authenticator-only
- zero mutations performed
- versions aligned at 0.1.0

## Live read-only acceptance (separate, not in CI)
Manual campaign against the real tenant with an attested UIContract, read-only, evidence captured
outside the repository. Blocked until `P-045`/`P-050`.
