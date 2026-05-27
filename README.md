# Media Downloader

### **One desktop app for your entire media workflow — download, queue, convert, cut out backgrounds, screenshot, and record.**

Stop switching between a video downloader, a download manager, a converter, a background remover, and separate capture tools. **Media Downloader** puts six professional workflows behind one window — free, open source, and ready for **Windows** and **Linux**.

<p align="center">
  <strong>Free &nbsp;·&nbsp; MIT licensed &nbsp;·&nbsp; No account &nbsp;·&nbsp; No ads &nbsp;·&nbsp; Offline-first on your PC</strong>
</p>

<p align="center">
  <a href="https://github.com/needyamin/media-downloader/releases"><strong>⬇ Download latest release</strong></a>
  &nbsp;|&nbsp;
  <a href="index.html">Landing page</a>
</p>

---

## The main idea

| | |
|---|---|
| **What it is** | A single **media workstation** for your desktop |
| **What you get** | **6 integrated tools** launched from one hub, tray, or hotkeys |
| **Who it’s for** | Creators, students, power users, and anyone tired of tool sprawl |
| **Why it matters** | **Save time, disk clutter, and context switching** — paste a link, open a tool, get a file |

> **Marketing headline:** *Download it once. Do everything in one place.*

---

## See it in action

![Media Downloader — main window and integrated tools](https://github.com/user-attachments/assets/311e27ab-fda2-4234-98a8-d7fef466579e)

---

## Why choose Media Downloader?

Most people juggle separate apps for each task. Media Downloader is built around one promise:

**Everything you need for everyday media work lives in one install.**

| Instead of… | You use… |
|-------------|----------|
| A site downloader + a file download manager | **Streaming downloads** + **Download List** (IDM-style queue) |
| A standalone FFmpeg GUI | **Video Converter** (shared engine, presets, batch queue) |
| A web-based background remover | **BG Remover** (local AI, private on your machine) |
| Extra screenshot / recorder apps | **YScreenshot** + **YScreenRecorder** (region pick, HUD, hotkeys) |

**Differentiators that matter:**

- **One hub** — menu bar, system tray, and Windows global shortcuts open every tool instantly  
- **Smart downloads** — site URLs via `yt-dlp`; direct file links with pause, resume, and history  
- **FFmpeg handled for you** on Windows — auto-detect, download, and update from Settings  
- **Packaged for real users** — Windows installer and Linux AppImage, not “Python script only”  
- **Respects your machine** — optional domain blocklist, configurable logging, organized output folders  

---

## Six tools. One app.

| Tool | Your benefit |
|------|----------------|
| **Media Downloader** | Paste a link → pick quality → get video or audio from supported public sites and playlists |
| **Download List** | Queue direct files (`.mp4`, `.zip`, installers…) with pause, resume, and broken-link repair |
| **Video Converter** | Batch-convert formats and quality without hunting for FFmpeg paths |
| **BG Remover** | Remove image backgrounds with on-device AI — preview and export transparent PNG |
| **YScreenshot** | Region or full-screen capture with a clean overlay workflow |
| **YScreenRecorder** | Record your screen with a floating HUD — pause, finish, open output folder |

Open any tool from **Tools** in the menu, the **tray**, or **keyboard shortcuts** (Windows).

---

## Three pillars (how we talk about the product)

### 1. Download — streaming and files

- **Site & playlist URLs** — video/audio quality presets, playlist caps, clipboard auto-detect  
- **Direct file URLs** — persistent queue, history, `.part` resume sidecars  
- Output sorted into `video/`, `audio/`, `playlists/`, and your direct-download folder  

### 2. Create — convert and polish

- **Video Converter** — encode, remux, and batch jobs on one FFmpeg stack  
- **BG Remover** — cutout studio with AI (`rembg` + ONNX Runtime)  

### 3. Capture — screenshot and record

| | YScreenshot | YScreenRecorder |
|---|-------------|-----------------|
| Region / full screen | ✓ | ✓ |
| Overlay UI | Dimmed screen + controls | Bottom control bar + recording HUD |
| Windows | Full support | FFmpeg `ddagrab` / `gdigrab` |
| Linux X11 | Tool fallbacks + ImageGrab | `x11grab` via system FFmpeg |
| Linux Wayland | `grim`, etc. | Guidance in-app (recording not built-in yet) |

**Linux tip:** install host packages for best capture:  
`ffmpeg` `ffprobe` `python3-tk` `xclip` `wl-clipboard` `grim` `gnome-screenshot` `scrot` `imagemagick`

---

## Get started in 60 seconds

### Windows

1. [Download `MediaDownloader_Setup.exe`](https://github.com/needyamin/media-downloader/releases) from Releases  
2. Run the installer  
3. Launch **Media Downloader** — paste a URL or open **Download List** / **Tools**

### Linux

1. Download `Media-Downloader-x86_64.AppImage` from [Releases](https://github.com/needyamin/media-downloader/releases)  
2. `chmod +x Media-Downloader-x86_64.AppImage` and run it  
3. Install capture packages above if you use screenshot or recorder features  

### From source (developers)

```bash
git clone https://github.com/needyamin/media-downloader.git
cd media-downloader
pip install -r src/desktop_tools/app/requirements.txt
python run.py
```

---

## Windows shortcuts

| Shortcut | Opens |
|----------|--------|
| `Ctrl+Shift+V` | Video Converter |
| `Ctrl+Shift+B` | BG Remover |
| `Ctrl+Shift+Y` | YScreenshot |
| `Ctrl+Shift+R` | YScreenRecorder |

**While recording:** `Ctrl+Shift+P` pause/resume · `Ctrl+Shift+S` finish and save  

---

## Built for distribution

| Platform | What users download | How maintainers build |
|----------|---------------------|------------------------|
| **Windows** | `MediaDownloader_Setup.exe` | `python src/desktop_tools/app/nutika_build.py` (+ [Inno Setup 6](https://jrsoftware.org/isdl.php)) |
| **Linux** | `Media-Downloader-x86_64.AppImage` | `python3 src/desktop_tools/app/linux_appimage_build.py` (Linux or **WSL Ubuntu**) |

Packaging is driven by **`build_manifest.py`** so every release automatically includes app modules, shared code, assets, and required libraries.

**WSL build (Windows → Linux AppImage):**

```powershell
wsl.exe -d Ubuntu -- sh -lc "cd /mnt/c/Users/<you>/Desktop/media-downloader && python3 src/desktop_tools/app/linux_appimage_build.py"
```

Output: `release/linux/Media-Downloader-x86_64.AppImage`

---

## Configuration

Edit root **`app_flags.json`**:

| Key | Use |
|-----|-----|
| `debug_logging` | Quieter logs when `false` |
| `disabled_domains` | Block specific sites (e.g. parental or policy control) |
| `clipboard_poll_ms_*`, `max_log_lines` | Tune UI responsiveness and log size |

---

## For developers

<details>
<summary><strong>Project layout</strong></summary>

```text
media-downloader/
├── README.md · index.html · app_flags.json · run.py
└── src/desktop_tools/
    ├── app/          # Hub, tools, build scripts, assets
    └── shared/       # FFmpeg, direct download, capture helpers
```

</details>

<details>
<summary><strong>Tech stack</strong></summary>

- **Runtime:** Python 3.12+ · `yt-dlp` · Pillow · pystray · customtkinter · rembg · onnxruntime  
- **Windows:** pywin32 hotkeys · managed FFmpeg · Nuitka standalone + Inno installer  
- **Linux:** PyInstaller onedir + AppImage · system FFmpeg for converter/recorder  

</details>

<details>
<summary><strong>Windows code signing (optional)</strong></summary>

SignPath workflow: `.github/workflows/windows-signpath.yml` — set `SIGNPATH_API_TOKEN`, `SIGNPATH_ORGANIZATION_ID`, `SIGNPATH_PROJECT_SLUG` in GitHub.

</details>

---

## Legal

**Educational and personal use only.** You are responsible for complying with copyright, platform terms of service, and local law. Do not download or redistribute content you do not have rights to use.

---

## Credits & license

**Author:** [Md Yamin Hossain](https://github.com/needyamin)  
**Packaging:** [ANSNEW TECH](https://inside.ansnew.com)  
**License:** [MIT](LICENSE)
