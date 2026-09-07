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
        if (root / "desktop_tools" / "anika" / "main.py").exists():
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


_ICON_PHOTO = None
_ICON_HOOK_INSTALLED = False
DEFAULT_APP_ID = "needyamin.media_downloader"


class _WinRECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _WinPOINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _WinMONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", _WinRECT),
        ("rcWork", _WinRECT),
        ("dwFlags", ctypes.c_ulong),
    ]


def _icon_photo(icon_path: Path):
    """Keep one PhotoImage alive so Tk does not drop the window icon."""
    global _ICON_PHOTO
    if _ICON_PHOTO is not None:
        return _ICON_PHOTO
    if Image is None or ImageTk is None or not icon_path.exists():
        return None
    try:
        _ICON_PHOTO = ImageTk.PhotoImage(Image.open(icon_path))
    except Exception:
        return None
    return _ICON_PHOTO


def _window_exists(window) -> bool:
    if window is None:
        return False
    try:
        return bool(window.winfo_exists())
    except Exception:
        return False


def _apply_icon_now(window, icon_path: Path) -> None:
    if not _window_exists(window) or not icon_path.exists():
        return
    try:
        photo = _icon_photo(icon_path)
        if photo is not None:
            window.iconphoto(True, photo)
            window._shared_icon_photo = photo
    except Exception:
        pass
    if sys.platform.startswith("win"):
        try:
            window.iconbitmap(default=str(icon_path))
        except Exception:
            try:
                window.iconbitmap(str(icon_path))
            except Exception:
                pass


def apply_window_icon(window, app_id: str = DEFAULT_APP_ID) -> Path:
    """Apply the shared app icon to a Tk window and its Windows taskbar identity."""
    icon_path = get_asset_path("needyamin.ico")

    try:
        if sys.platform.startswith("win"):
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass

    if window is not None:
        _apply_icon_now(window, icon_path)
        # CTk / Windows often reset the icon after the window is mapped.
        try:
            window.after_idle(lambda w=window, path=icon_path: _apply_icon_now(w, path))
            window.after(250, lambda w=window, path=icon_path: _apply_icon_now(w, path))
        except Exception:
            pass

    install_window_icon_hook()
    return icon_path


def _window_is_borderless(window) -> bool:
    try:
        if bool(window.overrideredirect()):
            return True
    except Exception:
        pass
    try:
        if str(window.attributes("-fullscreen")).lower() in {"1", "true"}:
            return True
    except Exception:
        pass
    return False


def _window_is_withdrawn(window) -> bool:
    try:
        return str(window.state()) == "withdrawn"
    except Exception:
        return False


def _should_auto_center(window) -> bool:
    if not _window_exists(window):
        return False
    if getattr(window, "_skip_auto_center", False):
        return False
    if _window_is_borderless(window):
        return False
    if _window_is_withdrawn(window):
        return False
    return True


def _schedule_auto_center(window) -> None:
    """Center a new window after it has a real size and has been mapped."""
    def _run(target=window):
        if _should_auto_center(target):
            center_window(target)

    def _finish(target=window):
        _run(target)
        bind_id = getattr(target, "_center_map_bind", None)
        if bind_id is not None:
            try:
                target.unbind("<Map>", bind_id)
            except Exception:
                pass
            target._center_map_bind = None

    try:
        window.after_idle(_run)
        window.after(60, _finish)

        def _on_map(event, target=window):
            if event.widget is target:
                _run()

        window._center_map_bind = window.bind("<Map>", _on_map, add="+")
    except Exception:
        pass

    try:
        window.after_idle(_run)
        window.after(50, _run)

        def _on_map(event, target=window):
            if event.widget is target:
                _run()

        window._center_map_bind = window.bind("<Map>", _on_map, add="+")
    except Exception:
        pass


def install_window_icon_hook() -> None:
    """Make every new Tk / CustomTkinter window use the app icon and open centered."""
    global _ICON_HOOK_INSTALLED
    if _ICON_HOOK_INSTALLED:
        return
    _ICON_HOOK_INSTALLED = True

    try:
        import tkinter as tk

        original_tk = tk.Tk.__init__

        def _tk_init(self, *args, **kwargs):
            original_tk(self, *args, **kwargs)
            _schedule_auto_center(self)

        tk.Tk.__init__ = _tk_init

        original = tk.Toplevel.__init__

        def _toplevel_init(self, *args, **kwargs):
            original(self, *args, **kwargs)
            apply_window_icon(self)
            _schedule_auto_center(self)

        tk.Toplevel.__init__ = _toplevel_init
    except Exception:
        pass

    try:
        import customtkinter as ctk

        original_ctk = ctk.CTkToplevel.__init__

        def _ctk_init(self, *args, **kwargs):
            original_ctk(self, *args, **kwargs)
            apply_window_icon(self)
            _schedule_auto_center(self)

        ctk.CTkToplevel.__init__ = _ctk_init
    except Exception:
        pass


def _screen_work_area(window) -> tuple[int, int, int, int]:
    """Return (left, top, width, height) of the screen work area to center on."""
    if sys.platform.startswith("win"):
        try:
            user32 = ctypes.windll.user32
            point = _WinPOINT()
            if user32.GetCursorPos(ctypes.byref(point)):
                monitor = user32.MonitorFromPoint(point, 2)  # MONITOR_DEFAULTTONEAREST
                info = _WinMONITORINFO()
                info.cbSize = ctypes.sizeof(_WinMONITORINFO)
                if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                    work = info.rcWork
                    width = work.right - work.left
                    height = work.bottom - work.top
                    if width > 0 and height > 0:
                        return work.left, work.top, width, height
        except Exception:
            pass
        try:
            rect = _WinRECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                width = rect.right - rect.left
                height = rect.bottom - rect.top
                if width > 0 and height > 0:
                    return rect.left, rect.top, width, height
        except Exception:
            pass

    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    return 0, 0, screen_width, screen_height


def _window_size(window) -> tuple[int, int]:
    geometry = window.geometry().split("+", 1)[0]
    if "x" in geometry:
        try:
            width, height = [int(value) for value in geometry.split("x", 1)]
            if width > 1 and height > 1:
                return width, height
        except ValueError:
            pass
    width = max(int(window.winfo_width() or 0), int(window.winfo_reqwidth() or 0), 1)
    height = max(int(window.winfo_height() or 0), int(window.winfo_reqheight() or 0), 1)
    return width, height


def center_window(window, parent=None) -> None:
    """Center a Tk window in the middle of the screen work area.

    ``parent`` is accepted for call-site compatibility and is not used for
    placement. Borderless overlays are left untouched.
    """
    _ = parent
    try:
        if not _window_exists(window) or getattr(window, "_skip_auto_center", False):
            return
        if _window_is_borderless(window):
            return

        window.update_idletasks()
        width, height = _window_size(window)
        if width <= 1 or height <= 1:
            return
        left, top, area_width, area_height = _screen_work_area(window)
        x = left + max(0, (area_width - width) // 2)
        y = top + max(0, (area_height - height) // 2)
        x = max(left, min(x, left + max(area_width - width, 0)))
        y = max(top, min(y, top + max(area_height - height, 0)))
        window.geometry(f"+{x}+{y}")
    except Exception:
        pass


try:
    install_window_icon_hook()
except Exception:
    pass
