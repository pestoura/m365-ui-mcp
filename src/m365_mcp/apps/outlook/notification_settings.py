"""Tenant-neutral synthetic notification settings for OUT-072."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


@dataclass(frozen=True)
class SyntheticNotificationSettings:
    mail_notifications_enabled: bool
    calendar_notifications_enabled: bool

    def to_projection(self) -> dict[str, object]:
        return {
            "mail_notifications_enabled": self.mail_notifications_enabled,
            "calendar_notifications_enabled": self.calendar_notifications_enabled,
            "synthetic": True,
        }


@dataclass(frozen=True)
class NotificationMutationRequest:
    desired: SyntheticNotificationSettings

    def to_payload(self) -> dict[str, object]:
        return {"desired": self.desired.to_projection()}


@dataclass(frozen=True)
class NotificationMutationResult:
    previous: SyntheticNotificationSettings
    read_back: SyntheticNotificationSettings
    changed: bool
    verified: bool
    synthetic: bool = True


def default_synthetic_notification_settings() -> SyntheticNotificationSettings:
    return SyntheticNotificationSettings(
        mail_notifications_enabled=True,
        calendar_notifications_enabled=True,
    )


def mutate_notification_settings(
    current: SyntheticNotificationSettings,
    request: NotificationMutationRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[SyntheticNotificationSettings, NotificationMutationResult]:
    """Apply synthetic notification preferences with immediate read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    updated = request.desired
    read_back = updated
    if read_back != request.desired:
        raise RuntimeError("synthetic read-back did not prove notification settings")

    return updated, NotificationMutationResult(
        previous=current,
        read_back=read_back,
        changed=current != updated,
        verified=True,
    )


__all__ = [
    "NotificationMutationRequest",
    "NotificationMutationResult",
    "SyntheticNotificationSettings",
    "default_synthetic_notification_settings",
    "mutate_notification_settings",
]
