import tkinter as tk
from tkinter import ttk, messagebox, BooleanVar, filedialog
import os
from collections import deque
import yt_dlp
import threading
import webbrowser
import pyperclip
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageTk, ImageSequence, ImageDraw
import sys
import ctypes
from ctypes import wintypes
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import validators
import yt_dlp.postprocessor.ffmpeg
import queue
import shutil
import requests
import json
import zipfile
import subprocess
import time
import ssl
import certifi
import io
import traceback
from datetime import datetime

try:
    import winreg
except ImportError:
    winreg = None

APP_DIR = Path(__file__).resolve().parent
SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

IS_WINDOWS = sys.platform.startswith("win")
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
SCREENSHOT_HOTKEY_ID = 0x594D
SCREENSHOT_HOTKEY_LABEL = "Ctrl+Shift+Y"
SCREENRECORDER_HOTKEY_ID = 0x5952
SCREENRECORDER_HOTKEY_LABEL = "Ctrl+Shift+R"

try:
    from desktop_tools.shared.resources import apply_window_icon, center_window, get_asset_path, get_project_root, get_user_data_dir
    from desktop_tools.shared.ffmpeg import (
        download_managed_ffmpeg,
        ensure_managed_ffmpeg,
        find_existing_ffmpeg,
        get_managed_ffmpeg_paths,
        update_managed_ffmpeg_if_needed,
        verify_ffmpeg_binaries,
    )
    from desktop_tools.shared.direct_download import DirectDownloadError, DirectDownloadTask
except Exception:
    def apply_window_icon(window, app_id="needyamin.media_downloader"):
        return APP_DIR / "assets" / "needyamin.ico"

    def center_window(window, parent=None):
        return None

    def get_asset_path(asset_name):
        return APP_DIR / "assets" / asset_name

    def get_project_root():
        return APP_DIR.parents[2]

    def get_user_data_dir(app_name="Media Downloader"):
        base_dir = Path.home() / ".local" / "share" / app_name
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    class DirectDownloadError(Exception):
        pass

    class DirectDownloadTask:
        def __init__(self, *args, **kwargs):
            self.state = "error"
            self.error_message = "Direct download module is unavailable."

        def is_busy(self):
            return False

        def start(self):
            raise DirectDownloadError("Direct download module is unavailable.")

        def pause(self):
            return None

        def resume(self):
            return False

        def cancel(self):
            return None

    def verify_ffmpeg_binaries(ffmpeg_path, ffprobe_path, logger=None):
        return False

    def ensure_managed_ffmpeg(extra_paths=None, logger=None, progress_callback=None):
        return None, None

    def find_existing_ffmpeg(extra_paths=None, logger=None):
        return None, None

    def get_managed_ffmpeg_paths():
        return APP_DIR / "ffmpeg" / "ffmpeg.exe", APP_DIR / "ffmpeg" / "ffprobe.exe"

    def download_managed_ffmpeg(logger=None, progress_callback=None):
        return None, None

    def update_managed_ffmpeg_if_needed(logger=None, progress_callback=None, force=False, extra_paths=None):
        return None, None, False

APP_FLAGS_PATH = get_project_root() / "app_flags.json"
DEFAULT_APP_FLAGS = {
    "debug_logging": False,
    "ui_queue_poll_ms": 150,
    "clipboard_poll_ms_active": 1200,
    "clipboard_poll_ms_background": 2500,
    "clipboard_recent_limit": 10,
    "progress_log_min_interval_ms": 1500,
    "progress_ui_min_interval_ms": 250,
    "max_log_lines": 400,
    "disabled_domains": [],
}

def load_app_flags():
    """Load runtime flags from the project root for easy tuning."""
    flags = DEFAULT_APP_FLAGS.copy()
    try:
        if APP_FLAGS_PATH.exists():
            with open(APP_FLAGS_PATH, 'r', encoding='utf-8') as flag_file:
                loaded_flags = json.load(flag_file)
            if isinstance(loaded_flags, dict):
                flags.update(loaded_flags)
    except Exception:
        pass
    return flags

APP_FLAGS = load_app_flags()
DEBUG_MODE = bool(APP_FLAGS.get("debug_logging", False))
UI_QUEUE_POLL_MS = max(50, int(APP_FLAGS.get("ui_queue_poll_ms", 150)))
CLIPBOARD_POLL_MS_ACTIVE = max(250, int(APP_FLAGS.get("clipboard_poll_ms_active", 1200)))
CLIPBOARD_POLL_MS_BACKGROUND = max(500, int(APP_FLAGS.get("clipboard_poll_ms_background", 2500)))
CLIPBOARD_RECENT_LIMIT = max(1, int(APP_FLAGS.get("clipboard_recent_limit", 10)))
PROGRESS_LOG_MIN_INTERVAL_MS = max(250, int(APP_FLAGS.get("progress_log_min_interval_ms", 1500)))
PROGRESS_UI_MIN_INTERVAL_MS = max(100, int(APP_FLAGS.get("progress_ui_min_interval_ms", 250)))
MAX_LOG_LINES = max(50, int(APP_FLAGS.get("max_log_lines", 400)))

def normalize_domain_name(domain):
    """Normalize a domain name for blocklist checks."""
    if not domain:
        return ""

    normalized = str(domain).strip().lower().rstrip('.')
    while normalized.startswith('.'):
        normalized = normalized[1:]
    if normalized.startswith('www.'):
        normalized = normalized[4:]
    return normalized

DISABLED_DOMAINS = [
    normalized
    for normalized in (
        normalize_domain_name(domain)
        for domain in APP_FLAGS.get("disabled_domains", [])
        if isinstance(domain, str)
    )
    if normalized
]

def get_disabled_domain_match(url):
    """Return the blocked domain that matches a URL, if any."""
    try:
        hostname = normalize_domain_name(urlparse(url).hostname)
        if not hostname:
            return None

        for blocked_domain in DISABLED_DOMAINS:
            if hostname == blocked_domain or hostname.endswith(f".{blocked_domain}"):
                return blocked_domain
    except Exception:
        return None

    return None

def debug_print(*args, **kwargs):
    """Print only when debug logging is enabled."""
    if DEBUG_MODE:
        print(*args, **kwargs)

def debug_log(message):
    """Log only when debug logging is enabled."""
    if DEBUG_MODE:
        log(message)


def ffmpeg_log(message):
    """Always show FFmpeg activity in the main log."""
    normalized_message = str(message).strip()
    if normalized_message:
        log(f"[FFmpeg] {normalized_message}")

