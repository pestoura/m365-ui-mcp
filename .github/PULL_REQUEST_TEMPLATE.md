## Scope

<!-- State the canonical P-XXX backlog item(s) and the concrete change. -->

Backlog: `P-XXX`

## Changes

- 

## Validation

- [ ] `python -m compileall -q src tests scripts`
- [ ] `ruff check .`
- [ ] `mypy`
- [ ] `pytest -q`
- [ ] `python scripts/check_docs.py` when documentation/traceability is affected
- [ ] Required CI/security/image/SBOM gates are GREEN/PASS

## Security and governance

- [ ] No secrets, credentials, tokens, cookies or tenant content are committed or exposed in evidence.
- [ ] No Conditional Access, MFA, device-enrolment or UI-attestation bypass is introduced.
- [ ] Microsoft Graph is not introduced as the Planner functional backend.
- [ ] No live capability is claimed without the required browser evidence and attestation.
- [ ] The 0.1.0 public tool surface remains read-only unless a later canonical release explicitly changes this contract.

## Evidence

<!-- Link the CI run(s), test evidence, artifacts and any required attestation. -->

## Blockers / residual risk

<!-- State "None" only when all mandatory gates executed and passed. -->
