"""Apply the Media Downloader app icon to Anika windows."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    src_dir = Path(__file__).resolve().parents[3]
    src_text = str(src_dir)
    if (src_dir / "desktop_tools").is_dir() and src_text not in sys.path:
        sys.path.insert(0, src_text)


def resolve_app_icon_path() -> Path:
    _ensure_src_on_path()
    try:
        from desktop_tools.shared.resources import get_asset_path

        candidate = get_asset_path("needyamin.ico")
        if candidate.exists():
            return candidate
    except Exception:
        pass

    here = Path(__file__).resolve()
    exe_dir = Path(sys.executable).resolve().parent
    argv_dir = Path(sys.argv[0]).resolve().parent if sys.argv and sys.argv[0] else exe_dir
    candidates = [
        here.parents[2] / "app" / "assets" / "needyamin.ico",
        here.parents[1] / "resources" / "needyamin.ico",
        exe_dir / "needyamin.ico",
        exe_dir / "assets" / "needyamin.ico",
        exe_dir / "desktop_tools" / "app" / "assets" / "needyamin.ico",
        argv_dir / "needyamin.ico",
        argv_dir / "assets" / "needyamin.ico",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def apply_app_icon(window) -> Path:
    _ensure_src_on_path()
    try:
        from desktop_tools.shared.resources import apply_window_icon

        return apply_window_icon(window)
    except Exception:
        pass

    icon_path = resolve_app_icon_path()
    if window is None:
        return icon_path
    try:
        if sys.platform.startswith("win"):
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("needyamin.media_downloader")
    except Exception:
        pass
    if icon_path.is_file():
        try:
            from PIL import Image, ImageTk

            photo = ImageTk.PhotoImage(Image.open(icon_path))
            window.iconphoto(True, photo)
            window._shared_icon_photo = photo
        except Exception:
            pass
        try:
            if sys.platform.startswith("win"):
                window.iconbitmap(default=str(icon_path))
            else:
                window.iconbitmap(str(icon_path))
        except Exception:
            try:
                window.iconbitmap(str(icon_path))
            except Exception:
                pass
        try:
            window.after_idle(lambda w=window, path=icon_path: _reapply(w, path))
            window.after(250, lambda w=window, path=icon_path: _reapply(w, path))
        except Exception:
            pass
    return icon_path


def center_app_window(window) -> None:
    """Center an Anika window in the middle of the screen."""
    _ensure_src_on_path()
    try:
        from desktop_tools.shared.resources import center_window

        center_window(window)
        return
    except Exception:
        pass
    try:
        window.update_idletasks()
        width = window.winfo_width() or window.winfo_reqwidth()
        height = window.winfo_height() or window.winfo_reqheight()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        pass


def _reapply(window, icon_path: Path) -> None:
    try:
        if not window.winfo_exists() or not icon_path.is_file():
            return
        window.iconbitmap(str(icon_path))
    except Exception:
        pass


def install_app_icon_hook() -> None:
    _ensure_src_on_path()
    try:
        from desktop_tools.shared.resources import install_window_icon_hook

        install_window_icon_hook()
        return
    except Exception:
        pass

    if getattr(install_app_icon_hook, "_installed", False):
        return
    install_app_icon_hook._installed = True
    try:
        import tkinter as tk

        original = tk.Toplevel.__init__

        def _init(self, *args, **kwargs):
            original(self, *args, **kwargs)
            apply_app_icon(self)
            try:
                self.after_idle(lambda w=self: center_app_window(w))
            except Exception:
                pass

        tk.Toplevel.__init__ = _init
    except Exception:
        pass
    try:
        import customtkinter as ctk

        original_ctk = ctk.CTkToplevel.__init__

        def _ctk_init(self, *args, **kwargs):
            original_ctk(self, *args, **kwargs)
            apply_app_icon(self)
            try:
                self.after_idle(lambda w=self: center_app_window(w))
            except Exception:
                pass

        ctk.CTkToplevel.__init__ = _ctk_init
    except Exception:
        pass
