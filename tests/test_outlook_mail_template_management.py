from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import mail_template_management, readiness
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


def test_mail_template_catalog_create_update_delete_with_read_back() -> None:
    created = mail_template_management.SyntheticMailTemplate(
        template_key="template-status",
        subject="Synthetic status",
        body_text="Synthetic body",
    )
    catalog, result = mail_template_management.mutate_mail_template_catalog(
        (),
        mail_template_management.MailTemplateRequest(
            mail_template_management.MailTemplateAction.CREATE,
            created.template_key,
            created,
        ),
        readiness=_ready(),
    )
    assert result.read_back == created
    assert result.verified is True

    updated_template = mail_template_management.SyntheticMailTemplate(
        template_key=created.template_key,
        subject="Synthetic status revised",
        body_text="Synthetic body revised",
    )
    catalog, result = mail_template_management.mutate_mail_template_catalog(
        catalog,
        mail_template_management.MailTemplateRequest(
            mail_template_management.MailTemplateAction.UPDATE,
            updated_template.template_key,
            updated_template,
        ),
        readiness=_ready(),
    )
    assert result.read_back == updated_template

    catalog, result = mail_template_management.mutate_mail_template_catalog(
        catalog,
        mail_template_management.MailTemplateRequest(
            mail_template_management.MailTemplateAction.DELETE,
            updated_template.template_key,
        ),
        readiness=_ready(),
    )
    assert catalog == ()
    assert result.read_back is None


def test_full_template_projects_to_existing_draft_insert_contract() -> None:
    template = mail_template_management.SyntheticMailTemplate(
        template_key="template-status",
        subject="Synthetic status",
        body_text="Synthetic body",
    )
    projected = template.to_draft_insert()
    assert projected.insert_key == template.template_key
    assert projected.subject == template.subject
    assert projected.body_text == template.body_text


def test_out074_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
