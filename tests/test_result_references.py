import pytest

import m365_mcp.result_references as result_references


CONTENT_DIGEST = "a" * 64


def test_reference_hashes_locator_and_projects_no_storage_location() -> None:
    raw_locator = "artifact://private/run-123/evidence.json"
    reference = result_references.make_artifact_reference(
        kind=result_references.ReferenceKind.EVIDENCE,
        artifact_type="policy_evidence",
        locator=raw_locator,
        content_digest=CONTENT_DIGEST,
        media_type="application/json",
        size_bytes=128,
    )

    projection = reference.to_projection()
    assert len(reference.locator_digest) == 64
    assert raw_locator not in repr(reference)
    assert raw_locator not in str(projection)
    assert "locator_digest" not in projection
    assert projection["content_digest"] == CONTENT_DIGEST
    assert projection["size_bytes"] == 128


def test_reference_identity_is_deterministic_and_content_addressed() -> None:
    first = result_references.make_artifact_reference(
        kind=result_references.ReferenceKind.ARTIFACT,
        artifact_type="report",
        locator="artifact://run/report.json",
        content_digest=CONTENT_DIGEST,
        media_type="application/json",
    )
    same = result_references.make_artifact_reference(
        kind=result_references.ReferenceKind.ARTIFACT,
        artifact_type="report",
        locator="artifact://run/report.json",
        content_digest=CONTENT_DIGEST,
        media_type="application/json",
    )
    changed = result_references.make_artifact_reference(
        kind=result_references.ReferenceKind.ARTIFACT,
        artifact_type="report",
        locator="artifact://run/report.json",
        content_digest="b" * 64,
        media_type="application/json",
    )

    assert first.reference_id == same.reference_id
    assert first.reference_id != changed.reference_id


def test_artifact_and_evidence_roles_remain_distinct() -> None:
    artifact = result_references.make_artifact_reference(
        kind=result_references.ReferenceKind.ARTIFACT,
        artifact_type="snapshot",
        locator="artifact://run/snapshot",
        content_digest=CONTENT_DIGEST,
        media_type="application/json",
    )
    evidence = result_references.make_artifact_reference(
        kind=result_references.ReferenceKind.EVIDENCE,
        artifact_type="snapshot",
        locator="artifact://run/snapshot",
        content_digest=CONTENT_DIGEST,
        media_type="application/json",
    )

    assert artifact.reference_id != evidence.reference_id
    assert artifact.to_projection()["kind"] == "ARTIFACT"
    assert evidence.to_projection()["kind"] == "EVIDENCE"


def test_referenced_result_deduplicates_by_opaque_reference_identity() -> None:
    reference = result_references.make_artifact_reference(
        kind=result_references.ReferenceKind.EVIDENCE,
        artifact_type="ui_attestation",
        locator="artifact://run/attestation",
        content_digest=CONTENT_DIGEST,
        media_type="application/json",
    )

    with pytest.raises(ValueError, match="references must be unique"):
        result_references.ReferencedResult(
            result={"status": "ok"},
            references=(reference, reference),
        )


def test_referenced_result_does_not_modify_semantic_result() -> None:
    semantic_result = {"count": 3}
    reference = result_references.make_artifact_reference(
        kind=result_references.ReferenceKind.ARTIFACT,
        artifact_type="sbom",
        locator="artifact://build/control-plane-sbom",
        content_digest=CONTENT_DIGEST,
        media_type="application/vnd.cyclonedx+json",
    )
    wrapped = result_references.ReferencedResult(
        result=semantic_result,
        references=(reference,),
    )

    assert wrapped.result is semantic_result
    assert wrapped.reference_projection() == (reference.to_projection(),)


def test_invalid_reference_metadata_fails_closed() -> None:
    with pytest.raises(ValueError, match="locator must not be empty"):
        result_references.make_artifact_reference(
            kind=result_references.ReferenceKind.ARTIFACT,
            artifact_type="report",
            locator=" ",
            content_digest=CONTENT_DIGEST,
            media_type="application/json",
        )

    with pytest.raises(ValueError, match="content_digest"):
        result_references.make_artifact_reference(
            kind=result_references.ReferenceKind.ARTIFACT,
            artifact_type="report",
            locator="artifact://report",
            content_digest="bad",
            media_type="application/json",
        )

    with pytest.raises(ValueError, match="media_type"):
        result_references.make_artifact_reference(
            kind=result_references.ReferenceKind.ARTIFACT,
            artifact_type="report",
            locator="artifact://report",
            content_digest=CONTENT_DIGEST,
            media_type="json",
        )
