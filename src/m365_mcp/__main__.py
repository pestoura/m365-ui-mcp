"""Canonical console entry point for the M365 control plane."""

from __future__ import annotations

from .server import run


def main() -> None:
    """Start the control plane through the canonical M365 namespace."""
    run()


if __name__ == "__main__":  # pragma: no cover
    main()
