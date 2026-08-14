import json

COMMON_AUTH_SELECTORS = (
    "auth.login_email_input",
    "auth.mfa_number_display",
    "auth.login_password_input",
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
    assert len(contract_set.selectors()) == 11


def test_common_auth_fragment_remains_platform_owned() -> None:
    contract_set = _contract_set()
    common = tuple(fragment for fragment in contract_set.fragments if fragment.scope == "common")

    assert len(common) == 1
    assert common[0].fragment_id == "common.auth"
    assert common[0].application is None
    assert tuple(common[0].selectors) == COMMON_AUTH_SELECTORS


def test_legacy_contract_selector_order_and_metadata_remain_identical() -> None:
    legacy = json.loads((_contracts_dir() / "ui_contract.json").read_text(encoding="utf-8"))
    fragmented = _contract_set()

    assert legacy["ui_contract_version"] == fragmented.legacy_version
    assert legacy["selectors"] == fragmented.selectors()


def test_planner_fragment_declarations_contain_no_selector_values() -> None:
    for spec in _planner_fragment_specs():
        assert spec.fragment_id.startswith("planner.")
        assert all(
            selector.startswith(("plan.", "task.", "account."))
            for selector in spec.selector_names
        )
