import tkinter as tk
from tkinter import ttk, messagebox, BooleanVar
import os
import yt_dlp
import threading
import webbrowser
import pyperclip
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageTk, ImageSequence, ImageDraw
import sys
import ctypes
import re
from pathlib import Path
from urllib.parse import urlparse
import validators
import yt_dlp.postprocessor.ffmpeg
import queue
import shutil
import win32com.client  # Requires: pip install pywin32
import requests
import json
import zipfile
import tempfile
import subprocess
import time
import ssl
import certifi
import io
import winreg

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
APP_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = Path(APP_DIR) / "needyamin.ico"

# Set app ID for Windows taskbar
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('needyamin.video_downloader')

# Installation directory (using AppData by default for better compatibility)
INSTALL_DIR = Path(os.environ["LOCALAPPDATA"]) / "Media Downloader"
INSTALL_DIR.mkdir(parents=True, exist_ok=True)

# Output directories
downloads_path = Path(os.environ["USERPROFILE"]) / "Downloads" / "Yamin Downloader"
video_output_dir = downloads_path / "video"
audio_output_dir = downloads_path / "audio"
playlist_output_dir = downloads_path / "playlists"
video_output_dir.mkdir(parents=True, exist_ok=True)
audio_output_dir.mkdir(parents=True, exist_ok=True)
playlist_output_dir.mkdir(parents=True, exist_ok=True)

# Auto-update configuration
REPO_OWNER = "needyamin"
REPO_NAME = "video-audio-downloader"
CURRENT_VERSION = "1.0.13"  # Updated to match latest release
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
UPDATE_CHECK_FILE = Path(os.environ["LOCALAPPDATA"]) / "Media Downloader" / "last_update_check.txt"

# Global variables
ffmpeg_path = None
early_log_queue = queue.Queue()
loading_gif = None
loading_label = None
quality_settings = {
    'video_quality': 'best',  # best, 1080p, 720p, 480p, 360p
    'audio_quality': '192',   # 320, 256, 192, 128, 96
    'format': 'mp4'          # mp4, webm, mkv
}

