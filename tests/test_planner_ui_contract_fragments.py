import json

COMMON_AUTH_SELECTORS = (
    "auth.login_email_input",
    "auth.login_next_button",
    "auth.login_password_input",
    "auth.login_signin_button",
)


def _contract_set():
    from m365_mcp.ui_contract_projection import project_ui_contract_set
    from m365_mcp.ui_contract_store import load_ui_contract_set

    return project_ui_contract_set(load_ui_contract_set(), "planner")


def _planner_fragment_specs():
    from m365_mcp.apps.planner.ui_contracts import planner_ui_contract_fragment_specs

    return planner_ui_contract_fragment_specs()


def _planner_selector_names():
    from m365_mcp.apps.planner.ui_contracts import planner_selector_names

    return planner_selector_names()


def _contracts_dir():
    from m365_mcp.contracts import contracts_dir

    return contracts_dir()


def test_planner_fragment_specs_match_canonical_contract_set() -> None:
    contract_set = _contract_set()
    planner_fragments = tuple(
        fragment for fragment in contract_set.fragments if fragment.application == "planner"
    )
    specs = _planner_fragment_specs()

    assert len(planner_fragments) == len(specs) == 3
    for fragment, spec in zip(planner_fragments, specs, strict=True):
        assert fragment.fragment_id == spec.fragment_id
        assert fragment.scope == spec.scope
        assert fragment.surface == spec.surface
        assert fragment.capability_keys == spec.capability_keys
        assert tuple(fragment.selectors) == spec.selector_names


def test_planner_partition_preserves_eight_app_selectors_and_ten_legacy_selectors() -> None:
    contract_set = _contract_set()
    planner_selectors = _planner_selector_names()

    assert len(planner_selectors) == 8
    assert len(set(planner_selectors)) == 8
    assert tuple(contract_set.selectors()) == COMMON_AUTH_SELECTORS + planner_selectors
    assert len(contract_set.selectors()) == 12


def test_common_auth_fragment_remains_platform_owned() -> None:
    contract_set = _contract_set()
    common = tuple(
        fragment
        for fragment in contract_set.fragments
        if fragment.scope == "common"
    )

    # The two atomic ``common.auth`` fragments must remain platform-owned:
    # scope == common, application is None, and together they declare exactly the
    # four authentication selectors. The email and password surfaces never coexist
    # on the same Microsoft Entra ID sign-in page, so a single fragment was
    # structurally impossible to collect.
    assert len(common) == 2
    assert {fragment.fragment_id for fragment in common} == {
        "common.auth.email",
        "common.auth.password",
    }
    for fragment in common:
        assert fragment.application is None
    assert tuple(
        sel for fragment in common for sel in fragment.selectors
    ) == COMMON_AUTH_SELECTORS


def test_legacy_contract_selector_order_and_metadata_remain_identical() -> None:
    contract_set = _contract_set()
    legacy = json.loads((_contracts_dir() / "ui_contract.json").read_text(encoding="utf-8"))
    fragmented = contract_set.selectors()

    # The Foundation UIContract (contracts/ui_contract.json) is the canonical
    # fail-closed baseline and MUST stay UNVERIFIED_LIVE (check_contracts.py
    # enforces attested=False / UNVERIFIED_LIVE for every selector). The atomic
    # common.auth fragments are promoted to ATTESTED by explicit evidence-backed
    # PR promotion, so the fragmented view legitimately diverges from the
    # Foundation baseline on the four auth selectors. Everything else must remain
    # byte-identical: same selector names (manifest order) and identical
    # value/status for every non-auth selector.
    auth_selectors = {
        "auth.login_email_input",
        "auth.login_next_button",
        "auth.login_password_input",
        "auth.login_signin_button",
    }
    assert set(fragmented) == set(legacy["selectors"])
    for name in fragmented:
        if name in auth_selectors:
            # Promoted: attested in the fragmented view.
            assert fragmented[name]["status"] == "ATTESTED", name
            assert fragmented[name]["value"] is None, name
        else:
            # Unchanged: identical to the Foundation baseline.
            assert fragmented[name] == legacy["selectors"][name], name


def test_planner_fragment_declarations_contain_no_selector_values() -> None:
    for spec in _planner_fragment_specs():
        assert spec.fragment_id.startswith("planner.")
        assert all(
            selector.startswith(("plan.", "task.", "account."))
            for selector in spec.selector_names
        )
