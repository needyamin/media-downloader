"""Path and resource helpers used across desktop tools."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import ctypes

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None


def _get_nuitka_containing_dir() -> Path | None:
    """Return Nuitka's containing directory when available."""
    compiled_info = globals().get("__compiled__")
    if compiled_info is None:
        return None

    containing_dir = getattr(compiled_info, "containing_dir", None)
    if containing_dir is None and isinstance(compiled_info, dict):
        containing_dir = compiled_info.get("containing_dir")

    return Path(containing_dir) if containing_dir else None


def _iter_candidate_roots() -> list[Path]:
    """Return likely runtime roots for development and packaged builds."""
    roots: list[Path] = []

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        roots.append(Path(sys._MEIPASS))

    nuitka_dir = _get_nuitka_containing_dir()
    if nuitka_dir is not None:
        roots.append(nuitka_dir)

    try:
        roots.append(Path(sys.argv[0]).resolve().parent)
    except Exception:
        pass

    roots.append(Path(__file__).resolve().parents[3])

    unique_roots: list[Path] = []
    for root in roots:
        if root not in unique_roots:
            unique_roots.append(root)
    return unique_roots


def get_project_root() -> Path:
    """Return the repository root in development mode or bundle root in packaged mode."""
    candidate_roots = _iter_candidate_roots()
    for root in candidate_roots:
        if (root / "app_flags.json").exists() or (root / "assets").exists() or (root / "needyamin.ico").exists():
            return root
    return candidate_roots[0]

def get_app_root() -> Path:
    """Return the app package root in development mode or bundle root in packaged mode."""
    for root in _iter_candidate_roots():
        candidates = [
            root / "src" / "desktop_tools" / "app",
            root / "desktop_tools" / "app",
            root,
        ]
        for candidate in candidates:
            if (candidate / "assets").exists():
                return candidate
    return get_project_root()


def get_asset_path(asset_name: str) -> Path:
    """Resolve a bundled or development asset path."""
    root = get_project_root()
    app_root = get_app_root()
    candidates = [
        app_root / "assets" / asset_name,
        root / "assets" / asset_name,
        root / asset_name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def get_user_data_dir(app_name: str = "Media Downloader") -> Path:
    """Return a writable per-user app data directory across supported platforms."""
    if sys.platform.startswith("win"):
        base_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Application Support"
    else:
        base_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    target_dir = base_dir / app_name
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def apply_window_icon(window, app_id: str = "needyamin.media_downloader") -> Path:
    """Apply the shared app icon to a Tk window and its Windows taskbar identity."""
    icon_path = get_asset_path("needyamin.ico")

    try:
        if sys.platform.startswith("win"):
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass

    if icon_path.exists():
        try:
            if Image is not None and ImageTk is not None:
                icon_image = ImageTk.PhotoImage(Image.open(icon_path))
                window.iconphoto(True, icon_image)
                window._shared_icon_photo = icon_image
            if sys.platform.startswith("win"):
                window.iconbitmap(str(icon_path))
        except Exception:
            pass

    return icon_path


def center_window(window, parent=None) -> None:
    """Center a Tk window on its parent, or on screen when no parent is available."""
    try:
        window.update_idletasks()

        width = window.winfo_width() or window.winfo_reqwidth()
        height = window.winfo_height() or window.winfo_reqheight()

        if width <= 1 or height <= 1:
            geometry = window.geometry().split("+", 1)[0]
            if "x" in geometry:
                try:
                    width, height = [int(value) for value in geometry.split("x", 1)]
                except ValueError:
                    width = max(window.winfo_reqwidth(), 1)
                    height = max(window.winfo_reqheight(), 1)

        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()

        if parent is not None and parent.winfo_exists():
            parent.update_idletasks()
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_width = max(parent.winfo_width(), parent.winfo_reqwidth())
            parent_height = max(parent.winfo_height(), parent.winfo_reqheight())
            x = parent_x + (parent_width - width) // 2
            y = parent_y + (parent_height - height) // 2
        else:
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2

        x = max(0, min(x, max(screen_width - width, 0)))
        y = max(0, min(y, max(screen_height - height, 0)))
        window.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        pass
