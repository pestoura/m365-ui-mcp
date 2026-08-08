"""Typed resource lock definitions."""

from __future__ import annotations

from enum import StrEnum


class LockType(StrEnum):
    """Lock granularity types."""

    PLAN = "plan"
    TASK = "task"
    BUCKET = "bucket"
    SESSION = "session"
    BROWSER_PROFILE = "browser_profile"
