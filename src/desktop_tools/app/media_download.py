import tkinter as tk
from tkinter import ttk, messagebox, BooleanVar, filedialog, simpledialog
import os
from collections import deque
import yt_dlp
import threading
import webbrowser
import pyperclip
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageTk, ImageDraw
import sys
import ctypes
from ctypes import wintypes
import re
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlparse, urlunparse
import validators
import yt_dlp.postprocessor.ffmpeg
import queue
import shutil
import requests
import json
import subprocess
import time
import io
import traceback
from datetime import datetime

try:
    import winreg
except ImportError:
    winreg = None

APP_DIR = Path(__file__).resolve().parent
try:
    from desktop_tools.app.app_windowing import ensure_src_on_path
except Exception:
    from app_windowing import ensure_src_on_path
SRC_DIR = ensure_src_on_path(__file__)

IS_WINDOWS = sys.platform.startswith("win")

try:
    from desktop_tools.shared.resources import apply_window_icon, center_window, get_asset_path, get_project_root, get_user_data_dir
    from desktop_tools.app.hub import tool_actions as hub_tool_actions
    from desktop_tools.app.platform.hotkeys import (
        BG_REMOVER_HOTKEY_ID,
        BG_REMOVER_HOTKEY_MODIFIERS,
        BG_REMOVER_HOTKEY_VK,
        BG_REMOVER_HOTKEY_LABEL,
        CONVERTER_HOTKEY_ID,
        CONVERTER_HOTKEY_MODIFIERS,
        CONVERTER_HOTKEY_VK,
        CONVERTER_HOTKEY_LABEL,
        SCREENRECORDER_HOTKEY_ID,
        SCREENRECORDER_HOTKEY_MODIFIERS,
        SCREENRECORDER_HOTKEY_VK,
        SCREENRECORDER_HOTKEY_LABEL,
        ANIKA_HOTKEY_ID,
        ANIKA_HOTKEY_MODIFIERS,
        ANIKA_HOTKEY_VK,
        ANIKA_HOTKEY_LABEL,
        SCREENSHOT_HOTKEY_ID,
        SCREENSHOT_HOTKEY_MODIFIERS,
        SCREENSHOT_HOTKEY_VK,
        SCREENSHOT_HOTKEY_LABEL,
        WM_HOTKEY,
        WM_QUIT,
    )
    from desktop_tools.app.services.url_policy import get_blocked_domain
    from desktop_tools.app.config.runtime_flags import (
        APP_FLAGS,
        APP_VERSION_MAIN,
        CLIPBOARD_POLL_MS_ACTIVE,
        CLIPBOARD_POLL_MS_BACKGROUND,
        CLIPBOARD_RECENT_LIMIT,
        DEBUG_MODE,
        DOWNLOAD_ROOT_DIRNAME,
        DISABLED_DOMAINS,
        MAX_LOG_LINES,
        PROGRESS_LOG_MIN_INTERVAL_MS,
        PROGRESS_UI_MIN_INTERVAL_MS,
        UI_QUEUE_POLL_MS,
        get_tool_theme,
        normalize_domain_name,
    )
    from desktop_tools.shared.ffmpeg import (
        FFMPEG_DOWNLOAD_PAGE,
        FFMPEG_WINGET_PACKAGE,
        clear_custom_ffmpeg_paths,
        download_managed_ffmpeg,
        find_existing_ffmpeg,
        get_custom_ffmpeg_paths,
        get_ffmpeg_install_help,
        get_ffmpeg_version_line,
        install_ffmpeg_with_winget,
        set_custom_ffmpeg_paths,
        update_managed_ffmpeg_if_needed,
    )
    from desktop_tools.shared.direct_download import DirectDownloadError
    from desktop_tools.shared.direct_download_manager import DirectDownloadManager
    from desktop_tools.shared.dependency_progress import DependencyProgressPanel, parse_progress_percent
except Exception:
    WM_HOTKEY = 0x0312
    WM_QUIT = 0x0012
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_NOREPEAT = 0x4000
    CONVERTER_HOTKEY_ID = 0x5943
    CONVERTER_HOTKEY_MODIFIERS = MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT
    CONVERTER_HOTKEY_VK = ord("V")
    CONVERTER_HOTKEY_LABEL = "Ctrl+Shift+V"
    BG_REMOVER_HOTKEY_ID = 0x5942
    BG_REMOVER_HOTKEY_MODIFIERS = MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT
    BG_REMOVER_HOTKEY_VK = ord("B")
    BG_REMOVER_HOTKEY_LABEL = "Ctrl+Shift+B"
    SCREENSHOT_HOTKEY_ID = 0x594D
    SCREENSHOT_HOTKEY_MODIFIERS = MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT
    SCREENSHOT_HOTKEY_VK = ord("Y")
    SCREENSHOT_HOTKEY_LABEL = "Ctrl+Shift+Y"
    SCREENRECORDER_HOTKEY_ID = 0x5952
    SCREENRECORDER_HOTKEY_MODIFIERS = MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT
    SCREENRECORDER_HOTKEY_VK = ord("R")
    SCREENRECORDER_HOTKEY_LABEL = "Ctrl+Shift+R"
    ANIKA_HOTKEY_ID = 0x5955
    ANIKA_HOTKEY_MODIFIERS = MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT
    ANIKA_HOTKEY_VK = ord("U")
    ANIKA_HOTKEY_LABEL = "Ctrl+Shift+A"

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

    class DirectDownloadManager:
        def __init__(self, *args, **kwargs):
            self.error_message = "Direct download manager is unavailable."

        def get_records(self):
            return []

        def get_record(self, record_id):
            return None

        def get_active_record(self):
            return None

        def has_active_download(self):
            return False

        def queue_download(self, url):
            raise DirectDownloadError(self.error_message)

        def resume_record(self, record_id):
            return False

        def pause_record(self, record_id):
            return False

        def cancel_record(self, record_id):
            return False

        def replace_record_url(self, record_id, new_url):
            return False

        def delete_record(self, record_id, delete_files=False):
            return False

        def clear_finished(self, delete_files=False):
            return 0

        def start_next_download(self):
            return False

    def download_managed_ffmpeg(logger=None, progress_callback=None):
        return None, None

    def update_managed_ffmpeg_if_needed(logger=None, progress_callback=None, force=False, extra_paths=None):
        return None, None, False

    def find_existing_ffmpeg(extra_paths=None, logger=None):
        return None, None

    def get_custom_ffmpeg_paths():
        return None, None

    def set_custom_ffmpeg_paths(ffmpeg_path, ffprobe_path=None):
        raise RuntimeError("FFmpeg path settings are unavailable.")

    def clear_custom_ffmpeg_paths():
        return None

    def get_ffmpeg_install_help():
        return (
            "Install FFmpeg if needed:\n\n"
            "    Windows: winget install Gyan.FFmpeg\n"
            "    Or download from https://ffmpeg.org and add bin to PATH"
        )

    def get_ffmpeg_version_line(ffmpeg_path):
        return ""

    def install_ffmpeg_with_winget(logger=None):
        raise RuntimeError(get_ffmpeg_install_help())

    class DependencyProgressPanel:
        def __init__(self, *args, **kwargs):
            self.frame = None
            self.visible = False

        def show(self, *args, **kwargs):
            return None

        def update(self, *args, **kwargs):
            return None

        def hide(self):
            return None

        def threadsafe_callback(self, *args, **kwargs):
            return lambda *cb_args, **cb_kwargs: None

    def parse_progress_percent(message=None, percent=None):
        return percent

    FFMPEG_WINGET_PACKAGE = "Gyan.FFmpeg"
    FFMPEG_DOWNLOAD_PAGE = "https://ffmpeg.org/download.html"

    APP_FLAGS = {}
    APP_VERSION_MAIN = "3.0.0"
    DEBUG_MODE = False
    DOWNLOAD_ROOT_DIRNAME = "AnsNewTech Downloads"
    UI_QUEUE_POLL_MS = 150
    CLIPBOARD_POLL_MS_ACTIVE = 1200
    CLIPBOARD_POLL_MS_BACKGROUND = 2500
    CLIPBOARD_RECENT_LIMIT = 10
    PROGRESS_LOG_MIN_INTERVAL_MS = 1500
    PROGRESS_UI_MIN_INTERVAL_MS = 250
    MAX_LOG_LINES = 400
    DISABLED_DOMAINS = []

    def normalize_domain_name(domain):
        if not domain:
            return ""
        normalized = str(domain).strip().lower().rstrip(".")
        while normalized.startswith("."):
            normalized = normalized[1:]
        if normalized.startswith("www."):
            normalized = normalized[4:]
        return normalized

    def _get_disabled_domain_match(url, disabled_domains):
        try:
            hostname = normalize_domain_name(urlparse(url).hostname)
            if not hostname:
                return None
            for blocked_domain in disabled_domains:
                if hostname == blocked_domain or hostname.endswith(f".{blocked_domain}"):
                    return blocked_domain
        except Exception:
            return None
        return None

    def get_blocked_domain(url, disabled_domains):
        return _get_disabled_domain_match(url, disabled_domains)

    def get_tool_theme(tool_name, defaults):
        return defaults

    class _HubToolActionsFallback:
        @staticmethod
        def open_converter(*, root, log, messagebox_module):
            raise RuntimeError("Desktop tool launchers are unavailable.")

        @staticmethod
        def open_background_remover(*, root, log, messagebox_module):
            raise RuntimeError("Desktop tool launchers are unavailable.")

        @staticmethod
        def open_screenshot_studio(*, root, log, messagebox_module):
            raise RuntimeError("Desktop tool launchers are unavailable.")

        @staticmethod
        def open_yscreenrecorder(*, root, log, messagebox_module):
            raise RuntimeError("Desktop tool launchers are unavailable.")

        @staticmethod
        def open_anika(*, root, log, messagebox_module):
            raise RuntimeError("Desktop tool launchers are unavailable.")

        @staticmethod
        def open_anika_settings(*, root, log, messagebox_module):
            raise RuntimeError("Desktop tool launchers are unavailable.")

    hub_tool_actions = _HubToolActionsFallback()

def get_disabled_domain_match(url):
    """Return the blocked domain that matches a URL, if any."""
    return get_blocked_domain(url, DISABLED_DOMAINS)

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
THEME_DEFAULTS = {
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
THEME = get_tool_theme("media_downloader", THEME_DEFAULTS)

# Path configuration
ICON_PATH = get_asset_path("needyamin.ico")

# Installation directory (using AppData by default for better compatibility)
INSTALL_DIR = get_user_data_dir("Media Downloader")
INSTALL_DIR.mkdir(parents=True, exist_ok=True)
DIRECT_DOWNLOAD_HISTORY_FILE = INSTALL_DIR / "direct_download_history.json"

# Persistent settings and output directories
DEFAULT_DOWNLOADS_PATH = Path.home() / "Downloads" / DOWNLOAD_ROOT_DIRNAME
SETTINGS_FILE = INSTALL_DIR / "settings.json"
VALID_VIDEO_QUALITIES = {"best", "1080", "720", "480", "360"}
VALID_AUDIO_QUALITIES = {"320", "256", "192", "128", "96"}
VALID_FORMATS = {"mp4", "webm", "mkv"}

# Auto-update configuration
REPO_OWNER = "needyamin"
REPO_NAME = "media-downloader"
CURRENT_VERSION = APP_VERSION_MAIN
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
_update_system_state = {
    "release_info": None,
    "auto_apply": False,
    "checking": False,
    "applying": False,
}
_update_system_progress = None
_pending_update_installer = None

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
        path = Path(path_value).expanduser() if path_value else DEFAULT_DOWNLOADS_PATH
    except Exception:
        return DEFAULT_DOWNLOADS_PATH
    if path.name == "Yamin Downloader":
        return path.parent / DOWNLOAD_ROOT_DIRNAME
    return path

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

    previous_root = str(settings.get('download_root') or '')
    settings['download_root'] = str(normalize_download_root(settings.get('download_root')))
    if previous_root and previous_root != settings['download_root']:
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as settings_file:
                json.dump(settings, settings_file, indent=2)
        except Exception:
            pass
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

def download_ffmpeg():
    """Download and install FFmpeg."""
    message_label = None
    try:
        begin_dep_job("ffmpeg", "FFmpeg download / update", "Downloading FFmpeg...", indeterminate=True)
        message_label = show_loading("Downloading FFmpeg...")
        def update_status(message, percent=None):
            ffmpeg_download_progress(message, percent)
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
            "FFmpeg Required",
            "FFmpeg could not be installed automatically.\n\n" + get_ffmpeg_install_help(),
        )
        return None
            
    except Exception as e:
        log(f"Error downloading FFmpeg: {str(e)}")
        return None
    finally:
        end_dep_job("ffmpeg")
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
    """Return True when running as a packaged Windows executable (PyInstaller)."""
    executable_name = Path(sys.executable).name.lower()
    if not IS_WINDOWS or executable_name in {'python.exe', 'pythonw.exe'}:
        return False
    if getattr(sys, 'frozen', False):
        return True
    if globals().get('__compiled__') is not None:
        return True
    return executable_name.endswith('.exe')

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
    """Close the Update System window."""
    global debug_update_window, _update_system_progress
    _update_system_progress = None
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

    header_card = tk.Frame(
        outer,
        bg='#fff3f3',
        bd=0,
        relief='flat',
        highlightthickness=1,
        highlightbackground=THEME['border'],
        highlightcolor=THEME['border'],
    )
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

    body_card = tk.Frame(
        outer,
        bg='white',
        bd=0,
        relief='flat',
        highlightthickness=1,
        highlightbackground=THEME['border'],
        highlightcolor=THEME['border'],
    )
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


def focus_url_entry(select_existing=False):
    """Bring focus back to the main URL field."""
    try:
        root.deiconify()
    except Exception:
        pass

    try:
        root.lift()
        root.focus_force()
    except Exception:
        pass

    if 'url_entry' not in globals():
        return

    try:
        url_entry.focus_set()
        if select_existing:
            url_entry.selection_range(0, tk.END)
        url_entry.icursor(tk.END)
    except Exception:
        pass


