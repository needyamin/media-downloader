# Media Downloader

A complete desktop app for your entire media workflow — download and queue files, convert media, remove backgrounds, capture screenshots, and record your screen, all in one place.

<p align="center">
  <strong>Free · MIT licensed · No account · No ads · Offline-first · v3.0.0</strong>
</p>

<p align="center">
  <a href="https://github.com/needyamin/media-downloader/releases"><strong>Download latest release</strong></a>
  &nbsp;|&nbsp;
  <a href="https://apps.microsoft.com/detail/9PHDQLBB8QCK">Microsoft Store</a>
  &nbsp;|&nbsp;
  <a href="privacy.html">Privacy</a>
</p>

---

## Screenshot
<img width="884" height="945" alt="Image" src="https://github.com/user-attachments/assets/ef7ce79b-e73b-40aa-b6b9-ae95c4788caa" />

## Overview

Media Downloader combines core media tools and a desktop assistant into one workspace:

- Media download from supported public URLs (video/audio)
- Direct file download queue with resume/history
- Video conversion (FFmpeg-based)
- AI background removal
- Screenshot capture
- Screen recording
- **Anika** — optional desktop assistant (break reminders, Today tasks, Workday timer)

It is built for Windows and Linux, with one shared UI hub, tray actions, and keyboard shortcuts.

---

## Main Features

- One launcher window for all tools
- **Download List** — IDM-style queue (add, pause, resume, replace broken links, history) with a compact icon toolbar
- Shared managed FFmpeg workflow (auto-install/update)
- Background remover: **classic `u2net` by default**; premium models (`BiRefNet`, `BRIA`) download only with your consent and show live progress
- Screenshot and recording overlays with quick controls
- **Anika** desktop assistant from **Tools → Anika** (separate process; no duplicate tray icon when launched from the hub)
- Packaged apps **auto-update** from GitHub Releases (Windows installer); releases ship **compiled binaries only** (no source zip)
- Microsoft Store package via MSIX (`MediaDownloader.msix`)
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
| Anika | Desktop assistant — break reminders, Today tasks, Workday timer |

### Anika (desktop assistant)

Open from **Tools → Anika** or **`Ctrl+Shift+A`**. Anika runs in a separate process. If she is already running, another click brings her window to the front.

Highlights:

- Break reminders (interval + how long she stays on screen)
- Drag to a **screen edge** to hide her for a configurable time (default 5 minutes)
- Right-click **Today** for the day's tasks (slots + optional AM/PM time)
- Right-click **Workday** for focus blocks and a timer that keeps running after you close the window
- Assistant size, opacity, language, personality, and visual effects
- Settings stored in `%LOCALAPPDATA%\Media Downloader\` (Anika: `anika\`, BG remover models: `rembg_models\`, ffmpeg, updates). Legacy folders `.yamos_witch_mate` and `.u2net` are migrated automatically and removed on uninstall.

---

## Install

### Windows

1. Download `MediaDownloader_Setup.exe` from [Releases](https://github.com/needyamin/media-downloader/releases), or install from the [Microsoft Store](https://apps.microsoft.com/detail/9PHDQLBB8QCK)
2. Run the installer (or open the Store listing)
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
| `Ctrl+Shift+A` | Open Anika |

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
python -m desktop_tools.tools.bg_remover_checks
python -m desktop_tools.tools.uninstall_cleanup_checks
```

Optional (import-boundary lint for contributors):

```bash
python -m desktop_tools.tools.architecture_guard
```

Bundle manifest:

```bash
python -m desktop_tools.app.build_tools.manifest
```

---

## Build & Packaging

| Platform | Output |
|---|---|
| Windows installer | `release/windows/MediaDownloader_Setup.exe` |
| Windows Store / sideload | `release/windows/MediaDownloader.msix` |
| Linux | `release/linux/Media-Downloader-x86_64.AppImage` |

Current app version is **3.0.0** (`versions.media_downloader` in `app_flags.json`).

### Windows (PyInstaller + Inno Setup)

Default path: **PyInstaller onedir** (fast compile) then Inno Setup. The installed app keeps DLLs and assets beside the exe, so it should not unpack or hang on every launch.

From the **repo root** in PowerShell:

```powershell
$env:PYTHONPATH = "src"
pip install -r src\desktop_tools\app\requirements.txt
python -m desktop_tools.app.build_tools.pyinstaller
```

That writes `release/windows/media_download.dist/` (`Media-Downloader.exe` + `_internal` + `Anika.exe`) and then `release/windows/MediaDownloader_Setup.exe`.

