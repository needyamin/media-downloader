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

try:
    from .build_manifest import (
        ANIKA_DIR,
        ANIKA_MAIN_SCRIPT,
        ANIKA_OUTPUT_EXE_WIN,
        ANIKA_APP_DIR,
        ANIKA_RESOURCES_DIR,
        ANIKA_INCLUDE_PACKAGES,
        ANIKA_INCLUDE_PACKAGE_DATA,
        ANIKA_OPTIONAL_MODULES,
        APP_DIR,
        APP_FLAGS_PATH,
        EXCLUDED_IMPORTS,
        ICON_PATH,
        INNO_SCRIPT,
        MAIN_SCRIPT,
        REPO_ROOT,
        REQUIREMENTS_FILE,
        REQUIRED_PACKAGES,
        REQUIRED_PACKAGE_DATA,
        anika_nuitka_data_arguments,
        discover_anika_module_names,
        linux_pyinstaller_data_arguments,
        nuitka_data_file_arguments,
        print_bundle_summary,
        required_include_modules,
        validate_source_tree,
    )
except ImportError:
    from build_manifest import (
        ANIKA_DIR,
        ANIKA_MAIN_SCRIPT,
        ANIKA_OUTPUT_EXE_WIN,
        ANIKA_APP_DIR,
        ANIKA_RESOURCES_DIR,
        ANIKA_INCLUDE_PACKAGES,
        ANIKA_INCLUDE_PACKAGE_DATA,
        ANIKA_OPTIONAL_MODULES,
        APP_DIR,
        APP_FLAGS_PATH,
        EXCLUDED_IMPORTS,
        ICON_PATH,
        INNO_SCRIPT,
        MAIN_SCRIPT,
        REPO_ROOT,
        REQUIREMENTS_FILE,
        REQUIRED_PACKAGES,
        REQUIRED_PACKAGE_DATA,
        anika_nuitka_data_arguments,
        discover_anika_module_names,
        linux_pyinstaller_data_arguments,
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
BUILD_DIR = WINDOWS_RELEASE_DIR / "build" / "nuitka"
# Stable paths so Nuitka reuses its .build cache between runs (major speed win on rebuilds).
WINDOWS_BUILD_OUTPUT_DIR = BUILD_DIR / "output"
NUITKA_CACHE_DIR = BUILD_DIR / "cache"
BUILD_TEMP_DIR = BUILD_DIR / "tmp"
STANDALONE_DIST_DIR = WINDOWS_BUILD_OUTPUT_DIR / f"{MAIN_SCRIPT.stem}.dist"
ANIKA_BUILD_DIR = BUILD_DIR / "anika"
OUTPUT_EXE_NAME = "Media-Downloader.exe"
OUTPUT_INSTALLER_NAME = "MediaDownloader_Setup.exe"
CPU_JOBS = max(1, os.cpu_count() or 1)

# PyInstaller --collect-all pulls test suites and demos; keep this list minimal.
PYINSTALLER_COLLECT_ALL_PACKAGES = [
    "desktop_tools",
    "yt_dlp",
    "customtkinter",
    "certifi",
    "rembg",
    "onnxruntime",
]

PYINSTALLER_EXCLUDE_MODULES = [
    "pytest",
    "IPython",
    "matplotlib",
    "pandas",
    "torch",
    "transformers",
    "gradio",
    "cv2",
    "tkinter.test",
    "scipy.tests",
    "numpy.tests",
    "numba.tests",
    "skimage.tests",
    "pooch.tests",
    "jsonschema.tests",
    "jsonschema.benchmarks",
    "win32com.test",
    "win32com.demos",
]


def read_current_version() -> str:
    """Read the release version from CI env, app_flags.json, or the main app module."""
    env_version = os.environ.get("MD_RELEASE_VERSION", "").strip().lstrip("v")
    if env_version:
        return env_version

    try:
        import json

        flags = json.loads(APP_FLAGS_PATH.read_text(encoding="utf-8"))
        version = flags.get("versions", {}).get("media_downloader")
        if version:
            return str(version)
    except Exception:
        pass

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
    if env_flag("MD_SKIP_PIP"):
        print("Skipping pip dependency checks (MD_SKIP_PIP=1).")
        return
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
    ensure_python_package("keyboard", "keyboard")

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
    """Run this script with Python 3.12/3.13 on Windows when currently on Python 3.14+."""
    if os.name != "nt":
        return
    if sys.version_info < (3, 14):
        return
    if os.environ.get("MD_SKIP_313_RELAUNCH") == "1":
        return

    launcher = shutil.which("py")
    if not launcher:
        print(
            "WARNING: Python 3.14 detected. Install Python 3.12/3.13 and use the py launcher."
        )
        return

    for version in ("3.13", "3.12"):
        try:
            probe = subprocess.run(
                [launcher, f"-{version}", "-c", "import sys; print(sys.executable)"],
                check=True,
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
        except subprocess.CalledProcessError:
            continue

        target_executable = probe.stdout.strip()
        if not target_executable:
            continue

        print(
            f"Detected Python {sys.version_info.major}.{sys.version_info.minor}; "
            f"relaunching build with Python {version}: {target_executable}"
        )
        env = os.environ.copy()
        env["MD_SKIP_313_RELAUNCH"] = "1"
        result = subprocess.run([target_executable, __file__, *sys.argv[1:]], cwd=str(REPO_ROOT), env=env)
        raise SystemExit(result.returncode)

    print(
        "WARNING: Python 3.14 is not available as py -3.13 / py -3.12. "
        "Install Python 3.13 (winget install Python.Python.3.13) before building."
    )


def nuitka_parallel_jobs(*, companion: bool = False) -> int:
    """Pick a safe Nuitka --jobs value (avoids Scons races on Python 3.14)."""
    if companion:
        return 1
    if sys.version_info >= (3, 14):
        return 1
    return min(CPU_JOBS, 8)


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


def env_flag(name: str) -> bool:
    """Return True when an MD_* env var is set to 1, true, or yes."""
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def clean_directories(*, full: bool = False) -> None:
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

    print("Preparing build directories...")
    WINDOWS_RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    WINDOWS_BUILD_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    NUITKA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_TEMP_DIR.mkdir(parents=True, exist_ok=True)

    if full:
        print("Full clean requested (MD_BUILD_CLEAN=1)...")
        for path in (STANDALONE_DIST_DIR, ANIKA_BUILD_DIR, NUITKA_CACHE_DIR):
            if path.exists():
                _remove_path(path)
                print(f"Removed {path}")
        hub_build = WINDOWS_BUILD_OUTPUT_DIR / f"{MAIN_SCRIPT.stem}.build"
        if hub_build.exists():
            _remove_path(hub_build)
            print(f"Removed {hub_build}")


def hub_dist_candidates() -> list[Path]:
    """Known standalone output folders for the hub executable."""
    pyinstaller_name = OUTPUT_EXE_NAME.removesuffix(".exe")
    return [
        STANDALONE_DIST_DIR,
        WINDOWS_BUILD_OUTPUT_DIR / pyinstaller_name,
        WINDOWS_BUILD_OUTPUT_DIR / f"{MAIN_SCRIPT.stem}.dist",
    ]


def resolve_hub_dist_dir(*, required: bool = True) -> Path | None:
    """Locate the folder that contains Media-Downloader.exe."""
    for dist_dir in hub_dist_candidates():
        if (dist_dir / OUTPUT_EXE_NAME).is_file():
            return dist_dir
    if required:
        expected = ", ".join(str(path / OUTPUT_EXE_NAME) for path in hub_dist_candidates())
        print(f"Hub executable not found. Expected one of: {expected}")
        raise SystemExit(1)
    return None


def normalize_hub_dist_dir(source_dir: Path) -> Path:
    """Move a PyInstaller onedir bundle into the canonical Nuitka-style dist folder."""
    source_dir = source_dir.resolve()
    target_dir = STANDALONE_DIST_DIR.resolve()
    hub_exe = source_dir / OUTPUT_EXE_NAME
    if not hub_exe.is_file():
        print(f"Cannot normalize hub dist; executable missing: {hub_exe}")
        raise SystemExit(1)
    if source_dir == target_dir:
        return target_dir
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_dir), str(target_dir))
    print(f"Normalized hub bundle to: {target_dir}")
    return target_dir


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
        f"--cache-dir={NUITKA_CACHE_DIR}",
        "--standalone",
        "--module-parameter=numba-disable-jit=yes",
        f"--jobs={nuitka_parallel_jobs()}",
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


