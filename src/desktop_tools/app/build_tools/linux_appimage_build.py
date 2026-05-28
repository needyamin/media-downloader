from __future__ import annotations

import importlib.util
from pathlib import Path
import os
import shutil
import stat
import subprocess
import sys
import urllib.request

try:
    from .build_manifest import (
        APP_DIR,
        ICON_PATH,
        LINUX_COLLECT_ALL_PACKAGES,
        LINUX_COLLECT_SUBMODULE_PACKAGES,
        LINUX_EXCLUDED_MODULES,
        MAIN_SCRIPT,
        REPO_ROOT,
        REQUIREMENTS_FILE,
        linux_pyinstaller_data_arguments,
        print_bundle_summary,
        required_include_modules,
        validate_source_tree,
    )
except ImportError:
    from build_manifest import (
        APP_DIR,
        ICON_PATH,
        LINUX_COLLECT_ALL_PACKAGES,
        LINUX_COLLECT_SUBMODULE_PACKAGES,
        LINUX_EXCLUDED_MODULES,
        MAIN_SCRIPT,
        REPO_ROOT,
        REQUIREMENTS_FILE,
        linux_pyinstaller_data_arguments,
        print_bundle_summary,
        required_include_modules,
        validate_source_tree,
    )


RELEASE_DIR = REPO_ROOT / "release"
LINUX_RELEASE_DIR = RELEASE_DIR / "linux"
PYINSTALLER_DIST_DIR = LINUX_RELEASE_DIR / "pyinstaller-dist"
PYINSTALLER_WORK_DIR = LINUX_RELEASE_DIR / "pyinstaller-work"
APPDIR_PATH = LINUX_RELEASE_DIR / "Media-Downloader.AppDir"
EXECUTABLE_NAME = "Media-Downloader"
APPIMAGE_NAME = "Media-Downloader-x86_64.AppImage"
APPIMAGETOOL_NAME = "appimagetool-x86_64.AppImage"
APPIMAGETOOL_URL = "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
BUILD_VENV_DIR = LINUX_RELEASE_DIR / "build" / "linux-appimage-venv"
APP_DESKTOP_ID = "com.needyamin.MediaDownloader"


def print_linux_runtime_guidance() -> None:
    """Print Linux runtime notes for capture features bundled in the AppImage."""
    print("Linux runtime notes for capture tools:")
    print("  - YScreenRecorder currently records on Linux/X11 using system ffmpeg with x11grab support.")
    print("  - Wayland recording is not available in-app yet and will show a guidance message instead.")
    print("  - YScreenshot may use grim, gnome-screenshot, scrot, or ImageMagick 'import' as screenshot fallbacks.")
    print("  - Clipboard image copy on Linux prefers wl-clipboard on Wayland or xclip on X11.")
    print("Recommended distro packages: ffmpeg xclip wl-clipboard grim gnome-screenshot scrot imagemagick python3-tk")


def get_build_python_executable() -> str:
    """Return the Python executable used for Linux build tooling."""
    venv_python = BUILD_VENV_DIR / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def build_module_available(module_name: str) -> bool:
    """Check whether a Python module is available in the build environment."""
    try:
        result = subprocess.run(
            [
                get_build_python_executable(),
                "-c",
                "import importlib.util, sys; raise SystemExit(0 if importlib.util.find_spec(sys.argv[1]) is not None else 1)",
                module_name,
            ],
            check=False,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
    except Exception:
        return False
    return result.returncode == 0


def ensure_build_virtualenv() -> None:
    """Create a dedicated Linux build virtualenv to avoid system-package restrictions."""
    if (BUILD_VENV_DIR / "bin" / "python").exists():
        return

    if importlib.util.find_spec("venv") is None:
        print("Python virtualenv support is missing in this Linux environment.")
        print("On Ubuntu/WSL, install it with:")
        print("  sudo apt update && sudo apt install -y python3-venv python3-dev")
        raise SystemExit(1)

    BUILD_VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
    print(f"Creating Linux build virtualenv at {BUILD_VENV_DIR}...")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(BUILD_VENV_DIR)],
            check=True,
            cwd=str(REPO_ROOT),
        )
    except subprocess.CalledProcessError as exc:
        print("Failed to create the Linux build virtualenv.")
        print("On Ubuntu/WSL, make sure python3-venv is installed:")
        print("  sudo apt update && sudo apt install -y python3-venv python3-dev")
        raise SystemExit(1) from exc


def ensure_python_package(module_name: str, package_name: str | None = None) -> None:
    """Install a required Python package if it is missing."""
    if build_module_available(module_name):
        return

    package_name = package_name or module_name
    print(f"Missing build dependency '{package_name}'. Installing it now...")
    try:
        subprocess.run(
            [get_build_python_executable(), "-m", "pip", "install", package_name],
            check=True,
            cwd=str(REPO_ROOT),
        )
    except subprocess.CalledProcessError as exc:
        print(f"Failed to install required package: {package_name}")
        raise SystemExit(1) from exc

    if not build_module_available(module_name):
        print(f"Package installed but module still not available: {module_name}")
        raise SystemExit(1)