# Set up debugging and error handling
def setup_debugging():
    """Configure debugging and error handling"""
    if DEBUG_MODE:
        debug_print("\n=== SYSTEM INFORMATION ===")
        debug_print(f"Python version: {sys.version}")
        debug_print(f"Operating system: {sys.platform}")
        debug_print(f"Current directory: {os.getcwd()}")
        
        try:
            debug_print(f"yt-dlp version: {yt_dlp.version.__version__}")
        except Exception as e:
            debug_print(f"Error getting yt-dlp version: {e}")
        
        required_modules = [
            "tkinter", "PIL", "yt_dlp", "pyperclip", "pystray", 
            "validators", "win32com", "requests"
        ]
        
        debug_print("\n=== MODULE CHECKS ===")
        for module_name in required_modules:
            try:
                module = __import__(module_name)
                if hasattr(module, "__version__"):
                    debug_print(f"{module_name}: OK (version {module.__version__})")
                else:
                    debug_print(f"{module_name}: OK")
            except ImportError as e:
                debug_print(f"{module_name}: MISSING - {e}")
            except Exception as e:
                debug_print(f"{module_name}: ERROR - {e}")
    
    # Set up global exception handler
    def global_exception_handler(exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
            
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        if DEBUG_MODE:
            debug_print(f"\n[CRITICAL ERROR]:\n{error_msg}")
        
        # If message box is available, show error
        try:
            if 'messagebox' in globals():
                messagebox.showerror("Critical Error", 
                    f"An unexpected error occurred: {exc_value}\n\nSee console for details.")
        except:
            pass
    
    # Install the exception handler
    sys.excepthook = global_exception_handler
    debug_print("\n=== DEBUG SETUP COMPLETE ===\n")

# Run debugging setup
setup_debugging()

# GUI Theme and Styles
THEME = {
    'bg': '#ffffff',
    'fg': '#333333',
    'primary': '#2196F3',
    'secondary': '#1976D2',
    'success': '#4CAF50',
    'error': '#F44336',
    'warning': '#FFC107',
    'gray': '#757575',
    'light_gray': '#f5f5f5',
    'border': '#e0e0e0'
}

# Path configuration
ICON_PATH = get_asset_path("needyamin.ico")

# Installation directory (using AppData by default for better compatibility)
INSTALL_DIR = get_user_data_dir("Media Downloader")
INSTALL_DIR.mkdir(parents=True, exist_ok=True)

# Persistent settings and output directories
DEFAULT_DOWNLOADS_PATH = Path.home() / "Downloads" / "Yamin Downloader"
SETTINGS_FILE = INSTALL_DIR / "settings.json"
VALID_VIDEO_QUALITIES = {"best", "1080", "720", "480", "360"}
VALID_AUDIO_QUALITIES = {"320", "256", "192", "128", "96"}
VALID_FORMATS = {"mp4", "webm", "mkv"}

# Auto-update configuration
REPO_OWNER = "needyamin"
REPO_NAME = "media-downloader"
CURRENT_VERSION = "2.0.0"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
UPDATE_CHECK_FILE = INSTALL_DIR / "last_update_check.txt"
APP_UPDATE_DIR = INSTALL_DIR / "updates"
AUTHOR_PROFILE = {
    'name': 'Md. Yamin Hossain',
    'role': 'Sr. Software Engineer',
    'location': 'Dhaka, Bangladesh',
    'github': 'https://github.com/needyamin',
    'website': 'https://needyamin.github.io',
    'orcid': 'https://orcid.org/0009-0009-1184-6005',
    'facebook': 'https://facebook.com/needyaminofficial',
    'avatar_url': 'https://github.com/needyamin.png?size=240',
    'bio': 'Software Engineer focused on scalable systems, infrastructure automation, and intuitive user experiences.',
}

# Add a force check flag to check for updates regardless of the time since last check
FORCE_UPDATE_CHECK = False

# Global variables
ffmpeg_path = None
ffprobe_path = None
ffmpeg_sync_thread = None
ffmpeg_sync_lock = threading.Lock()
app_update_thread = None
app_update_lock = threading.Lock()
early_log_queue = queue.Queue()
loading_gif = None
loading_label = None
about_window = None
debug_update_window = None
error_dialog_window = None

def default_app_settings():
    """Return default application settings."""
    return {
        'download_root': str(DEFAULT_DOWNLOADS_PATH),
        'video_quality': 'best',
        'audio_quality': '320',
        'format': 'mp4',
        'download_playlist': False,
        'max_files': '100',
    }

def normalize_bool(value):
    """Convert common truthy/falsey values into a boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)

def sanitize_max_files(value):
    """Normalize max file count to a safe positive integer string."""
    try:
        return str(max(1, int(str(value).strip())))
    except (TypeError, ValueError):
        return '100'

def normalize_download_root(path_value):
    """Return a valid download root path."""
    try:
        return Path(path_value).expanduser() if path_value else DEFAULT_DOWNLOADS_PATH
    except Exception:
        return DEFAULT_DOWNLOADS_PATH

def load_app_settings():
    """Load persisted settings from disk."""
    settings = default_app_settings()
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as settings_file:
                loaded_settings = json.load(settings_file)
            if isinstance(loaded_settings, dict):
                settings.update(loaded_settings)
    except Exception as e:
        print(f"Error loading settings: {e}")

    settings['download_root'] = str(normalize_download_root(settings.get('download_root')))
    settings['video_quality'] = settings.get('video_quality') if settings.get('video_quality') in VALID_VIDEO_QUALITIES else 'best'
    settings['audio_quality'] = settings.get('audio_quality') if settings.get('audio_quality') in VALID_AUDIO_QUALITIES else '320'
    settings['format'] = settings.get('format') if settings.get('format') in VALID_FORMATS else 'mp4'
    settings['download_playlist'] = normalize_bool(settings.get('download_playlist'))
    settings['max_files'] = sanitize_max_files(settings.get('max_files'))
    return settings

app_settings = load_app_settings()
downloads_path = normalize_download_root(app_settings.get('download_root'))
video_output_dir = downloads_path / "video"
audio_output_dir = downloads_path / "audio"
playlist_output_dir = downloads_path / "playlists"
direct_output_dir = downloads_path / "files"
video_output_dir.mkdir(parents=True, exist_ok=True)
audio_output_dir.mkdir(parents=True, exist_ok=True)
playlist_output_dir.mkdir(parents=True, exist_ok=True)
direct_output_dir.mkdir(parents=True, exist_ok=True)

quality_settings = {
    'video_quality': app_settings['video_quality'],  # best, 1080p, 720p, 480p, 360p
    'audio_quality': app_settings['audio_quality'],  # 320, 256, 192, 128, 96
    'format': app_settings['format']                 # mp4, webm, mkv
}

def verify_ffmpeg(ffmpeg_path, ffprobe_path):
    """Verify that FFmpeg and FFprobe are working."""
    try:
        print(f"\n=== FFMPEG VERIFICATION ===")
        print(f"FFmpeg path: {ffmpeg_path}")
        print(f"FFprobe path: {ffprobe_path}")
        is_valid = verify_ffmpeg_binaries(ffmpeg_path, ffprobe_path, logger=ffmpeg_log)
        if not is_valid:
            ffmpeg_log(f"FFmpeg verification failed for: {ffmpeg_path}")
        return is_valid
    except Exception as e:
        log(f"Error verifying FFmpeg: {str(e)}")
        print(f"Exception during FFmpeg verification: {str(e)}")
        print(traceback.format_exc())
        return False

def download_ffmpeg():
    """Download and install FFmpeg."""
    message_label = None
    try:
        message_label = show_loading("Downloading FFmpeg...")
        def update_status(message):
            ffmpeg_log(message)
            if message_label:
                try:
                    message_label.config(text=message)
                except Exception:
                    pass

        ffmpeg_path, ffprobe_path = download_managed_ffmpeg(logger=ffmpeg_log, progress_callback=update_status)
        if ffmpeg_path and ffprobe_path:
            ffmpeg_log("FFmpeg installation successful.")
            return str(ffmpeg_path)

        ffmpeg_log("All FFmpeg download attempts failed.")
        messagebox.showerror(
            "Error",
            "Failed to download FFmpeg. You may need to install it manually.\n"
            "Please visit: https://ffmpeg.org/download.html",
        )
        return None
            
    except Exception as e:
        log(f"Error downloading FFmpeg: {str(e)}")
        return None
    finally:
        if message_label:
            hide_loading(message_label)

def show_loading(message="Loading..."):
    """Show a loading animation with a message."""
    global loading_gif, loading_label
    try:
        if loading_gif is None:
            loading_gif = create_loading_icon()
        
        if loading_label is None:
            loading_label = tk.Label(root, bg=THEME['bg'])
            loading_label.place(relx=0.5, rely=0.5, anchor='center')
        
        loading_label.config(text=message)
        update_loading_animation()
        return loading_label
    except:
        return None

def hide_loading(label=None):
    """Hide the loading animation."""
    global loading_label
    try:
        if label:
            label.place_forget()
        elif loading_label:
            loading_label.place_forget()
        loading_label = None
    except:
        pass

def create_progress_hook():
    """Create a progress hook for yt-dlp."""
    hook_state = {
        'last_log_at': 0.0,
        'last_ui_at': 0.0,
        'finished_logged': False,
    }

    def progress_hook(d):
        if download_cancelled or cancel_event.is_set():
            # Raise an exception to stop the download
            raise yt_dlp.utils.DownloadError("Download cancelled by user")
            
        if d['status'] == 'downloading':
            try:
                # Calculate download progress
                total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                
                if total > 0:
                    percent = (downloaded / total) * 100
                    speed = d.get('speed', 0)
                    if speed:
                        eta = d.get('eta', 0)
                        speed_str = f"{speed/1024/1024:.1f} MB/s"
                        eta_str = f"ETA: {eta//60}m {eta%60}s"
                        message = f"Downloading: {percent:.1f}% | Speed: {speed_str} | {eta_str}"
                    else:
                        message = f"Downloading: {percent:.1f}%"
                    
                    now = time.monotonic()
                    if (now - hook_state['last_ui_at']) * 1000 >= PROGRESS_UI_MIN_INTERVAL_MS:
                        ui_queue.put(lambda: update_progress(percent, message))
                        hook_state['last_ui_at'] = now
                    if DEBUG_MODE and (now - hook_state['last_log_at']) * 1000 >= PROGRESS_LOG_MIN_INTERVAL_MS:
                        debug_log(message)
                        hook_state['last_log_at'] = now
            except Exception as e:
                if DEBUG_MODE:
                    debug_log(f"Progress error: {str(e)}")
        
        elif d['status'] == 'finished':
            if not download_cancelled and not hook_state['finished_logged']:
                ui_queue.put(lambda: update_progress(100, "Download complete! Processing..."))
                hook_state['finished_logged'] = True
        
        elif d['status'] == 'error':
            if not download_cancelled:
                error_msg = d.get('error', 'Unknown error')
                ui_queue.put(lambda: update_progress(0, f"Error occurred: {error_msg}"))
                log(f"Download error: {error_msg}")
    
    return progress_hook

def is_auto_start_enabled():
    """Check if the application is set to start with Windows"""
    if not IS_WINDOWS or winreg is None:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, "Video Downloader")
            return True
        except OSError:
            return False
        finally:
            key.Close()
    except Exception as e:
        print(f"Error checking auto-start: {e}")
        return False


auto_start_enabled = is_auto_start_enabled()

def toggle_auto_start():
    """Toggle auto-start with Windows"""
    global auto_start_enabled
    if not IS_WINDOWS or winreg is None:
        auto_start_enabled = False
        if 'auto_start_var' in globals():
            auto_start_var.set(False)
        messagebox.showinfo("Not Supported", "Auto-start is available on Windows only.")
        return
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        if auto_start_var.get():
            # Get the path to the Python executable and the script
            python_path = sys.executable
            script_path = os.path.abspath(__file__)
            # Create the command to run the script
            command = f'"{python_path}" "{script_path}"'
            winreg.SetValueEx(key, "Video Downloader", 0, winreg.REG_SZ, command)
            print("Auto-start enabled")
        else:
            try:
                winreg.DeleteValue(key, "Video Downloader")
                print("Auto-start disabled")
            except OSError:
                pass
        key.Close()
        auto_start_enabled = bool(auto_start_var.get())
    except Exception as e:
        print(f"Error toggling auto-start: {e}")
        auto_start_enabled = is_auto_start_enabled()

def is_packaged_runtime():
    """Return True when running as a packaged Windows executable."""
    executable_name = Path(sys.executable).name.lower()
    return IS_WINDOWS and bool(getattr(sys, 'frozen', False)) and executable_name not in {'python.exe', 'pythonw.exe'}

def get_update_headers():
    """Common headers for GitHub release requests."""
    return {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': f'Yamin-media-downloader/{CURRENT_VERSION}'
    }

def get_runtime_update_mode():
    """Describe how updates behave in the current runtime."""
    return "packaged-exe" if is_packaged_runtime() else "source-python"

def get_preferred_update_asset(release, require_installer=False):
    """Pick the safest release asset for the updater."""
    assets = release.get('assets', [])
    exe_assets = [asset for asset in assets if asset.get('name', '').lower().endswith('.exe')]
    installer_assets = [
        asset for asset in exe_assets
        if any(keyword in asset.get('name', '').lower() for keyword in ('setup', 'installer'))
    ]

    if require_installer:
        return installer_assets[0] if installer_assets else None
    if installer_assets:
        return installer_assets[0]
    return exe_assets[0] if exe_assets else None

def close_debug_update_window():
    """Close the custom update debug dialog."""
    global debug_update_window
    if debug_update_window and debug_update_window.winfo_exists():
        debug_update_window.destroy()
    debug_update_window = None

def copy_debug_report(report_text):
    """Copy the debug update report to the clipboard."""
    try:
        root.clipboard_clear()
        root.clipboard_append(report_text)
        root.update()
        messagebox.showinfo("Copied", "The debug update report has been copied to the clipboard.")
    except Exception as e:
        messagebox.showerror("Copy Failed", f"Could not copy the report:\n{e}")

def normalize_error_details(details, remove_prefix=None):
    """Clean repetitive exception text for display."""
    if details is None:
        return ""

    cleaned = str(details).strip()
    if remove_prefix and cleaned.lower().startswith(remove_prefix.lower()):
        cleaned = cleaned[len(remove_prefix):].lstrip(": -")
    return cleaned

def close_error_dialog():
    """Close the custom error dialog."""
    global error_dialog_window
    if error_dialog_window and error_dialog_window.winfo_exists():
        error_dialog_window.destroy()
    error_dialog_window = None

def copy_error_details(details):
    """Copy error details to the clipboard."""
    try:
        root.clipboard_clear()
        root.clipboard_append(details)
        root.update()
        messagebox.showinfo("Copied", "Error details copied to the clipboard.")
    except Exception as e:
        messagebox.showerror("Copy Failed", f"Could not copy the error details:\n{e}")

def show_error_dialog(title, summary, details="", suggestion=""):
    """Show a nicer custom error dialog instead of a raw messagebox."""
    global error_dialog_window

    if error_dialog_window and error_dialog_window.winfo_exists():
        error_dialog_window.destroy()

    error_dialog_window = tk.Toplevel(root)
    error_dialog_window.title(title)
    error_dialog_window.geometry("640x420")
    error_dialog_window.minsize(580, 360)
    error_dialog_window.configure(bg=THEME['bg'])
    error_dialog_window.transient(root)
    error_dialog_window.protocol("WM_DELETE_WINDOW", close_error_dialog)
    apply_window_icon(error_dialog_window, app_id="needyamin.media_downloader")

    outer = tk.Frame(error_dialog_window, bg=THEME['bg'])
    outer.pack(fill='both', expand=True, padx=20, pady=20)

    header_card = tk.Frame(outer, bg='#fff3f3', bd=1, relief='solid')
    header_card.pack(fill='x', pady=(0, 14))

    icon_box = tk.Label(
        header_card,
        text="!",
        font=('Segoe UI', 26, 'bold'),
        bg='#F44336',
        fg='white',
        width=2,
        height=1,
    )
    icon_box.pack(side='left', padx=18, pady=18)

    header_text = tk.Frame(header_card, bg='#fff3f3')
    header_text.pack(fill='both', expand=True, padx=(0, 18), pady=18)

    tk.Label(
        header_text,
        text=title,
        font=('Segoe UI', 16, 'bold'),
        bg='#fff3f3',
        fg=THEME['error'],
        anchor='w',
    ).pack(anchor='w')

    tk.Label(
        header_text,
        text=summary,
        font=('Segoe UI', 10),
        bg='#fff3f3',
        fg=THEME['fg'],
        anchor='w',
        justify='left',
        wraplength=470,
    ).pack(anchor='w', pady=(6, 0))

    body_card = tk.Frame(outer, bg='white', bd=1, relief='solid')
    body_card.pack(fill='both', expand=True)
    body_card.grid_rowconfigure(1, weight=1)
    body_card.grid_columnconfigure(0, weight=1)

    if suggestion:
        tk.Label(
            body_card,
            text=suggestion,
            font=('Segoe UI', 10),
            bg='white',
            fg=THEME['fg'],
            justify='left',
            wraplength=580,
        ).grid(row=0, column=0, sticky='w', padx=18, pady=(16, 10))

    details_text = tk.Text(
        body_card,
        wrap='word',
        font=('Consolas', 10),
        bg=THEME['light_gray'],
        fg=THEME['fg'],
        relief='flat',
        padx=12,
        pady=12,
        height=8,
    )
    details_text.grid(row=1, column=0, sticky='nsew', padx=(18, 0), pady=(0, 16))

    details_scroll = ttk.Scrollbar(body_card, orient='vertical', command=details_text.yview)
    details_scroll.grid(row=1, column=1, sticky='ns', padx=(0, 18), pady=(0, 16))
    details_text.configure(yscrollcommand=details_scroll.set)
    details_text.insert('1.0', details if details else "No additional details available.")
    details_text.config(state='disabled')

    button_row = tk.Frame(outer, bg=THEME['bg'])
    button_row.pack(fill='x', pady=(14, 0))

    tk.Button(
        button_row,
        text="Copy Details",
        bg=THEME['light_gray'],
        fg=THEME['fg'],
        activebackground=THEME['border'],
        activeforeground=THEME['fg'],
        relief='flat',
        cursor='hand2',
        padx=16,
        pady=7,
        command=lambda: copy_error_details(details if details else "No additional details available."),
    ).pack(side='left')

    tk.Button(
        button_row,
        text="Close",
        bg=THEME['primary'],
        fg='white',
        activebackground=THEME['secondary'],
        activeforeground='white',
        relief='flat',
        cursor='hand2',
        padx=16,
        pady=7,
        command=close_error_dialog,
    ).pack(side='right')

    error_dialog_window.after_idle(lambda: center_window(error_dialog_window, root))

def show_debug_update_window(debug_data, report_text):
    """Show a richer UI for update diagnostics."""
    global debug_update_window

    if debug_update_window and debug_update_window.winfo_exists():
        debug_update_window.destroy()

    debug_update_window = tk.Toplevel(root)
    debug_update_window.title("Debug Update System")
    debug_update_window.geometry("760x560")
    debug_update_window.minsize(700, 500)
    debug_update_window.configure(bg=THEME['bg'])
    debug_update_window.transient(root)
    debug_update_window.protocol("WM_DELETE_WINDOW", close_debug_update_window)
    apply_window_icon(debug_update_window, app_id="needyamin.media_downloader")

    outer = tk.Frame(debug_update_window, bg=THEME['bg'])
    outer.pack(fill='both', expand=True, padx=20, pady=20)

    header = tk.Frame(outer, bg=THEME['bg'])
    header.pack(fill='x', pady=(0, 14))

    tk.Label(
        header,
        text="Debug Update System",
        font=('Segoe UI', 20, 'bold'),
        bg=THEME['bg'],
        fg=THEME['primary']
    ).pack(anchor='w')

    tk.Label(
        header,
        text="Inspect the current updater runtime, release status, and selected installer behavior.",
        font=('Segoe UI', 10),
        bg=THEME['bg'],
        fg=THEME['gray']
    ).pack(anchor='w', pady=(4, 0))

    summary_card = tk.Frame(outer, bg=THEME['light_gray'], bd=1, relief='solid')
    summary_card.pack(fill='x', pady=(0, 14))
    summary_card.grid_columnconfigure(1, weight=1)
    summary_card.grid_columnconfigure(3, weight=1)

    summary_rows = [
        ("Current Version", debug_data.get('current_version', 'Unknown')),
        ("Runtime Mode", debug_data.get('runtime_mode', 'Unknown')),
        ("API Status", debug_data.get('api_status', 'Unknown')),
        ("Latest Release", debug_data.get('latest_release', 'Unknown')),
        ("Preferred Asset", debug_data.get('preferred_asset', 'Unknown')),
        ("Installer Asset", debug_data.get('installer_asset', 'Unknown')),
        ("Update Mode", debug_data.get('update_mode', 'Unknown')),
        ("Last Check", debug_data.get('last_check', 'Not found')),
    ]

    for index, (label, value) in enumerate(summary_rows):
        row = index // 2
        column = (index % 2) * 2
        tk.Label(
            summary_card,
            text=f"{label}:",
            font=('Segoe UI', 10, 'bold'),
            bg=THEME['light_gray'],
            fg=THEME['fg'],
            anchor='w'
        ).grid(row=row, column=column, sticky='w', padx=(16, 8), pady=8)

        tk.Label(
            summary_card,
            text=value,
            font=('Segoe UI', 10),
            bg=THEME['light_gray'],
            fg=THEME['fg'],
            anchor='w',
            justify='left',
            wraplength=250
        ).grid(row=row, column=column + 1, sticky='ew', padx=(0, 16), pady=8)

    if debug_data.get('release_url'):
        release_link = tk.Label(
            outer,
            text=debug_data['release_url'],
            font=('Segoe UI', 10, 'underline'),
            bg=THEME['bg'],
            fg=THEME['primary'],
            cursor='hand2',
            anchor='w',
        )
        release_link.pack(fill='x', pady=(0, 10))
        release_link.bind('<Button-1>', lambda _event: webbrowser.open(debug_data['release_url']))

    report_card = tk.Frame(outer, bg='white', bd=1, relief='solid')
    report_card.pack(fill='both', expand=True)
    report_card.grid_rowconfigure(1, weight=1)
    report_card.grid_columnconfigure(0, weight=1)

    tk.Label(
        report_card,
        text="Detailed Report",
        font=('Segoe UI', 12, 'bold'),
        bg='white',
        fg=THEME['fg']
    ).grid(row=0, column=0, sticky='w', padx=16, pady=(14, 8))

    report_text_widget = tk.Text(
        report_card,
        wrap='word',
        font=('Consolas', 10),
        bg='white',
        fg=THEME['fg'],
        relief='flat',
        padx=12,
        pady=12
    )
    report_text_widget.grid(row=1, column=0, sticky='nsew', padx=(12, 0), pady=(0, 12))

    report_scroll = ttk.Scrollbar(report_card, orient='vertical', command=report_text_widget.yview)
    report_scroll.grid(row=1, column=1, sticky='ns', padx=(0, 12), pady=(0, 12))
    report_text_widget.configure(yscrollcommand=report_scroll.set)
    report_text_widget.insert('1.0', report_text)
    report_text_widget.config(state='disabled')

    button_row = tk.Frame(outer, bg=THEME['bg'])
    button_row.pack(fill='x', pady=(14, 0))

    tk.Button(
        button_row,
        text="Copy Report",
        bg=THEME['primary'],
        fg='white',
        activebackground=THEME['secondary'],
        activeforeground='white',
        relief='flat',
        cursor='hand2',
        padx=16,
        pady=7,
        command=lambda: copy_debug_report(report_text)
    ).pack(side='left')

    if debug_data.get('release_url'):
        tk.Button(
            button_row,
            text="Open Release Page",
            bg=THEME['light_gray'],
            fg=THEME['fg'],
            activebackground=THEME['border'],
            activeforeground=THEME['fg'],
            relief='flat',
            cursor='hand2',
            padx=16,
            pady=7,
            command=lambda: webbrowser.open(debug_data['release_url'])
        ).pack(side='left', padx=(10, 0))

    tk.Button(
        button_row,
        text="Close",
        bg=THEME['light_gray'],
        fg=THEME['fg'],
        activebackground=THEME['border'],
        activeforeground=THEME['fg'],
        relief='flat',
        cursor='hand2',
        padx=16,
        pady=7,
        command=close_debug_update_window
    ).pack(side='right')

    debug_update_window.after_idle(lambda: center_window(debug_update_window, root))

def debug_update_check():
    """Debug function to check update system status"""
    try:
        log("\n=== DEBUG: Update System Status ===")

        debug_data = {
            'current_version': CURRENT_VERSION,
            'runtime_mode': get_runtime_update_mode(),
            'api_status': 'Not checked',
            'latest_release': 'Unknown',
            'preferred_asset': 'Unknown',
            'installer_asset': 'Unknown',
            'update_mode': 'Unknown',
            'last_check': 'Not found',
            'release_url': '',
        }

        debug_lines = [
            "Repository Configuration:",
            f"Owner: {REPO_OWNER}",
            f"Name: {REPO_NAME}",
            f"API URL: {GITHUB_API_URL}",
            f"Current Version: {CURRENT_VERSION}",
            f"Runtime Mode: {get_runtime_update_mode()}",
            f"Executable: {sys.executable}",
        ]

        debug_lines.append("")
        debug_lines.append("Update Check File Status:")
        if UPDATE_CHECK_FILE.exists():
            with open(UPDATE_CHECK_FILE, 'r') as f:
                last_check = float(f.read().strip())
                time_since_last_check = time.time() - last_check
                readable_last_check = time.ctime(last_check)
                debug_data['last_check'] = readable_last_check
                debug_lines.append(f"Last check: {readable_last_check}")
                debug_lines.append(f"Time since last check: {time_since_last_check/3600:.2f} hours")
        else:
            debug_lines.append("Update check file not found")

        debug_lines.append("")
        debug_lines.append("Testing GitHub API Connection:")
        try:
            response = requests.get(GITHUB_API_URL, headers=get_update_headers(), timeout=10)
            debug_data['api_status'] = str(response.status_code)
            debug_lines.append(f"API Response Status: {response.status_code}")

            if response.status_code == 200:
                latest_release = response.json()
                latest_version = latest_release.get('tag_name', '').lstrip('v')
                preferred_asset = get_preferred_update_asset(latest_release)
                installer_asset = get_preferred_update_asset(latest_release, require_installer=True)
                debug_data['latest_release'] = latest_version or 'Unknown'
                debug_data['release_url'] = latest_release.get('html_url', '')
                debug_data['preferred_asset'] = preferred_asset.get('name') if preferred_asset else 'No .exe asset found'
                debug_data['installer_asset'] = installer_asset.get('name') if installer_asset else 'No installer asset found'
                debug_lines.append(f"Latest Release: {latest_version or 'Unknown'}")
                debug_lines.append(f"Release Page: {latest_release.get('html_url', 'N/A')}")
                debug_lines.append(
                    f"Preferred Asset: {debug_data['preferred_asset']}"
                )
                debug_lines.append(
                    f"Installer Asset: {debug_data['installer_asset']}"
                )
                debug_lines.append(
                    f"Version Comparison: {get_version_comparison_info(latest_version, CURRENT_VERSION)['message']}"
                )
                if is_packaged_runtime():
                    debug_data['update_mode'] = 'Installer launch supported'
                    debug_lines.append("In-app update mode: installer launch supported")
                else:
                    debug_data['update_mode'] = 'Source build fallback to release page'
                    debug_lines.append("In-app update mode: source build; release page fallback will be used")
            else:
                debug_lines.append(f"API Error: {response.text[:300]}")
        except Exception as e:
            debug_data['api_status'] = 'Error'
            debug_lines.append(f"API Connection Error: {str(e)}")

        debug_lines.append("")
        debug_lines.append("=== DEBUG COMPLETED ===")

        for line in debug_lines:
            log(line)

        show_debug_update_window(debug_data, "\n".join(debug_lines))
        
    except Exception as e:
        log(f"Debug Error: {str(e)}")

# Create main window
root = tk.Tk()
root.title("Media Downloader")
root.geometry("880x860")
root.minsize(760, 620)  # Set minimum window size
root.configure(bg=THEME['bg'])

# Quality settings variables
video_quality_var = tk.StringVar(value=quality_settings['video_quality'])
audio_quality_var = tk.StringVar(value=quality_settings['audio_quality'])
format_var = tk.StringVar(value=quality_settings['format'])
download_path_var = tk.StringVar(value=str(downloads_path))

# Create auto-start variable
auto_start_var = tk.BooleanVar(value=auto_start_enabled)

def refresh_output_directories(selected_root=None):
    """Refresh all output directory paths."""
    global downloads_path, video_output_dir, audio_output_dir, playlist_output_dir, direct_output_dir

    if selected_root is not None:
        downloads_path = normalize_download_root(selected_root)

    video_output_dir = downloads_path / "video"
    audio_output_dir = downloads_path / "audio"
    playlist_output_dir = downloads_path / "playlists"
    direct_output_dir = downloads_path / "files"

def current_max_files_value():
    """Read the current max-files value from the UI or saved settings."""
    if 'max_files_entry' in globals():
        return sanitize_max_files(max_files_entry.get())
    return sanitize_max_files(app_settings.get('max_files', '100'))

def is_youtube_url(url):
    """Return True when a URL points at YouTube."""
    try:
        hostname = normalize_domain_name(urlparse(url).hostname)
    except Exception:
        return False
    return hostname in {"youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com"}

def strip_youtube_playlist_context(url):
    """Remove playlist-related query params so a single YouTube video stays a single video."""
    try:
        parsed = urlparse(url)
        query_pairs = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in {"list", "index", "start_radio"}
        ]
        return urlunparse(parsed._replace(query=urlencode(query_pairs, doseq=True)))
    except Exception:
        return url

def get_available_ytdlp_js_runtimes():
    """Detect supported yt-dlp JavaScript runtimes available on this system."""
    runtimes = {}
    runtime_binaries = {
        "node": ["node"],
        "deno": ["deno"],
        "bun": ["bun"],
    }
    for runtime, binary_names in runtime_binaries.items():
        if any(shutil.which(binary_name) for binary_name in binary_names):
            runtimes[runtime] = {}
    return runtimes

def get_available_browser_cookie_sources():
    """Return browser names that likely have cookie databases available."""
    candidates = []
    if IS_WINDOWS:
        local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
        roaming_appdata = Path(os.environ.get("APPDATA", ""))
        browser_paths = [
            ("firefox", roaming_appdata / "Mozilla" / "Firefox" / "Profiles"),
            ("edge", local_appdata / "Microsoft" / "Edge" / "User Data"),
            ("chrome", local_appdata / "Google" / "Chrome" / "User Data"),
            ("brave", local_appdata / "BraveSoftware" / "Brave-Browser" / "User Data"),
        ]
    elif sys.platform.startswith("linux"):
        home = Path.home()
        browser_paths = [
            ("firefox", home / ".mozilla" / "firefox"),
            ("chromium", home / ".config" / "chromium"),
            ("chrome", home / ".config" / "google-chrome"),
            ("edge", home / ".config" / "microsoft-edge"),
            ("brave", home / ".config" / "BraveSoftware" / "Brave-Browser"),
        ]
    else:
        browser_paths = []

    for browser_name, browser_path in browser_paths:
        if browser_path.exists() and browser_name not in candidates:
            candidates.append(browser_name)
    return candidates

def is_youtube_bot_or_login_error(error):
    """Detect common YouTube anti-bot and sign-in challenge failures."""
    error_text = str(error).lower()
    indicators = [
        "http error 429",
        "sign in to confirm you’re not a bot",
        "sign in to confirm you're not a bot",
        "login_required",
        "cookies-from-browser",
        "no supported javascript runtime",
    ]
    return any(indicator in error_text for indicator in indicators)

def try_extract_info_with_youtube_fallbacks(url, ydl_opts, extract_error):
    """Retry YouTube extraction with browser cookies when anti-bot protection triggers."""
    if not is_youtube_url(url) or not is_youtube_bot_or_login_error(extract_error):
        return None, None, extract_error

    browser_sources = get_available_browser_cookie_sources()
    if not browser_sources:
        return None, None, extract_error

    last_error = extract_error
    for browser_name in browser_sources:
        retry_opts = dict(ydl_opts)
        retry_opts['cookiesfrombrowser'] = (browser_name,)
        try:
            log(f"Trying YouTube browser-cookie fallback with {browser_name}...")
            candidate_ydl = yt_dlp.YoutubeDL(retry_opts)
            info = candidate_ydl.extract_info(url, download=False)
            log(f"YouTube extraction succeeded using {browser_name} browser cookies.")
            return candidate_ydl, info, None
        except Exception as cookie_error:
            last_error = cookie_error
            debug_log(f"{browser_name} cookie fallback failed: {cookie_error}")

    return None, None, last_error

def collect_app_settings():
    """Collect current application settings for persistence."""
    settings = default_app_settings()
    settings['download_root'] = str(downloads_path)
    settings['video_quality'] = video_quality_var.get() if 'video_quality_var' in globals() else quality_settings['video_quality']
    settings['audio_quality'] = audio_quality_var.get() if 'audio_quality_var' in globals() else quality_settings['audio_quality']
    settings['format'] = format_var.get() if 'format_var' in globals() else quality_settings['format']
    settings['download_playlist'] = bool(download_playlist.get()) if 'download_playlist' in globals() else app_settings.get('download_playlist', False)
    settings['max_files'] = current_max_files_value()
    return settings

def save_app_settings():
    """Persist current application settings to disk."""
    global app_settings
    try:
        app_settings = collect_app_settings()
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as settings_file:
            json.dump(app_settings, settings_file, indent=2)
    except Exception as e:
        print(f"Error saving settings: {e}")

def update_download_path_display():
    """Keep the visible download path label in sync."""
    if 'download_path_var' in globals():
        download_path_var.set(str(downloads_path))

def apply_download_root(selected_root, persist=True):
    """Apply a new root download folder and refresh dependent state."""
    refresh_output_directories(selected_root)
    verify_output_directories()
    update_download_path_display()
    if 'status_label' in globals():
        status_label.config(text=f"Download folder: {downloads_path}")
    if persist:
        save_app_settings()

def open_path_in_file_manager(path_value):
    """Open a file or directory using the current platform file manager."""
    path_str = str(Path(path_value).resolve())
    if IS_WINDOWS:
        os.startfile(path_str)
        return

    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, path_str])

def open_download_folder():
    """Open the active download folder."""
    try:
        verify_output_directories()
        open_path_in_file_manager(downloads_path)
    except Exception as e:
        log(f"Error opening download folder: {e}")
        messagebox.showerror("Folder Error", f"Could not open the download folder:\n{e}")

def choose_download_folder():
    """Let the user choose a custom download folder."""
    selected_directory = filedialog.askdirectory(
        title="Choose Download Folder",
        initialdir=str(downloads_path),
        mustexist=False
    )
    if selected_directory:
        apply_download_root(selected_directory, persist=True)
        log(f"Download folder updated to: {selected_directory}")

def create_default_profile_avatar(size=144):
    """Create a simple fallback avatar when the profile photo is unavailable."""
    avatar = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(avatar)
    draw.ellipse((0, 0, size - 1, size - 1), fill=THEME['primary'])

    initials = "MY"
    text_bbox = draw.textbbox((0, 0), initials)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    draw.text(
        ((size - text_width) / 2, (size - text_height) / 2 - 4),
        initials,
        fill='white',
    )
    return avatar

def prepare_profile_avatar(image, size=144):
    """Resize an image into a circular avatar."""
    image = image.convert('RGBA').resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new('L', (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, size - 1, size - 1), fill=255)

    avatar = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    avatar.paste(image, (0, 0), mask)
    return avatar

def load_profile_avatar(size=144):
    """Load the local About-page profile image from bundled assets."""
    try:
        avatar_path = get_asset_path("needyamin.jpg")
        if avatar_path.exists():
            return prepare_profile_avatar(Image.open(avatar_path), size=size)
    except Exception:
        pass
    return create_default_profile_avatar(size=size)

def create_link_label(master, text, url, bg):
    """Create a clickable link label."""
    link = tk.Label(
        master,
        text=text,
        font=('Segoe UI', 10, 'underline'),
        fg=THEME['primary'],
        bg=bg,
        cursor='hand2',
        anchor='w',
        justify='left',
    )
    link.bind('<Button-1>', lambda _event: webbrowser.open(url))
    return link

def close_about_window():
    """Close the custom About dialog."""
    global about_window
    if about_window and about_window.winfo_exists():
        about_window.destroy()
    about_window = None

def show_about_window():
    """Show a rich About window using the author's public profile information."""
    global about_window

    if about_window and about_window.winfo_exists():
        about_window.deiconify()
        center_window(about_window, root)
        about_window.lift()
        about_window.focus_force()
        return

    about_window = tk.Toplevel(root)
    about_window.title("About Us")
    about_window.geometry("700x500")
    about_window.minsize(640, 460)
    about_window.configure(bg=THEME['bg'])
    about_window.transient(root)
    about_window.protocol("WM_DELETE_WINDOW", close_about_window)
    apply_window_icon(about_window, app_id="needyamin.media_downloader")

    outer = tk.Frame(about_window, bg=THEME['bg'])
    outer.pack(fill='both', expand=True, padx=24, pady=24)

    header_card = tk.Frame(outer, bg=THEME['light_gray'], bd=1, relief='solid')
    header_card.pack(fill='x', pady=(0, 18))

    avatar_source = load_profile_avatar()
    avatar_photo = ImageTk.PhotoImage(avatar_source)
    avatar_label = tk.Label(header_card, image=avatar_photo, bg=THEME['light_gray'])
    avatar_label.image = avatar_photo
    avatar_label.pack(side='left', padx=20, pady=20)

    info_frame = tk.Frame(header_card, bg=THEME['light_gray'])
    info_frame.pack(fill='both', expand=True, padx=(0, 20), pady=20)

    tk.Label(
        info_frame,
        text=AUTHOR_PROFILE['name'],
        font=('Segoe UI', 20, 'bold'),
        bg=THEME['light_gray'],
        fg=THEME['fg'],
        anchor='w',
    ).pack(anchor='w')

    tk.Label(
        info_frame,
        text=AUTHOR_PROFILE['role'],
        font=('Segoe UI', 11),
        bg=THEME['light_gray'],
        fg=THEME['fg'],
        anchor='w',
    ).pack(anchor='w', pady=(4, 2))

    tk.Label(
        info_frame,
        text=AUTHOR_PROFILE['location'],
        font=('Segoe UI', 10),
        bg=THEME['light_gray'],
        fg=THEME['gray'],
        anchor='w',
    ).pack(anchor='w', pady=(0, 8))

    tk.Label(
        info_frame,
        text=AUTHOR_PROFILE['bio'],
        font=('Segoe UI', 10),
        bg=THEME['light_gray'],
        fg=THEME['fg'],
        anchor='w',
        justify='left',
        wraplength=430,
    ).pack(anchor='w')

    details_card = tk.Frame(outer, bg='white', bd=1, relief='solid')
    details_card.pack(fill='both', expand=True)

    tk.Label(
        details_card,
        text="Profile Links",
        font=('Segoe UI', 13, 'bold'),
        bg='white',
        fg=THEME['fg'],
    ).pack(anchor='w', padx=20, pady=(18, 10))

    links_frame = tk.Frame(details_card, bg='white')
    links_frame.pack(fill='x', padx=20)

    for label, url in [
        ("GitHub", AUTHOR_PROFILE['github']),
        ("Website", AUTHOR_PROFILE['website']),
        ("ORCID", AUTHOR_PROFILE['orcid']),
        ("Facebook", AUTHOR_PROFILE['facebook']),
    ]:
        row = tk.Frame(links_frame, bg='white')
        row.pack(fill='x', pady=4)
        tk.Label(
            row,
            text=f"{label}:",
            font=('Segoe UI', 10, 'bold'),
            bg='white',
            fg=THEME['fg'],
            width=10,
            anchor='w',
        ).pack(side='left')
        create_link_label(row, url, url, 'white').pack(side='left', fill='x', expand=True)

    description = tk.Label(
        details_card,
        text=(
            "Media Downloader is created and maintained by Md. Yamin Hossain. "
            "This open-source desktop app focuses on simple media tools with a clean user experience."
        ),
        font=('Segoe UI', 10),
        bg='white',
        fg=THEME['fg'],
        justify='left',
        wraplength=620,
    )
    description.pack(anchor='w', padx=20, pady=(18, 12))

    button_row = tk.Frame(details_card, bg='white')
    button_row.pack(fill='x', padx=20, pady=(0, 18))

    tk.Button(
        button_row,
        text="Visit GitHub",
        bg=THEME['primary'],
        fg='white',
        activebackground=THEME['secondary'],
        activeforeground='white',
        relief='flat',
        cursor='hand2',
        padx=16,
        pady=7,
        command=lambda: webbrowser.open(AUTHOR_PROFILE['github']),
    ).pack(side='left')

    tk.Button(
        button_row,
        text="Close",
        bg=THEME['light_gray'],
        fg=THEME['fg'],
        activebackground=THEME['border'],
        activeforeground=THEME['fg'],
        relief='flat',
        cursor='hand2',
        padx=16,
        pady=7,
        command=close_about_window,
    ).pack(side='right')

    about_window.after_idle(lambda: center_window(about_window, root))

def open_converter():
    """Open the converter from the downloader menu bar."""
    try:
        from desktop_tools.app.converter_app import open_converter_window

        converter_window = open_converter_window(root)
        if converter_window is not None:
            log("Opened Media Converter")
    except Exception as e:
        log(f"Error opening converter: {e}")
        messagebox.showerror("Converter Error", f"Could not open the converter:\n{e}")

def open_background_remover():
    """Open the background remover from the downloader menu bar."""
    try:
        from desktop_tools.app.background_remover_app import open_background_remover as launch_background_remover

        remover_window = launch_background_remover(root)
        if remover_window is not None:
            log("Opened Image Background Remover")
    except Exception as e:
        log(f"Error opening background remover: {e}")
        messagebox.showerror("Background Remover Error", f"Could not open the background remover:\n{e}")

def open_screenshot_studio():
    """Open YShoot from the downloader menu bar."""
    try:
        from desktop_tools.app.screenshot_app import open_screenshot_studio as launch_screenshot_studio

        screenshot_window = launch_screenshot_studio(root)
        if screenshot_window is not None:
            log("Opened YShoot")
    except Exception as e:
        log(f"Error opening screenshot studio: {e}")
        messagebox.showerror("YShoot Error", f"Could not open YShoot:\n{e}")

def trigger_screenshot_studio(event=None):
    """Open YShoot from the GUI or keyboard shortcut."""
    open_screenshot_studio()
    if event is not None:
        return "break"

def open_yscreenrecorder():
    """Open YScreenRecorder from the downloader menu bar."""
    try:
        from desktop_tools.app.yscreenrecorder_app import open_yscreenrecorder as launch_yscreenrecorder

        recorder_window = launch_yscreenrecorder(root)
        if recorder_window is not None:
            log("Opened YScreenRecorder")
    except Exception as e:
        log(f"Error opening YScreenRecorder: {e}")
        messagebox.showerror("YScreenRecorder Error", f"Could not open YScreenRecorder:\n{e}")

def trigger_yscreenrecorder(event=None):
    """Open YScreenRecorder from the GUI or keyboard shortcut."""
    open_yscreenrecorder()
    if event is not None:
        return "break"

def persist_max_files_value(event=None):
    """Normalize and save the playlist max-files value."""
    sanitized_value = current_max_files_value()
    if 'max_files_entry' in globals():
        max_files_entry.delete(0, tk.END)
        max_files_entry.insert(0, sanitized_value)
    save_app_settings()
    if event and getattr(event, 'keysym', None) == 'Return':
        return 'break'

def on_playlist_toggle():
    """Keep playlist UI state and saved settings in sync."""
    if 'max_files_entry' in globals():
        max_files_entry.configure(state='normal' if download_playlist.get() else 'disabled')
    save_app_settings()

def update_quality_settings(quality_type, value):
    """Update quality settings and log the change."""
    global quality_settings
    if quality_type in quality_settings:
        quality_settings[quality_type] = value
        log(f"Updated {quality_type} to: {value}")
        # Update status label to show current settings
        if 'status_label' in globals():
            status_label.config(text=f"Quality settings updated: {quality_type}={value}")
        save_app_settings()

def on_video_quality_change(*args):
    value = video_quality_var.get()
    quality_settings['video_quality'] = value
    log(f"Video quality changed to: {value}")
    update_quality_settings('video_quality', value)

def on_audio_quality_change(*args):
    value = audio_quality_var.get()
    quality_settings['audio_quality'] = value
    log(f"Audio quality changed to: {value}")
    update_quality_settings('audio_quality', value)

def on_format_change(*args):
    value = format_var.get()
    quality_settings['format'] = value
    log(f"Format changed to: {value}")
    update_quality_settings('format', value)

def is_site_download_running():
    """Return True when a yt-dlp download thread is active."""
    return current_download_thread is not None and current_download_thread.is_alive()

def direct_download_state():
    """Return the current direct-download task state."""
    if direct_download_task is None:
        return "idle"
    return getattr(direct_download_task, "state", "idle")

def is_direct_download_active():
    """Return True when a direct download is downloading or paused."""
    return direct_download_state() in {"probing", "downloading", "paused"}

def show_action_button(widget):
    """Show an action button using its stored layout options."""
    try:
        grid_kwargs = getattr(widget, "_grid_kwargs", None)
        pack_kwargs = getattr(widget, "_pack_kwargs", None)
        if grid_kwargs:
            if widget.winfo_manager() != 'grid':
                widget.grid(**grid_kwargs)
            else:
                widget.grid_configure(**grid_kwargs)
            return
        if pack_kwargs:
            if widget.winfo_manager() != 'pack':
                widget.pack(**pack_kwargs)
            else:
                widget.pack_configure(**pack_kwargs)
    except Exception:
        pass

def hide_action_button(widget):
    """Hide an action button without losing its layout metadata."""
    try:
        if widget.winfo_manager() == 'grid':
            widget.grid_remove()
        elif widget.winfo_manager() == 'pack':
            widget.pack_forget()
    except Exception:
        pass

def refresh_action_rows():
    """Keep the primary row full width and the secondary row centered when visible."""
    try:
        if 'primary_actions_row' in globals():
            if primary_actions_row.winfo_manager() != 'grid':
                primary_actions_row.grid(row=0, column=0, sticky="ew")

        if 'secondary_actions_row' in globals():
            secondary_visible = any(
                name in globals() and globals()[name].winfo_manager() in {'pack', 'grid'}
                for name in ('pause_resume_btn', 'cancel_btn')
            )
            if secondary_visible:
                if secondary_actions_row.winfo_manager() != 'grid':
                    secondary_actions_row.grid(row=1, column=0, pady=(10, 0))
            else:
                secondary_actions_row.grid_remove()
    except Exception:
        pass

def show_progress_section(mode):
    """Show only the requested progress section."""
    section_names = {
        "site": ("site_progress_title", "progress_label", "progress"),
        "direct": ("direct_progress_title", "direct_progress_label", "direct_progress"),
    }

    try:
        for section_mode, widget_names in section_names.items():
            for widget_name in widget_names:
                if widget_name not in globals():
                    continue
                widget = globals()[widget_name]
                if section_mode == mode:
                    grid_kwargs = getattr(widget, "_grid_kwargs", None)
                    if grid_kwargs:
                        if widget.winfo_manager() != 'grid':
                            widget.grid(**grid_kwargs)
                        else:
                            widget.grid_configure(**grid_kwargs)
                else:
                    if widget.winfo_manager() == 'grid':
                        widget.grid_remove()
    except Exception:
        pass

def enable_buttons():
    """Enable the main download buttons and hide transient controls."""
    try:
        if 'video_btn' in globals():
            video_btn.config(state='normal')
            show_action_button(video_btn)
        if 'audio_btn' in globals():
            audio_btn.config(state='normal')
            show_action_button(audio_btn)
        if 'direct_btn' in globals():
            direct_btn.config(state='normal')
            show_action_button(direct_btn)
        if 'pause_resume_btn' in globals():
            pause_resume_btn.config(state='normal', text="⏸ Pause Direct")
            hide_action_button(pause_resume_btn)
        if 'cancel_btn' in globals():
            cancel_btn.config(state='normal', text="✖ Cancel Download")
            hide_action_button(cancel_btn)
        if not is_site_download_running() and not is_direct_download_active():
            show_progress_section(None)
        refresh_action_rows()
    except Exception:
        pass

def disable_buttons():
    """Disable the standard download buttons while a site download is active."""
    try:
        if 'video_btn' in globals():
            video_btn.config(state='disabled')
            show_action_button(video_btn)
        if 'audio_btn' in globals():
            audio_btn.config(state='disabled')
            show_action_button(audio_btn)
        if 'direct_btn' in globals():
            direct_btn.config(state='disabled')
            show_action_button(direct_btn)
        if 'pause_resume_btn' in globals():
            hide_action_button(pause_resume_btn)
        if 'cancel_btn' in globals():
            cancel_btn.config(state='normal', text="✖ Cancel Download")
            show_action_button(cancel_btn)
        refresh_action_rows()
    except Exception:
        pass

def update_direct_download_controls():
    """Keep direct-download controls in sync with the current task state."""
    state = direct_download_state()
    try:
        if state in {"probing", "downloading"}:
            if 'video_btn' in globals():
                video_btn.config(state='disabled')
            if 'audio_btn' in globals():
                audio_btn.config(state='disabled')
            if 'direct_btn' in globals():
                direct_btn.config(state='disabled')
            if 'pause_resume_btn' in globals():
                pause_resume_btn.config(state='normal', text="⏸ Pause Direct")
                show_action_button(pause_resume_btn)
            if 'cancel_btn' in globals():
                cancel_btn.config(state='normal', text="✖ Cancel Download")
                show_action_button(cancel_btn)
        elif state == "paused":
            if 'video_btn' in globals():
                video_btn.config(state='disabled')
            if 'audio_btn' in globals():
                audio_btn.config(state='disabled')
            if 'direct_btn' in globals():
                direct_btn.config(state='disabled')
            if 'pause_resume_btn' in globals():
                pause_resume_btn.config(state='normal', text="▶ Resume Direct")
                show_action_button(pause_resume_btn)
            if 'cancel_btn' in globals():
                cancel_btn.config(state='normal', text="✖ Cancel Download")
                show_action_button(cancel_btn)
        elif not is_site_download_running():
            enable_buttons()
            return
        refresh_action_rows()
    except Exception:
        pass

def direct_download_log(message):
    """Log direct-download messages with a dedicated prefix."""
    log(f"[Direct] {message}")

def direct_download_progress(percent, message):
    """Marshal direct-download progress updates back to Tk."""
    def _apply():
        try:
            show_progress_section("direct")
            if percent is not None:
                direct_progress['value'] = max(0, min(100, float(percent)))
            direct_progress_label.config(text=message)
            status_label.config(text=message)
        except Exception as exc:
            log(f"Error updating direct download progress: {exc}")

    ui_queue.put(_apply)

def handle_direct_download_state_change(state, payload=None):
    """Handle direct-download lifecycle events on the Tk thread."""
    global direct_download_task

    def _apply():
        global direct_download_task
        update_direct_download_controls()

        if state == "completed":
            final_path = Path(payload) if payload else direct_output_dir
            direct_download_task = None
            update_direct_progress(100, f"Direct download complete: {final_path.name}")
            enable_buttons()
            try:
                open_path_in_file_manager(final_path.parent)
            except Exception as exc:
                log(f"Error opening direct-download folder: {exc}")
        elif state == "cancelled":
            direct_download_task = None
            update_direct_progress(0, "Direct download cancelled")
            enable_buttons()
        elif state == "paused":
            update_direct_progress(direct_progress['value'], "Direct download paused")
        elif state == "error":
            error_details = str(payload or "Unknown direct download error")
            direct_download_task = None
            show_error_dialog(
                "Direct Download Error",
                "The direct file download could not be completed.",
                details=error_details,
                suggestion=(
                    "Use a normal file/media URL for direct downloads. For video pages and streaming sites, use "
                    "the Video or Audio download buttons instead."
                ),
            )
            update_direct_progress(0, "Direct file download idle")
            enable_buttons()

    ui_queue.put(_apply)

def start_direct_download():
    """Start a direct file download in the same main window."""
    global direct_download_task

    if is_site_download_running():
        messagebox.showinfo("Download Busy", "A site download is already running. Please wait for it to finish first.")
        return

    if direct_download_task is not None and direct_download_state() == "paused":
        toggle_direct_pause_resume()
        return

    if direct_download_task is not None and direct_download_task.is_busy():
        messagebox.showinfo("Download Busy", "A direct download is already running.")
        return

    url = url_entry.get().strip()
    if not url:
        messagebox.showerror("Error", "Please enter a direct file URL")
        return

    if not url.startswith(('http://', 'https://')):
        messagebox.showerror("Error", "Please enter a valid URL starting with http:// or https://")
        return

    blocked_domain = get_disabled_domain_match(url)
    if blocked_domain:
        show_error_dialog(
            "Download Blocked",
            "This domain is disabled in the application settings.",
            details=f"Blocked domain match: {blocked_domain}\nURL: {url}",
            suggestion="Remove the domain from app_flags.json -> disabled_domains to allow it again.",
        )
        return

    if not verify_output_directories():
        messagebox.showerror("Error", "Failed to prepare output directories for direct downloads.")
        return

    direct_download_task = DirectDownloadTask(
        url=url,
        output_dir=direct_output_dir,
        log_callback=direct_download_log,
        progress_callback=direct_download_progress,
        state_callback=handle_direct_download_state_change,
    )

    direct_download_task.state = "probing"
    update_direct_progress(0, "Preparing direct download...")
    update_direct_download_controls()
    try:
        direct_download_task.start()
    except Exception as exc:
        direct_download_task = None
        show_error_dialog(
            "Direct Download Error",
            "The direct file download could not be started.",
            details=str(exc),
            suggestion="Try another direct media/file URL, or use the Video or Audio buttons for site downloads.",
        )

def toggle_direct_pause_resume():
    """Pause or resume the current direct download."""
    if direct_download_task is None:
        return

    state = direct_download_state()
    if state == "downloading":
        direct_download_task.pause()
    elif state == "paused":
        update_direct_progress(direct_progress['value'], "Resuming direct download...")
        direct_download_task.resume()
        update_direct_download_controls()

def threaded_download(is_audio):
    """Start the existing yt-dlp downloader in a separate thread."""
    global current_download_thread

    if is_direct_download_active():
        messagebox.showinfo("Download Busy", "A direct download is already active. Pause or cancel it first.")
        return

    disable_buttons()

    def download_thread():
        global current_download_thread
        try:
            download_media(is_audio)
        finally:
            ui_queue.put(enable_buttons)
            current_download_thread = None

    current_download_thread = threading.Thread(target=download_thread, daemon=True)
    current_download_thread.start()

def should_check_for_updates():
    """Determine if we should check for updates (once per day)."""
    global FORCE_UPDATE_CHECK
    try:
        debug_log("Checking if update check is needed.")
        
        # If force check is enabled, always check
        if FORCE_UPDATE_CHECK:
            debug_log("Force update check enabled, will check for updates.")
            return True
            
        if not UPDATE_CHECK_FILE.exists():
            debug_log("Update check file not found, will check for updates.")
            return True
        
        # Read last check time
        with open(UPDATE_CHECK_FILE, 'r') as f:
            last_check = float(f.read().strip())
        
        time_since_last_check = time.time() - last_check
        debug_log(f"Time since last check: {time_since_last_check/3600:.2f} hours")
        
        # Check if 24 hours have passed
        should_check = time_since_last_check >= 86400  # 24 hours in seconds
        debug_log(f"Should check for updates: {should_check}")
        return should_check
    except Exception as e:
        log(f"Error checking update timestamp: {e}")
        return True

def update_check_timestamp():
    """Update the timestamp of last update check."""
    try:
        UPDATE_CHECK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(UPDATE_CHECK_FILE, 'w') as f:
            f.write(str(time.time()))
    except:
        pass

def app_update_log(message):
    """Always show app update activity in the main log."""
    normalized_message = str(message).strip()
    if normalized_message:
        log(f"[App Update] {normalized_message}")

def show_info_threadsafe(title, message):
    """Show an info message from any thread."""
    if threading.current_thread() is threading.main_thread():
        messagebox.showinfo(title, message)
    elif 'ui_queue' in globals():
        ui_queue.put(lambda: messagebox.showinfo(title, message))

def show_error_threadsafe(title, message):
    """Show an error message from any thread."""
    if threading.current_thread() is threading.main_thread():
        messagebox.showerror(title, message)
    elif 'ui_queue' in globals():
        ui_queue.put(lambda: messagebox.showerror(title, message))

def get_app_update_dir():
    """Return the directory used for staged application updates."""
    APP_UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    return APP_UPDATE_DIR

def build_background_update_script(installer_path):
    """Create a helper script that installs an update after the app exits."""
    update_dir = get_app_update_dir()
    script_path = update_dir / f"install_update_{int(time.time())}.cmd"
    installer_log_path = update_dir / "installer-update.log"
    current_pid = os.getpid()
    current_executable = Path(sys.executable).resolve()

    script_contents = "\n".join([
        "@echo off",
        "setlocal",
        f'set "APP_PID={current_pid}"',
        f'set "INSTALLER={installer_path}"',
        f'set "TARGET_EXE={current_executable}"',
        f'set "INSTALL_LOG={installer_log_path}"',
        "",
        ":wait_for_app_exit",
        'tasklist /FI "PID eq %APP_PID%" 2>NUL | find "%APP_PID%" >NUL',
        "if not errorlevel 1 (",
        "  timeout /t 1 /nobreak >NUL",
        "  goto wait_for_app_exit",
        ")",
        "",
        'start /wait "" "%INSTALLER%" /SP- /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /LOG="%INSTALL_LOG%"',
        'if exist "%TARGET_EXE%" start "" "%TARGET_EXE%"',
        'del "%INSTALLER%" >NUL 2>&1',
        'del "%~f0" >NUL 2>&1',
    ]) + "\n"
    script_path.write_text(script_contents, encoding="utf-8")
    return script_path

def launch_background_update_installer(installer_path):
    """Launch a detached helper that silently installs the downloaded update."""
    script_path = build_background_update_script(installer_path)
    creationflags = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )
    subprocess.Popen(
        ["cmd", "/c", str(script_path)],
        creationflags=creationflags,
    )

