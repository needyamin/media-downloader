import os
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from pathlib import Path

try:
    from desktop_tools.app.app_windowing import cleanup_hidden_root, create_hidden_root, ensure_src_on_path
except Exception:
    from app_windowing import cleanup_hidden_root, create_hidden_root, ensure_src_on_path

ensure_src_on_path(__file__)

from desktop_tools.shared.resources import apply_window_icon, center_window
from desktop_tools.shared.dependency_progress import DependencyProgressPanel
from desktop_tools.shared.ffmpeg import (
    ensure_managed_ffmpeg,
    find_existing_ffmpeg,
    get_ffmpeg_install_help,
)
from desktop_tools.app.config.runtime_flags import get_tool_theme

CONVERTER_THEME_DEFAULTS = {
    "PRIMARY_BG": "#020617",
    "SURFACE_BG": "#081121",
    "CARD_BG": "#0B1628",
    "SECTION_BG": "#101C32",
    "INPUT_BG": "#0E1A2E",
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

OUTPUT_EXTENSIONS = (".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".ts", ".flv")
QUALITY_OPTIONS = ("Fast copy", "Balanced", "High")
VIDEO_FILETYPES = [
    ("Video files", "*.mp4;*.mkv;*.webm;*.mov;*.avi;*.m4v;*.ts;*.flv;*.wmv;*.mts;*.m2ts"),
    ("All files", "*.*"),
]
WINDOW_WIDTH = 500
WINDOW_HEIGHT = 560
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

converter_window = None


def normalize_output_ext(value: str) -> str:
    ext = str(value or ".mp4").strip().lower()
    if not ext.startswith("."):
        ext = f".{ext}"
    return ext if ext in OUTPUT_EXTENSIONS else ".mp4"


def next_output_path(out_dir: str, input_path: str, ext: str) -> str:
    """Pick an output path that does not overwrite the source file."""
    base = Path(input_path).stem
    candidate = Path(out_dir) / f"{base}{ext}"
    try:
        if candidate.resolve() == Path(input_path).resolve():
            candidate = Path(out_dir) / f"{base}_converted{ext}"
    except OSError:
        candidate = Path(out_dir) / f"{base}_converted{ext}"
    index = 1
    while candidate.exists():
        candidate = Path(out_dir) / f"{base}_{index}{ext}"
        index += 1
    return str(candidate)


def build_convert_command(ffmpeg_path, input_path, output_path, quality):
    """Build an FFmpeg command for container change or re-encode."""
    cmd = [str(ffmpeg_path), "-y", "-hide_banner", "-progress", "pipe:1", "-nostats", "-i", str(input_path)]
    ext = Path(output_path).suffix.lower()
    if quality == "Fast copy":
        cmd += ["-c", "copy"]
        if ext in {".mp4", ".m4v", ".mov"}:
            cmd += ["-movflags", "+faststart"]
    else:
        crf = 18 if quality == "High" else 22
        audio = "192k" if quality == "High" else "128k"
        preset = "medium" if quality == "High" else "faster"
        if ext == ".webm":
            vp9_crf = "30" if quality == "High" else "34"
            cmd += ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", vp9_crf, "-c:a", "libopus", "-b:a", audio]
        else:
            cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-c:a", "aac", "-b:a", audio]
            if ext in {".mp4", ".m4v", ".mov"}:
                cmd += ["-movflags", "+faststart"]
    cmd.append(str(output_path))
    return cmd


class ConverterApp(tk.Toplevel):
    def __init__(self, parent=None, default_output_dir=None, auto_prepare_ffmpeg=True):
        parent, self._standalone_root = create_hidden_root(parent)

        super().__init__(parent)
        self.parent_window = parent if isinstance(parent, (tk.Tk, tk.Toplevel)) else None

        self.title("Video Converter")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.resizable(False, False)
        self.configure(bg=PRIMARY_BG)
        self.icon_path = apply_window_icon(self, app_id="needyamin.media_downloader")

        initial_output_dir = default_output_dir or os.path.expanduser("~")
        self.output_dir_var = tk.StringVar(value=initial_output_dir)
        self.status_var = tk.StringVar(value="Add videos, pick a format, then convert")
        self.dep_var = tk.StringVar(value="")
        self.format_var = tk.StringVar(value=".mp4")
        self.quality_var = tk.StringVar(value="Balanced")
        self.ffmpeg_path = None
        self.ffprobe_path = None
        self.files = {}
        self.is_converting = False
        self._warned_download = False
        self._shutdown_event = threading.Event()
        self._ffmpeg_prepare_thread = None
        self._ffmpeg_prepare_lock = threading.Lock()
        self._ffmpeg_ready_event = threading.Event()

        self._configure_style()
        self._build_ui()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after_idle(lambda: center_window(self, self._center_parent()))
        if auto_prepare_ffmpeg:
            self._start_background_ffmpeg_prepare()

    def _center_parent(self):
        if self.parent_window and self.parent_window.winfo_exists() and self.parent_window is not self._standalone_root:
            return self.parent_window
        return None

    def _set_status_threadsafe(self, message):
        message = str(message)
        if threading.current_thread() is threading.main_thread():
            self.status_var.set(message)
        else:
            self.after(0, lambda msg=message: self.status_var.set(msg))

    def _show_dep_banner(self, message):
        self.dep_var.set(message)
        if not self.dep_banner.winfo_manager():
            self.dep_banner.pack(fill="x", pady=(0, 8), before=self.body)

    def _hide_dep_banner(self):
        self.dep_var.set("")
        if self.dep_banner.winfo_manager():
            self.dep_banner.pack_forget()

    def _ensure_ffmpeg_ready(self):
        if self.ffmpeg_path and self.ffprobe_path and os.path.isfile(self.ffmpeg_path) and os.path.isfile(self.ffprobe_path):
            self._ffmpeg_ready_event.set()
            return True
        self._set_status_threadsafe("Waiting for FFmpeg dependency download...")
        self._start_background_ffmpeg_prepare()
        return False

    def _warn_dependency_download(self):
        if self._warned_download:
            return
        self._warned_download = True
        self._show_dep_banner("Warning: FFmpeg is missing. Downloading this dependency now (one-time).")
        messagebox.showwarning(
            "Dependency download",
            "FFmpeg is missing and required for conversion.\n\n"
            "It will be downloaded automatically now. This is a one-time setup.\n\n"
            + get_ffmpeg_install_help(),
            parent=self,
        )

    def _background_prepare_ffmpeg(self):
        try:
            self._set_status_threadsafe("Checking FFmpeg...")
            ffmpeg_path, ffprobe_path = find_existing_ffmpeg()
            if ffmpeg_path and ffprobe_path:
                self.ffmpeg_path = ffmpeg_path
                self.ffprobe_path = ffprobe_path
                self._ffmpeg_ready_event.set()
                self.after(0, self._hide_dep_banner)
                self._set_status_threadsafe("FFmpeg is ready.")
                return

            self.after(0, self._warn_dependency_download)
            self.after(
                0,
                lambda: self.dep_progress.show(
                    title="Downloading FFmpeg",
                    message="FFmpeg missing — downloading dependency...",
                    indeterminate=True,
                ),
            )
            self._set_status_threadsafe("FFmpeg missing — downloading dependency...")
            ffmpeg_path, ffprobe_path = ensure_managed_ffmpeg(
                logger=self._set_status_threadsafe,
                progress_callback=self.dep_progress.threadsafe_callback(
                    widget=self,
                    title="Downloading FFmpeg",
                    extra=lambda message, _percent: self._set_status_threadsafe(message),
                ),
            )
            self.ffmpeg_path = ffmpeg_path
            self.ffprobe_path = ffprobe_path
            if ffmpeg_path and ffprobe_path:
                self._ffmpeg_ready_event.set()
                self.after(0, self._hide_dep_banner)
                self.after(0, self.dep_progress.hide)
                self._set_status_threadsafe("FFmpeg downloaded. Ready to convert.")
            else:
                self._ffmpeg_ready_event.clear()
                help_text = get_ffmpeg_install_help()
                self.after(0, self.dep_progress.hide)
                self.after(0, lambda: self._show_dep_banner("FFmpeg download failed. Install it, then retry."))
                self._set_status_threadsafe(help_text)
        except Exception as exc:
            self._ffmpeg_ready_event.clear()
            self.after(0, self.dep_progress.hide)
            self.after(0, lambda: self._show_dep_banner(f"FFmpeg setup failed: {exc}"))
            self._set_status_threadsafe(f"FFmpeg setup failed: {exc}")

    def _start_background_ffmpeg_prepare(self):
        with self._ffmpeg_prepare_lock:
            if self._ffmpeg_prepare_thread is not None and self._ffmpeg_prepare_thread.is_alive():
                return
            self._ffmpeg_prepare_thread = threading.Thread(
                target=self._background_prepare_ffmpeg,
                daemon=True,
            )
            self._ffmpeg_prepare_thread.start()

    def _status_tag(self, status):
        normalized = (status or "").lower()
        if normalized.startswith("ready"):
            return "status_ready"
        if normalized.startswith("queued") or normalized.startswith("retry"):
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

    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=PRIMARY_BG)
        style.configure("Surface.TFrame", background=SURFACE_BG)
        style.configure("Panel.TFrame", background=CARD_BG)
        style.configure("Section.TFrame", background=SECTION_BG)
        style.configure("Warn.TFrame", background="#3A2A0A")
        style.configure("Header.TLabel", background=PRIMARY_BG, foreground=TEXT_MAIN, font=("Segoe UI", 14, "bold"))
        style.configure("SubHeader.TLabel", background=PRIMARY_BG, foreground=TEXT_MUTED, font=("Segoe UI", 9))
        style.configure("Warn.TLabel", background="#3A2A0A", foreground=WARNING, font=("Segoe UI", 8), wraplength=460)
        style.configure("FieldLabel.TLabel", background=SECTION_BG, foreground=TEXT_MAIN, font=("Segoe UI", 9, "bold"))
        style.configure(
            "Modern.TEntry",
            fieldbackground=INPUT_BG,
            foreground=TEXT_MAIN,
            bordercolor=INPUT_BORDER,
            lightcolor=INPUT_BORDER,
            darkcolor=INPUT_BORDER,
            insertcolor=TEXT_MAIN,
            padding=6,
        )
        style.configure(
            "Modern.TCombobox",
            fieldbackground=INPUT_BG,
            background=INPUT_BG,
            foreground=TEXT_MAIN,
            bordercolor=INPUT_BORDER,
            arrowcolor=ACCENT,
            padding=4,
        )
        style.map(
            "Modern.TCombobox",
            fieldbackground=[("readonly", INPUT_BG)],
            selectbackground=[("readonly", INPUT_BG)],
            selectforeground=[("readonly", TEXT_MAIN)],
            foreground=[("readonly", TEXT_MAIN)],
        )
        style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"), padding=(8, 6), borderwidth=0, background=ACCENT_BG, foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", ACCENT), ("disabled", "#374151")], foreground=[("disabled", "#9ca3af")])
        style.configure("Secondary.TButton", font=("Segoe UI", 9), padding=(8, 6), borderwidth=0, background=SECTION_BG, foreground=TEXT_MAIN)
        style.map("Secondary.TButton", background=[("active", "#16233A"), ("disabled", "#1E293B")], foreground=[("disabled", "#9ca3af")])
        style.configure("Danger.TButton", font=("Segoe UI", 9, "bold"), padding=(8, 6), borderwidth=0, background=ACCENT_DANGER, foreground="#ffffff")
        style.map("Danger.TButton", background=[("active", "#fb7185"), ("disabled", "#374151")], foreground=[("disabled", "#9ca3af")])
        style.configure("Treeview", background=SECTION_BG, foreground=TEXT_MAIN, fieldbackground=SECTION_BG, borderwidth=0, rowheight=26, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#16233A", foreground=TEXT_MAIN, font=("Segoe UI", 8, "bold"), relief="flat", padding=4)
        style.map("Treeview", background=[("selected", "#16233A")], foreground=[("selected", ACCENT)])
        style.configure("Vertical.TScrollbar", background=SECTION_BG, troughcolor=PRIMARY_BG, borderwidth=0, arrowsize=0)
        style.configure(
            "Converter.Horizontal.TProgressbar",
            troughcolor=INPUT_BG,
            background=ACCENT_BG,
            bordercolor=INPUT_BORDER,
            lightcolor=ACCENT_BG,
            darkcolor=ACCENT_BG,
        )
        style.configure("DepTitle.TLabel", background=PRIMARY_BG, foreground=TEXT_MAIN, font=("Segoe UI", 9, "bold"))
        style.configure("DepStatus.TLabel", background=PRIMARY_BG, foreground=TEXT_MUTED, font=("Segoe UI", 8))

    def _build_ui(self):
        root = ttk.Frame(self, style="TFrame")
        root.pack(fill="both", expand=True, padx=14, pady=12)

        ttk.Label(root, text="Video Converter", style="Header.TLabel").pack(anchor="w")
        ttk.Label(root, textvariable=self.status_var, style="SubHeader.TLabel", wraplength=460, justify="left").pack(anchor="w", pady=(2, 8))

        self.dep_banner = ttk.Frame(root, style="Warn.TFrame", padding=(8, 6))
        ttk.Label(self.dep_banner, textvariable=self.dep_var, style="Warn.TLabel").pack(anchor="w")

        self.body = ttk.Frame(root, style="TFrame")
        self.body.pack(fill="both", expand=True)
        self.dep_progress = DependencyProgressPanel(
            root,
            title_style="DepTitle.TLabel",
            status_style="DepStatus.TLabel",
            bar_style="Converter.Horizontal.TProgressbar",
            wraplength=460,
            layout="pack",
            layout_kwargs={"fill": "x", "pady": (0, 8)},
            before=self.body,
        )

        toolbar = ttk.Frame(self.body, style="TFrame")
        toolbar.pack(fill="x", pady=(0, 6))
        ttk.Button(toolbar, text="Add", style="Accent.TButton", command=self.add_files).pack(side="left")
        ttk.Button(toolbar, text="Remove", style="Secondary.TButton", command=self.remove_selected).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Clear done", style="Secondary.TButton", command=self.clear_completed).pack(side="left", padx=(6, 0))

        tree_shell = ttk.Frame(self.body, style="Surface.TFrame", padding=1)
        tree_shell.pack(fill="both", expand=True)
        columns = ("name", "status", "progress")
        self.tree = ttk.Treeview(tree_shell, columns=columns, show="headings", selectmode="extended", height=8)
        self.tree.heading("name", text="File")
        self.tree.heading("status", text="Status")
        self.tree.heading("progress", text="")
        self.tree.column("name", width=280, anchor="w")
        self.tree.column("status", width=110, anchor="center")
        self.tree.column("progress", width=60, anchor="center")
        self.tree.tag_configure("status_ready", foreground=TEXT_MAIN)
        self.tree.tag_configure("status_queued", foreground=WARNING)
        self.tree.tag_configure("status_converting", foreground=ACCENT)
        self.tree.tag_configure("status_done", foreground=SUCCESS)
        self.tree.tag_configure("status_failed", foreground=ACCENT_DANGER)
        self.tree.tag_configure("status_cancelled", foreground=TEXT_SOFT)
        self.tree.tag_configure("status_default", foreground=TEXT_MAIN)
        sb = ttk.Scrollbar(tree_shell, orient="vertical", command=self.tree.yview, style="Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        options = ttk.Frame(self.body, style="Section.TFrame", padding=(10, 8))
        options.pack(fill="x", pady=(8, 0))
        options.columnconfigure(1, weight=1)
        options.columnconfigure(3, weight=1)

        ttk.Label(options, text="Format", style="FieldLabel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            options,
            textvariable=self.format_var,
            values=OUTPUT_EXTENSIONS,
            state="readonly",
            width=8,
            style="Modern.TCombobox",
        ).grid(row=0, column=1, sticky="ew", padx=(8, 12))

        ttk.Label(options, text="Quality", style="FieldLabel.TLabel").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            options,
            textvariable=self.quality_var,
            values=QUALITY_OPTIONS,
            state="readonly",
            width=12,
            style="Modern.TCombobox",
        ).grid(row=0, column=3, sticky="ew", padx=(8, 0))

        ttk.Label(options, text="Save to", style="FieldLabel.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(options, textvariable=self.output_dir_var, style="Modern.TEntry").grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=(8, 8), pady=(8, 0)
        )
        ttk.Button(options, text="Browse", style="Secondary.TButton", command=self.browse_output_dir).grid(
            row=1, column=3, sticky="ew", pady=(8, 0)
        )

        actions = ttk.Frame(self.body, style="TFrame")
        actions.pack(fill="x", pady=(10, 0))
        self.btn_start = ttk.Button(actions, text="Convert", style="Accent.TButton", command=self.start_queue)
        self.btn_start.pack(side="left", fill="x", expand=True)
        self.btn_stop = ttk.Button(actions, text="Stop", style="Danger.TButton", command=self.stop_queue, state="disabled")
        self.btn_stop.pack(side="left", fill="x", expand=True, padx=(8, 0))

    def browse_output_dir(self):
        chosen = filedialog.askdirectory(parent=self)
        if chosen:
            self.output_dir_var.set(chosen)

    def add_files(self):
        paths = filedialog.askopenfilenames(parent=self, title="Select videos", filetypes=VIDEO_FILETYPES)
        if not paths:
            return
        added = 0
        existing = {data["path"] for data in self.files.values()}
        for path in paths:
            if path in existing:
                continue
            item_id = self.tree.insert("", "end", values=(os.path.basename(path), "Ready", ""), tags=("status_ready",))
            self.files[item_id] = {"path": path, "status": "Ready"}
            added += 1
        self.status_var.set(f"Added {added} file{'s' if added != 1 else ''}.")

    def remove_selected(self):
        for item_id in self.tree.selection():
            if self.files.get(item_id, {}).get("status") == "Converting...":
                messagebox.showwarning("Busy", "Cannot remove a file that is converting.", parent=self)
                continue
            self.tree.delete(item_id)
            self.files.pop(item_id, None)

    def clear_completed(self):
        for item_id in [iid for iid, data in self.files.items() if data["status"] == "Done"]:
            self.tree.delete(item_id)
            del self.files[item_id]

    def start_queue(self):
        if self.is_converting:
            return

        to_process = [iid for iid, data in self.files.items() if data["status"] in ("Ready", "Failed")]
        if not to_process:
            messagebox.showinfo("Video Converter", "Add videos first.", parent=self)
            return

        if not self._ensure_ffmpeg_ready():
            preparing = self._ffmpeg_prepare_thread is not None and self._ffmpeg_prepare_thread.is_alive()
            messagebox.showwarning(
                "Dependency download",
                "FFmpeg is still being downloaded. Wait until the warning clears, then convert."
                if preparing
                else "FFmpeg is required and could not be downloaded.\n\n" + get_ffmpeg_install_help(),
                parent=self,
            )
            if not preparing:
                self._start_background_ffmpeg_prepare()
            return

        out_dir = self.output_dir_var.get()
        if not os.path.isdir(out_dir):
            if not messagebox.askyesno("Create folder", "Output folder does not exist. Create it?", parent=self):
                return
            os.makedirs(out_dir, exist_ok=True)

        self.is_converting = True
        self._shutdown_event.clear()
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        ext = normalize_output_ext(self.format_var.get())
        self.status_var.set(f"Converting to {ext}...")
        threading.Thread(target=self._run_queue, args=(to_process,), daemon=True).start()

    def _run_queue(self, item_ids):
        ext = normalize_output_ext(self.format_var.get())
        quality = self.quality_var.get() if self.quality_var.get() in QUALITY_OPTIONS else "Balanced"
        out_dir = self.output_dir_var.get()
        for item_id in item_ids:
            if self._shutdown_event.is_set():
                self.after(0, self._update_item, item_id, "Cancelled", "")
                continue
            self.after(0, self._update_item, item_id, "Queued", "0%")
            self._convert_file(item_id, self.files[item_id]["path"], out_dir, ext, quality)
        self.after(0, self._on_queue_finished)

    def _on_queue_finished(self):
        self.is_converting = False
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        if self._shutdown_event.is_set():
            self.status_var.set("Stopped.")
        else:
            self.status_var.set("Done.")

    def stop_queue(self):
        if not self.is_converting:
            return
        self.status_var.set("Stopping...")
        self._shutdown_event.set()

    def _update_item(self, item_id, status=None, progress=None):
        if item_id not in self.files:
            return
        values = list(self.tree.item(item_id, "values"))
        if status is not None:
            self.files[item_id]["status"] = status
            values[1] = status
        if progress is not None:
            values[2] = progress
        self.tree.item(item_id, values=values, tags=(self._status_tag(status or values[1]),))

    def _convert_file(self, item_id, input_path, out_dir, ext, quality):
        if self._shutdown_event.is_set():
            self.after(0, self._update_item, item_id, "Cancelled", "")
            return

        self.after(0, self._update_item, item_id, "Converting...", "0%")
        out_path = next_output_path(out_dir, input_path, ext)
        duration_sec = self._get_duration(input_path)

        if quality == "Fast copy":
            ok = self._run_ffmpeg(item_id, build_convert_command(self.ffmpeg_path, input_path, out_path, "Fast copy"), duration_sec)
            if ok:
                self.after(0, self._update_item, item_id, "Done", "100%")
                return
            if self._shutdown_event.is_set():
                self.after(0, self._update_item, item_id, "Cancelled", "")
                return
            self.after(0, self._update_item, item_id, "Retrying encode...", "0%")
            quality = "Balanced"

        ok = self._run_ffmpeg(item_id, build_convert_command(self.ffmpeg_path, input_path, out_path, quality), duration_sec)
        if ok:
            self.after(0, self._update_item, item_id, "Done", "100%")
        elif self._shutdown_event.is_set():
            self.after(0, self._update_item, item_id, "Cancelled", "")
        else:
            self.after(0, self._update_item, item_id, "Failed", "")

    def _run_ffmpeg(self, item_id, cmd, duration_sec):
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                universal_newlines=True,
                creationflags=_NO_WINDOW,
            )
            for raw_line in process.stdout or []:
                if self._shutdown_event.is_set():
                    process.terminate()
                    return False
                line = raw_line.strip()
                if line.startswith("out_time_ms="):
                    try:
                        seconds = int(line.split("=", 1)[1]) / 1_000_000.0
                        if duration_sec and duration_sec > 0:
                            pct = min(99.0, (seconds / duration_sec) * 100)
                            self.after(0, self._update_item, item_id, None, f"{pct:.0f}%")
                    except ValueError:
                        pass
            process.wait()
            return process.returncode == 0
        except Exception:
            return False

    def _get_duration(self, path):
        if not self.ffprobe_path or not os.path.isfile(self.ffprobe_path):
            return None
        try:
            result = subprocess.run(
                [self.ffprobe_path, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True,
                text=True,
                creationflags=_NO_WINDOW,
            )
            return float(result.stdout.strip())
        except Exception:
            return None

    def on_close(self):
        global converter_window
        if self.is_converting and not messagebox.askyesno("Exit", "Conversion in progress. Stop and close?", parent=self):
            return
        if self.is_converting:
            self.stop_queue()
        self.destroy()
        if converter_window is self:
            converter_window = None
        if self._standalone_root is not None:
            cleanup_hidden_root(self._standalone_root)


def force_close_converter_if_open() -> None:
    """Close the converter without confirmation (hub shutdown)."""
    global converter_window
    window = converter_window
    if window is None:
        return
    try:
        if not window.winfo_exists():
            converter_window = None
            return
        if getattr(window, "is_converting", False):
            try:
                window.stop_queue()
            except Exception:
                pass
        standalone = getattr(window, "_standalone_root", None)
        window.destroy()
        if standalone is not None:
            cleanup_hidden_root(standalone)
    except Exception:
        pass
    converter_window = None


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
