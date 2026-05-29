"""Compile and sanity-check every project Python script."""

from __future__ import annotations

import compileall
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src" / "desktop_tools"
ROOT_SCRIPTS = (REPO_ROOT / "run.py",)


def _iter_project_python_files():
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path
    for path in ROOT_SCRIPTS:
        if path.is_file():
            yield path


def check_compile_all() -> None:
    failed: list[str] = []
    count = 0
    for path in _iter_project_python_files():
        if not compileall.compile_file(str(path), quiet=1):
            failed.append(str(path.relative_to(REPO_ROOT)))
        count += 1
    print(f"OK compile: {count} project Python files")
    if failed:
        print("Compile failures:")
        for item in failed:
            print(f"  - {item}")
        raise SystemExit(1)


def check_anika_settings_window() -> None:
    """Open the break settings dialog briefly (headless-friendly)."""
    import tkinter as tk

    from desktop_tools.tools.media_downloader.launchers import open_anika_settings

    root = tk.Tk()
    root.withdraw()
    try:
        window = open_anika_settings(root)
        root.update()
        window.update()
        if window is None or not window.winfo_exists():
            raise SystemExit("Anika settings window did not open")
        window.destroy()
    finally:
        try:
            root.destroy()
        except Exception:
            pass
    print("OK integration: open_anika_settings window")


def check_anika_subprocess_launch() -> None:
    """Start Anika briefly to ensure the entry script runs."""
    import os
    import time

    anika_dir = SRC_ROOT / "anika"
    main_script = anika_dir / "main.py"
    if not main_script.is_file():
        raise SystemExit(f"Anika entry script missing: {main_script}")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(anika_dir)
    proc = subprocess.Popen(
        [sys.executable, str(main_script)],
        cwd=str(anika_dir),
        env=env,
    )
    time.sleep(2)
    if proc.poll() is not None:
        raise SystemExit(f"Anika subprocess exited early with code {proc.returncode}")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
    print("OK integration: open_anika subprocess launch")


def check_anika_main_help() -> None:
    """Run anika/main.py import path without starting the GUI mainloop."""
    anika_dir = SRC_ROOT / "anika"
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(anika_dir)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import main; assert callable(main.verify_assets); assert callable(main.main)",
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
        raise SystemExit(f"anika main module check failed: {detail}")
    print("OK script: anika/main.py (module API)")


def check_background_remover() -> None:
    from desktop_tools.tools.bg_remover_checks import main as bg_remover_main

    bg_remover_main()


def check_uninstall_cleanup() -> None:
    from desktop_tools.tools.uninstall_cleanup_checks import main as uninstall_main

    uninstall_main()


def main() -> None:
    check_compile_all()
    check_anika_main_help()
    check_anika_settings_window()
    check_anika_subprocess_launch()
    check_background_remover()
    check_uninstall_cleanup()
    print("Script checks passed.")


if __name__ == "__main__":
    main()
