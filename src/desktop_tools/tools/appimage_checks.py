"""Verify a built Linux AppImage bundle (run on Linux/WSL after linux_appimage build)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APPIMAGE_PATH = REPO_ROOT / "release" / "linux" / "Media-Downloader-x86_64.AppImage"
REQUIRED_ANIKA_ASSETS = ("idle.png", "dragged.png", "action.png", "sleeping.png")


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def check_appimage_exists() -> None:
    if not APPIMAGE_PATH.is_file():
        raise SystemExit(f"AppImage not found: {APPIMAGE_PATH}")
    if not os.access(APPIMAGE_PATH, os.X_OK):
        APPIMAGE_PATH.chmod(APPIMAGE_PATH.stat().st_mode | 0o111)
    print(f"OK appimage: {APPIMAGE_PATH} ({APPIMAGE_PATH.stat().st_size // (1024 * 1024)} MB)")


def extract_appimage() -> Path:
    extract_dir = Path(tempfile.mkdtemp(prefix="md-appimage-test-"))
    env = os.environ.copy()
    env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    result = _run([str(APPIMAGE_PATH), "--appimage-extract"], cwd=extract_dir.parent, env=env, timeout=180)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise SystemExit(f"AppImage extract failed ({result.returncode}): {detail[:800]}")

    squashed = extract_dir.parent / "squashfs-root"
    if not squashed.is_dir():
        raise SystemExit("AppImage extract did not produce squashfs-root")
    print(f"OK appimage: extracted to {squashed}")
    return squashed


def check_bundle_layout(root: Path) -> Path:
    hub = root / "usr" / "bin" / "Media-Downloader"
    if not hub.is_file():
        raise SystemExit(f"Hub binary missing: {hub}")
    if not os.access(hub, os.X_OK):
        hub.chmod(hub.stat().st_mode | 0o111)
    desktop = root / "com.needyamin.MediaDownloader.desktop"
    if not desktop.is_file():
        raise SystemExit(f"Desktop entry missing: {desktop}")
    icon = root / "Media-Downloader.png"
    if not icon.is_file():
        raise SystemExit(f"AppImage icon missing: {icon}")
    print("OK appimage: bundle layout (hub, desktop, icon)")
    return hub


def check_anika_assets(root: Path) -> None:
    search_roots = [
        root / "usr" / "bin" / "desktop_tools" / "anika" / "resources",
        root / "usr" / "bin" / "_internal" / "desktop_tools" / "anika" / "resources",
    ]
    resources_dir = next((path for path in search_roots if path.is_dir()), None)
    if resources_dir is None:
        raise SystemExit("Anika resources directory not found in AppImage bundle")
    missing = [name for name in REQUIRED_ANIKA_ASSETS if not (resources_dir / name).is_file()]
    if missing:
        raise SystemExit(f"Anika assets missing in bundle: {', '.join(missing)}")
    print(f"OK appimage: Anika assets in {resources_dir}")


def check_bundled_modules(root: Path) -> None:
    internal = root / "usr" / "bin" / "_internal"
    if not internal.is_dir():
        internal = root / "usr" / "bin"
    required = [
        internal / "rembg",
        internal / "customtkinter",
        internal / "onnxruntime",
        internal / "desktop_tools" / "anika",
    ]
    missing = [str(path.relative_to(root)) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"Bundled modules missing: {', '.join(missing)}")
    yt_dlp = internal / "yt_dlp"
    if not yt_dlp.exists():
        print("WARN appimage: yt_dlp folder not loose (may still be inside PYZ archive)")
    else:
        print("OK appimage: yt_dlp bundled")
    print("OK appimage: rembg, customtkinter, onnxruntime, Anika data tree")


def check_hub_launches(hub: Path) -> None:
    env = os.environ.copy()
    if not env.get("DISPLAY"):
        print("SKIP appimage: hub launch (no DISPLAY — run on a Linux desktop or install xvfb)")
        return
    proc = subprocess.Popen([str(hub)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=10)
        if proc.returncode not in (0, None):
            raise SystemExit(f"Hub exited immediately with code {proc.returncode}")
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("OK appimage: hub launches with DISPLAY")


def check_anika_linux_message() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    code = (
        "import tkinter as tk; "
        "from desktop_tools.app.ui.anika_app import open_anika; "
        "root = tk.Tk(); root.withdraw(); "
        "status = open_anika(root); "
        "root.update(); "
        "assert status == 'failed', status; "
        "print('anika linux gate ok')"
    )
    xvfb = shutil.which("xvfb-run")
    cmd = [xvfb, "-a", sys.executable, "-c", code] if xvfb else [sys.executable, "-c", code]
    result = _run(cmd, env=env, timeout=60)
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0 or "anika linux gate ok" not in output:
        raise SystemExit(f"Anika Linux gate check failed ({result.returncode}):\n{output[:800]}")
    print("OK appimage: Anika shows Linux availability message (desktop assistant is Windows-only)")


def check_anika_settings_window() -> None:
    from desktop_tools.tools.script_checks import check_anika_settings_window

    check_anika_settings_window()


def main() -> None:
    if not sys.platform.startswith("linux"):
        raise SystemExit("AppImage checks must run on Linux/WSL.")

    check_appimage_exists()
    root = extract_appimage()
    try:
        hub = check_bundle_layout(root)
        check_anika_assets(root)
        check_bundled_modules(root)
        check_hub_launches(hub)
        check_anika_linux_message()
        check_anika_settings_window()
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("All AppImage checks passed.")


if __name__ == "__main__":
    main()
