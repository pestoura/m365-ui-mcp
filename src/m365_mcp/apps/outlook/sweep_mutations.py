"""Synthetic Outlook Sweep discovery/manage semantics for OUT-060."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_SWEEPS = 100


def _semantic_token(value: str, name: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")
    return value


class SweepMode(StrEnum):
    MOVE_CURRENT = "MOVE_CURRENT"
    MOVE_CURRENT_AND_FUTURE = "MOVE_CURRENT_AND_FUTURE"
    DELETE_CURRENT_AND_FUTURE = "DELETE_CURRENT_AND_FUTURE"
    KEEP_LATEST = "KEEP_LATEST"
    DELETE_OLDER_THAN_10_DAYS = "DELETE_OLDER_THAN_10_DAYS"

    @property
    def destructive(self) -> bool:
        return self in {
            SweepMode.DELETE_CURRENT_AND_FUTURE,
            SweepMode.KEEP_LATEST,
            SweepMode.DELETE_OLDER_THAN_10_DAYS,
        }


@dataclass(frozen=True)
class SyntheticSweepRule:
    sweep_key: str
    sender_key: str
    mode: SweepMode
    target_folder_key: str | None = None
    enabled: bool = True
    synthetic: bool = True

    def __post_init__(self) -> None:
        _semantic_token(self.sweep_key, "sweep_key")
        _semantic_token(self.sender_key, "sender_key")
        move_mode = self.mode in {
            SweepMode.MOVE_CURRENT,
            SweepMode.MOVE_CURRENT_AND_FUTURE,
        }
        if move_mode and self.target_folder_key is None:
            raise ValueError("move Sweep modes require target_folder_key")
        if not move_mode and self.target_folder_key is not None:
            raise ValueError("delete/keep Sweep modes do not accept target_folder_key")
        if self.target_folder_key is not None:
            _semantic_token(self.target_folder_key, "target_folder_key")
        if not self.synthetic:
            raise ValueError("Sweep foundation is synthetic-only")

    @property
    def destructive(self) -> bool:
        return self.mode.destructive

    def to_projection(self) -> dict[str, object]:
        return {
            "sweep_key": self.sweep_key,
            "sender_key": self.sender_key,
            "mode": self.mode.value,
            "target_folder_key": self.target_folder_key,
            "enabled": self.enabled,
            "destructive": self.destructive,
            "synthetic": True,
        }


class SweepMutationAction(StrEnum):
    UPSERT = "UPSERT"
    DELETE = "DELETE"


@dataclass(frozen=True)
class SweepMutationRequest:
    action: SweepMutationAction
    sweep_key: str
    rule: SyntheticSweepRule | None = None

    def __post_init__(self) -> None:
        _semantic_token(self.sweep_key, "sweep_key")
        if self.action is SweepMutationAction.UPSERT:
            if self.rule is None or self.rule.sweep_key != self.sweep_key:
                raise ValueError("UPSERT requires a matching synthetic Sweep rule")
        elif self.rule is not None:
            raise ValueError("DELETE does not accept rule")

    def to_payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "sweep_key": self.sweep_key,
            "rule": None if self.rule is None else self.rule.to_projection(),
        }


@dataclass(frozen=True)
class SweepMutationResult:
    sweep_key: str
    action: SweepMutationAction
    changed: bool
    verified: bool
    read_back: SyntheticSweepRule | None
    synthetic: bool = True


def default_synthetic_sweeps() -> tuple[SyntheticSweepRule, ...]:
    return (
        SyntheticSweepRule(
            sweep_key="sweep-project",
            sender_key="person-alpha",
            mode=SweepMode.MOVE_CURRENT_AND_FUTURE,
            target_folder_key="archive",
        ),
    )


def _validate_catalog(rules: tuple[SyntheticSweepRule, ...]) -> None:
    if len(rules) > _MAX_SWEEPS:
        raise ValueError("Sweep catalog exceeds bounded size")
    keys = tuple(rule.sweep_key for rule in rules)
    if len(keys) != len(set(keys)):
        raise ValueError("Sweep keys must be unique")
    if any(not rule.synthetic for rule in rules):
        raise ValueError("Sweep catalog must remain synthetic")


def list_sweeps(
    *,
    readiness: OutlookReadinessReport,
    rules: tuple[SyntheticSweepRule, ...] | None = None,
) -> tuple[SyntheticSweepRule, ...]:
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    catalog = default_synthetic_sweeps() if rules is None else rules
    _validate_catalog(catalog)
    return tuple(sorted(catalog, key=lambda item: item.sweep_key))


def manage_sweeps(
    rules: tuple[SyntheticSweepRule, ...],
    request: SweepMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    allow_destructive: bool = False,
) -> tuple[tuple[SyntheticSweepRule, ...], SweepMutationResult]:
    """Apply one synthetic Sweep definition mutation with explicit read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    _validate_catalog(rules)

    existing = next((item for item in rules if item.sweep_key == request.sweep_key), None)
    if request.action is SweepMutationAction.UPSERT:
        assert request.rule is not None
        if request.rule.destructive and not allow_destructive:
            raise PermissionError("destructive Sweep mode requires explicit policy allowance")
        replacement = request.rule
        updated = tuple(item for item in rules if item.sweep_key != request.sweep_key) + (
            replacement,
        )
        changed = existing != replacement
    else:
        updated = tuple(item for item in rules if item.sweep_key != request.sweep_key)
        changed = existing is not None

    _validate_catalog(updated)
    ordered = tuple(sorted(updated, key=lambda item: item.sweep_key))
    matches = tuple(item for item in ordered if item.sweep_key == request.sweep_key)
    read_back = matches[0] if len(matches) == 1 else None
    if request.action is SweepMutationAction.UPSERT and read_back != request.rule:
        raise RuntimeError("synthetic read-back did not prove Sweep state")
    if request.action is SweepMutationAction.DELETE and matches:
        raise RuntimeError("synthetic read-back did not prove Sweep deletion")

    return ordered, SweepMutationResult(
        sweep_key=request.sweep_key,
        action=request.action,
        changed=changed,
        verified=True,
        read_back=read_back,
    )


__all__ = [
    "SweepMode",
    "SweepMutationAction",
    "SweepMutationRequest",
    "SweepMutationResult",
    "SyntheticSweepRule",
    "default_synthetic_sweeps",
    "list_sweeps",
    "manage_sweeps",
]
