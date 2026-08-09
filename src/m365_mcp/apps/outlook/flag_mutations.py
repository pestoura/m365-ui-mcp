"""Synthetic-only Outlook flag/unflag/complete semantics for OUT-033.

The domain operation mutates only synthetic FollowUpFlag tuples and immediately
verifies the result through OUT-018 reads. Outlook remains RESERVED and no
public mutation or browser primitive is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.follow_up_reads import (
    FollowUpFlag,
    FollowUpState,
    read_fixture_follow_up_state,
)
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MIN_DAY_OFFSET = -3650
_MAX_DAY_OFFSET = 3650


class FlagMutationAction(StrEnum):
    FLAG = "FLAG"
    UNFLAG = "UNFLAG"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True)
class FlagMutationRequest:
    action: FlagMutationAction
    message_key: str
    completed_day_offset: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, FlagMutationAction):
            raise ValueError("action must be a closed FlagMutationAction")
        invalid_key = (
            not self.message_key
            or self.message_key != self.message_key.strip()
            or any(char.isspace() for char in self.message_key)
        )
        if invalid_key:
            raise ValueError("message_key must be a non-empty semantic token")

        if self.action is FlagMutationAction.COMPLETE:
            if self.completed_day_offset is None:
                raise ValueError("complete requires completed_day_offset")
            if (
                isinstance(self.completed_day_offset, bool)
                or not _MIN_DAY_OFFSET
                <= self.completed_day_offset
                <= _MAX_DAY_OFFSET
            ):
                raise ValueError("completed_day_offset exceeds bounded window")
        elif self.completed_day_offset is not None:
            raise ValueError("completed_day_offset is only valid for complete")

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "action": self.action.value,
            "message_key": self.message_key,
        }
        if self.completed_day_offset is not None:
            payload["completed_day_offset"] = self.completed_day_offset
        return payload


@dataclass(frozen=True)
class FlagMutationResult:
    action: FlagMutationAction
    message_key: str
    previous_state: FollowUpState
    read_back_state: FollowUpState
    changed: bool
    verified: bool
    synthetic: bool = True


def _current_flag(
    flags: tuple[FollowUpFlag, ...],
    message_key: str,
) -> FollowUpFlag | None:
    return next((item for item in flags if item.message_key == message_key), None)


def apply_fixture_flag_mutation(
    fixture: OutlookMockFixture,
    request: FlagMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    flags: tuple[FollowUpFlag, ...],
) -> tuple[tuple[FollowUpFlag, ...], FlagMutationResult]:
    """Apply one synthetic flag transition and verify the resulting state."""
    if not fixture.synthetic:
        raise ValueError("OUT-033 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not any(message.message_key == request.message_key for message in fixture.messages):
        raise ValueError("synthetic message_key not found")

    current = _current_flag(flags, request.message_key)
    previous_state = FollowUpState.NOT_FLAGGED if current is None else current.state

    if request.action is FlagMutationAction.FLAG:
        if current is not None and current.state is FollowUpState.COMPLETED:
            raise ValueError("completed follow-up must not be silently re-flagged")
        replacement = FollowUpFlag(
            message_key=request.message_key,
            state=FollowUpState.FLAGGED,
            start_day_offset=current.start_day_offset if current is not None else None,
            due_day_offset=current.due_day_offset if current is not None else None,
        )
        changed = current != replacement
        updated = tuple(
            item for item in flags if item.message_key != request.message_key
        ) + (replacement,)

    elif request.action is FlagMutationAction.UNFLAG:
        updated = tuple(
            item for item in flags if item.message_key != request.message_key
        )
        changed = current is not None

    else:
        if current is None or current.state is FollowUpState.NOT_FLAGGED:
            raise ValueError("only an existing flagged follow-up can be completed")
        if current.state is FollowUpState.COMPLETED:
            if current.completed_day_offset != request.completed_day_offset:
                raise ValueError("completed follow-up cannot change completion day")
            updated = flags
            changed = False
        else:
            replacement = FollowUpFlag(
                message_key=current.message_key,
                state=FollowUpState.COMPLETED,
                start_day_offset=current.start_day_offset,
                due_day_offset=current.due_day_offset,
                completed_day_offset=request.completed_day_offset,
            )
            updated = tuple(
                replacement if item.message_key == request.message_key else item
                for item in flags
            )
            changed = True

    read_back = read_fixture_follow_up_state(
        fixture,
        request.message_key,
        readiness=readiness,
        flags=updated,
    )
    expected = {
        FlagMutationAction.FLAG: FollowUpState.FLAGGED,
        FlagMutationAction.UNFLAG: FollowUpState.NOT_FLAGGED,
        FlagMutationAction.COMPLETE: FollowUpState.COMPLETED,
    }[request.action]
    if read_back.state is not expected:
        raise RuntimeError("synthetic follow-up read-back did not prove requested state")

    return (
        updated,
        FlagMutationResult(
            action=request.action,
            message_key=request.message_key,
            previous_state=previous_state,
            read_back_state=read_back.state,
            changed=changed,
            verified=True,
        ),
    )


__all__ = [
    "FlagMutationAction",
    "FlagMutationRequest",
    "FlagMutationResult",
    "apply_fixture_flag_mutation",
]
