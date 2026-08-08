import pytest

import m365_mcp.result_fields as result_fields


def _schema() -> result_fields.ResultFieldSchema:
    return result_fields.ResultFieldSchema(
        (
            result_fields.ResultFieldDefinition(
                name="status",
                sensitivity=result_fields.FieldSensitivity.STANDARD,
                exposure=result_fields.FieldExposure.VALUE,
            ),
            result_fields.ResultFieldDefinition(
                name="access_token",
                sensitivity=result_fields.FieldSensitivity.SECRET,
                exposure=result_fields.FieldExposure.REDACTED,
            ),
        )
    )


def test_secret_field_is_never_projected_in_clear_text() -> None:
    raw_secret = "opaque-token-value"
    result = result_fields.project_secret_aware_fields(
        {"status": "ok", "access_token": raw_secret},
        _schema(),
    )

    assert result.fields["status"] == "ok"
    assert result.fields["access_token"] == {"redacted": True, "present": True}
    assert raw_secret not in repr(result)
    assert result.redacted_fields == ("access_token",)
    assert result.contains_clear_secret is False


def test_null_secret_projects_presence_false_without_value() -> None:
    result = result_fields.project_secret_aware_fields(
        {"status": "ok", "access_token": None},
        _schema(),
    )

    assert result.fields["access_token"] == {"redacted": True, "present": False}


def test_secret_field_cannot_be_configured_for_value_exposure() -> None:
    with pytest.raises(ValueError, match="secret result field cannot use VALUE"):
        result_fields.ResultFieldDefinition(
            name="token",
            sensitivity=result_fields.FieldSensitivity.SECRET,
            exposure=result_fields.FieldExposure.VALUE,
        )


def test_unknown_unclassified_field_fails_closed() -> None:
    with pytest.raises(ValueError, match="unclassified result fields"):
        result_fields.project_secret_aware_fields(
            {
                "status": "ok",
                "access_token": "opaque",
                "new_field": "unreviewed",
            },
            _schema(),
        )


def test_missing_classified_field_fails_closed() -> None:
    with pytest.raises(ValueError, match="missing classified result fields"):
        result_fields.project_secret_aware_fields(
            {"status": "ok"},
            _schema(),
        )


def test_field_definitions_must_be_unique_semantic_tokens() -> None:
    standard = result_fields.ResultFieldDefinition(
        name="status",
        sensitivity=result_fields.FieldSensitivity.STANDARD,
        exposure=result_fields.FieldExposure.VALUE,
    )

    with pytest.raises(ValueError, match="must be unique"):
        result_fields.ResultFieldSchema((standard, standard))

    with pytest.raises(ValueError, match="semantic token"):
        result_fields.ResultFieldDefinition(
            name="bad field",
            sensitivity=result_fields.FieldSensitivity.STANDARD,
            exposure=result_fields.FieldExposure.VALUE,
        )


def test_standard_fields_may_be_deliberately_redacted() -> None:
    schema = result_fields.ResultFieldSchema(
        (
            result_fields.ResultFieldDefinition(
                name="opaque_id",
                sensitivity=result_fields.FieldSensitivity.STANDARD,
                exposure=result_fields.FieldExposure.REDACTED,
            ),
        )
    )
    result = result_fields.project_secret_aware_fields(
        {"opaque_id": "resource-123"},
        schema,
    )

    assert result.fields["opaque_id"] == {"redacted": True, "present": True}
    assert result.redacted_fields == ("opaque_id",)
