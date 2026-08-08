"""Console entry point for the control plane."""

from __future__ import annotations

from .server import run


def main() -> None:
    """Start the control plane."""
    run()


if __name__ == "__main__":  # pragma: no cover
    main()
