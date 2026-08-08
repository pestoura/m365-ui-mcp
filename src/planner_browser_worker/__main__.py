"""Planner compatibility entry point for the canonical M365 browser worker."""

from __future__ import annotations

from m365_browser_worker.__main__ import main

__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover
    main()
