from __future__ import annotations

import importlib.util
import importlib.metadata
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import time

from build_manifest import (
    APP_DIR,
    EXCLUDED_IMPORTS,
    ICON_PATH,
    INNO_SCRIPT,
    MAIN_SCRIPT,
    REPO_ROOT,
    REQUIREMENTS_FILE,
    REQUIRED_PACKAGES,
    REQUIRED_PACKAGE_DATA,
    nuitka_data_file_arguments,
    print_bundle_summary,
    required_include_modules,
    validate_source_tree,
)


APP_NAME = "Media Downloader"
AUTHOR = "Yamin Hossain"
DESCRIPTION = "Media Downloader with integrated desktop tools"
RELEASE_DIR = REPO_ROOT / "release"
WINDOWS_RELEASE_DIR = RELEASE_DIR / "windows"
BUILD_DIR = APP_DIR / "build" / "nuitka"
BUILD_RUN_ID = f"{int(time.time())}-{os.getpid()}"
WINDOWS_BUILD_OUTPUT_DIR = BUILD_DIR / "runs" / BUILD_RUN_ID / "windows-output"
OUTPUT_EXE_NAME = "Media-Downloader.exe"
OUTPUT_INSTALLER_NAME = "MediaDownloader_Setup.exe"
CPU_JOBS = max(1, os.cpu_count() or 1)
BUILD_TEMP_DIR = BUILD_DIR / "tmp" / BUILD_RUN_ID
STANDALONE_DIST_DIR = WINDOWS_BUILD_OUTPUT_DIR / f"{MAIN_SCRIPT.stem}.dist"


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
    if sys.version_info >= (3, 14):
        try:
            nuitka_version = importlib.metadata.version("nuitka")
        except importlib.metadata.PackageNotFoundError:
            nuitka_version = "0"
        if nuitka_version.startswith("4.1."):
            print(f"Detected Nuitka {nuitka_version} on Python {sys.version_info.major}.{sys.version_info.minor}; upgrading Nuitka for better compatibility...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", "nuitka"],
                    check=True,
                    cwd=str(REPO_ROOT),
                )
            except subprocess.CalledProcessError as exc:
                print("Failed to upgrade Nuitka automatically.")
                raise SystemExit(1) from exc

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
    ensure_python_package("jsonschema_specifications", "jsonschema-specifications")

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


def relaunch_with_python_313_if_available() -> None:
    """Run this script with Python 3.13 on Windows when currently on Python 3.14+."""
    if os.name != "nt":
        return
    if sys.version_info < (3, 14):
        return
    if os.environ.get("MD_SKIP_313_RELAUNCH") == "1":
        return

    launcher = shutil.which("py")
    if not launcher:
        return

    try:
        probe = subprocess.run(
            [launcher, "-3.13", "-c", "import sys; print(sys.executable)"],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
    except subprocess.CalledProcessError:
        return

    py313_executable = probe.stdout.strip()
    if not py313_executable:
        return

    print(f"Detected Python {sys.version_info.major}.{sys.version_info.minor}; relaunching build with Python 3.13: {py313_executable}")
    env = os.environ.copy()
    env["MD_SKIP_313_RELAUNCH"] = "1"
    result = subprocess.run([py313_executable, __file__, *sys.argv[1:]], cwd=str(REPO_ROOT), env=env)
    raise SystemExit(result.returncode)


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
    def _remove_path(path: Path) -> None:
        attempts = 5
        for attempt in range(1, attempts + 1):
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()
                return
            except PermissionError as exc:
                if attempt == attempts:
                    print(f"Failed to remove locked path after {attempts} attempts: {path}")
                    print("Close running app/build processes that may hold files in release/windows, then retry.")
                    raise SystemExit(1) from exc
                time.sleep(1.0)

    print("Cleaning build directories...")
    WINDOWS_RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    installer_path = WINDOWS_RELEASE_DIR / OUTPUT_INSTALLER_NAME
    if installer_path.exists():
        _remove_path(installer_path)
        print(f"Removed {installer_path}")

    # Use per-run output/temp folders to avoid collisions with stale/locked prior runs.
    WINDOWS_BUILD_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_TEMP_DIR.mkdir(parents=True, exist_ok=True)


def build_nuitka_args() -> list[str]:
    """Assemble the Nuitka command line with explicit modules, data, and package data."""
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
        "--plugin-enable=tk-inter",
        f"--output-dir={WINDOWS_BUILD_OUTPUT_DIR}",
        f"--output-filename={OUTPUT_EXE_NAME}",
        "--standalone",
        "--module-parameter=numba-disable-jit=yes",
        f"--jobs={CPU_JOBS}",
        "--lto=no",
        str(MAIN_SCRIPT),
    ]

    nuitka_args[4:4] = compiler_args
    nuitka_args.extend(nuitka_data_file_arguments())

    for package_name in REQUIRED_PACKAGES:
        nuitka_args.append(f"--include-package={package_name}")
    for module_name in required_include_modules():
        nuitka_args.append(f"--include-module={module_name}")
    for package_name in REQUIRED_PACKAGE_DATA:
        nuitka_args.append(f"--include-package-data={package_name}")
    for excluded_import in EXCLUDED_IMPORTS:
        nuitka_args.append(f"--nofollow-import-to={excluded_import}")

    return nuitka_args


