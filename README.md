# Media Downloader

One desktop app for downloading, converting, background removal, screenshots, screen recording, and the **Anika** desktop companion.

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

Media Downloader combines core media tools and a desktop mascot into one workspace:

- Media download from supported public URLs (video/audio)
- Direct file download queue with resume/history
- Video conversion (FFmpeg-based)
- AI background removal
- Screenshot capture
- Screen recording
- **Anika** — optional desktop companion (break reminders, spell book, timer, personality & effects)

It is built for Windows and Linux, with one shared UI hub, tray actions, and keyboard shortcuts.

---

## Main Features

- One launcher window for all tools
- Shared managed FFmpeg workflow
- Direct-download queue with persistent history
- Local AI background remover (`rembg` + ONNX Runtime)
- Screenshot and recording overlays with quick controls
- **Anika** launched from the hub (no extra system-tray icon when started from Media Downloader)
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
| Anika | Desktop companion — break reminders, to-do spell book, chaa timer, mascot settings |

### Anika (desktop companion)

Open from **Tools → Anika** or **`Ctrl+Shift+U`**. Anika runs in a separate process and opens her settings panel on first launch.

Highlights:

- Break reminders (interval + how long she stays on screen)
- Drag to a **screen edge** to hide her for a configurable time (default 5 minutes)
- Right-click menu and **Settings → Actions** for spell book, timer, force actions, and quit
- Mascot size, opacity, language, personality, and visual effects
- Settings stored in `%USERPROFILE%\.yamos_witch_mate\config.json` (Linux: `~/.yamos_witch_mate/config.json`)

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

Set `PYTHONPATH=src` when running modules directly (checks, builds):

```bash
# Windows PowerShell
$env:PYTHONPATH="src"

# Linux / macOS
export PYTHONPATH=src
```

---

## Keyboard Shortcuts (Windows)

| Shortcut | Action |
|---|---|
| `Ctrl+Shift+V` | Open Video Converter |
| `Ctrl+Shift+B` | Open BG Remover |
| `Ctrl+Shift+Y` | Open YScreenshot |
| `Ctrl+Shift+R` | Open YScreenRecorder |
| `Ctrl+Shift+U` | Open Anika |

While recording:

- `Ctrl+Shift+P` pause/resume
- `Ctrl+Shift+S` finish and save

Hotkeys are configurable under `hotkeys` in `app_flags.json`.

---

## Development Checks

With `PYTHONPATH=src`:

```bash
python -m desktop_tools.tools.smoke_checks
python -m desktop_tools.tools.script_checks
python -m desktop_tools.tools.anika_checks
python -m desktop_tools.tools.architecture_guard
```

Bundle manifest:

```bash
python -m desktop_tools.app.build_tools.manifest
```

---

## Build & Packaging

| Platform | Build command | Output |
|---|---|---|
| Windows | `python -m desktop_tools.app.build_tools.nuitka` | `release/windows/MediaDownloader_Setup.exe` |
| Linux | `python -m desktop_tools.app.build_tools.linux_appimage` | `release/linux/Media-Downloader-x86_64.AppImage` |

WSL Linux build from Windows:

```powershell
wsl.exe -d Ubuntu -- sh -lc "cd /mnt/c/Users/<you>/Desktop/media-downloader && python3 -m desktop_tools.app.build_tools.linux_appimage"
```

Packaged builds include `src/desktop_tools/anika/` (mascot assets and entry script).

---

## Configuration

Global runtime behavior is controlled from root `app_flags.json`.

Common keys:

- `debug_logging`
- `disabled_domains`
- `clipboard_poll_ms_*`
- `max_log_lines`
- `hotkeys.*` (including `anika`: `Ctrl+Shift+U`)
- `versions.*`
- `paths.*`
- `themes.*`

Anika-specific settings (break timing, edge hide, mascot size, etc.) live in the user config file under `.yamos_witch_mate/`, not in `app_flags.json`.

---

## Project Structure

```text
media-downloader/
├── README.md
├── index.html
├── app_flags.json
├── run.py
└── src/desktop_tools/
    ├── app/           # Hub UI, tool windows, build tools, services
    ├── anika/         # Desktop companion (pet process, assets, settings GUI)
    ├── shared/        # Reusable services (ffmpeg, capture, downloads)
    ├── tools/         # Entrypoints, smoke/script/anika checks, architecture guard
    └── README.md      # Desktop architecture notes
```

See [src/desktop_tools/README.md](src/desktop_tools/README.md) for launcher conventions and import boundaries.

---

## Tech Stack

- Python 3.12+
- `yt-dlp`, Pillow, `pystray`, `customtkinter`
- `rembg`, `onnxruntime`
- Anika: Tkinter + CustomTkinter desktop pet
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
