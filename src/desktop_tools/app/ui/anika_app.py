"""Launch the Anika desktop mascot in an isolated subprocess."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_ANIKA_PROCESS: subprocess.Popen | None = None


def _resolve_anika_dir() -> Path:
    """Locate the anika package directory in development or packaged layouts."""
    candidates: list[Path] = [
        Path(__file__).resolve().parents[2] / "anika",
    ]
    try:
        from desktop_tools.shared.resources import get_project_root

        bundle_root = get_project_root()
        candidates.extend(
            [
                bundle_root / "desktop_tools" / "anika",
                bundle_root / "anika",
                bundle_root / "src" / "desktop_tools" / "anika",
                # Legacy bundle layout
                bundle_root / "desktop_tools" / "yfun",
            ]
        )
    except Exception:
        pass

    for candidate in candidates:
        if (candidate / "main.py").is_file():
            return candidate
    return candidates[0]


def open_anika(parent=None):
    """Start Anika in a separate process (avoids `app` package name clashes with desktop_tools.app)."""
    global _ANIKA_PROCESS

    if _ANIKA_PROCESS is not None and _ANIKA_PROCESS.poll() is None:
        return None

    anika_dir = _resolve_anika_dir()
    main_script = anika_dir / "main.py"
    if not main_script.is_file():
        raise FileNotFoundError(f"Anika entry script not found: {main_script}")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(anika_dir)
    env["ANIKA_OPEN_SETTINGS"] = "1"
    # Legacy env name from older builds
    env["YFUN_OPEN_SETTINGS"] = "1"
    # Use Media Downloader tray only — no second Anika icon
    env["ANIKA_NO_TRAY"] = "1"

    _ANIKA_PROCESS = subprocess.Popen(
        [sys.executable, str(main_script)],
        cwd=str(anika_dir),
        env=env,
    )
    return None
