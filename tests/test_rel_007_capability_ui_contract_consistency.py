"""REL-007 — Capability / UIContract consistency assurance.

Assurance-only cross-checks between three canonical sources of truth:
the Tool Registry, the scoped Capability Registry and the fragmented
UIContract set. Any future application must keep them mutually consistent.
"""

from __future__ import annotations

from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.ui_contract_store import load_ui_contract_set

GLOBAL_DEPENDENCY = "GLOBAL_UI_CONTRACT_ATTESTATION"


def test_every_tool_capability_key_exists_in_the_capability_registry() -> None:
    capabilities = default_capability_registry()
    registry = default_tool_registry()

    for name in registry.names():
        definition = registry.get(name)
        for key in definition.capability_keys:
            assert capabilities.has_capability(definition.application, key), (name, key)


def test_every_tool_ui_dependency_resolves_to_a_declared_selector() -> None:
    contract_set = load_ui_contract_set()
    known_selectors = set(contract_set.selectors())
    registry = default_tool_registry()

    for name in registry.names():
        for dependency in registry.get(name).ui_contract_dependencies:
            if dependency == GLOBAL_DEPENDENCY:
                continue
            assert dependency in known_selectors, (name, dependency)


def test_every_declared_selector_is_owned_by_exactly_one_fragment() -> None:
    contract_set = load_ui_contract_set()
    owners: dict[str, list[str]] = {}
    for fragment in contract_set.fragments:
        for selector in fragment.selectors:
            owners.setdefault(selector, []).append(fragment.fragment_id)

    duplicated = {name: ids for name, ids in owners.items() if len(ids) > 1}
    assert duplicated == {}
    assert set(owners) == set(contract_set.selectors())


def test_fragment_capability_keys_are_declared_capabilities() -> None:
    capabilities = default_capability_registry()
    for fragment in load_ui_contract_set().fragments:
        application = fragment.application
        if application is None:
            assert fragment.capability_keys == ()
            continue
        for key in fragment.capability_keys:
            assert capabilities.has_capability(application, key), (
                fragment.fragment_id,
                key,
            )


def test_capability_backed_tools_resolve_to_at_least_one_fragment() -> None:
    contract_set = load_ui_contract_set()
    registry = default_tool_registry()

    for name in registry.names():
        definition = registry.get(name)
        if not definition.capability_keys:
            continue
        if definition.ui_contract_dependencies in ((), (GLOBAL_DEPENDENCY,)):
            # Aggregate/status tools depend on global attestation, not selectors.
            continue
        resolved = {
            fragment.fragment_id
            for key in definition.capability_keys
            for fragment in contract_set.fragments_for_capability(
                definition.application, key
            )
        }
        assert resolved, name


# Fragments promoted by explicit, evidence-backed PR promotion (live UNIQUE_MATCH
# on every selector, reviewed contract JSON edit) are permitted to be ATTESTED.
# This global invariant therefore scopes to the NON-auth fragments: every other
# fragment must still be UNVERIFIED_LIVE by default, and the auth fragments that
# ARE attested must satisfy total consistency (fragment + all selectors ATTESTED,
# value None, locator plans preserved, no drift).
ATTESTED_AUTH_FRAGMENT_IDS = ("common.auth.email", "common.auth.password")


def _auth_fragment_is_consistently_attested(fragment: object) -> bool:
    fragment = fragment  # type: ignore[assignment]
    if not fragment.attested:  # type: ignore[attr-defined]
        return False
    if fragment.attestation_status != "ATTESTED":  # type: ignore[attr-defined]
        return False
    for selector in fragment.selectors.values():  # type: ignore[attr-defined]
        if selector["status"] != "ATTESTED":
            return False
        if selector["value"] is not None:
            return False
    return True


def test_no_capability_or_fragment_claims_live_attestation_yet() -> None:
    contract_set = load_ui_contract_set()
    for fragment in contract_set.fragments:
        if fragment.fragment_id in ATTESTED_AUTH_FRAGMENT_IDS:
            # Evidence-backed promotion: total consistency required.
            assert _auth_fragment_is_consistently_attested(fragment), fragment.fragment_id
            continue
        assert fragment.attested is False, fragment.fragment_id
        assert fragment.attestation_status == "UNVERIFIED_LIVE", fragment.fragment_id
        for selector in fragment.selectors.values():
            assert selector["status"] == "UNVERIFIED_LIVE"
            assert selector["value"] is None


def test_capability_registry_scopes_are_internally_consistent() -> None:
    capabilities = default_capability_registry()
    identities = [definition.identity for definition in capabilities.definitions()]
    assert len(set(identities)) == len(identities)
    for definition in capabilities.definitions():
        assert "." in definition.capability
        assert definition.surface.strip()
        assert definition.account_scope.strip()
        assert definition.container_scope.strip()
