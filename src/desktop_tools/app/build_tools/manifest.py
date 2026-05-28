"""Canonical module entrypoint for build manifest generation."""

from __future__ import annotations

from desktop_tools.app.build_tools.build_manifest import main as _main_impl


def main() -> None:
    """Validate and print the shared build manifest."""
    _main_impl()


if __name__ == "__main__":
    main()

