"""Runtime checks for the Anika desktop assistant package."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
ANIKA_DIR = REPO_ROOT / "src" / "desktop_tools" / "anika"


def _anika_import(name: str):
    anika_path = str(ANIKA_DIR)
    if anika_path not in sys.path:
        sys.path.insert(0, anika_path)
    return importlib.import_module(name)


def check_modules_import() -> None:
    modules = [
        "main",
        "app.config",
        "app.menu_actions",
        "app.ui_theme",
        "app.assets",
        "app.particles",
        "app.window_detector",
        "app.hotkey",
        "app.tray",
        "app.gui",
    ]
    for name in modules:
        _anika_import(name)
        print(f"OK import: {name}")


def check_menu_actions() -> None:
    menu_actions = _anika_import("app.menu_actions")
    keys = {k for k, _ in menu_actions.PET_TOOL_ACTIONS}
    keys |= {k for k, _ in menu_actions.PET_FORCE_ACTIONS}
    keys.add(menu_actions.PET_QUIT_ACTION[0])
    expected_force = {
        "action", "sleeping", "dance", "waving", "crying", "eating",
        "study", "tea", "broom", "blush", "laugh", "shocked", "peek", "focus", "chase", "hide",
    }
    if keys - {"spellbook", "timer", "magic_clean", "quit"} != expected_force:
        raise SystemExit(f"Unexpected menu action keys: {keys}")
    print("OK menu_actions: action keys")


def check_theme_hub_match() -> None:
    ui_theme = _anika_import("app.ui_theme")
    theme = ui_theme.get_ui_theme()
    if theme["accent"] != "#2196F3" or theme["bg"] != "#ffffff":
        raise SystemExit(f"Hub theme mismatch: {theme}")
    config = _anika_import("app.config")
    gui_theme = config.get_gui_theme()
    if gui_theme["accent"] != "#2196F3":
        raise SystemExit(f"GUI theme mismatch: {gui_theme}")
    print("OK theme: hub-aligned colors")


def check_assets() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ANIKA_DIR)
    result = subprocess.run(
        [sys.executable, "-c", "from main import verify_assets; verify_assets()"],
        cwd=str(ANIKA_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise SystemExit((result.stderr or result.stdout or "verify_assets failed").strip())
    print("OK assets: verify_assets")


def main() -> None:
    if not ANIKA_DIR.is_dir():
        raise SystemExit(f"Anika directory missing: {ANIKA_DIR}")
    check_modules_import()
    check_menu_actions()
    check_theme_hub_match()
    check_assets()
    print("Anika checks passed.")


if __name__ == "__main__":
    main()