def ensure_dist_icon(dist_dir: Path) -> None:
    """Copy the app icon beside the hub so shortcuts and Explorer can use it."""
    if not ICON_PATH.is_file():
        return
    shutil.copy2(ICON_PATH, dist_dir / ICON_PATH.name)


def build_pyinstaller_fallback() -> None:
    """Fallback Windows build path when Nuitka fails on this runtime."""
    print("Falling back to PyInstaller Windows onedir build...")
    pyinstaller_work_dir = WINDOWS_BUILD_OUTPUT_DIR / "pyinstaller-work"
    pyinstaller_name = OUTPUT_EXE_NAME.removesuffix(".exe")
    pyinstaller_args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        f"--icon={ICON_PATH.resolve()}",
        f"--name={pyinstaller_name}",
        f"--distpath={WINDOWS_BUILD_OUTPUT_DIR}",
        f"--workpath={pyinstaller_work_dir}",
        f"--specpath={pyinstaller_work_dir}",
        f"--paths={REPO_ROOT / 'src'}",
        str(MAIN_SCRIPT),
    ]
    pyinstaller_args.extend(linux_pyinstaller_data_arguments(os.pathsep))
    pyinstaller_args.append(f"--add-data={ICON_PATH}{os.pathsep}.")

    for module_name in required_include_modules():
        pyinstaller_args.append(f"--hidden-import={module_name}")
    for package_name in REQUIRED_PACKAGES:
        pyinstaller_args.append(f"--hidden-import={package_name}")

    for package_name in PYINSTALLER_COLLECT_ALL_PACKAGES:
        pyinstaller_args.append(f"--collect-all={package_name}")
    for package_name in REQUIRED_PACKAGE_DATA:
        pyinstaller_args.append(f"--collect-data={package_name}")
    for excluded_module in PYINSTALLER_EXCLUDE_MODULES:
        pyinstaller_args.append(f"--exclude-module={excluded_module}")

    try:
        subprocess.run(pyinstaller_args, check=True, cwd=str(REPO_ROOT))
    except subprocess.CalledProcessError as exc:
        print("PyInstaller fallback failed.")
        raise SystemExit(1) from exc

    pyinstaller_dist = WINDOWS_BUILD_OUTPUT_DIR / pyinstaller_name
    if not (pyinstaller_dist / OUTPUT_EXE_NAME).is_file():
        found = _find_newest_exe(WINDOWS_BUILD_OUTPUT_DIR, (OUTPUT_EXE_NAME,))
        if found is None:
            print(f"PyInstaller fallback completed but no executable was found under {WINDOWS_BUILD_OUTPUT_DIR}")
            raise SystemExit(1)
        pyinstaller_dist = found.parent

    dist_dir = normalize_hub_dist_dir(pyinstaller_dist)
    ensure_dist_icon(dist_dir)
    print(f"PyInstaller fallback produced executable: {dist_dir / OUTPUT_EXE_NAME}")


