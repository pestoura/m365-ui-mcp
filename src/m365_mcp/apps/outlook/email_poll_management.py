"""Synthetic email poll create/manage/results for OUT-136."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_POLLS = 100
_MAX_OPTIONS = 10
_MAX_VOTES = 1000
_MAX_TEXT = 500


class EmailPollState(StrEnum):
    PREPARED = "PREPARED"
    CLOSED = "CLOSED"


class EmailPollAction(StrEnum):
    CREATE = "CREATE"
    ADD_OPTION = "ADD_OPTION"
    REMOVE_OPTION = "REMOVE_OPTION"
    RECORD_VOTE = "RECORD_VOTE"
    CLOSE = "CLOSE"


def _key(field: str, value: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{field} must be a non-empty semantic token")
    if "@" in value or "://" in value:
        raise ValueError(f"{field} must not encode an address or URL")
    return value


@dataclass(frozen=True)
class EmailPollOption:
    option_key: str
    label: str

    def __post_init__(self) -> None:
        _key("option_key", self.option_key)
        invalid_label = (
            not self.label
            or self.label != self.label.strip()
            or len(self.label) > _MAX_TEXT
        )
        if invalid_label:
            raise ValueError("poll option label must be bounded and trimmed")


@dataclass(frozen=True)
class EmailPollVote:
    option_key: str
    participant_key: str

    def __post_init__(self) -> None:
        _key("option_key", self.option_key)
        _key("participant_key", self.participant_key)


@dataclass(frozen=True)
class SyntheticEmailPoll:
    poll_key: str
    question: str
    state: EmailPollState
    options: tuple[EmailPollOption, ...] = ()
    votes: tuple[EmailPollVote, ...] = ()
    dispatched: bool = False
    synthetic: bool = True
    live_support_state: str = "UNOBSERVED"

    def __post_init__(self) -> None:
        _key("poll_key", self.poll_key)
        invalid_question = (
            not self.question
            or self.question != self.question.strip()
            or len(self.question) > _MAX_TEXT
        )
        if invalid_question:
            raise ValueError("poll question must be bounded and trimmed")
        if len(self.options) > _MAX_OPTIONS or len(self.votes) > _MAX_VOTES:
            raise ValueError("email poll exceeds bounded size")
        option_keys = tuple(item.option_key for item in self.options)
        if len(option_keys) != len(set(option_keys)):
            raise ValueError("email poll options must be unique")
        vote_keys = tuple((vote.option_key, vote.participant_key) for vote in self.votes)
        if len(vote_keys) != len(set(vote_keys)):
            raise ValueError("duplicate participant vote is not allowed")
        if any(vote.option_key not in option_keys for vote in self.votes):
            raise ValueError("vote references unknown option_key")
        if self.dispatched or not self.synthetic or self.live_support_state != "UNOBSERVED":
            raise ValueError("email poll must remain local, synthetic and live-unobserved")


@dataclass(frozen=True)
class EmailPollResult:
    poll_key: str
    state: EmailPollState
    tallies: tuple[tuple[str, int], ...]
    total_votes: int
    synthetic: bool = True


def read_email_poll_results(
    polls: tuple[SyntheticEmailPoll, ...],
    poll_key: str,
    *,
    readiness: OutlookReadinessReport,
) -> EmailPollResult:
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    _key("poll_key", poll_key)
    matches = tuple(item for item in polls if item.poll_key == poll_key)
    if len(matches) != 1:
        raise ValueError("synthetic poll_key must resolve exactly once")
    poll = matches[0]
    tallies = tuple(
        (
            option.option_key,
            sum(1 for vote in poll.votes if vote.option_key == option.option_key),
        )
        for option in sorted(poll.options, key=lambda item: item.option_key)
    )
    return EmailPollResult(poll.poll_key, poll.state, tallies, len(poll.votes))


def apply_email_poll_action(
    polls: tuple[SyntheticEmailPoll, ...],
    *,
    action: EmailPollAction,
    poll_key: str,
    question: str | None = None,
    option: EmailPollOption | None = None,
    option_key: str | None = None,
    participant_key: str | None = None,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticEmailPoll, ...], EmailPollResult]:
    """Apply one local email-poll mutation and return deterministic read-back results."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    _key("poll_key", poll_key)
    if len(polls) > _MAX_POLLS:
        raise ValueError("email poll catalog exceeds bounded size")
    existing = tuple(item for item in polls if item.poll_key == poll_key)
    if len(existing) > 1:
        raise ValueError("email poll catalog contains duplicate poll_key")
    current = existing[0] if existing else None

    if action is EmailPollAction.CREATE:
        if current is not None:
            updated_poll = current
        else:
            if question is None:
                raise ValueError("CREATE requires question")
            updated_poll = SyntheticEmailPoll(poll_key, question, EmailPollState.PREPARED)
    else:
        if current is None:
            raise ValueError("synthetic poll_key must resolve exactly once")
        if current.state is EmailPollState.CLOSED and action is not EmailPollAction.CLOSE:
            raise ValueError("closed email poll does not allow further mutations")
        if action is EmailPollAction.ADD_OPTION:
            if option is None:
                raise ValueError("ADD_OPTION requires option")
            options = (
                current.options if option in current.options else current.options + (option,)
            )
            updated_poll = SyntheticEmailPoll(
                current.poll_key,
                current.question,
                current.state,
                options,
                current.votes,
            )
        elif action is EmailPollAction.REMOVE_OPTION:
            if option_key is None:
                raise ValueError("REMOVE_OPTION requires option_key")
            options = tuple(
                item for item in current.options if item.option_key != option_key
            )
            votes = tuple(
                item for item in current.votes if item.option_key != option_key
            )
            updated_poll = SyntheticEmailPoll(
                current.poll_key,
                current.question,
                current.state,
                options,
                votes,
            )
        elif action is EmailPollAction.RECORD_VOTE:
            if option_key is None or participant_key is None:
                raise ValueError("RECORD_VOTE requires option_key and participant_key")
            vote = EmailPollVote(option_key, participant_key)
            updated_poll = SyntheticEmailPoll(
                current.poll_key,
                current.question,
                current.state,
                current.options,
                current.votes + (vote,),
            )
        elif action is EmailPollAction.CLOSE:
            updated_poll = SyntheticEmailPoll(
                current.poll_key,
                current.question,
                EmailPollState.CLOSED,
                current.options,
                current.votes,
            )
        else:
            raise ValueError("unsupported email poll action")

    remaining = tuple(item for item in polls if item.poll_key != poll_key)
    updated = tuple(sorted(remaining + (updated_poll,), key=lambda item: item.poll_key))
    return updated, read_email_poll_results(updated, poll_key, readiness=readiness)


__all__ = [
    "EmailPollAction",
    "EmailPollOption",
    "EmailPollResult",
    "EmailPollState",
    "EmailPollVote",
    "SyntheticEmailPoll",
    "apply_email_poll_action",
    "read_email_poll_results",
]
