from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import readiness, scheduling_poll_state
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


def _option(key: str = "option-alpha") -> scheduling_poll_state.PollOption:
    return scheduling_poll_state.PollOption(key, 0, 540, 600)


def test_poll_create_add_vote_results_and_close_are_read_back() -> None:
    polls, created = scheduling_poll_state.apply_synthetic_poll_mutation(
        (),
        scheduling_poll_state.PollMutationRequest(
            scheduling_poll_state.PollAction.CREATE,
            "poll-alpha",
        ),
        readiness=_ready(),
    )
    assert created.read_back_state is scheduling_poll_state.PollState.PREPARED
    assert created.dispatched is False
    assert created.verified is True

    polls, added = scheduling_poll_state.apply_synthetic_poll_mutation(
        polls,
        scheduling_poll_state.PollMutationRequest(
            scheduling_poll_state.PollAction.ADD_OPTION,
            "poll-alpha",
            option=_option(),
        ),
        readiness=_ready(),
    )
    assert added.changed is True
    polls, voted = scheduling_poll_state.apply_synthetic_poll_mutation(
        polls,
        scheduling_poll_state.PollMutationRequest(
            scheduling_poll_state.PollAction.RECORD_VOTE,
            "poll-alpha",
            option_key="option-alpha",
            participant_key="participant-alpha",
        ),
        readiness=_ready(),
    )
    assert voted.vote_count == 1
    results = scheduling_poll_state.read_synthetic_poll_results(
        polls,
        poll_key="poll-alpha",
        readiness=_ready(),
    )
    assert tuple((item.option_key, item.vote_count) for item in results.tallies) == (
        ("option-alpha", 1),
    )

    polls, closed = scheduling_poll_state.apply_synthetic_poll_mutation(
        polls,
        scheduling_poll_state.PollMutationRequest(
            scheduling_poll_state.PollAction.CLOSE,
            "poll-alpha",
        ),
        readiness=_ready(),
    )
    assert closed.read_back_state is scheduling_poll_state.PollState.CLOSED
    assert polls[0].state is scheduling_poll_state.PollState.CLOSED


def test_poll_option_mutations_are_idempotent_and_results_are_sorted() -> None:
    poll = scheduling_poll_state.SyntheticSchedulingPoll(
        "poll-alpha",
        scheduling_poll_state.PollState.PREPARED,
        options=(_option("option-bravo"), _option("option-alpha")),
    )
    polls, duplicate = scheduling_poll_state.apply_synthetic_poll_mutation(
        (poll,),
        scheduling_poll_state.PollMutationRequest(
            scheduling_poll_state.PollAction.ADD_OPTION,
            "poll-alpha",
            option=_option("option-alpha"),
        ),
        readiness=_ready(),
    )
    assert duplicate.changed is False
    results = scheduling_poll_state.read_synthetic_poll_results(
        polls,
        poll_key="poll-alpha",
        readiness=_ready(),
    )
    assert tuple(item.option_key for item in results.tallies) == (
        "option-alpha",
        "option-bravo",
    )

    polls, removed = scheduling_poll_state.apply_synthetic_poll_mutation(
        polls,
        scheduling_poll_state.PollMutationRequest(
            scheduling_poll_state.PollAction.REMOVE_OPTION,
            "poll-alpha",
            option_key="option-alpha",
        ),
        readiness=_ready(),
    )
    assert removed.changed is True
    _, absent = scheduling_poll_state.apply_synthetic_poll_mutation(
        polls,
        scheduling_poll_state.PollMutationRequest(
            scheduling_poll_state.PollAction.REMOVE_OPTION,
            "poll-alpha",
            option_key="option-alpha",
        ),
        readiness=_ready(),
    )
    assert absent.changed is False


def test_poll_rejects_duplicate_votes_and_mutation_after_close() -> None:
    poll = scheduling_poll_state.SyntheticSchedulingPoll(
        "poll-alpha",
        scheduling_poll_state.PollState.PREPARED,
        options=(_option(),),
        votes=(scheduling_poll_state.PollVote("option-alpha", "participant-alpha"),),
    )
    with pytest.raises(ValueError, match="duplicate participant vote"):
        scheduling_poll_state.apply_synthetic_poll_mutation(
            (poll,),
            scheduling_poll_state.PollMutationRequest(
                scheduling_poll_state.PollAction.RECORD_VOTE,
                "poll-alpha",
                option_key="option-alpha",
                participant_key="participant-alpha",
            ),
            readiness=_ready(),
        )
    closed = scheduling_poll_state.SyntheticSchedulingPoll(
        "poll-alpha",
        scheduling_poll_state.PollState.CLOSED,
        options=(_option(),),
    )
    with pytest.raises(ValueError, match="does not allow"):
        scheduling_poll_state.apply_synthetic_poll_mutation(
            (closed,),
            scheduling_poll_state.PollMutationRequest(
                scheduling_poll_state.PollAction.ADD_OPTION,
                "poll-alpha",
                option=_option("option-bravo"),
            ),
            readiness=_ready(),
        )


def test_out094_remains_reserved_not_public_and_never_dispatches() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
    _, result = scheduling_poll_state.apply_synthetic_poll_mutation(
        (),
        scheduling_poll_state.PollMutationRequest(
            scheduling_poll_state.PollAction.CREATE,
            "poll-alpha",
        ),
        readiness=_ready(),
    )
    assert result.dispatched is False
    rendered = repr(result).lower()
    for marker in (
        "https://",
        "http://",
        "selector",
        "xpath",
        "css=",
        "cookie",
        "token",
        "graph.microsoft",
        "@",
    ):
        assert marker not in rendered
