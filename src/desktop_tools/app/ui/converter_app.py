import os
import threading
import subprocess
import json
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from concurrent.futures import ThreadPoolExecutor
import time
from pathlib import Path
import sys

try:
    from desktop_tools.app.app_windowing import cleanup_hidden_root, create_hidden_root, ensure_src_on_path
except Exception:
    from app_windowing import cleanup_hidden_root, create_hidden_root, ensure_src_on_path

APP_DIR = Path(__file__).resolve().parent
SRC_DIR = ensure_src_on_path(__file__)

from desktop_tools.shared.resources import apply_window_icon, center_window
from desktop_tools.shared.ffmpeg import ensure_managed_ffmpeg, update_managed_ffmpeg_if_needed
from desktop_tools.app.config.runtime_flags import get_tool_theme

# Colors & Theme
CONVERTER_THEME_DEFAULTS = {
    "PRIMARY_BG": "#020617",
    "SURFACE_BG": "#081121",
    "CARD_BG": "#0B1628",
    "SECTION_BG": "#101C32",
    "INPUT_BG": "#0E1A2E",
    "BORDER": "#22304A",
    "INPUT_BORDER": "#334155",
    "ACCENT": "#38BDF8",
    "ACCENT_BG": "#0EA5E9",
    "ACCENT_SOFT": "#082F49",
    "ACCENT_DANGER": "#F43F5E",
    "SUCCESS": "#22C55E",
    "WARNING": "#F59E0B",
    "TEXT_MAIN": "#F8FAFC",
    "TEXT_MUTED": "#A5B4CC",
    "TEXT_SOFT": "#64748B",
}
CONVERTER_THEME = get_tool_theme("converter", CONVERTER_THEME_DEFAULTS)
PRIMARY_BG = CONVERTER_THEME["PRIMARY_BG"]
SURFACE_BG = CONVERTER_THEME["SURFACE_BG"]
CARD_BG = CONVERTER_THEME["CARD_BG"]
SECTION_BG = CONVERTER_THEME["SECTION_BG"]
INPUT_BG = CONVERTER_THEME["INPUT_BG"]
BORDER = CONVERTER_THEME["BORDER"]
INPUT_BORDER = CONVERTER_THEME["INPUT_BORDER"]
ACCENT = CONVERTER_THEME["ACCENT"]
ACCENT_BG = CONVERTER_THEME["ACCENT_BG"]
ACCENT_SOFT = CONVERTER_THEME["ACCENT_SOFT"]
ACCENT_DANGER = CONVERTER_THEME["ACCENT_DANGER"]
SUCCESS = CONVERTER_THEME["SUCCESS"]
WARNING = CONVERTER_THEME["WARNING"]
TEXT_MAIN = CONVERTER_THEME["TEXT_MAIN"]
TEXT_MUTED = CONVERTER_THEME["TEXT_MUTED"]
TEXT_SOFT = CONVERTER_THEME["TEXT_SOFT"]

converter_window = None

