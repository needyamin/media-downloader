"""Canonical module entrypoint for Linux AppImage build flow."""

from __future__ import annotations

from desktop_tools.app.build_tools.linux_appimage_build import main as _main_impl


def main() -> None:
    """Run the Linux AppImage build flow."""
    _main_impl()


if __name__ == "__main__":
    main()

