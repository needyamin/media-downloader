# Media Downloader

A desktop application developed for educational and personal use, designed to help users explore how media handling tools work. It supports downloading high-quality videos and audio from public sources.

The main entry opens the Media Downloader window directly. Extra tools such as `Video Converter` and `BG Remover` are available from the downloader menu bar and reuse the same shared FFmpeg installation where needed.

## Application Preview
![Image](https://github.com/user-attachments/assets/9be2138d-cb43-425d-b8f9-a3c53309076f)

## Features

- Simple and intuitive user interface
- Download videos and audio in various formats with `yt-dlp`
- IDM-style direct file downloads for normal media/file URLs
- Pause and resume support for direct downloads when the server supports byte-range requests
- Automatic clipboard monitoring for media links
- Customizable download quality settings
- Support for downloading entire playlists with a max-files limit
- Desktop support (Windows and Linux AppImage builds)
- System tray integration for background operation
- Automatic app update checks
- Silent background app update flow for packaged Windows installs
- Shared FFmpeg auto-find, auto-download, auto-configure, and background auto-update
- One-click `Settings -> Install / Update FFmpeg`
- Integrated `Video Converter` and `BG Remover` tools
- YouTube extraction retries with detected JavaScript runtimes and browser-cookie fallback

## Installation

### Option 1: Download the Installer
1. Go to the [Releases](https://github.com/needyamin/media-downloader/releases) page
2. Download the latest `MediaDownloader_Setup.exe` 
3. Run the installer and follow the on-screen instructions

### Option 2: Build from Source
1. Clone this repository:
   ```
   git clone https://github.com/needyamin/media-downloader.git
   cd media-downloader
   ```

2. Make sure you have the required dependencies:
   ```
   pip install -r src/desktop_tools/app/requirements.txt
   ```

3. Run the application directly:
   ```
   python run.py
   ```

4. (Optional) Build release artifacts:
   - Windows `.exe` + installer:
     - Install [Inno Setup](https://jrsoftware.org/isdl.php)
     - Run:
       ```
       python "src\desktop_tools\app\nutika_build.py"
       ```
     - Find the outputs in `release/windows`
   - Linux AppImage:
     - Run on a Linux machine:
       ```
       python3 "src/desktop_tools/app/linux_appimage_build.py"
       ```
       or
       ```
       ./src/desktop_tools/app/build_linux_appimage.sh
       ```
     - Find the output in `release/linux`

## Usage

1. Launch the application
2. Paste a URL, then choose the correct download mode:
   - `Download Video` or `Download Audio` for streaming pages and supported sites
   - `Direct Download (IDM)` for direct file/media links such as `.mp4`, `.mp3`, `.zip`, installers, images, and other normal file URLs
3. Use `Download Entire Playlist` when you want the whole playlist, and set `Max Files` if you want to limit playlist items
4. For direct downloads, the pause/resume controls appear only while a direct download is active
5. The app shows only the active progress section for the current download mode, while `Download History` stays visible for logs and status messages
6. Downloads are organized inside the selected base folder:
   - `video/`
   - `audio/`
   - `playlists/`
   - `files/`
7. Open extra tools from the menu bar with `Tools -> Video Converter` or `Tools -> BG Remover`
8. FFmpeg starts automatically in the background when the downloader opens:
   - if FFmpeg is already available, the app reuses it
   - if FFmpeg is missing, the app downloads and configures it automatically
   - if a newer FFmpeg release is available later, the app can update it in the background
9. Use `Settings -> Install / Update FFmpeg` if you want to force a manual FFmpeg install/update
10. Both the downloader and converter share the same managed FFmpeg runtime
11. Packaged Windows installs can download and stage app updates automatically in the background; source builds and non-Windows environments fall back to the release page when silent installer mode is not available

## Runtime Flags

You can tune lightweight runtime behavior from the root `app_flags.json` file.

Most useful option:

- `debug_logging`: set to `false` to reduce verbose debug logging, console noise, and log-history overhead
- `disabled_domains`: add domains like `youtube.com` or `example.org` to block downloads from those sites even if `yt-dlp` supports them

Notes:

- FFmpeg activity logs are shown in the normal in-app log even when `debug_logging` is `false`
- Keep `debug_logging` enabled only when you want extra internal diagnostics beyond the visible FFmpeg status messages

## Windows Signing

To reduce Windows SmartScreen and "unknown publisher" warnings for this open-source project, the repo now includes an optional GitHub Actions workflow for [SignPath Foundation](https://signpath.org/).

Included files:

- `.github/workflows/windows-signpath.yml`
- `.signpath/artifact-configurations/windows-release.xml`

Recommended setup:

1. Apply for SignPath Foundation for this open-source repository.
2. In SignPath, create a project for this repo and add the artifact configuration from `.signpath/artifact-configurations/windows-release.xml`.
3. Add these GitHub repository settings:
   - Secret: `SIGNPATH_API_TOKEN`
   - Variable: `SIGNPATH_ORGANIZATION_ID`
   - Variable: `SIGNPATH_PROJECT_SLUG`
   - Optional variable: `SIGNPATH_SIGNING_POLICY_SLUG` (defaults to `release-signing`)
   - Optional variable: `SIGNPATH_ARTIFACT_CONFIGURATION_SLUG` (defaults to `windows-release`)
4. Trigger the workflow manually or publish a GitHub release.

Behavior:

- If SignPath is configured, the workflow builds and signs:
  - `Media-Downloader.exe`
  - `MediaDownloader_Setup.exe`
- If SignPath is not configured yet, the workflow still builds unsigned Windows artifacts so the pipeline remains usable.

## Project Structure

The project is now organized so more GUI tools can be added later without turning the root folder into one large script dump.

```text
media-downloader/
├── README.md
├── LICENSE
├── run.py
└── src/
    └── desktop_tools/
        ├── app/          # App implementation, assets, requirements, packaging
        └── shared/       # Shared helpers
```

Current extensibility points:

- Keep shared helpers in `src/desktop_tools/shared/`
- Put app-specific code and packaging files in `src/desktop_tools/app/`
- Reuse shared FFmpeg logic from `src/desktop_tools/shared/ffmpeg.py`

## Dependencies

- Python 3.6+
- yt-dlp
- Tkinter
- PIL (Pillow)
- PyPerClip
- PyStray
- Validators
- PyWin32 (Windows only)
- Requests
- CustomTkinter
- rembg
- onnxruntime
- Certifi
- FFmpeg (automatically found/downloaded/updated by the application)

## Legal Notice

This software is provided for educational and personal use only. Users are responsible for ensuring they comply with all applicable laws and terms of service when using this application.

❌ Do not use this software to access or download content in violation of any terms of service or applicable laws.

## Author

Created by [Md Yamin Hossain](https://github.com/needyamin)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
