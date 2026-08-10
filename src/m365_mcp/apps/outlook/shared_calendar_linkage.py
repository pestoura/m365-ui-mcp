"""Synthetic shared-mailbox to shared-calendar linkage reporting for OUT-118."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from m365_mcp.apps.outlook.shared_calendar_reads import (
    SharedCalendarPermission,
    SharedCalendarScope,
)
from m365_mcp.apps.outlook.shared_mailbox_context import SharedMailboxContext


@dataclass(frozen=True)
class SharedCalendarLinkage:
    linkage_key: str
    shared_calendar_scope_key: str
    calendar_key: str
    permission: SharedCalendarPermission
    verified: bool
    synthetic: bool = True

    def to_projection(self) -> dict[str, object]:
        return {
            "linkage_key": self.linkage_key,
            "shared_calendar_scope_key": self.shared_calendar_scope_key,
            "calendar_key": self.calendar_key,
            "permission": self.permission.value,
            "verified": self.verified,
            "synthetic": True,
        }


def resolve_shared_calendar_linkage(
    context: SharedMailboxContext,
    scope_key: str,
    *,
    scopes: tuple[SharedCalendarScope, ...],
) -> SharedCalendarLinkage:
    """Resolve one verified, identity-free shared-calendar linkage."""
    if not context.valid or context.scope_digest is None:
        raise ValueError("shared-calendar linkage requires verified shared mailbox context")
    if not scope_key or scope_key != scope_key.strip() or any(char.isspace() for char in scope_key):
        raise ValueError("scope_key must be a non-empty semantic token")
    if "@" in scope_key:
        raise ValueError("scope_key must not encode an address identity")

    matches = tuple(scope for scope in scopes if scope.scope_key == scope_key)
    if len(matches) != 1:
        raise ValueError("shared calendar scope must resolve to exactly one candidate")
    scope = matches[0]
    if scope.permission is SharedCalendarPermission.NONE:
        raise ValueError("shared calendar scope has no delegated permission")

    digest_input = f"{context.scope_digest}:{scope.scope_key}:{scope.calendar_key}"
    linkage_key = f"link-{sha256(digest_input.encode('utf-8')).hexdigest()[:24]}"
    return SharedCalendarLinkage(
        linkage_key=linkage_key,
        shared_calendar_scope_key=scope.scope_key,
        calendar_key=scope.calendar_key,
        permission=scope.permission,
        verified=True,
    )


__all__ = ["SharedCalendarLinkage", "resolve_shared_calendar_linkage"]
