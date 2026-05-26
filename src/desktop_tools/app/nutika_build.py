from __future__ import annotations

import importlib.util
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_DIR = Path(__file__).resolve().parent
APP_NAME = "Media Downloader"
MAIN_SCRIPT = APP_DIR / "media_download.py"
ICON_PATH = APP_DIR / "assets" / "needyamin.ico"
ASSETS_DIR = APP_DIR / "assets"
REQUIREMENTS_FILE = APP_DIR / "requirements.txt"
APP_FLAGS_PATH = REPO_ROOT / "app_flags.json"
INNO_SCRIPT = APP_DIR / "installer" / "setup.iss"
AUTHOR = "Yamin Hossain"
DESCRIPTION = "Media Downloader with integrated desktop tools"
RELEASE_DIR = REPO_ROOT / "release"
WINDOWS_RELEASE_DIR = RELEASE_DIR / "windows"
BUILD_DIR = APP_DIR / "build" / "nuitka"
OUTPUT_EXE_NAME = "Media-Downloader.exe"
OUTPUT_INSTALLER_NAME = "MediaDownloader_Setup.exe"
CPU_JOBS = max(1, os.cpu_count() or 1)
EXCLUDED_IMPORTS = [
    "IPython",
    "matplotlib",
    "pandas",
    "pytest",
    "jupyter",
    "setuptools",
    "win32com.test",
]


def read_current_version() -> str:
    """Read the app version directly from the main application file."""
    try:
        contents = MAIN_SCRIPT.read_text(encoding="utf-8")
        match = re.search(r"CURRENT_VERSION\s*=\s*['\"]([^'\"]+)['\"]", contents)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "1.0.0"


VERSION = read_current_version()


def ensure_python_package(module_name: str, package_name: str | None = None) -> None:
    """Install a Python package if its module is not currently available."""
    if importlib.util.find_spec(module_name) is not None:
        return

    package_name = package_name or module_name
    print(f"Missing build dependency '{package_name}'. Installing it now...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name],
            check=True,
            cwd=str(REPO_ROOT),
        )
    except subprocess.CalledProcessError as exc:
        print(f"Failed to install required package: {package_name}")
        raise SystemExit(1) from exc

    if importlib.util.find_spec(module_name) is None:
        print(f"Package installed but module still not available: {module_name}")
        raise SystemExit(1)


def ensure_build_dependencies() -> None:
    """Make sure local Python build tools are installed before running Nuitka."""
    ensure_python_package("nuitka", "nuitka")
    ensure_python_package("ordered_set", "ordered-set")
    ensure_python_package("zstandard", "zstandard")
    ensure_python_package("yt_dlp", "yt-dlp")
    ensure_python_package("PIL", "pillow")
    ensure_python_package("pyperclip", "pyperclip")
    ensure_python_package("pystray", "pystray")
    ensure_python_package("win32com", "pywin32")
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
                [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
                check=True,
                cwd=str(REPO_ROOT),
            )
        except subprocess.CalledProcessError as exc:
            print("Failed to install application requirements for the Windows build.")
            raise SystemExit(1) from exc


def ensure_windows_environment() -> None:
    """Stop early when the Windows build script is run on another platform."""
    if os.name != "nt":
        print("The Nuitka Windows build script must be run on Windows.")
        raise SystemExit(1)


def select_compiler_arguments() -> list[str]:
    """Choose the fastest safe compiler flags available for this Python runtime."""
    python_version = sys.version_info[:2]
    cl_path = shutil.which("cl")
    clang_path = shutil.which("clang")

    if python_version < (3, 13):
        print("Compiler backend: MinGW64")
        return ["--mingw64"]

    if cl_path:
        print("Compiler backend: MSVC")
        return ["--msvc=latest"]

    if clang_path:
        print("Compiler backend: Clang")
        return ["--clang"]

    print("Compiler backend: default Nuitka backend for this Python version")
    return []


def clean_directories() -> None:
    print("Cleaning build directories...")
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
        print(f"Removed {BUILD_DIR}")

    WINDOWS_RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    for generated_path in WINDOWS_RELEASE_DIR.iterdir():
        if generated_path.is_dir():
            shutil.rmtree(generated_path)
        else:
            generated_path.unlink()
        print(f"Removed {generated_path}")