def close_url_dialog_and_focus():
    """Close the active dialog and move the user back to the URL field."""
    close_error_dialog()
    focus_url_entry(select_existing=True)


def paste_clipboard_into_url_entry():
    """Paste the clipboard into the main URL field when possible."""
    clipboard_text = ""
    try:
        clipboard_text = pyperclip.paste().strip()
    except Exception:
        clipboard_text = ""

    if 'url_entry' in globals() and clipboard_text:
        try:
            url_entry.delete(0, tk.END)
            url_entry.insert(0, clipboard_text)
            schedule_url_preview_refresh()
        except Exception:
            pass

    close_url_dialog_and_focus()


def show_url_validation_dialog(current_text=""):
    """Show a styled URL guidance dialog instead of a plain warning popup."""
    global error_dialog_window

    if error_dialog_window and error_dialog_window.winfo_exists():
        error_dialog_window.destroy()

    current_text = str(current_text or "").strip()
    is_invalid = bool(current_text)
    title = "Paste a Media URL" if not is_invalid else "Check the URL Format"
    summary = (
        "Add a video or audio link to start the download."
        if not is_invalid
        else "The text in the URL box is not a complete web link yet."
    )
    helper_text = (
        "Copy a full media page link from your browser, then paste it into the main URL field."
        if not is_invalid
        else "A valid media link must begin with http:// or https:// before the downloader can use it."
    )
    details_text = (
        "The URL field is currently empty."
        if not is_invalid
        else f"Current text:\n{current_text}"
    )

    error_dialog_window = tk.Toplevel(root)
    error_dialog_window.title(title)
    error_dialog_window.geometry("620x360")
    error_dialog_window.minsize(560, 320)
    error_dialog_window.configure(bg=THEME['bg'])
    error_dialog_window.transient(root)
    error_dialog_window.protocol("WM_DELETE_WINDOW", close_error_dialog)
    apply_window_icon(error_dialog_window, app_id="needyamin.media_downloader")

    outer = tk.Frame(error_dialog_window, bg=THEME['bg'])
    outer.pack(fill='both', expand=True, padx=20, pady=20)

    header_card = tk.Frame(
        outer,
        bg='#EEF6FF',
        bd=0,
        relief='flat',
        highlightthickness=1,
        highlightbackground=THEME['border'],
        highlightcolor=THEME['border'],
    )
    header_card.pack(fill='x', pady=(0, 14))

    icon_box = tk.Label(
        header_card,
        text="URL",
        font=('Segoe UI', 11, 'bold'),
        bg=THEME['secondary'],
        fg='white',
        padx=14,
        pady=12,
    )
    icon_box.pack(side='left', padx=18, pady=18)

    header_text = tk.Frame(header_card, bg='#EEF6FF')
    header_text.pack(fill='both', expand=True, padx=(0, 18), pady=18)

    tk.Label(
        header_text,
        text=title,
        font=('Segoe UI', 16, 'bold'),
        bg='#EEF6FF',
        fg=THEME['secondary'],
        anchor='w',
    ).pack(anchor='w')

    tk.Label(
        header_text,
        text=summary,
        font=('Segoe UI', 10),
        bg='#EEF6FF',
        fg=THEME['fg'],
        anchor='w',
        justify='left',
        wraplength=440,
    ).pack(anchor='w', pady=(6, 0))

    body_card = tk.Frame(
        outer,
        bg='white',
        bd=0,
        relief='flat',
        highlightthickness=1,
        highlightbackground=THEME['border'],
        highlightcolor=THEME['border'],
    )
    body_card.pack(fill='both', expand=True)

    tk.Label(
        body_card,
        text="What to do",
        font=('Segoe UI', 11, 'bold'),
        bg='white',
        fg=THEME['fg'],
        anchor='w',
    ).pack(anchor='w', padx=18, pady=(16, 6))

    tk.Label(
        body_card,
        text=helper_text,
        font=('Segoe UI', 10),
        bg='white',
        fg=THEME['gray'],
        justify='left',
        wraplength=560,
    ).pack(anchor='w', padx=18)

    detail_card = tk.Frame(
        body_card,
        bg=THEME['light_gray'],
        bd=0,
        relief='flat',
        highlightthickness=1,
        highlightbackground=THEME['border'],
        highlightcolor=THEME['border'],
    )
    detail_card.pack(fill='x', padx=18, pady=14)

    tk.Label(
        detail_card,
        text=details_text,
        font=('Segoe UI', 10),
        bg=THEME['light_gray'],
        fg=THEME['fg'],
        justify='left',
        anchor='w',
        padx=12,
        pady=12,
        wraplength=530,
    ).pack(fill='x')

    tk.Label(
        body_card,
        text="Example: https://www.youtube.com/watch?v=example",
        font=('Consolas', 10),
        bg='white',
        fg=THEME['secondary'],
        anchor='w',
    ).pack(anchor='w', padx=18, pady=(0, 16))

    button_row = tk.Frame(outer, bg=THEME['bg'])
    button_row.pack(fill='x')

    tk.Button(
        button_row,
        text="Paste Clipboard",
        bg=THEME['light_gray'],
        fg=THEME['fg'],
        activebackground=THEME['border'],
        activeforeground=THEME['fg'],
        relief='flat',
        cursor='hand2',
        padx=16,
        pady=7,
        command=paste_clipboard_into_url_entry,
    ).pack(side='left')

    tk.Button(
        button_row,
        text="Go to URL Box",
        bg=THEME['primary'],
        fg='white',
        activebackground=THEME['secondary'],
        activeforeground='white',
        relief='flat',
        cursor='hand2',
        padx=16,
        pady=7,
        command=close_url_dialog_and_focus,
    ).pack(side='right')

    error_dialog_window.after_idle(lambda: center_window(error_dialog_window, root))


def show_url_validation_dialog_threadsafe(current_text=""):
    """Show the styled URL guidance dialog from any thread."""
    if threading.current_thread() is threading.main_thread():
        show_url_validation_dialog(current_text)
    elif 'ui_queue' in globals():
        ui_queue.put(lambda text=current_text: show_url_validation_dialog(text))


def validate_main_download_url():
    """Validate the main URL box before starting a site download."""
    url = url_entry.get().strip() if 'url_entry' in globals() else ""
    if not url:
        show_url_validation_dialog("")
        return None
    if not url.startswith(('http://', 'https://')):
        log(f"URL validation failed: {url}")
        show_url_validation_dialog(url)
        return None
    return url

def _last_update_check_label():
    try:
        if UPDATE_CHECK_FILE.exists():
            last_check = float(UPDATE_CHECK_FILE.read_text(encoding="utf-8").strip())
            return time.ctime(last_check)
    except Exception:
        pass
    return "Not checked yet"


def _update_system_widgets():
    window = debug_update_window
    if window is None or not window.winfo_exists():
        return None
    return getattr(window, "_update_widgets", None)


def refresh_update_system_ui(info=None, status=None, apply_enabled=None):
    """Refresh the Update System window from any thread."""
    info = info if info is not None else _update_system_state.get("release_info")

    def apply():
        widgets = _update_system_widgets()
        if widgets is None:
            return
        widgets["current"].set(f"v{CURRENT_VERSION}")
        widgets["runtime"].set("Installed app" if is_packaged_runtime() else "Source (python run.py)")
        widgets["last_check"].set(_last_update_check_label())
        if info:
            widgets["latest"].set(f"v{info.get('latest_version') or '—'}")
            if info.get("ok"):
                if info.get("is_newer"):
                    widgets["status"].set(f"New version {info.get('latest_version')} is available.")
                    widgets["status_color"](THEME.get("success") or "#16A34A")
                else:
                    widgets["status"].set("You already have the latest version.")
                    widgets["status_color"](THEME.get("primary"))
            else:
                widgets["status"].set(info.get("error") or "Could not check for updates.")
                widgets["status_color"](THEME.get("error"))
            widgets["note"].set(info.get("comparison") or info.get("error") or "")
        if status:
            widgets["status"].set(status)
        if apply_enabled is not None:
            widgets["apply_btn"].configure(state="normal" if apply_enabled else "disabled")

    if "_run_on_ui" in globals():
        _run_on_ui(apply)
    elif threading.current_thread() is threading.main_thread():
        apply()
    elif "ui_queue" in globals():
        ui_queue.put(apply)


def open_update_system(start_check=True, auto_apply=False):
    """Open the live updater window without blocking the main UI."""
    global debug_update_window, _update_system_progress

    _update_system_state["auto_apply"] = bool(auto_apply)

    if debug_update_window is not None and debug_update_window.winfo_exists():
        debug_update_window.lift()
        debug_update_window.focus_force()
        if start_check:
            start_app_update_check(user_initiated=True)
        return debug_update_window

    win = tk.Toplevel(root)
    debug_update_window = win
    win.title("Update System")
    win.geometry("520x420")
    win.minsize(480, 380)
    win.configure(bg=THEME["bg"])
    win.transient(root)
    win.protocol("WM_DELETE_WINDOW", close_debug_update_window)
    apply_window_icon(win, app_id="needyamin.media_downloader")

    outer = tk.Frame(win, bg=THEME["bg"])
    outer.pack(fill="both", expand=True, padx=18, pady=16)

    tk.Label(outer, text="Update System", font=("Segoe UI", 18, "bold"), bg=THEME["bg"], fg=THEME["fg"]).pack(anchor="w")
    tk.Label(
        outer,
        text="Checks GitHub in the background. The app stays usable while an update downloads.",
        font=("Segoe UI", 9),
        bg=THEME["bg"],
        fg=THEME["gray"],
        wraplength=470,
        justify="left",
    ).pack(anchor="w", pady=(4, 12))

    card = tk.Frame(outer, bg=THEME["light_gray"], highlightthickness=1, highlightbackground=THEME["border"])
    card.pack(fill="x")
    current_var = tk.StringVar(value=f"v{CURRENT_VERSION}")
    latest_var = tk.StringVar(value="Checking…")
    runtime_var = tk.StringVar(value="Installed app" if is_packaged_runtime() else "Source (python run.py)")
    last_check_var = tk.StringVar(value=_last_update_check_label())
    status_var = tk.StringVar(value="Checking for updates…")
    note_var = tk.StringVar(value="")

    rows = (
        ("Current version", current_var),
        ("Latest version", latest_var),
        ("Runtime", runtime_var),
        ("Last check", last_check_var),
    )
    for index, (label, variable) in enumerate(rows):
        tk.Label(card, text=label, font=("Segoe UI", 9, "bold"), bg=THEME["light_gray"], fg=THEME["fg"]).grid(
            row=index, column=0, sticky="w", padx=14, pady=(10 if index == 0 else 4, 4)
        )
        tk.Label(card, textvariable=variable, font=("Segoe UI", 9), bg=THEME["light_gray"], fg=THEME["fg"]).grid(
            row=index, column=1, sticky="w", padx=(8, 14), pady=(10 if index == 0 else 4, 4)
        )
    card.grid_columnconfigure(1, weight=1)

    status_label_widget = tk.Label(
        outer,
        textvariable=status_var,
        font=("Segoe UI", 10, "bold"),
        bg=THEME["bg"],
        fg=THEME["primary"],
        wraplength=470,
        justify="left",
    )
    status_label_widget.pack(anchor="w", pady=(14, 2))
    tk.Label(outer, textvariable=note_var, font=("Segoe UI", 9), bg=THEME["bg"], fg=THEME["gray"], wraplength=470, justify="left").pack(anchor="w")

    _update_system_progress = DependencyProgressPanel(
        outer,
        background=THEME["bg"],
        foreground=THEME["fg"],
        muted=THEME["gray"],
        bar_style="Modern.Horizontal.TProgressbar",
        wraplength=470,
        use_ttk=False,
        layout="pack",
        layout_kwargs={"fill": "x", "pady": (12, 0)},
    )

    button_row = tk.Frame(outer, bg=THEME["bg"])
    button_row.pack(fill="x", pady=(16, 0))

    def _small_btn(parent, text, command, *, primary=False):
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", 9, "bold" if primary else "normal"),
            bg=THEME["primary"] if primary else THEME["light_gray"],
            fg="#ffffff" if primary else THEME["fg"],
            activebackground=THEME["secondary"] if primary else THEME["border"],
            activeforeground="#ffffff" if primary else THEME["fg"],
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=7,
        )

    apply_btn = _small_btn(button_row, "Install Update", lambda: apply_available_update(user_initiated=True), primary=True)
    apply_btn.pack(side="left")
    apply_btn.configure(state="disabled")
    _small_btn(button_row, "Check Again", lambda: start_app_update_check(user_initiated=True)).pack(side="left", padx=(8, 0))
    _small_btn(button_row, "Open Release", lambda: webbrowser.open(
        (_update_system_state.get("release_info") or {}).get("release_url")
        or f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    )).pack(side="left", padx=(8, 0))
    _small_btn(button_row, "Close", close_debug_update_window).pack(side="right")

    def status_color(color):
        status_label_widget.configure(fg=color)

    win._update_widgets = {
        "current": current_var,
        "latest": latest_var,
        "runtime": runtime_var,
        "last_check": last_check_var,
        "status": status_var,
        "note": note_var,
        "apply_btn": apply_btn,
        "status_color": status_color,
    }

    win.after_idle(lambda: center_window(win, root))
    win.lift()
    win.focus_force()
    if start_check:
        start_app_update_check(user_initiated=True)
    return win


def debug_update_check():
    """Same as Check for Updates — kept as an alias."""
    set_status_threadsafe("Checking for app updates in background...")
    open_update_system(start_check=True, auto_apply=True)

# Create main window
root = tk.Tk()
root.title("Media Downloader")
root.geometry("880x840")
root.minsize(760, 740)
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

