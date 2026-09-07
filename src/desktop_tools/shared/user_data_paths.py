"""Per-user data locations and uninstall cleanup paths for Media Downloader tools."""

from __future__ import annotations

import shutil
from pathlib import Path
import tempfile

from desktop_tools.shared.resources import get_user_data_dir

APP_USER_DATA_NAME = "Media Downloader"
REMBG_MODELS_DIRNAME = "rembg_models"
ANIKA_DATA_DIRNAME = "anika"
LEGACY_REMBG_DIR = Path.home() / ".u2net"
LEGACY_REMBG_NESTED_DIR = Path.home() / ".rembg"
LEGACY_ANIKA_DIR = Path.home() / ".yamos_witch_mate"
BG_REMOVER_DIAGNOSTICS_BASENAME = "media_downloader_bg_remover_diagnostics.txt"


def get_app_user_data_dir() -> Path:
    """Writable app folder: settings, ffmpeg, AI models, Anika config, updates."""
    return get_user_data_dir(APP_USER_DATA_NAME)


def get_rembg_models_dir() -> Path:
    """Directory for downloaded rembg ONNX weights (background remover)."""
    target = get_app_user_data_dir() / REMBG_MODELS_DIRNAME
    target.mkdir(parents=True, exist_ok=True)
    _migrate_files(LEGACY_REMBG_DIR, target, ("*.onnx",))
    _migrate_nested_onnx(LEGACY_REMBG_NESTED_DIR / "models", target)
    return target


def get_anika_user_dir() -> Path:
    """Directory for Anika desktop assistant settings and session files."""
    target = get_app_user_data_dir() / ANIKA_DATA_DIRNAME
    target.mkdir(parents=True, exist_ok=True)
    _migrate_tree(LEGACY_ANIKA_DIR, target)
    return target


def get_bg_remover_diagnostics_path() -> Path:
    return Path(tempfile.gettempdir()) / BG_REMOVER_DIAGNOSTICS_BASENAME


def iter_uninstall_cleanup_paths() -> list[Path]:
    """
    Paths removed by the Windows uninstaller (app data + legacy caches).

    Does not include the user's download folder (e.g. Downloads/AnsNewTech Downloads).
    """
    paths = [
        get_app_user_data_dir(),
        LEGACY_REMBG_DIR,
        LEGACY_REMBG_NESTED_DIR,
        LEGACY_ANIKA_DIR,
        get_bg_remover_diagnostics_path(),
    ]
    unique: list[Path] = []
    for path in paths:
        normalized = path.resolve()
        if normalized not in unique:
            unique.append(normalized)
    return unique


def _migrate_nested_onnx(source_models_dir: Path, target_dir: Path) -> None:
    """Copy ~/.rembg/models/<name>/<name>.onnx into the flat app cache."""
    if not source_models_dir.is_dir():
        return
    for model_dir in source_models_dir.iterdir():
        if not model_dir.is_dir():
            continue
        for item in model_dir.glob("*.onnx"):
            destination = target_dir / item.name
            if destination.exists():
                continue
            try:
                shutil.copy2(item, destination)
            except OSError:
                pass


def _migrate_files(source_dir: Path, target_dir: Path, patterns: tuple[str, ...]) -> None:
    if not source_dir.is_dir():
        return
    if any(target_dir.glob("*.onnx")):
        return
    for pattern in patterns:
        for item in source_dir.glob(pattern):
            if not item.is_file():
                continue
            destination = target_dir / item.name
            if destination.exists():
                continue
            try:
                shutil.copy2(item, destination)
            except OSError:
                pass


def _migrate_tree(source_dir: Path, target_dir: Path) -> None:
    if not source_dir.is_dir():
        return
    if any(target_dir.iterdir()):
        return
    for item in source_dir.iterdir():
        destination = target_dir / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, destination, dirs_exist_ok=True)
            elif item.is_file():
                shutil.copy2(item, destination)
        except OSError:
            pass
