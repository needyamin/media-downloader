"""Root launcher for the media downloader GUI."""

from __future__ import annotations

from pathlib import Path
import runpy
import sys


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
APP_SCRIPT = ROOT_DIR / "src" / "desktop_tools" / "app" / "media_download.py"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if __name__ == "__main__":
    runpy.run_path(str(APP_SCRIPT), run_name="__main__")
