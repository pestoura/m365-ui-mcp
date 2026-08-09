from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import readiness, signature_management
from m365_mcp.tool_registry import default_tool_registry


def _ready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.DISCOVERY_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=1,
        blocked_count=0,
        reattestation_count=0,
    )


def test_signature_catalog_create_update_delete_with_read_back() -> None:
    created = signature_management.SyntheticManagedSignature(
        signature_key="signature-primary",
        body_text="Synthetic signature",
    )
    catalog, result = signature_management.mutate_signature_catalog(
        (),
        signature_management.SignatureCatalogRequest(
            signature_management.SignatureCatalogAction.CREATE,
            created.signature_key,
            created,
        ),
        readiness=_ready(),
    )
    assert result.read_back == created
    assert result.verified is True

    updated_signature = signature_management.SyntheticManagedSignature(
        signature_key=created.signature_key,
        body_text="Synthetic signature revised",
        enabled=False,
    )
    catalog, result = signature_management.mutate_signature_catalog(
        catalog,
        signature_management.SignatureCatalogRequest(
            signature_management.SignatureCatalogAction.UPDATE,
            updated_signature.signature_key,
            updated_signature,
        ),
        readiness=_ready(),
    )
    assert result.read_back == updated_signature

    catalog, result = signature_management.mutate_signature_catalog(
        catalog,
        signature_management.SignatureCatalogRequest(
            signature_management.SignatureCatalogAction.DELETE,
            updated_signature.signature_key,
        ),
        readiness=_ready(),
    )
    assert catalog == ()
    assert result.read_back is None


def test_managed_signature_projects_to_existing_draft_signature_contract() -> None:
    managed = signature_management.SyntheticManagedSignature(
        signature_key="signature-primary",
        body_text="Synthetic signature",
        enabled=False,
    )
    projected = managed.to_draft_signature()
    assert projected.signature_key == managed.signature_key
    assert projected.enabled is False


def test_out073_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