def build_pyinstaller_fallback() -> None:
    """Fallback Windows build path when Nuitka fails on this runtime."""
    print("Falling back to PyInstaller Windows onedir build...")
    pyinstaller_work_dir = WINDOWS_BUILD_OUTPUT_DIR / "pyinstaller-work"
    pyinstaller_args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        f"--name={OUTPUT_EXE_NAME.removesuffix('.exe')}",
        f"--distpath={WINDOWS_BUILD_OUTPUT_DIR}",
        f"--workpath={pyinstaller_work_dir}",
        f"--specpath={pyinstaller_work_dir}",
        f"--paths={REPO_ROOT / 'src'}",
        f"--add-data={APP_DIR / 'assets'}{os.pathsep}assets",
        f"--add-data={REPO_ROOT / 'app_flags.json'}{os.pathsep}.",
        f"--add-data={ICON_PATH}{os.pathsep}.",
        str(MAIN_SCRIPT),
    ]

    for module_name in required_include_modules():
        pyinstaller_args.append(f"--hidden-import={module_name}")

    # Collect dynamic package content needed by rembg/image stack and downloader plugins.
    collect_all_packages = [
        "desktop_tools",
        "yt_dlp",
        "customtkinter",
        "PIL",
        "pystray",
        "rembg",
        "onnxruntime",
        "scipy",
        "skimage",
        "pymatting",
        "pooch",
        "tqdm",
        "jsonschema",
        "jsonschema_specifications",
        "certifi",
        "validators",
        "requests",
        "win32com",
    ]
    for package_name in collect_all_packages:
        pyinstaller_args.append(f"--collect-all={package_name}")

    try:
        subprocess.run(pyinstaller_args, check=True, cwd=str(REPO_ROOT))
    except subprocess.CalledProcessError as exc:
        print("PyInstaller fallback failed.")
        raise SystemExit(1) from exc

    expected = STANDALONE_DIST_DIR / OUTPUT_EXE_NAME
    if not expected.exists():
        print(f"PyInstaller fallback completed but expected executable is missing: {expected}")
        raise SystemExit(1)
    print(f"PyInstaller fallback produced executable: {expected}")


def build_executable() -> None:
    print("Building executable with Nuitka...")
    print(f"Using up to {CPU_JOBS} parallel compiler jobs.")
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    # Keep onefile payload writes in a short, local temp path to reduce AV/FS locking issues.
    BUILD_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    env["TMP"] = str(BUILD_TEMP_DIR)
    env["TEMP"] = str(BUILD_TEMP_DIR)
    nuitka_args = build_nuitka_args()
    if "--onefile" in nuitka_args:
        print("Refusing to build with --onefile from this script due known Nuitka payload failures on this environment.")
        raise SystemExit(1)
    print("Packaging mode: standalone")
    print("Nuitka command:")
    print(" ".join(nuitka_args))

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
        build_pyinstaller_fallback()


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

    expected_binary_path = STANDALONE_DIST_DIR / OUTPUT_EXE_NAME
    if not expected_binary_path.exists():
        print(f"Expected executable not found: {expected_binary_path}")
        raise SystemExit(1)

    print("Building installer with Inno Setup...")
    source_dir = STANDALONE_DIST_DIR
    try:
        result = subprocess.run(
            [
                compiler,
                f"/DMyAppSourceDir={source_dir}",
                f"/DMyAppExeName={OUTPUT_EXE_NAME}",
                str(INNO_SCRIPT),
            ],
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
    relaunch_with_python_313_if_available()
    validate_source_tree()
    print_bundle_summary()
    ensure_build_dependencies()
    clean_directories()
    build_executable()
    build_inno_installer()
    print("Build process finished.")


if __name__ == "__main__":
    main()