def parse_version_parts(version):
    """Convert a version string like v1.2.3 into comparable integer parts."""
    version = str(version).strip()
    if version.lower().startswith('v'):
        version = version[1:]

    version = ''.join(char for char in version if char.isdigit() or char == '.')
    if not version:
        return [0]

    parts = []
    for part in version.split('.'):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return parts


def get_version_comparison_info(latest_version, current_version):
    """Return a clear comparison summary for update checks."""
    latest_version = str(latest_version).strip()
    current_version = str(current_version).strip()

    if not latest_version:
        return {
            "is_newer": False,
            "status": "missing_latest",
            "message": "Latest version is missing.",
        }

    if not current_version:
        return {
            "is_newer": True,
            "status": "missing_current",
            "message": f"Current version is missing, so {latest_version} is treated as newer.",
        }

    latest_parts = parse_version_parts(latest_version)
    current_parts = parse_version_parts(current_version)
    max_len = max(len(latest_parts), len(current_parts))
    latest_parts.extend([0] * (max_len - len(latest_parts)))
    current_parts.extend([0] * (max_len - len(current_parts)))

    if latest_parts > current_parts:
        return {
            "is_newer": True,
            "status": "newer",
            "message": f"{latest_version} is newer than {current_version}.",
        }

    if latest_parts < current_parts:
        return {
            "is_newer": False,
            "status": "older",
            "message": f"{latest_version} is older than {current_version}.",
        }

    return {
        "is_newer": False,
        "status": "equal",
        "message": f"Versions are equal ({current_version}).",
    }


