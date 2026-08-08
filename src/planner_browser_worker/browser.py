"""Planner compatibility imports for canonical M365 browser lifecycle."""

from __future__ import annotations

from m365_browser_worker.browser import (
    CONDITIONAL_ACCESS_MARKERS,
    BrowserConfig,
    PersistentBrowser,
    detect_conditional_access_block,
)

__all__ = [
    "BrowserConfig",
    "PersistentBrowser",
    "CONDITIONAL_ACCESS_MARKERS",
    "detect_conditional_access_block",
]
