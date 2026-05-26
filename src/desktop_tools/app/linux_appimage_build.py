from __future__ import annotations

import importlib.util
from pathlib import Path
import os
import shutil
import stat
import subprocess
import sys
import urllib.request


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_DIR = Path(__file__).resolve().parent
MAIN_SCRIPT = APP_DIR / "media_download.py"
ICON_PATH = APP_DIR / "assets" / "needyamin.ico"
ASSETS_DIR = APP_DIR / "assets"
REQUIREMENTS_FILE = APP_DIR / "requirements.txt"
APP_FLAGS_PATH = REPO_ROOT / "app_flags.json"
RELEASE_DIR = REPO_ROOT / "release"
LINUX_RELEASE_DIR = RELEASE_DIR / "linux"
PYINSTALLER_DIST_DIR = LINUX_RELEASE_DIR / "pyinstaller-dist"
PYINSTALLER_WORK_DIR = LINUX_RELEASE_DIR / "pyinstaller-work"
APPDIR_PATH = LINUX_RELEASE_DIR / "Media-Downloader.AppDir"
EXECUTABLE_NAME = "Media-Downloader"
APPIMAGE_NAME = "Media-Downloader-x86_64.AppImage"
APPIMAGETOOL_NAME = "appimagetool-x86_64.AppImage"
APPIMAGETOOL_URL = "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"


def ensure_python_package(module_name: str, package_name: str | None = None) -> None:
    """Install a required Python package if it is missing."""
    if importlib.util.find_spec(module_name) is not None:
        return

    package_name = package_name or module_name
    print(f"Missing build dependency '{package_name}'. Installing it now...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", package_name], check=True, cwd=str(REPO_ROOT))
    except subprocess.CalledProcessError as exc:
        print(f"Failed to install required package: {package_name}")
        raise SystemExit(1) from exc


def ensure_linux_environment() -> None:
    """Stop early when the script is not running on Linux."""
    if not sys.platform.startswith("linux"):
        print("Linux AppImage builds must be run on Linux.")
        raise SystemExit(1)


def ensure_build_dependencies() -> None:
    """Install Python-level build requirements for AppImage packaging."""
    ensure_python_package("PyInstaller", "pyinstaller")
    ensure_python_package("PIL", "pillow")
    ensure_python_package("yt_dlp", "yt-dlp")
    ensure_python_package("pyperclip", "pyperclip")
    ensure_python_package("pystray", "pystray")
    ensure_python_package("validators", "validators")
    ensure_python_package("requests", "requests")
    ensure_python_package("certifi", "certifi")
    ensure_python_package("customtkinter", "customtkinter")
    ensure_python_package("numpy", "numpy")
    ensure_python_package("rembg", "rembg")
    ensure_python_package("onnxruntime", "onnxruntime")
    ensure_python_package("scipy", "scipy")
    ensure_python_package("skimage", "scikit-image")
    ensure_python_package("pymatting", "pymatting")
    ensure_python_package("pooch", "pooch")
    ensure_python_package("tqdm", "tqdm")
    ensure_python_package("jsonschema", "jsonschema")

    if REQUIREMENTS_FILE.exists():
        print(f"Ensuring application requirements from {REQUIREMENTS_FILE}...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
                check=True,
                cwd=str(REPO_ROOT),
            )
        except subprocess.CalledProcessError as exc:
            print("Failed to install application requirements for the Linux build.")
            raise SystemExit(1) from exc


def clean_directories() -> None:
    """Remove previous Linux release artifacts while keeping cached tools."""
    print("Cleaning Linux release directories...")
    LINUX_RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    for generated_path in LINUX_RELEASE_DIR.iterdir():
        if generated_path.name == APPIMAGETOOL_NAME:
            continue
        if generated_path.is_dir():
            shutil.rmtree(generated_path)
        else:
            generated_path.unlink()
        print(f"Removed {generated_path}")


def generate_linux_icon() -> Path:
    """Convert the shared ICO icon to a PNG for Linux desktop metadata."""
    try:
        from PIL import Image
    except Exception as exc:
        print(f"Pillow is required to create the Linux icon: {exc}")
        raise SystemExit(1) from exc

    icon_png = LINUX_RELEASE_DIR / "Media-Downloader.png"
    with Image.open(ICON_PATH) as icon_image:
        icon_image.save(icon_png, format="PNG")
    return icon_png


