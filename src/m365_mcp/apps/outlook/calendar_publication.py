"""Synthetic-only calendar publication state for OUT-097.

Publication is represented by a deterministic opaque semantic key, never by a
URL or location. The model performs local publish/unpublish read-back only and
carries no tenant identity, selector, session, token or live Microsoft 365 data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_FORBIDDEN_KEY_MARKERS = ("://", "http", "www", "/", ".", "@")
_MAX_PUBLICATIONS = 100


class PublicationAction(StrEnum):
    """Closed synthetic publication mutations."""

    PUBLISH = "PUBLISH"
    UNPUBLISH = "UNPUBLISH"


class PublicationDetail(StrEnum):
    """Closed synthetic publication detail levels."""

    FREE_BUSY_ONLY = "FREE_BUSY_ONLY"
    LIMITED_DETAILS = "LIMITED_DETAILS"
    FULL_DETAILS = "FULL_DETAILS"


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


def _validate_publication_key(value: str) -> None:
    _validate_key("publication_key", value)
    lowered = value.lower()
    if any(marker in lowered for marker in _FORBIDDEN_KEY_MARKERS):
        raise ValueError("publication_key must not encode a location")


def _publication_key(calendar_key: str, detail: PublicationDetail) -> str:
    digest = sha256(f"{calendar_key}|{detail.value}".encode()).hexdigest()[:16]
    return f"pub-{digest}"


@dataclass(frozen=True)
class SyntheticPublication:
    """One local synthetic publication record."""

    calendar_key: str
    publication_key: str
    detail: PublicationDetail

    def __post_init__(self) -> None:
        _validate_key("calendar_key", self.calendar_key)
        _validate_publication_key(self.publication_key)
        if not isinstance(self.detail, PublicationDetail):
            raise ValueError("detail must be a closed PublicationDetail")


@dataclass(frozen=True)
class PublicationRequest:
    """One local publish/unpublish request."""

    action: PublicationAction
    calendar_key: str
    detail: PublicationDetail = PublicationDetail.FREE_BUSY_ONLY

    def __post_init__(self) -> None:
        if not isinstance(self.action, PublicationAction):
            raise ValueError("action must be a closed PublicationAction")
        _validate_key("calendar_key", self.calendar_key)
        if not isinstance(self.detail, PublicationDetail):
            raise ValueError("detail must be a closed PublicationDetail")


@dataclass(frozen=True)
class PublicationState:
    """Read-side synthetic publication projection."""

    calendar_key: str
    is_published: bool
    publication_key: str | None
    detail: PublicationDetail | None
    synthetic: bool

    def to_projection(self) -> dict[str, object]:
        return {
            "calendar_key": self.calendar_key,
            "is_published": self.is_published,
            "publication_key": self.publication_key,
            "detail": self.detail.value if self.detail is not None else None,
            "synthetic": self.synthetic,
        }


@dataclass(frozen=True)
class PublicationResult:
    """Read-back proof for one synthetic publication mutation."""

    action: PublicationAction
    calendar_key: str
    publication_key: str | None
    previous_publication_key: str | None
    detail: PublicationDetail | None
    changed: bool
    verified: bool
    synthetic: bool


def _require_ready(readiness: OutlookReadinessReport) -> None:
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _validate_publications(publications: tuple[SyntheticPublication, ...]) -> None:
    if len(publications) > _MAX_PUBLICATIONS:
        raise ValueError("calendar publications exceed bounded size")
    keys = tuple(item.calendar_key for item in publications)
    if len(set(keys)) != len(keys):
        raise ValueError("calendar publications contain duplicate calendar_key")


def read_calendar_publication(
    publications: tuple[SyntheticPublication, ...],
    *,
    calendar_key: str,
    readiness: OutlookReadinessReport,
) -> PublicationState:
    """Read one calendar's synthetic publication state."""
    _require_ready(readiness)
    _validate_key("calendar_key", calendar_key)
    _validate_publications(publications)
    matches = tuple(item for item in publications if item.calendar_key == calendar_key)
    if not matches:
        return PublicationState(
            calendar_key=calendar_key,
            is_published=False,
            publication_key=None,
            detail=None,
            synthetic=True,
        )
    item = matches[0]
    return PublicationState(
        calendar_key=calendar_key,
        is_published=True,
        publication_key=item.publication_key,
        detail=item.detail,
        synthetic=True,
    )


def apply_calendar_publication(
    publications: tuple[SyntheticPublication, ...],
    request: PublicationRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticPublication, ...], PublicationResult]:
    """Apply a local synthetic publish/unpublish and prove state by read-back."""
    _require_ready(readiness)
    _validate_publications(publications)
    previous_state = read_calendar_publication(
        publications,
        calendar_key=request.calendar_key,
        readiness=readiness,
    )
    remaining = tuple(
        item for item in publications if item.calendar_key != request.calendar_key
    )

    if request.action is PublicationAction.PUBLISH:
        key = _publication_key(request.calendar_key, request.detail)
        _validate_publication_key(key)
        record = SyntheticPublication(request.calendar_key, key, request.detail)
        if not previous_state.is_published and len(publications) >= _MAX_PUBLICATIONS:
            raise ValueError("calendar publications exceed bounded size")
        updated = remaining + (record,)
        changed = (
            previous_state.publication_key != key
            or previous_state.detail is not request.detail
        )
        expected_published = True
        expected_key: str | None = key
        expected_detail: PublicationDetail | None = request.detail
    elif request.action is PublicationAction.UNPUBLISH:
        updated = remaining
        changed = previous_state.is_published
        expected_published = False
        expected_key = None
        expected_detail = None
    else:
        raise ValueError("unsupported publication action")

    updated = tuple(sorted(updated, key=lambda item: item.calendar_key))
    read_back = read_calendar_publication(
        updated,
        calendar_key=request.calendar_key,
        readiness=readiness,
    )
    if (
        read_back.is_published is not expected_published
        or read_back.publication_key != expected_key
        or read_back.detail is not expected_detail
    ):
        raise RuntimeError("calendar publication read-back did not prove requested state")

    return updated, PublicationResult(
        action=request.action,
        calendar_key=request.calendar_key,
        publication_key=read_back.publication_key,
        previous_publication_key=previous_state.publication_key,
        detail=read_back.detail,
        changed=changed,
        verified=True,
        synthetic=True,
    )


__all__ = [
    "PublicationAction",
    "PublicationDetail",
    "PublicationRequest",
    "PublicationResult",
    "PublicationState",
    "SyntheticPublication",
    "apply_calendar_publication",
    "read_calendar_publication",
]
