# Testing

- `python -m compileall -q src tests`
- `ruff check .`
- `mypy`
- `pytest` (mock mode is the default; no network, no real Planner)
- Release contract validation: `tests/test_release_contract.py`
- Isolated acceptance: `scripts/isolated_acceptance.py`

CI never mutates real Planner and never performs live sign-in. Live read-only acceptance is a
separate, manually triggered campaign documented in `docs/acceptance.md`.
