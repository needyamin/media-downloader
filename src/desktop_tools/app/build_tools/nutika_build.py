"""Backward-compatible shim for the legacy misspelled build module name."""

from __future__ import annotations

from desktop_tools.app.build_tools.nuitka_build import main


if __name__ == "__main__":
    main()