def check_internet_connection():
    """Return True when internet appears reachable."""
    test_urls = (
        "https://clients3.google.com/generate_204",
        "https://www.cloudflare.com/cdn-cgi/trace",
    )
    for test_url in test_urls:
        try:
            response = requests.get(test_url, timeout=3)
            if response.status_code < 500:
                return True
        except Exception:
            continue
    return False

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
        font=('Segoe UI', 10),
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
    about_window.geometry("780x560")
    about_window.minsize(700, 500)
    about_window.configure(bg=THEME['bg'])
    about_window.transient(root)
    about_window.protocol("WM_DELETE_WINDOW", close_about_window)
    apply_window_icon(about_window, app_id="needyamin.media_downloader")

    outer = tk.Frame(about_window, bg=THEME['bg'])
    outer.pack(fill='both', expand=True, padx=24, pady=22)

    shell_card = tk.Frame(
        outer,
        bg='white',
        bd=0,
        highlightthickness=1,
        highlightbackground=THEME['border'],
        highlightcolor=THEME['border'],
    )
    shell_card.pack(fill='both', expand=True)

    header_card = tk.Frame(shell_card, bg='white')
    header_card.pack(fill='x', padx=24, pady=(22, 14))

    avatar_source = load_profile_avatar()
    avatar_photo = ImageTk.PhotoImage(avatar_source)
    avatar_label = tk.Label(header_card, image=avatar_photo, bg='white')
    avatar_label.image = avatar_photo
    avatar_label.pack(side='left', padx=20, pady=20)

    info_frame = tk.Frame(header_card, bg='white')
    info_frame.pack(fill='both', expand=True, padx=(0, 20), pady=20)

    tk.Label(
        info_frame,
        text=AUTHOR_PROFILE['name'],
        font=('Segoe UI', 21, 'bold'),
        bg='white',
        fg=THEME['fg'],
        anchor='w',
    ).pack(anchor='w')

    tk.Label(
        info_frame,
        text=AUTHOR_PROFILE['role'],
        font=('Segoe UI', 11),
        bg='white',
        fg=THEME['secondary'],
        anchor='w',
    ).pack(anchor='w', pady=(5, 2))

    tk.Label(
        info_frame,
        text=AUTHOR_PROFILE['location'],
        font=('Segoe UI', 10),
        bg='white',
        fg=THEME['gray'],
        anchor='w',
    ).pack(anchor='w', pady=(0, 10))

    tk.Label(
        info_frame,
        text=AUTHOR_PROFILE['bio'],
        font=('Segoe UI', 10),
        bg='white',
        fg=THEME['fg'],
        anchor='w',
        justify='left',
        wraplength=470,
    ).pack(anchor='w')

    tk.Frame(shell_card, bg=THEME['border'], height=1).pack(fill='x', padx=24, pady=(0, 0))

    details_card = tk.Frame(shell_card, bg='white')
    details_card.pack(fill='both', expand=True, padx=24, pady=(14, 18))

    tk.Label(
        details_card,
        text="Profile Links",
        font=('Segoe UI', 13, 'bold'),
        bg='white',
        fg=THEME['fg'],
    ).pack(anchor='w', padx=20, pady=(18, 10))

    links_frame = tk.Frame(details_card, bg='white')
    links_frame.pack(fill='x', padx=20, pady=(0, 6))

    for label, url in [
        ("GitHub", AUTHOR_PROFILE['github']),
        ("Website", AUTHOR_PROFILE['website']),
        ("ORCID", AUTHOR_PROFILE['orcid']),
        ("Facebook", AUTHOR_PROFILE['facebook']),
    ]:
        row = tk.Frame(links_frame, bg='white')
        row.pack(fill='x', pady=3)
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
    description.pack(anchor='w', padx=20, pady=(16, 14))

    button_row = tk.Frame(details_card, bg='white')
    button_row.pack(fill='x', padx=20, pady=(2, 4))

    tk.Button(
        button_row,
        text="Visit GitHub",
        bg=THEME['primary'],
        fg='white',
        activebackground=THEME['secondary'],
        activeforeground='white',
        relief='flat',
        cursor='hand2',
        padx=18,
        pady=8,
        command=lambda: webbrowser.open(AUTHOR_PROFILE['github']),
    ).pack(side='left')

    tk.Button(
        button_row,
        text="Close",
        bg='white',
        fg=THEME['fg'],
        activebackground=THEME['border'],
        activeforeground=THEME['fg'],
        relief='flat',
        bd=0,
        cursor='hand2',
        padx=18,
        pady=8,
        command=close_about_window,
    ).pack(side='right')

    about_window.after_idle(lambda: center_window(about_window, root))

def open_converter():
    """Open the converter from the downloader menu bar."""
    hub_tool_actions.open_converter(
        root=root,
        log=log,
        messagebox_module=messagebox,
        default_output_dir=str(downloads_path),
    )

def open_background_remover():
    """Open the background remover from the downloader menu bar."""
    hub_tool_actions.open_background_remover(root=root, log=log, messagebox_module=messagebox)

def trigger_converter(event=None):
    """Open the converter from the GUI or keyboard shortcut."""
    open_converter()
    if event is not None:
        return "break"

def trigger_background_remover(event=None):
    """Open the background remover from the GUI or keyboard shortcut."""
    open_background_remover()
    if event is not None:
        return "break"

def open_screenshot_studio():
    """Open YScreenshot from the downloader menu bar."""
    hub_tool_actions.open_screenshot_studio(root=root, log=log, messagebox_module=messagebox)

def trigger_screenshot_studio(event=None):
    """Open YScreenshot from the GUI or keyboard shortcut."""
    open_screenshot_studio()
    if event is not None:
        return "break"

def open_yscreenrecorder():
    """Open YScreenRecorder from the downloader menu bar."""
    hub_tool_actions.open_yscreenrecorder(root=root, log=log, messagebox_module=messagebox)

def trigger_yscreenrecorder(event=None):
    """Open YScreenRecorder from the GUI or keyboard shortcut."""
    open_yscreenrecorder()
    if event is not None:
        return "break"

def open_anika():
    """Open Anika character and settings from the downloader menu bar."""
    hub_tool_actions.open_anika(root=root, log=log, messagebox_module=messagebox)

def trigger_anika(event=None):
    """Open Anika from the GUI or keyboard shortcut."""
    open_anika()
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

def get_direct_download_manager():
    """Return the shared IDM-style direct download manager."""
    return direct_download_manager

def get_active_direct_record():
    """Return the currently active direct-download record, if any."""
    manager = get_direct_download_manager()
    if manager is None:
        return None
    return manager.get_active_record()

def get_direct_download_record(record_id):
    """Return a direct-download record by ID."""
    manager = get_direct_download_manager()
    if manager is None:
        return None
    return manager.get_record(record_id)

def direct_download_state():
    """Return the current active direct-download state."""
    active_record = get_active_direct_record()
    if active_record is None:
        return "idle"
    return getattr(active_record, "state", "idle")

def is_direct_download_active():
    """Return True when a direct download is downloading or paused."""
    return direct_download_state() in {"probing", "downloading", "paused"}

def format_download_size(byte_count):
    """Return a compact human-readable size string."""
    try:
        value = float(byte_count or 0)
    except Exception:
        value = 0.0
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return f"{int(value)} {units[unit_index]}"
    return f"{value:.1f} {units[unit_index]}"

def format_download_percent(record):
    """Return the progress percent for a download record."""
    if record is None:
        return "0%"
    try:
        return f"{record.progress_percent:.1f}%"
    except Exception:
        return "0%"

def format_download_progress_text(record):
    """Return a compact progress summary for a download record."""
    if record is None:
        return "0 B"
    if getattr(record, "total_size", 0):
        return f"{format_download_size(record.downloaded_bytes)} / {format_download_size(record.total_size)}"
    return format_download_size(getattr(record, "downloaded_bytes", 0))

