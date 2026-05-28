"""Canonical module entrypoint for Windows/Nuitka build flow."""

from __future__ import annotations

from desktop_tools.app.build_tools.nuitka_build import main as _main_impl


def main() -> None:
    """Run the Windows/Nuitka build flow."""
    _main_impl()


if __name__ == "__main__":
    main()