def compare_versions(v1, v2):
    """Compare two version strings and return True if v1 > v2."""
    try:
        return get_version_comparison_info(v1, v2)["is_newer"]
    except Exception as e:
        print(f"Error comparing versions: {e}")
        return False

def check_updates_on_startup(user_initiated=False):
    """Check for app updates and install packaged releases in the background."""
    global FORCE_UPDATE_CHECK

    update_started = False
    performed_check = False

    try:
        debug_log("Update check process started.")
        print("\n=== UPDATE CHECK PROCESS STARTED ===")

        if not should_check_for_updates() and not user_initiated:
            debug_log("Skipping app update check because the last check was recent.")
            check_ffmpeg_update()
            return False

        performed_check = True
        app_update_log("Checking GitHub for a newer application release...")
        latest_release = check_for_updates()

        if latest_release:
            latest_version = latest_release.get('tag_name', '').lstrip('v')
            release_url = latest_release.get('html_url') or f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest"

            if is_packaged_runtime():
                app_update_log(f"New version {latest_version} detected. Starting background update.")
                set_status_threadsafe(f"Downloading app update {latest_version} in background...")
                update_started = download_and_install_update(latest_release, user_initiated=user_initiated)
            else:
                app_update_log(
                    f"New version {latest_version} detected, but automatic installation is only supported in the packaged app."
                )
                if user_initiated:
                    show_info_threadsafe(
                        "Source Build Detected",
                        "Automatic in-app installation is only supported for the packaged app.\n\n"
                        "The latest release page will open in your browser instead.",
                    )
                    webbrowser.open(release_url)
        else:
            if user_initiated:
                show_info_threadsafe("No Updates", "You have the latest version.")
            debug_log("No updates available.")

        if performed_check:
            update_check_timestamp()

        if not update_started:
            debug_log("Starting FFmpeg update check.")
            check_ffmpeg_update()

        debug_log("Update check process completed.")
        print("=== UPDATE CHECK PROCESS COMPLETED ===\n")
        return update_started

    except Exception as e:
        app_update_log(f"Error in update check process: {str(e)}")
        print(f"Error in update check process: {str(e)}")
        print(traceback.format_exc())

        if user_initiated:
            show_error_threadsafe(
                "Update Check Failed",
                f"Failed to check for updates: {str(e)}\n\nPlease check your internet connection.",
            )
        return False
    finally:
        FORCE_UPDATE_CHECK = False

