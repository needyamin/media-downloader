"""Import, entrypoint, and launcher smoke checks for desktop tool architecture."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path


MODULES = [
    "desktop_tools.tools.media_downloader.main",
    "desktop_tools.tools.media_downloader.launchers",
    "desktop_tools.app.ui.entrypoints",
    "desktop_tools.app.services.anika_config",
    "desktop_tools.app.hub.tool_actions",
    "desktop_tools.app.build_tools.manifest",
    "desktop_tools.app.build_tools.nuitka",
    "desktop_tools.app.build_tools.linux_appimage",
]

LAUNCHER_FUNCTIONS = (
    "open_converter",
    "open_background_remover",
    "open_screenshot_studio",
    "open_yscreenrecorder",
    "open_anika",
    "open_anika_settings",
)

UI_APP_MODULES = (
    "desktop_tools.app.ui.converter_app",
    "desktop_tools.app.ui.background_remover_app",
    "desktop_tools.app.ui.screenshot_app",
    "desktop_tools.app.ui.yscreenrecorder_app",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _anika_dir() -> Path:
    return _repo_root() / "src" / "desktop_tools" / "anika"


def check_anika_assets_subprocess() -> None:
    """Verify Anika assets in an isolated process (no app-package name clash)."""
    anika_dir = _anika_dir()
    main_script = anika_dir / "main.py"
    if not main_script.is_file():
        raise SystemExit(f"Anika entry script missing: {main_script}")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(anika_dir)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from main import verify_assets; verify_assets(); print('anika assets ok')",
        ],
        cwd=str(anika_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise SystemExit(f"Anika asset check failed ({result.returncode}): {detail}")
    print("OK anika: verify_assets (subprocess)")


def check_anika_launcher_resolution() -> None:
    entrypoints_file = importlib.import_module("desktop_tools.app.ui.entrypoints").__file__
    if not entrypoints_file:
        raise SystemExit("Could not resolve desktop_tools.app.ui.entrypoints path")
    resolved = Path(entrypoints_file).resolve().parents[2] / "anika"
    if not (resolved / "main.py").is_file():
        raise SystemExit(f"Anika launcher path invalid: {resolved}")
    print(f"OK anika: launcher resolves to {resolved}")


def main() -> None:
    for module_name in MODULES:
        importlib.import_module(module_name)
        print(f"OK import: {module_name}")

    for module_name in UI_APP_MODULES:
        importlib.import_module(module_name)
        print(f"OK import: {module_name}")

    from desktop_tools.app.build_tools import manifest
    from desktop_tools.tools.media_downloader import launchers

    if not callable(getattr(manifest, "main", None)):
        raise SystemExit("Expected desktop_tools.app.build_tools.manifest.main to be callable")
    print("OK callable: desktop_tools.app.build_tools.manifest.main")

    for function_name in LAUNCHER_FUNCTIONS:
        if not callable(getattr(launchers, function_name, None)):
            raise SystemExit(f"Missing launcher: {function_name}")
    print(f"OK launchers: {', '.join(LAUNCHER_FUNCTIONS)}")

    check_anika_launcher_resolution()
    check_anika_assets_subprocess()

    print("Smoke checks passed.")


if __name__ == "__main__":
    main()
