import sys
import subprocess
import os
import shutil

# Configs
APP_NAME = "Advanced YouTube Downloader"
VERSION = "1.0.0"
MAIN_SCRIPT = "media-download.py"
ICON_PATH = "needyamin.ico"
AUTHOR = "Yamin Hossain"
DESCRIPTION = "YouTube Video and Playlist Downloader with GUI"
DIST_DIR = "dist"
BUILD_DIR = "build"

REQUIRED_PACKAGES = [
    "nuitka",
    "tkinter",
    "yt_dlp",
    "pystray",
    "Pillow",
    "pyperclip",
    "validators",
    "requests",
    "pywin32",
    "certifi",
    "webbrowser",
    "win32com",
]

def clean_directories():
    print("Cleaning build directories...")
    for d in [DIST_DIR, BUILD_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"Removed {d}/")

def build_executable():
    print("Building executable with Nuitka...")
    nuitka_args = [
        sys.executable,
        "-m", "nuitka",
        "--mingw64",
        "--windows-company-name=" + AUTHOR,
        "--windows-product-name=" + APP_NAME,
        "--windows-file-version=" + VERSION,
        "--windows-product-version=" + VERSION,
        "--windows-file-description=" + DESCRIPTION,
        "--windows-icon-from-ico=" + ICON_PATH,
        "--disable-console",
        "--follow-imports",
        "--plugin-enable=tk-inter",
        "--include-package=yt_dlp",
        "--include-package=pystray",
        "--include-package=PIL",
        "--include-package=pyperclip",
        "--include-package=validators",
        "--include-package=requests",
        "--include-package=win32com",
        "--include-package=certifi",
        "--include-module=tkinter",
        "--include-module=tkinter.ttk",
        "--include-module=tkinter.messagebox",
        "--include-module=tkinter.filedialog",
        "--include-module=webbrowser",
        #"--include-data-dir=assets=assets",
        "--output-dir=" + DIST_DIR,
        "--verbose",
        "--standalone",
        "--onefile",
        "--jobs=4",
        "--lto=yes",
        MAIN_SCRIPT,
    ]

    try:
        print("Running Nuitka compilation...")
        result = subprocess.run(nuitka_args, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("Warnings/Errors:")
            print(result.stderr)
        print("Build completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error code {e.returncode}")
        print("Error output:")
        print(e.stdout)
        print(e.stderr)
        sys.exit(1)

def main():
    print("Starting build process...")
    clean_directories()
    build_executable()
    print("Build process finished.")

if __name__ == "__main__":
    main()