def check_for_updates():
    """Check for updates on GitHub and return the latest version if available."""
    try:
        debug_log("Checking for updates.")
        print("\n=== CHECKING FOR UPDATES ===")
        print(f"Current version: {CURRENT_VERSION}")
        print(f"GitHub API URL: {GITHUB_API_URL}")
        print(f"Repository: {REPO_OWNER}/{REPO_NAME}")
        
        # Make the request with headers to avoid rate limiting
        headers = get_update_headers()
        
        print("Sending request to GitHub API...")
        response = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
        debug_log(f"GitHub API Response Status: {response.status_code}")
        print(f"GitHub API Response Status: {response.status_code}")
        
        if response.status_code != 200:
            debug_log(f"GitHub API Error: {response.text}")
            print(f"GitHub API Error: {response.text}")
            return None
            
        latest_release = response.json()
        
        # Check if there's a valid release
        if 'tag_name' not in latest_release:
            debug_log("No tag_name found in release.")
            print("No tag_name found in GitHub response")
            return None
            
        # Get the latest version number (strip v prefix if present)
        latest_version = latest_release.get('tag_name', '').lstrip('v')
        debug_log(f"Latest version on GitHub: {latest_version}")
        print(f"Latest version on GitHub: {latest_version}")
        
        if not latest_version:
            debug_log("Empty version tag found in release.")
            print("Empty version tag found in release")
            return None
            
        # Compare versions with detailed logging
        comparison_info = get_version_comparison_info(latest_version, CURRENT_VERSION)
        print(f"\n=== VERSION COMPARISON DETAILS ===")
        print(f"Current version: {CURRENT_VERSION}")
        print(f"Latest version: {latest_version}")
        print(f"Comparison summary: {comparison_info['message']}")
        print(f"Is update available: {'Yes' if comparison_info['is_newer'] else 'No'}")
        
        if comparison_info['is_newer']:
            log(f"New version {latest_version} is available!")
            print(f"✅ New version {latest_version} is available!")
            # Return the entire release data for use in download_and_install_update
            return latest_release
        else:
            debug_log("You have the latest version.")
            print("✓ You have the latest version")
            return None
    except requests.exceptions.RequestException as e:
        log(f"Network error checking for updates: {e}")
        print(f"Network error checking for updates: {e}")
        return None
    except Exception as e:
        log(f"Unexpected error checking for updates: {e}")
        print(f"Unexpected error checking for updates: {e}")
        print(traceback.format_exc())
        return None

def download_and_install_update(release, user_initiated=False):
    """Download and silently install the latest packaged release in the background."""
    try:
        print("\n=== DOWNLOADING UPDATE ===")
        
        # If release is a string (legacy calls), convert to new format
        if isinstance(release, str):
            print(f"Converting legacy version string: {release}")
            latest_version = release
            # We need to fetch the release data
            headers = get_update_headers()
            response = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
            if response.status_code != 200:
                raise Exception(f"Could not fetch release data: {response.status_code}")
            release = response.json()
        else:
            latest_version = release.get('tag_name', '').lstrip('v')
        
        print(f"Preparing to download version {latest_version}")

        if not is_packaged_runtime():
            return False

        assets = release.get('assets', [])
        print(f"Release has {len(assets)} assets")
        for asset in assets:
            print(f"Asset: {asset.get('name')} ({asset.get('content_type')})")

        installer_asset = get_preferred_update_asset(release, require_installer=True)
        if not installer_asset:
            raise Exception("No installer executable found in release assets")

        update_dir = get_app_update_dir()
        safe_version = re.sub(r'[^A-Za-z0-9._-]+', '_', latest_version or "latest")
        exe_path = update_dir / f"{safe_version}-{installer_asset['name']}"
        part_path = exe_path.with_suffix(exe_path.suffix + ".part")

        download_url = installer_asset['browser_download_url']
        print(f"Downloading from: {download_url}")
        app_update_log(f"Downloading update installer for version {latest_version}...")
        set_status_threadsafe(f"Downloading update {latest_version} in background...")

        response = requests.get(download_url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        last_logged_bucket = -1

        with open(part_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                downloaded += len(chunk)
                f.write(chunk)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    bucket = int(percent // 10)
                    if bucket > last_logged_bucket:
                        last_logged_bucket = bucket
                        app_update_log(
                            f"Download progress: {percent:.0f}% ({downloaded}/{total_size} bytes)"
                        )

        shutil.move(str(part_path), str(exe_path))
        print(f"Download complete: {exe_path}")
        app_update_log(f"Installer downloaded to: {exe_path}")
        app_update_log("Launching silent installer and restarting the app after update.")
        set_status_threadsafe("Installing downloaded update in background...")

        launch_background_update_installer(exe_path)
        ui_queue.put(lambda: root.after(800, root.quit))
        return True
            
    except Exception as e:
        error_msg = str(e)
        app_update_log(f"Error installing update: {error_msg}")
        print(f"Error installing update: {error_msg}")
        print(traceback.format_exc())
        if user_initiated:
            show_error_threadsafe("Update Error", f"Failed to install update: {error_msg}")
        else:
            set_status_threadsafe("App update failed")
        return False

def start_app_update_check(user_initiated=False):
    """Run the app update check in a single background worker."""
    global FORCE_UPDATE_CHECK, app_update_thread

    if user_initiated:
        FORCE_UPDATE_CHECK = True

    with app_update_lock:
        if app_update_thread is not None and app_update_thread.is_alive():
            app_update_log("An app update check is already running in the background.")
            if user_initiated:
                show_info_threadsafe("Update Check", "An update check is already running.")
            return False

        app_update_thread = threading.Thread(
            target=check_updates_on_startup,
            kwargs={"user_initiated": user_initiated},
            daemon=True,
        )
        app_update_thread.start()
        return True

def check_ffmpeg_update():
    """Check for FFmpeg updates and install them automatically in the background."""
    start_ffmpeg_background_sync(force_update=False, user_initiated=False)


def set_status_threadsafe(message):
    """Update the main status label safely from any thread."""
    normalized_message = str(message).strip()
    if not normalized_message:
        return

    if threading.current_thread() is threading.main_thread():
        if 'status_label' in globals():
            status_label.config(text=normalized_message)
        return

    if 'ui_queue' in globals():
        ui_queue.put(lambda msg=normalized_message: status_label.config(text=msg) if 'status_label' in globals() else None)


def apply_ffmpeg_runtime_paths(resolved_ffmpeg_path, resolved_ffprobe_path):
    """Store FFmpeg paths globally and wire them into yt-dlp."""
    global ffmpeg_path, ffprobe_path

    if not resolved_ffmpeg_path or not resolved_ffprobe_path:
        return False

    ffmpeg_path = str(resolved_ffmpeg_path)
    ffprobe_path = str(resolved_ffprobe_path)
    yt_dlp.postprocessor.ffmpeg.FFmpegPostProcessor.EXES = {
        'ffmpeg': ffmpeg_path,
        'ffprobe': ffprobe_path,
    }
    return True


def run_ffmpeg_background_sync(force_update=False, user_initiated=False):
    """Auto-find, auto-install, auto-configure, and auto-update FFmpeg in the background."""
    try:
        if user_initiated:
            ffmpeg_log("Manual install/update started in background.")
            set_status_threadsafe("Installing or updating FFmpeg in background...")
        else:
            ffmpeg_log("Automatic FFmpeg startup check started.")
            set_status_threadsafe("Checking FFmpeg in background...")

        resolved_ffmpeg_path, resolved_ffprobe_path, updated = update_managed_ffmpeg_if_needed(
            logger=ffmpeg_log,
            progress_callback=ffmpeg_log,
            force=force_update,
            extra_paths=[APP_DIR / "ffmpeg" / "ffmpeg.exe"],
        )

        if not apply_ffmpeg_runtime_paths(resolved_ffmpeg_path, resolved_ffprobe_path):
            raise Exception("FFmpeg is still not available after background setup")

        ffmpeg_log(f"FFmpeg configured successfully: {resolved_ffmpeg_path}")
        verify_output_directories()

        if updated:
            ffmpeg_log("FFmpeg updated automatically in background.")
        elif user_initiated:
            ffmpeg_log("FFmpeg is ready.")
        else:
            ffmpeg_log("FFmpeg is ready for downloads.")

        set_status_threadsafe("Ready to download")
    except Exception as exc:
        ffmpeg_log(f"Error initializing FFmpeg: {exc}")
        print(f"Error initializing FFmpeg: {exc}")
        print(traceback.format_exc())
        set_status_threadsafe("Error: FFmpeg initialization failed")


def start_ffmpeg_background_sync(force_update=False, user_initiated=False):
    """Start a single FFmpeg background worker if one is not already running."""
    global ffmpeg_sync_thread

    with ffmpeg_sync_lock:
        if ffmpeg_sync_thread is not None and ffmpeg_sync_thread.is_alive():
            if user_initiated:
                log("FFmpeg setup is already running in background.")
                set_status_threadsafe("FFmpeg is already being prepared in background...")
            return False

        ffmpeg_sync_thread = threading.Thread(
            target=run_ffmpeg_background_sync,
            kwargs={"force_update": force_update, "user_initiated": user_initiated},
            daemon=True,
        )
        ffmpeg_sync_thread.start()
        return True


def force_install_or_update_ffmpeg():
    """Force a background FFmpeg install/update from the Settings menu."""
    started = start_ffmpeg_background_sync(force_update=True, user_initiated=True)
    if started:
        messagebox.showinfo(
            "FFmpeg Background Update",
            "FFmpeg install/update started in the background.\n\nYou can keep using the app while it finishes.",
        )

# Create menubar
menubar = tk.Menu(root)
root.config(menu=menubar)

# File Menu
file_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Open Folder", command=open_download_folder)
file_menu.add_command(label="Choose Folder", command=choose_download_folder)
file_menu.add_separator()
file_menu.add_checkbutton(
    label="Auto-start",
    variable=auto_start_var,
    command=toggle_auto_start,
    state='normal' if IS_WINDOWS else 'disabled'
)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.quit)

# Settings Menu
settings_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Settings", menu=settings_menu)

# Video Quality Submenu
video_quality_menu = tk.Menu(settings_menu, tearoff=0)
settings_menu.add_cascade(label="Video Quality", menu=video_quality_menu)
video_quality_menu.add_radiobutton(label="Best Quality", variable=video_quality_var, value='best', command=lambda: on_video_quality_change())
video_quality_menu.add_radiobutton(label="1080p", variable=video_quality_var, value='1080', command=lambda: on_video_quality_change())
video_quality_menu.add_radiobutton(label="720p", variable=video_quality_var, value='720', command=lambda: on_video_quality_change())
video_quality_menu.add_radiobutton(label="480p", variable=video_quality_var, value='480', command=lambda: on_video_quality_change())
video_quality_menu.add_radiobutton(label="360p", variable=video_quality_var, value='360', command=lambda: on_video_quality_change())

# Audio Quality Submenu
audio_quality_menu = tk.Menu(settings_menu, tearoff=0)
settings_menu.add_cascade(label="Audio Quality", menu=audio_quality_menu)
audio_quality_menu.add_radiobutton(label="320 kbps", variable=audio_quality_var, value='320', command=lambda: on_audio_quality_change())
audio_quality_menu.add_radiobutton(label="256 kbps", variable=audio_quality_var, value='256', command=lambda: on_audio_quality_change())
audio_quality_menu.add_radiobutton(label="192 kbps", variable=audio_quality_var, value='192', command=lambda: on_audio_quality_change())
audio_quality_menu.add_radiobutton(label="128 kbps", variable=audio_quality_var, value='128', command=lambda: on_audio_quality_change())
audio_quality_menu.add_radiobutton(label="96 kbps", variable=audio_quality_var, value='96', command=lambda: on_audio_quality_change())

# Format Submenu
format_menu = tk.Menu(settings_menu, tearoff=0)
settings_menu.add_cascade(label="Format", menu=format_menu)
format_menu.add_radiobutton(label="MP4", variable=format_var, value='mp4', command=lambda: on_format_change())
format_menu.add_radiobutton(label="WebM", variable=format_var, value='webm', command=lambda: on_format_change())
format_menu.add_radiobutton(label="MKV", variable=format_var, value='mkv', command=lambda: on_format_change())
settings_menu.add_separator()
settings_menu.add_command(label="Install / Update FFmpeg", command=force_install_or_update_ffmpeg)

# Tools Menu
tools_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Tools", menu=tools_menu)
tools_menu.add_command(label="Video Converter", command=open_converter)
tools_menu.add_command(label="BG Remover", command=open_background_remover)
tools_menu.add_command(label="YShoot", accelerator=SCREENSHOT_HOTKEY_LABEL, command=open_screenshot_studio)
tools_menu.add_command(label="YScreenRecorder", accelerator=SCREENRECORDER_HOTKEY_LABEL, command=open_yscreenrecorder)

# Help Menu
help_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Help", menu=help_menu)
help_menu.add_command(label="About Us", command=show_about_window)
help_menu.add_command(label="Check for Updates", command=lambda: force_check_updates())
help_menu.add_separator()
help_menu.add_command(label="Report Issue", 
    command=lambda: webbrowser.open("https://github.com/needyamin/media-downloader/issues"))

# Add debug command to Help menu
help_menu.add_separator()
help_menu.add_command(label="Debug Update System", command=debug_update_check)

# Add function to force update check
def force_check_updates():
    """Force check for updates when user clicks menu item"""
    log("Forcing update check...")
    set_status_threadsafe("Checking for app updates in background...")
    print("\n=== FORCING UPDATE CHECK ===")
    start_app_update_check(user_initiated=True)

# Custom Widget Classes
class ModernButton(ttk.Button):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(style='Modern.TButton')

class ModernEntry(tk.Entry):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(
            relief='flat',
            font=('Segoe UI', 10),
            bg=THEME['light_gray'],
            fg=THEME['fg'],
            insertbackground=THEME['primary']
        )
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Cut", command=lambda: self.event_generate('<<Cut>>'))
        self.context_menu.add_command(label="Copy", command=lambda: self.event_generate('<<Copy>>'))
        self.context_menu.add_command(label="Paste", command=lambda: self.event_generate('<<Paste>>'))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Select All", command=self.select_all)
        self.bind('<FocusIn>', self.on_focus_in)
        self.bind('<FocusOut>', self.on_focus_out)
        self.bind('<Button-3>', self.show_context_menu)
        
    def on_focus_in(self, e):
        self.configure(bg='white')
        
    def on_focus_out(self, e):
        self.configure(bg=THEME['light_gray'])

    def select_all(self):
        self.focus_set()
        self.selection_range(0, tk.END)
        self.icursor(tk.END)

    def show_context_menu(self, event):
        self.focus_set()
        try:
            self.icursor(f"@{event.x}")
        except Exception:
            pass
        self.context_menu.tk_popup(event.x_root, event.y_root)
        self.context_menu.grab_release()
        return 'break'

class ModernCheckbutton(tk.Checkbutton):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(
            bg=THEME['bg'],
            fg=THEME['fg'],
            activebackground=THEME['bg'],
            activeforeground=THEME['primary'],
            selectcolor=THEME['light_gray'],
            font=('Segoe UI', 10),
            anchor='w',
            justify='left'
        )

# Create a queue for thread-safe UI updates
ui_queue = queue.Queue()
last_visible_log_message = None

def log(message, show_console=True):
    """Log a message to the output box and status label if available, or queue it for later."""
    global last_visible_log_message
    try:
        normalized_message = str(message).strip()
        if not normalized_message:
            return
        if show_console and DEBUG_MODE:
            print(f"[Yamin Downloader] {normalized_message}")  # Always show in console
        if threading.current_thread() is not threading.main_thread():
            if 'ui_queue' in globals() and 'output_box' in globals() and 'status_label' in globals():
                ui_queue.put(lambda msg=normalized_message: log(msg, show_console=False))
            else:
                early_log_queue.put(normalized_message)
            return
        if 'output_box' in globals() and 'status_label' in globals():
            if normalized_message == last_visible_log_message:
                status_label.config(text=normalized_message)
                return
            output_box.config(state='normal')
            # Insert at the beginning (index 1.0) instead of the end
            output_box.insert('1.0', normalized_message + '\n')
            line_count = int(float(output_box.index('end-1c')))
            if line_count > MAX_LOG_LINES:
                output_box.delete(f"{MAX_LOG_LINES + 1}.0", tk.END)
            # Auto-scroll to the top
            output_box.see('1.0')
            output_box.config(state='disabled')
            status_label.config(text=normalized_message)
            last_visible_log_message = normalized_message
        else:
            early_log_queue.put(normalized_message)
    except:
        if DEBUG_MODE:
            print(f"[Yamin Downloader] {normalized_message}")  # Fallback to console output

def process_early_logs():
    """Process any queued log messages once the GUI is ready."""
    global last_visible_log_message
    while not early_log_queue.empty():
        try:
            message = early_log_queue.get_nowait()
            if 'output_box' in globals() and 'status_label' in globals():
                if message == last_visible_log_message:
                    status_label.config(text=message)
                    continue
                output_box.config(state='normal')
                # Insert at the beginning (index 1.0) instead of the end
                output_box.insert('1.0', message + '\n')
                # Auto-scroll to the top
                output_box.see('1.0')
                output_box.config(state='disabled')
                status_label.config(text=message)
                last_visible_log_message = message
        except queue.Empty:
            break

# Set window icon
try:
    ICON_PATH = apply_window_icon(root, app_id="needyamin.media_downloader")
except Exception as e:
    messagebox.showwarning("Icon Error", f"Could not load window icon: {e}")

# Make window resizable
root.resizable(True, True)

# Configure grid weights for responsive layout
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)

# Create main container
main_container = tk.Frame(root, bg=THEME['bg'])
main_container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
main_container.grid_rowconfigure(1, weight=1)
main_container.grid_columnconfigure(0, weight=1)

# Header Frame
header_frame = tk.Frame(main_container, bg=THEME['bg'])
header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))