def format_download_timestamp(timestamp_value):
    """Format a unix timestamp for display in the download list."""
    try:
        if not timestamp_value:
            return "-"
        return datetime.fromtimestamp(float(timestamp_value)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "-"

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

_dep_jobs = set()
dep_progress_panel = None
_ffmpeg_settings_progress = None


def _run_on_ui(callback):
    if threading.current_thread() is threading.main_thread():
        callback()
        return
    if "ui_queue" in globals():
        ui_queue.put(callback)


def begin_dep_job(job_id, title, message, percent=None, indeterminate=False):
    """Show the hub dependency/update bar for one background job."""
    _dep_jobs.add(job_id)

    def apply():
        panel = globals().get("dep_progress_panel")
        if panel is None:
            return
        panel.show(title=title, message=message, percent=percent, indeterminate=indeterminate)
        if message and "status_label" in globals():
            status_label.config(text=message)
        settings_panel = globals().get("_ffmpeg_settings_progress")
        if job_id == "ffmpeg" and settings_panel is not None:
            settings_panel.show(title=title, message=message, percent=percent, indeterminate=indeterminate)
        update_panel = globals().get("_update_system_progress")
        if job_id == "app-update" and update_panel is not None:
            update_panel.show(title=title, message=message, percent=percent, indeterminate=indeterminate)

    _run_on_ui(apply)


def update_dep_job(job_id, message=None, percent=None, title=None, indeterminate=None):
    """Update an active dependency/update bar."""
    if job_id not in _dep_jobs:
        _dep_jobs.add(job_id)

    def apply():
        panel = globals().get("dep_progress_panel")
        if panel is None:
            return
        panel.update(message=message, percent=percent, title=title, indeterminate=indeterminate)
        if message and "status_label" in globals():
            status_label.config(text=message)
        settings_panel = globals().get("_ffmpeg_settings_progress")
        if job_id == "ffmpeg" and settings_panel is not None:
            settings_panel.update(message=message, percent=percent, title=title, indeterminate=indeterminate)
        update_panel = globals().get("_update_system_progress")
        if job_id == "app-update" and update_panel is not None:
            update_panel.update(message=message, percent=percent, title=title, indeterminate=indeterminate)

    _run_on_ui(apply)


def end_dep_job(job_id):
    """Hide the hub dependency bar when no download/update jobs remain."""
    _dep_jobs.discard(job_id)

    def apply():
        panel = globals().get("dep_progress_panel")
        settings_panel = globals().get("_ffmpeg_settings_progress")
        if job_id == "ffmpeg" and settings_panel is not None:
            settings_panel.hide()
        update_panel = globals().get("_update_system_progress")
        if job_id == "app-update" and update_panel is not None:
            update_panel.hide()
        if panel is None:
            return
        if not _dep_jobs:
            panel.hide()

    _run_on_ui(apply)


def ffmpeg_download_progress(message, percent=None):
    """FFmpeg download callback that drives the visible processing bar."""
    ffmpeg_log(message)
    parsed = parse_progress_percent(message, percent)
    extracting = "extract" in str(message).lower()
    update_dep_job(
        "ffmpeg",
        message=message,
        percent=parsed,
        title="FFmpeg download / update",
        indeterminate=parsed is None or extracting,
    )

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
        manager = get_direct_download_manager()
        if manager is not None:
            manager.start_next_download()
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
            direct_btn.config(state='normal')
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
                direct_btn.config(state='normal')
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
                direct_btn.config(state='normal')
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

def initialize_direct_download_manager():
    """Create the persistent direct-download manager once."""
    global direct_download_manager
    if direct_download_manager is None:
        direct_download_manager = DirectDownloadManager(
            output_dir=direct_output_dir,
            storage_path=DIRECT_DOWNLOAD_HISTORY_FILE,
            log_callback=direct_download_log,
            can_start_downloads=lambda: not is_site_download_running(),
            on_change=handle_direct_download_manager_change,
            on_active_progress=handle_direct_download_manager_change,
        )
    return direct_download_manager

def get_direct_download_message(record):
    """Return the status text for the current direct download record."""
    if record is None:
        return "Download list idle"
    if getattr(record, "last_message", ""):
        return record.last_message
    title = record.final_name or record.filename or "Direct download"
    return f"{title}: {record.state.title()}"

def sync_direct_download_progress(record=None):
    """Update the main direct-download progress widgets from the manager."""
    active_record = record or get_active_direct_record()
    if active_record is None:
        update_direct_progress(0, "Download list idle")
        return
    update_direct_progress(active_record.progress_percent, get_direct_download_message(active_record))

def handle_direct_download_manager_change(record=None):
    """Refresh direct-download UI after queue/history changes."""
    def _apply():
        try:
            sync_direct_download_progress(record)
            update_direct_download_controls()
            if 'download_list_window' in globals() and download_list_window is not None:
                refresh_download_list_window()
            if record is not None and getattr(record, 'state', '') == 'completed' and getattr(record, 'final_path', ''):
                try:
                    open_path_in_file_manager(Path(record.final_path).parent)
                except Exception as exc:
                    log(f"Error opening direct-download folder: {exc}")
            elif record is not None and getattr(record, 'state', '') == 'error':
                show_error_dialog(
                    "Direct Download Error",
                    "The direct file download could not be completed.",
                    details=str(getattr(record, 'error_message', '') or "Unknown direct download error"),
                    suggestion=(
                        "Use a normal file/media URL for direct downloads. For video pages and streaming sites, use "
                        "the Video or Audio download buttons instead."
                    ),
                )
        except Exception as exc:
            log(f"Error refreshing direct download manager UI: {exc}")

    if threading.current_thread() is threading.main_thread():
        _apply()
    else:
        ui_queue.put(_apply)

def validate_direct_download_url(url):
    """Validate a direct-download URL and return the normalized value."""
    cleaned_url = str(url or "").strip()
    if not cleaned_url:
        raise DirectDownloadError("Please enter a direct file URL.")
    if not cleaned_url.startswith(("http://", "https://")):
        raise DirectDownloadError("Please enter a valid URL starting with http:// or https://")
    blocked_domain = get_disabled_domain_match(cleaned_url)
    if blocked_domain:
        raise DirectDownloadError(f"Blocked domain match: {blocked_domain}\nURL: {cleaned_url}")
    return cleaned_url

def queue_direct_download_url(url, *, open_window=False):
    """Queue a direct-download URL into the IDM-style download list."""
    manager = initialize_direct_download_manager()
    try:
        cleaned_url = validate_direct_download_url(url)
    except DirectDownloadError as exc:
        show_error_dialog(
            "Direct Download Error",
            "The direct file download could not be added.",
            details=str(exc),
            suggestion="Use a normal file/media URL here. For video pages and streaming sites, use the Video or Audio buttons instead.",
        )
        return None

    if not verify_output_directories():
        messagebox.showerror("Error", "Failed to prepare output directories for direct downloads.")
        return None

    try:
        record = manager.queue_download(cleaned_url)
    except Exception as exc:
        show_error_dialog(
            "Direct Download Error",
            "The direct file download could not be added.",
            details=str(exc),
            suggestion="Try another direct media/file URL, or use the Video or Audio buttons for site downloads.",
        )
        return None

    update_direct_progress(0, "Added direct file to the download list.")
    if open_window:
        open_download_list_window(select_record_id=record.id)
    return record

def queue_direct_download_from_entry(*, open_window=False):
    """Queue the current main-URL entry into the download list."""
    return queue_direct_download_url(url_entry.get().strip(), open_window=open_window)

def toggle_direct_pause_resume():
    """Pause or resume the current direct download from the main window."""
    manager = initialize_direct_download_manager()
    active_record = get_active_direct_record()
    if active_record is None:
        return
    if active_record.state == "downloading":
        manager.pause_record(active_record.id)
    elif active_record.state == "paused":
        update_direct_progress(active_record.progress_percent, "Resuming direct download...")
        manager.resume_record(active_record.id)

def get_selected_download_record_id():
    """Return the selected download-list record ID."""
    if 'download_list_tree' not in globals() or download_list_tree is None:
        return None
    selection = download_list_tree.selection()
    if not selection:
        return None
    return str(selection[0])

def get_selected_download_record():
    """Return the selected download-list record object."""
    record_id = get_selected_download_record_id()
    if not record_id:
        return None
    return get_direct_download_record(record_id)

def friendly_download_name(record):
    """Return a user-friendly title for a download record."""
    if record is None:
        return ""
    return record.final_name or record.filename or Path(urlparse(record.url).path).name or record.url

def build_download_details_text(record):
    """Build the details text for the selected download-list item."""
    if record is None:
        return "Select a download item to view details and actions."
    details = [
        f"Name: {friendly_download_name(record)}",
        f"Status: {record.state.title()}",
        f"Progress: {format_download_percent(record)} ({format_download_progress_text(record)})",
        f"Added: {format_download_timestamp(record.added_at)}",
        f"Updated: {format_download_timestamp(record.updated_at)}",
        f"URL: {record.url}",
    ]
    if record.final_path:
        details.append(f"File: {record.final_path}")
    elif record.part_path:
        details.append(f"Partial file: {record.part_path}")
    if record.error_message:
        details.append(f"Error: {record.error_message}")
    elif record.last_message:
        details.append(f"Message: {record.last_message}")
    return "\n".join(details)

def update_download_list_action_states():
    """Enable or disable download-list buttons based on the current selection."""
    record = get_selected_download_record()
    selection_exists = record is not None
    active_busy = selection_exists and record.id == getattr(get_direct_download_manager(), "active_record_id", None) and record.state in {"probing", "downloading"}

    button_states = {
        'download_list_resume_btn': 'normal' if selection_exists and record.state in {"queued", "paused", "cancelled", "error"} else 'disabled',
        'download_list_pause_btn': 'normal' if active_busy else 'disabled',
        'download_list_cancel_btn': 'normal' if selection_exists and record.state in {"queued", "probing", "downloading", "paused"} else 'disabled',
        'download_list_replace_btn': 'normal' if selection_exists and record.state != "completed" else 'disabled',
        'download_list_open_file_btn': 'normal' if selection_exists and record.final_path and Path(record.final_path).exists() else 'disabled',
        'download_list_open_folder_btn': 'normal' if selection_exists else 'disabled',
        'download_list_delete_btn': 'normal' if selection_exists else 'disabled',
    }
    for widget_name, state in button_states.items():
        if widget_name in globals() and globals()[widget_name] is not None:
            globals()[widget_name].config(state=state)

def on_download_list_selection_change(event=None):
    """Refresh details when the selected download-list item changes."""
    record = get_selected_download_record()
    if 'download_list_details_var' in globals() and download_list_details_var is not None:
        download_list_details_var.set(build_download_details_text(record))
    update_download_list_action_states()

def select_download_record(record_id):
    """Select a download-list item by record ID if it exists."""
    if not record_id or 'download_list_tree' not in globals() or download_list_tree is None:
        return
    if not download_list_tree.exists(record_id):
        return
    download_list_tree.selection_set(record_id)
    download_list_tree.focus(record_id)
    download_list_tree.see(record_id)
    on_download_list_selection_change()

def refresh_download_list_window():
    """Refresh the IDM-style download list window contents."""
    if 'download_list_window' not in globals() or download_list_window is None or not download_list_window.winfo_exists():
        return
    manager = initialize_direct_download_manager()
    previous_selection = get_selected_download_record_id()
    download_list_tree.delete(*download_list_tree.get_children())

    for record in manager.get_records():
        download_list_tree.insert(
            "",
            "end",
            iid=record.id,
            values=(
                record.state.title(),
                friendly_download_name(record),
                format_download_percent(record),
                format_download_progress_text(record),
                format_download_timestamp(record.updated_at),
            ),
        )

    if previous_selection and download_list_tree.exists(previous_selection):
        select_download_record(previous_selection)
    elif download_list_tree.get_children():
        select_download_record(download_list_tree.get_children()[0])
    else:
        if 'download_list_details_var' in globals() and download_list_details_var is not None:
            download_list_details_var.set(build_download_details_text(None))
        update_download_list_action_states()

def add_current_url_to_download_list():
    """Add the current main-URL field into the direct download list."""
    record = queue_direct_download_from_entry(open_window=True)
    if record is not None:
        url_entry.delete(0, tk.END)

def prompt_add_url_to_download_list():
    """Prompt the user for a direct-download URL and add it to the list."""
    initial_url = url_entry.get().strip() if 'url_entry' in globals() else ""
    entered_url = simpledialog.askstring(
        "Add Direct Download",
        "Enter a direct file or media URL:",
        parent=download_list_window if 'download_list_window' in globals() and download_list_window is not None else root,
        initialvalue=initial_url,
    )
    if entered_url:
        queue_direct_download_url(entered_url, open_window=True)

def resume_selected_download_record():
    """Resume or start the selected direct-download record."""
    record = get_selected_download_record()
    if record is None:
        return
    initialize_direct_download_manager().resume_record(record.id)

def pause_selected_download_record():
    """Pause the selected active direct download."""
    record = get_selected_download_record()
    if record is None:
        return
    initialize_direct_download_manager().pause_record(record.id)

def cancel_selected_download_record():
    """Cancel the selected direct-download item while keeping it in history."""
    record = get_selected_download_record()
    if record is None:
        return
    initialize_direct_download_manager().cancel_record(record.id)

def replace_selected_download_link():
    """Replace the URL for a failed or paused direct download."""
    record = get_selected_download_record()
    if record is None:
        return
    replacement_url = simpledialog.askstring(
        "Replace Download Link",
        "Enter a new direct file URL for this item:",
        parent=download_list_window if 'download_list_window' in globals() and download_list_window is not None else root,
        initialvalue=record.url,
    )
    if not replacement_url:
        return
    try:
        cleaned_url = validate_direct_download_url(replacement_url)
    except DirectDownloadError as exc:
        show_error_dialog(
            "Replace Link Error",
            "The new direct link is not valid.",
            details=str(exc),
            suggestion="Enter a direct media/file URL beginning with http:// or https://.",
        )
        return
    initialize_direct_download_manager().replace_record_url(record.id, cleaned_url)

def open_selected_download_file():
    """Open the completed file for the selected direct-download item."""
    record = get_selected_download_record()
    if record is None or not record.final_path:
        return
    target_path = Path(record.final_path)
    if not target_path.exists():
        messagebox.showinfo("File Missing", "The downloaded file could not be found on disk.")
        return
    open_path_in_file_manager(target_path)

def open_selected_download_folder():
    """Open the containing folder for the selected direct-download item."""
    record = get_selected_download_record()
    if record is None:
        return
    target_path = Path(record.final_path).parent if record.final_path else direct_output_dir
    open_path_in_file_manager(target_path)

def delete_selected_download_record():
    """Delete the selected direct-download history row, optionally removing files."""
    record = get_selected_download_record()
    if record is None:
        return
    if record.id == getattr(get_direct_download_manager(), "active_record_id", None) and record.state in {"probing", "downloading"}:
        messagebox.showinfo("Download Busy", "Cancel or pause the active direct download before deleting it.")
        return
    choice = messagebox.askyesnocancel(
        "Delete Download Record",
        "Do you want to delete the selected download from the list?\n\nYes = Delete record and files\nNo = Delete record only\nCancel = Keep it",
        parent=download_list_window if 'download_list_window' in globals() and download_list_window is not None else root,
    )
    if choice is None:
        return
    initialize_direct_download_manager().delete_record(record.id, delete_files=bool(choice))

def clear_finished_download_records():
    """Clear completed, cancelled, and failed items from the download list."""
    manager = initialize_direct_download_manager()
    choice = messagebox.askyesnocancel(
        "Clear Finished Items",
        "Clear completed, cancelled, and failed downloads from the list?\n\nYes = Clear records and files\nNo = Clear records only\nCancel = Keep everything",
        parent=download_list_window if 'download_list_window' in globals() and download_list_window is not None else root,
    )
    if choice is None:
        return
    removed = manager.clear_finished(delete_files=bool(choice))
    if removed:
        log(f"Cleared {removed} direct download history item(s).")

def close_download_list_window():
    """Close the download list window without losing persisted history."""
    global download_list_window
    if download_list_window is not None and download_list_window.winfo_exists():
        download_list_window.destroy()
    download_list_window = None

def open_download_list_window(select_record_id=None):
    """Open the IDM-style direct download list window."""
    global download_list_window, download_list_tree, download_list_details_var
    global download_list_resume_btn, download_list_pause_btn, download_list_cancel_btn
    global download_list_replace_btn, download_list_open_file_btn, download_list_open_folder_btn, download_list_delete_btn

    initialize_direct_download_manager()
    if download_list_window is not None and download_list_window.winfo_exists():
        download_list_window.deiconify()
        download_list_window.lift()
        download_list_window.focus_force()
        refresh_download_list_window()
        if select_record_id:
            download_list_window.after(0, lambda item_id=select_record_id: select_download_record(item_id))
        return download_list_window

    download_list_window = tk.Toplevel(root)
    download_list_window.title("Download List")
    download_list_window.configure(bg=THEME['bg'])
    download_list_window.geometry("1160x700")
    download_list_window.minsize(980, 560)
    apply_window_icon(download_list_window, app_id="needyamin.media_downloader")
    download_list_window.protocol("WM_DELETE_WINDOW", close_download_list_window)
    download_list_window.grid_rowconfigure(1, weight=1)
    download_list_window.grid_columnconfigure(0, weight=1)

    def make_download_list_button(parent, text, command, *, bg, fg="white", active_bg=None, disabled_fg="#E2E8F0", compact=False):
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active_bg or bg,
            activeforeground=fg,
            disabledforeground=disabled_fg,
            font=('Segoe UI', 10, 'bold'),
            relief='flat',
            bd=0,
            cursor='hand2',
            padx=10 if compact else 14,
            pady=6 if compact else 8,
            highlightthickness=0,
        )
        return button

    header = tk.Frame(download_list_window, bg=THEME['light_gray'])
    header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
    header.grid_columnconfigure(0, weight=1)

    tk.Label(
        header,
        text="📋 Download List",
        font=('Segoe UI', 13, 'bold'),
        bg=THEME['light_gray'],
        fg=THEME['fg'],
    ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))

    tk.Label(
        header,
        text="IDM-style queue: add links, resume/pause, replace broken URLs, and manage history.",
        font=('Segoe UI', 8),
        bg=THEME['light_gray'],
        fg=THEME['gray'],
    ).grid(row=1, column=0, sticky="w", padx=10, pady=(0, 8))

    actions = tk.Frame(download_list_window, bg=THEME['bg'])
    actions.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
    actions.grid_rowconfigure(2, weight=1)
    actions.grid_columnconfigure(0, weight=1)

    toolbar = tk.Frame(actions, bg=THEME['light_gray'])
    toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    toolbar.grid_columnconfigure(1, weight=1)

    left_toolbar = tk.Frame(toolbar, bg=THEME['light_gray'])
    left_toolbar.grid(row=0, column=0, sticky="w", padx=8, pady=8)
    make_download_list_button(left_toolbar, "➕ Add Current URL", add_current_url_to_download_list, bg='#2563EB', active_bg='#1D4ED8', compact=True).pack(side='left', padx=(0, 6))
    make_download_list_button(left_toolbar, "🔗 Add URL", prompt_add_url_to_download_list, bg='#1D4ED8', active_bg='#1E40AF', compact=True).pack(side='left', padx=(0, 6))

    download_list_resume_btn = make_download_list_button(left_toolbar, "▶ Resume", resume_selected_download_record, bg='#0891B2', active_bg='#0E7490', compact=True)
    download_list_resume_btn.pack(side='left', padx=(0, 6))
    download_list_pause_btn = make_download_list_button(left_toolbar, "⏸ Pause", pause_selected_download_record, bg='#D97706', active_bg='#B45309', compact=True)
    download_list_pause_btn.pack(side='left', padx=(0, 6))
    download_list_cancel_btn = make_download_list_button(left_toolbar, "✖ Cancel", cancel_selected_download_record, bg='#DC2626', active_bg='#B91C1C', compact=True)
    download_list_cancel_btn.pack(side='left', padx=(0, 6))
    download_list_replace_btn = make_download_list_button(left_toolbar, "🔄 Replace Link", replace_selected_download_link, bg='#7C3AED', active_bg='#6D28D9', compact=True)
    download_list_replace_btn.pack(side='left')

    right_toolbar = tk.Frame(toolbar, bg=THEME['light_gray'])
    right_toolbar.grid(row=0, column=1, sticky="e", padx=8, pady=8)
    download_list_open_file_btn = make_download_list_button(right_toolbar, "📄 Open File", open_selected_download_file, bg='#334155', active_bg='#1E293B', compact=True)
    download_list_open_file_btn.pack(side='left', padx=(0, 6))
    download_list_open_folder_btn = make_download_list_button(right_toolbar, "📁 Open Folder", open_selected_download_folder, bg='#475569', active_bg='#334155', compact=True)
    download_list_open_folder_btn.pack(side='left', padx=(0, 6))
    download_list_delete_btn = make_download_list_button(right_toolbar, "🗑 Delete", delete_selected_download_record, bg='#92400E', active_bg='#78350F', compact=True)
    download_list_delete_btn.pack(side='left', padx=(0, 6))
    make_download_list_button(right_toolbar, "🧹 Clear Done", clear_finished_download_records, bg='#64748B', active_bg='#475569', compact=True).pack(side='left', padx=(0, 6))
    make_download_list_button(right_toolbar, "🔄 Refresh", refresh_download_list_window, bg='#0F766E', active_bg='#0F5F59', compact=True).pack(side='left')

    tree_frame = tk.Frame(actions, bg=THEME['light_gray'])
    tree_frame.grid(row=2, column=0, sticky="nsew")
    tree_frame.grid_rowconfigure(0, weight=1)
    tree_frame.grid_columnconfigure(0, weight=1)

    columns = ("status", "name", "progress", "size", "updated")
    download_list_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
    download_list_tree.heading("status", text="📌 Status")
    download_list_tree.heading("name", text="📄 Name")
    download_list_tree.heading("progress", text="📶 Progress")
    download_list_tree.heading("size", text="💾 Size")
    download_list_tree.heading("updated", text="🕒 Updated")
    download_list_tree.column("status", width=130, anchor="w")
    download_list_tree.column("name", width=420, anchor="w")
    download_list_tree.column("progress", width=120, anchor="center")
    download_list_tree.column("size", width=170, anchor="center")
    download_list_tree.column("updated", width=170, anchor="center")
    download_list_tree.grid(row=0, column=0, sticky="nsew")
    download_list_tree.bind("<<TreeviewSelect>>", on_download_list_selection_change)

    tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=download_list_tree.yview)
    tree_scroll.grid(row=0, column=1, sticky="ns")
    download_list_tree.configure(yscrollcommand=tree_scroll.set)

    download_list_details_var = tk.StringVar(value="Ready. Select a download item to view details and actions.")
    status_bar = tk.Label(
        actions,
        textvariable=download_list_details_var,
        justify='left',
        anchor='w',
        bg=THEME['light_gray'],
        fg=THEME['fg'],
        relief='flat',
        padx=10,
        pady=8,
        wraplength=980,
    )
    status_bar.grid(row=3, column=0, sticky="ew", pady=(8, 0))

    refresh_download_list_window()
    if select_record_id:
        download_list_window.after(0, lambda item_id=select_record_id: select_download_record(item_id))
    download_list_window.after_idle(lambda: center_window(download_list_window, root))
    return download_list_window

