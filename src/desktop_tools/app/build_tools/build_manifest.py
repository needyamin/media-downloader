"""Shared packaging manifest for Windows (Nuitka) and Linux (PyInstaller) builds."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
APP_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
SHARED_DIR = SRC_DIR / "desktop_tools" / "shared"
ANIKA_DIR = SRC_DIR / "desktop_tools" / "anika"
ANIKA_MAIN_SCRIPT = ANIKA_DIR / "main.py"
ANIKA_RESOURCES_DIR = ANIKA_DIR / "resources"
ANIKA_APP_DIR = ANIKA_DIR / "app"
ANIKA_OUTPUT_EXE_WIN = "Anika.exe"
ANIKA_OUTPUT_EXE_LINUX = "Anika"
ANIKA_REQUIRED_ASSETS = frozenset(
    {
        "idle.png",
        "dragged.png",
        "action.png",
        "sleeping.png",
    }
)
ANIKA_INCLUDE_PACKAGES = [
    "PIL",
    "customtkinter",
]
ANIKA_INCLUDE_PACKAGE_DATA = [
    "customtkinter",
    "PIL",
]
ANIKA_OPTIONAL_MODULES = [
    "keyboard",
]
APP_PACKAGE = "desktop_tools.app"
SHARED_PACKAGE = "desktop_tools.shared"

MAIN_SCRIPT = APP_DIR / "media_download.py"
ASSETS_DIR = APP_DIR / "assets"
ICON_PATH = ASSETS_DIR / "needyamin.ico"
REQUIREMENTS_FILE = APP_DIR / "requirements.txt"
APP_FLAGS_PATH = REPO_ROOT / "app_flags.json"
INNO_SCRIPT = APP_DIR / "installer" / "setup.iss"

# App entry scripts that are build tooling, not bundled application code.
BUILD_SCRIPT_STEMS = frozenset(
    {
        "nutika_build",
        "nuitka_build",
        "linux_appimage_build",
        "build_manifest",
        "__init__",
    }
)

EXCLUDED_IMPORTS = [
    "IPython",
    "matplotlib",
    "pandas",
    "pytest",
    "jupyter",
    "setuptools",
    "win32com.test",
]

REQUIRED_DYNAMIC_MODULES = [
    "tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    "tkinter.filedialog",
    "tkinter.simpledialog",
    "webbrowser",
    "onnxruntime.capi._ld_preload",
    "onnxruntime.capi._pybind_state",
    "onnxruntime.capi.onnxruntime_pybind11_state",
    "scipy.ndimage",
    "skimage.morphology",
    "pymatting.alpha.estimate_alpha_cf",
    "pymatting.foreground.estimate_foreground_ml",
    "pymatting.util.util",
]

REQUIRED_PACKAGES = [
    "yt_dlp",
    "pystray",
    "PIL",
    "pyperclip",
    "validators",
    "requests",
    "win32com",
    "certifi",
    "desktop_tools",
    "customtkinter",
    "numpy",
    "numba",
    "llvmlite",
    "rembg",
    "onnxruntime",
    "scipy",
    "skimage",
    "pymatting",
    "pooch",
    "tqdm",
    "jsonschema",
]

REQUIRED_PACKAGE_DATA = [
    "customtkinter",
    "PIL",
    "pystray",
    "rembg",
    "onnxruntime",
    "pooch",
    "certifi",
    "jsonschema",
    "jsonschema_specifications",
    "scipy",
    "skimage",
    "yt_dlp",
]

LINUX_EXCLUDED_MODULES = [
    "win32com",
    "win32com.client",
    "pywintypes",
    "pythoncom",
    "winreg",
]

LINUX_COLLECT_ALL_PACKAGES = [
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
]

LINUX_COLLECT_SUBMODULE_PACKAGES = [
    "desktop_tools",
    "yt_dlp",
]


def discover_app_module_names() -> list[str]:
    """Return desktop_tools.app.* modules for every bundled tool script."""
    modules: list[str] = []
    for script_path in sorted(APP_DIR.rglob("*_app.py")):
        if script_path.stem in BUILD_SCRIPT_STEMS:
            continue
        relative_module = script_path.relative_to(SRC_DIR).with_suffix("")
        modules.append(".".join(relative_module.parts))
    return modules


def discover_shared_module_names() -> list[str]:
    """Return desktop_tools.shared.* modules shipped with the desktop bundle."""
    modules: list[str] = []
    for script_path in sorted(SHARED_DIR.glob("*.py")):
        if script_path.stem == "__init__":
            continue
        modules.append(f"{SHARED_PACKAGE}.{script_path.stem}")
    return modules


def discover_asset_files() -> list[Path]:
    """Return every file under the app assets directory."""
    if not ASSETS_DIR.is_dir():
        return []
    return sorted(path for path in ASSETS_DIR.rglob("*") if path.is_file())


def discover_anika_module_names() -> list[str]:
    """Return app.* modules shipped inside the Anika desktop assistant process."""
    if not ANIKA_APP_DIR.is_dir():
        return []
    modules: list[str] = []
    for script_path in sorted(ANIKA_APP_DIR.glob("*.py")):
        if script_path.stem == "__init__":
            continue
        modules.append(f"app.{script_path.stem}")
    return modules


def discover_anika_data_files() -> list[Path]:
    """Return Anika desktop assistant resources and entry scripts for packaged builds."""
    if not ANIKA_DIR.is_dir():
        return []
    files: list[Path] = []
    for path in ANIKA_DIR.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        if path.suffix == ".pyc":
            continue
        files.append(path)
    return sorted(files)


def discover_asset_names_from_source() -> set[str]:
    """Collect asset filenames referenced via get_asset_path(...) in app sources."""
    names: set[str] = set()
    pattern = re.compile(r"""get_asset_path\(\s*['"]([^'"]+)['"]\s*\)""")
    for script_path in APP_DIR.rglob("*.py"):
        if "build_tools" in script_path.parts:
            continue
        if script_path.stem in BUILD_SCRIPT_STEMS:
            continue
        try:
            contents = script_path.read_text(encoding="utf-8")
        except OSError:
            continue
        names.update(pattern.findall(contents))
    return names


def validate_source_tree() -> None:
    """Fail fast when required packaging inputs are missing."""
    missing: list[str] = []

    for label, path in (
        ("main script", MAIN_SCRIPT),
        ("requirements", REQUIREMENTS_FILE),
        ("app flags", APP_FLAGS_PATH),
        ("installer script", INNO_SCRIPT),
        ("app icon", ICON_PATH),
    ):
        if not path.exists():
            missing.append(f"{label}: {path}")

    if not ASSETS_DIR.is_dir():
        missing.append(f"assets directory: {ASSETS_DIR}")

    asset_files = discover_asset_files()
    if ASSETS_DIR.is_dir() and not asset_files:
        missing.append(f"no files found under assets: {ASSETS_DIR}")

    referenced_assets = discover_asset_names_from_source()
    available_names = {path.name for path in asset_files}
    for asset_name in sorted(referenced_assets):
        if asset_name not in available_names:
            missing.append(f"referenced asset not on disk: assets/{asset_name}")

    app_modules = discover_app_module_names()
    if not app_modules:
        missing.append(f"no *_app.py modules found in {APP_DIR}")

    shared_modules = discover_shared_module_names()
    if not shared_modules:
        missing.append(f"no shared modules found in {SHARED_DIR}")

    if not ANIKA_DIR.is_dir():
        missing.append(f"anika directory: {ANIKA_DIR}")
    elif not ANIKA_MAIN_SCRIPT.is_file():
        missing.append(f"anika entry script: {ANIKA_MAIN_SCRIPT}")
    elif not ANIKA_RESOURCES_DIR.is_dir():
        missing.append(f"anika resources directory: {ANIKA_RESOURCES_DIR}")
    else:
        for asset_name in sorted(ANIKA_REQUIRED_ASSETS):
            asset_path = ANIKA_RESOURCES_DIR / asset_name
            if not asset_path.is_file():
                missing.append(f"anika required asset: resources/{asset_name}")
        if not discover_anika_module_names():
            missing.append(f"no anika app modules found in {ANIKA_APP_DIR}")

    if missing:
        print("Packaging manifest validation failed:")
        for item in missing:
            print(f"  - {item}")
        raise SystemExit(1)


def print_bundle_summary() -> None:
    """Print everything that will be included in packaged builds."""
    print("Bundle manifest:")
    print(f"  Main script: {MAIN_SCRIPT.name}")
    print(f"  App flags: {APP_FLAGS_PATH.name}")
    print("  App modules:")
    for module_name in discover_app_module_names():
        print(f"    - {module_name}")
    print("  Shared modules:")
    for module_name in discover_shared_module_names():
        print(f"    - {module_name}")
    print("  Asset files:")
    for asset_path in discover_asset_files():
        relative = asset_path.relative_to(ASSETS_DIR)
        print(f"    - assets/{relative.as_posix()}")
    print("  Anika desktop assistant:")
    print(f"    - entry: {ANIKA_MAIN_SCRIPT.relative_to(REPO_ROOT).as_posix()}")
    print(f"    - packaged exe (Windows): {ANIKA_OUTPUT_EXE_WIN}")
    print("  Anika modules:")
    for module_name in discover_anika_module_names():
        print(f"    - {module_name}")
    print("  Anika data files:")
    for data_path in discover_anika_data_files():
        relative = data_path.relative_to(ANIKA_DIR)
        print(f"    - anika/{relative.as_posix()}")


def anika_nuitka_data_arguments() -> list[str]:
    """Data files embedded in the standalone Anika desktop assistant binary."""
    args: list[str] = []
    if ANIKA_RESOURCES_DIR.is_dir():
        args.append(f"--include-data-dir={ANIKA_RESOURCES_DIR}=resources")
    return args


def nuitka_data_file_arguments() -> list[str]:
    """Build Nuitka --include-data-* arguments for flags, assets, and root-level fallbacks."""
    args: list[str] = [
        f"--include-data-dir={ASSETS_DIR}=assets",
        f"--include-data-files={APP_FLAGS_PATH}=app_flags.json",
    ]
    if ANIKA_DIR.is_dir():
        args.append(f"--include-data-dir={ANIKA_DIR}=desktop_tools/anika")

    # Top-level copies support get_asset_path() and get_project_root() bundle fallbacks.
    for asset_path in discover_asset_files():
        if asset_path.parent == ASSETS_DIR:
            args.append(f"--include-data-files={asset_path}={asset_path.name}")

    return _dedupe_preserve_order(args)


def linux_pyinstaller_data_arguments(os_pathsep: str) -> list[str]:
    """Build PyInstaller --add-data arguments mirroring the Nuitka bundle layout."""
    args: list[str] = [
        f"--add-data={ASSETS_DIR}{os_pathsep}assets",
        f"--add-data={APP_FLAGS_PATH}{os_pathsep}.",
    ]
    if ANIKA_DIR.is_dir():
        args.append(f"--add-data={ANIKA_DIR}{os_pathsep}desktop_tools/anika")

    for asset_path in discover_asset_files():
        if asset_path.parent == ASSETS_DIR:
            args.append(f"--add-data={asset_path}{os_pathsep}.")

    return _dedupe_preserve_order(args)


def required_include_modules() -> list[str]:
    """Return all explicit Python modules that must be embedded in packaged builds."""
    return [
        *discover_app_module_names(),
        *discover_shared_module_names(),
        *REQUIRED_DYNAMIC_MODULES,
    ]


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def main() -> None:
    """Validate package inputs and print the effective bundle manifest."""
    validate_source_tree()
    print_bundle_summary()


if __name__ == "__main__":
    main()
