"""Outlook application foundation and reserved read-only models.

OUT-001..OUT-007 establish the inert application/readiness foundation.
OUT-010..OUT-014 add synthetic-only read models. OUT-015 adds controlled
attachment retrieval into an injected artifact sink; no attachment bytes or
raw storage locator are projected. Outlook remains RESERVED and exposes no
public MCP registrar or browser operation surface.
"""

from m365_mcp.apps.outlook.attachment_metadata import (
    AttachmentMetadataResult,
    SyntheticAttachment,
    default_synthetic_attachments,
    list_fixture_attachment_metadata,
)
from m365_mcp.apps.outlook.attachment_retrieval import (
    AttachmentArtifactSink,
    AttachmentRetrievalResult,
    SyntheticAttachmentPayload,
    retrieve_synthetic_attachment,
)
from m365_mcp.apps.outlook.category_reads import (
    CategoryAssignment,
    CategoryColorToken,
    CategoryListResult,
    CategoryUsage,
    MessageCategoryState,
    SyntheticCategory,
    default_synthetic_categories,
    default_synthetic_category_assignments,
    list_fixture_categories,
    read_fixture_message_categories,
)
from m365_mcp.apps.outlook.conversation_reads import (
    ConversationReadResult,
    SyntheticConversation,
    default_synthetic_conversations,
    read_fixture_conversation,
)
from m365_mcp.apps.outlook.discovery import (
    DiscoveryState,
    OutlookCapabilityCandidate,
    default_outlook_discovery_candidates,
)
from m365_mcp.apps.outlook.folder_reads import (
    FolderListResult,
    FolderNavigationResult,
    FolderNode,
    SyntheticFolder,
    default_synthetic_folders,
    list_fixture_folders,
    navigate_fixture_folder,
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
    "AttachmentArtifactSink",
    "AttachmentMetadataResult",
    "AttachmentRetrievalResult",
    "CategoryAssignment",
    "CategoryColorToken",
    "CategoryListResult",
    "CategoryUsage",
    "ConversationReadResult",
    "DiscoveryState",
    "FolderListResult",
    "FolderNavigationResult",
    "FolderNode",
    "MailSearchRequest",
    "MailSearchResult",
    "MessageGetRequest",
    "MessageGetResult",
    "MessageListItem",
    "MessageListRequest",
    "MessageCategoryState",
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
    "SyntheticAttachment",
    "SyntheticAttachmentPayload",
    "SyntheticCategory",
    "SyntheticConversation",
    "SyntheticFolder",
    "default_outlook_discovery_candidates",
    "default_outlook_fixture",
    "default_synthetic_attachments",
    "default_synthetic_categories",
    "default_synthetic_category_assignments",
    "default_synthetic_conversations",
    "default_synthetic_folders",
    "evaluate_outlook_readiness",
    "foundation_manifest",
    "get_fixture_message",
    "list_fixture_attachment_metadata",
    "list_fixture_categories",
    "list_fixture_folders",
    "list_fixture_messages",
    "navigate_fixture_folder",
    "outlook_shell_contracts",
    "read_fixture_conversation",
    "read_fixture_message_categories",
    "retrieve_synthetic_attachment",
    "search_fixture_messages",
    "verify_primary_mailbox_context",
    "verify_shared_mailbox_context",
]
