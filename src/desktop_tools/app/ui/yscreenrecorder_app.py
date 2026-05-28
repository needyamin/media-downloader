"""YScreenRecorder overlay recorder with YScreenshot-style selection UI."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from collections import deque
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageTk

try:
    import pystray
    from pystray import MenuItem as tray_item
except Exception:
    pystray = None
    tray_item = None

try:
    from desktop_tools.app.app_windowing import cleanup_hidden_root, create_hidden_root, ensure_src_on_path
except Exception:
    from app_windowing import cleanup_hidden_root, create_hidden_root, ensure_src_on_path

SRC_DIR = ensure_src_on_path(__file__)

from desktop_tools.shared.ffmpeg import ensure_managed_ffmpeg, update_managed_ffmpeg_if_needed
from desktop_tools.shared.capture_support import capture_desktop_snapshot, get_linux_display_name, is_linux_wayland, is_linux_x11
from desktop_tools.shared.resources import apply_window_icon
from desktop_tools.app.config.runtime_flags import SCREEN_RECORDER_OUTPUT_DIRNAME, get_tool_theme
from desktop_tools.app.platform.hotkeys import (
    WM_HOTKEY,
    WM_QUIT,
    YSCREENRECORDER_FINISH_HOTKEY_ID,
    YSCREENRECORDER_FINISH_HOTKEY_LABEL,
    YSCREENRECORDER_FINISH_HOTKEY_MODIFIERS,
    YSCREENRECORDER_FINISH_HOTKEY_VK,
    YSCREENRECORDER_PAUSE_HOTKEY_ID,
    YSCREENRECORDER_PAUSE_HOTKEY_LABEL,
    YSCREENRECORDER_PAUSE_HOTKEY_MODIFIERS,
    YSCREENRECORDER_PAUSE_HOTKEY_VK,
)

IS_WINDOWS = os.name == "nt"
IS_LINUX = sys.platform.startswith("linux")
SCREENRECORDER_THEME_DEFAULTS = {
    "TEXT_MAIN": "#F8FAFC",
    "TEXT_MUTED": "#94A3B8",
    "TEXT_SOFT": "#7F91AB",
    "PANEL_BG": "#0F172A",
    "PANEL_ALT": "#132238",
    "PANEL_CHIP": "#172235",
    "PANEL_BORDER": "#2B405E",
    "ACCENT": "#38BDF8",
    "SUCCESS": "#22C55E",
    "DANGER": "#F43F5E",
}
SCREENRECORDER_THEME = get_tool_theme("screen_recorder", SCREENRECORDER_THEME_DEFAULTS)
TEXT_MAIN = SCREENRECORDER_THEME["TEXT_MAIN"]
TEXT_MUTED = SCREENRECORDER_THEME["TEXT_MUTED"]
TEXT_SOFT = SCREENRECORDER_THEME["TEXT_SOFT"]
PANEL_BG = SCREENRECORDER_THEME["PANEL_BG"]
PANEL_ALT = SCREENRECORDER_THEME["PANEL_ALT"]
PANEL_CHIP = SCREENRECORDER_THEME["PANEL_CHIP"]
PANEL_BORDER = SCREENRECORDER_THEME["PANEL_BORDER"]
ACCENT = SCREENRECORDER_THEME["ACCENT"]
SUCCESS = SCREENRECORDER_THEME["SUCCESS"]
DANGER = SCREENRECORDER_THEME["DANGER"]

yscreenrecorder_window = None
last_recording_path: Path | None = None


def _default_recording_dir() -> Path:
    """Return a writable default directory for recordings."""
    candidates = [
        Path.home() / "Videos",
        Path.home() / "Downloads",
        Path.home(),
    ]
    for base in candidates:
        try:
            target = base / SCREEN_RECORDER_OUTPUT_DIRNAME
            target.mkdir(parents=True, exist_ok=True)
            return target
        except Exception:
            continue
    target = Path.cwd() / SCREEN_RECORDER_OUTPUT_DIRNAME
    target.mkdir(parents=True, exist_ok=True)
    return target


def _open_path(path: Path) -> None:
    """Open a file or folder in the system shell."""
    if sys.platform.startswith("win"):
        resolved_path = path.resolve()
        try:
            os.startfile(str(resolved_path))
        except OSError:
            if resolved_path.is_dir():
                subprocess.Popen(["explorer", str(resolved_path)])
            else:
                subprocess.Popen(["explorer", "/select,", str(resolved_path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])

class YScreenRecorderOverlay(tk.Toplevel):
    """Overlay-based recorder with transparent area selection and bottom controls."""

    def __init__(self, parent=None):
        parent, self._standalone_root = create_hidden_root(parent)

        super().__init__(parent)
        self.parent_window = parent if isinstance(parent, (tk.Tk, tk.Toplevel)) else None

        self.base_image, self.virtual_x, self.virtual_y, self.screen_width, self.screen_height = self._capture_screen()
        self.dimmed_image = Image.blend(
            self.base_image,
            Image.new("RGBA", self.base_image.size, (0, 0, 0, 255)),
            0.40,
        )

        self.background_photo = ImageTk.PhotoImage(self.dimmed_image)
        self.selection_photo = None
        self.selection_image_item = None
        self.selection_border_item = None
        self.selection_label_item = None
        self.selection_handles = []

        self.capture_mode = "region"
        self.selection_box = None
        self.selection_anchor = None
        self.status_var = tk.StringVar(value="Drag to select an area or use Full Screen.")
        self.summary_var = tk.StringVar(
            value=f"Start recording. Use the tray icon, pause with {YSCREENRECORDER_PAUSE_HOTKEY_LABEL}, finish with {YSCREENRECORDER_FINISH_HOTKEY_LABEL}."
        )
        self.mode_var = tk.StringVar(value="Area mode")
        self.last_recording_var = tk.StringVar(value="Last clip: none")
        self.timer_state_var = tk.StringVar(value="READY")
        self.timer_var = tk.StringVar(value="00:00")

        self.output_dir = _default_recording_dir()
        self.ffmpeg_path = None
        self.ffprobe_path = None
        self.recording_process = None
        self.recording_started_at = None
        self.recording_output_path = None
        self.recording_backend = None
        self.recording_state = "idle"
        self.recording_region = None
        self.recording_segments = []
        self.recording_session_dir = None
        self.recording_elapsed_before_segment = 0.0
        self._post_stop_action = None
        self._stderr_lines = deque(maxlen=40)
        self._poll_job = None
        self._ffmpeg_prepare_thread = None
        self._ffmpeg_prepare_lock = threading.Lock()
        self._record_hotkey_thread = None
        self._record_hotkey_thread_id = None
        self._record_hotkey_registered = False
        self._tray_icon = None
        self._tray_thread = None
        self._overlay_hidden_for_recording = False
        self._parent_hidden_for_recording = False

        self.control_frame = None
        self.control_window = None
        self.record_btn = None
        self.pause_btn = None
        self.finish_btn = None
        self.play_btn = None
        self.full_btn = None
        self.area_btn = None
        self.open_folder_btn = None
        self.close_btn = None
        self.recording_hud = None
        self.recording_hud_pause_btn = None
        self.recording_hud_finish_btn = None
        self.recording_hud_open_folder_btn = None
        self._controls_manual_pos = None
        self._controls_drag_state = None
        self._hud_manual_pos = None
        self._hud_drag_state = None
        self._controls_minimized = False
        self.mini_timer_frame = None
        self.mini_timer_window = None

        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry(f"{self.screen_width}x{self.screen_height}+{self.virtual_x}+{self.virtual_y}")
        self.configure(bg="black")
        apply_window_icon(self, app_id="needyamin.media_downloader")

        self.canvas = tk.Canvas(
            self,
            width=self.screen_width,
            height=self.screen_height,
            bg="black",
            highlightthickness=0,
            bd=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, anchor="nw", image=self.background_photo)

        self._build_hint()
        self._build_controls()
        self._bind_events()
        self._update_last_clip_text()
        self._set_action_states(recording=False)
        self._refresh_overlay()
        self._start_background_ffmpeg_prepare()
        self._start_record_hotkey_listener()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.deiconify()
        self.lift()
        self.focus_force()

    def _capture_screen(self):
        try:
            return capture_desktop_snapshot(self)
        except Exception as exc:
            self.destroy()
            raise RuntimeError(f"Could not capture the screen: {exc}") from exc

    def _build_hint(self):
        self.canvas.create_rectangle(20, 20, 430, 70, fill=PANEL_BG, outline=PANEL_BORDER, width=1)
        self.canvas.create_text(
            38,
            42,
            anchor="w",
            fill=TEXT_MAIN,
            font=("Segoe UI", 11, "bold"),
            text="YScreenRecorder: transparent area with controls below",
        )
        self.canvas.create_text(
            38,
            58,
            anchor="w",
            fill=TEXT_MUTED,
            font=("Segoe UI", 8),
            text="Drag to select an area. Full Screen and Play Last are available below.",
        )

    def _build_controls(self):
        self.control_frame = tk.Frame(
            self.canvas,
            bg=PANEL_BG,
            highlightbackground=PANEL_BORDER,
            highlightthickness=1,
            bd=0,
            padx=10,
            pady=10,
        )

        top_row = tk.Frame(self.control_frame, bg=PANEL_BG)
        top_row.pack(fill="x")

        title_col = tk.Frame(top_row, bg=PANEL_BG)
        title_col.pack(side="left", fill="x", expand=True)
        tk.Label(title_col, text="YScreenRecorder", bg=PANEL_BG, fg=TEXT_MAIN, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(title_col, textvariable=self.status_var, bg=PANEL_BG, fg=TEXT_MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))

        timer_shell = tk.Frame(top_row, bg=PANEL_CHIP, highlightbackground=PANEL_BORDER, highlightthickness=1, bd=0)
        timer_shell.pack(side="right")
        tk.Label(timer_shell, textvariable=self.timer_state_var, bg=PANEL_CHIP, fg=ACCENT, font=("Segoe UI", 7, "bold")).pack(anchor="center", padx=12, pady=(6, 0))
        tk.Label(timer_shell, textvariable=self.timer_var, bg=PANEL_CHIP, fg=TEXT_MAIN, font=("Consolas", 14, "bold")).pack(anchor="center", padx=12, pady=(0, 6))

        tk.Label(
            self.control_frame,
            textvariable=self.summary_var,
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            justify="left",
            wraplength=540,
            anchor="w",
        ).pack(fill="x", pady=(10, 0))

        controls_row = tk.Frame(self.control_frame, bg=PANEL_BG)
        controls_row.pack(fill="x", pady=(12, 0))

        mode_group = tk.Frame(controls_row, bg=PANEL_BG)
        mode_group.pack(side="left", padx=(0, 10))
        mode_buttons = tk.Frame(mode_group, bg=PANEL_BG)
        mode_buttons.pack(anchor="w")
        self.full_btn = self._button(mode_buttons, "Full Screen", self.set_full_screen_mode, variant="secondary")
        self.full_btn.pack(side="left", padx=(0, 6))
        self.area_btn = self._button(mode_buttons, "Select Area", self.prepare_region_mode, variant="secondary")
        self.area_btn.pack(side="left")

        record_group = tk.Frame(controls_row, bg=PANEL_BG)
        record_group.pack(side="left", padx=(0, 10))
        record_buttons = tk.Frame(record_group, bg=PANEL_BG)
        record_buttons.pack(anchor="w")
        self.record_btn = self._button(record_buttons, "Start Recording", self.start_recording, variant="primary")
        self.record_btn.pack(side="left", padx=(0, 6))
        self.pause_btn = self._button(record_buttons, "Pause", self.pause_recording, variant="warning")
        self.pause_btn.pack(side="left", padx=(0, 6))
        self.finish_btn = self._button(record_buttons, "Finish & Save", self.finish_recording, variant="danger")
        self.finish_btn.pack(side="left", padx=(0, 6))
        self.play_btn = self._button(record_buttons, "Play Last", self.play_last_recording, variant="success")
        self.play_btn.pack(side="left")

        utility_group = tk.Frame(controls_row, bg=PANEL_BG)
        utility_group.pack(side="left")
        utility_buttons = tk.Frame(utility_group, bg=PANEL_BG)
        utility_buttons.pack(anchor="w")
        self.open_folder_btn = self._button(utility_buttons, "Open Folder", self.open_output_dir, variant="secondary")
        self.open_folder_btn.pack(side="left", padx=(0, 6))
        self.minimize_btn = self._button(utility_buttons, "Minimize", self._minimize_controls_to_timer, variant="secondary")
        self.minimize_btn.pack(side="left", padx=(0, 6))
        self.close_btn = self._button(utility_buttons, "Close", self.on_close, variant="secondary")
        self.close_btn.pack(side="left")

        self.control_window = self.canvas.create_window(0, 0, anchor="nw", window=self.control_frame)
        self._bind_controls_drag(top_row)
        self._bind_controls_drag(title_col)

    def _info_chip(self, parent, variable):
        chip = tk.Frame(parent, bg=PANEL_CHIP, highlightbackground=PANEL_BORDER, highlightthickness=1, bd=0)
        tk.Label(
            chip,
            textvariable=variable,
            bg=PANEL_CHIP,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=5,
        ).pack()
        return chip

    def _button(self, parent, text, command, *, variant="secondary"):
        # Unified button theme for a cleaner, consistent control bar.
        bg = ACCENT
        active_bg = "#0EA5E9"
        fg = "#FFFFFF"
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=fg,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=7,
            font=("Segoe UI", 8, "bold"),
            highlightthickness=0,
            width=12,
        )

    def _bind_controls_drag(self, widget):
        widget.bind("<ButtonPress-1>", self._start_controls_drag, add="+")
        widget.bind("<B1-Motion>", self._on_controls_drag, add="+")
        widget.bind("<ButtonRelease-1>", self._end_controls_drag, add="+")

    def _start_controls_drag(self, event):
        if self.control_window is None:
            return
        coords = self.canvas.coords(self.control_window)
        if len(coords) < 2:
            return
        self._controls_drag_state = {
            "start_root_x": event.x_root,
            "start_root_y": event.y_root,
            "window_x": float(coords[0]),
            "window_y": float(coords[1]),
        }

    def _on_controls_drag(self, event):
        if not self._controls_drag_state:
            return
        width = self.control_frame.winfo_reqwidth()
        height = self.control_frame.winfo_reqheight()
        dx = event.x_root - self._controls_drag_state["start_root_x"]
        dy = event.y_root - self._controls_drag_state["start_root_y"]
        x = self._controls_drag_state["window_x"] + dx
        y = self._controls_drag_state["window_y"] + dy
        x = max(8, min(x, max(self.screen_width - width - 8, 8)))
        y = max(8, min(y, max(self.screen_height - height - 8, 8)))
        self._controls_manual_pos = (x, y)
        self.canvas.coords(self.control_window, x, y)

    def _end_controls_drag(self, _event):
        self._controls_drag_state = None

    def _ensure_mini_timer(self):
        if self.mini_timer_frame is not None and self.mini_timer_window is not None:
            return

        self.mini_timer_frame = tk.Frame(
            self.canvas,
            bg=PANEL_CHIP,
            highlightbackground=PANEL_BORDER,
            highlightthickness=1,
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
        )
        top = tk.Frame(self.mini_timer_frame, bg=PANEL_CHIP, cursor="hand2")
        top.pack(fill="x")
        tk.Label(top, text="YSR", bg=PANEL_CHIP, fg=TEXT_MUTED, font=("Segoe UI", 7, "bold"), cursor="hand2").pack(side="left")
        tk.Label(top, textvariable=self.timer_state_var, bg=PANEL_CHIP, fg=ACCENT, font=("Segoe UI", 7, "bold"), cursor="hand2").pack(side="right")
        tk.Label(
            self.mini_timer_frame,
            textvariable=self.timer_var,
            bg=PANEL_CHIP,
            fg=TEXT_MAIN,
            font=("Consolas", 12, "bold"),
            cursor="hand2",
        ).pack(anchor="center", pady=(2, 0))
        self.mini_timer_frame.bind("<Button-1>", lambda _e: self._restore_controls_from_timer())
        for child in self.mini_timer_frame.winfo_children():
            child.bind("<Button-1>", lambda _e: self._restore_controls_from_timer())
            for nested in child.winfo_children() if hasattr(child, "winfo_children") else []:
                nested.bind("<Button-1>", lambda _e: self._restore_controls_from_timer())

        self.mini_timer_window = self.canvas.create_window(0, 0, anchor="nw", window=self.mini_timer_frame, state="hidden")

    def _minimize_controls_to_timer(self):
        self._controls_minimized = True
        self._ensure_mini_timer()
        if self.control_window is not None:
            self.canvas.itemconfigure(self.control_window, state="hidden")
        if self.mini_timer_window is not None:
            self.canvas.itemconfigure(self.mini_timer_window, state="normal")
        self._position_mini_timer()

    def _restore_controls_from_timer(self):
        self._controls_minimized = False
        if self.control_window is not None:
            self.canvas.itemconfigure(self.control_window, state="normal")
        if self.mini_timer_window is not None:
            self.canvas.itemconfigure(self.mini_timer_window, state="hidden")
        self._position_controls()

    def _position_mini_timer(self):
        if self.mini_timer_window is None or self.mini_timer_frame is None:
            return
        self.update_idletasks()
        width = self.mini_timer_frame.winfo_reqwidth()
        height = self.mini_timer_frame.winfo_reqheight()
        x = max(8, self.screen_width - width - 16)
        y = max(8, self.screen_height - height - 16)
        self.canvas.coords(self.mini_timer_window, x, y)

    def _bind_events(self):
        self.bind("<Escape>", lambda event: self.on_close())
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    def _set_action_states(self, *, recording):
        paused = self.recording_state == "paused"
        session_active = paused or recording

        if self.record_btn is not None:
            if recording:
                self.record_btn.configure(text="Recording...", state="disabled")
            elif paused:
                self.record_btn.configure(text="Resume Recording", state="normal")
            else:
                self.record_btn.configure(text="Start Recording", state="normal")
        if self.pause_btn is not None:
            self.pause_btn.configure(state="normal" if recording else "disabled")
        if self.finish_btn is not None:
            self.finish_btn.configure(state="normal" if (recording or paused) else "disabled")
        if self.play_btn is not None:
            self.play_btn.configure(
                state="normal" if (not session_active and last_recording_path is not None and last_recording_path.exists()) else "disabled"
            )
        for button in (self.full_btn, self.area_btn):
            if button is not None:
                button.configure(state="disabled" if session_active else "normal")
        if self.recording_hud_pause_btn is not None:
            if recording:
                self.recording_hud_pause_btn.configure(text="Pause", state="normal")
            elif paused:
                self.recording_hud_pause_btn.configure(text="Resume", state="normal")
            else:
                self.recording_hud_pause_btn.configure(text="Pause", state="disabled")
        if self.recording_hud_finish_btn is not None:
            self.recording_hud_finish_btn.configure(state="normal" if (recording or paused) else "disabled")
        if self.recording_hud_open_folder_btn is not None:
            self.recording_hud_open_folder_btn.configure(state="normal")

        self.timer_state_var.set("LIVE" if recording else "PAUSED" if paused else "READY")
        self._sync_tray_icon()
        self._refresh_mode_buttons()
        if recording or paused:
            self._position_recording_hud()

    def _refresh_mode_buttons(self):
        for button, active in (
            (self.full_btn, self.capture_mode == "full"),
            (self.area_btn, self.capture_mode == "region"),
        ):
            if button is None:
                continue
            if active:
                button.configure(bg=ACCENT, fg="#031925", activebackground="#0EA5E9", activeforeground="#031925")
            else:
                button.configure(bg=PANEL_ALT, fg=TEXT_MAIN, activebackground="#1B2D46", activeforeground=TEXT_MAIN)

    def _update_last_clip_text(self):
        if last_recording_path is not None and last_recording_path.exists():
            self.last_recording_var.set(f"Last clip: {last_recording_path.name}")
        else:
            self.last_recording_var.set("Last clip: none")

    def _format_elapsed(self, seconds):
        total_seconds = max(0, int(seconds))
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

    def _current_elapsed_seconds(self):
        elapsed = self.recording_elapsed_before_segment
        if self.recording_process is not None and self.recording_started_at is not None:
            elapsed += max(0.0, time.time() - self.recording_started_at)
        return elapsed

    def _update_timer_display(self):
        self.timer_var.set(self._format_elapsed(self._current_elapsed_seconds()))

    def _reset_recording_session(self, *, reset_timer=True):
        self.recording_state = "idle"
        self.recording_region = None
        self.recording_segments = []
        self.recording_session_dir = None
        self.recording_elapsed_before_segment = 0.0
        self._post_stop_action = None
        self.recording_output_path = None
        self.recording_started_at = None
        self.recording_backend = None
        if reset_timer:
            self.timer_var.set("00:00")

    def _discard_recording_session(self, *, reset_timer=True):
        session_dir = self.recording_session_dir
        self._reset_recording_session(reset_timer=reset_timer)
        if session_dir is not None:
            shutil.rmtree(session_dir, ignore_errors=True)

    def _tray_run_ui_action(self, callback):
        def _runner(icon=None, menu_item=None):
            try:
                self.after(0, callback)
            except Exception:
                pass

        return _runner

    def _create_tray_image(self):
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((6, 6, 58, 58), radius=14, fill=PANEL_BG, outline=ACCENT, width=3)
        draw.rounded_rectangle((18, 16, 46, 40), radius=8, fill=ACCENT)
        draw.ellipse((24, 44, 40, 60), fill=DANGER, outline="#FFFFFF", width=2)
        return image

    def _build_tray_menu(self):
        if pystray is None or tray_item is None:
            return None
        return pystray.Menu(
            tray_item("Show Controls", self._tray_run_ui_action(self.show_controls_from_tray), default=True),
            tray_item("Pause / Resume", self._tray_run_ui_action(self.toggle_pause_resume)),
            tray_item("Finish & Save", self._tray_run_ui_action(self.finish_recording)),
            tray_item("Open Folder", self._tray_run_ui_action(self.open_output_dir)),
        )

    def _ensure_tray_icon(self):
        if pystray is None or self._tray_icon is not None:
            return
        try:
            self._tray_icon = pystray.Icon(
                "yscreenrecorder-session",
                self._create_tray_image(),
                "YScreenRecorder",
                self._build_tray_menu(),
            )
            self._tray_thread = threading.Thread(target=self._tray_icon.run, daemon=True)
            self._tray_thread.start()
        except Exception:
            self._tray_icon = None
            self._tray_thread = None

    def _stop_tray_icon(self):
        icon = self._tray_icon
        self._tray_icon = None
        self._tray_thread = None
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass

    def _sync_tray_icon(self):
        session_active = self.recording_process is not None or self.recording_state == "paused"
        if not session_active:
            self._stop_tray_icon()
            return

        self._ensure_tray_icon()
        if self._tray_icon is not None:
            try:
                if self.recording_process is not None:
                    self._tray_icon.title = "YScreenRecorder: recording"
                else:
                    self._tray_icon.title = "YScreenRecorder: paused"
                self._tray_icon.update_menu()
            except Exception:
                pass

    def _ensure_background_controls_available(self):
        if not IS_WINDOWS:
            return True
        if self._record_hotkey_registered:
            return True
        self._ensure_tray_icon()
        return self._tray_icon is not None

    def _recording_controls_summary(self):
        if self._record_hotkey_registered:
            return f"Use the tray icon, {YSCREENRECORDER_PAUSE_HOTKEY_LABEL}, or {YSCREENRECORDER_FINISH_HOTKEY_LABEL} while recording."
        return "Use the tray icon to pause or finish while recording."

    def _paused_controls_summary(self):
        if self._record_hotkey_registered:
            return (
                f"Resume Recording to continue, or Finish & Save to export the MP4. "
                f"Hotkeys: {YSCREENRECORDER_PAUSE_HOTKEY_LABEL} / {YSCREENRECORDER_FINISH_HOTKEY_LABEL}."
            )
        return "Resume Recording to continue, or Finish & Save to export the MP4."

    def _recording_hud_geometry(self, width, height):
        if self.capture_mode == "region" and self.selection_box is not None:
            x0, y0, x1, y1 = self.selection_box
            x = x0 + max(0, (x1 - x0 - width) // 2)
            x = max(8, min(x, self.screen_width - width - 8))
            y = y1 + 12
            if y + height > self.screen_height - 8:
                y = y0 - height - 12
            if y < 8:
                x = max(8, self.screen_width - width - 18)
                y = max(8, self.screen_height - height - 18)
        else:
            x = max(8, self.screen_width - width - 18)
            y = max(8, self.screen_height - height - 18)
        return f"{width}x{height}+{self.virtual_x + x}+{self.virtual_y + y}"

    def _position_recording_hud(self):
        hud = self.recording_hud
        if hud is None or not hud.winfo_exists():
            return
        hud.update_idletasks()
        width = hud.winfo_reqwidth()
        height = hud.winfo_reqheight()
        if self._hud_manual_pos is not None:
            x, y = self._hud_manual_pos
            min_x = self.virtual_x + 8
            min_y = self.virtual_y + 8
            max_x = self.virtual_x + max(self.screen_width - width - 8, 8)
            max_y = self.virtual_y + max(self.screen_height - height - 8, 8)
            x = max(min_x, min(x, max_x))
            y = max(min_y, min(y, max_y))
            self._hud_manual_pos = (x, y)
            hud.geometry(f"{width}x{height}+{int(x)}+{int(y)}")
        else:
            hud.geometry(self._recording_hud_geometry(width, height))

    def _hide_recording_hud(self):
        hud = self.recording_hud
        self.recording_hud = None
        self.recording_hud_pause_btn = None
        self.recording_hud_finish_btn = None
        self.recording_hud_open_folder_btn = None
        self._hud_manual_pos = None
        self._hud_drag_state = None
        if hud is not None and hud.winfo_exists():
            try:
                hud.destroy()
            except Exception:
                pass

    def _ensure_recording_hud(self):
        hud = self.recording_hud
        if hud is not None and hud.winfo_exists():
            return hud

        hud = tk.Toplevel()
        hud.withdraw()
        hud.title("YScreenRecorder")
        hud.configure(bg=PANEL_BG)
        hud.resizable(False, False)
        hud.attributes("-topmost", True)
        try:
            hud.attributes("-alpha", 0.86)
        except Exception:
            pass
        if IS_WINDOWS:
            try:
                hud.attributes("-toolwindow", True)
            except Exception:
                pass
        apply_window_icon(hud, app_id="needyamin.media_downloader")
        hud.protocol("WM_DELETE_WINDOW", self._hide_recording_hud)

        shell = tk.Frame(
            hud,
            bg=PANEL_BG,
            highlightbackground=PANEL_BORDER,
            highlightthickness=1,
            bd=0,
            padx=10,
            pady=10,
        )
        shell.pack(fill="both", expand=True)

        top_row = tk.Frame(shell, bg=PANEL_BG)
        top_row.pack(fill="x")
        title_col = tk.Frame(top_row, bg=PANEL_BG)
        title_col.pack(side="left", fill="x", expand=True)
        tk.Label(title_col, text="YScreenRecorder", bg=PANEL_BG, fg=TEXT_MAIN, font=("Segoe UI", 11, "bold")).pack(anchor="w")

        timer_shell = tk.Frame(top_row, bg=PANEL_CHIP, highlightbackground=PANEL_BORDER, highlightthickness=1, bd=0)
        timer_shell.pack(side="right")
        tk.Label(timer_shell, textvariable=self.timer_state_var, bg=PANEL_CHIP, fg=ACCENT, font=("Segoe UI", 7, "bold")).pack(
            anchor="center",
            padx=12,
            pady=(6, 0),
        )
        tk.Label(timer_shell, textvariable=self.timer_var, bg=PANEL_CHIP, fg=TEXT_MAIN, font=("Consolas", 14, "bold")).pack(
            anchor="center",
            padx=12,
            pady=(0, 6),
        )

        tk.Label(
            shell,
            textvariable=self.summary_var,
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            justify="left",
            wraplength=360,
        ).pack(anchor="w", fill="x", pady=(10, 0))

        button_row = tk.Frame(shell, bg=PANEL_BG)
        button_row.pack(fill="x", pady=(12, 0))
        self.recording_hud_pause_btn = self._button(button_row, "Pause", self.toggle_pause_resume, variant="warning")
        self.recording_hud_pause_btn.configure(width=10)
        self.recording_hud_pause_btn.pack(side="left", padx=(0, 6))
        self.recording_hud_finish_btn = self._button(button_row, "Finish & Save", self.finish_recording, variant="danger")
        self.recording_hud_finish_btn.configure(width=11)
        self.recording_hud_finish_btn.pack(side="left", padx=(0, 6))
        self.recording_hud_open_folder_btn = self._button(button_row, "Open Folder", self.open_output_dir, variant="secondary")
        self.recording_hud_open_folder_btn.configure(width=10)
        self.recording_hud_open_folder_btn.pack(side="left", padx=(0, 6))
        hide_btn = self._button(button_row, "Hide", self._hide_recording_hud, variant="secondary")
        hide_btn.configure(width=8)
        hide_btn.pack(side="left")

        self._bind_hud_drag(top_row)
        self._bind_hud_drag(title_col)

        self.recording_hud = hud
        self._set_action_states(recording=self.recording_process is not None)
        return hud

    def _show_recording_hud(self):
        hud = self._ensure_recording_hud()
        self._position_recording_hud()
        try:
            hud.deiconify()
            hud.lift()
            hud.focus_force()
        except Exception:
            pass

    def _bind_hud_drag(self, widget):
        widget.bind("<ButtonPress-1>", self._start_hud_drag, add="+")
        widget.bind("<B1-Motion>", self._on_hud_drag, add="+")
        widget.bind("<ButtonRelease-1>", self._end_hud_drag, add="+")

    def _start_hud_drag(self, event):
        hud = self.recording_hud
        if hud is None or not hud.winfo_exists():
            return
        hud.update_idletasks()
        self._hud_drag_state = {
            "start_root_x": event.x_root,
            "start_root_y": event.y_root,
            "window_x": hud.winfo_x(),
            "window_y": hud.winfo_y(),
            "width": hud.winfo_width(),
            "height": hud.winfo_height(),
        }

    def _on_hud_drag(self, event):
        if not self._hud_drag_state:
            return
        dx = event.x_root - self._hud_drag_state["start_root_x"]
        dy = event.y_root - self._hud_drag_state["start_root_y"]
        width = self._hud_drag_state["width"]
        height = self._hud_drag_state["height"]
        x = self._hud_drag_state["window_x"] + dx
        y = self._hud_drag_state["window_y"] + dy
        min_x = self.virtual_x + 8
        min_y = self.virtual_y + 8
        max_x = self.virtual_x + max(self.screen_width - width - 8, 8)
        max_y = self.virtual_y + max(self.screen_height - height - 8, 8)
        x = max(min_x, min(x, max_x))
        y = max(min_y, min(y, max_y))
        self._hud_manual_pos = (x, y)
        self.recording_hud.geometry(f"{width}x{height}+{int(x)}+{int(y)}")

    def _end_hud_drag(self, _event):
        self._hud_drag_state = None

    def show_controls_from_tray(self):
        if self.recording_process is not None:
            self._show_recording_hud()
            return
        self._restore_after_recording()
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.status_var.set("Recorder controls are visible.")
            self.summary_var.set("Use Resume Recording to continue, or Finish & Save to export the MP4.")
            self._refresh_overlay()
        except Exception:
            pass

    def _session_output_dir(self):
        session_dir = self.output_dir / f".ysr-session-{int(time.time() * 1000)}"
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def _segment_output_path(self):
        if self.recording_session_dir is None:
            self.recording_session_dir = self._session_output_dir()
        return self.recording_session_dir / f"segment-{len(self.recording_segments) + 1:03d}.mp4"

    def _write_concat_manifest(self):
        manifest_path = self.recording_session_dir / "segments.txt"
        manifest_lines = [f"file '{segment.resolve().as_posix()}'" for segment in self.recording_segments]
        manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
        return manifest_path

    def _run_concat(self, manifest_path, output_path):
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        copy_result = subprocess.run(
            [
                str(self.ffmpeg_path),
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(manifest_path),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            creationflags=creationflags,
        )
        if copy_result.returncode == 0:
            return

        reencode_result = subprocess.run(
            [
                str(self.ffmpeg_path),
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(manifest_path),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            creationflags=creationflags,
        )
        if reencode_result.returncode != 0:
            error_line = next(
                (
                    line
                    for line in reversed((reencode_result.stderr or copy_result.stderr or "").splitlines())
                    if line.strip()
                ),
                "Could not merge recording parts.",
            )
            raise RuntimeError(error_line)

    def _save_recording_session(self):
        global last_recording_path

        if not self.recording_segments:
            self.status_var.set("Nothing has been recorded yet.")
            self.summary_var.set("Choose a mode, start recording, then finish to save.")
            self._refresh_overlay()
            return False

        final_duration_text = self._format_elapsed(self.recording_elapsed_before_segment)
        output_path = self._output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if len(self.recording_segments) == 1:
                self.recording_segments[0].replace(output_path)
            else:
                if not self._ensure_ffmpeg_ready():
                    raise RuntimeError("FFmpeg is not ready yet.")
                manifest_path = self._write_concat_manifest()
                self._run_concat(manifest_path, output_path)
            last_recording_path = output_path
        except Exception as exc:
            self.recording_state = "paused"
            self.status_var.set(f"Could not save recording: {exc}")
            self.summary_var.set("Resume recording or try Finish & Save again.")
            self._refresh_overlay()
            return False

        self.status_var.set(f"Recording saved to {output_path.name}")
        self.summary_var.set("MP4 ready. Play Last or Open Folder to review it.")
        self._discard_recording_session(reset_timer=False)
        self.timer_var.set(final_duration_text)
        self._refresh_overlay()
        self.after(0, self.open_output_dir)
        return True

    def _point(self, event):
        return (
            max(0, min(int(event.x), self.screen_width - 1)),
            max(0, min(int(event.y), self.screen_height - 1)),
        )

    def _normalize_box(self, start, end, minimum_size=12):
        x0 = min(start[0], end[0])
        y0 = min(start[1], end[1])
        x1 = max(start[0], end[0])
        y1 = max(start[1], end[1])
        if x1 - x0 < minimum_size or y1 - y0 < minimum_size:
            return None
        return (x0, y0, x1, y1)

    def _clear_selection_items(self):
        for name in ("selection_image_item", "selection_border_item", "selection_label_item"):
            item = getattr(self, name)
            if item is not None:
                self.canvas.delete(item)
                setattr(self, name, None)
        while self.selection_handles:
            self.canvas.delete(self.selection_handles.pop())
        self.selection_photo = None

    def _refresh_overlay(self):
        self._clear_selection_items()

        if self.selection_box is not None:
            x0, y0, x1, y1 = self.selection_box
            crop = self.base_image.crop((x0, y0, x1, y1))
            self.selection_photo = ImageTk.PhotoImage(crop)
            self.selection_image_item = self.canvas.create_image(x0, y0, anchor="nw", image=self.selection_photo)
            self.selection_border_item = self.canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                outline=ACCENT,
                width=2,
                dash=(8, 4),
            )
            mode_label = "Full Screen" if self.capture_mode == "full" else f"{x1 - x0} x {y1 - y0}"
            self.selection_label_item = self.canvas.create_text(
                x0 + 10,
                max(16, y0 - 10),
                anchor="sw",
                fill=TEXT_MAIN,
                font=("Segoe UI", 10, "bold"),
                text=f"{mode_label} • MP4",
            )

            for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
                handle = self.canvas.create_rectangle(
                    cx - 3,
                    cy - 3,
                    cx + 3,
                    cy + 3,
                    fill="white",
                    outline=ACCENT,
                    width=1,
                )
                self.selection_handles.append(handle)

        if self.capture_mode == "full":
            self.mode_var.set("Full Screen")
        elif self.selection_box is not None:
            x0, y0, x1, y1 = self.selection_box
            self.mode_var.set(f"Area {x1 - x0} x {y1 - y0}")
        else:
            self.mode_var.set("Area mode")

        if self._controls_minimized:
            self._position_mini_timer()
        else:
            self._position_controls()
        self._set_action_states(recording=self.recording_process is not None)
        self._update_last_clip_text()

    def _position_controls(self):
        if self._controls_minimized and self.control_window is not None:
            self.canvas.itemconfigure(self.control_window, state="hidden")
            return
        self.update_idletasks()
        width = self.control_frame.winfo_reqwidth()
        height = self.control_frame.winfo_reqheight()
        if self._controls_manual_pos is not None:
            x, y = self._controls_manual_pos
            x = max(8, min(x, max(self.screen_width - width - 8, 8)))
            y = max(8, min(y, max(self.screen_height - height - 8, 8)))
            self._controls_manual_pos = (x, y)
        else:
            x = max(8, (self.screen_width - width) // 2)
            y = max(8, self.screen_height - height - 18)
        self.canvas.coords(self.control_window, x, y)

    def prepare_region_mode(self):
        if self.recording_process is not None or self.recording_state == "paused":
            return
        self.capture_mode = "region"
        self.selection_box = None
        self.status_var.set("Drag to select the recording area.")
        self.summary_var.set("Release the mouse to lock the area, then click Start Recording.")
        self._refresh_overlay()

    def set_full_screen_mode(self):
        if self.recording_process is not None or self.recording_state == "paused":
            return
        self.capture_mode = "full"
        self.selection_box = (0, 0, self.screen_width, self.screen_height)
        self.status_var.set("Full screen is selected for recording.")
        self.summary_var.set("Click Start Recording to begin a full-screen session.")
        self._refresh_overlay()

    def _record_region(self):
        if self.capture_mode == "full":
            return {
                "x": self.virtual_x,
                "y": self.virtual_y,
                "width": self.screen_width,
                "height": self.screen_height,
            }
        if self.selection_box is None:
            return None
        x0, y0, x1, y1 = self.selection_box
        return {
            "x": self.virtual_x + x0,
            "y": self.virtual_y + y0,
            "width": x1 - x0,
            "height": y1 - y0,
        }

    def _normalized_region(self, region):
        width = int(region["width"])
        height = int(region["height"])
        if width % 2:
            width -= 1
        if height % 2:
            height -= 1
        if width < 2 or height < 2:
            raise ValueError("Selected area is too small to record.")
        return {
            "x": int(region["x"]),
            "y": int(region["y"]),
            "width": width,
            "height": height,
        }

    def _output_path(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir / f"yscreenrecorder-{time.strftime('%Y%m%d-%H%M%S')}.mp4"

    def _background_prepare_ffmpeg(self):
        try:
            ffmpeg_path, ffprobe_path, _updated = update_managed_ffmpeg_if_needed()
            self.ffmpeg_path = ffmpeg_path
            self.ffprobe_path = ffprobe_path
        except Exception:
            self.ffmpeg_path = None
            self.ffprobe_path = None

    def _start_background_ffmpeg_prepare(self):
        with self._ffmpeg_prepare_lock:
            if self._ffmpeg_prepare_thread is not None and self._ffmpeg_prepare_thread.is_alive():
                return
            self._ffmpeg_prepare_thread = threading.Thread(target=self._background_prepare_ffmpeg, daemon=True)
            self._ffmpeg_prepare_thread.start()

    def _ensure_ffmpeg_ready(self):
        if self.ffmpeg_path and Path(self.ffmpeg_path).exists():
            return True
        ffmpeg_path, ffprobe_path = ensure_managed_ffmpeg()
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        return bool(ffmpeg_path and ffprobe_path)

    def _build_capture_attempts(self, region, output_path):
        common_output_args = [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        if IS_WINDOWS:
            return [
                (
                    "Desktop Duplication",
                    [
                        str(self.ffmpeg_path),
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        (
                            "ddagrab="
                            f"framerate=30:draw_mouse=1:video_size={region['width']}x{region['height']}:"
                            f"offset_x={region['x']}:offset_y={region['y']}"
                        ),
                        "-vf",
                        "hwdownload,format=bgra,format=yuv420p",
                        *common_output_args,
                    ],
                ),
                (
                    "GDI Capture",
                    [
                        str(self.ffmpeg_path),
                        "-y",
                        "-f",
                        "gdigrab",
                        "-draw_mouse",
                        "1",
                        "-framerate",
                        "30",
                        "-offset_x",
                        str(region["x"]),
                        "-offset_y",
                        str(region["y"]),
                        "-video_size",
                        f"{region['width']}x{region['height']}",
                        "-i",
                        "desktop",
                        *common_output_args,
                    ],
                ),
            ]

        if IS_LINUX and is_linux_x11():
            display_name = get_linux_display_name()
            if not display_name:
                return []
            return [
                (
                    "X11 Screen Capture",
                    [
                        str(self.ffmpeg_path),
                        "-y",
                        "-f",
                        "x11grab",
                        "-draw_mouse",
                        "1",
                        "-framerate",
                        "30",
                        "-video_size",
                        f"{region['width']}x{region['height']}",
                        "-i",
                        f"{display_name}+{region['x']},{region['y']}",
                        *common_output_args,
                    ],
                )
            ]

        return []

    def _friendly_capture_error(self, error_line):
        message = (error_line or "").strip()
        lower_message = message.lower()
        if not message:
            if IS_LINUX:
                message = "Linux blocked the recorder before FFmpeg could start."
            else:
                message = "Windows blocked the recorder before FFmpeg could start."
            lower_message = message.lower()

        if IS_LINUX:
            if is_linux_wayland():
                return (
                    "Wayland recording is not available in YScreenRecorder yet. "
                    "Run the app in an X11 session to use in-app recording."
                )
            if not get_linux_display_name():
                return "Linux recording needs an X11 session with DISPLAY available."
            if "cannot open display" in lower_message or "x11grab" in lower_message:
                return (
                    f"{message} Make sure ffmpeg includes x11grab support and that the app is running inside an X11 session."
                )
            return message

        if "access is denied" in lower_message or "0x80070005" in lower_message or "permission denied" in lower_message:
            return (
                "Windows denied screen capture. If the app you want to record is running as Administrator, "
                "run Media Downloader as Administrator too. Privacy or security software can also block capture."
            )
        if "protected" in lower_message or "secure desktop" in lower_message:
            return (
                "Windows protected that screen from capture. UAC prompts, DRM video, and some secure windows "
                "cannot be recorded."
            )
        if "ddagrab" in lower_message or "desktop duplication" in lower_message or "acquirenextframe" in lower_message:
            return (
                f"{message} If this is a protected or elevated window, try recording a normal desktop window "
                "or run Media Downloader with the same privileges as the target app."
            )
        return message

    def _start_capture_process(self, region, output_path):
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        last_error_line = ""

        for backend_name, ffmpeg_cmd in self._build_capture_attempts(region, output_path):
            self._stderr_lines.clear()
            try:
                process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=creationflags,
                )
            except Exception as exc:
                last_error_line = str(exc)
                continue

            time.sleep(0.45)
            if process.poll() is None:
                self.recording_process = process
                self.recording_backend = backend_name
                threading.Thread(target=self._collect_ffmpeg_output, daemon=True).start()
                return

            try:
                _stdout, stderr_output = process.communicate(timeout=1)
            except Exception:
                stderr_output = ""

            for line in (stderr_output or "").splitlines():
                stripped = line.strip()
                if stripped:
                    self._stderr_lines.append(stripped)
            last_error_line = next(
                (line for line in reversed(self._stderr_lines) if line),
                f"{backend_name} could not start recording.",
            )

        self.recording_process = None
        self.recording_backend = None
        raise RuntimeError(self._friendly_capture_error(last_error_line))

    def _run_record_hotkey_listener(self):
        if not IS_WINDOWS:
            return

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._record_hotkey_thread_id = int(kernel32.GetCurrentThreadId())
        message = wintypes.MSG()

        try:
            finish_registered = bool(
                user32.RegisterHotKey(
                    None,
                    YSCREENRECORDER_FINISH_HOTKEY_ID,
                    YSCREENRECORDER_FINISH_HOTKEY_MODIFIERS,
                    YSCREENRECORDER_FINISH_HOTKEY_VK,
                )
            )
            pause_registered = bool(
                user32.RegisterHotKey(
                    None,
                    YSCREENRECORDER_PAUSE_HOTKEY_ID,
                    YSCREENRECORDER_PAUSE_HOTKEY_MODIFIERS,
                    YSCREENRECORDER_PAUSE_HOTKEY_VK,
                )
            )
            if not finish_registered and not pause_registered:
                return
            self._record_hotkey_registered = True
            while True:
                result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result in (0, -1):
                    break
                if message.message != WM_HOTKEY:
                    continue
                hotkey_id = int(message.wParam)
                if hotkey_id == YSCREENRECORDER_FINISH_HOTKEY_ID:
                    self.after(0, self.finish_recording)
                elif hotkey_id == YSCREENRECORDER_PAUSE_HOTKEY_ID:
                    self.after(0, self.toggle_pause_resume)
        finally:
            for hotkey_id in (YSCREENRECORDER_FINISH_HOTKEY_ID, YSCREENRECORDER_PAUSE_HOTKEY_ID):
                try:
                    user32.UnregisterHotKey(None, hotkey_id)
                except Exception:
                    pass
            self._record_hotkey_registered = False
            self._record_hotkey_thread_id = None

    def _start_record_hotkey_listener(self):
        if not IS_WINDOWS:
            return
        if self._record_hotkey_thread is not None and self._record_hotkey_thread.is_alive():
            return
        self._record_hotkey_thread = threading.Thread(target=self._run_record_hotkey_listener, daemon=True)
        self._record_hotkey_thread.start()

    def _stop_record_hotkey_listener(self):
        if not IS_WINDOWS or self._record_hotkey_thread_id is None:
            return
        try:
            ctypes.windll.user32.PostThreadMessageW(self._record_hotkey_thread_id, WM_QUIT, 0, 0)
        except Exception:
            pass

    def _hide_for_recording(self):
        self._overlay_hidden_for_recording = False
        self._parent_hidden_for_recording = False

        try:
            self.withdraw()
            self.update()
            self._overlay_hidden_for_recording = True
        except Exception:
            self._overlay_hidden_for_recording = False

        if (
            self.parent_window is not None
            and self.parent_window is not self._standalone_root
            and self.parent_window.winfo_exists()
            and self.parent_window.winfo_viewable()
        ):
            try:
                self.parent_window.withdraw()
                self._parent_hidden_for_recording = True
            except Exception:
                self._parent_hidden_for_recording = False

        self.update_idletasks()
        time.sleep(0.18)

    def _restore_after_recording(self):
        self._hide_recording_hud()
        if self._parent_hidden_for_recording and self.parent_window is not None and self.parent_window.winfo_exists():
            try:
                self.parent_window.deiconify()
                self.parent_window.lift()
            except Exception:
                pass
        self._parent_hidden_for_recording = False

        if self._overlay_hidden_for_recording:
            try:
                self.deiconify()
                self.lift()
                self.focus_force()
            except Exception:
                pass
        self._overlay_hidden_for_recording = False

    def start_recording(self):
        if self.recording_process is not None:
            return
        if not IS_WINDOWS and not IS_LINUX:
            messagebox.showinfo("YScreenRecorder", "This recorder currently supports Windows and Linux X11 desktop capture.", parent=self)
            return
        if IS_LINUX and is_linux_wayland():
            messagebox.showinfo(
                "YScreenRecorder",
                "Wayland recording is not available in YScreenRecorder yet.\n\nRun the app in an X11 session to use in-app recording.",
                parent=self,
            )
            return
        if IS_LINUX and not is_linux_x11():
            messagebox.showinfo(
                "YScreenRecorder",
                "Linux recording currently requires an X11 session with DISPLAY available.",
                parent=self,
            )
            return

        if self.recording_state == "paused" and self.recording_region is not None:
            region = dict(self.recording_region)
        else:
            region = self._record_region()
            if region is None:
                self.status_var.set("Select an area first.")
                self.summary_var.set("Choose Full Screen or drag a region, then start recording.")
                self._refresh_overlay()
                return
            try:
                region = self._normalized_region(region)
            except ValueError as exc:
                self.status_var.set(str(exc))
                self._refresh_overlay()
                return
            self._discard_recording_session()
            self.recording_region = dict(region)
            self.recording_session_dir = self._session_output_dir()

        if not self._ensure_ffmpeg_ready():
            messagebox.showerror("YScreenRecorder", "FFmpeg is not ready yet. Please try again in a moment.", parent=self)
            return
        if not self._ensure_background_controls_available():
            self.status_var.set("Recorder controls are unavailable.")
            self.summary_var.set(
                "Hotkeys could not start and the tray icon is unavailable. Close apps using the recorder shortcuts and try again."
            )
            self._refresh_overlay()
            return

        try:
            output_path = self._segment_output_path()
            self._hide_recording_hud()
            self._hide_for_recording()
            self._start_capture_process(region, output_path)
        except Exception as exc:
            self.recording_process = None
            self.recording_backend = None
            self._restore_after_recording()
            messagebox.showerror("YScreenRecorder", f"Could not start recording:\n{exc}", parent=self)
            return

        self.recording_state = "recording"
        self.recording_started_at = time.time()
        self.recording_output_path = output_path
        self._post_stop_action = None
        self._update_timer_display()
        self.status_var.set("Recording is live.")
        self.summary_var.set(self._recording_controls_summary())
        self._set_action_states(recording=True)
        self._show_recording_hud()
        self._schedule_poll()

    def _collect_ffmpeg_output(self):
        process = self.recording_process
        if process is None or process.stderr is None:
            return
        try:
            for line in iter(process.stderr.readline, ""):
                if not line:
                    break
                self._stderr_lines.append(line.strip())
        except Exception:
            pass

    def _request_stop_current_segment(self):
        if self.recording_process is None:
            return
        try:
            if self.recording_process.stdin is not None:
                self.recording_process.stdin.write("q\n")
                self.recording_process.stdin.flush()
                return
        except Exception:
            pass
        try:
            self.recording_process.terminate()
        except Exception:
            pass

    def pause_recording(self):
        if self.recording_process is None:
            return
        self._post_stop_action = "pause"
        self.status_var.set("Pausing recording...")
        self.summary_var.set("The current part will stop, then you can resume.")
        self._request_stop_current_segment()

    def finish_recording(self):
        if self.recording_process is not None:
            self._post_stop_action = "finish"
            self.status_var.set("Finishing recording and saving MP4...")
            self.summary_var.set("Please wait while the current part is finalized.")
            self._request_stop_current_segment()
            return

        if self.recording_state == "paused" and self.recording_segments:
            self.status_var.set("Saving recording...")
            self.summary_var.set("Building final MP4 from the recorded parts.")
            self._save_recording_session()

    def stop_recording(self):
        self.finish_recording()

    def toggle_pause_resume(self):
        if self.recording_process is not None:
            self.pause_recording()
        elif self.recording_state == "paused":
            self.start_recording()

    def _schedule_poll(self):
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
        self._poll_job = self.after(350, self._poll_recording_process)

    def _poll_recording_process(self):
        self._poll_job = None
        process = self.recording_process
        if process is None:
            return
        if process.poll() is None:
            self._update_timer_display()
            self._schedule_poll()
            return
        self._finalize_recording(process.poll())

    def _finalize_recording(self, exit_code):
        process = self.recording_process
        output_path = self.recording_output_path
        action = self._post_stop_action or "finish"
        segment_started_at = self.recording_started_at
        self.recording_process = None
        self.recording_started_at = None
        self.recording_output_path = None
        self._post_stop_action = None

        if process is not None:
            try:
                process.wait(timeout=1)
            except Exception:
                pass

        if segment_started_at is not None:
            self.recording_elapsed_before_segment += max(0.0, time.time() - segment_started_at)

        self._restore_after_recording()

        if output_path is not None and output_path.exists() and exit_code == 0:
            self.recording_segments.append(output_path)
            self._update_timer_display()
            if action == "pause":
                self.recording_state = "paused"
                self.status_var.set("Recording paused.")
                self.summary_var.set(self._paused_controls_summary())
            else:
                self.recording_state = "paused"
                self.status_var.set("Saving recording...")
                self.summary_var.set("Building final MP4 from the recorded parts.")
                self._save_recording_session()
        else:
            error_line = next((line for line in reversed(self._stderr_lines) if line), "Recording stopped before a file was created.")
            if self.recording_segments:
                self.recording_state = "paused"
                self.status_var.set(error_line)
                self.summary_var.set("Resume recording or finish saving the parts that already exist.")
            else:
                self.status_var.set(error_line)
                self.summary_var.set("Choose a mode and start a new recording.")
                self._discard_recording_session()
        self._refresh_overlay()

    def play_last_recording(self):
        if last_recording_path is None or not last_recording_path.exists():
            messagebox.showinfo("YScreenRecorder", "No recording is available to play yet.", parent=self)
            return
        _open_path(last_recording_path)

    def open_output_dir(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        try:
            _open_path(self.output_dir)
        except Exception as exc:
            messagebox.showerror("YScreenRecorder", f"Could not open the output folder:\n{exc}", parent=self)

    def _on_press(self, event):
        if self.recording_process is not None or self.recording_state == "paused":
            return
        self.capture_mode = "region"
        self.selection_anchor = self._point(event)
        self.selection_box = None
        self.status_var.set("Selecting area...")
        self.summary_var.set("Release the mouse to lock the area, then click Start Recording.")
        self._refresh_overlay()

    def _on_drag(self, event):
        if self.selection_anchor is None or self.recording_process is not None or self.recording_state == "paused":
            return
        point = self._point(event)
        self.selection_box = self._normalize_box(self.selection_anchor, point, minimum_size=2)
        self._refresh_overlay()

    def _on_release(self, event):
        if self.selection_anchor is None or self.recording_process is not None or self.recording_state == "paused":
            return
        point = self._point(event)
        box = self._normalize_box(self.selection_anchor, point)
        self.selection_anchor = None
        self.selection_box = box
        if box is None:
            self.status_var.set("Selection too small. Drag a bigger area.")
        else:
            x0, y0, x1, y1 = box
            self.status_var.set(f"Selected area {x1 - x0} x {y1 - y0}.")
            self.summary_var.set("Click Start Recording. Pause and Finish hotkeys also work while recording.")
        self._refresh_overlay()

    def on_close(self):
        self._controls_minimized = False
        if self.mini_timer_window is not None:
            try:
                self.canvas.delete(self.mini_timer_window)
            except Exception:
                pass
            self.mini_timer_window = None
        self.mini_timer_frame = None
        global yscreenrecorder_window

        if self.recording_process is not None or self.recording_state == "paused":
            choice = messagebox.askyesnocancel(
                "YScreenRecorder",
                "Do you want to finish and save the current recording before closing?\n\nYes = Finish & Save\nNo = Discard current recording\nCancel = Keep recorder open",
                parent=self,
            )
            if choice is None:
                return
            if choice:
                if self.recording_process is not None:
                    self._post_stop_action = "finish"
                    self._request_stop_current_segment()
                    deadline = time.time() + 6
                    while self.recording_process is not None and time.time() < deadline:
                        self.update()
                        time.sleep(0.05)
                    if self.recording_process is not None:
                        try:
                            self.recording_process.terminate()
                        except Exception:
                            pass
                if self.recording_segments:
                    self._save_recording_session()
            else:
                self._discard_recording_session()

        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None

        self._stop_tray_icon()
        self._stop_record_hotkey_listener()
        self._restore_after_recording()
        self.destroy()

        if yscreenrecorder_window is self:
            yscreenrecorder_window = None
        if self._standalone_root is not None:
            cleanup_hidden_root(self._standalone_root)


def open_yscreenrecorder(parent=None):
    """Open YScreenRecorder as an overlay singleton."""
    global yscreenrecorder_window

    if yscreenrecorder_window is not None and yscreenrecorder_window.winfo_exists():
        if yscreenrecorder_window.recording_process is not None:
            yscreenrecorder_window._show_recording_hud()
            return yscreenrecorder_window
        yscreenrecorder_window.deiconify()
        yscreenrecorder_window.lift()
        yscreenrecorder_window.focus_force()
        return yscreenrecorder_window

    yscreenrecorder_window = YScreenRecorderOverlay(parent=parent)
    return yscreenrecorder_window


if __name__ == "__main__":
    app = open_yscreenrecorder()
    app.mainloop()
