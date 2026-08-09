"""Synthetic-only Outlook Scheduling Poll state for OUT-094.

The model prepares and reads deterministic local poll state. It never sends an
invitation, message, response or poll, and carries no tenant identity, address,
URL, selector, cookie, token or Microsoft Graph material.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_POLLS = 100
_MAX_OPTIONS = 20
_MAX_VOTES = 1000


class PollState(StrEnum):
    """Closed synthetic poll lifecycle."""

    DRAFT = "DRAFT"
    PREPARED = "PREPARED"
    CLOSED = "CLOSED"


class PollAction(StrEnum):
    """Closed poll mutations that remain local and synthetic."""

    CREATE = "CREATE"
    ADD_OPTION = "ADD_OPTION"
    REMOVE_OPTION = "REMOVE_OPTION"
    RECORD_VOTE = "RECORD_VOTE"
    CLOSE = "CLOSE"


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
class PollOption:
    """One relative synthetic poll option."""

    option_key: str
    day_offset: int
    start_minute_of_day: int
    end_minute_of_day: int

    def __post_init__(self) -> None:
        _validate_key("option_key", self.option_key)
        if self.day_offset < 0:
            raise ValueError("day_offset must be non-negative")
        if not 0 <= self.start_minute_of_day < self.end_minute_of_day <= 1440:
            raise ValueError("poll option minutes must form a bounded positive interval")


@dataclass(frozen=True)
class PollVote:
    """One opaque participant vote for an option."""

    option_key: str
    participant_key: str

    def __post_init__(self) -> None:
        _validate_key("option_key", self.option_key)
        _validate_key("participant_key", self.participant_key)


@dataclass(frozen=True)
class SyntheticSchedulingPoll:
    """Deterministic local poll state."""

    poll_key: str
    state: PollState
    options: tuple[PollOption, ...] = ()
    votes: tuple[PollVote, ...] = ()

    def __post_init__(self) -> None:
        _validate_key("poll_key", self.poll_key)
        if not isinstance(self.state, PollState):
            raise ValueError("state must be a closed PollState")
        if len(self.options) > _MAX_OPTIONS:
            raise ValueError("poll options exceed bounded size")
        if len(self.votes) > _MAX_VOTES:
            raise ValueError("poll votes exceed bounded size")
        option_keys = tuple(item.option_key for item in self.options)
        if len(set(option_keys)) != len(option_keys):
            raise ValueError("poll contains duplicate option_key")
        vote_keys = tuple((item.option_key, item.participant_key) for item in self.votes)
        if len(set(vote_keys)) != len(vote_keys):
            raise ValueError("poll contains duplicate participant vote")
        unknown = tuple(vote.option_key for vote in self.votes if vote.option_key not in option_keys)
        if unknown:
            raise ValueError("poll vote references an unknown option_key")


@dataclass(frozen=True)
class PollMutationRequest:
    """Prepared synthetic poll mutation."""

    action: PollAction
    poll_key: str
    option: PollOption | None = None
    option_key: str | None = None
    participant_key: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, PollAction):
            raise ValueError("action must be a closed PollAction")
        _validate_key("poll_key", self.poll_key)
        if self.option_key is not None:
            _validate_key("option_key", self.option_key)
        if self.participant_key is not None:
            _validate_key("participant_key", self.participant_key)


@dataclass(frozen=True)
class PollMutationResult:
    """Read-back proof for one local poll mutation."""

    action: PollAction
    poll_key: str
    previous_state: PollState | None
    read_back_state: PollState
    option_count: int
    vote_count: int
    changed: bool
    verified: bool
    dispatched: bool
    synthetic: bool


@dataclass(frozen=True)
class PollOptionTally:
    """Deterministic tally for one option."""

    option_key: str
    vote_count: int

    def to_projection(self) -> dict[str, object]:
        return {"option_key": self.option_key, "vote_count": self.vote_count}


@dataclass(frozen=True)
class PollResults:
    """Read-side synthetic poll results."""

    poll_key: str
    state: PollState
    tallies: tuple[PollOptionTally, ...]
    total_votes: int
    synthetic: bool


def _validate_catalog(polls: tuple[SyntheticSchedulingPoll, ...]) -> None:
    if len(polls) > _MAX_POLLS:
        raise ValueError("poll catalog exceeds bounded size")
    keys = tuple(item.poll_key for item in polls)
    if len(set(keys)) != len(keys):
        raise ValueError("poll catalog contains duplicate poll_key")


def _require_ready(readiness: OutlookReadinessReport) -> None:
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _find_poll(
    polls: tuple[SyntheticSchedulingPoll, ...], poll_key: str
) -> SyntheticSchedulingPoll:
    matches = tuple(item for item in polls if item.poll_key == poll_key)
    if len(matches) != 1:
        raise ValueError("synthetic poll_key must resolve exactly once")
    return matches[0]


def read_synthetic_poll_results(
    polls: tuple[SyntheticSchedulingPoll, ...],
    *,
    poll_key: str,
    readiness: OutlookReadinessReport,
) -> PollResults:
    """Read deterministic synthetic poll tallies."""
    _require_ready(readiness)
    _validate_key("poll_key", poll_key)
    _validate_catalog(polls)
    poll = _find_poll(polls, poll_key)
    tallies = tuple(
        PollOptionTally(
            option_key=option.option_key,
            vote_count=sum(1 for vote in poll.votes if vote.option_key == option.option_key),
        )
        for option in sorted(poll.options, key=lambda item: item.option_key)
    )
    return PollResults(
        poll_key=poll.poll_key,
        state=poll.state,
        tallies=tallies,
        total_votes=len(poll.votes),
        synthetic=True,
    )


def apply_synthetic_poll_mutation(
    polls: tuple[SyntheticSchedulingPoll, ...],
    request: PollMutationRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticSchedulingPoll, ...], PollMutationResult]:
    """Apply one prepared synthetic poll mutation with deterministic read-back."""
    _require_ready(readiness)
    _validate_catalog(polls)

    existing = tuple(item for item in polls if item.poll_key == request.poll_key)
    previous = existing[0] if existing else None
    if len(existing) > 1:
        raise ValueError("poll catalog contains duplicate poll_key")

    if request.action is PollAction.CREATE:
        if previous is None:
            if len(polls) >= _MAX_POLLS:
                raise ValueError("poll catalog exceeds bounded size")
            updated_poll = SyntheticSchedulingPoll(
                poll_key=request.poll_key,
                state=PollState.PREPARED,
            )
            changed = True
        else:
            updated_poll = previous
            changed = False
    else:
        if previous is None:
            raise ValueError("synthetic poll_key must resolve exactly once")
        if previous.state is PollState.CLOSED and request.action is not PollAction.CLOSE:
            raise ValueError("closed synthetic poll does not allow further mutations")

        if request.action is PollAction.ADD_OPTION:
            if request.option is None:
                raise ValueError("ADD_OPTION requires option")
            match = tuple(
                item for item in previous.options if item.option_key == request.option.option_key
            )
            if match:
                updated_poll = previous
                changed = False
            else:
                if len(previous.options) >= _MAX_OPTIONS:
                    raise ValueError("poll options exceed bounded size")
                updated_poll = SyntheticSchedulingPoll(
                    poll_key=previous.poll_key,
                    state=PollState.PREPARED,
                    options=previous.options + (request.option,),
                    votes=previous.votes,
                )
                changed = True
        elif request.action is PollAction.REMOVE_OPTION:
            if request.option_key is None:
                raise ValueError("REMOVE_OPTION requires option_key")
            remaining = tuple(
                item for item in previous.options if item.option_key != request.option_key
            )
            remaining_votes = tuple(
                item for item in previous.votes if item.option_key != request.option_key
            )
            changed = remaining != previous.options
            updated_poll = SyntheticSchedulingPoll(
                poll_key=previous.poll_key,
                state=previous.state,
                options=remaining,
                votes=remaining_votes,
            )
        elif request.action is PollAction.RECORD_VOTE:
            if request.option_key is None or request.participant_key is None:
                raise ValueError("RECORD_VOTE requires option_key and participant_key")
            if request.option_key not in {item.option_key for item in previous.options}:
                raise ValueError("vote option_key must exist in the synthetic poll")
            vote = PollVote(request.option_key, request.participant_key)
            if vote in previous.votes:
                raise ValueError("duplicate participant vote is not allowed")
            if len(previous.votes) >= _MAX_VOTES:
                raise ValueError("poll votes exceed bounded size")
            updated_poll = SyntheticSchedulingPoll(
                poll_key=previous.poll_key,
                state=previous.state,
                options=previous.options,
                votes=previous.votes + (vote,),
            )
            changed = True
        elif request.action is PollAction.CLOSE:
            changed = previous.state is not PollState.CLOSED
            updated_poll = SyntheticSchedulingPoll(
                poll_key=previous.poll_key,
                state=PollState.CLOSED,
                options=previous.options,
                votes=previous.votes,
            )
        else:
            raise ValueError("unsupported synthetic poll action")

    new_catalog = tuple(
        sorted(
            (item for item in polls if item.poll_key != request.poll_key)
            + (updated_poll,),
            key=lambda item: item.poll_key,
        )
    )
    read_back = read_synthetic_poll_results(
        new_catalog,
        poll_key=request.poll_key,
        readiness=readiness,
    )
    if read_back.state is not updated_poll.state:
        raise RuntimeError("synthetic poll read-back did not prove requested state")

    result = PollMutationResult(
        action=request.action,
        poll_key=request.poll_key,
        previous_state=previous.state if previous is not None else None,
        read_back_state=read_back.state,
        option_count=len(updated_poll.options),
        vote_count=len(updated_poll.votes),
        changed=changed,
        verified=True,
        dispatched=False,
        synthetic=True,
    )
    return new_catalog, result


__all__ = [
    "PollAction",
    "PollMutationRequest",
    "PollMutationResult",
    "PollOption",
    "PollOptionTally",
    "PollResults",
    "PollState",
    "PollVote",
    "SyntheticSchedulingPoll",
    "apply_synthetic_poll_mutation",
    "read_synthetic_poll_results",
]
