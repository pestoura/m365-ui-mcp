from __future__ import annotations

from dataclasses import dataclass, field

from m365_mcp.apps.outlook import attachment_metadata, attachment_retrieval, readiness
from m365_mcp.result_references import ReferenceKind

EVIDENCE = "f" * 64


@dataclass
class MemorySink:
    locator: str = "artifact://synthetic/att-001"
    stored: list[tuple[str, str, bytes]] = field(default_factory=list)

    def store(self, *, attachment_key: str, media_type: str, payload: bytes) -> str:
        self.stored.append((attachment_key, media_type, payload))
        return self.locator


def _ready_report() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.DISCOVERY_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=1,
        blocked_count=0,
        reattestation_count=0,
    )


def _metadata() -> attachment_metadata.SyntheticAttachment:
    return attachment_metadata.SyntheticAttachment(
        attachment_key="att-001",
        message_key="msg-002",
        file_name="synthetic-meeting-notes.txt",
        media_type="text/plain",
        size_bytes=128,
    )


def test_retrieval_stores_bytes_but_projects_only_opaque_artifact_reference() -> None:
    payload_bytes = b"x" * 128
    sink = MemorySink()
    result = attachment_retrieval.retrieve_synthetic_attachment(
        _metadata(),
        attachment_retrieval.SyntheticAttachmentPayload(
            attachment_key="att-001",
            payload=payload_bytes,
        ),
        readiness=_ready_report(),
        sink=sink,
    )

    projection = result.to_projection()
    assert sink.stored == [("att-001", "text/plain", payload_bytes)]
    assert result.artifact.kind is ReferenceKind.ARTIFACT
    assert projection["artifact"]["artifact_type"] == "outlook_attachment"
    assert projection["artifact"]["size_bytes"] == 128
    assert payload_bytes not in repr(projection).encode()
    assert sink.locator not in repr(projection)
    assert "locator_digest" not in projection["artifact"]


def test_payload_key_and_size_must_match_metadata() -> None:
    sink = MemorySink()
    for payload in (
        attachment_retrieval.SyntheticAttachmentPayload("att-other", b"x" * 128),
        attachment_retrieval.SyntheticAttachmentPayload("att-001", b"x" * 127),
    ):
        try:
            attachment_retrieval.retrieve_synthetic_attachment(
                _metadata(),
                payload,
                readiness=_ready_report(),
                sink=sink,
            )
        except ValueError as exc:
            assert "does not match metadata" in str(exc)
        else:
            raise AssertionError("mismatched attachment payload must fail closed")
    assert sink.stored == []


def test_unready_context_and_empty_sink_locator_fail_closed() -> None:
    unready = readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.FOUNDATION_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=0,
        blocked_count=0,
        reattestation_count=0,
    )
    payload = attachment_retrieval.SyntheticAttachmentPayload("att-001", b"x" * 128)

    try:
        attachment_retrieval.retrieve_synthetic_attachment(
            _metadata(),
            payload,
            readiness=unready,
            sink=MemorySink(),
        )
    except ValueError as exc:
        assert "read-only discovery is not ready" in str(exc)
    else:
        raise AssertionError("unready retrieval must fail closed")

    try:
        attachment_retrieval.retrieve_synthetic_attachment(
            _metadata(),
            payload,
            readiness=_ready_report(),
            sink=MemorySink(locator=" "),
        )
    except ValueError as exc:
        assert "empty locator" in str(exc)
    else:
        raise AssertionError("empty artifact locator must fail closed")


def test_payload_validation_rejects_empty_and_oversized_bytes() -> None:
    try:
        attachment_retrieval.SyntheticAttachmentPayload("att-001", b"")
    except ValueError as exc:
        assert "must not be empty" in str(exc)
    else:
        raise AssertionError("empty attachment payload must fail closed")

    try:
        attachment_retrieval.SyntheticAttachmentPayload(
            "att-001",
            b"x" * (10 * 1024 * 1024 + 1),
        )
    except ValueError as exc:
        assert "exceeds retrieval size limit" in str(exc)
    else:
        raise AssertionError("oversized attachment payload must fail closed")
