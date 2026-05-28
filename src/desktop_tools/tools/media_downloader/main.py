"""Canonical entrypoint for launching the Media Downloader desktop app."""

from __future__ import annotations

from pathlib import Path
import runpy


def run_main_app() -> None:
    """Run the current main desktop application script."""
    app_script = Path(__file__).resolve().parents[2] / "app" / "media_download.py"
    runpy.run_path(str(app_script), run_name="__main__")


if __name__ == "__main__":
    run_main_app()