def build_executable() -> None:
    print("Building executable with Nuitka...")
    print(f"Using up to {CPU_JOBS} parallel compiler jobs.")
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    compiler_args = select_compiler_arguments()

    nuitka_args = [
        sys.executable,
        "-m",
        "nuitka",
        "--assume-yes-for-downloads",
        f"--windows-company-name={AUTHOR}",
        f"--windows-product-name={APP_NAME}",
        f"--windows-file-version={VERSION}",
        f"--windows-product-version={VERSION}",
        f"--windows-file-description={DESCRIPTION}",
        f"--windows-icon-from-ico={ICON_PATH.resolve()}",
        "--windows-console-mode=disable",
        "--follow-imports",
        "--plugin-enable=tk-inter",
        "--include-package=yt_dlp",
        "--include-package=pystray",
        "--include-package=PIL",
        "--include-package=pyperclip",
        "--include-package=validators",
        "--include-package=requests",
        "--include-package=win32com",
        "--include-package=certifi",
        "--include-package=desktop_tools",
        "--include-package=customtkinter",
        "--include-package=numpy",
        "--include-package=numba",
        "--include-package=llvmlite",
        "--include-package=rembg",
        "--include-package=onnxruntime",
        "--include-package=scipy",
        "--include-package=skimage",
        "--include-package=pymatting",
        "--include-package=pooch",
        "--include-package=tqdm",
        "--include-package=jsonschema",
        "--include-module=desktop_tools.app.converter_app",
        "--include-module=desktop_tools.app.background_remover_app",
        "--include-module=desktop_tools.app.screenshot_app",
        "--include-module=desktop_tools.app.yscreenrecorder_app",
        "--include-module=tkinter",
        "--include-module=tkinter.ttk",
        "--include-module=tkinter.messagebox",
        "--include-module=tkinter.filedialog",
        "--include-module=webbrowser",
        "--include-module=onnxruntime.capi._ld_preload",
        "--include-module=onnxruntime.capi._pybind_state",
        "--include-module=onnxruntime.capi.onnxruntime_pybind11_state",
        f"--include-data-dir={ASSETS_DIR}=assets",
        f"--include-data-files={APP_FLAGS_PATH}=app_flags.json",
        f"--include-data-files={ICON_PATH}=needyamin.ico",
        f"--output-dir={WINDOWS_RELEASE_DIR}",
        f"--output-filename={OUTPUT_EXE_NAME}",
        "--standalone",
        "--onefile",
        f"--jobs={CPU_JOBS}",
        "--lto=no",
        str(MAIN_SCRIPT),
    ]

    nuitka_args[4:4] = compiler_args

    for excluded_import in EXCLUDED_IMPORTS:
        nuitka_args.append(f"--nofollow-import-to={excluded_import}")

    try:
        print("Running Nuitka compilation...")
        result = subprocess.run(
            nuitka_args,
            check=True,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
        )
        print(result.stdout)
        if result.stderr:
            print("Warnings/Errors:")
            print(result.stderr)
        print("Build completed successfully!")
    except subprocess.CalledProcessError as exc:
        print(f"Build failed with error code {exc.returncode}")
        print("Error output:")
        print(exc.stdout)
        print(exc.stderr)
        raise SystemExit(1) from exc


def find_inno_setup_compiler() -> str | None:
    """Locate ISCC.exe on common Windows install paths."""
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    iscc_on_path = shutil.which("ISCC.exe") or shutil.which("iscc")
    return iscc_on_path


def build_inno_installer() -> None:
    """Build the Windows installer using Inno Setup."""
    compiler = find_inno_setup_compiler()
    if not compiler:
        print("Inno Setup compiler not found. Install Inno Setup 6 or add ISCC.exe to PATH.")
        raise SystemExit(1)

    if not (WINDOWS_RELEASE_DIR / OUTPUT_EXE_NAME).exists():
        print(f"Expected executable not found: {WINDOWS_RELEASE_DIR / OUTPUT_EXE_NAME}")
        raise SystemExit(1)

    print("Building installer with Inno Setup...")
    try:
        result = subprocess.run(
            [compiler, str(INNO_SCRIPT)],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        print(result.stdout)
        if result.stderr:
            print("Warnings/Errors:")
            print(result.stderr)
        print(f"Installer created: {WINDOWS_RELEASE_DIR / OUTPUT_INSTALLER_NAME}")
    except subprocess.CalledProcessError as exc:
        print(f"Inno Setup failed with error code {exc.returncode}")
        print(exc.stdout)
        print(exc.stderr)
        raise SystemExit(1) from exc


def main() -> None:
    print("Starting build process...")
    ensure_windows_environment()
    ensure_build_dependencies()
    clean_directories()
    build_executable()
    build_inno_installer()
    print("Build process finished.")


if __name__ == "__main__":
    main()
