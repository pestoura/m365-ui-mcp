# Governance

- Semantic versioning across product, schema and contract versions (all `0.1.0` today).
- Every change must keep `tests/test_release_contract.py` green.
- Mutation-capable tools require: attested UIContract, approval policy, saga/compensation design,
  idempotency class, and an explicit ADR.
- Backlog is canonical in `docs/backlog.json`; `docs/backlog.md` is the human view.
- Security controls that are incomplete are documented as incomplete with a backlog ID; never as done.
