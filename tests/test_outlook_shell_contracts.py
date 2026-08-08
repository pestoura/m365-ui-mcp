from __future__ import annotations

import pytest

from m365_mcp.apps.outlook import (
    OutlookShellContract,
    OutlookShellTarget,
    foundation_manifest,
    outlook_shell_contracts,
)
from m365_mcp.tool_registry import default_tool_registry


def test_outlook_shell_contract_set_is_closed_and_deterministic() -> None:
    contracts = outlook_shell_contracts()

    assert tuple(contract.target for contract in contracts) == (
        OutlookShellTarget.MAIL,
        OutlookShellTarget.CALENDAR,
        OutlookShellTarget.PEOPLE,
        OutlookShellTarget.TODO,
        OutlookShellTarget.SETTINGS,
    )
    assert len({contract.contract_key for contract in contracts}) == len(contracts)
    assert all(contract.requires_authenticated_shell for contract in contracts)
    assert all(contract.live_evidence_state == "UNVERIFIED_LIVE" for contract in contracts)


def test_shell_contracts_contain_no_generic_browser_primitive() -> None:
    serialized = repr(outlook_shell_contracts()).lower()
    forbidden = (
        "https://",
        "css=",
        "xpath",
        "selector",
        "javascript",
        "cookie",
        "token",
        "storage_state",
    )
    assert not any(marker in serialized for marker in forbidden)


def test_out_003_does_not_activate_outlook() -> None:
    manifest = foundation_manifest()

    assert manifest.public_tools_enabled is False
    assert manifest.browser_operations_enabled is False
    assert default_tool_registry().by_application("outlook") == ()


def test_shell_contract_cannot_claim_live_attestation() -> None:
    with pytest.raises(ValueError, match="cannot claim live shell attestation"):
        OutlookShellContract(
            contract_key="outlook.shell.mail",
            target=OutlookShellTarget.MAIL,
            semantic_role="mail_navigation",
            live_evidence_state="ATTESTED",
        )