def verify_ffmpeg(ffmpeg_path, ffprobe_path):
    """Verify that FFmpeg and FFprobe are working."""
    try:
        if not ffmpeg_path or not ffprobe_path:
            return False
            
        # Check FFmpeg
        result = subprocess.run([ffmpeg_path, '-version'], 
                              capture_output=True, 
                              text=True,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode != 0:
            return False
            
        # Check FFprobe
        result = subprocess.run([ffprobe_path, '-version'], 
                              capture_output=True, 
                              text=True,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode != 0:
            return False
            
        return True
    except Exception as e:
        log(f"Error verifying FFmpeg: {str(e)}")
        return False

def download_ffmpeg():
    """Download and install FFmpeg."""
    message_label = None
    try:
        # Create FFmpeg directory in AppData
        ffmpeg_dir = Path(os.environ["LOCALAPPDATA"]) / "Media Downloader" / "ffmpeg"
        ffmpeg_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if FFmpeg is already installed and working
        ffmpeg_path = ffmpeg_dir / "ffmpeg.exe"
        ffprobe_path = ffmpeg_dir / "ffprobe.exe"
        
        if ffmpeg_path.exists() and ffprobe_path.exists():
            if verify_ffmpeg(str(ffmpeg_path), str(ffprobe_path)):
                log("FFmpeg is already installed and working")
                return str(ffmpeg_path)
        
        # Show loading animation
        message_label = show_loading("Downloading FFmpeg...")
        
        # Download FFmpeg from GitHub
        log("Starting FFmpeg download...")
        response = requests.get("https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip", stream=True)
        response.raise_for_status()
        
        # Get total file size
        total_size = int(response.headers.get('content-length', 0))
        block_size = 1024  # 1 Kibibyte
        downloaded = 0
        
        # Save the zip file with progress
        zip_path = ffmpeg_dir / "ffmpeg.zip"
        with open(zip_path, 'wb') as f:
            for data in response.iter_content(block_size):
                downloaded += len(data)
                f.write(data)
                # Update progress
                if total_size:
                    percent = int(100 * downloaded / total_size)
                    message = f"Downloading FFmpeg... {percent}% ({downloaded}/{total_size} bytes)"
                    log(message)
                    if message_label:
                        message_label.config(text=message)
        
        log("FFmpeg download completed. Extracting files...")
        if message_label:
            message_label.config(text="Extracting FFmpeg files...")
        
        # Extract the zip file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(ffmpeg_dir)
        
        # Find the bin directory
        bin_dir = next(ffmpeg_dir.glob("**/bin"), None)
        if not bin_dir:
            raise Exception("Could not find FFmpeg bin directory")
        
        log("Moving FFmpeg files to correct location...")
        if message_label:
            message_label.config(text="Installing FFmpeg...")
        
        # Move FFmpeg and FFprobe to the main directory
        shutil.move(str(bin_dir / "ffmpeg.exe"), str(ffmpeg_path))
        shutil.move(str(bin_dir / "ffprobe.exe"), str(ffprobe_path))
        
        # Clean up
        zip_path.unlink()
        for item in ffmpeg_dir.glob("*"):
            if item.is_dir() and item.name != "bin":
                shutil.rmtree(item)
        
        log("Verifying FFmpeg installation...")
        if message_label:
            message_label.config(text="Verifying installation...")
        
        # Verify installation
        if verify_ffmpeg(str(ffmpeg_path), str(ffprobe_path)):
            log("FFmpeg installation successful")
            return str(ffmpeg_path)
        else:
            raise Exception("FFmpeg verification failed after installation")
            
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
    def progress_hook(d):
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
                    
                    update_progress(percent, message)
                    log(message)
            except Exception as e:
                log(f"Progress error: {str(e)}")
        
        elif d['status'] == 'finished':
            update_progress(100, "Download complete! Processing...")
            log("Download complete! Processing video...")
        
        elif d['status'] == 'error':
            update_progress(0, "Error occurred during download")
            log(f"Download error: {d.get('error', 'Unknown error')}")
    
    return progress_hook

def is_auto_start_enabled():
    """Check if the application is set to start with Windows"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, "Video Downloader")
            return True
        except WindowsError:
            return False
        finally:
            key.Close()
    except Exception as e:
        print(f"Error checking auto-start: {e}")
        return False

def toggle_auto_start():
    """Toggle auto-start with Windows"""
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
            except WindowsError:
                pass
        key.Close()
    except Exception as e:
        print(f"Error toggling auto-start: {e}")

def debug_update_check():
    """Debug function to check update system status"""
    try:
        log("\n=== DEBUG: Update System Status ===")
        
        # Check repository configuration
        log(f"\nRepository Configuration:")
        log(f"Owner: {REPO_OWNER}")
        log(f"Name: {REPO_NAME}")
        log(f"API URL: {GITHUB_API_URL}")
        log(f"Current Version: {CURRENT_VERSION}")
        
        # Check update check file
        log(f"\nUpdate Check File Status:")
        if UPDATE_CHECK_FILE.exists():
            with open(UPDATE_CHECK_FILE, 'r') as f:
                last_check = float(f.read().strip())
                time_since_last_check = time.time() - last_check
                log(f"Last check: {time.ctime(last_check)}")
                log(f"Time since last check: {time_since_last_check/3600:.2f} hours")
        else:
            log("Update check file not found")
        
        # Test GitHub API connection
        log(f"\nTesting GitHub API Connection:")
        try:
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'Yamin-Video-Downloader'
            }
            response = requests.get(GITHUB_API_URL, headers=headers)
            log(f"API Response Status: {response.status_code}")
            
            if response.status_code == 200:
                latest_release = response.json()
                latest_version = latest_release.get('tag_name', '').lstrip('v')
                log(f"Latest Release: {latest_version}")
                log(f"Release Details: {json.dumps(latest_release, indent=2)}")
            else:
                log(f"API Error: {response.text}")
        except Exception as e:
            log(f"API Connection Error: {str(e)}")
        
        # Test version comparison
        log(f"\nTesting Version Comparison:")
        test_versions = [
            ("1.0.0", "1.0.12"),
            ("1.0.12", "1.0.12"),
            ("1.0.13", "1.0.12"),
            ("2.0.0", "1.0.12")
        ]
        for v1, v2 in test_versions:
            result = compare_versions(v1, v2)
            log(f"Compare {v1} > {v2}: {result}")
        
        log("\n=== DEBUG COMPLETED ===\n")
        
    except Exception as e:
        log(f"Debug Error: {str(e)}")

# Create main window
root = tk.Tk()
root.title("Media Downloader")
root.geometry("800x700")
root.minsize(600, 500)  # Set minimum window size
root.configure(bg=THEME['bg'])

# Quality settings variables
video_quality_var = tk.StringVar(value='best')
audio_quality_var = tk.StringVar(value='192')
format_var = tk.StringVar(value='mp4')

# Create auto-start variable
auto_start_var = tk.BooleanVar(value=is_auto_start_enabled())

def update_quality_settings(quality_type, value):
    """Update quality settings and log the change."""
    global quality_settings
    if quality_type in quality_settings:
        quality_settings[quality_type] = value
        log(f"Updated {quality_type} to: {value}")
        # Update status label to show current settings
        if 'status_label' in globals():
            status_label.config(text=f"Quality settings updated: {quality_type}={value}")

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

def threaded_download(is_audio):
    """Start download in a separate thread."""
    def download_thread():
        try:
            disable_buttons()
            download_media(is_audio)
        finally:
            enable_buttons()
    
    # Start the download in a new thread
    thread = threading.Thread(target=download_thread, daemon=True)
    thread.start()

def enable_buttons():
    """Enable the download buttons."""
    try:
        if 'video_btn' in globals():
            video_btn.config(state='normal')
        if 'audio_btn' in globals():
            audio_btn.config(state='normal')
    except:
        pass

def disable_buttons():
    """Disable the download buttons."""
    try:
        if 'video_btn' in globals():
            video_btn.config(state='disabled')
        if 'audio_btn' in globals():
            audio_btn.config(state='disabled')
    except:
        pass

def should_check_for_updates():
    """Determine if we should check for updates (once per day)."""
    try:
        log("Checking if update check is needed...")
        if not UPDATE_CHECK_FILE.exists():
            log("Update check file not found, will check for updates")
            return True
        
        # Read last check time
        with open(UPDATE_CHECK_FILE, 'r') as f:
            last_check = float(f.read().strip())
        
        time_since_last_check = time.time() - last_check
        log(f"Time since last check: {time_since_last_check/3600:.2f} hours")
        
        # Check if 24 hours have passed
        should_check = time_since_last_check >= 86400  # 24 hours in seconds
        log(f"Should check for updates: {should_check}")
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

def compare_versions(v1, v2):
    """Compare two version strings and return True if v1 > v2."""
    def parse_version(v):
        # Remove any non-numeric and non-dot characters
        v = ''.join(c for c in v if c.isdigit() or c == '.')
        # Split into parts and convert to integers
        parts = []
        for part in v.split('.'):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(0)
        return parts
    
    v1_parts = parse_version(v1)
    v2_parts = parse_version(v2)
    
    # Pad with zeros to make lengths equal
    max_len = max(len(v1_parts), len(v2_parts))
    v1_parts.extend([0] * (max_len - len(v1_parts)))
    v2_parts.extend([0] * (max_len - len(v2_parts)))
    
    log(f"Comparing versions: {v1_parts} > {v2_parts}")
    return v1_parts > v2_parts

def check_updates_on_startup():
    """Check for updates when the application starts"""
    try:
        log("\n=== Update Check Process Started ===")
        
        # Check for application updates
        if should_check_for_updates():
            log("Starting application update check...")
            latest_version = check_for_updates()
            if latest_version:
                log(f"New version {latest_version} available!")
                if messagebox.askyesno("Update Available", 
                                      f"Version {latest_version} is available. Would you like to update now?"):
                    log("User chose to update")
                    download_and_install_update(latest_version)
                else:
                    log("User chose not to update")
            else:
                log("No updates available")
            update_check_timestamp()
        else:
            log("Skipping update check (checked recently)")
            
        # Check for FFmpeg updates
        log("Starting FFmpeg update check...")
        check_ffmpeg_update()
        
        log("=== Update Check Process Completed ===\n")
    except Exception as e:
        log(f"Error in update check process: {str(e)}")

def check_for_updates():
    """Check for updates on GitHub and return the latest version if available."""
    try:
        log("=== Starting Update Check ===")
        log(f"GitHub API URL: {GITHUB_API_URL}")
        
        # Make the request with headers to avoid rate limiting
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Yamin-Video-Downloader'
        }
        response = requests.get(GITHUB_API_URL, headers=headers)
        log(f"GitHub API Response Status: {response.status_code}")
        
        if response.status_code != 200:
            log(f"GitHub API Error: {response.text}")
            return None
            
        latest_release = response.json()
        log(f"GitHub API Response: {json.dumps(latest_release, indent=2)}")
        
        # Get the latest version number
        latest_version = latest_release.get('tag_name', '').lstrip('v')
        log(f"Latest version on GitHub: {latest_version}")
        log(f"Current version: {CURRENT_VERSION}")
        
        if not latest_version:
            log("No version tag found in release")
            return None
            
        # Compare versions
        if compare_versions(latest_version, CURRENT_VERSION):
            log(f"New version {latest_version} is available!")
            return latest_version
        else:
            log("You have the latest version")
            return None
    except requests.exceptions.RequestException as e:
        log(f"Network error checking for updates: {e}")
        return None
    except Exception as e:
        log(f"Unexpected error checking for updates: {e}")
        return None

def download_and_install_update(release):
    """Download and install the latest release."""
    try:
        # Find the asset with .exe extension
        exe_asset = next((asset for asset in release['assets'] if asset['name'].endswith('.exe')), None)
        if not exe_asset:
            raise Exception("No executable found in release assets")
        
        # Create temporary directory for download
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            exe_path = temp_path / exe_asset['name']
            
            # Download the new version
            log("Downloading update...")
            response = requests.get(exe_asset['browser_download_url'], stream=True)
            response.raise_for_status()
            
            with open(exe_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Create update script
            update_script = temp_path / "update.bat"
            current_exe = sys.executable
            with open(update_script, 'w') as f:
                f.write(f"""@echo off
timeout /t 2 /nobreak
del "{current_exe}"
move "{exe_path}" "{current_exe}"
start "" "{current_exe}"
""")
            
            # Run update script and exit
            subprocess.Popen([str(update_script)], shell=True)
            sys.exit(0)
            
    except Exception as e:
        log("Error installing update: {e}")
        messagebox.showerror("Update Error", f"Failed to install update: {e}")

def check_ffmpeg_update():
    """Check for FFmpeg updates."""
    try:
        # Get the current FFmpeg version
        ffmpeg_dir = Path(os.environ["LOCALAPPDATA"]) / "Media Downloader" / "ffmpeg"
        ffmpeg_path = ffmpeg_dir / "ffmpeg.exe"
        
        if not ffmpeg_path.exists():
            return
            
        result = subprocess.run([str(ffmpeg_path), '-version'], 
                              capture_output=True, 
                              text=True,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode != 0:
            return
            
        # Check GitHub for latest FFmpeg version
        log("Checking for FFmpeg updates...")
        response = requests.get("https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest")
        response.raise_for_status()
        latest_release = response.json()
        
        # If there's a new version, download it
        if latest_release.get('tag_name'):
            log("New FFmpeg version available. Starting download...")
            # The download_ffmpeg function will handle its own loading animation
            download_ffmpeg()
            
    except Exception as e:
        log(f"Error checking FFmpeg updates: {str(e)}")

# Create menubar
menubar = tk.Menu(root)
root.config(menu=menubar)

# File Menu
file_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Open Download Folder", command=lambda: os.startfile(str(downloads_path)))
file_menu.add_checkbutton(label="Auto-start", variable=auto_start_var, command=toggle_auto_start)
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

# Help Menu
help_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Help", menu=help_menu)
help_menu.add_command(label="About", command=lambda: messagebox.showinfo("About", 
    "Media Downloader v" + CURRENT_VERSION + "\n\n" +
    "Created by Md Yamin Hossain\n" +
    "GitHub: https://github.com/needyamin\n\n" +
    "A powerful media downloader supporting multiple platforms."))
help_menu.add_command(label="Check for Updates", command=check_updates_on_startup)
help_menu.add_separator()
help_menu.add_command(label="Report Issue", 
    command=lambda: webbrowser.open("https://github.com/needyamin/Video-Downloader/issues"))

# Add debug command to Help menu
help_menu.add_separator()
help_menu.add_command(label="Debug Update System", command=debug_update_check)

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
        self.bind('<FocusIn>', self.on_focus_in)
        self.bind('<FocusOut>', self.on_focus_out)
        
    def on_focus_in(self, e):
        self.configure(bg='white')
        
    def on_focus_out(self, e):
        self.configure(bg=THEME['light_gray'])

class ModernCheckbutton(tk.Checkbutton):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(
            bg=THEME['bg'],
            fg=THEME['fg'],
            activebackground=THEME['bg'],
            activeforeground=THEME['primary'],
            selectcolor=THEME['light_gray'],
            font=('Segoe UI', 10)
        )

# Create a queue for thread-safe UI updates
ui_queue = queue.Queue()

def log(message, show_console=True):
    """Log a message to the output box and status label if available, or queue it for later."""
    try:
        if show_console:
            print(f"[Yamin Downloader] {message}")  # Always show in console
        if 'output_box' in globals() and 'status_label' in globals():
            output_box.config(state='normal')
            # Insert at the beginning (index 1.0) instead of the end
            output_box.insert('1.0', message + '\n')
            # Auto-scroll to the top
            output_box.see('1.0')
            output_box.config(state='disabled')
            status_label.config(text=message)
        else:
            early_log_queue.put(message)
    except:
        print(f"[Yamin Downloader] {message}")  # Fallback to console output

def process_early_logs():
    """Process any queued log messages once the GUI is ready."""
    while not early_log_queue.empty():
        try:
            message = early_log_queue.get_nowait()
            if 'output_box' in globals() and 'status_label' in globals():
                output_box.config(state='normal')
                # Insert at the beginning (index 1.0) instead of the end
                output_box.insert('1.0', message + '\n')
                # Auto-scroll to the top
                output_box.see('1.0')
                output_box.config(state='disabled')
                status_label.config(text=message)
        except queue.Empty:
            break

# Set window icon
if ICON_PATH.exists():
    try:
        root.iconbitmap(str(ICON_PATH))
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
main_frame.grid_rowconfigure(3, weight=1)
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

# Initialize FFmpeg in a separate thread
def initialize_ffmpeg():
    """Initialize FFmpeg and FFprobe."""
    global ffmpeg_path, ffprobe_path
    try:
        # Try to download FFmpeg if not already installed
        if not ffmpeg_path or not verify_ffmpeg(ffmpeg_path, str(Path(ffmpeg_path).parent / "ffprobe.exe")):
            ffmpeg_path = download_ffmpeg()
            if not ffmpeg_path:
                raise Exception("Failed to download FFmpeg")
        
        ffprobe_path = str(Path(ffmpeg_path).parent / "ffprobe.exe")
        
        # Configure yt-dlp to use both FFmpeg and FFprobe
        yt_dlp.postprocessor.ffmpeg.FFmpegPostProcessor.EXES = {
            'ffmpeg': ffmpeg_path,
            'ffprobe': ffprobe_path,
        }
        
        # Verify installation
        if not verify_ffmpeg(ffmpeg_path, ffprobe_path):
            raise Exception("FFmpeg verification failed after initialization")
        
        # Update status
        log("Initialization complete. Ready to download!")
        status_label.config(text="Ready to download")
    except Exception as e:
        log(f"Error initializing FFmpeg: {str(e)}")
        status_label.config(text="Error: FFmpeg initialization failed")

# Start FFmpeg initialization in a separate thread
threading.Thread(target=initialize_ffmpeg, daemon=True).start()

last_copied_url = ""
tray_icon = None
tray_thread = None

# Options Frame
options_frame = tk.Frame(main_frame, bg=THEME['bg'])
options_frame.grid(row=1, column=0, sticky="ew", pady=(0, 20))
options_frame.grid_columnconfigure(0, weight=1)

# Left Options
left_options = tk.Frame(options_frame, bg=THEME['bg'])
left_options.grid(row=0, column=0, sticky="w")

download_playlist = BooleanVar()
playlist_check = ModernCheckbutton(
    left_options,
    text="Download Entire Playlist",
    variable=download_playlist,
    command=lambda: max_files_entry.configure(state='normal' if download_playlist.get() else 'disabled')
)
playlist_check.grid(row=0, column=0, padx=(0, 20))

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
max_files_entry.insert(0, "100")
max_files_entry.configure(state='disabled')
max_files_entry.grid(row=0, column=1)

# Buttons Frame
buttons_frame = tk.Frame(main_frame, bg=THEME['bg'])
buttons_frame.grid(row=2, column=0, sticky="ew", pady=(0, 20))
buttons_frame.grid_columnconfigure(0, weight=1)
buttons_frame.grid_columnconfigure(1, weight=1)

video_btn = tk.Button(
    buttons_frame,
    text="Download Video",
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
video_btn.grid(row=0, column=0, padx=(0, 10), sticky="ew")

audio_btn = tk.Button(
    buttons_frame,
    text="Download Audio",
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
audio_btn.grid(row=0, column=1, sticky="ew")

# Progress Section
progress_frame = tk.Frame(main_frame, bg=THEME['bg'])
progress_frame.grid(row=3, column=0, sticky="ew", pady=(0, 20))
progress_frame.grid_columnconfigure(0, weight=1)

progress_label = tk.Label(
    progress_frame,
    text="Ready to download",
    font=('Segoe UI', 10),
    bg=THEME['bg'],
    fg=THEME['fg']
)
progress_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

progress = ttk.Progressbar(
    progress_frame,
    style="Modern.Horizontal.TProgressbar",
    orient="horizontal",
    length=500,
    mode="determinate"
)
progress.grid(row=1, column=0, sticky="ew")

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
    height=10,
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
def create_tray_icon():
    global tray_icon, tray_thread
    try:
        if ICON_PATH.exists():
            icon_image = Image.open(ICON_PATH)
        else:
            # Create a simple icon if the file doesn't exist
            icon_image = Image.new('RGB', (64, 64), THEME['primary'])
        
        menu = (
            item('Show', lambda: show_window()),
            item('Exit', lambda: root.quit())
        )
        
        tray_icon = pystray.Icon(
            "media_downloader",
            icon_image,
            "Media Downloader",
            menu
        )
        
        # Run the tray icon in a separate thread
        tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
        tray_thread.start()
    except Exception as e:
        log(f"Error creating tray icon: {e}")

def show_window():
    root.deiconify()
    root.lift()
    root.focus_force()

def hide_window():
    root.withdraw()

def on_minimize(event):
    hide_window()
    if tray_icon is None:
        create_tray_icon()

def on_close():
    hide_window()
    if tray_icon is None:
        create_tray_icon()

# Bind minimize and close events
root.protocol('WM_DELETE_WINDOW', on_close)
root.bind('<Unmap>', on_minimize)  # Handle minimize button click

# Start tray icon
create_tray_icon()

# Update progress function to show percentage in status
def update_progress(percent, message=None):
    progress['value'] = percent
    if message:
        progress_label.config(text=message)
        status_label.config(text=message)
        log(message)

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
    root.after(100, process_queue)

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

def download_media(is_audio):
    """Download media from the provided URL."""
    global ffmpeg_path, ffprobe_path
    try:
        show_loading()  # Show loading animation
        
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
            return

        # Log current quality settings
        log(f"Current quality settings:")
        log(f"- Video Quality: {current_video_quality}")
        log(f"- Audio Quality: {current_audio_quality}kbps")
        log(f"- Format: {current_format}")

        # Verify FFmpeg and FFprobe exist and are working
        if not verify_ffmpeg(ffmpeg_path, ffprobe_path):
            log("FFmpeg not found or not working, attempting to download...")
            ffmpeg_path = download_ffmpeg()
            ffprobe_path = str(Path(ffmpeg_path).parent / "ffprobe.exe")
            
            if not verify_ffmpeg(ffmpeg_path, ffprobe_path):
                messagebox.showerror("Error", 
                    "FFmpeg is required for audio extraction. Failed to download or verify FFmpeg.\n"
                    "Please try again or download FFmpeg manually from: https://ffmpeg.org/download.html")
                hide_loading()
                return

        is_playlist = download_playlist.get()
        max_files = max_files_entry.get() or '100'
        
        try:
            max_files = int(max_files)
        except ValueError:
            max_files = 100

        output_path = audio_output_dir if is_audio else video_output_dir

        # Configure format and quality settings
        if is_audio:
            format_code = 'bestaudio/best'
            log(f"Downloading audio with settings:")
            log(f"- Format: {format_code}")
            log(f"- Quality: {current_audio_quality}kbps")
        else:
            if current_video_quality == 'best':
                format_code = 'bestvideo+bestaudio/best'
            else:
                format_code = f'bestvideo[height<={current_video_quality}]+bestaudio/best'
            log(f"Downloading video with settings:")
            log(f"- Format: {format_code}")
            log(f"- Quality: {current_video_quality}")
            log(f"- Output Format: {current_format}")

        ydl_opts = {
            'format': format_code,
            'progress_hooks': [create_progress_hook()],
            'restrictfilenames': True,
            'windowsfilenames': True,
            'quiet': False,  # Set to False to see more output
            'no_warnings': False,
            'nocheckcertificate': False,
            'nooverwrites': True,
            'continuedl': True,
            'ffmpeg_location': ffmpeg_path,
            'merge_output_format': current_format,
            'verbose': True,  # Add verbose output
            'outtmpl': str(output_path / ('playlists/%(playlist_title)s/%(playlist_index)s_%(title)s.%(ext)s' 
                          if is_playlist else '%(title)s.%(ext)s')),
            'ssl_verify': True,
            'source_address': None,
            'socket_timeout': 30,
            'retries': 10,
            'extractor_retries': 10,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            },
            'postprocessors': [{
                'key': 'FFmpegVideoRemuxer',
                'preferedformat': current_format
            }]
        }

        # Configure postprocessor based on download type and quality settings
        if is_audio:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': current_audio_quality,
            }]
        else:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegVideoRemuxer',
                'preferedformat': current_format
            }]
            # Add audio quality postprocessor for videos
            ydl_opts['postprocessors'].append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': current_audio_quality
            })
        
        # Add FFmpeg location and merge format
        ydl_opts['ffmpeg_location'] = ffmpeg_path
        ydl_opts['merge_output_format'] = current_format

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                
                if is_playlist and 'entries' in info:
                    log(f"? Downloading playlist: {info.get('title', 'Untitled')}")
                    log(f"?? Number of items: {len(info['entries'])}")
                    log(f"?? Downloading first {max_files} items")
                
                log(f"? Starting download: {url}")
                log(f"? Using quality settings: Video={current_video_quality}, Audio={current_audio_quality}kbps, Format={current_format}")
                ydl.download([url])
                
                if is_playlist:
                    log(f"? Playlist download completed!")
                    log(f"?? Saved to: {output_path}/playlists/")
                    # Open the playlist folder
                    playlist_folder = output_path / "playlists" / info.get('title', 'Untitled')
                    if playlist_folder.exists():
                        os.startfile(str(playlist_folder))
                else:
                    log("? Download completed!")
                    log(f"?? Saved to: {output_path}")
                    # Open the output folder
                    os.startfile(str(output_path))

            except yt_dlp.utils.DownloadError as e:
                if "ffmpeg" in str(e).lower():
                    messagebox.showerror("Error", 
                        "FFmpeg is required for audio extraction. Please install FFmpeg and try again.\n"
                        "You can download FFmpeg from: https://ffmpeg.org/download.html")
                elif "certificate" in str(e).lower():
                    messagebox.showerror("Error", 
                        "SSL certificate verification failed. Please try the following:\n"
                        "1. Update your Python installation\n"
                        "2. Run: pip install --upgrade certifi\n"
                        "3. Run: pip install --upgrade yt-dlp")
                else:
                    messagebox.showerror("Error", f"Download failed: {str(e)}")
                log(f"Error: {str(e)}")
            except Exception as e:
                messagebox.showerror("Error", f"An unexpected error occurred: {str(e)}")
                log(f"Error: {str(e)}")

    except Exception as e:
        messagebox.showerror("Error", f"Error occurred:\n{e}")
    finally:
        hide_loading()  # Hide loading animation
        ui_queue.put(lambda: enable_buttons())
        ui_queue.put(lambda: update_progress(0, "Ready to download"))

# Clipboard Monitoring Functions
def is_supported_url(url):
    try:
        return validators.url(url)
    except:
        return False

def check_clipboard():
    global last_copied_url
    try:
        clipboard_content = pyperclip.paste().strip()
        if validators.url(clipboard_content):
            if clipboard_content != last_copied_url and is_supported_url(clipboard_content):
                url_entry.delete(0, tk.END)
                url_entry.insert(0, clipboard_content)
                last_copied_url = clipboard_content
                log(f"Auto-detected URL: {clipboard_content}")
    except Exception as e:
        print("Clipboard error:", e)
    root.after(1000, check_clipboard)

# Start clipboard monitoring
check_clipboard()

# Start queue processing
root.after(100, process_queue)

# Main loop
if __name__ == "__main__":
    try:
        # Check for updates on startup
        check_updates_on_startup()
        
        # Show the window by default
        root.deiconify()
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
        if tray_icon is not None:
            tray_icon.stop()

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