# Logo and Title
try:
    logo = Image.open(ICON_PATH)
    logo = logo.resize((48, 48), Image.Resampling.LANCZOS)
    logo_photo = ImageTk.PhotoImage(logo)
    logo_label = tk.Label(header_frame, image=logo_photo, bg=THEME['bg'])
    logo_label.image = logo_photo
    logo_label.pack(side='left', padx=(0, 10))
except:
    pass

title_label = tk.Label(
    header_frame,
    text="Media Downloader",
    font=('Segoe UI', 24, 'bold'),
    bg=THEME['bg'],
    fg=THEME['primary']
)
title_label.pack(side='left')

version_label = tk.Label(
    header_frame,
    text=f"v{CURRENT_VERSION}",
    font=('Segoe UI', 10),
    bg=THEME['bg'],
    fg=THEME['gray']
)
version_label.pack(side='left', padx=(10, 0), pady=(10, 0))

# Main Content Frame
main_frame = tk.Frame(main_container, bg=THEME['bg'])
main_frame.grid(row=1, column=0, sticky="nsew")
main_frame.grid_rowconfigure(4, weight=1)
main_frame.grid_columnconfigure(0, weight=1)

# URL Input Section
url_frame = tk.Frame(main_frame, bg=THEME['bg'])
url_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
url_frame.grid_columnconfigure(0, weight=1)  # Make the URL entry expand

url_label = tk.Label(
    url_frame,
    text="Enter Media URL:",
    font=('Segoe UI', 12, 'bold'),
    bg=THEME['bg'],
    fg=THEME['fg']
)
url_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

url_entry = ModernEntry(url_frame)
url_entry.grid(row=1, column=0, sticky="ew", ipady=8)

download_path_frame = tk.Frame(url_frame, bg=THEME['bg'])
download_path_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
download_path_frame.grid_columnconfigure(1, weight=1)

tk.Label(
    download_path_frame,
    text="Save to:",
    font=('Segoe UI', 10, 'bold'),
    bg=THEME['bg'],
    fg=THEME['fg']
).grid(row=0, column=0, sticky="w", padx=(0, 8))

download_path_label = tk.Label(
    download_path_frame,
    textvariable=download_path_var,
    font=('Segoe UI', 9),
    bg=THEME['bg'],
    fg=THEME['gray'],
    anchor='w',
    justify='left',
    wraplength=420
)
download_path_label.grid(row=0, column=1, sticky="ew")

change_folder_btn = tk.Button(
    download_path_frame,
    text="Change Folder",
    bg=THEME['light_gray'],
    fg=THEME['fg'],
    activebackground=THEME['border'],
    activeforeground=THEME['fg'],
    relief='flat',
    cursor='hand2',
    padx=12,
    pady=4,
    command=choose_download_folder
)
change_folder_btn.grid(row=0, column=2, padx=(10, 0))

# Status Label
status_label = tk.Label(
    main_frame,
    text="Initializing...",
    font=('Segoe UI', 9),
    bg=THEME['border'],
    fg=THEME['fg']
)
status_label.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 10))

# Process any early logs
process_early_logs()

# Initialize FFmpeg automatically when the GUI opens
def initialize_ffmpeg():
    """Kick off automatic FFmpeg preparation when the GUI opens."""
    start_ffmpeg_background_sync(force_update=False, user_initiated=False)

def verify_output_directories():
    """Verify that output directories exist and create them if they don't."""
    try:
        debug_log("Verifying output directories.")
        print("\n=== VERIFYING OUTPUT DIRECTORIES ===")
        
        # Check for invalid characters in paths (Windows restrictions)
        invalid_chars = {'<', '>', ':', '"', '/', '\\', '|', '?', '*'}
        for path in [downloads_path, video_output_dir, audio_output_dir, playlist_output_dir, direct_output_dir]:
            path_str = str(path)
            print(f"Checking path: {path_str}")
            
            # Skip the drive anchor so normal Windows paths like C:\ don't trigger false warnings.
            has_invalid = False
            path_obj = Path(path)
            for part in path_obj.parts:
                if part in {path_obj.anchor, path_obj.drive}:
                    continue
                if any(char in part for char in invalid_chars):
                    has_invalid = True
                    break
            if has_invalid:
                print(f"WARNING: Path contains invalid characters: {path_str}")
            
            # Check for long path issues (Windows MAX_PATH is 260 chars)
            if len(path_str) > 240:  # Leave some room for filenames
                print(f"WARNING: Path is very long ({len(path_str)} chars): {path_str}")
        
        # Ensure the main download directory exists
        if not downloads_path.exists():
            debug_log(f"Creating main download directory: {downloads_path}")
            print(f"Creating main download directory: {downloads_path}")
            downloads_path.mkdir(parents=True, exist_ok=True)
        
        # Ensure the video directory exists
        if not video_output_dir.exists():
            debug_log(f"Creating video output directory: {video_output_dir}")
            print(f"Creating video output directory: {video_output_dir}")
            video_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure the audio directory exists
        if not audio_output_dir.exists():
            debug_log(f"Creating audio output directory: {audio_output_dir}")
            print(f"Creating audio output directory: {audio_output_dir}")
            audio_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure the playlist directory exists
        if not playlist_output_dir.exists():
            debug_log(f"Creating playlist output directory: {playlist_output_dir}")
            print(f"Creating playlist output directory: {playlist_output_dir}")
            playlist_output_dir.mkdir(parents=True, exist_ok=True)

        # Ensure the direct-download directory exists
        if not direct_output_dir.exists():
            debug_log(f"Creating direct output directory: {direct_output_dir}")
            print(f"Creating direct output directory: {direct_output_dir}")
            direct_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Test write permissions
        try:
            print("Testing write permissions...")
            test_files = []
            for dir_path in [video_output_dir, audio_output_dir, playlist_output_dir]:
                test_file = dir_path / "write_test.tmp"
                test_files.append(test_file)
                with open(test_file, 'w') as f:
                    f.write("write test")
            
            # Cleanup test files
            for test_file in test_files:
                if test_file.exists():
                    test_file.unlink()
            print("All directories are writable")
        except Exception as e:
            print(f"WARNING: Write permission test failed: {e}")
            print(traceback.format_exc())
            # Continue anyway, might still work
        
        debug_log("Output directories verified and created if needed.")
        print("Output directory verification complete")
        return True
    except Exception as e:
        log(f"Error verifying output directories: {str(e)}")
        print(f"Error verifying output directories: {str(e)}")
        print(traceback.format_exc())
        return False

# Start FFmpeg initialization when the GUI opens
initialize_ffmpeg()

last_clipboard_value = ""
recent_clipboard_urls = deque(maxlen=CLIPBOARD_RECENT_LIMIT)
tray_icon = None
tray_thread = None
screenshot_hotkey_thread = None
screenshot_hotkey_thread_id = None
screenshot_hotkey_registered = False
screenrecorder_hotkey_registered = False

def _run_screenshot_hotkey_listener():
    """Listen for the global screenshot hotkey while the app is in the background."""
    global screenshot_hotkey_thread_id, screenshot_hotkey_registered, screenrecorder_hotkey_registered

    if not IS_WINDOWS:
        return

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    screenshot_hotkey_thread_id = int(kernel32.GetCurrentThreadId())
    modifiers = MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT
    message = wintypes.MSG()

    try:
        screenshot_registered = bool(user32.RegisterHotKey(None, SCREENSHOT_HOTKEY_ID, modifiers, ord('Y')))
        if not screenshot_registered:
            log(f"Global screenshot hotkey unavailable: {SCREENSHOT_HOTKEY_LABEL}")

        recorder_registered = bool(user32.RegisterHotKey(None, SCREENRECORDER_HOTKEY_ID, modifiers, ord('R')))
        if not recorder_registered:
            log(f"Global screen recorder hotkey unavailable: {SCREENRECORDER_HOTKEY_LABEL}")

        if not screenshot_registered and not recorder_registered:
            return

        screenshot_hotkey_registered = screenshot_registered
        screenrecorder_hotkey_registered = recorder_registered
        if screenshot_registered:
            log(f"Global screenshot hotkey ready: {SCREENSHOT_HOTKEY_LABEL}")
        if recorder_registered:
            log(f"Global screen recorder hotkey ready: {SCREENRECORDER_HOTKEY_LABEL}")

        while True:
            result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
            if result in (0, -1):
                break

            if message.message == WM_HOTKEY:
                try:
                    hotkey_id = int(message.wParam)
                    if hotkey_id == SCREENSHOT_HOTKEY_ID:
                        root.after(0, trigger_screenshot_studio)
                    elif hotkey_id == SCREENRECORDER_HOTKEY_ID:
                        root.after(0, trigger_yscreenrecorder)
                except Exception as exc:
                    log(f"Error opening desktop tool from hotkey: {exc}")
    finally:
        if screenshot_hotkey_registered:
            try:
                user32.UnregisterHotKey(None, SCREENSHOT_HOTKEY_ID)
            except Exception:
                pass
        if screenrecorder_hotkey_registered:
            try:
                user32.UnregisterHotKey(None, SCREENRECORDER_HOTKEY_ID)
            except Exception:
                pass
        screenshot_hotkey_registered = False
        screenrecorder_hotkey_registered = False
        screenshot_hotkey_thread_id = None

def start_screenshot_hotkey_listener():
    """Start the Windows global hotkey listener once per app session."""
    global screenshot_hotkey_thread

    if not IS_WINDOWS:
        return False

    if screenshot_hotkey_thread is not None and screenshot_hotkey_thread.is_alive():
        return True

    screenshot_hotkey_thread = threading.Thread(
        target=_run_screenshot_hotkey_listener,
        daemon=True,
    )
    screenshot_hotkey_thread.start()
    return True

def stop_screenshot_hotkey_listener():
    """Stop the background screenshot hotkey listener cleanly."""
    if not IS_WINDOWS or screenshot_hotkey_thread_id is None:
        return

    try:
        ctypes.windll.user32.PostThreadMessageW(screenshot_hotkey_thread_id, WM_QUIT, 0, 0)
    except Exception:
        pass

# Options Frame
options_frame = tk.Frame(main_frame, bg=THEME['bg'])
options_frame.grid(row=1, column=0, sticky="ew", pady=(0, 20))
options_frame.grid_columnconfigure(0, weight=1)

# Left Options
left_options = tk.Frame(options_frame, bg=THEME['bg'])
left_options.grid(row=0, column=0, sticky="w")
left_options.grid_columnconfigure(0, weight=1)

download_playlist = BooleanVar(value=app_settings.get('download_playlist', False))
playlist_check = ModernCheckbutton(
    left_options,
    text="Download Entire Playlist",
    variable=download_playlist,
    command=on_playlist_toggle
)
playlist_check.grid(row=0, column=0, sticky="w", padx=(0, 20))

tk.Label(
    left_options,
    text="Use Direct Download for normal media/file links with pause and resume support.",
    font=('Segoe UI', 9),
    bg=THEME['bg'],
    fg=THEME['gray']
).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

# Right Options
right_options = tk.Frame(options_frame, bg=THEME['bg'])
right_options.grid(row=0, column=1, sticky="e")

tk.Label(
    right_options,
    text="Max Files:",
    font=('Segoe UI', 10),
    bg=THEME['bg'],
    fg=THEME['fg']
).grid(row=0, column=0, padx=(0, 5))

max_files_entry = ModernEntry(right_options, width=5)
max_files_entry.insert(0, app_settings.get('max_files', '100'))
max_files_entry.configure(state='normal' if download_playlist.get() else 'disabled')
max_files_entry.grid(row=0, column=1)
max_files_entry.bind('<FocusOut>', persist_max_files_value)
max_files_entry.bind('<Return>', persist_max_files_value)

# Buttons Frame
buttons_frame = tk.Frame(main_frame, bg=THEME['bg'])
buttons_frame.grid(row=2, column=0, sticky="ew", pady=(0, 20))
buttons_frame.grid_columnconfigure(0, weight=1)

primary_actions_row = tk.Frame(buttons_frame, bg=THEME['bg'])
primary_actions_row.grid_columnconfigure(0, weight=1)
primary_actions_row.grid_columnconfigure(1, weight=1)
primary_actions_row.grid_columnconfigure(2, weight=1)

secondary_actions_row = tk.Frame(buttons_frame, bg=THEME['bg'])

video_btn = tk.Button(
    primary_actions_row,
    text="🎬 Download Video",
    bg='#2196F3',
    fg='white',
    activebackground='#424242',
    activeforeground='white',
    font=('Segoe UI', 10, 'bold'),
    relief='flat',
    cursor='hand2',
    padx=20,
    pady=8,
    command=lambda: threaded_download(False)
)
video_btn._grid_kwargs = {"row": 0, "column": 0, "padx": (0, 10), "sticky": "ew"}
video_btn.grid(**video_btn._grid_kwargs)

audio_btn = tk.Button(
    primary_actions_row,
    text="🎵 Download Audio",
    bg='#2196F3',
    fg='white',
    activebackground='#424242',
    activeforeground='white',
    font=('Segoe UI', 10, 'bold'),
    relief='flat',
    cursor='hand2',
    padx=20,
    pady=8,
    command=lambda: threaded_download(True)
)
audio_btn._grid_kwargs = {"row": 0, "column": 1, "padx": (0, 10), "sticky": "ew"}
audio_btn.grid(**audio_btn._grid_kwargs)

direct_btn = tk.Button(
    primary_actions_row,
    text="📥 Direct Download (IDM)",
    bg='#4CAF50',
    fg='white',
    activebackground='#424242',
    activeforeground='white',
    font=('Segoe UI', 10, 'bold'),
    relief='flat',
    cursor='hand2',
    padx=20,
    pady=8,
    command=start_direct_download
)
direct_btn._grid_kwargs = {"row": 0, "column": 2, "sticky": "ew"}
direct_btn.grid(**direct_btn._grid_kwargs)

