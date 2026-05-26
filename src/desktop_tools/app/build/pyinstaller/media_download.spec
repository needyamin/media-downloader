# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


REPO_ROOT = Path(SPEC).resolve().parents[5]
APP_DIR = REPO_ROOT / "src" / "desktop_tools" / "app"
ICON_PATH = APP_DIR / "assets" / "needyamin.ico"
VERSION_INFO = APP_DIR / "file_version_info.txt"
APP_FLAGS = REPO_ROOT / "app_flags.json"
ENTRY_SCRIPT = APP_DIR / "media_download.py"

block_cipher = None

a = Analysis(
    [str(ENTRY_SCRIPT)],
    pathex=[str(REPO_ROOT), str(REPO_ROOT / "src")],
    binaries=[],
    datas=[
        (str(ICON_PATH), "."),
        (str(APP_FLAGS), "."),
    ],
    hiddenimports=[
        "desktop_tools",
        "desktop_tools.app",
        "desktop_tools.app.background_remover_app",
        "desktop_tools.shared",
        "desktop_tools.shared.resources",
        "PIL._tkinter_finder",
        "PIL._imagingtk",
        "PIL._imaging",
        "PIL._imagingft",
        "PIL._imagingmath",
        "PIL._imagingmorph",
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "yt_dlp",
        "yt_dlp.extractor",
        "yt_dlp.downloader",
        "yt_dlp.postprocessor",
        "yt_dlp.postprocessor.ffmpeg",
        "pyperclip",
        "pystray",
        "validators",
        "win32com",
        "win32com.client",
        "requests",
        "customtkinter",
        "rembg",
        "onnxruntime",
        "json",
        "certifi",
        "ssl",
        "shutil",
        "io",
        "winreg",
        "zipfile",
        "tempfile",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Media-Downloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_PATH),
    version=str(VERSION_INFO),
)
