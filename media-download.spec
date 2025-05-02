# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

block_cipher = None

# Get the path to the icon file
icon_path = Path('needyamin.ico')

a = Analysis(
    ['media-download.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('needyamin.ico', '.'),  # Include the icon file
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        'PIL._imagingtk',
        'PIL._imaging',
        'PIL._imagingft',
        'PIL._imagingmath',
        'PIL._imagingmorph',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'yt_dlp',
        'yt_dlp.extractor',
        'yt_dlp.downloader',
        'yt_dlp.postprocessor',
        'yt_dlp.postprocessor.ffmpeg',
        'pyperclip',
        'pystray',
        'validators',
        'win32com',
        'win32com.client',
        'requests',
        'json',
        'certifi',
        'ssl',
        'shutil',
        'io',
        'winreg',
        'zipfile',
        'tempfile',
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
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Media Downloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False for a windowed application
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='needyamin.ico',  # Set the application icon
    version='file_version_info.txt',  # Include version information
) 