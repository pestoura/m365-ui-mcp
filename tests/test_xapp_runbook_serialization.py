import json

import pytest

from m365_mcp.xapp_runbook_serialization import (
    CanonicalRunbook,
    CanonicalRunbookNode,
    canonical_runbook_digest,
    canonical_runbook_json,
)


def test_canonical_serialization_is_order_independent_and_deterministic() -> None:
    alpha = CanonicalRunbookNode(
        node_id="alpha",
        tool_name="planner.list_tasks",
        input_binding_keys=("binding-b", "binding-a"),
    )
    beta = CanonicalRunbookNode(
        node_id="beta",
        tool_name="planner.get_task",
        depends_on=("alpha",),
    )

    first = CanonicalRunbook("review", "1.0.0", (beta, alpha))
    second = CanonicalRunbook(
        "review",
        "1.0.0",
        (
            CanonicalRunbookNode(
                node_id="alpha",
                tool_name="planner.list_tasks",
                input_binding_keys=("binding-a", "binding-b"),
            ),
            beta,
        ),
    )

    assert canonical_runbook_json(first) == canonical_runbook_json(second)
    assert canonical_runbook_digest(first) == canonical_runbook_digest(second)
    assert len(canonical_runbook_digest(first)) == 64
    assert canonical_runbook_digest(first).islower()

    payload = json.loads(canonical_runbook_json(first))
    assert [node["node_id"] for node in payload["nodes"]] == ["alpha", "beta"]
    assert payload["nodes"][0]["input_binding_keys"] == ["binding-a", "binding-b"]


def test_canonical_projection_contains_semantic_metadata_only() -> None:
    runbook = CanonicalRunbook(
        runbook_key="review",
        version="1.0.0",
        nodes=(CanonicalRunbookNode("alpha", "planner.list_tasks"),),
    )

    encoded = canonical_runbook_json(runbook)

    assert "callable" not in encoded
    assert "selector" not in encoded
    assert "script" not in encoded
    assert "://" not in encoded
    assert set(runbook.canonical_projection()) == {"runbook_key", "version", "nodes"}


def test_runbook_rejects_unknown_self_and_duplicate_dependencies() -> None:
    with pytest.raises(ValueError, match="unknown node"):
        CanonicalRunbook(
            "review",
            "1.0.0",
            (CanonicalRunbookNode("alpha", "planner.list_tasks", ("missing",)),),
        )

    with pytest.raises(ValueError, match="depend on itself"):
        CanonicalRunbookNode("alpha", "planner.list_tasks", ("alpha",))

    with pytest.raises(ValueError, match="dependencies must be unique"):
        CanonicalRunbookNode("beta", "planner.get_task", ("alpha", "alpha"))


def test_runbook_rejects_locator_like_or_unbounded_metadata() -> None:
    with pytest.raises(ValueError, match="semantic token"):
        CanonicalRunbookNode("alpha", "https://example.invalid")

    with pytest.raises(ValueError, match="bounded size"):
        CanonicalRunbookNode(
            "alpha",
            "planner.list_tasks",
            input_binding_keys=tuple(f"binding-{index}" for index in range(101)),
        )

    nodes = tuple(
        CanonicalRunbookNode(f"node-{index}", "planner.list_tasks")
        for index in range(101)
    )
    with pytest.raises(ValueError, match="bounded node count"):
        CanonicalRunbook("review", "1.0.0", nodes)
