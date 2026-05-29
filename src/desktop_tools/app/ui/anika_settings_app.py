"""Anika break-reminder settings (Tools menu) — Media Downloader hub styling."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

try:
    from desktop_tools.app.app_windowing import create_hidden_root, cleanup_hidden_root
    from desktop_tools.shared.resources import apply_window_icon, center_window
    from desktop_tools.app.config.runtime_flags import get_tool_theme
    from desktop_tools.app.services.anika_config import (
        MAX_BREAK_INTERVAL_MINS,
        MAX_BREAK_STAY_SECS,
        MIN_BREAK_INTERVAL_MINS,
        MIN_BREAK_STAY_SECS,
        get_break_settings,
        save_break_settings,
    )
except Exception:
    from app_windowing import create_hidden_root, cleanup_hidden_root
    from desktop_tools.shared.resources import apply_window_icon, center_window
    from desktop_tools.app.config.runtime_flags import get_tool_theme
    from desktop_tools.app.services.anika_config import (
        MAX_BREAK_INTERVAL_MINS,
        MAX_BREAK_STAY_SECS,
        MIN_BREAK_INTERVAL_MINS,
        MIN_BREAK_STAY_SECS,
        get_break_settings,
        save_break_settings,
    )

HUB_THEME_DEFAULTS = {
    "bg": "#ffffff",
    "fg": "#1a1a1a",
    "primary": "#2196F3",
    "secondary": "#1565C0",
    "success": "#2E7D32",
    "error": "#D32F2F",
    "warning": "#F57F17",
    "gray": "#424242",
    "light_gray": "#ECEFF1",
    "border": "#90A4AE",
}
HUB = get_tool_theme("media_downloader", HUB_THEME_DEFAULTS)

THEME = {
    "PRIMARY_BG": HUB["bg"],
    "SURFACE_BG": HUB["light_gray"],
    "CARD_BG": "#FAFAFA",
    "BORDER": HUB["border"],
    "ACCENT": HUB["primary"],
    "ACCENT_HOVER": HUB["secondary"],
    "TEXT_MAIN": HUB["fg"],
    "TEXT_MUTED": HUB["gray"],
    "BTN_SECONDARY_BG": "#E3F2FD",
    "BTN_SECONDARY_TEXT": "#0D47A1",
    "SUCCESS": HUB["success"],
    "DANGER": HUB["error"],
}

_settings_window: tk.Toplevel | None = None
DEFAULT_INTERVAL_FALLBACK = 30


def _configure_ttk_styles(root: tk.Misc) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(
        "Hub.Horizontal.TScale",
        background=THEME["CARD_BG"],
        troughcolor="#B0BEC5",
        bordercolor=THEME["BORDER"],
        lightcolor=THEME["ACCENT"],
        darkcolor=THEME["ACCENT"],
    )
    style.map(
        "Hub.Horizontal.TScale",
        background=[("active", THEME["ACCENT"])],
    )


class AnikaBreakSettingsWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc | None = None):
        super().__init__(parent)
        self._parent_window = parent
        self.title("Anika — Break Reminder")
        self.configure(bg=THEME["PRIMARY_BG"])
        self.geometry("520x480")
        self.resizable(False, False)
        apply_window_icon(self)
        _configure_ttk_styles(self)

        enabled, interval_mins, stay_secs = get_break_settings()
        self.enabled_var = tk.BooleanVar(value=enabled)
        self.interval_var = tk.IntVar(value=interval_mins if enabled else DEFAULT_INTERVAL_FALLBACK)
        self.stay_var = tk.IntVar(value=stay_secs)

        self._build_ui()
        self.interval_scale.set(self.interval_var.get())
        self.stay_scale.set(self.stay_var.get())
        self._sync_controls()
        self.protocol("WM_DELETE_WINDOW", self._close)
        if parent is not None and parent.winfo_exists():
            self.transient(parent)
            self.after_idle(lambda: center_window(self, parent))
        else:
            self.after_idle(lambda: center_window(self))
        self.lift()
        self.focus_force()

    def _build_ui(self) -> None:
        header = tk.Frame(
            self,
            bg=THEME["SURFACE_BG"],
            highlightbackground=THEME["BORDER"],
            highlightthickness=1,
        )
        header.pack(fill="x", padx=16, pady=(16, 10))

        tk.Label(
            header,
            text="Break reminder",
            font=("Segoe UI", 15, "bold"),
            fg=THEME["TEXT_MAIN"],
            bg=THEME["SURFACE_BG"],
        ).pack(anchor="w", padx=14, pady=(12, 4))
        tk.Label(
            header,
            text="Set how often Anika reminds you to take a break and how long\n"
            "she stays on screen before going away automatically.",
            font=("Segoe UI", 11),
            fg=THEME["TEXT_MUTED"],
            bg=THEME["SURFACE_BG"],
            justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 12))

        body = tk.Frame(self, bg=THEME["PRIMARY_BG"])
        body.pack(fill="both", expand=True, padx=16, pady=4)

        tk.Checkbutton(
            body,
            text="Enable break reminders",
            variable=self.enabled_var,
            command=self._sync_controls,
            font=("Segoe UI", 12, "bold"),
            fg=THEME["TEXT_MAIN"],
            bg=THEME["PRIMARY_BG"],
            activebackground=THEME["PRIMARY_BG"],
            activeforeground=THEME["TEXT_MAIN"],
            selectcolor="#ffffff",
            highlightthickness=0,
        ).pack(anchor="w", pady=(0, 12))

        self.interval_card = self._card(body, "Remind me after (minutes)")
        self.interval_label = tk.Label(
            self.interval_card,
            text="",
            font=("Segoe UI", 12, "bold"),
            fg=THEME["ACCENT"],
            bg=THEME["CARD_BG"],
        )
        self.interval_label.pack(anchor="w", padx=12, pady=(10, 4))
        self.interval_scale = ttk.Scale(
            self.interval_card,
            from_=MIN_BREAK_INTERVAL_MINS,
            to=MAX_BREAK_INTERVAL_MINS,
            orient="horizontal",
            style="Hub.Horizontal.TScale",
            command=self._on_interval_scale,
        )
        self.interval_scale.pack(fill="x", padx=12, pady=(0, 8))

        self.stay_card = self._card(body, "Stay on screen before auto-dismiss (seconds)")
        self.stay_label = tk.Label(
            self.stay_card,
            text="",
            font=("Segoe UI", 12, "bold"),
            fg=THEME["ACCENT"],
            bg=THEME["CARD_BG"],
        )
        self.stay_label.pack(anchor="w", padx=12, pady=(10, 4))
        self.stay_scale = ttk.Scale(
            self.stay_card,
            from_=MIN_BREAK_STAY_SECS,
            to=MAX_BREAK_STAY_SECS,
            orient="horizontal",
            style="Hub.Horizontal.TScale",
            command=self._on_stay_scale,
        )
        self.stay_scale.pack(fill="x", padx=12, pady=(0, 10))

        tk.Label(
            body,
            text="Tip: Open Tools → Anika to configure your desktop assistant (size, effects, actions). "
            "Anika picks up saved break timing within about 30 seconds.",
            font=("Segoe UI", 10),
            fg=THEME["TEXT_MUTED"],
            bg=THEME["PRIMARY_BG"],
            wraplength=460,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        actions = tk.Frame(self, bg=THEME["PRIMARY_BG"])
        actions.pack(fill="x", padx=16, pady=(12, 16))
        tk.Button(
            actions,
            text="Cancel",
            command=self._close,
            font=("Segoe UI", 11, "bold"),
            bg=THEME["BTN_SECONDARY_BG"],
            fg=THEME["BTN_SECONDARY_TEXT"],
            activebackground=THEME["SURFACE_BG"],
            activeforeground=THEME["BTN_SECONDARY_TEXT"],
            relief="solid",
            bd=1,
            highlightbackground=THEME["ACCENT"],
            highlightcolor=THEME["ACCENT"],
            padx=18,
            pady=8,
            cursor="hand2",
        ).pack(side="right", padx=(8, 0))
        tk.Button(
            actions,
            text="Save",
            command=self._save,
            font=("Segoe UI", 11, "bold"),
            bg=THEME["ACCENT"],
            fg="#ffffff",
            activebackground=THEME["ACCENT_HOVER"],
            activeforeground="#ffffff",
            relief="flat",
            padx=22,
            pady=8,
            cursor="hand2",
        ).pack(side="right")

    def _card(self, parent: tk.Misc, title: str) -> tk.Frame:
        tk.Label(
            parent,
            text=title,
            font=("Segoe UI", 11, "bold"),
            fg=THEME["TEXT_MAIN"],
            bg=THEME["PRIMARY_BG"],
        ).pack(anchor="w", pady=(0, 4))
        frame = tk.Frame(
            parent,
            bg=THEME["CARD_BG"],
            highlightbackground=THEME["BORDER"],
            highlightthickness=1,
        )
        frame.pack(fill="x", pady=(0, 10))
        return frame

    def _sync_controls(self) -> None:
        enabled = self.enabled_var.get()
        state = "normal" if enabled else "disabled"
        self.interval_scale.configure(state=state)
        self.stay_scale.configure(state=state)
        if enabled and self.interval_var.get() < MIN_BREAK_INTERVAL_MINS:
            self.interval_var.set(DEFAULT_INTERVAL_FALLBACK)
        self._refresh_labels()

    def _refresh_labels(self) -> None:
        self.interval_label.configure(text=f"Every {int(self.interval_var.get())} minutes")
        self.stay_label.configure(text=f"Visible for {int(self.stay_var.get())} seconds")

    def _on_interval_scale(self, _value: str) -> None:
        self.interval_var.set(int(float(_value)))
        self._refresh_labels()

    def _on_stay_scale(self, _value: str) -> None:
        self.stay_var.set(int(float(_value)))
        self._refresh_labels()

    def _save(self) -> None:
        try:
            save_break_settings(
                enabled=self.enabled_var.get(),
                interval_mins=int(self.interval_var.get()),
                stay_secs=int(self.stay_var.get()),
            )
        except Exception as exc:
            messagebox.showerror("Anika Settings", f"Could not save settings:\n{exc}", parent=self)
            return
        messagebox.showinfo("Anika Settings", "Break reminder settings saved.", parent=self)
        self._close()

    def _close(self) -> None:
        global _settings_window
        try:
            self.destroy()
        except Exception:
            pass
        if _settings_window is self:
            _settings_window = None


def force_close_anika_settings_if_open() -> None:
    """Close break-settings without prompting (hub shutdown)."""
    global _settings_window
    window = _settings_window
    if window is None:
        return
    try:
        if window.winfo_exists():
            window.destroy()
    except Exception:
        pass
    _settings_window = None


def open_anika_settings(parent: tk.Misc | None = None):
    """Open break reminder settings as a singleton window."""
    global _settings_window

    if _settings_window is not None and _settings_window.winfo_exists():
        _settings_window.lift()
        _settings_window.focus_force()
        return _settings_window

    host, hidden_root = create_hidden_root(parent)
    _settings_window = AnikaBreakSettingsWindow(parent=host)
    if hidden_root is not None:
        _settings_window.bind("<Destroy>", lambda _event: cleanup_hidden_root(hidden_root), add="+")
    return _settings_window
