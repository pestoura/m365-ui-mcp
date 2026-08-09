"""Synthetic Outlook mail-forwarding settings for OUT-069.

Destination values are tenant-neutral semantic keys, never email addresses. Any
enablement or destination reconfiguration requires explicit policy allowance.
No message is sent and no browser/UI operation is performed.
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


def _semantic_token(value: str, name: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")
    if "@" in value:
        raise ValueError(f"{name} must be tenant-neutral and must not contain an email address")
    return value


@dataclass(frozen=True)
class SyntheticForwardingSettings:
    enabled: bool
    destination_key: str | None = None
    keep_copy: bool = False
    synthetic: bool = True

    def __post_init__(self) -> None:
        if self.destination_key is not None:
            _semantic_token(self.destination_key, "destination_key")
        if self.enabled and self.destination_key is None:
            raise ValueError("enabled forwarding requires destination_key")
        if not self.synthetic:
            raise ValueError("forwarding settings are synthetic-only")

    def to_projection(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "destination_key": self.destination_key,
            "keep_copy": self.keep_copy,
            "synthetic": True,
        }


def default_synthetic_forwarding_settings() -> SyntheticForwardingSettings:
    return SyntheticForwardingSettings(enabled=False)


@dataclass(frozen=True)
class ForwardingMutationRequest:
    desired: SyntheticForwardingSettings

    def to_payload(self) -> dict[str, object]:
        return {"desired": self.desired.to_projection()}


@dataclass(frozen=True)
class ForwardingMutationResult:
    changed: bool
    verified: bool
    read_back: SyntheticForwardingSettings
    sensitive_configuration: bool
    synthetic: bool = True


def read_forwarding_settings(
    settings: SyntheticForwardingSettings,
    *,
    readiness: OutlookReadinessReport,
) -> SyntheticForwardingSettings:
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not settings.synthetic:
        raise ValueError("forwarding settings must remain synthetic")
    return settings


def mutate_forwarding_settings(
    current: SyntheticForwardingSettings,
    request: ForwardingMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    allow_forwarding_configuration: bool = False,
) -> tuple[SyntheticForwardingSettings, ForwardingMutationResult]:
    """Apply desired synthetic forwarding state with explicit policy and read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not current.synthetic or not request.desired.synthetic:
        raise ValueError("forwarding settings must remain synthetic")

    desired = request.desired
    sensitive = desired.enabled or desired.destination_key != current.destination_key
    if sensitive and not allow_forwarding_configuration:
        raise PermissionError("forwarding configuration requires explicit policy allowance")

    read_back = read_forwarding_settings(desired, readiness=readiness)
    if read_back != desired:
        raise RuntimeError("synthetic read-back did not prove forwarding settings")
    return desired, ForwardingMutationResult(
        changed=desired != current,
        verified=True,
        read_back=read_back,
        sensitive_configuration=sensitive,
    )


__all__ = [
    "ForwardingMutationRequest",
    "ForwardingMutationResult",
    "SyntheticForwardingSettings",
    "default_synthetic_forwarding_settings",
    "mutate_forwarding_settings",
    "read_forwarding_settings",
]
