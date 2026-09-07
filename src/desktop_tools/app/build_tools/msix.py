"""Canonical module entrypoint for Windows MSIX packaging."""

from __future__ import annotations

from desktop_tools.app.build_tools.msix_build import main as _main_impl


def main() -> None:
    """Build the Microsoft Store MSIX package."""
    _main_impl()


if __name__ == "__main__":
    main()
