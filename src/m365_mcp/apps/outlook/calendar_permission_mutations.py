"""Synthetic-only calendar permission/delegation state for OUT-096.

Grants use opaque semantic keys and bounded local policy. No mailbox identity,
address, URL, selector, session material, token or live Microsoft 365 mutation
is represented.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_GRANTS = 200


class CalendarRole(StrEnum):
    """Closed synthetic calendar permission roles."""

    NONE = "NONE"
    FREE_BUSY = "FREE_BUSY"
    READ = "READ"
    WRITE = "WRITE"
    DELEGATE = "DELEGATE"


class PermissionAction(StrEnum):
    """Closed permission mutation actions."""

    GRANT = "GRANT"
    REVOKE = "REVOKE"


_ROLE_RANK: dict[CalendarRole, int] = {
    CalendarRole.NONE: 0,
    CalendarRole.FREE_BUSY: 1,
    CalendarRole.READ: 2,
    CalendarRole.WRITE: 3,
    CalendarRole.DELEGATE: 4,
}


def _validate_key(field_name: str, value: str) -> None:
    invalid = (
        not value
        or value != value.strip()
        or any(char.isspace() for char in value)
    )
    if invalid:
        raise ValueError(f"{field_name} must be a non-empty semantic token")
    if "@" in value:
        raise ValueError(f"{field_name} must not encode an address identity")


@dataclass(frozen=True)
class CalendarPermissionGrant:
    """One synthetic calendar permission grant."""

    calendar_key: str
    grantee_key: str
    role: CalendarRole

    def __post_init__(self) -> None:
        _validate_key("calendar_key", self.calendar_key)
        _validate_key("grantee_key", self.grantee_key)
        if not isinstance(self.role, CalendarRole):
            raise ValueError("role must be a closed CalendarRole")
        if self.role is CalendarRole.NONE:
            raise ValueError("stored grant role must be above NONE")


@dataclass(frozen=True)
class PermissionPolicy:
    """Bounded local policy for delegate grants."""

    max_delegates: int = 2
    allow_delegate_role: bool = True

    def __post_init__(self) -> None:
        if self.max_delegates < 0 or self.max_delegates > _MAX_GRANTS:
            raise ValueError("max_delegates must be a bounded non-negative count")


@dataclass(frozen=True)
class PermissionMutationRequest:
    """One synthetic permission mutation."""

    action: PermissionAction
    calendar_key: str
    grantee_key: str
    role: CalendarRole = CalendarRole.NONE

    def __post_init__(self) -> None:
        if not isinstance(self.action, PermissionAction):
            raise ValueError("action must be a closed PermissionAction")
        _validate_key("calendar_key", self.calendar_key)
        _validate_key("grantee_key", self.grantee_key)
        if not isinstance(self.role, CalendarRole):
            raise ValueError("role must be a closed CalendarRole")
        if self.action is PermissionAction.GRANT and self.role is CalendarRole.NONE:
            raise ValueError("grant requires a role above NONE")


@dataclass(frozen=True)
class CalendarPermissionState:
    """Deterministic read-side permission projection."""

    calendar_key: str
    grants: tuple[CalendarPermissionGrant, ...]
    delegate_count: int
    synthetic: bool

    def to_projection(self) -> dict[str, object]:
        return {
            "calendar_key": self.calendar_key,
            "grants": [
                {"grantee_key": grant.grantee_key, "role": grant.role.value}
                for grant in self.grants
            ],
            "delegate_count": self.delegate_count,
            "synthetic": self.synthetic,
        }


@dataclass(frozen=True)
class PermissionMutationResult:
    """Read-back proof for one synthetic permission mutation."""

    action: PermissionAction
    calendar_key: str
    grantee_key: str
    previous_role: CalendarRole
    read_back_role: CalendarRole
    changed: bool
    verified: bool
    synthetic: bool


def _require_ready(readiness: OutlookReadinessReport) -> None:
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _validate_grants(grants: tuple[CalendarPermissionGrant, ...]) -> None:
    if len(grants) > _MAX_GRANTS:
        raise ValueError("calendar permission grants exceed bounded size")
    pairs = tuple((item.calendar_key, item.grantee_key) for item in grants)
    if len(set(pairs)) != len(pairs):
        raise ValueError("calendar permission grants contain duplicate relation")


def read_calendar_permissions(
    grants: tuple[CalendarPermissionGrant, ...],
    *,
    calendar_key: str,
    readiness: OutlookReadinessReport,
) -> CalendarPermissionState:
    """Read one calendar's bounded synthetic grants."""
    _require_ready(readiness)
    _validate_key("calendar_key", calendar_key)
    _validate_grants(grants)
    selected = tuple(
        sorted(
            (item for item in grants if item.calendar_key == calendar_key),
            key=lambda item: item.grantee_key,
        )
    )
    return CalendarPermissionState(
        calendar_key=calendar_key,
        grants=selected,
        delegate_count=sum(item.role is CalendarRole.DELEGATE for item in selected),
        synthetic=True,
    )