class ConverterApp(tk.Toplevel):
    def __init__(self, parent=None, default_output_dir=None):
        parent, self._standalone_root = create_hidden_root(parent)

        super().__init__(parent)
        self.parent_window = parent if isinstance(parent, (tk.Tk, tk.Toplevel)) else None

        self.title("Video Converter")
        self.geometry("1040x780")
        self.minsize(860, 700)
        self.configure(bg=PRIMARY_BG)
        self.icon_path = apply_window_icon(self, app_id="needyamin.media_downloader")

        # --- Variables ---
        initial_output_dir = default_output_dir or os.path.expanduser("~")
        self.output_dir_var = tk.StringVar(value=initial_output_dir)
        self.status_var = tk.StringVar(value="Ready to add files")
        
        # Advanced options
        self.mode_var = tk.StringVar(value="encode")  # Default to High Quality
        self.encode_crf_var = tk.IntVar(value=18)      # Default 18 (High Quality)
        self.encode_preset_var = tk.StringVar(value="medium")
        self.max_threads_var = tk.IntVar(value=3)
        self.size_profile_var = tk.StringVar(value="Balanced")
        self.resolution_var = tk.StringVar(value="Original")
        self.audio_bitrate_var = tk.StringVar(value="128k")
        self.faststart_var = tk.BooleanVar(value=True)
        self.ffmpeg_path = None
        self.ffprobe_path = None
        self.queue_summary_var = tk.StringVar(value="0 files")
        self.queue_detail_var = tk.StringVar(value="No videos in queue yet")
        self.mode_summary_var = tk.StringVar(value="High Quality")
        self.mode_detail_var = tk.StringVar(value="Re-encode to MP4 for best compatibility")
        self.output_summary_var = tk.StringVar(value=self._format_path_label(self.output_dir_var.get(), fallback="Home"))
        self.output_detail_var = tk.StringVar(value=self._truncate_text(self.output_dir_var.get(), 52))

        # State management
        # self.files map: item_id -> { "path": str, "status": str, "progress": float, "future": Future/None }
        self.files = {} 
        self.executor = None
        self.is_converting = False
        self._shutdown_event = threading.Event()
        self._ffmpeg_prepare_thread = None
        self._ffmpeg_prepare_lock = threading.Lock()
        self._ffmpeg_ready_event = threading.Event()
        self.output_dir_var.trace_add("write", lambda *_: self._refresh_dashboard())

        self._configure_style()
        self._build_ui()
        self._refresh_dashboard()

        # Handle window close gracefully
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after_idle(lambda: center_window(self, self.parent_window if self.parent_window and self.parent_window.winfo_exists() and self.parent_window is not self._standalone_root else None))
        self._start_background_ffmpeg_prepare()

    def _set_status_threadsafe(self, message):
        """Update the status text safely from any thread."""
        message = str(message)
        if threading.current_thread() is threading.main_thread():
            self.status_var.set(message)
        else:
            self.after(0, lambda msg=message: self.status_var.set(msg))

    def _ensure_ffmpeg_ready(self):
        """Resolve the shared FFmpeg binaries managed by the main app."""
        if self.ffmpeg_path and self.ffprobe_path and os.path.isfile(self.ffmpeg_path) and os.path.isfile(self.ffprobe_path):
            self._ffmpeg_ready_event.set()
            return True

        if self._ffmpeg_prepare_thread is not None and self._ffmpeg_prepare_thread.is_alive():
            self._set_status_threadsafe("FFmpeg is being prepared in the background...")
            return False

        ffmpeg_path, ffprobe_path = ensure_managed_ffmpeg(
            logger=self._set_status_threadsafe,
            progress_callback=self._set_status_threadsafe,
        )
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        if ffmpeg_path and ffprobe_path:
            self._ffmpeg_ready_event.set()
            self._set_status_threadsafe("Shared FFmpeg is ready.")
            return True

        self._ffmpeg_ready_event.clear()
        return False

    def _background_prepare_ffmpeg(self):
        """Auto-find, auto-install, and auto-update shared FFmpeg in the background."""
        try:
            self._set_status_threadsafe("Checking shared FFmpeg...")
            ffmpeg_path, ffprobe_path, updated = update_managed_ffmpeg_if_needed(
                logger=self._set_status_threadsafe,
                progress_callback=self._set_status_threadsafe,
            )
            self.ffmpeg_path = ffmpeg_path
            self.ffprobe_path = ffprobe_path

            if ffmpeg_path and ffprobe_path:
                self._ffmpeg_ready_event.set()
                if updated:
                    self._set_status_threadsafe("FFmpeg updated automatically in background.")
                else:
                    self._set_status_threadsafe("Shared FFmpeg is ready.")
            else:
                self._ffmpeg_ready_event.clear()
                self._set_status_threadsafe("FFmpeg is not available yet.")
        except Exception as exc:
            self._ffmpeg_ready_event.clear()
            self._set_status_threadsafe(f"FFmpeg setup failed: {exc}")

    def _start_background_ffmpeg_prepare(self):
        """Start FFmpeg auto-setup without blocking the converter UI."""
        with self._ffmpeg_prepare_lock:
            if self._ffmpeg_prepare_thread is not None and self._ffmpeg_prepare_thread.is_alive():
                return

            self._ffmpeg_prepare_thread = threading.Thread(
                target=self._background_prepare_ffmpeg,
                daemon=True,
            )
            self._ffmpeg_prepare_thread.start()

    def _truncate_text(self, value, max_length=48):
        value = str(value or "")
        if len(value) <= max_length:
            return value
        return f"{value[:max_length - 3]}..."

    def _format_path_label(self, path, fallback="Not set"):
        if not path:
            return fallback
        label = Path(path).name or path
        return self._truncate_text(label, 22)

    def _status_tag(self, status):
        normalized = (status or "").lower()
        if normalized.startswith("ready"):
            return "status_ready"
        if normalized.startswith("queued"):
            return "status_queued"
        if normalized.startswith("converting"):
            return "status_converting"
        if normalized.startswith("done"):
            return "status_done"
        if normalized.startswith("failed"):
            return "status_failed"
        if normalized.startswith("cancelled"):
            return "status_cancelled"
        return "status_default"

    def _create_stat_card(self, parent, column, title, value_var, detail_var):
        shell = ttk.Frame(parent, style="Surface.TFrame", padding=1)
        shell.grid(row=0, column=column, sticky="nsew", padx=(0, 8) if column < 2 else 0)

        card = ttk.Frame(shell, style="Section.TFrame", padding=(14, 12))
        card.pack(fill="both", expand=True)

        ttk.Label(card, text=title, style="MetricLabel.TLabel").pack(anchor="w")
        ttk.Label(card, textvariable=value_var, style="MetricValue.TLabel").pack(anchor="w", pady=(6, 2))
        ttk.Label(card, textvariable=detail_var, style="MetricHint.TLabel", wraplength=180, justify="left").pack(anchor="w")
        return card

    def _refresh_dashboard(self):
        total = len(self.files)
        ready = sum(1 for data in self.files.values() if data["status"] == "Ready")
        active = sum(1 for data in self.files.values() if data["status"] in ("Queued", "Converting..."))
        failed = sum(1 for data in self.files.values() if data["status"] == "Failed")
        done = sum(1 for data in self.files.values() if data["status"] == "Done")

        self.queue_summary_var.set(f"{total} file{'s' if total != 1 else ''}")
        if active:
            self.queue_detail_var.set(f"{active} active in queue, {ready} ready to start")
        elif ready:
            self.queue_detail_var.set(f"{ready} ready to convert")
        elif failed:
            self.queue_detail_var.set(f"{failed} failed item{'s' if failed != 1 else ''} can be retried")
        elif done and total:
            self.queue_detail_var.set("All queued files are complete")
        else:
            self.queue_detail_var.set("No videos in queue yet")

        if self.mode_var.get() == "encode":
            self.mode_summary_var.set("High Quality")
            self.mode_detail_var.set("Re-encode to MP4 for best compatibility")
        else:
            self.mode_summary_var.set("Lossless Copy")
            self.mode_detail_var.set("Fastest route when codecs are already compatible")

        output_dir = self.output_dir_var.get()
        self.output_summary_var.set(self._format_path_label(output_dir, fallback="Home"))
        self.output_detail_var.set(self._truncate_text(output_dir, 52))

    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=PRIMARY_BG)
        style.configure("Surface.TFrame", background=SURFACE_BG, relief="flat")
        style.configure("Panel.TFrame", background=CARD_BG, relief="flat")
        style.configure("Section.TFrame", background=SECTION_BG, relief="flat")

        style.configure(
            "Header.TLabel",
            background=PRIMARY_BG,
            foreground=TEXT_MAIN,
            font=("Segoe UI", 19, "bold"),
        )
        style.configure(
            "SubHeader.TLabel",
            background=PRIMARY_BG,
            foreground=TEXT_MUTED,
            font=("Segoe UI", 10),
        )
        style.configure(
            "SectionTitle.TLabel",
            background=CARD_BG,
            foreground=TEXT_MAIN,
            font=("Segoe UI", 13, "bold"),
        )
        style.configure(
            "SectionBody.TLabel",
            background=CARD_BG,
            foreground=TEXT_MUTED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "FieldLabel.TLabel",
            background=SECTION_BG,
            foreground=TEXT_MAIN,
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "Hint.TLabel",
            background=SECTION_BG,
            foreground=TEXT_MUTED,
            font=("Segoe UI", 8),
        )
        style.configure(
            "Pill.TLabel",
            background=ACCENT_SOFT,
            foreground=ACCENT,
            font=("Segoe UI", 9, "bold"),
            padding=(10, 5),
        )
        style.configure(
            "HeroStatus.TLabel",
            background=SECTION_BG,
            foreground=TEXT_MAIN,
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "MetricLabel.TLabel",
            background=SECTION_BG,
            foreground=TEXT_SOFT,
            font=("Segoe UI", 8, "bold"),
        )
        style.configure(
            "MetricValue.TLabel",
            background=SECTION_BG,
            foreground=TEXT_MAIN,
            font=("Segoe UI", 16, "bold"),
        )
        style.configure(
            "MetricHint.TLabel",
            background=SECTION_BG,
            foreground=TEXT_MUTED,
            font=("Segoe UI", 8),
        )

        style.configure(
            "Modern.TEntry",
            fieldbackground=INPUT_BG,
            foreground=TEXT_MAIN,
            bordercolor=INPUT_BORDER,
            lightcolor=INPUT_BORDER,
            darkcolor=INPUT_BORDER,
            insertcolor=TEXT_MAIN,
            padding=8,
        )
        style.configure(
            "Modern.TCombobox",
            fieldbackground=INPUT_BG,
            background=INPUT_BG,
            foreground=TEXT_MAIN,
            bordercolor=INPUT_BORDER,
            darkcolor=INPUT_BG,
            lightcolor=INPUT_BG,
            arrowcolor=ACCENT,
            padding=6,
        )
        style.map(
            "Modern.TCombobox",
            fieldbackground=[("readonly", INPUT_BG)],
            selectbackground=[("readonly", INPUT_BG)],
            selectforeground=[("readonly", TEXT_MAIN)],
            foreground=[("readonly", TEXT_MAIN)],
        )
        style.configure(
            "Modern.TSpinbox",
            fieldbackground=INPUT_BG,
            foreground=TEXT_MAIN,
            bordercolor=INPUT_BORDER,
            darkcolor=INPUT_BG,
            lightcolor=INPUT_BG,
            arrowcolor=ACCENT,
            padding=6,
        )
        style.configure(
            "Card.TRadiobutton",
            background=SECTION_BG,
            foreground=TEXT_MAIN,
            font=("Segoe UI", 10),
            indicatorcolor=TEXT_MAIN,
        )
        style.map(
            "Card.TRadiobutton",
            indicatorcolor=[("selected", ACCENT)],
        )

        style.configure(
            "Accent.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(10, 8),
            borderwidth=0,
            background=ACCENT_BG,
            foreground="#ffffff"
        )
        style.map(
            "Accent.TButton",
            background=[("active", ACCENT), ("disabled", "#374151")],
            foreground=[("disabled", "#9ca3af")]
        )

        style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(10, 8),
            borderwidth=0,
            background=SECTION_BG,
            foreground=TEXT_MAIN
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#16233A"), ("disabled", "#1E293B")],
            foreground=[("disabled", "#9ca3af")]
        )
        style.configure(
            "Danger.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(10, 8),
            borderwidth=0,
            background=ACCENT_DANGER,
            foreground="#ffffff"
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#fb7185"), ("disabled", "#374151")],
            foreground=[("disabled", "#9ca3af")]
        )

        style.configure(
            "Treeview",
            background=SECTION_BG,
            foreground=TEXT_MAIN,
            fieldbackground=SECTION_BG,
            borderwidth=0,
            rowheight=32,
            font=("Segoe UI", 9)
        )
        style.configure(
            "Treeview.Heading",
            background="#16233A",
            foreground=TEXT_MAIN,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padding=6
        )
        style.map(
            "Treeview",
            background=[("selected", "#16233A")],
            foreground=[("selected", ACCENT)]
        )
        style.configure(
            "Horizontal.TScale",
            background=SECTION_BG,
            troughcolor="#1E293B",
        )
        style.configure(
            "Vertical.TScrollbar",
            background=SECTION_BG,
            troughcolor=PRIMARY_BG,
            borderwidth=0,
            arrowsize=0,
        )

    def _build_ui(self):
        root = ttk.Frame(self, style="TFrame")
        root.pack(fill="both", expand=True, padx=16, pady=16)

        ttk.Label(root, text="Video Converter", style="Header.TLabel").pack(anchor="w")
        self.lbl_global_status = ttk.Label(
            root,
            textvariable=self.status_var,
            style="SubHeader.TLabel",
            wraplength=900,
            justify="left",
        )
        self.lbl_global_status.pack(anchor="w", pady=(2, 10))

        main_frame = ttk.Frame(root, style="TFrame")
        main_frame.pack(fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=6)
        main_frame.grid_columnconfigure(1, weight=4)
        main_frame.grid_rowconfigure(0, weight=1)

        left_shell = ttk.Frame(main_frame, style="Surface.TFrame", padding=1)
        left_shell.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left_panel = ttk.Frame(left_shell, style="Panel.TFrame", padding=(14, 14))
        left_panel.pack(fill="both", expand=True)

        queue_header = ttk.Frame(left_panel, style="Panel.TFrame")
        queue_header.pack(fill="x")
        queue_title = ttk.Frame(queue_header, style="Panel.TFrame")
        queue_title.pack(side="left", fill="x", expand=True)
        ttk.Label(queue_title, text="Conversion Queue", style="SectionTitle.TLabel").pack(anchor="w")
        ttk.Label(queue_header, textvariable=self.queue_summary_var, style="Pill.TLabel").pack(side="right")

        toolbar = ttk.Frame(left_panel, style="Panel.TFrame")
        toolbar.pack(fill="x", pady=(12, 10))

        toolbar_left = ttk.Frame(toolbar, style="Panel.TFrame")
        toolbar_left.pack(side="left")
        ttk.Button(toolbar_left, text="Add Videos", style="Accent.TButton", command=self.add_files).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar_left, text="Remove Selected", style="Secondary.TButton", command=self.remove_selected).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar_left, text="Clear Done", style="Secondary.TButton", command=self.clear_completed).pack(side="left")

        toolbar_right = ttk.Frame(toolbar, style="Panel.TFrame")
        toolbar_right.pack(side="right")
        self.btn_start = ttk.Button(toolbar_right, text="Start Queue", style="Accent.TButton", command=self.start_queue)
        self.btn_start.pack(side="left", padx=(0, 8))
        self.btn_stop = ttk.Button(toolbar_right, text="Stop", style="Danger.TButton", command=self.stop_queue, state="disabled")
        self.btn_stop.pack(side="left")

        tree_shell = ttk.Frame(left_panel, style="Surface.TFrame", padding=1)
        tree_shell.pack(fill="both", expand=True)
        tree_container = ttk.Frame(tree_shell, style="Section.TFrame", padding=1)
        tree_container.pack(fill="both", expand=True)

        columns = ("name", "size", "duration", "status", "progress")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("name", text="File Name")
        self.tree.heading("size", text="Size")
        self.tree.heading("duration", text="Duration")
        self.tree.heading("status", text="Status")
        self.tree.heading("progress", text="Progress")
        self.tree.column("name", width=250, anchor="w")
        self.tree.column("size", width=82, anchor="center")
        self.tree.column("duration", width=82, anchor="center")
        self.tree.column("status", width=120, anchor="center")
        self.tree.column("progress", width=82, anchor="center")
        self.tree.tag_configure("status_ready", foreground=TEXT_MAIN)
        self.tree.tag_configure("status_queued", foreground=WARNING)
        self.tree.tag_configure("status_converting", foreground=ACCENT)
        self.tree.tag_configure("status_done", foreground=SUCCESS)
        self.tree.tag_configure("status_failed", foreground=ACCENT_DANGER)
        self.tree.tag_configure("status_cancelled", foreground=TEXT_SOFT)
        self.tree.tag_configure("status_default", foreground=TEXT_MAIN)

        sb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview, style="Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        right_shell = ttk.Frame(main_frame, style="Surface.TFrame", padding=1)
        right_shell.grid(row=0, column=1, sticky="nsew")
        right_panel = ttk.Frame(right_shell, style="Panel.TFrame", padding=(14, 14))
        right_panel.pack(fill="both", expand=True)

        ttk.Label(right_panel, text="Settings", style="SectionTitle.TLabel").pack(anchor="w", pady=(0, 10))

        output_section = ttk.Frame(right_panel, style="Section.TFrame", padding=(12, 12))
        output_section.pack(fill="x", pady=(0, 8))
        ttk.Label(output_section, text="Output Directory", style="FieldLabel.TLabel").pack(anchor="w")
        dir_frame = ttk.Frame(output_section, style="Section.TFrame")
        dir_frame.pack(fill="x")
        ttk.Entry(dir_frame, textvariable=self.output_dir_var, style="Modern.TEntry").pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(dir_frame, text="Browse", style="Secondary.TButton", command=self.browse_output_dir).pack(side="right")

        mode_section = ttk.Frame(right_panel, style="Section.TFrame", padding=(12, 12))
        mode_section.pack(fill="x", pady=(0, 8))
        mode_header = ttk.Frame(mode_section, style="Section.TFrame")
        mode_header.pack(fill="x")
        ttk.Label(mode_header, text="Conversion Profile", style="FieldLabel.TLabel").pack(side="left")
        ttk.Label(mode_header, textvariable=self.mode_summary_var, style="Pill.TLabel").pack(side="right")

        mode_picker = ttk.Frame(mode_section, style="Section.TFrame")
        mode_picker.pack(fill="x", pady=(6, 4))
        ttk.Radiobutton(
            mode_picker,
            text="High Quality",
            variable=self.mode_var,
            value="encode",
            style="Card.TRadiobutton",
            command=self._update_mode_state,
        ).pack(side="left", padx=(0, 16))
        ttk.Radiobutton(
            mode_picker,
            text="Lossless Copy",
            variable=self.mode_var,
            value="copy",
            style="Card.TRadiobutton",
            command=self._update_mode_state,
        ).pack(side="left")

        ttk.Label(
            mode_section,
            textvariable=self.mode_detail_var,
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(0, 6))

        self.frm_encode = ttk.Frame(mode_section, style="Section.TFrame")
        self.frm_encode.pack(fill="x", pady=(2, 0))
        advanced_row = ttk.Frame(self.frm_encode, style="Section.TFrame")
        advanced_row.pack(fill="x")
        advanced_row.grid_columnconfigure(0, weight=1)
        advanced_row.grid_columnconfigure(1, weight=1)

        quality_box = ttk.Frame(advanced_row, style="Section.TFrame")
        quality_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        quality_header = ttk.Frame(quality_box, style="Section.TFrame")
        quality_header.pack(fill="x")
        ttk.Label(quality_header, text="CRF", style="FieldLabel.TLabel").pack(side="left")
        self.lbl_crf = ttk.Label(quality_header, text="18", style="Hint.TLabel", foreground=ACCENT)
        self.lbl_crf.pack(side="right")
        scale = ttk.Scale(
            quality_box,
            from_=14,
            to=28,
            variable=self.encode_crf_var,
            orient="horizontal",
            command=lambda v: self.lbl_crf.config(text=str(int(float(v)))),
        )
        scale.pack(fill="x", pady=(4, 0))

        preset_box = ttk.Frame(advanced_row, style="Section.TFrame")
        preset_box.grid(row=0, column=1, sticky="ew")
        ttk.Label(preset_box, text="Preset", style="FieldLabel.TLabel").pack(anchor="w")
        presets = ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"]
        cb = ttk.Combobox(
            preset_box,
            textvariable=self.encode_preset_var,
            values=presets,
            state="readonly",
            style="Modern.TCombobox",
        )
        cb.pack(fill="x", pady=(4, 0))

        performance_section = ttk.Frame(right_panel, style="Section.TFrame", padding=(12, 12))
        performance_section.pack(fill="x", pady=(0, 8))
        ttk.Label(performance_section, text="Performance", style="FieldLabel.TLabel").pack(anchor="w")
        ttk.Label(performance_section, text="Threads (Max Concurrent)", style="Hint.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Spinbox(performance_section, from_=1, to=16, textvariable=self.max_threads_var, width=6, style="Modern.TSpinbox").pack(anchor="w")

        reduction_section = ttk.Frame(right_panel, style="Section.TFrame", padding=(12, 12))
        reduction_section.pack(fill="x", pady=(0, 8))
        ttk.Label(reduction_section, text="Size Reduction", style="FieldLabel.TLabel").pack(anchor="w")
        ttk.Label(
            reduction_section,
            text="Use these options to reduce output MB size.",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(0, 6))

        profile_row = ttk.Frame(reduction_section, style="Section.TFrame")
        profile_row.pack(fill="x", pady=(0, 6))
        ttk.Label(profile_row, text="Profile", style="Hint.TLabel").pack(side="left")
        profile_cb = ttk.Combobox(
            profile_row,
            textvariable=self.size_profile_var,
            values=["Balanced", "Smaller File", "Smallest File"],
            state="readonly",
            width=16,
            style="Modern.TCombobox",
        )
        profile_cb.pack(side="right")
        profile_cb.bind("<<ComboboxSelected>>", lambda _e: self._apply_size_profile())

        resolution_row = ttk.Frame(reduction_section, style="Section.TFrame")
        resolution_row.pack(fill="x", pady=(0, 6))
        ttk.Label(resolution_row, text="Max Resolution", style="Hint.TLabel").pack(side="left")
        ttk.Combobox(
            resolution_row,
            textvariable=self.resolution_var,
            values=["Original", "1080p", "720p", "480p"],
            state="readonly",
            width=16,
            style="Modern.TCombobox",
        ).pack(side="right")

        audio_row = ttk.Frame(reduction_section, style="Section.TFrame")
        audio_row.pack(fill="x", pady=(0, 6))
        ttk.Label(audio_row, text="Audio Bitrate", style="Hint.TLabel").pack(side="left")
        ttk.Combobox(
            audio_row,
            textvariable=self.audio_bitrate_var,
            values=["192k", "160k", "128k", "96k", "64k"],
            state="readonly",
            width=16,
            style="Modern.TCombobox",
        ).pack(side="right")

        ttk.Checkbutton(
            reduction_section,
            text="Web optimize (fast start)",
            variable=self.faststart_var,
            style="Card.TCheckbutton",
        ).pack(anchor="w", pady=(2, 0))

        self._apply_size_profile()
        self._update_mode_state()

    def _update_mode_state(self):
        mode = self.mode_var.get()
        if mode == "encode":
            if not self.frm_encode.winfo_manager():
                self.frm_encode.pack(fill="x", pady=(2, 0))
            for child in self.frm_encode.winfo_children():
                try: child.configure(state="normal")
                except: pass
        else:
            self.frm_encode.pack_forget()
            for child in self.frm_encode.winfo_children():
                try: child.configure(state="disabled")
                except: pass
        self._refresh_dashboard()

    def _apply_size_profile(self):
        profile = self.size_profile_var.get()
        if profile == "Smaller File":
            self.mode_var.set("encode")
            self.encode_crf_var.set(22)
            self.encode_preset_var.set("faster")
            self.resolution_var.set("1080p")
            self.audio_bitrate_var.set("128k")
        elif profile == "Smallest File":
            self.mode_var.set("encode")
            self.encode_crf_var.set(26)
            self.encode_preset_var.set("veryfast")
            self.resolution_var.set("720p")
            self.audio_bitrate_var.set("96k")
        else:
            self.encode_crf_var.set(18)
            self.encode_preset_var.set("medium")
            self.resolution_var.set("Original")
            self.audio_bitrate_var.set("160k")
        self.lbl_crf.config(text=str(self.encode_crf_var.get()))
        self._update_mode_state()
                
    # --- Logic ---

    def browse_output_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.output_dir_var.set(d)

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select Video Files",
            filetypes=[("Video Files", "*.mp4;*.mkv;*.avi;*.mov;*.flv;*.ts;*.webm;*.mts;*.m2ts"), ("All Files", "*.*")]
        )
        if not paths:
            return
            
        for path in paths:
            # Avoid duplicates? (Optional: allow for now)
            # Get info
            size_mb = os.path.getsize(path) / (1024 * 1024)
            size_str = f"{size_mb:.1f} MB"
            
            # Use ffprobe for duration? Lazy load it later or do it now?
            # Doing it now might freeze UI if many files. Let's do a placeholder or quick probe separate thread?
            # For simplicity, we'll placeholder duration or get it in worker.
            duration_str = "..."
            
            fname = os.path.basename(path)
            item_id = self.tree.insert("", "end", values=(fname, size_str, duration_str, "Ready", "0%"), tags=("status_ready",))
            
            self.files[item_id] = {
                "path": path,
                "status": "Ready",
                "progress": 0.0,
                "future": None
            }
        
        self.status_var.set(f"Added {len(paths)} files.")
        self._refresh_dashboard()

    def remove_selected(self):
        selected = self.tree.selection()
        for item_id in selected:
            # Don't remove if running?
            if self.files[item_id]["status"] == "Converting...":
                messagebox.showwarning("Busy", "Cannot remove a file that is currently converting.")
                continue
            self.tree.delete(item_id)
            del self.files[item_id]
        self._refresh_dashboard()

    def clear_completed(self):
        to_remove = []
        for item_id, data in self.files.items():
            if data["status"] == "Done":
                to_remove.append(item_id)
        for item_id in to_remove:
            self.tree.delete(item_id)
            del self.files[item_id]
        self._refresh_dashboard()

    def start_queue(self):
        if self.is_converting:
            return

        to_process = [iid for iid, data in self.files.items() if data["status"] in ("Ready", "Failed")]
        if not to_process:
            messagebox.showinfo("Info", "No files ready to convert.")
            return

        if not self._ensure_ffmpeg_ready():
            messagebox.showerror(
                "Error",
                "Shared FFmpeg is still being prepared in the background.\n\nPlease wait a moment and try again.",
            )
            return
            
        out_dir = self.output_dir_var.get()
        if not os.path.isdir(out_dir):
            if messagebox.askyesno("Create Directory", "Output directory does not exist. Create it?"):
                os.makedirs(out_dir, exist_ok=True)
            else:
                return

        self.is_converting = True
        self._shutdown_event.clear()
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.status_var.set("Starting queue...")
        self._refresh_dashboard()

        max_workers = self.max_threads_var.get()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Launch a monitor thread to check when all are done
        threading.Thread(target=self._queue_monitor, args=(to_process,), daemon=True).start()

    def _queue_monitor(self, item_ids):
        futures = []
        for iid in item_ids:
            if self._shutdown_event.is_set():
                break
            
            # Update status to Queued
            self.after(0, self._update_item, iid, "Queued", "0%")
            
            # Submit to pool
            data = self.files[iid]
            # Capture settings NOW
            mode = self.mode_var.get()
            crf = self.encode_crf_var.get()
            preset = self.encode_preset_var.get()
            resolution = self.resolution_var.get()
            audio_bitrate = self.audio_bitrate_var.get()
            faststart = bool(self.faststart_var.get())
            out_dir = self.output_dir_var.get()
            
            f = self.executor.submit(
                self._convert_file,
                iid,
                data["path"],
                out_dir,
                mode,
                crf,
                preset,
                resolution,
                audio_bitrate,
                faststart,
            )
            data["future"] = f
            futures.append(f)
        
        # Wait for all
        for f in futures:
            if f.running() or not f.done():
                try:
                    f.result() # Wait for it
                except Exception:
                    pass
        
        self.executor.shutdown(wait=True)
        self.after(0, self._on_queue_finished)

    def _on_queue_finished(self):
        self.is_converting = False
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.status_var.set("Queue finished.")
        self.executor = None
        self._refresh_dashboard()

    def stop_queue(self):
        if not self.is_converting:
            return
        
        self.status_var.set("Stopping...")
        self._shutdown_event.set()
        self._refresh_dashboard()
        
        # Cancel pending futures
        if self.executor:
            # We can't easily kill running threads in Python without C-extensions or subprocess hacking.
            # But the _convert_file loop checks _shutdown_event.
            pass

    def _update_item(self, item_id, status=None, progress=None):
        vals = list(self.tree.item(item_id, "values"))
        if status is not None:
            self.files[item_id]["status"] = status
            vals[3] = status
        if progress is not None:
            vals[4] = progress
        self.tree.item(item_id, values=vals)
        if status is not None:
            self.tree.item(item_id, tags=(self._status_tag(status),))
            self._refresh_dashboard()

    def _convert_file(self, item_id, input_path, out_dir, mode, crf, preset, resolution, audio_bitrate, faststart):
        # 1. Prepare
        if self._shutdown_event.is_set():
            self.after(0, self._update_item, item_id, "Cancelled", None)
            return

        self.after(0, self._update_item, item_id, "Converting...", "0%")
        
        filename = os.path.basename(input_path)
        base, _ = os.path.splitext(filename)
        out_name = f"{base}.mp4"
        out_path = os.path.join(out_dir, out_name)
        
        # 2. Get Duration (for progress)
        duration_sec = self._get_duration(input_path)
        if duration_sec:
            # Update UI Duration column if missing
            pass # TODO: update duration col
        
        # 3. Build Command
        cmd = [self.ffmpeg_path, "-y", "-i", input_path, "-progress", "pipe:1", "-nostats"]
        
        if mode == "encode":
            cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf)]
            resolution_filters = {
                "1080p": "scale=-2:1080",
                "720p": "scale=-2:720",
                "480p": "scale=-2:480",
            }
            scale_filter = resolution_filters.get(resolution)
            if scale_filter:
                cmd += ["-vf", scale_filter]
            cmd += ["-c:a", "aac", "-b:a", audio_bitrate]
            if faststart:
                cmd += ["-movflags", "+faststart"]
        else:
            cmd += ["-c", "copy"]
            
        cmd.append(out_path)
        
        # 4. Run Process
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
            
            for line in process.stdout:
                if self._shutdown_event.is_set():
                    process.terminate()
                    raise Exception("Cancelled")
                    
                line = line.strip()
                if line.startswith("out_time_ms="):
                    try:
                        ms = int(line.split("=")[1])
                        sec = ms / 1000000.0
                        if duration_sec and duration_sec > 0:
                            pct = (sec / duration_sec) * 100
                            pct_str = f"{pct:.1f}%"
                            self.after(0, self._update_item, item_id, None, pct_str)
                    except: pass
            
            process.wait()
            if process.returncode == 0:
                self.files[item_id]["status"] = "Done"
                self.after(0, self._update_item, item_id, "Done", "100%")
            else:
                 raise Exception(f"Exit code {process.returncode}")

        except Exception as e:
            status = "Cancelled" if "Cancelled" in str(e) else "Failed"
            self.files[item_id]["status"] = status
            self.after(0, self._update_item, item_id, status, "Error")

    def _get_duration(self, path):
        # ffprobe
        if not self.ffprobe_path or not os.path.isfile(self.ffprobe_path):
            if not self._ensure_ffmpeg_ready():
                return None
        ffprobe = self.ffprobe_path
        if not os.path.isfile(ffprobe):
            return None
        try:
            cmd = [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
            res = subprocess.run(cmd, capture_output=True, text=True)
            return float(res.stdout.strip())
        except:
            return None

    def on_close(self):
        global converter_window
        should_close = True
        if self.is_converting:
            if messagebox.askyesno("Exit", "Conversion in progress. Stop and exit?"):
                self.stop_queue()
            else:
                should_close = False

        if not should_close:
            return

        self.destroy()

        if converter_window is self:
            converter_window = None

        if self._standalone_root is not None:
            cleanup_hidden_root(self._standalone_root)


def open_converter_window(parent=None, default_output_dir=None):
    """Open the converter as a centered child window."""
    global converter_window

    if converter_window is not None and converter_window.winfo_exists():
        if default_output_dir:
            converter_window.output_dir_var.set(str(default_output_dir))
        converter_window.deiconify()
        center_window(converter_window, parent)
        converter_window.lift()
        converter_window.focus_force()
        return converter_window

    converter_window = ConverterApp(parent=parent, default_output_dir=default_output_dir)
    if parent is not None and parent.winfo_exists():
        converter_window.transient(parent)
        converter_window.after_idle(lambda: center_window(converter_window, parent))
    return converter_window

if __name__ == "__main__":
    app = open_converter_window()
    app.mainloop()