pause_resume_btn = tk.Button(
    secondary_actions_row,
    text="⏸ Pause Direct",
    bg='#FF9800',
    fg='white',
    activebackground='#424242',
    activeforeground='white',
    font=('Segoe UI', 10, 'bold'),
    relief='flat',
    cursor='hand2',
    padx=20,
    pady=8,
    command=toggle_direct_pause_resume
)
pause_resume_btn._pack_kwargs = {"side": "left", "padx": (0, 10)}

# Add cancel button to buttons frame
cancel_btn = tk.Button(
    secondary_actions_row,
    text="✖ Cancel Download",
    bg='#F44336',
    fg='white',
    activebackground='#424242',
    activeforeground='white',
    font=('Segoe UI', 10, 'bold'),
    relief='flat',
    cursor='hand2',
    padx=20,
    pady=8,
    command=lambda: cancel_download()
)
cancel_btn._pack_kwargs = {"side": "left"}
refresh_action_rows()

# Progress Section
progress_frame = tk.Frame(main_frame, bg=THEME['bg'])
progress_frame.grid(row=3, column=0, sticky="ew", pady=(0, 20))
progress_frame.grid_columnconfigure(0, weight=1)

site_progress_title = tk.Label(
    progress_frame,
    text="Site / Streaming Download Progress",
    font=('Segoe UI', 10, 'bold'),
    bg=THEME['bg'],
    fg=THEME['fg']
)
site_progress_title._grid_kwargs = {"row": 0, "column": 0, "sticky": "w"}
site_progress_title.grid(**site_progress_title._grid_kwargs)

progress_label = tk.Label(
    progress_frame,
    text="Ready to download",
    font=('Segoe UI', 10),
    bg=THEME['bg'],
    fg=THEME['fg']
)
progress_label._grid_kwargs = {"row": 1, "column": 0, "sticky": "w", "pady": (4, 5)}
progress_label.grid(**progress_label._grid_kwargs)

progress = ttk.Progressbar(
    progress_frame,
    style="Modern.Horizontal.TProgressbar",
    orient="horizontal",
    length=500,
    mode="determinate"
)
progress._grid_kwargs = {"row": 2, "column": 0, "sticky": "ew"}
progress.grid(**progress._grid_kwargs)

direct_progress_title = tk.Label(
    progress_frame,
    text="Direct File Download Progress",
    font=('Segoe UI', 10, 'bold'),
    bg=THEME['bg'],
    fg=THEME['fg']
)
direct_progress_title._grid_kwargs = {"row": 3, "column": 0, "sticky": "w", "pady": (14, 0)}
direct_progress_title.grid(**direct_progress_title._grid_kwargs)

direct_progress_label = tk.Label(
    progress_frame,
    text="Direct file download idle",
    font=('Segoe UI', 10),
    bg=THEME['bg'],
    fg=THEME['fg']
)
direct_progress_label._grid_kwargs = {"row": 4, "column": 0, "sticky": "w", "pady": (4, 5)}
direct_progress_label.grid(**direct_progress_label._grid_kwargs)

direct_progress = ttk.Progressbar(
    progress_frame,
    style="Modern.Horizontal.TProgressbar",
    orient="horizontal",
    length=500,
    mode="determinate"
)
direct_progress._grid_kwargs = {"row": 5, "column": 0, "sticky": "ew"}
direct_progress.grid(**direct_progress._grid_kwargs)

show_progress_section(None)

# Output Display
output_frame = tk.Frame(main_frame, bg=THEME['bg'])
output_frame.grid(row=4, column=0, sticky="nsew", pady=(0, 20))
output_frame.grid_rowconfigure(1, weight=1)
output_frame.grid_columnconfigure(0, weight=1)

output_label = tk.Label(
    output_frame,
    text="Download History:",
    font=('Segoe UI', 12, 'bold'),
    bg=THEME['bg'],
    fg=THEME['fg']
)
output_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

output_box = tk.Text(
    output_frame,
    height=14,
    font=('Consolas', 10),
    bg=THEME['light_gray'],
    fg=THEME['fg'],
    relief='flat',
    padx=10,
    pady=10
)
output_box.grid(row=1, column=0, sticky="nsew")

# Status Bar
status_frame = tk.Frame(root, bg=THEME['border'], height=30)
status_frame.grid(row=1, column=0, sticky="ew")
status_frame.grid_columnconfigure(0, weight=1)

status_label = tk.Label(
    status_frame,
    text="Ready",
    font=('Segoe UI', 9),
    bg=THEME['border'],
    fg=THEME['fg']
)
status_label.grid(row=0, column=0, sticky="w", padx=10)

# System Tray Icon
def tray_show_window(icon=None, menu_item=None):
    """Restore the main window from the tray."""
    try:
        root.after(0, show_window)
    except Exception as e:
        log(f"Error restoring window from tray: {e}")

def tray_exit_application(icon=None, menu_item=None):
    """Exit the application from the tray."""
    try:
        root.after(0, root.quit)
    except Exception as e:
        log(f"Error exiting from tray: {e}")

def tray_run_ui_action(callback, *args, refresh_menu=False):
    """Run a tray action on the Tk thread."""
    def _run():
        try:
            callback(*args)
        finally:
            if refresh_menu and tray_icon is not None:
                try:
                    tray_icon.update_menu()
                except Exception:
                    pass

    root.after(0, _run)

def tray_toggle_auto_start(icon=None, menu_item=None):
    """Toggle auto-start from the tray menu."""
    def _apply():
        auto_start_var.set(not auto_start_var.get())
        toggle_auto_start()

    tray_run_ui_action(_apply, refresh_menu=True)

def tray_set_video_quality(value):
    """Create a tray callback for video quality selection."""
    def _handler(icon=None, menu_item=None):
        def _apply():
            video_quality_var.set(value)
            on_video_quality_change()

        tray_run_ui_action(_apply, refresh_menu=True)
    return _handler

def tray_set_audio_quality(value):
    """Create a tray callback for audio quality selection."""
    def _handler(icon=None, menu_item=None):
        def _apply():
            audio_quality_var.set(value)
            on_audio_quality_change()

        tray_run_ui_action(_apply, refresh_menu=True)
    return _handler

def tray_set_format(value):
    """Create a tray callback for format selection."""
    def _handler(icon=None, menu_item=None):
        def _apply():
            format_var.set(value)
            on_format_change()

        tray_run_ui_action(_apply, refresh_menu=True)
    return _handler

def build_tray_menu():
    """Mirror the main menu actions in the system tray menu."""
    return pystray.Menu(
        item('Show', tray_show_window, default=True),
        item('File', pystray.Menu(
            item('Open Folder', lambda icon=None, menu_item=None: tray_run_ui_action(open_download_folder)),
            item('Choose Folder', lambda icon=None, menu_item=None: tray_run_ui_action(choose_download_folder)),
            item('Auto-start', tray_toggle_auto_start, checked=lambda menu_item: bool(auto_start_enabled)),
        )),
        item('Settings', pystray.Menu(
            item('Video Quality', pystray.Menu(
                item('Best Quality', tray_set_video_quality('best'), checked=lambda menu_item: quality_settings.get('video_quality') == 'best', radio=True),
                item('1080p', tray_set_video_quality('1080'), checked=lambda menu_item: quality_settings.get('video_quality') == '1080', radio=True),
                item('720p', tray_set_video_quality('720'), checked=lambda menu_item: quality_settings.get('video_quality') == '720', radio=True),
                item('480p', tray_set_video_quality('480'), checked=lambda menu_item: quality_settings.get('video_quality') == '480', radio=True),
                item('360p', tray_set_video_quality('360'), checked=lambda menu_item: quality_settings.get('video_quality') == '360', radio=True),
            )),
            item('Audio Quality', pystray.Menu(
                item('320 kbps', tray_set_audio_quality('320'), checked=lambda menu_item: quality_settings.get('audio_quality') == '320', radio=True),
                item('256 kbps', tray_set_audio_quality('256'), checked=lambda menu_item: quality_settings.get('audio_quality') == '256', radio=True),
                item('192 kbps', tray_set_audio_quality('192'), checked=lambda menu_item: quality_settings.get('audio_quality') == '192', radio=True),
                item('128 kbps', tray_set_audio_quality('128'), checked=lambda menu_item: quality_settings.get('audio_quality') == '128', radio=True),
                item('96 kbps', tray_set_audio_quality('96'), checked=lambda menu_item: quality_settings.get('audio_quality') == '96', radio=True),
            )),
            item('Format', pystray.Menu(
                item('MP4', tray_set_format('mp4'), checked=lambda menu_item: quality_settings.get('format') == 'mp4', radio=True),
                item('WebM', tray_set_format('webm'), checked=lambda menu_item: quality_settings.get('format') == 'webm', radio=True),
                item('MKV', tray_set_format('mkv'), checked=lambda menu_item: quality_settings.get('format') == 'mkv', radio=True),
            )),
            item('Install / Update FFmpeg', lambda icon=None, menu_item=None: tray_run_ui_action(force_install_or_update_ffmpeg)),
        )),
        item('Tools', pystray.Menu(
            item('Video Converter', lambda icon=None, menu_item=None: tray_run_ui_action(open_converter)),
            item('BG Remover', lambda icon=None, menu_item=None: tray_run_ui_action(open_background_remover)),
            item('YShoot', lambda icon=None, menu_item=None: tray_run_ui_action(open_screenshot_studio)),
            item('YScreenRecorder', lambda icon=None, menu_item=None: tray_run_ui_action(open_yscreenrecorder)),
        )),
        item('Help', pystray.Menu(
            item('About Us', lambda icon=None, menu_item=None: tray_run_ui_action(show_about_window)),
            item('Check for Updates', lambda icon=None, menu_item=None: tray_run_ui_action(force_check_updates)),
            item('Report Issue', lambda icon=None, menu_item=None: tray_run_ui_action(lambda: webbrowser.open("https://github.com/needyamin/media-downloader/issues"))),
            item('Debug Update System', lambda icon=None, menu_item=None: tray_run_ui_action(debug_update_check)),
        )),
        item('Exit', tray_exit_application),
    )

def create_tray_icon():
    global tray_icon, tray_thread
    try:
        if ICON_PATH.exists():
            icon_image = Image.open(ICON_PATH)
        else:
            # Create a simple icon if the file doesn't exist
            icon_image = Image.new('RGB', (64, 64), THEME['primary'])

        tray_icon = pystray.Icon(
            "media_downloader",
            icon_image,
            "Media Downloader",
            build_tray_menu()
        )
        
        # Run the tray icon in a separate thread
        tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
        tray_thread.start()
    except Exception as e:
        log(f"Error creating tray icon: {e}")

def show_window():
    """Show the main window."""
    root.deiconify()
    root.lift()
    root.focus_force()

def hide_window():
    """Hide the window to system tray."""
    root.withdraw()
    if tray_icon is None:
        create_tray_icon()

def on_minimize(event):
    """Handle window minimize event."""
    if event.widget == root and root.state() == 'iconic':
        hide_window()

def on_close():
    """Handle window close event."""
    hide_window()

# Bind minimize and close events
root.protocol('WM_DELETE_WINDOW', on_close)
root.bind('<Unmap>', on_minimize)  # Handle minimize button click
root.bind_all('<Control-Shift-Y>', trigger_screenshot_studio)
root.bind_all('<Control-Shift-R>', trigger_yscreenrecorder)

# Start tray icon
create_tray_icon()
start_screenshot_hotkey_listener()

# Update progress function to show percentage in status
def update_progress(percent, message=None):
    """Update the progress bar and label."""
    try:
        if message == "Ready to download" and not is_site_download_running():
            show_progress_section(None)
        else:
            show_progress_section("site")
        progress['value'] = percent
        if message:
            progress_label.config(text=message)
            status_label.config(text=message)
    except Exception as e:
        log(f"Error updating progress: {str(e)}")

def update_direct_progress(percent, message=None):
    """Update the direct-download progress bar and label."""
    try:
        if message == "Direct file download idle" and not is_direct_download_active():
            show_progress_section(None)
        else:
            show_progress_section("direct")
        direct_progress['value'] = percent
        if message:
            direct_progress_label.config(text=message)
            status_label.config(text=message)
    except Exception as e:
        log(f"Error updating direct progress: {str(e)}")

def finish_progress():
    progress['value'] = 100
    progress_label.config(text="Download Complete!")
    status_label.config(text="Download Complete!")

def process_queue():
    """Process the UI update queue."""
    while not ui_queue.empty():
        try:
            task = ui_queue.get_nowait()
            task()
        except queue.Empty:
            break
    root.after(UI_QUEUE_POLL_MS, process_queue)

def create_loading_icon():
    """Create a loading GIF animation."""
    global loading_gif, loading_label
    try:
        # Create a simple loading animation
        frames = []
        for i in range(8):
            img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            angle = i * 45
            draw.pieslice([0, 0, 16, 16], angle, angle + 180, fill=THEME['primary'])
            frames.append(img)
        
        # Save frames to memory
        output = io.BytesIO()
        frames[0].save(output, format='GIF', save_all=True, append_images=frames[1:], 
                      duration=100, loop=0, transparency=0)
        loading_gif = Image.open(output)
        return loading_gif
    except:
        return None

def update_loading_animation():
    """Update the loading animation."""
    if loading_gif and loading_label:
        try:
            frame = next(loading_gif.iter_frames())
            photo = ImageTk.PhotoImage(frame)
            loading_label.configure(image=photo)
            loading_label.image = photo
            root.after(100, update_loading_animation)
        except:
            pass

# Add global variable for download cancellation and yt-dlp instance
download_cancelled = False
cancel_event = threading.Event()
ydl_instance = None
current_download_thread = None
direct_download_task = None

def cancel_download():
    """Cancel the current download."""
    global download_cancelled, direct_download_task

    if direct_download_task is not None and direct_download_state() in {"probing", "downloading", "paused"}:
        direct_download_task.cancel()
        update_direct_progress(direct_progress['value'], "Cancelling direct download...")
        return

    download_cancelled = True
    cancel_event.set()
    
    try:
        if 'cancel_btn' in globals():
            cancel_btn.config(state='disabled')

        ui_queue.put(lambda: update_progress(0, "Cancelling download..."))
        log("Cancellation requested by user")
        
        # Ensure window stays visible after cancellation
        root.deiconify()
        root.lift()
        root.focus_force()
    except Exception as e:
        log(f"Error during cancellation: {str(e)}")

