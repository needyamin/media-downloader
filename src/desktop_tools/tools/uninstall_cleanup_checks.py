"""Checks for uninstall user-data path helpers."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def check_paths() -> None:
    from desktop_tools.shared.user_data_paths import (
        ANIKA_DATA_DIRNAME,
        APP_USER_DATA_NAME,
        REMBG_MODELS_DIRNAME,
        get_anika_user_dir,
        get_app_user_data_dir,
        get_rembg_models_dir,
        iter_uninstall_cleanup_paths,
    )

    app_dir = get_app_user_data_dir()
    assert APP_USER_DATA_NAME in str(app_dir)
    assert get_rembg_models_dir().parent == app_dir
    assert get_rembg_models_dir().name == REMBG_MODELS_DIRNAME
    assert get_anika_user_dir().name == ANIKA_DATA_DIRNAME

    cleanup = iter_uninstall_cleanup_paths()
    assert app_dir in cleanup
    print("OK uninstall: user data paths", len(cleanup), "entries")


def main() -> None:
    _ensure_src_on_path()
    check_paths()
    print("Uninstall cleanup checks passed.")


if __name__ == "__main__":
    main()