**Requirements**

- Windows only (the script exits on Linux/macOS)
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) installed (`ISCC.exe` on PATH or default install location)
- Python 3.12+ (3.12 or 3.13 recommended)

### Windows MSIX (Microsoft Store / sideload)

After a Windows exe build exists:

```powershell
$env:PYTHONPATH = "src"
python -m desktop_tools.app.build_tools.msix
```

Output: `release/windows/MediaDownloader.msix` plus `release/windows/store_listing.json`.

Store identity is set in the MSIX build:

- Name: `ANSNEWTECH.AnsNewTech.MediaDownloader4K`
- Publisher: `CN=087A9974-75CB-44FC-B893-8D3999E5E5E5`
- Store ID: `9PHDQLBB8QCK`
- Store URL: https://apps.microsoft.com/detail/9PHDQLBB8QCK

Upload `release/windows/MediaDownloader.msix` on the Packages tab if the submission accepts MSIX. If the listing type is **EXE or MSI**, upload `MediaDownloader_Setup.exe` instead. Host `privacy.html` so the privacy URL is live.

### Linux (AppImage)

```bash
export PYTHONPATH=src
pip install -r src/desktop_tools/app/requirements.txt
python -m desktop_tools.app.build_tools.linux_appimage
```

### GitHub releases (auto-update + protected binaries)

Pushing a version tag builds **compiled** Windows and Linux artifacts only — no Python source is attached to the release.

1. Tag and push: `git tag v3.0.0` then `git push origin v3.0.0`
2. GitHub Actions (`.github/workflows/release.yml`) runs PyInstaller + Inno Setup (Windows) and PyInstaller + AppImage (Linux), then publishes a GitHub Release with `MediaDownloader_Setup.exe`, `Media-Downloader-x86_64.AppImage`, and `SHA256SUMS.txt`.
3. Installed apps compare their bundled version (`app_flags.json`) to [releases/latest](https://github.com/needyamin/media-downloader/releases/latest) and silently install a newer `MediaDownloader_Setup.exe` when available (`updates.packaged_auto_update` in `app_flags.json`).

Manual CI run: **Actions → Release (PyInstaller + AppImage) → Run workflow** and enter a version like `3.0.0`.

If the hub exe already built and only Anika/Inno failed, re-run with `$env:MD_INSTALLER_ONLY='1'` or just run the same command again — it reuses the onedir dist when possible.

WSL Linux build from Windows:

```powershell
wsl.exe -d Ubuntu -- sh -lc "cd /mnt/c/Users/<you>/Desktop/media-downloader && python3 -m desktop_tools.app.build_tools.linux_appimage"
```

Packaged builds bundle `src/desktop_tools/anika/` (sprites, Python sources, settings GUI). Windows installers also build `Anika.exe` beside `Media-Downloader.exe` so Tools → Anika works in the frozen app.

---

## Configuration

Global runtime behavior is controlled from root `app_flags.json`.

Common keys:

- `debug_logging`
- `disabled_domains`
- `clipboard_poll_ms_*`
- `max_log_lines`
- `hotkeys.*` (including `anika`: `Ctrl+Shift+A`)
- `versions.*`
- `paths.*`
- `themes.*`
- `updates.packaged_auto_update`, `updates.github_repo`

Anika-specific settings (break timing, edge hide, assistant size, etc.) live under `%LOCALAPPDATA%\Media Downloader\anika\`, not in `app_flags.json`. Uninstalling via the Windows installer removes that folder, downloaded AI models, ffmpeg cache, and legacy `.u2net` / `.yamos_witch_mate` data (not your Downloads folder).

---

## Project Structure

```text
media-downloader/
├── README.md
├── privacy.html
├── app_flags.json
├── run.py
├── scripts/           # Local helper scripts (signing, blogger theme)
└── src/desktop_tools/
    ├── app/           # Hub UI, tool windows, build tools, services
    ├── anika/         # Desktop assistant (Anika process, assets, settings GUI)
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
- Anika: Tkinter + CustomTkinter desktop assistant
- Packaging: PyInstaller onedir + Inno Setup (Windows installer), MSIX (Microsoft Store), PyInstaller + AppImage (Linux)

---

## Legal

Educational and personal use only.  
Users are responsible for compliance with copyright law, platform terms, and local regulations.

See [privacy.html](privacy.html) for what the app stores on your PC.

---

## Credits

- Author: [Md Yamin Hossain](https://github.com/needyamin)
- Packaging: [ANSNEW TECH](https://inside.ansnew.com)
- License: [MIT](LICENSE)
