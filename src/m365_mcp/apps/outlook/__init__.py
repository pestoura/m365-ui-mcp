"""Outlook application foundation and reserved read-only models.

OUT-001 creates an application-owned package boundary, OUT-002 adds synthetic
isolated fixtures, OUT-003 adds semantic shell/navigation requirements,
OUT-004 adds evidence-neutral capability discovery, OUT-005 adds sanitized
primary-mailbox context verification, OUT-006 adds scoped shared-mailbox
context verification, OUT-007 adds bounded readiness/smoke projection,
OUT-010 adds message listing, OUT-011 adds synthetic message get/read, and
OUT-012 adds bounded synthetic mail search.
Outlook remains RESERVED and exposes no public MCP registrar or browser
operation surface.
"""

from m365_mcp.apps.outlook.discovery import (
    DiscoveryState,
    OutlookCapabilityCandidate,
    default_outlook_discovery_candidates,
)
from m365_mcp.apps.outlook.mail_search import (
    MailSearchRequest,
    MailSearchResult,
    search_fixture_messages,
)
from m365_mcp.apps.outlook.mailbox_context import (
    PrimaryMailboxContext,
    PrimaryMailboxContextState,
    PrimaryMailboxObservation,
    verify_primary_mailbox_context,
)
from m365_mcp.apps.outlook.manifest import OutlookFoundationManifest, foundation_manifest
from m365_mcp.apps.outlook.message_get import (
    MessageGetRequest,
    MessageGetResult,
    get_fixture_message,
)
from m365_mcp.apps.outlook.message_list import (
    MessageListItem,
    MessageListRequest,
    MessageListResult,
    list_fixture_messages,
)
from m365_mcp.apps.outlook.mock_ui import (
    MockMessage,
    OutlookMockFixture,
    default_outlook_fixture,
)
from m365_mcp.apps.outlook.readiness import (
    OutlookReadinessReport,
    OutlookReadinessState,
    evaluate_outlook_readiness,
)
from m365_mcp.apps.outlook.shared_mailbox_context import (
    SharedMailboxContext,
    SharedMailboxContextState,
    SharedMailboxObservation,
    verify_shared_mailbox_context,
)
from m365_mcp.apps.outlook.shell_contracts import (
    OutlookShellContract,
    OutlookShellTarget,
    outlook_shell_contracts,
)

__all__ = [
    "DiscoveryState",
    "MailSearchRequest",
    "MailSearchResult",
    "MessageGetRequest",
    "MessageGetResult",
    "MessageListItem",
    "MessageListRequest",
    "MessageListResult",
    "MockMessage",
    "OutlookCapabilityCandidate",
    "OutlookFoundationManifest",
    "OutlookMockFixture",
    "OutlookReadinessReport",
    "OutlookReadinessState",
    "OutlookShellContract",
    "OutlookShellTarget",
    "PrimaryMailboxContext",
    "PrimaryMailboxContextState",
    "PrimaryMailboxObservation",
    "SharedMailboxContext",
    "SharedMailboxContextState",
    "SharedMailboxObservation",
    "default_outlook_discovery_candidates",
    "default_outlook_fixture",
    "evaluate_outlook_readiness",
    "foundation_manifest",
    "get_fixture_message",
    "list_fixture_messages",
    "outlook_shell_contracts",
    "search_fixture_messages",
    "verify_primary_mailbox_context",
    "verify_shared_mailbox_context",
]