def _find_newest_exe(search_dir: Path, preferred_names: tuple[str, ...]) -> Path | None:
    """Locate a freshly built executable under a Nuitka output directory."""
    if not search_dir.exists():
        return None
    for name in preferred_names:
        candidate = search_dir / name
        if candidate.is_file():
            return candidate
    matches = sorted(search_dir.rglob("*.exe"), key=lambda path: path.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _newest_mtime(paths: list[Path]) -> float:
    """Return the newest modification time among existing paths."""
    latest = 0.0
    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            latest = max(latest, path.stat().st_mtime)
            continue
        for child in path.rglob("*"):
            if child.is_file():
                latest = max(latest, child.stat().st_mtime)
    return latest


def anika_build_is_current(destination: Path) -> bool:
    """Return True when Anika.exe is newer than all Anika source files."""
    if not destination.is_file():
        return False
    source_mtime = _newest_mtime([ANIKA_DIR / "main.py", ANIKA_APP_DIR, ANIKA_RESOURCES_DIR])
    return destination.stat().st_mtime >= source_mtime


def build_anika_with_pyinstaller(dist_dir: Path) -> Path | None:
    """Build Anika.exe via PyInstaller onefile (faster than Nuitka for the companion app)."""
    print("Building Anika desktop assistant with PyInstaller...")
    pyinstaller_work = ANIKA_BUILD_DIR / "pyinstaller-work"
    pyinstaller_dist = ANIKA_BUILD_DIR / "pyinstaller-dist"
    pyinstaller_work.mkdir(parents=True, exist_ok=True)
    pyinstaller_dist.mkdir(parents=True, exist_ok=True)

    anika_args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        f"--icon={ICON_PATH.resolve()}",
        "--name=Anika",
        f"--distpath={pyinstaller_dist}",
        f"--workpath={pyinstaller_work}",
        f"--specpath={pyinstaller_work}",
        f"--paths={ANIKA_DIR}",
        f"--add-data={ANIKA_RESOURCES_DIR}{os.pathsep}resources",
        str(ANIKA_MAIN_SCRIPT),
    ]
    for package_name in ANIKA_INCLUDE_PACKAGES:
        anika_args.append(f"--hidden-import={package_name}")
    for module_name in discover_anika_module_names():
        anika_args.append(f"--hidden-import={module_name}")
    for module_name in ANIKA_OPTIONAL_MODULES:
        anika_args.append(f"--hidden-import={module_name}")

    try:
        subprocess.run(anika_args, check=True, cwd=str(ANIKA_DIR))
    except subprocess.CalledProcessError:
        print("Anika PyInstaller build failed.")
        return None

    built_exe = pyinstaller_dist / ANIKA_OUTPUT_EXE_WIN
    if not built_exe.is_file():
        built_exe = _find_newest_exe(pyinstaller_dist, (ANIKA_OUTPUT_EXE_WIN, "Anika.exe"))
    if built_exe is None:
        print(f"Anika PyInstaller build finished but no executable was found under {pyinstaller_dist}")
        return None

    destination = dist_dir / ANIKA_OUTPUT_EXE_WIN
    shutil.copy2(built_exe, destination)
    print(f"Anika assistant executable copied to: {destination}")
    return destination


