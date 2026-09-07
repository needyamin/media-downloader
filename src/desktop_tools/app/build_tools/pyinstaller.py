"""Canonical Windows installer build: PyInstaller onedir + Inno Setup."""

from __future__ import annotations

from desktop_tools.app.build_tools.pyinstaller_build import main as _main_impl


def main() -> None:
    """Build Media-Downloader.exe (onedir) and MediaDownloader_Setup.exe."""
    _main_impl()


if __name__ == "__main__":
    main()