def download_media(is_audio):
    """Download media from the provided URL."""
    global ffmpeg_path, ffprobe_path, download_cancelled, ydl_instance
    download_cancelled = False  # Reset cancellation flag
    cancel_event.clear()
    ydl_instance = None  # Reset yt-dlp instance
    
    try:
        show_loading()  # Show loading animation
        update_progress(0, "Starting download...")  # Initialize progress bar
        
        # Verify output directories exist
        if not verify_output_directories():
            messagebox.showerror("Error", "Failed to create output directories. Check permissions and disk space.")
            hide_loading()
            update_progress(0, "Ready to download")
            return
            
        # Verify FFmpeg is available
        if not ffmpeg_path or not os.path.exists(ffmpeg_path):
            log("FFmpeg not found. Attempting to download...")
            ffmpeg_path = download_ffmpeg()
            if not ffmpeg_path or not os.path.exists(ffmpeg_path):
                messagebox.showerror("Error", "FFmpeg is required but could not be installed automatically.")
                hide_loading()
                update_progress(0, "Ready to download")
                return
        
        # Get current quality settings
        current_video_quality = video_quality_var.get()
        current_audio_quality = audio_quality_var.get()
        current_format = format_var.get()
        
        # Update quality settings dictionary
        quality_settings['video_quality'] = current_video_quality
        quality_settings['audio_quality'] = current_audio_quality
        quality_settings['format'] = current_format
        
        url = url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a video URL")
            hide_loading()
            update_progress(0, "Ready to download")
            return

        # Check if URL is a playlist
        is_playlist = ('playlist' in url.lower() or 
                       'list=' in url.lower() or 
                       '/sets/' in url.lower())  # Handle SoundCloud sets
                       
        if is_playlist and not download_playlist.get():
            if not messagebox.askyesno("Playlist Detected", 
                "This appears to be a playlist URL. Would you like to download the entire playlist?\n\n"
                "If not, only the first video will be downloaded."):
                is_playlist = False
        if is_youtube_url(url) and not is_playlist:
            normalized_url = strip_youtube_playlist_context(url)
            if normalized_url != url:
                log("Removed YouTube playlist context and kept only the selected video.")
                url = normalized_url

        max_files = max_files_entry.get() or '100'
        max_files = int(sanitize_max_files(max_files))

        # Set the appropriate output directory
        if is_playlist:
            output_path = playlist_output_dir
            output_template = str(playlist_output_dir / '%(playlist_index)s_%(title)s.%(ext)s')
        elif is_audio:
            output_path = audio_output_dir
            output_template = str(audio_output_dir / '%(title)s.%(ext)s')
        else:
            output_path = video_output_dir
            output_template = str(video_output_dir / '%(title)s.%(ext)s')

        log(f"Save folder: {output_path}")
        existing_output_files = snapshot_directory_files(output_path)

        # Validate URL
        if not url.startswith(('http://', 'https://')):
            log(f"URL validation failed: {url}")
            messagebox.showerror("Error", "Please enter a valid URL starting with http:// or https://")
            hide_loading()
            update_progress(0, "Ready to download")
            return

        blocked_domain = get_disabled_domain_match(url)
        if blocked_domain:
            log(f"Blocked domain: {blocked_domain}")
            show_error_dialog(
                "Download Blocked",
                "This domain is disabled in the application settings.",
                details=f"Blocked domain match: {blocked_domain}\nURL: {url}",
                suggestion=(
                    "Remove the domain from app_flags.json -> disabled_domains if you want to allow downloads from it again."
                ),
            )
            hide_loading()
            update_progress(0, "Ready to download")
            return

        # Configure format and quality settings for highest quality
        if is_audio:
            format_code = 'bestaudio/best'
            log(f"Starting audio download ({current_audio_quality} kbps).")
            debug_log(f"Audio format code: {format_code}")
        else:
            # Updated format selection for highest quality
            if current_video_quality == 'best':
                format_code = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
            else:
                format_code = f'bestvideo[height<={current_video_quality}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={current_video_quality}]+bestaudio/best[height<={current_video_quality}]'
            
            log(f"Starting video download ({current_video_quality}, {current_format}).")
            debug_log(f"Video format code: {format_code}")

        ydl_opts = {
            'format': format_code,
            'progress_hooks': [create_progress_hook()],
            'restrictfilenames': True,
            'windowsfilenames': True,
            'quiet': False,
            'no_warnings': False,
            'nocheckcertificate': True,  # Avoid certificate issues
            'nooverwrites': True,
            'ignoreerrors': True,  # Don't stop on errors
            'continuedl': True,
            'ffmpeg_location': ffmpeg_path,
            'merge_output_format': current_format,
            'verbose': True,
            'outtmpl': output_template,
            'playlist_items': f'1-{max_files}' if is_playlist else None,
            'noplaylist': not is_playlist,
            'ssl_verify': False,  # Disable SSL verification to avoid certificate issues
            'source_address': None,
            'socket_timeout': 30,
            'retries': 10,
            'extractor_retries': 10,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        }

        if is_youtube_url(url):
            js_runtimes = get_available_ytdlp_js_runtimes()
            if js_runtimes:
                ydl_opts['js_runtimes'] = js_runtimes
                debug_log(f"Using yt-dlp JS runtimes: {', '.join(js_runtimes.keys())}")
        
        # Configure postprocessor based on download type and quality settings
        if is_audio:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': current_audio_quality,
            }]
        else:
            # For video downloads, add postprocessor to ensure best quality
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': current_format,
            }]

        ydl_instance = yt_dlp.YoutubeDL(ydl_opts)
        try:
            debug_log("Extracting video information.")
            try:
                info = ydl_instance.extract_info(url, download=False)
                if not info:
                    raise Exception("Failed to extract video information")
            except Exception as extract_error:
                retry_ydl, retry_info, retry_error = try_extract_info_with_youtube_fallbacks(url, ydl_opts, extract_error)
                if retry_ydl is not None and retry_info is not None:
                    ydl_instance = retry_ydl
                    info = retry_info
                else:
                    extract_error = retry_error or extract_error
                    debug_log(f"Error extracting info: {str(extract_error)}")
                    details = normalize_error_details(
                        extract_error,
                        remove_prefix="Failed to extract video information"
                    )
                    suggestion = (
                        "Try checking the URL, waiting a bit, or switching to another public video link. "
                        "If the site changed recently, yt-dlp may also need an update."
                    )
                    if is_youtube_url(url) and is_youtube_bot_or_login_error(extract_error):
                        browser_sources = get_available_browser_cookie_sources()
                        browser_hint = ", ".join(browser_sources) if browser_sources else "a signed-in supported browser"
                        suggestion = (
                            "YouTube is asking for a sign-in or anti-bot confirmation. "
                            f"Make sure you are signed in to YouTube in {browser_hint}, then try again."
                        )
                    show_error_dialog(
                        "Could Not Read Media Info",
                        "We couldn't extract media information from this link.",
                        details=details or "The site may be unsupported, temporarily blocked, or the link may be invalid.",
                        suggestion=suggestion,
                    )
                    hide_loading()
                    update_progress(0, "Ready to download")
                    return
            
            debug_log(f"Download options: {ydl_opts}")
            
            if is_playlist and 'entries' in info:
                log(f"Playlist: {info.get('title', 'Untitled')}")
                entries_count = len(list(info.get('entries', [])))
                log(f"Items found: {entries_count}. Downloading up to {max_files}.")
            else:
                log(f"Title: {info.get('title', 'Untitled')}")

            debug_log(f"Starting download URL: {url}")
            debug_log(f"Using quality settings: Video={current_video_quality}, Audio={current_audio_quality}kbps, Format={current_format}")
            
            if download_cancelled:
                return
            if cancel_event.is_set():
                raise yt_dlp.utils.DownloadError("Download cancelled by user")
                
            # Start the actual download
            debug_log("Starting download process.")
            try:
                print("\n=== DOWNLOAD PROCESS STARTING ===")
                print(f"URL: {url}")
                print(f"Output path: {output_path}")
                print(f"Format: {format_code}")
                print(f"Is audio only: {is_audio}")
                print(f"Is playlist: {is_playlist}")
                print(f"FFmpeg path: {ffmpeg_path}")
                print(f"Output template: {output_template}")
                
                # Check that output directory exists and is writable
                print(f"Checking output directory...")
                if not output_path.exists():
                    print(f"Creating output directory: {output_path}")
                    output_path.mkdir(parents=True, exist_ok=True)
                
                # Test write access to output directory
                try:
                    test_file = output_path / "test_write.tmp"
                    with open(test_file, 'w') as f:
                        f.write("test")
                    test_file.unlink()
                    print("Output directory is writable")
                except Exception as e:
                    print(f"Warning: Output directory may not be writable: {e}")
                
                print("Starting yt-dlp download...")
                try:
                    # First attempt - use the configured options
                    ydl_instance.download([url])
                    print("yt-dlp download function completed")
                except Exception as primary_error:
                    # If the primary method failed, try a fallback with simpler options
                    print(f"\n=== PRIMARY DOWNLOAD FAILED, TRYING FALLBACK ===")
                    print(f"Primary error: {str(primary_error)}")
                    
                    # Create simpler fallback options
                    fallback_opts = {
                        'format': 'best' if not is_audio else 'bestaudio',
                        'outtmpl': output_template,
                        'nocheckcertificate': True,
                        'ignoreerrors': True,
                        'no_warnings': True,
                        'quiet': False,
                        'verbose': True,
                        'progress_hooks': [create_progress_hook()]
                    }
                    if ydl_opts.get('cookiesfrombrowser'):
                        fallback_opts['cookiesfrombrowser'] = ydl_opts['cookiesfrombrowser']
                    if ydl_opts.get('js_runtimes'):
                        fallback_opts['js_runtimes'] = ydl_opts['js_runtimes']
                    
                    if is_audio:
                        fallback_opts['postprocessors'] = [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': current_audio_quality,
                        }]
                        
                    print(f"Trying fallback with simplified options: {fallback_opts}")
                    fallback_ydl = yt_dlp.YoutubeDL(fallback_opts)
                    fallback_ydl.download([url])
                    print("Fallback download completed")
                
            except yt_dlp.utils.DownloadError as download_error:
                error_str = str(download_error)
                print(f"\n=== DOWNLOAD ERROR DETAILS ===")
                print(f"Error: {error_str}")
                print(f"Error type: {type(download_error).__name__}")
                
                # Detailed error diagnosis
                if "ffmpeg" in error_str.lower():
                    print("This appears to be an FFmpeg error")
                    debug_log(f"FFmpeg error: {error_str}")
                    show_error_dialog(
                        "FFmpeg Error",
                        "There was a problem while processing media with FFmpeg.",
                        details=normalize_error_details(error_str, remove_prefix="Error with FFmpeg"),
                        suggestion="Please check that FFmpeg is installed correctly, then try again."
                    )
                elif "HTTP Error 429" in error_str:
                    print("This appears to be a rate limit error")
                    debug_log(f"Rate limit error: {error_str}")
                    show_error_dialog(
                        "Rate Limit Error",
                        "The website is temporarily limiting requests from your network.",
                        details=error_str,
                        suggestion="Please wait a while and try again later."
                    )
                elif "postprocessor" in error_str.lower():
                    print("This appears to be a postprocessor error")
                    debug_log(f"Postprocessor error: {error_str}")
                    show_error_dialog(
                        "Processing Error",
                        "The download finished, but the media could not be converted or processed correctly.",
                        details=normalize_error_details(error_str, remove_prefix="Error processing the video"),
                        suggestion="Try downloading without conversion or switch to another output format."
                    )
                elif "copyright" in error_str.lower() or "not available" in error_str.lower():
                    print("This appears to be a content availability error")
                    debug_log(f"Content availability error: {error_str}")
                    show_error_dialog(
                        "Content Not Available",
                        "This media does not appear to be available for download right now.",
                        details=normalize_error_details(error_str, remove_prefix="This content may not be available"),
                        suggestion="The content may be private, geo-restricted, removed, or otherwise unavailable."
                    )
                elif "network" in error_str.lower() or "connection" in error_str.lower():
                    print("This appears to be a network error")
                    debug_log(f"Network error: {error_str}")
                    show_error_dialog(
                        "Network Error",
                        "A network problem interrupted the download.",
                        details=normalize_error_details(error_str, remove_prefix="Network connection issue"),
                        suggestion="Check your internet connection and try again."
                    )
                elif "cancelled by user" in error_str.lower():
                    log("Download cancelled by user")
                    ui_queue.put(lambda: update_progress(0, "Download cancelled"))
                else:
                    print("This is an unclassified error")
                    debug_log(f"Download error: {error_str}")
                    show_error_dialog(
                        "Download Error",
                        "The media could not be downloaded.",
                        details=error_str,
                        suggestion="Please review the error details and try again with another link or format."
                    )
                
                hide_loading()
                update_progress(0, "Ready to download")
                return
            except Exception as e:
                debug_log(f"Unexpected download error: {str(e)}")
                show_error_dialog(
                    "Unexpected Error",
                    "Something unexpected happened while starting the download.",
                    details=str(e),
                    suggestion="Please try again. If the problem keeps happening, copy the details and report the issue."
                )
            finally:
                ydl_instance = None

            if download_cancelled:
                log("Download cancelled")
                return

            renamed_files = rename_blank_downloaded_files(output_path, existing_output_files)
            for original_path, new_path in renamed_files:
                log(f"Renamed blank filename: {original_path.name} -> {new_path.name}")

            # Success! Open the appropriate folder
            if is_playlist:
                log("Playlist download completed.")
                log(f"Saved to: {playlist_output_dir}")
                
                # Ensure the folder exists and open it
                if playlist_output_dir.exists():
                    try:
                        # Convert to string and normalize path
                        folder_path = str(playlist_output_dir.resolve())
                        debug_log(f"Opening folder: {folder_path}")
                        open_path_in_file_manager(folder_path)
                    except Exception as e:
                        log(f"Error opening folder: {str(e)}")
            else:
                log("Download completed.")
                log(f"Saved to: {output_path}")
                # Open the output folder
                try:
                    folder_path = str(output_path.resolve())
                    open_path_in_file_manager(folder_path)
                except Exception as e:
                    log(f"Error opening folder: {str(e)}")

        except yt_dlp.utils.DownloadError as e:
            # This block will only be reached for errors not caught in the inner try block
            if not download_cancelled:  # Only show error if not cancelled
                log(f"Uncaught download error: {str(e)}")
                messagebox.showerror("Download Error", f"Download failed: {str(e)}")
        except Exception as e:
            if not download_cancelled:  # Only show error if not cancelled
                log(f"Unexpected error: {str(e)}")
                messagebox.showerror("Error", f"An unexpected error occurred: {str(e)}")
        finally:
            ydl_instance = None

    except Exception as e:
        if not download_cancelled:  # Only show error if not cancelled
            messagebox.showerror("Error", f"Error occurred:\n{e}")
    finally:
        hide_loading()  # Hide loading animation
        if not download_cancelled:
            ui_queue.put(lambda: enable_buttons())
            ui_queue.put(lambda: update_progress(0, "Ready to download"))
        else:
            ui_queue.put(lambda: update_progress(0, "Download cancelled"))
        # Ensure window stays visible after download
        root.deiconify()
        root.lift()
        root.focus_force()

# Clipboard Monitoring Functions
def is_supported_url(url):
    try:
        return validators.url(url) and not get_disabled_domain_match(url)
    except:
        return False

def remember_clipboard_url(url):
    """Keep only the most recent copied URLs in memory."""
    if not url:
        return

    try:
        recent_clipboard_urls.remove(url)
    except ValueError:
        pass

    recent_clipboard_urls.append(url)


def snapshot_directory_files(directory):
    """Capture the current files in a directory tree."""
    try:
        return {
            file_path.resolve()
            for file_path in Path(directory).rglob('*')
            if file_path.is_file()
        }
    except Exception:
        return set()


def is_blank_like_download_name(file_path):
    """Detect files whose saved title became effectively blank."""
    name = Path(file_path).name.strip()
    if not name:
        return True

    stem = Path(file_path).stem.strip()
    normalized = re.sub(r'[_\-\s\.\(\)\[\]]+', '', stem)
    return not normalized


def build_timestamp_fallback_path(file_path):
    """Create a unique timestamp-based fallback filename."""
    file_path = Path(file_path)
    suffix = file_path.suffix or ''
    timestamp_base = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    candidate = file_path.with_name(f"{timestamp_base}{suffix}")
    counter = 1

    while candidate.exists():
        candidate = file_path.with_name(f"{timestamp_base}_{counter}{suffix}")
        counter += 1

    return candidate


def rename_blank_downloaded_files(output_directory, previous_files):
    """Rename blank-like downloaded filenames to a timestamp."""
    renamed_files = []
    try:
        current_files = snapshot_directory_files(output_directory)
        new_files = sorted(current_files - previous_files, key=lambda path: path.stat().st_mtime)

        for file_path in new_files:
            if file_path.suffix.lower() in {'.part', '.ytdl', '.temp'}:
                continue
            if not is_blank_like_download_name(file_path):
                continue

            fallback_path = build_timestamp_fallback_path(file_path)
            file_path.rename(fallback_path)
            renamed_files.append((file_path, fallback_path))
    except Exception as rename_error:
        log(f"Filename fallback rename error: {rename_error}")

    return renamed_files

def check_clipboard():
    global last_clipboard_value
    try:
        clipboard_content = pyperclip.paste().strip()
        if clipboard_content and clipboard_content != last_clipboard_value:
            last_clipboard_value = clipboard_content

            if validators.url(clipboard_content):
                blocked_domain = get_disabled_domain_match(clipboard_content)
                if blocked_domain:
                    debug_log(f"Clipboard URL ignored for blocked domain: {blocked_domain}")
                elif is_supported_url(clipboard_content):
                    remember_clipboard_url(clipboard_content)
                    url_entry.delete(0, tk.END)
                    url_entry.insert(0, recent_clipboard_urls[-1])
                    url_entry.icursor(tk.END)
                    debug_log(f"Auto-filled latest clipboard URL: {clipboard_content}")
    except Exception as e:
        debug_print("Clipboard error:", e)

    poll_interval = CLIPBOARD_POLL_MS_ACTIVE
    try:
        if not root.winfo_viewable() or root.state() == 'iconic':
            poll_interval = CLIPBOARD_POLL_MS_BACKGROUND
    except Exception:
        poll_interval = CLIPBOARD_POLL_MS_BACKGROUND

    root.after(poll_interval, check_clipboard)

# Start clipboard monitoring
check_clipboard()

# Start queue processing
root.after(UI_QUEUE_POLL_MS, process_queue)
root.after_idle(lambda: center_window(root))

# Main loop
if __name__ == "__main__":
    try:
        # Check for updates on startup in the background
        start_app_update_check(user_initiated=False)
        
        # Show the window by default
        root.deiconify()
        center_window(root)
        root.lift()
        root.focus_force()
        
        # Create tray icon but don't start minimized
        if tray_icon is None:
            create_tray_icon()
        
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)
    finally:
        # Clean up tray icon when exiting
        stop_screenshot_hotkey_listener()
        if tray_icon is not None:
            tray_icon.stop()

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
