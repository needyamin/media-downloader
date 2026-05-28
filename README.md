# Media Downloader

One desktop app for downloading, converting, background removal, screenshots, and screen recording.

<p align="center">
  <strong>Free · MIT licensed · No account · No ads · Offline-first</strong>
</p>

<p align="center">
  <a href="https://github.com/needyamin/media-downloader/releases"><strong>Download latest release</strong></a>
  &nbsp;|&nbsp;
  <a href="index.html">Landing page</a>
</p>

---

## Overview

Media Downloader combines 6 tools into one desktop workspace:

- Media download from supported public URLs (video/audio)
- Direct file download queue with resume/history
- Video conversion (FFmpeg-based)
- AI background removal
- Screenshot capture
- Screen recording

It is built for Windows and Linux, with one shared UI hub, tray actions, and keyboard shortcuts.

---

## Main Features

- One launcher window for all tools
- Shared managed FFmpeg workflow
- Direct-download queue with persistent history
- Local AI background remover (`rembg` + ONNX Runtime)
- Screenshot and recording overlays with quick controls
- Configurable behavior via `app_flags.json`

---

## Included Tools

| Tool | Purpose |
|---|---|
| Media Downloader | Download video/audio from supported public sources |
| Download List | Queue and manage direct file downloads |
| Video Converter | Convert/remux with quality and size controls |
| BG Remover | Remove image backgrounds and export PNG |
| YScreenshot | Capture selected or full screen image |
| YScreenRecorder | Record screen with pause/finish controls |

---

## Install

### Windows

1. Download `MediaDownloader_Setup.exe` from [Releases](https://github.com/needyamin/media-downloader/releases)
2. Run installer
3. Launch Media Downloader

### Linux

1. Download `Media-Downloader-x86_64.AppImage` from [Releases](https://github.com/needyamin/media-downloader/releases)
2. Make executable and run:

```bash
chmod +x Media-Downloader-x86_64.AppImage
./Media-Downloader-x86_64.AppImage
```

For best capture support on Linux, install:
`ffmpeg` `ffprobe` `python3-tk` `xclip` `wl-clipboard` `grim` `gnome-screenshot` `scrot` `imagemagick`

---

## Run from Source

```bash
git clone https://github.com/needyamin/media-downloader.git
cd media-downloader
pip install -r src/desktop_tools/app/requirements.txt
python run.py
```

---

## Keyboard Shortcuts (Windows)

| Shortcut | Action |
|---|---|
| `Ctrl+Shift+V` | Open Video Converter |
| `Ctrl+Shift+B` | Open BG Remover |
| `Ctrl+Shift+Y` | Open YScreenshot |
| `Ctrl+Shift+R` | Open YScreenRecorder |

While recording:
- `Ctrl+Shift+P` pause/resume
- `Ctrl+Shift+S` finish and save

---

## Build & Packaging

| Platform | Build command | Output |
|---|---|---|
| Windows | `python -m desktop_tools.app.build_tools.nuitka` | `release/windows/MediaDownloader_Setup.exe` |
| Linux | `python -m desktop_tools.app.build_tools.linux_appimage` | `release/linux/Media-Downloader-x86_64.AppImage` |

Bundle manifest check:

```bash
python -m desktop_tools.app.build_tools.manifest
```

WSL Linux build from Windows:

```powershell
wsl.exe -d Ubuntu -- sh -lc "cd /mnt/c/Users/<you>/Desktop/media-downloader && python3 -m desktop_tools.app.build_tools.linux_appimage"
```

---

## Configuration

Global runtime behavior is controlled from root `app_flags.json`.

Common keys:

- `debug_logging`
- `disabled_domains`
- `clipboard_poll_ms_*`
- `max_log_lines`
- `hotkeys.*`
- `versions.*`
- `paths.*`
- `themes.*`

---

## Project Structure

```text
media-downloader/
├── README.md
├── index.html
├── app_flags.json
├── run.py
└── src/desktop_tools/
    ├── app/        # UI modules, orchestration, build tool modules
    ├── shared/     # reusable services (ffmpeg, capture, downloads)
    ├── tools/      # stable entrypoints, smoke checks, architecture guards
    └── README.md   # desktop architecture notes
```

---

## Tech Stack

- Python 3.12+
- `yt-dlp`, Pillow, `pystray`, `customtkinter`
- `rembg`, `onnxruntime`
- Packaging: Nuitka + Inno Setup (Windows), PyInstaller + AppImage flow (Linux)

---

## Legal

Educational and personal use only.  
Users are responsible for compliance with copyright law, platform terms, and local regulations.

---

## Credits

- Author: [Md Yamin Hossain](https://github.com/needyamin)
- Packaging: [ANSNEW TECH](https://inside.ansnew.com)
- License: [MIT](LICENSE)