def hub_uses_pyinstaller_layout(dist_dir: Path) -> bool:
    """Return True when the hub bundle was produced by PyInstaller onedir."""
    return dist_dir.name == OUTPUT_EXE_NAME.removesuffix(".exe")


def build_anika_companion() -> None:
    """Build a standalone Anika.exe desktop assistant placed beside the main hub binary."""
    if env_flag("MD_SKIP_ANIKA"):
        print("Skipping Anika build (MD_SKIP_ANIKA=1).")
        return
    if not ANIKA_MAIN_SCRIPT.is_file():
        print("Anika entry script missing; skipping assistant build.")
        return

    dist_dir = resolve_hub_dist_dir()
    destination = dist_dir / ANIKA_OUTPUT_EXE_WIN
    if anika_build_is_current(destination):
        print(f"Anika assistant is up to date: {destination}")
        return

    prefer_pyinstaller = env_flag("MD_ANIKA_PYINSTALLER") or hub_uses_pyinstaller_layout(dist_dir)
    if prefer_pyinstaller:
        if build_anika_with_pyinstaller(dist_dir) is not None:
            return
        print("Anika PyInstaller build failed; trying Nuitka...")

    print("Building Anika desktop assistant executable with Nuitka...")
    if ANIKA_BUILD_DIR.exists():
        shutil.rmtree(ANIKA_BUILD_DIR, ignore_errors=True)
    ANIKA_BUILD_DIR.mkdir(parents=True, exist_ok=True)
    anika_jobs = nuitka_parallel_jobs(companion=True)
    print(f"Anika Nuitka parallel jobs: {anika_jobs}")

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ANIKA_DIR) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")

    anika_args = [
        sys.executable,
        "-m",
        "nuitka",
        "--assume-yes-for-downloads",
        "--windows-console-mode=disable",
        "--plugin-enable=tk-inter",
        f"--output-dir={ANIKA_BUILD_DIR}",
        f"--output-filename={ANIKA_OUTPUT_EXE_WIN}",
        f"--cache-dir={NUITKA_CACHE_DIR}",
        "--standalone",
        f"--jobs={anika_jobs}",
        "--lto=no",
        str(ANIKA_MAIN_SCRIPT),
    ]
    anika_args.extend(select_compiler_arguments())
    anika_args.extend(anika_nuitka_data_arguments())
    for excluded_import in EXCLUDED_IMPORTS:
        anika_args.append(f"--nofollow-import-to={excluded_import}")
    for package_name in ANIKA_INCLUDE_PACKAGES:
        anika_args.append(f"--include-package={package_name}")
    for package_name in ANIKA_INCLUDE_PACKAGE_DATA:
        anika_args.append(f"--include-package-data={package_name}")
    for module_name in discover_anika_module_names():
        anika_args.append(f"--include-module={module_name}")
    for module_name in ANIKA_OPTIONAL_MODULES:
        anika_args.append(f"--include-module={module_name}")

    try:
        subprocess.run(anika_args, check=True, cwd=str(ANIKA_DIR), env=env)
    except subprocess.CalledProcessError as exc:
        print(f"Anika Nuitka build failed with error code {exc.returncode}")
        if build_anika_with_pyinstaller(dist_dir) is not None:
            return
        print("The hub installer will still ship without Anika.exe; Tools -> Anika will not work until it is built.")
        return

    built_exe = _find_newest_exe(
        ANIKA_BUILD_DIR,
        (ANIKA_OUTPUT_EXE_WIN, "main.exe", "Anika.exe"),
    )
    if built_exe is None:
        built_exe = _find_newest_exe(ANIKA_BUILD_DIR / "main.dist", (ANIKA_OUTPUT_EXE_WIN, "main.exe"))
    if built_exe is None:
        print(f"Anika Nuitka build finished but no executable was found under {ANIKA_BUILD_DIR}")
        if build_anika_with_pyinstaller(dist_dir) is not None:
            return
        return

    shutil.copy2(built_exe, destination)
    print(f"Anika assistant executable copied to: {destination}")


