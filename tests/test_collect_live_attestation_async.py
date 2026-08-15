"""Regression tests for scripts/collect_live_attestation_observation.py.

Locks the two live-correctness invariants that the canonical collection script
must satisfy:

* (async-correct) the injected live probe MAY be an async locator probe; it is
  awaited before its match count is consumed. A synchronous test double must
  still work (backward compatibility).
* (canonical import) ``load_ui_contract_set`` is imported from
  ``m365_mcp.ui_contract_store`` (its canonical module), NOT from
  ``m365_mcp.attestation`` (which does not define it).

The async test fails on the pre-fix code (``int(coroutine)`` TypeError) and
passes after the fix.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

from m365_mcp.attestation import AttestationLevel, ObservationSource
from m365_mcp.attestation_collection import collect_structural_observation
from m365_mcp.ui_contract_store import load_ui_contract_set

ROOT = Path(__file__).resolve().parent.parent


def _load_script_module():
    """Load the operator script by absolute path (CI-proof, like existing tests)."""
    script_path = ROOT / "scripts" / "collect_live_attestation_observation.py"
    spec = importlib.util.spec_from_file_location(
        "_collect_live_attestation_observation_regression", str(script_path)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contract_loader_imported_from_ui_contract_store() -> None:
    # Defect (1) regression lock: the canonical contract loader must be sourced
    # from m365_mcp.ui_contract_store, and attestation must not define it. The
    # operator script delegates building to m365_mcp.attestation_collection, which
    # imports load_ui_contract_set from the canonical module.
    module = _load_script_module()
    assert hasattr(module, "collect_structural_observation")
    from m365_mcp.attestation_collection import (
        load_ui_contract_set as shared_loader,
    )

    assert module.collect_structural_observation is collect_structural_observation
    assert shared_loader is load_ui_contract_set
    import m365_mcp.attestation as attestation_mod

    assert not hasattr(attestation_mod, "load_ui_contract_set")


async def test_async_live_probe_is_awaited_before_count() -> None:
    # Defect (2) regression: an async probe must be awaited, not coerced via int().
    module = _load_script_module()

    async def async_probe(selector_key, metadata):  # noqa: ARG001 - structural stub
        await asyncio.sleep(0)
        return 1

    observation = await module.collect_structural_observation(
        "common.auth.email", AttestationLevel.DISCOVERY, live_probe=async_probe
    )
    assert observation.source is ObservationSource.LIVE_UI
    assert observation.selector_observations
    for item in observation.selector_observations:
        assert item.result.value == "UNIQUE_MATCH"
        assert item.structural_digest.startswith("sha256:")


async def test_sync_live_probe_still_supported() -> None:
    # Backward-compat: a synchronous test double is not awaited; contract intact.
    module = _load_script_module()

    def sync_probe(selector_key, metadata):  # noqa: ARG001 - structural stub
        return 1

    observation = await module.collect_structural_observation(
        "common.auth.email", AttestationLevel.DISCOVERY, live_probe=sync_probe
    )
    assert observation.source is ObservationSource.LIVE_UI
    for item in observation.selector_observations:
        assert item.result.value == "UNIQUE_MATCH"


def test_supported_fragments_resolve_to_real_fragments() -> None:
    # AUTH-107 regression: the two atomic common.auth.* fragments replaced the
    # legacy single ``common.auth`` fragment. Every SUPPORTED_FRAGMENTS entry must
    # resolve to a real fragment id in the current UIContract set; the removed
    # ``common.auth`` id must NOT be present.
    module = _load_script_module()
    contract_set = load_ui_contract_set()
    known = {fragment.fragment_id for fragment in contract_set.fragments}

    assert "common.auth" not in module.SUPPORTED_FRAGMENTS
    assert "common.auth.email" in module.SUPPORTED_FRAGMENTS
    assert "common.auth.password" in module.SUPPORTED_FRAGMENTS
    for fragment_id in module.SUPPORTED_FRAGMENTS:
        assert fragment_id in known, f"SUPPORTED_FRAGMENTS has unknown id: {fragment_id}"


def test_legacy_common_auth_fragment_is_rejected() -> None:
    # The legacy ``common.auth`` fragment no longer exists; a campaign built for
    # it must fail closed rather than silently collecting against a phantom id.
    contract_set = load_ui_contract_set()
    import pytest

    from m365_mcp.attestation import build_attestation_campaign

    with pytest.raises(ValueError):
        build_attestation_campaign(
            contract_set, AttestationLevel.DISCOVERY, fragment_ids=("common.auth",)
        )
