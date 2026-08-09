from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import my_template_snippets, readiness
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


def test_snippet_catalog_create_update_delete_with_read_back() -> None:
    created = my_template_snippets.SyntheticSnippet(
        snippet_key="snippet-thanks",
        body_text="Synthetic thanks",
    )
    catalog, result = my_template_snippets.mutate_snippet_catalog(
        (),
        my_template_snippets.SnippetRequest(
            my_template_snippets.SnippetAction.CREATE,
            created.snippet_key,
            created,
        ),
        readiness=_ready(),
    )
    assert result.read_back == created
    assert result.verified is True

    updated_snippet = my_template_snippets.SyntheticSnippet(
        snippet_key=created.snippet_key,
        body_text="Synthetic thanks revised",
    )
    catalog, result = my_template_snippets.mutate_snippet_catalog(
        catalog,
        my_template_snippets.SnippetRequest(
            my_template_snippets.SnippetAction.UPDATE,
            updated_snippet.snippet_key,
            updated_snippet,
        ),
        readiness=_ready(),
    )
    assert result.read_back == updated_snippet

    catalog, result = my_template_snippets.mutate_snippet_catalog(
        catalog,
        my_template_snippets.SnippetRequest(
            my_template_snippets.SnippetAction.DELETE,
            updated_snippet.snippet_key,
        ),
        readiness=_ready(),
    )
    assert catalog == ()
    assert result.read_back is None


def test_snippet_projects_to_existing_body_only_insert_contract() -> None:
    snippet = my_template_snippets.SyntheticSnippet(
        snippet_key="snippet-thanks",
        body_text="Synthetic thanks",
    )
    projected = snippet.to_draft_insert()
    assert projected.insert_key == snippet.snippet_key
    assert projected.subject is None
    assert projected.body_text == snippet.body_text


def test_out075_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