def ensure_linux_environment() -> None:
    """Stop early when the script is not running on Linux."""
    if not sys.platform.startswith("linux"):
        print("Linux AppImage builds must be run on Linux.")
        raise SystemExit(1)


def ensure_build_dependencies() -> None:
    """Install Python-level build requirements for AppImage packaging."""
    ensure_build_virtualenv()
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
    ensure_python_package("numba", "numba")
    ensure_python_package("llvmlite", "llvmlite")
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
                [get_build_python_executable(), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
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
    icon_png = LINUX_RELEASE_DIR / "Media-Downloader.png"
    try:
        subprocess.run(
            [
                get_build_python_executable(),
                "-c",
                "from PIL import Image; import sys; Image.open(sys.argv[1]).save(sys.argv[2], format='PNG')",
                str(ICON_PATH),
                str(icon_png),
            ],
            check=True,
            cwd=str(REPO_ROOT),
        )
    except subprocess.CalledProcessError as exc:
        print("Pillow is required to create the Linux icon.")
        raise SystemExit(1) from exc
    return icon_png


def build_pyinstaller_args() -> list[str]:
    """Assemble the PyInstaller command line with explicit modules, package data, and exclusions."""
    pyinstaller_args = [
        get_build_python_executable(),
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
        str(MAIN_SCRIPT),
    ]
    pyinstaller_args.extend(linux_pyinstaller_data_arguments(os.pathsep))

    for package_name in LINUX_COLLECT_SUBMODULE_PACKAGES:
        pyinstaller_args.append(f"--collect-submodules={package_name}")
    for package_name in LINUX_COLLECT_ALL_PACKAGES:
        pyinstaller_args.append(f"--collect-all={package_name}")
    for module_name in required_include_modules():
        pyinstaller_args.append(f"--hidden-import={module_name}")
    for module_name in LINUX_EXCLUDED_MODULES:
        pyinstaller_args.append(f"--exclude-module={module_name}")

    return pyinstaller_args


def build_pyinstaller_bundle() -> Path:
    """Create a Linux onedir bundle that will be wrapped into an AppImage."""
    print("Building Linux onedir bundle with PyInstaller...")
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + (os.pathsep + existing_pythonpath if existing_pythonpath else "")

    pyinstaller_args = build_pyinstaller_args()

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
    metainfo_dir = APPDIR_PATH / "usr" / "share" / "metainfo"

    usr_bin_dir.mkdir(parents=True, exist_ok=True)
    icon_dir.mkdir(parents=True, exist_ok=True)
    applications_dir.mkdir(parents=True, exist_ok=True)
    metainfo_dir.mkdir(parents=True, exist_ok=True)

    for item in bundle_dir.iterdir():
        destination = usr_bin_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)

    shutil.copy2(icon_png, APPDIR_PATH / "Media-Downloader.png")
    shutil.copy2(icon_png, icon_dir / "Media-Downloader.png")

    desktop_file = APPDIR_PATH / f"{APP_DESKTOP_ID}.desktop"
    desktop_file.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=Media Downloader",
                "Exec=Media-Downloader",
                "Icon=Media-Downloader",
                "Categories=AudioVideo;Video;Audio;",
                "Terminal=false",
                "StartupNotify=true",
                "StartupWMClass=Media Downloader",
                "",
            ]
        ),
        encoding="utf-8",
    )
    shutil.copy2(desktop_file, applications_dir / f"{APP_DESKTOP_ID}.desktop")

    appdata_file = metainfo_dir / f"{APP_DESKTOP_ID}.appdata.xml"
    appdata_file.write_text(
        "\n".join(
            [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<component type="desktop-application">',
                f"  <id>{APP_DESKTOP_ID}.desktop</id>",
                "  <name>Media Downloader</name>",
                "  <summary>Download media and use bundled desktop tools</summary>",
                "  <metadata_license>MIT</metadata_license>",
                "  <project_license>MIT</project_license>",
                "  <developer id=\"inside.ansnew.com\">",
                "    <name>Yamin Hossain</name>",
                "  </developer>",
                f"  <launchable type=\"desktop-id\">{APP_DESKTOP_ID}.desktop</launchable>",
                "  <url type=\"homepage\">https://github.com/needyamin/media-downloader</url>",
                "  <description>",
                "    <p>Media Downloader bundles video and audio downloads with built-in converter, background remover, screenshot, and screen recorder tools.</p>",
                "  </description>",
                "  <categories>",
                "    <category>AudioVideo</category>",
                "    <category>Video</category>",
                "  </categories>",
                "</component>",
                "",
            ]
        ),
        encoding="utf-8",
    )

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
    validate_source_tree()
    print_bundle_summary()
    print_linux_runtime_guidance()
    ensure_build_dependencies()
    clean_directories()
    icon_png = generate_linux_icon()
    bundle_dir = build_pyinstaller_bundle()
    appdir = create_appdir(bundle_dir, icon_png)
    appimagetool_path = ensure_appimagetool()
    output_path = build_appimage(appdir, appimagetool_path)
    print(f"Linux AppImage created: {output_path}")
    print_linux_runtime_guidance()


if __name__ == "__main__":
    main()
