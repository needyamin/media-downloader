"""Root launcher for the media downloader GUI."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def cleanup_legacy_app_build_dir() -> None:
    """Delete old in-app build artifacts once they are no longer locked."""
    legacy_build_dir = ROOT_DIR / "src" / "desktop_tools" / "app" / "build"
    if not legacy_build_dir.exists():
        return

    try:
        shutil.rmtree(legacy_build_dir)
        print(f"Removed legacy build folder: {legacy_build_dir}")
    except OSError:
        # Ignore locks/transient file errors; cleanup can succeed on a later run.
        pass


if __name__ == "__main__":
    from desktop_tools.tools.media_downloader.main import run_main_app

    cleanup_legacy_app_build_dir()
    run_main_app()