def _role_for(
    grants: tuple[CalendarPermissionGrant, ...],
    calendar_key: str,
    grantee_key: str,
) -> CalendarRole:
    matches = tuple(
        item
        for item in grants
        if item.calendar_key == calendar_key and item.grantee_key == grantee_key
    )
    if not matches:
        return CalendarRole.NONE
    if len(matches) != 1:
        raise ValueError("calendar permission grants contain duplicate relation")
    return matches[0].role


def apply_calendar_permission_mutation(
    grants: tuple[CalendarPermissionGrant, ...],
    request: PermissionMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    policy: PermissionPolicy | None = None,
) -> tuple[tuple[CalendarPermissionGrant, ...], PermissionMutationResult]:
    """Apply a bounded local grant/revoke and prove effective role by read-back."""
    _require_ready(readiness)
    _validate_grants(grants)
    effective_policy = PermissionPolicy() if policy is None else policy
    previous_role = _role_for(grants, request.calendar_key, request.grantee_key)

    remaining = tuple(
        item
        for item in grants
        if not (
            item.calendar_key == request.calendar_key
            and item.grantee_key == request.grantee_key
        )
    )
    if request.action is PermissionAction.GRANT:
        if request.role is CalendarRole.DELEGATE:
            if not effective_policy.allow_delegate_role:
                raise ValueError("policy forbids DELEGATE role")
            current_delegates = sum(
                item.role is CalendarRole.DELEGATE
                for item in remaining
                if item.calendar_key == request.calendar_key
            )
            if current_delegates >= effective_policy.max_delegates:
                raise ValueError("policy forbids additional DELEGATE grants")
        if previous_role is CalendarRole.NONE and len(grants) >= _MAX_GRANTS:
            raise ValueError("calendar permission grants exceed bounded size")
        updated = remaining + (
            CalendarPermissionGrant(
                request.calendar_key,
                request.grantee_key,
                request.role,
            ),
        )
        expected = request.role
        changed = previous_role is not request.role
    elif request.action is PermissionAction.REVOKE:
        updated = remaining
        expected = CalendarRole.NONE
        changed = previous_role is not CalendarRole.NONE
    else:
        raise ValueError("unsupported permission action")

    updated = tuple(
        sorted(updated, key=lambda item: (item.calendar_key, item.grantee_key))
    )
    state = read_calendar_permissions(
        updated,
        calendar_key=request.calendar_key,
        readiness=readiness,
    )
    read_back_role = next(
        (
            item.role
            for item in state.grants
            if item.grantee_key == request.grantee_key
        ),
        CalendarRole.NONE,
    )
    if read_back_role is not expected:
        raise RuntimeError("calendar permission read-back did not prove requested role")
    if _ROLE_RANK[read_back_role] != _ROLE_RANK[expected]:
        raise RuntimeError("calendar permission role ranking is inconsistent")

    return updated, PermissionMutationResult(
        action=request.action,
        calendar_key=request.calendar_key,
        grantee_key=request.grantee_key,
        previous_role=previous_role,
        read_back_role=read_back_role,
        changed=changed,
        verified=True,
        synthetic=True,
    )


__all__ = [
    "CalendarPermissionGrant",
    "CalendarPermissionState",
    "CalendarRole",
    "PermissionAction",
    "PermissionMutationRequest",
    "PermissionMutationResult",
    "PermissionPolicy",
    "apply_calendar_permission_mutation",
    "read_calendar_permissions",
]