def build_executable() -> None:
    if env_flag("MD_INSTALLER_ONLY"):
        dist_dir = resolve_hub_dist_dir()
        print(f"Skipping hub build; reusing {dist_dir / OUTPUT_EXE_NAME}")
        return

    if env_flag("MD_HUB_PYINSTALLER"):
        build_pyinstaller_fallback()
        return

    print("Building executable with Nuitka...")
    print(f"Using up to {nuitka_parallel_jobs()} parallel compiler jobs.")
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
    if env_flag("MD_SKIP_INNO"):
        print("Skipping Inno Setup (MD_SKIP_INNO=1).")
        return

    compiler = find_inno_setup_compiler()
    if not compiler:
        print("Inno Setup compiler not found. Install Inno Setup 6 or add ISCC.exe to PATH.")
        raise SystemExit(1)

    expected_binary_path = resolve_hub_dist_dir() / OUTPUT_EXE_NAME
    if not expected_binary_path.exists():
        print(f"Expected executable not found: {expected_binary_path}")
        raise SystemExit(1)

    print("Building installer with Inno Setup...")
    source_dir = expected_binary_path.parent
    try:
        result = subprocess.run(
            [
                compiler,
                f"/DMyAppSourceDir={source_dir}",
                f"/DMyAppExeName={OUTPUT_EXE_NAME}",
                f"/DMyAppVersion={VERSION}",
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


def ensure_supported_python_for_nuitka() -> None:
    """Refuse Python 3.14+ — Nuitka bundles crash at startup (marshal data too short)."""
    if sys.version_info >= (3, 14):
        print(
            "ERROR: Python 3.14 is not supported for Nuitka builds.\n"
            "Installed apps crash on launch with: EOFError: marshal data too short\n\n"
            "Install Python 3.13 from https://www.python.org/downloads/\n"
            "Then rebuild:\n"
            "  py -3.13 -m pip install -r src\\desktop_tools\\app\\requirements.txt nuitka ordered-set zstandard\n"
            "  set PYTHONPATH=src\n"
            "  py -3.13 -m desktop_tools.app.build_tools.nuitka"
        )
        raise SystemExit(1)


def main() -> None:
    print("Starting build process...")
    ensure_windows_environment()
    relaunch_with_python_313_if_available()
    ensure_supported_python_for_nuitka()
    validate_source_tree()
    print_bundle_summary()
    ensure_build_dependencies()
    clean_directories(full=env_flag("MD_BUILD_CLEAN"))

    if env_flag("MD_ANIKA_ONLY"):
        build_anika_companion()
        build_inno_installer()
    elif env_flag("MD_REBUILD_ICONS"):
        build_pyinstaller_fallback()
        build_anika_companion()
        build_inno_installer()
    else:
        build_executable()
        build_anika_companion()
        build_inno_installer()
    try:
        from .release_ci import write_build_info

        write_build_info(VERSION, WINDOWS_RELEASE_DIR)
    except Exception as exc:
        print(f"Could not write build-info.json: {exc}")
    print("Build process finished.")


if __name__ == "__main__":
    main()