def build_pyinstaller_bundle() -> Path:
    """Create a Linux onedir bundle that will be wrapped into an AppImage."""
    print("Building Linux onedir bundle with PyInstaller...")
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + (os.pathsep + existing_pythonpath if existing_pythonpath else "")

    pyinstaller_args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        f"--name={EXECUTABLE_NAME}",
        f"--distpath={PYINSTALLER_DIST_DIR}",
        f"--workpath={PYINSTALLER_WORK_DIR}",
        f"--specpath={PYINSTALLER_WORK_DIR}",
        f"--paths={REPO_ROOT / 'src'}",
        f"--add-data={ASSETS_DIR}{os.pathsep}assets",
        f"--add-data={APP_FLAGS_PATH}{os.pathsep}.",
        f"--add-data={ICON_PATH}{os.pathsep}.",
        "--collect-submodules=yt_dlp",
        "--collect-all=customtkinter",
        "--collect-all=rembg",
        "--collect-all=onnxruntime",
        "--collect-all=scipy",
        "--collect-all=skimage",
        "--collect-all=pymatting",
        "--collect-all=pooch",
        "--collect-all=tqdm",
        "--collect-all=jsonschema",
        "--hidden-import=desktop_tools.app.converter_app",
        "--hidden-import=desktop_tools.app.background_remover_app",
        "--hidden-import=rembg",
        "--hidden-import=onnxruntime",
        "--hidden-import=onnxruntime.capi.onnxruntime_pybind11_state",
        "--exclude-module=win32com",
        "--exclude-module=win32com.client",
        "--exclude-module=pywintypes",
        "--exclude-module=pythoncom",
        "--exclude-module=winreg",
        str(MAIN_SCRIPT),
    ]

    try:
        subprocess.run(pyinstaller_args, check=True, cwd=str(REPO_ROOT), env=env)
    except subprocess.CalledProcessError as exc:
        print("PyInstaller Linux bundle build failed.")
        raise SystemExit(1) from exc

    bundle_dir = PYINSTALLER_DIST_DIR / EXECUTABLE_NAME
    if not bundle_dir.exists():
        print(f"Expected Linux bundle not found: {bundle_dir}")
        raise SystemExit(1)

    return bundle_dir


def create_appdir(bundle_dir: Path, icon_png: Path) -> Path:
    """Wrap the onedir bundle into an AppDir structure."""
    print("Creating AppDir structure...")
    usr_bin_dir = APPDIR_PATH / "usr" / "bin"
    icon_dir = APPDIR_PATH / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    applications_dir = APPDIR_PATH / "usr" / "share" / "applications"

    usr_bin_dir.mkdir(parents=True, exist_ok=True)
    icon_dir.mkdir(parents=True, exist_ok=True)
    applications_dir.mkdir(parents=True, exist_ok=True)

    for item in bundle_dir.iterdir():
        destination = usr_bin_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)

    shutil.copy2(icon_png, APPDIR_PATH / "Media-Downloader.png")
    shutil.copy2(icon_png, icon_dir / "Media-Downloader.png")

    desktop_file = APPDIR_PATH / "Media-Downloader.desktop"
    desktop_file.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=Media Downloader",
                "Exec=Media-Downloader",
                "Icon=Media-Downloader",
                "Categories=AudioVideo;Network;",
                "Terminal=false",
                "StartupNotify=true",
                "StartupWMClass=Media Downloader",
                "",
            ]
        ),
        encoding="utf-8",
    )
    shutil.copy2(desktop_file, applications_dir / "Media-Downloader.desktop")

    app_run = APPDIR_PATH / "AppRun"
    app_run.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                'HERE="$(dirname "$(readlink -f "$0")")"',
                'export APPDIR="$HERE"',
                'export PATH="$HERE/usr/bin:$PATH"',
                'exec "$HERE/usr/bin/Media-Downloader" "$@"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    app_run.chmod(app_run.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return APPDIR_PATH


def ensure_appimagetool() -> Path:
    """Download appimagetool if it is not already present."""
    appimagetool_path = LINUX_RELEASE_DIR / APPIMAGETOOL_NAME
    if appimagetool_path.exists():
        return appimagetool_path

    print("Downloading appimagetool...")
    urllib.request.urlretrieve(APPIMAGETOOL_URL, appimagetool_path)
    appimagetool_path.chmod(appimagetool_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return appimagetool_path


def build_appimage(appdir: Path, appimagetool_path: Path) -> Path:
    """Create the final AppImage in release/linux."""
    output_path = LINUX_RELEASE_DIR / APPIMAGE_NAME
    print("Building AppImage...")
    env = os.environ.copy()
    env["ARCH"] = "x86_64"
    env["APPIMAGE_EXTRACT_AND_RUN"] = "1"

    try:
        subprocess.run(
            [str(appimagetool_path), str(appdir), str(output_path)],
            check=True,
            cwd=str(LINUX_RELEASE_DIR),
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        print("AppImage creation failed.")
        raise SystemExit(1) from exc

    return output_path


def main() -> None:
    print("Starting Linux AppImage build...")
    ensure_linux_environment()
    ensure_build_dependencies()
    clean_directories()
    icon_png = generate_linux_icon()
    bundle_dir = build_pyinstaller_bundle()
    appdir = create_appdir(bundle_dir, icon_png)
    appimagetool_path = ensure_appimagetool()
    output_path = build_appimage(appdir, appimagetool_path)
    print(f"Linux AppImage created: {output_path}")


if __name__ == "__main__":
    main()