def threaded_download(is_audio):
    """Start the existing yt-dlp downloader in a separate thread."""
    global current_download_thread

    if is_direct_download_active():
        messagebox.showinfo("Download Busy", "A direct download is already active. Pause or cancel it first.")
        return

    validated_url = validate_main_download_url()
    if not validated_url:
        return

    disable_buttons()

    def download_thread():
        global current_download_thread
        try:
            download_media(is_audio, validated_url)
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

def get_source_update_settings():
    """Read source-mode updater settings from app flags."""
    updates = APP_FLAGS.get("updates", {}) if isinstance(APP_FLAGS, dict) else {}
    if not isinstance(updates, dict):
        updates = {}
    return {
        "source_auto_pull": bool(updates.get("source_auto_pull", True)),
        "source_auto_restart_after_pull": bool(updates.get("source_auto_restart_after_pull", False)),
        "source_remote": str(updates.get("source_remote", "origin") or "origin").strip(),
        "source_branch": str(updates.get("source_branch", "auto") or "auto").strip(),
    }

def is_packaged_auto_update_enabled():
    """Whether the installed app should download GitHub release installers."""
    updates = APP_FLAGS.get("updates", {}) if isinstance(APP_FLAGS, dict) else {}
    if not isinstance(updates, dict):
        return True
    return bool(updates.get("packaged_auto_update", True))


def fetch_latest_release_info():
    """Fetch the latest GitHub release without blocking the UI thread."""
    result = {
        "ok": False,
        "error": None,
        "release": None,
        "latest_version": "",
        "current_version": CURRENT_VERSION,
        "is_newer": False,
        "comparison": "",
        "release_url": f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest",
        "preferred_asset": None,
        "installer_asset": None,
        "installer": None,
    }
    try:
        response = requests.get(GITHUB_API_URL, headers=get_update_headers(), timeout=15)
        if response.status_code != 200:
            result["error"] = f"GitHub returned HTTP {response.status_code}."
            return result
        release = response.json()
        latest_version = str(release.get("tag_name") or "").lstrip("v").strip()
        if not latest_version:
            result["error"] = "The latest GitHub release has no version tag."
            return result
        comparison = get_version_comparison_info(latest_version, CURRENT_VERSION)
        preferred = get_preferred_update_asset(release)
        installer = get_preferred_update_asset(release, require_installer=True)
        result.update({
            "ok": True,
            "release": release,
            "latest_version": latest_version,
            "is_newer": bool(comparison.get("is_newer")),
            "comparison": comparison.get("message") or "",
            "release_url": release.get("html_url") or result["release_url"],
            "preferred_asset": preferred.get("name") if preferred else None,
            "installer_asset": installer.get("name") if installer else None,
            "installer": installer,
        })
        return result
    except requests.exceptions.RequestException as exc:
        result["error"] = f"Network error: {exc}"
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result


def app_is_busy_for_update():
    """True when an in-progress download should delay restart."""
    try:
        return is_site_download_running() or is_direct_download_active()
    except Exception:
        return False


def source_working_tree_is_clean(repo_root):
    status = run_git_command(["status", "--porcelain"], repo_root)
    if status.returncode != 0:
        raise RuntimeError(status.stderr.strip() or status.stdout.strip() or "git status failed")
    return not (status.stdout or "").strip()

