# Media Downloader

A cross-platform desktop suite for **media downloads**, **direct file queueing**, and **built-in creative tools** — all from one main window. The app is intended for educational and personal use, helping you explore how media handling, capture, and conversion workflows work on your machine.

Open **Media Downloader** as the hub, then launch every other tool from the menu bar, tray, or global shortcuts.

## Application Preview

![Image](https://github.com/user-attachments/assets/9be2138d-cb43-425d-b8f9-a3c53309076f)

---

## Integrated Tools

| Tool | Category | What it does |
|------|----------|----------------|
| **Media Downloader** | Streaming & playlists | Download video/audio from supported sites with `yt-dlp`, quality presets, and playlist limits |
| **Download List** | Direct files (IDM-style) | Queue, pause, resume, replace broken links, and manage history for direct file URLs |
| **Video Converter** | Conversion | Batch-convert videos with shared FFmpeg (encode, remux, quality presets) |
| **BG Remover** | Image | Remove image backgrounds with AI (`rembg` + ONNX Runtime) |
| **YScreenshot** | Capture | Region or full-screen screenshots with overlay selection UI |
| **YScreenRecorder** | Capture | Region or full-screen screen recording with transparent HUD controls |

All tools share the same app packaging, tray integration, and (where applicable) the **managed FFmpeg** runtime.

---

## Special Categories

### 1. Streaming downloads (site URLs)

Use the main URL box with **Download Video** or **Download Audio** for pages and streams that `yt-dlp` understands (YouTube, and many other public sources).

- Custom video quality, audio bitrate, and output format
- Optional **Download Entire Playlist** with a **Max Files** cap
- Clipboard auto-fill for supported links
- Organized output folders: `video/`, `audio/`, `playlists/`
- YouTube retries with detected JS runtimes and browser-cookie fallback when needed

### 2. Direct downloads (file URLs) — Download List

Use **Download List** for true direct links (`.mp4`, `.mp3`, `.zip`, installers, images, archives, etc.) — similar to an IDM-style manager:

- Multiple items in a persistent queue and history
- **Pause**, **resume**, and **cancel** when the server supports byte ranges
- **Replace broken link** on failed items
- Open file/folder, delete items, clear finished downloads
- Resume metadata stored as `.part` sidecars

### 3. Conversion & processing

- **Video Converter** — FFmpeg-based queue with presets; uses the same auto-managed FFmpeg as the downloader
- **BG Remover** — Desktop studio UI for cutout preview and export

### 4. Capture studio (YScreenshot & YScreenRecorder)

| Feature | YScreenshot | YScreenRecorder |
|---------|-------------|-----------------|
| Region select | Yes | Yes |
| Full screen | Yes | Yes |
| Overlay UI | Dimmed screen + controls | Dimmed screen + fixed bottom-center control panel |
| While recording | — | Transparent HUD (pause, finish, open folder) |
| **Windows** | Full support | `ddagrab` / `gdigrab` via FFmpeg |
| **Linux X11** | ImageGrab + tool fallbacks | `x11grab` via system FFmpeg |
| **Linux Wayland** | Screenshot fallbacks (`grim`, etc.) | Recording not in-app yet (guidance shown) |

**Linux runtime packages** (not bundled; install on the host):  
`ffmpeg` `ffprobe` `python3-tk` `xclip` `wl-clipboard` `grim` `gnome-screenshot` `scrot` `imagemagick`

---

## Global shortcuts (Windows)

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+V` | Open **Video Converter** |
| `Ctrl+Shift+B` | Open **BG Remover** |
| `Ctrl+Shift+Y` | Open **YScreenshot** |
| `Ctrl+Shift+R` | Open **YScreenRecorder** |

Inside **YScreenRecorder** while recording:

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+P` | Pause / resume |
| `Ctrl+Shift+S` | Finish & save |

Tray menu duplicates the main tools and **Install / Update FFmpeg**.

---

## Platform builds

| Platform | Release artifact | Build script |
|----------|------------------|--------------|
| **Windows** | `release/windows/MediaDownloader_Setup.exe` (Inno Setup installer) | `src/desktop_tools/app/nutika_build.py` |
| **Linux** | `release/linux/Media-Downloader-x86_64.AppImage` | `src/desktop_tools/app/linux_appimage_build.py` |

Both platforms use **`build_manifest.py`** to auto-discover app modules (`*_app.py`), shared `desktop_tools` code, assets, and third-party package data so packaged builds stay in sync with the source tree.

Packaged builds bundle app assets, root `app_flags.json`, and runtime dependencies for the downloader, **Download List**, converter, BG remover, screenshot, and screen recorder.

### Windows build notes

- **Packaging mode:** Nuitka **standalone** (a `media_download.dist` folder), not onefile — avoids payload/AV locking issues on some setups.
- **Compile output:** `src/desktop_tools/app/build/nuitka/runs/<run-id>/windows-output/media_download.dist/Media-Downloader.exe`
- **Installer output:** `release/windows/MediaDownloader_Setup.exe` (requires [Inno Setup 6](https://jrsoftware.org/isdl.php))
- **Python:** 3.12 or **3.13** recommended for Nuitka on Windows. On **3.14+**, the script may relaunch with `py -3.13` when available, upgrade Nuitka, or fall back to **PyInstaller onedir** if Nuitka fails.
- **Prerequisites:** build tools for your Python version (MSVC, Clang, or MinGW64 — the script picks a backend), plus dependencies from `src/desktop_tools/app/requirements.txt`.
- Close any running **Media Downloader** build/output folders before rebuilding to avoid locked files.

Build trees under `src/desktop_tools/app/build/` and `release/` contain generated artifacts — do not commit installers or intermediate `.build` / `.dist` folders.

---

## Features (summary)

- Simple, resizable main UI with activity log and system tray
- **Download List** instead of a single direct-download button — full queue and history
- IDM-style direct file downloads with pause/resume when supported
- Automatic clipboard monitoring for media links
- Customizable download quality settings
- Playlist downloads with max-files limit
- Silent background app updates (packaged Windows installer flow)
- Shared FFmpeg: auto-find, auto-download, background update, **Settings → Install / Update FFmpeg**
- Optional domain blocklist via `app_flags.json`
- Styled in-app dialogs for URL validation and detailed errors (not only raw message boxes)

---

## Installation

### Option 1: Download the installer

1. Go to the [Releases](https://github.com/needyamin/media-downloader/releases) page
2. Download the latest `MediaDownloader_Setup.exe`
3. Run the installer and follow the on-screen instructions

**Linux:** download `Media-Downloader-x86_64.AppImage` from Releases, make it executable (`chmod +x`), and run it. Install the [capture runtime packages](#4-capture-studio-yscreenshot--yscreenrecorder) on your distro for full screenshot/recorder support.

### Option 2: Build from source

1. Clone this repository:

   ```bash
   git clone https://github.com/needyamin/media-downloader.git
   cd media-downloader
   ```

2. Install Python dependencies:

   ```bash
   pip install -r src/desktop_tools/app/requirements.txt
   ```

3. Run the application:

   ```bash
   python run.py
   ```

4. **(Optional) Build release artifacts**

   **Windows** (standalone app folder + Inno Setup installer):

   - Install [Inno Setup 6](https://jrsoftware.org/isdl.php)
   - On Windows, from the repo root:

     ```powershell
     python src\desktop_tools\app\nutika_build.py
     ```

   - **App bundle:** `src\desktop_tools\app\build\nuitka\runs\<run-id>\windows-output\media_download.dist\` (contains `Media-Downloader.exe`)
   - **Installer:** `release\windows\MediaDownloader_Setup.exe`

   **Linux** (AppImage, on Linux or WSL Ubuntu):

   ```bash
   python3 src/desktop_tools/app/linux_appimage_build.py
   ```

   or:

   ```bash
   ./src/desktop_tools/app/build_linux_appimage.sh
   ```

   The Linux build uses a dedicated virtualenv under `src/desktop_tools/app/build/linux-appimage-venv` to avoid PEP 668 system-Python restrictions.

   **WSL example** (replace your user/path):

   ```powershell
   wsl.exe -d Ubuntu -u root -- sh -lc "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip python3-venv python3-dev python3-tk build-essential patchelf file zsync libglib2.0-0 libnss3 libgtk-3-0 libx11-6 libxkbcommon0 libdbus-1-3 libasound2t64 libtbb12"
   wsl.exe -d Ubuntu -- sh -lc "cd /mnt/c/Users/<your-user>/Desktop/media-downloader && python3 src/desktop_tools/app/linux_appimage_build.py"
   ```

   Output: `release/linux/Media-Downloader-x86_64.AppImage`

---

## Usage

1. Launch the application (main **Media Downloader** window).
2. Paste a URL and choose the right action:
   - **Download Video** / **Download Audio** — streaming or site pages
   - **Download List** — open the queue, add direct file URLs, and manage history
3. Enable **Download Entire Playlist** when needed; set **Max Files** to cap playlist size.
4. Open tools from **Tools** in the menu bar (or use Windows global shortcuts above).
5. FFmpeg prepares automatically in the background; force update via **Settings → Install / Update FFmpeg**.
6. Downloads land under your chosen base folder: `video/`, `audio/`, `playlists/`, and direct files under the configured direct-download path.

---

## Runtime flags

Edit the root `app_flags.json` file:

| Key | Purpose |
|-----|---------|
| `debug_logging` | Set `false` to reduce verbose internal logging |
| `disabled_domains` | Block downloads from listed domains (e.g. `youtube.com`) even if `yt-dlp` supports them |
| `clipboard_poll_ms_*`, `max_log_lines`, etc. | Fine-tune UI polling and log size |

FFmpeg status messages still appear in the main log when `debug_logging` is `false`.

---

## Windows signing

To reduce SmartScreen / “unknown publisher” warnings, the repo includes an optional [SignPath Foundation](https://signpath.org/) workflow:

- `.github/workflows/windows-signpath.yml`
- `.signpath/artifact-configurations/windows-release.xml`

Configure `SIGNPATH_API_TOKEN`, `SIGNPATH_ORGANIZATION_ID`, and `SIGNPATH_PROJECT_SLUG` in GitHub, then run the workflow or publish a release. Unsigned artifacts are still produced if SignPath is not configured.

---

## Project structure

```text
media-downloader/
├── README.md
├── index.html                     # Project landing page (GitHub Pages / docs)
├── LICENSE
├── app_flags.json
├── run.py                         # Launch: python run.py
└── src/
    └── desktop_tools/
        ├── app/
        │   ├── media_download.py      # Main hub + Download List
        │   ├── converter_app.py
        │   ├── background_remover_app.py
        │   ├── screenshot_app.py      # YScreenshot
        │   ├── yscreenrecorder_app.py # YScreenRecorder
        │   ├── build_manifest.py      # Shared packaging manifest
        │   ├── nutika_build.py        # Windows Nuitka + Inno Setup
        │   ├── linux_appimage_build.py
        │   ├── installer/setup.iss    # Inno Setup script
        │   ├── requirements.txt
        │   └── assets/
        └── shared/
            ├── ffmpeg.py
            ├── direct_download.py
            ├── direct_download_manager.py
            ├── capture_support.py
            └── resources.py
```

---

## Dependencies

- **Python:** 3.12+ for development; **3.12–3.13** recommended for Windows Nuitka release builds (3.14+ may use PyInstaller fallback)
- **Core:** `yt-dlp`, Pillow, pyperclip, pystray, validators, requests, certifi
- **Tools:** customtkinter, rembg, onnxruntime, scipy, scikit-image, pymatting, pooch, jsonschema
- **Windows:** pywin32 (hotkeys, shell integration)
- **Build:** Nuitka (standalone) + Inno Setup 6 (Windows installer); PyInstaller + appimagetool (Linux AppImage). See `src/desktop_tools/app/build_manifest.py` for the canonical include list.
- **FFmpeg / ffprobe:** managed automatically on Windows; use system packages on Linux for converter and recorder

Install app dependencies:

```bash
pip install -r src/desktop_tools/app/requirements.txt
```

---

## Legal notice

This software is provided for **educational and personal use** only. You are responsible for complying with applicable laws and the terms of service of any site or content you access.

Do not use this software to download or redistribute content in violation of copyright, platform rules, or local law.

---

## Author

Created by [Md Yamin Hossain](https://github.com/needyamin)

Packaged builds credit: **ANSNEW TECH** — [inside.ansnew.com](https://inside.ansnew.com)

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
