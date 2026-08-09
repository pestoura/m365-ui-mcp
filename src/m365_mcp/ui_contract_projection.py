"""Application-scoped projections over the global fragmented UIContract set.

The global store remains the source of truth for all Microsoft 365 applications.
Compatibility and app-specific consumers project only the common fragments plus
the fragments owned by their application, preserving manifest order and keeping
unrelated application drift/evidence from changing another application's view.
"""

from __future__ import annotations

from m365_mcp.ui_contract_store import UIContractSet


def project_ui_contract_set(
    contract_set: UIContractSet,
    application: str,
    *,
    set_version: str | None = None,
) -> UIContractSet:
    """Return common plus application-owned fragments in manifest order."""
    if (
        not application
        or application != application.strip()
        or any(char.isspace() for char in application)
    ):
        raise ValueError("application must be a non-empty semantic token")
    if set_version is not None and (
        not set_version
        or set_version != set_version.strip()
        or any(char.isspace() for char in set_version)
    ):
        raise ValueError("set_version must be a non-empty semantic version token")

    fragments = tuple(
        fragment
        for fragment in contract_set.fragments
        if fragment.scope == "common" or fragment.application == application
    )
    application_fragments = tuple(
        fragment for fragment in fragments if fragment.application == application
    )
    if not application_fragments:
        raise ValueError(f"UIContract has no fragments for application: {application}")

    return UIContractSet(
        set_version=contract_set.set_version if set_version is None else set_version,
        legacy_version=contract_set.legacy_version,
        fragments=fragments,
    )


__all__ = ["project_ui_contract_set"]