def run_git_command(args, cwd, timeout=60):
    """Run a git command and return CompletedProcess."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

def restart_source_app():
    """Restart the source app process with the current CLI args."""
    try:
        target_script = Path(sys.argv[0]).resolve() if sys.argv else Path(__file__).resolve()
        launch_args = [sys.executable, str(target_script), *sys.argv[1:]]
        subprocess.Popen(launch_args, cwd=str(get_project_root()))
        ui_queue.put(lambda: root.after(400, exit_application))
        return True
    except Exception as restart_error:
        app_update_log(f"Could not restart automatically: {restart_error}")
        return False

def check_and_apply_source_git_update(user_initiated=False):
    """Fast-forward the local source checkout when the tree is clean."""
    settings = get_source_update_settings()
    if not settings["source_auto_pull"] and not user_initiated:
        app_update_log("Source auto-pull is disabled in app_flags.json.")
        return False

    repo_root = get_project_root()
    if not (repo_root / ".git").exists():
        app_update_log("Source auto-update skipped: project is not a git checkout.")
        return False

    if not shutil.which("git"):
        app_update_log("Source auto-update skipped: git is not installed.")
        if user_initiated:
            show_error_threadsafe("Git Not Found", "Git is required for source auto-update but was not found on PATH.")
        return False

    try:
        if not source_working_tree_is_clean(repo_root):
            app_update_log("Source auto-update skipped: local repository has uncommitted changes.")
            if user_initiated:
                refresh_update_system_ui(
                    status="Local git changes are present, so source pull was skipped.",
                    apply_enabled=False,
                )
            return False

        branch = settings["source_branch"]
        if branch.lower() == "auto":
            branch_proc = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
            if branch_proc.returncode != 0:
                raise RuntimeError(branch_proc.stderr.strip() or "Could not detect current branch")
            branch = (branch_proc.stdout or "").strip() or "main"

        remote = settings["source_remote"] or "origin"
        app_update_log(f"Checking git updates from {remote}/{branch}...")
        begin_dep_job("app-update", "App update", f"Checking git updates from {remote}/{branch}...", indeterminate=True)
        fetch_proc = run_git_command(["fetch", "--prune", remote, branch], repo_root, timeout=120)
        if fetch_proc.returncode != 0:
            raise RuntimeError(fetch_proc.stderr.strip() or "git fetch failed")

        behind_proc = run_git_command(["rev-list", "--count", f"HEAD..{remote}/{branch}"], repo_root)
        if behind_proc.returncode != 0:
            raise RuntimeError(behind_proc.stderr.strip() or "Could not compare local and remote revisions")
        behind_count = int((behind_proc.stdout or "0").strip() or "0")
        if behind_count <= 0:
            app_update_log("Source repository already up to date.")
            return False

        app_update_log(f"Pulling {behind_count} new commit(s) from {remote}/{branch}...")
        update_dep_job(
            "app-update",
            message=f"Pulling {behind_count} update(s) from {remote}/{branch}...",
            title="App update",
            indeterminate=True,
        )
        pull_proc = run_git_command(["pull", "--ff-only", remote, branch], repo_root, timeout=180)
        if pull_proc.returncode != 0:
            raise RuntimeError(pull_proc.stderr.strip() or pull_proc.stdout.strip() or "git pull failed")

        app_update_log("Source update applied successfully.")
        set_status_threadsafe("Source update applied")
        refresh_update_system_ui(status="Source update applied. Restart the app to load it.", apply_enabled=False)
        if settings["source_auto_restart_after_pull"] or user_initiated:
            if not restart_source_app():
                show_info_threadsafe("Update Applied", "Source was updated. Please restart the app to use the new code.")
        return True
    except Exception as update_error:
        app_update_log(f"Source auto-update error: {update_error}")
        if user_initiated:
            refresh_update_system_ui(status=f"Source update failed: {update_error}", apply_enabled=False)
            show_error_threadsafe("Source Update Failed", f"Could not update from git:\n{update_error}")
        return False
    finally:
        end_dep_job("app-update")

def check_updates_on_startup(user_initiated=False):
    """Check GitHub for a newer release in the background and apply it safely."""
    global FORCE_UPDATE_CHECK

    update_started = False
    try:
        if not should_check_for_updates() and not user_initiated:
            return False

        if user_initiated:
            begin_dep_job("app-update", "App update", "Checking for updates...", indeterminate=True)
            refresh_update_system_ui(status="Checking GitHub for updates…", apply_enabled=False)
        app_update_log("Checking GitHub for a newer application release...")
        info = fetch_latest_release_info()
        _update_system_state["release_info"] = info
        update_check_timestamp()

        if not info.get("ok"):
            app_update_log(info.get("error") or "Update check failed.")
            refresh_update_system_ui(info, apply_enabled=False)
            if user_initiated:
                show_error_threadsafe(
                    "Update Check Failed",
                    f"{info.get('error') or 'Could not check for updates.'}\n\nPlease check your internet connection.",
                )
            return False

        refresh_update_system_ui(info, apply_enabled=bool(info.get("is_newer")))
        if not info.get("is_newer"):
            app_update_log(f"Already up to date ({CURRENT_VERSION}).")
            if user_initiated:
                set_status_threadsafe("You have the latest version")
            return False

        latest_version = info.get("latest_version")
        app_update_log(f"New version {latest_version} is available.")
        set_status_threadsafe(f"Update {latest_version} is available")

        should_apply = bool(_update_system_state.get("auto_apply")) or (not user_initiated)
        if is_packaged_runtime():
            if not is_packaged_auto_update_enabled() and not user_initiated:
                app_update_log("Packaged auto-update is disabled in app_flags.json.")
                return False
            if should_apply:
                update_started = download_and_install_update(info["release"], user_initiated=user_initiated)
        elif user_initiated and should_apply:
            update_started = check_and_apply_source_git_update(user_initiated=True)
        elif not user_initiated:
            settings = get_source_update_settings()
            if settings["source_auto_pull"]:
                update_started = check_and_apply_source_git_update(user_initiated=False)

        return update_started
    except Exception as exc:
        app_update_log(f"Error in update check process: {exc}")
        if user_initiated:
            show_error_threadsafe(
                "Update Check Failed",
                f"Failed to check for updates: {exc}\n\nPlease check your internet connection.",
            )
        return False
    finally:
        FORCE_UPDATE_CHECK = False
        _update_system_state["checking"] = False
        if not update_started:
            end_dep_job("app-update")


def check_for_updates():
    """Return the latest GitHub release when it is newer than this install."""
    info = fetch_latest_release_info()
    _update_system_state["release_info"] = info
    if info.get("ok") and info.get("is_newer"):
        return info.get("release")
    return None

def schedule_install_and_exit(installer_path):
    """Install after the app is idle so an in-progress download is not interrupted."""
    global _pending_update_installer
    _pending_update_installer = Path(installer_path)
    launch_background_update_installer(installer_path)
    update_dep_job(
        "app-update",
        message="Update downloaded. The app will restart when it is idle...",
        title="App update",
        indeterminate=True,
    )

    def try_exit():
        if app_is_busy_for_update():
            set_status_threadsafe("Update is ready. Waiting for current downloads to finish...")
            root.after(1500, try_exit)
            return
        set_status_threadsafe("Restarting to finish the update...")
        exit_application()

    _run_on_ui(lambda: root.after(400, try_exit))


def apply_available_update(user_initiated=True):
    """Apply the latest checked release from the Update System window."""
    if _update_system_state.get("applying"):
        return False
    info = _update_system_state.get("release_info") or {}
    if not info.get("is_newer"):
        start_app_update_check(user_initiated=True)
        return False

    def worker():
        _update_system_state["applying"] = True
        try:
            if is_packaged_runtime():
                download_and_install_update(info.get("release"), user_initiated=user_initiated)
            else:
                if not check_and_apply_source_git_update(user_initiated=True):
                    release_url = info.get("release_url") or f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest"
                    refresh_update_system_ui(
                        info,
                        status="Could not pull source automatically. Opening the GitHub release page.",
                        apply_enabled=True,
                    )
                    webbrowser.open(release_url)
        finally:
            _update_system_state["applying"] = False

    threading.Thread(target=worker, daemon=True).start()
    return True


def download_and_install_update(release, user_initiated=False):
    """Download the packaged installer in the background and restart when idle."""
    succeeded = False
    try:
        if isinstance(release, str):
            info = fetch_latest_release_info()
            if not info.get("ok") or not info.get("release"):
                raise RuntimeError(info.get("error") or "Could not fetch release data")
            release = info["release"]
            latest_version = info.get("latest_version") or release.get("tag_name", "").lstrip("v")
        else:
            latest_version = str((release or {}).get("tag_name", "")).lstrip("v")

        if not is_packaged_runtime():
            return False

        installer_asset = get_preferred_update_asset(release, require_installer=True)
        if not installer_asset:
            installer_asset = get_preferred_update_asset(release, require_installer=False)
        if not installer_asset:
            raise RuntimeError("No Windows installer was found in the latest GitHub release.")

        update_dir = get_app_update_dir()
        safe_version = re.sub(r"[^A-Za-z0-9._-]+", "_", latest_version or "latest")
        exe_path = update_dir / f"{safe_version}-{installer_asset['name']}"
        part_path = Path(str(exe_path) + ".part")

        if exe_path.exists() and exe_path.stat().st_size > 0:
            app_update_log(f"Using already downloaded installer: {exe_path}")
            schedule_install_and_exit(exe_path)
            succeeded = True
            return True

        download_url = installer_asset["browser_download_url"]
        app_update_log(f"Downloading update installer for version {latest_version}...")
        begin_dep_job("app-update", "App update", f"Downloading update {latest_version}...", percent=0)
        refresh_update_system_ui(status=f"Downloading update {latest_version}…", apply_enabled=False)

        response = requests.get(download_url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0
        last_logged_bucket = -1
        last_ui_percent = -2
        last_ui_at = 0.0
        last_unknown_report = 0

        with open(part_path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=256 * 1024):
                if not chunk:
                    continue
                downloaded += len(chunk)
                handle.write(chunk)
                now = time.monotonic()
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    ui_percent = int(percent)
                    if ui_percent >= last_ui_percent + 2 or now - last_ui_at >= 0.4:
                        last_ui_percent = ui_percent
                        last_ui_at = now
                        update_dep_job(
                            "app-update",
                            message=f"Downloading update {latest_version}... {ui_percent}%",
                            percent=ui_percent,
                            title="App update",
                        )
                    bucket = int(percent // 25)
                    if bucket > last_logged_bucket:
                        last_logged_bucket = bucket
                        app_update_log(f"Download progress: {percent:.0f}%")
                elif downloaded - last_unknown_report >= 4 * 1024 * 1024:
                    last_unknown_report = downloaded
                    update_dep_job(
                        "app-update",
                        message=f"Downloading update {latest_version}... {downloaded / (1024 * 1024):.1f} MB",
                        title="App update",
                        indeterminate=True,
                    )

        if downloaded <= 0:
            raise RuntimeError("The update download returned no data.")
        shutil.move(str(part_path), str(exe_path))
        app_update_log(f"Installer downloaded to: {exe_path}")
        schedule_install_and_exit(exe_path)
        succeeded = True
        return True
    except Exception as exc:
        error_msg = str(exc)
        app_update_log(f"Error installing update: {error_msg}")
        refresh_update_system_ui(status=f"Update failed: {error_msg}", apply_enabled=True)
        if user_initiated:
            show_error_threadsafe("Update Error", f"Failed to install update: {error_msg}")
        else:
            set_status_threadsafe("App update failed")
        return False
    finally:
        if not succeeded:
            end_dep_job("app-update")
            try:
                part_path = locals().get("part_path")
                if part_path and Path(part_path).exists():
                    Path(part_path).unlink()
            except Exception:
                pass

def start_app_update_check(user_initiated=False):
    """Run the app update check in a single background worker."""
    global FORCE_UPDATE_CHECK, app_update_thread

    if user_initiated:
        FORCE_UPDATE_CHECK = True
        _update_system_state["checking"] = True

    with app_update_lock:
        if app_update_thread is not None and app_update_thread.is_alive():
            app_update_log("An app update check is already running in the background.")
            if user_initiated:
                set_status_threadsafe("An update check is already running...")
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
            begin_dep_job("ffmpeg", "FFmpeg download / update", "Installing or updating FFmpeg...", indeterminate=True)
        else:
            ffmpeg_log("Automatic FFmpeg startup check started.")
            set_status_threadsafe("Checking FFmpeg in background...")

        resolved_ffmpeg_path, resolved_ffprobe_path, updated = update_managed_ffmpeg_if_needed(
            logger=ffmpeg_log,
            progress_callback=ffmpeg_download_progress,
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
    finally:
        end_dep_job("ffmpeg")


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
            "FFmpeg",
            "Bundled FFmpeg install/update started in the background.\n\n"
            "You can keep using the app while it finishes.",
        )


_ffmpeg_settings_window = None


def _ffmpeg_status_text():
    custom_ffmpeg, _custom_ffprobe = get_custom_ffmpeg_paths()
    current = ffmpeg_path if ffmpeg_path and os.path.exists(ffmpeg_path) else None
    if not current:
        found_ffmpeg, _found_ffprobe = find_existing_ffmpeg()
        current = found_ffmpeg
    if not current:
        return "Not set", "Not found", False
    source = "Custom path" if custom_ffmpeg else "Automatic"
    version = get_ffmpeg_version_line(current)
    status = version.split("Copyright", 1)[0].strip() if version else "Ready"
    return str(current), f"{source}  ·  {status}", True


def open_ffmpeg_settings():
    """Compact FFmpeg path and install dialog."""
    global _ffmpeg_settings_window, _ffmpeg_settings_progress

    if _ffmpeg_settings_window is not None and _ffmpeg_settings_window.winfo_exists():
        _ffmpeg_settings_window.lift()
        _ffmpeg_settings_window.focus_force()
        return _ffmpeg_settings_window

    win = tk.Toplevel(root)
    _ffmpeg_settings_window = win
    win.title("FFmpeg")
    win.configure(bg=THEME["bg"])
    win.resizable(False, False)
    apply_window_icon(win)
    win.transient(root)

    def close_window():
        global _ffmpeg_settings_window, _ffmpeg_settings_progress
        _ffmpeg_settings_progress = None
        try:
            win.destroy()
        except Exception:
            pass
        if _ffmpeg_settings_window is win:
            _ffmpeg_settings_window = None

    win.protocol("WM_DELETE_WINDOW", close_window)

    path_var = tk.StringVar()
    status_var = tk.StringVar()
    note_var = tk.StringVar()

    def refresh_status(note=""):
        path_text, status_text, ready = _ffmpeg_status_text()
        path_var.set(path_text)
        status_var.set(status_text)
        status_label.configure(fg=THEME["success"] if ready else THEME["error"])
        if note:
            note_var.set(note)
        elif ready:
            note_var.set("")
        else:
            note_var.set("Install FFmpeg, or choose an existing ffmpeg.exe")

    def _small_button(parent, text, command, *, primary=False):
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", 9, "bold" if primary else "normal"),
            bg=THEME["primary"] if primary else THEME["light_gray"],
            fg="#ffffff" if primary else THEME["fg"],
            activebackground=THEME["secondary"] if primary else THEME["border"],
            activeforeground="#ffffff" if primary else THEME["fg"],
            relief="flat",
            padx=8,
            pady=5,
            cursor="hand2",
        )

    def change_path():
        selected = filedialog.askopenfilename(
            parent=win,
            title="Choose ffmpeg.exe",
            filetypes=[("FFmpeg", "ffmpeg.exe"), ("All files", "*.*")],
        )
        if not selected:
            return
        try:
            resolved_ffmpeg, resolved_ffprobe = set_custom_ffmpeg_paths(selected)
        except Exception as exc:
            messagebox.showerror("FFmpeg", str(exc), parent=win)
            return
        apply_ffmpeg_runtime_paths(resolved_ffmpeg, resolved_ffprobe)
        ffmpeg_log(f"Using custom FFmpeg: {resolved_ffmpeg}")
        refresh_status("Custom path saved.")

    def restore_default_path():
        clear_custom_ffmpeg_paths()
        ffmpeg_log("Custom FFmpeg path cleared. Restoring automatic detection...")
        start_ffmpeg_background_sync(force_update=False, user_initiated=True)
        refresh_status("Default path restored.")

    def copy_winget_command():
        command = f"winget install {FFMPEG_WINGET_PACKAGE}"
        try:
            pyperclip.copy(command)
            refresh_status(f"Copied: {command}")
        except Exception:
            refresh_status(command)

    def run_winget_install():
        refresh_status("Installing with winget...")
        begin_dep_job("ffmpeg", "FFmpeg download / update", f"Installing FFmpeg with winget ({FFMPEG_WINGET_PACKAGE})...", indeterminate=True)

        def worker():
            try:
                ffmpeg_log(f"Installing FFmpeg with winget ({FFMPEG_WINGET_PACKAGE})...")
                resolved_ffmpeg, resolved_ffprobe = install_ffmpeg_with_winget(logger=ffmpeg_log)
                if not apply_ffmpeg_runtime_paths(resolved_ffmpeg, resolved_ffprobe):
                    raise RuntimeError("Installed, but FFmpeg is not on PATH yet. Restart the app or choose the path.")
                ffmpeg_log(f"FFmpeg configured from winget: {resolved_ffmpeg}")
                ui_queue.put(lambda: refresh_status("FFmpeg is ready."))
            except Exception as exc:
                ui_queue.put(lambda: refresh_status(str(exc).split("\n", 1)[0]))
                ui_queue.put(lambda: messagebox.showerror("FFmpeg", str(exc), parent=win))
            finally:
                end_dep_job("ffmpeg")

        threading.Thread(target=worker, daemon=True).start()

    def open_download_page():
        webbrowser.open(FFMPEG_DOWNLOAD_PAGE)

    pad = {"padx": 14, "pady": 0}
    tk.Label(win, text="FFmpeg", font=("Segoe UI", 14, "bold"), fg=THEME["fg"], bg=THEME["bg"]).pack(
        anchor="w", padx=14, pady=(14, 2)
    )
    status_label = tk.Label(win, textvariable=status_var, font=("Segoe UI", 9), fg=THEME["primary"], bg=THEME["bg"])
    status_label.pack(anchor="w", **pad)

    path_box = tk.Label(
        win,
        textvariable=path_var,
        font=("Segoe UI", 9),
        fg=THEME["fg"],
        bg=THEME["light_gray"],
        justify="left",
        wraplength=400,
        anchor="w",
        padx=8,
        pady=6,
    )
    path_box.pack(fill="x", padx=14, pady=(8, 8))

    path_row = tk.Frame(win, bg=THEME["bg"])
    path_row.pack(fill="x", padx=14, pady=(0, 10))
    path_row.columnconfigure(0, weight=1)
    path_row.columnconfigure(1, weight=1)
    _small_button(path_row, "Change path", change_path, primary=True).grid(row=0, column=0, sticky="ew", padx=(0, 4))
    _small_button(path_row, "Restore default", restore_default_path).grid(row=0, column=1, sticky="ew", padx=(4, 0))

    tk.Label(win, text="Install if needed", font=("Segoe UI", 10, "bold"), fg=THEME["fg"], bg=THEME["bg"]).pack(
        anchor="w", padx=14, pady=(2, 2)
    )
    tk.Label(
        win,
        text=f"Windows: winget install {FFMPEG_WINGET_PACKAGE}\nOr download from ffmpeg.org and add bin to PATH",
        font=("Segoe UI", 9),
        fg=THEME["gray"],
        bg=THEME["bg"],
        justify="left",
    ).pack(anchor="w", padx=14, pady=(0, 8))

    install_row = tk.Frame(win, bg=THEME["bg"])
    install_row.pack(fill="x", padx=14)
    install_row.columnconfigure(0, weight=1)
    install_row.columnconfigure(1, weight=1)
    if IS_WINDOWS:
        _small_button(install_row, "Install with winget", run_winget_install, primary=True).grid(
            row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 6)
        )
        _small_button(install_row, "Copy command", copy_winget_command).grid(
            row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 6)
        )
        _small_button(install_row, "Open ffmpeg.org", open_download_page).grid(
            row=1, column=0, sticky="ew", padx=(0, 4)
        )
        _small_button(install_row, "Update bundled", force_install_or_update_ffmpeg).grid(
            row=1, column=1, sticky="ew", padx=(4, 0)
        )
    else:
        _small_button(install_row, "Open ffmpeg.org", open_download_page, primary=True).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        _small_button(install_row, "Update bundled", force_install_or_update_ffmpeg).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

    tk.Label(win, textvariable=note_var, font=("Segoe UI", 8), fg=THEME["gray"], bg=THEME["bg"], wraplength=400, justify="left").pack(
        anchor="w", padx=14, pady=(8, 0)
    )
    _ffmpeg_settings_progress = DependencyProgressPanel(
        win,
        background=THEME["bg"],
        foreground=THEME["fg"],
        muted=THEME["gray"],
        bar_style="Modern.Horizontal.TProgressbar",
        wraplength=390,
        use_ttk=False,
        layout="pack",
        layout_kwargs={"fill": "x", "padx": 14, "pady": (8, 0)},
    )
    _small_button(win, "Done", close_window, primary=True).pack(fill="x", padx=14, pady=(8, 14))

    refresh_status()
    win.update_idletasks()
    width = max(420, win.winfo_reqwidth())
    height = max(win.winfo_reqheight() + 8, 320)
    win.geometry(f"{width}x{height}")
    center_window(win, root)
    win.lift()
    win.focus_force()
    return win


def restore_default_settings():
    """Reset download folder, quality, format, and FFmpeg path to defaults."""
    confirmed = messagebox.askyesno(
        "Restore default settings",
        "Reset download folder, quality, format, playlist options, and FFmpeg path to defaults?",
    )
    if not confirmed:
        return

    defaults = default_app_settings()
    video_quality_var.set(defaults["video_quality"])
    audio_quality_var.set(defaults["audio_quality"])
    format_var.set(defaults["format"])
    quality_settings["video_quality"] = defaults["video_quality"]
    quality_settings["audio_quality"] = defaults["audio_quality"]
    quality_settings["format"] = defaults["format"]
    if "download_playlist" in globals():
        download_playlist.set(defaults["download_playlist"])
    if "max_files_entry" in globals():
        max_files_entry.configure(state="normal")
        max_files_entry.delete(0, tk.END)
        max_files_entry.insert(0, defaults["max_files"])
        max_files_entry.configure(state="normal" if defaults["download_playlist"] else "disabled")
    apply_download_root(defaults["download_root"], persist=False)
    clear_custom_ffmpeg_paths()
    save_app_settings()
    start_ffmpeg_background_sync(force_update=False, user_initiated=True)
    log("Restored default settings.")
    messagebox.showinfo("Settings", "Default settings restored.")

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
file_menu.add_command(label="Exit", command=lambda: exit_application())

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
settings_menu.add_command(label="FFmpeg...", command=open_ffmpeg_settings)
settings_menu.add_command(label="Restore Default Settings", command=restore_default_settings)

# Tools Menu
tools_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Tools", menu=tools_menu)
tools_menu.add_command(label="Video Converter", accelerator=CONVERTER_HOTKEY_LABEL, command=open_converter)
tools_menu.add_command(label="BG Remover", accelerator=BG_REMOVER_HOTKEY_LABEL, command=open_background_remover)
tools_menu.add_command(label="YScreenshot", accelerator=SCREENSHOT_HOTKEY_LABEL, command=open_screenshot_studio)
tools_menu.add_command(label="YScreenRecorder", accelerator=SCREENRECORDER_HOTKEY_LABEL, command=open_yscreenrecorder)
tools_menu.add_separator()
tools_menu.add_command(label="Anika", accelerator=ANIKA_HOTKEY_LABEL, command=open_anika)

# Help Menu
help_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Help", menu=help_menu)
help_menu.add_command(label="About Us", command=show_about_window)
help_menu.add_command(label="Check for Updates", command=lambda: force_check_updates())
help_menu.add_separator()
help_menu.add_command(label="Report Issue", 
    command=lambda: webbrowser.open("https://github.com/needyamin/media-downloader/issues"))

def force_check_updates():
    """Open the updater and apply a newer release when one is available."""
    set_status_threadsafe("Checking for app updates in background...")
    open_update_system(start_check=True, auto_apply=True)

# Custom Widget Classes
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

def clear_activity_log():
    """Clear all entries from the activity log box."""
    global last_visible_log_message
    if 'output_box' not in globals():
        return
    try:
        output_box.config(state='normal')
        output_box.delete('1.0', tk.END)
        output_box.config(state='disabled')
        last_visible_log_message = None
        if 'status_label' in globals():
            status_label.config(text="Activity log cleared")
    except Exception as exc:
        if DEBUG_MODE:
            print(f"[Yamin Downloader] Failed to clear activity log: {exc}")

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

internet_status_var = tk.StringVar(value="Network: checking...")
internet_status_label = tk.Label(
    header_frame,
    textvariable=internet_status_var,
    font=('Segoe UI', 10, 'bold'),
    bg=THEME['bg'],
    fg=THEME['gray'],
)
internet_status_label.pack(side='right', padx=(10, 0), pady=(10, 0))

def _apply_internet_status(connected):
    if connected:
        internet_status_var.set("Network: online")
        internet_status_label.config(fg='#16A34A')
    else:
        internet_status_var.set("Network: offline")
        internet_status_label.config(fg=THEME['error'])

def schedule_internet_status_check():
    """Check internet in background and refresh header status."""
    internet_status_var.set("Network: checking...")
    internet_status_label.config(fg=THEME['gray'])
    def _worker():
        connected = check_internet_connection()
        root.after(0, lambda: _apply_internet_status(connected))
    threading.Thread(target=_worker, daemon=True).start()
    root.after(12000, schedule_internet_status_check)

schedule_internet_status_check()

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
url_entry.bind("<KeyRelease>", lambda _event: schedule_url_preview_refresh())
url_entry.bind("<FocusOut>", lambda _event: schedule_url_preview_refresh())

URL_PREVIEW_THUMB_SIZE = (220, 124)

url_preview_frame = tk.Frame(
    url_frame,
    bg=THEME['light_gray'],
    bd=0,
    relief='flat',
    highlightthickness=1,
    highlightbackground=THEME['border'],
    highlightcolor=THEME['border'],
)
url_preview_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
url_preview_frame.grid_columnconfigure(1, weight=1)

url_preview_thumb_wrap = tk.Frame(
    url_preview_frame,
    bg=THEME['light_gray'],
    width=URL_PREVIEW_THUMB_SIZE[0],
    height=URL_PREVIEW_THUMB_SIZE[1],
)
url_preview_thumb_wrap.grid(row=0, column=0, padx=12, pady=12, sticky="nw")
url_preview_thumb_wrap.grid_propagate(False)

url_preview_thumb_label = tk.Label(
    url_preview_thumb_wrap,
    bg=THEME['light_gray'],
    anchor='center',
)
url_preview_thumb_label.pack(fill="both", expand=True)

url_preview_text_var = tk.StringVar(value="Paste or type a supported URL to preview thumbnail and metadata.")
url_preview_text_label = tk.Label(
    url_preview_frame,
    textvariable=url_preview_text_var,
    font=('Segoe UI', 9),
    bg=THEME['light_gray'],
    fg=THEME['fg'],
    anchor='nw',
    justify='left',
    wraplength=470,
)
url_preview_text_label.grid(row=0, column=1, padx=(0, 12), pady=12, sticky="nsew")

url_preview_job = None
url_preview_request_id = 0
url_preview_image = None
url_preview_visible = False
url_preview_spinner_job = None
url_preview_spinner_index = 0

url_preview_frame.grid_remove()

download_path_frame = tk.Frame(url_frame, bg=THEME['bg'])
download_path_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
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

def _format_duration_text(seconds):
    try:
        total = int(float(seconds))
    except Exception:
        return "Unknown"
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def _is_previewable_url(url):
    """Return True when URL looks like a valid web URL for preview."""
    try:
        parsed = urlparse(str(url).strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False

def _stop_url_preview_spinner():
    global url_preview_spinner_job
    if url_preview_spinner_job is not None:
        try:
            root.after_cancel(url_preview_spinner_job)
        except Exception:
            pass
        url_preview_spinner_job = None
    try:
        if url_preview_text_var.get().startswith("Loading preview..."):
            url_preview_text_var.set("Loading preview...")
    except Exception:
        pass

def _start_url_preview_spinner():
    global url_preview_spinner_job, url_preview_spinner_index
    _stop_url_preview_spinner()
    url_preview_spinner_index = 0

    def _tick():
        global url_preview_spinner_job, url_preview_spinner_index
        frames = ["◐", "◓", "◑", "◒"]
        marker = frames[url_preview_spinner_index % len(frames)]
        url_preview_spinner_index += 1
        url_preview_text_var.set(f"Loading preview... {marker}")
        url_preview_spinner_job = root.after(60, _tick)

    _tick()

def _apply_url_preview_result(request_id, url_snapshot, title, uploader, duration_text, source_label, thumb_pil_image):
    global url_preview_image, url_preview_visible
    current_url = ""
    try:
        current_url = url_entry.get().strip()
    except Exception:
        current_url = ""
    if request_id != url_preview_request_id and current_url != (url_snapshot or "").strip():
        return
    _stop_url_preview_spinner()

    if not url_preview_visible:
        url_preview_frame.grid()
        url_preview_visible = True

    parts = []
    if title:
        parts.append(f"Title: {title}")
    if uploader:
        parts.append(f"Uploader: {uploader}")
    if duration_text:
        parts.append(f"Duration: {duration_text}")
    if source_label:
        parts.append(f"Source: {source_label}")

    if parts:
        url_preview_text_var.set("\n".join(parts))
    else:
        url_preview_text_var.set("Preview not available for this URL yet.")

    if thumb_pil_image is not None:
        url_preview_image = ImageTk.PhotoImage(thumb_pil_image)
        url_preview_thumb_label.configure(image=url_preview_image, text="")
    else:
        url_preview_image = None
        url_preview_thumb_label.configure(image="", text="")

def _clear_url_preview(request_id, url_snapshot):
    global url_preview_visible
    current_url = ""
    try:
        current_url = url_entry.get().strip()
    except Exception:
        current_url = ""
    if request_id != url_preview_request_id and current_url != (url_snapshot or "").strip():
        return
    _stop_url_preview_spinner()
    if not url_preview_visible:
        url_preview_frame.grid()
        url_preview_visible = True
    url_preview_text_var.set("No metadata available for this URL.")
    url_preview_thumb_label.configure(image="", text="")

def _fetch_url_preview_worker(url, request_id):
    info = None
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as preview_ydl:
            info = preview_ydl.extract_info(url, download=False)
    except Exception:
        info = None

    # Fallback for direct file URLs when yt-dlp metadata is unavailable.
    if not info:
        try:
            direct_title = Path(urlparse(url).path).name or "Direct file"
            if "%" in direct_title:
                direct_title = unquote(direct_title)

            headers = {}
            try:
                head_response = requests.head(url, timeout=8, allow_redirects=True)
                headers = dict(head_response.headers or {})
                if head_response.status_code >= 400:
                    get_response = requests.get(url, timeout=8, allow_redirects=True, stream=True)
                    headers = dict(get_response.headers or {})
                    get_response.close()
            except Exception:
                headers = {}

            content_type = (headers.get("Content-Type") or "").split(";")[0].strip()
            content_length_raw = headers.get("Content-Length") or ""
            size_text = ""
            try:
                size_bytes = int(content_length_raw)
                if size_bytes > 0:
                    size_text = humanize.naturalsize(size_bytes, binary=True)
            except Exception:
                size_text = ""

            source_bits = ["Direct Download"]
            if content_type:
                source_bits.append(content_type)
            if size_text:
                source_bits.append(size_text)
            source_label = " | ".join(source_bits)

            root.after(
                0,
                lambda rid=request_id, u=url, t=direct_title, s=source_label:
                _apply_url_preview_result(rid, u, t, "", "", s, None)
            )
            return
        except Exception:
            root.after(0, lambda rid=request_id, u=url: _clear_url_preview(rid, u))
            return

    playlist_info = None
    if isinstance(info, dict) and info.get('_type') == 'playlist':
        playlist_info = info
        first_entry = next((entry for entry in info.get('entries', []) if isinstance(entry, dict)), None)
        if first_entry:
            info = first_entry
        else:
            info = playlist_info

    title = str(info.get('title') or "Unknown title")
    uploader = str(info.get('uploader') or info.get('channel') or "")
    duration_text = _format_duration_text(info.get('duration'))
    source_label = str(info.get('extractor_key') or info.get('extractor') or "")
    thumbnail_url = info.get('thumbnail')

    if playlist_info is not None:
        playlist_title = str(playlist_info.get('title') or "").strip()
        if playlist_title:
            title = playlist_title
        playlist_uploader = str(
            playlist_info.get('uploader')
            or playlist_info.get('channel')
            or playlist_info.get('creator')
            or ""
        ).strip()
        if playlist_uploader:
            uploader = playlist_uploader
        source_label = "Playlist"
        thumbnail_url = (
            playlist_info.get('thumbnail')
            or thumbnail_url
            or (info.get('thumbnail') if isinstance(info, dict) else None)
        )

    thumb_pil_image = None
    if thumbnail_url:
        try:
            response = requests.get(thumbnail_url, timeout=8)
            response.raise_for_status()
            image = Image.open(io.BytesIO(response.content)).convert("RGB")
            image.thumbnail(URL_PREVIEW_THUMB_SIZE, Image.Resampling.LANCZOS)
            thumb_pil_image = image
        except Exception:
            thumb_pil_image = None

    root.after(
        0,
        lambda rid=request_id, preview_url=url, t=title, u=uploader, d=duration_text, s=source_label, img=thumb_pil_image:
        _apply_url_preview_result(rid, preview_url, t, u, d, s, img)
    )

def schedule_url_preview_refresh():
    global url_preview_job, url_preview_request_id, url_preview_visible, url_preview_image
    if 'url_entry' not in globals():
        return

    if url_preview_job is not None:
        try:
            root.after_cancel(url_preview_job)
        except Exception:
            pass
        url_preview_job = None

    def _run_preview():
        global url_preview_request_id, url_preview_job, url_preview_visible, url_preview_image
        url_preview_job = None
        url = url_entry.get().strip()
        if not url:
            if url_preview_visible:
                url_preview_frame.grid_remove()
                url_preview_visible = False
            _stop_url_preview_spinner()
            url_preview_text_var.set("Paste or type a supported URL to preview thumbnail and metadata.")
            url_preview_thumb_label.configure(image="", text="")
            url_preview_image = None
            return
        if not url_preview_visible:
            url_preview_frame.grid()
            url_preview_visible = True
        if not _is_previewable_url(url):
            _stop_url_preview_spinner()
            url_preview_text_var.set("Enter a valid URL to preview metadata.")
            url_preview_thumb_label.configure(image="", text="")
            url_preview_image = None
            return
        url_preview_text_var.set("Loading preview...")
        url_preview_thumb_label.configure(image="", text="")
        url_preview_image = None
        _start_url_preview_spinner()
        url_preview_request_id += 1
        request_id = url_preview_request_id
        threading.Thread(target=_fetch_url_preview_worker, args=(url, request_id), daemon=True).start()

    url_preview_job = root.after(450, _run_preview)

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
converter_hotkey_registered = False
background_remover_hotkey_registered = False
screenshot_hotkey_registered = False
screenrecorder_hotkey_registered = False
anika_hotkey_registered = False

def _run_screenshot_hotkey_listener():
    """Listen for the global desktop tool hotkeys while the app is in the background."""
    global screenshot_hotkey_thread_id, converter_hotkey_registered, background_remover_hotkey_registered
    global screenshot_hotkey_registered, screenrecorder_hotkey_registered, anika_hotkey_registered

    if not IS_WINDOWS:
        return

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    screenshot_hotkey_thread_id = int(kernel32.GetCurrentThreadId())
    message = wintypes.MSG()

    try:
        converter_registered = bool(user32.RegisterHotKey(None, CONVERTER_HOTKEY_ID, CONVERTER_HOTKEY_MODIFIERS, CONVERTER_HOTKEY_VK))
        if not converter_registered:
            log(f"Global converter hotkey unavailable: {CONVERTER_HOTKEY_LABEL}")

        background_remover_registered = bool(user32.RegisterHotKey(None, BG_REMOVER_HOTKEY_ID, BG_REMOVER_HOTKEY_MODIFIERS, BG_REMOVER_HOTKEY_VK))
        if not background_remover_registered:
            log(f"Global background remover hotkey unavailable: {BG_REMOVER_HOTKEY_LABEL}")

        screenshot_registered = bool(user32.RegisterHotKey(None, SCREENSHOT_HOTKEY_ID, SCREENSHOT_HOTKEY_MODIFIERS, SCREENSHOT_HOTKEY_VK))
        if not screenshot_registered:
            log(f"Global screenshot hotkey unavailable: {SCREENSHOT_HOTKEY_LABEL}")

        recorder_registered = bool(user32.RegisterHotKey(None, SCREENRECORDER_HOTKEY_ID, SCREENRECORDER_HOTKEY_MODIFIERS, SCREENRECORDER_HOTKEY_VK))
        if not recorder_registered:
            log(f"Global screen recorder hotkey unavailable: {SCREENRECORDER_HOTKEY_LABEL}")

        anika_registered = bool(user32.RegisterHotKey(None, ANIKA_HOTKEY_ID, ANIKA_HOTKEY_MODIFIERS, ANIKA_HOTKEY_VK))
        if not anika_registered:
            log(f"Global Anika hotkey unavailable: {ANIKA_HOTKEY_LABEL}")

        if not converter_registered and not background_remover_registered and not screenshot_registered and not recorder_registered and not anika_registered:
            return

        converter_hotkey_registered = converter_registered
        background_remover_hotkey_registered = background_remover_registered
        screenshot_hotkey_registered = screenshot_registered
        screenrecorder_hotkey_registered = recorder_registered
        anika_hotkey_registered = anika_registered
        if converter_registered:
            log(f"Global converter hotkey ready: {CONVERTER_HOTKEY_LABEL}")
        if background_remover_registered:
            log(f"Global background remover hotkey ready: {BG_REMOVER_HOTKEY_LABEL}")
        if screenshot_registered:
            log(f"Global screenshot hotkey ready: {SCREENSHOT_HOTKEY_LABEL}")
        if recorder_registered:
            log(f"Global screen recorder hotkey ready: {SCREENRECORDER_HOTKEY_LABEL}")
        if anika_registered:
            log(f"Global Anika hotkey ready: {ANIKA_HOTKEY_LABEL}")

        while True:
            result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
            if result in (0, -1):
                break

            if message.message == WM_HOTKEY:
                try:
                    hotkey_id = int(message.wParam)
                    if hotkey_id == CONVERTER_HOTKEY_ID:
                        root.after(0, trigger_converter)
                    elif hotkey_id == BG_REMOVER_HOTKEY_ID:
                        root.after(0, trigger_background_remover)
                    elif hotkey_id == SCREENSHOT_HOTKEY_ID:
                        root.after(0, trigger_screenshot_studio)
                    elif hotkey_id == SCREENRECORDER_HOTKEY_ID:
                        root.after(0, trigger_yscreenrecorder)
                    elif hotkey_id == ANIKA_HOTKEY_ID:
                        root.after(0, trigger_anika)
                except Exception as exc:
                    log(f"Error opening desktop tool from hotkey: {exc}")
    finally:
        if converter_hotkey_registered:
            try:
                user32.UnregisterHotKey(None, CONVERTER_HOTKEY_ID)
            except Exception:
                pass
        if background_remover_hotkey_registered:
            try:
                user32.UnregisterHotKey(None, BG_REMOVER_HOTKEY_ID)
            except Exception:
                pass
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
        if anika_hotkey_registered:
            try:
                user32.UnregisterHotKey(None, ANIKA_HOTKEY_ID)
            except Exception:
                pass
        converter_hotkey_registered = False
        background_remover_hotkey_registered = False
        screenshot_hotkey_registered = False
        screenrecorder_hotkey_registered = False
        anika_hotkey_registered = False
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
    text="Use Download List for direct file links with queue, resume, history, and broken-link replacement.",
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
    text="📋 Download List",
    bg='#4CAF50',
    fg='white',
    activebackground='#424242',
    activeforeground='white',
    font=('Segoe UI', 10, 'bold'),
    relief='flat',
    cursor='hand2',
    padx=20,
    pady=8,
    command=open_download_list_window
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
    text="Download List Activity",
    font=('Segoe UI', 10, 'bold'),
    bg=THEME['bg'],
    fg=THEME['fg']
)
direct_progress_title._grid_kwargs = {"row": 3, "column": 0, "sticky": "w", "pady": (14, 0)}
direct_progress_title.grid(**direct_progress_title._grid_kwargs)

direct_progress_label = tk.Label(
    progress_frame,
    text="Download list idle",
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

dep_progress_panel = DependencyProgressPanel(
    progress_frame,
    background=THEME["bg"],
    foreground=THEME["fg"],
    muted=THEME["gray"],
    bar_style="Modern.Horizontal.TProgressbar",
    wraplength=500,
    use_ttk=False,
    layout="grid",
    layout_kwargs={"row": 6, "column": 0, "sticky": "ew", "pady": (14, 0)},
)
if _dep_jobs:
    dep_progress_panel.show(title="Downloading or updating", message="Working…", indeterminate=True)

show_progress_section(None)

# Output Display
output_frame = tk.Frame(main_frame, bg=THEME['bg'])
output_frame.grid(row=4, column=0, sticky="nsew", pady=(0, 20))
output_frame.grid_rowconfigure(1, weight=1)
output_frame.grid_columnconfigure(0, weight=1)

output_header = tk.Frame(output_frame, bg=THEME['bg'])
output_header.grid(row=0, column=0, sticky="ew", pady=(0, 5))
output_header.grid_columnconfigure(0, weight=1)

output_label = tk.Label(
    output_header,
    text="Activity Log:",
    font=('Segoe UI', 12, 'bold'),
    bg=THEME['bg'],
    fg=THEME['fg']
)
output_label.grid(row=0, column=0, sticky="w")

clear_logs_btn = tk.Label(
    output_header,
    text="Clear Logs",
    font=('Segoe UI', 10),
    bg=THEME['bg'],
    fg=THEME['primary'],
    cursor='hand2',
)
clear_logs_btn.grid(row=0, column=1, sticky="e")
clear_logs_btn.bind('<Button-1>', lambda _event: clear_activity_log())
clear_logs_btn.bind('<Enter>', lambda _event: clear_logs_btn.config(fg=THEME['secondary']))
clear_logs_btn.bind('<Leave>', lambda _event: clear_logs_btn.config(fg=THEME['primary']))

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
status_frame.grid_columnconfigure(1, weight=0)

status_label = tk.Label(
    status_frame,
    text="Ready",
    font=('Segoe UI', 9),
    bg=THEME['border'],
    fg=THEME['fg']
)
status_label.grid(row=0, column=0, sticky="w", padx=10)

ansnew_credit_label = tk.Label(
    status_frame,
    text="ANSNEW TECH.",
    font=('Segoe UI', 9, 'bold'),
    bg=THEME['border'],
    fg=THEME['gray'],
    cursor='hand2'
)
ansnew_credit_label.grid(row=0, column=1, sticky="e", padx=10)
ansnew_credit_label.bind('<Enter>', lambda _event: ansnew_credit_label.config(fg=THEME['secondary']))
ansnew_credit_label.bind('<Leave>', lambda _event: ansnew_credit_label.config(fg=THEME['gray']))
ansnew_credit_label.bind('<Button-1>', lambda _event: webbrowser.open("https://inside.ansnew.com"))

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
        root.after(0, exit_application)
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
            item('FFmpeg...', lambda icon=None, menu_item=None: tray_run_ui_action(open_ffmpeg_settings)),
            item('Restore Default Settings', lambda icon=None, menu_item=None: tray_run_ui_action(restore_default_settings)),
        )),
        item('Tools', pystray.Menu(
            item('Video Converter', lambda icon=None, menu_item=None: tray_run_ui_action(open_converter)),
            item('BG Remover', lambda icon=None, menu_item=None: tray_run_ui_action(open_background_remover)),
            item('YScreenshot', lambda icon=None, menu_item=None: tray_run_ui_action(open_screenshot_studio)),
            item('YScreenRecorder', lambda icon=None, menu_item=None: tray_run_ui_action(open_yscreenrecorder)),
            item('Anika', lambda icon=None, menu_item=None: tray_run_ui_action(open_anika)),
        )),
        item('Help', pystray.Menu(
            item('About Us', lambda icon=None, menu_item=None: tray_run_ui_action(show_about_window)),
            item('Check for Updates', lambda icon=None, menu_item=None: tray_run_ui_action(force_check_updates)),
            item('Report Issue', lambda icon=None, menu_item=None: tray_run_ui_action(lambda: webbrowser.open("https://github.com/needyamin/media-downloader/issues"))),
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

def close_hub_owned_windows():
    """Close auxiliary windows owned by the main hub."""
    close_download_list_window()
    close_about_window()
    try:
        if debug_update_window is not None and debug_update_window.winfo_exists():
            close_debug_update_window()
    except Exception:
        pass
    try:
        if error_dialog_window is not None and error_dialog_window.winfo_exists():
            close_error_dialog()
    except Exception:
        pass


def shutdown_hub_tools():
    """Close Anika, tool windows, and hub-owned dialogs."""
    try:
        from desktop_tools.app.hub.tool_lifecycle import close_all_hub_tools

        close_all_hub_tools()
    except Exception as exc:
        log(f"Error closing hub tools: {exc}")
    try:
        close_hub_owned_windows()
    except Exception as exc:
        log(f"Error closing hub windows: {exc}")


def exit_application():
    """Fully exit the app after closing child tools."""
    shutdown_hub_tools()
    try:
        root.quit()
    except Exception as exc:
        log(f"Error exiting application: {exc}")

def show_window():
    """Show the main window."""
    root.deiconify()
    root.lift()
    root.focus_force()

def hide_window():
    """Hide the window to system tray and close child tools."""
    shutdown_hub_tools()
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
root.bind_all('<Control-Shift-V>', trigger_converter)
root.bind_all('<Control-Shift-B>', trigger_background_remover)
root.bind_all('<Control-Shift-Y>', trigger_screenshot_studio)
root.bind_all('<Control-Shift-R>', trigger_yscreenrecorder)
root.bind_all('<Control-Shift-A>', trigger_anika)

# Tray icon and screenshot hotkey start inside if __name__ == "__main__" (see below).

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
        if message == "Download list idle" and not is_direct_download_active():
            show_progress_section(None)
        else:
            show_progress_section("direct")
        direct_progress['value'] = percent
        if message:
            direct_progress_label.config(text=message)
            status_label.config(text=message)
    except Exception as e:
        log(f"Error updating direct progress: {str(e)}")

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
direct_download_manager = None
download_list_window = None
download_list_tree = None
download_list_details_var = None
download_list_resume_btn = None
download_list_pause_btn = None
download_list_cancel_btn = None
download_list_replace_btn = None
download_list_open_file_btn = None
download_list_open_folder_btn = None
download_list_delete_btn = None

initialize_direct_download_manager()
handle_direct_download_manager_change()

def cancel_download():
    """Cancel the current download."""
    global download_cancelled

    manager = initialize_direct_download_manager()
    active_record = get_active_direct_record()
    if active_record is not None and direct_download_state() in {"probing", "downloading", "paused"}:
        manager.cancel_record(active_record.id)
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

def download_media(is_audio, url=None):
    """Download media from the provided URL."""
    global ffmpeg_path, ffprobe_path, download_cancelled, ydl_instance
    download_cancelled = False  # Reset cancellation flag
    cancel_event.clear()
    ydl_instance = None  # Reset yt-dlp instance
    
    try:
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
                messagebox.showerror(
                    "FFmpeg Required",
                    "FFmpeg is required but could not be installed automatically.\n\n"
                    + get_ffmpeg_install_help(),
                )
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
        
        url = str(url or "").strip()
        if not url:
            url = url_entry.get().strip()
        if not url:
            show_url_validation_dialog_threadsafe("")
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
            show_url_validation_dialog_threadsafe(url)
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
                    schedule_url_preview_refresh()
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

        create_tray_icon()
        start_screenshot_hotkey_listener()
        
        # Show the window by default
        root.deiconify()
        center_window(root)
        root.lift()
        root.focus_force()
        
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)
    finally:
        shutdown_hub_tools()
        stop_screenshot_hotkey_listener()
        if tray_icon is not None:
            tray_icon.stop()
