"""Shared FFmpeg management for desktop tools."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import zipfile

import requests

from desktop_tools.shared.resources import get_user_data_dir


IS_WINDOWS = os.name == "nt"


FFMPEG_DOWNLOAD_URLS = [
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    "https://github.com/GyanD/codexffmpeg/releases/download/2023-10-08-git-10a3e7e0f8/ffmpeg-2023-10-08-git-10a3e7e0f8-essentials_build.zip",
]
FFMPEG_RELEASE_API_URL = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest"
FFMPEG_WINGET_PACKAGE = "Gyan.FFmpeg"
FFMPEG_DOWNLOAD_PAGE = "https://ffmpeg.org"


def get_ffmpeg_install_help() -> str:
    """User-facing install instructions when FFmpeg is missing."""
    if IS_WINDOWS:
        return (
            "Install FFmpeg if needed:\n\n"
            f"    Windows: winget install {FFMPEG_WINGET_PACKAGE}\n"
            f"    Or download from {FFMPEG_DOWNLOAD_PAGE} and add bin to PATH"
        )
    return (
        "Install FFmpeg if needed:\n\n"
        "    Linux: sudo apt install ffmpeg\n"
        f"    Or download from {FFMPEG_DOWNLOAD_PAGE} and add bin to PATH"
    )


def resolve_ffmpeg_pair(
    ffmpeg_path: str | Path,
    ffprobe_path: str | Path | None = None,
) -> tuple[Path, Path]:
    """Resolve ffmpeg + ffprobe from a file or folder the user selected."""
    path = Path(ffmpeg_path).expanduser()
    suffix = ".exe" if IS_WINDOWS else ""
    if path.is_dir():
        path = path / f"ffmpeg{suffix}"
    probe = Path(ffprobe_path).expanduser() if ffprobe_path else path.parent / f"ffprobe{suffix}"
    return path, probe


def get_custom_ffmpeg_paths() -> tuple[Path | None, Path | None]:
    """Return the user-selected FFmpeg override, if one is saved."""
    metadata = load_managed_ffmpeg_metadata()
    ffmpeg_value = str(metadata.get("custom_ffmpeg_path") or "").strip()
    if not ffmpeg_value:
        return None, None
    ffprobe_value = str(metadata.get("custom_ffprobe_path") or "").strip() or None
    return resolve_ffmpeg_pair(ffmpeg_value, ffprobe_value)


def set_custom_ffmpeg_paths(
    ffmpeg_path: str | Path,
    ffprobe_path: str | Path | None = None,
) -> tuple[str, str]:
    """Save and verify a custom FFmpeg location."""
    resolved_ffmpeg, resolved_ffprobe = resolve_ffmpeg_pair(ffmpeg_path, ffprobe_path)
    if not verify_ffmpeg_binaries(resolved_ffmpeg, resolved_ffprobe):
        raise ValueError(
            "That location does not contain working ffmpeg and ffprobe binaries.\n\n"
            + get_ffmpeg_install_help()
        )
    metadata = load_managed_ffmpeg_metadata()
    metadata["custom_ffmpeg_path"] = str(resolved_ffmpeg)
    metadata["custom_ffprobe_path"] = str(resolved_ffprobe)
    save_managed_ffmpeg_metadata(metadata)
    record_managed_ffmpeg_state(resolved_ffmpeg, resolved_ffprobe)
    return str(resolved_ffmpeg), str(resolved_ffprobe)


def clear_custom_ffmpeg_paths() -> None:
    """Remove the custom FFmpeg override and return to automatic detection."""
    metadata = load_managed_ffmpeg_metadata()
    metadata.pop("custom_ffmpeg_path", None)
    metadata.pop("custom_ffprobe_path", None)
    save_managed_ffmpeg_metadata(metadata)


def get_managed_ffmpeg_dir() -> Path:
    """Return the shared FFmpeg install directory used by desktop tools."""
    ffmpeg_dir = get_user_data_dir("Media Downloader") / "ffmpeg"
    ffmpeg_dir.mkdir(parents=True, exist_ok=True)
    return ffmpeg_dir


def get_managed_ffmpeg_paths() -> tuple[Path, Path]:
    """Return the managed FFmpeg and FFprobe executable paths."""
    ffmpeg_dir = get_managed_ffmpeg_dir()
    executable_suffix = ".exe" if IS_WINDOWS else ""
    return ffmpeg_dir / f"ffmpeg{executable_suffix}", ffmpeg_dir / f"ffprobe{executable_suffix}"


def get_managed_ffmpeg_metadata_path() -> Path:
    """Return the metadata file used to track FFmpeg install/update state."""
    return get_managed_ffmpeg_dir() / "ffmpeg_metadata.json"


def load_managed_ffmpeg_metadata() -> dict:
    """Load FFmpeg metadata from disk."""
    metadata_path = get_managed_ffmpeg_metadata_path()
    if not metadata_path.exists():
        return {}

    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_managed_ffmpeg_metadata(metadata: dict) -> None:
    """Persist FFmpeg metadata to disk."""
    metadata_path = get_managed_ffmpeg_metadata_path()
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def get_ffmpeg_version_line(ffmpeg_path: str | Path) -> str:
    """Read the first version line from an FFmpeg executable."""
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            [str(ffmpeg_path), "-version"],
            capture_output=True,
            text=True,
            creationflags=creationflags,
        )
        if result.returncode != 0:
            return ""
        return (result.stdout.splitlines() or [""])[0].strip()
    except Exception:
        return ""


def record_managed_ffmpeg_state(
    ffmpeg_path: str | Path,
    ffprobe_path: str | Path,
    release_tag: str | None = None,
) -> None:
    """Store the current FFmpeg install details for future update checks."""
    metadata = load_managed_ffmpeg_metadata()
    metadata.update(
        {
            "ffmpeg_path": str(ffmpeg_path),
            "ffprobe_path": str(ffprobe_path),
            "version_line": get_ffmpeg_version_line(ffmpeg_path),
            "updated_at": int(time.time()),
        }
    )
    if release_tag:
        metadata["release_tag"] = release_tag
    save_managed_ffmpeg_metadata(metadata)


def fetch_latest_ffmpeg_release_info(logger=None) -> dict | None:
    """Fetch the latest FFmpeg release metadata used for auto-updates."""
    try:
        if logger:
            logger("Checking latest FFmpeg release information...")
        response = requests.get(
            FFMPEG_RELEASE_API_URL,
            headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "media-downloader/ffmpeg-updater"},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        if logger:
            logger(f"Unable to fetch latest FFmpeg release info: {exc}")
        return None


def verify_ffmpeg_binaries(ffmpeg_path: str | Path, ffprobe_path: str | Path, logger=None) -> bool:
    """Verify that FFmpeg and FFprobe binaries exist and execute correctly."""
    try:
        ffmpeg_path = Path(ffmpeg_path)
        ffprobe_path = Path(ffprobe_path)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        if logger:
            logger(f"Testing FFmpeg at: {ffmpeg_path}")
        if not ffmpeg_path.exists() or not ffprobe_path.exists():
            return False

        ffmpeg_result = subprocess.run(
            [str(ffmpeg_path), "-version"],
            capture_output=True,
            text=True,
            creationflags=creationflags,
        )
        if ffmpeg_result.returncode != 0:
            return False

        if logger:
            logger(f"Testing FFprobe at: {ffprobe_path}")
        ffprobe_result = subprocess.run(
            [str(ffprobe_path), "-version"],
            capture_output=True,
            text=True,
            creationflags=creationflags,
        )
        return ffprobe_result.returncode == 0
    except Exception:
        return False


def find_existing_ffmpeg(extra_paths: list[Path] | None = None, logger=None) -> tuple[str | None, str | None]:
    """Look for a valid FFmpeg install in standard and optional locations."""
    custom_ffmpeg, custom_ffprobe = get_custom_ffmpeg_paths()
    if custom_ffmpeg is not None and custom_ffprobe is not None:
        if logger:
            logger(f"Checking custom FFmpeg path: {custom_ffmpeg}")
        if verify_ffmpeg_binaries(custom_ffmpeg, custom_ffprobe, logger=logger):
            if logger:
                logger(f"Using custom FFmpeg from: {custom_ffmpeg}")
            return str(custom_ffmpeg), str(custom_ffprobe)
        if logger:
            logger("Custom FFmpeg path is set but not working. Searching other locations...")

    managed_ffmpeg, managed_ffprobe = get_managed_ffmpeg_paths()
    potential_ffmpeg_paths = [managed_ffmpeg]
    executable_suffix = ".exe" if IS_WINDOWS else ""
    if logger:
        logger("Searching for an existing FFmpeg installation...")
    if extra_paths:
        potential_ffmpeg_paths.extend(extra_paths)

    ffmpeg_on_path = shutil.which("ffmpeg")
    if ffmpeg_on_path:
        potential_ffmpeg_paths.append(Path(ffmpeg_on_path))

    if IS_WINDOWS:
        potential_ffmpeg_paths.extend(
            [
                Path(os.environ.get("PROGRAMFILES", "")) / "ffmpeg" / "bin" / "ffmpeg.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "ffmpeg" / "bin" / "ffmpeg.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
            ]
        )
    else:
        potential_ffmpeg_paths.extend(
            [
                Path("/usr/bin/ffmpeg"),
                Path("/usr/local/bin/ffmpeg"),
            ]
        )

    for ffmpeg_path in potential_ffmpeg_paths:
        if not ffmpeg_path:
            continue
        ffmpeg_path = Path(ffmpeg_path)
        ffprobe_path = ffmpeg_path.parent / f"ffprobe{executable_suffix}"
        if logger:
            logger(f"Checking FFmpeg path: {ffmpeg_path}")
        if ffmpeg_path.exists() and verify_ffmpeg_binaries(ffmpeg_path, ffprobe_path, logger=logger):
            if logger:
                logger(f"Using FFmpeg from: {ffmpeg_path}")
            return str(ffmpeg_path), str(ffprobe_path)

    if logger:
        logger("No working FFmpeg installation was found.")
    return None, None


def _report_download_progress(callback, message, percent=None):
    """Call a progress callback that may accept (message) or (message, percent)."""
    if callback is None:
        return
    try:
        callback(message, percent)
    except TypeError:
        callback(message)


def download_managed_ffmpeg(logger=None, progress_callback=None, release_tag: str | None = None) -> tuple[str | None, str | None]:
    """Download FFmpeg into the shared managed install directory."""
    ffmpeg_dir = get_managed_ffmpeg_dir()
    ffmpeg_path, ffprobe_path = get_managed_ffmpeg_paths()

    if verify_ffmpeg_binaries(ffmpeg_path, ffprobe_path, logger=logger):
        if logger:
            logger("FFmpeg is already installed and verified.")
        record_managed_ffmpeg_state(ffmpeg_path, ffprobe_path, release_tag=release_tag)
        return str(ffmpeg_path), str(ffprobe_path)

    if not IS_WINDOWS:
        if logger:
            logger(
                "Automatic FFmpeg download is currently only bundled for Windows builds. "
                "Install both ffmpeg and ffprobe from your Linux package manager."
            )
        return None, None

    for download_url in FFMPEG_DOWNLOAD_URLS:
        try:
            if logger:
                logger(f"Downloading FFmpeg into: {ffmpeg_dir}")
                logger(f"Attempting to download FFmpeg from: {download_url}")
            _report_download_progress(progress_callback, "Starting FFmpeg download...", None)

            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            last_percent = -1
            last_unknown_report = 0
            block_size = 64 * 1024
            zip_path = ffmpeg_dir / "ffmpeg.zip"

            with open(zip_path, "wb") as zip_file:
                for data in response.iter_content(block_size):
                    downloaded += len(data)
                    zip_file.write(data)
                    if progress_callback and total_size:
                        percent = int(100 * downloaded / total_size)
                        if percent != last_percent:
                            last_percent = percent
                            _report_download_progress(
                                progress_callback,
                                f"Downloading FFmpeg... {percent}% ({downloaded}/{total_size} bytes)",
                                percent,
                            )
                    elif progress_callback and downloaded - last_unknown_report >= 2 * 1024 * 1024:
                        last_unknown_report = downloaded
                        _report_download_progress(
                            progress_callback,
                            f"Downloading FFmpeg... {downloaded} bytes",
                            None,
                        )

            if progress_callback:
                _report_download_progress(progress_callback, "Extracting FFmpeg files...", None)

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(ffmpeg_dir)

            ffmpeg_exe_paths = list(ffmpeg_dir.glob("**/ffmpeg.exe"))
            ffprobe_exe_paths = list(ffmpeg_dir.glob("**/ffprobe.exe"))
            if not ffmpeg_exe_paths or not ffprobe_exe_paths:
                continue

            shutil.copy2(str(ffmpeg_exe_paths[0]), str(ffmpeg_path))
            shutil.copy2(str(ffprobe_exe_paths[0]), str(ffprobe_path))

            try:
                zip_path.unlink(missing_ok=True)
            except TypeError:
                if zip_path.exists():
                    zip_path.unlink()

            for item in ffmpeg_dir.glob("*"):
                if item.is_dir() and item not in {ffmpeg_path.parent, ffprobe_path.parent}:
                    shutil.rmtree(item, ignore_errors=True)

            if verify_ffmpeg_binaries(ffmpeg_path, ffprobe_path, logger=logger):
                if logger:
                    logger("FFmpeg download and verification completed successfully.")
                record_managed_ffmpeg_state(ffmpeg_path, ffprobe_path, release_tag=release_tag)
                return str(ffmpeg_path), str(ffprobe_path)
        except Exception as exc:
            if logger:
                logger(f"Error downloading FFmpeg from {download_url}: {exc}")

    return None, None


def ensure_managed_ffmpeg(extra_paths: list[Path] | None = None, logger=None, progress_callback=None) -> tuple[str | None, str | None]:
    """Return working FFmpeg and FFprobe paths, downloading them if necessary."""
    ffmpeg_path, ffprobe_path = find_existing_ffmpeg(extra_paths=extra_paths, logger=logger)
    if ffmpeg_path and ffprobe_path:
        record_managed_ffmpeg_state(ffmpeg_path, ffprobe_path)
        return ffmpeg_path, ffprobe_path
    if logger:
        logger("FFmpeg not found.")
        logger(get_ffmpeg_install_help())
        if IS_WINDOWS:
            logger("Trying automatic download as a fallback...")
        else:
            logger("Automatic download is not available on this platform.")
    return download_managed_ffmpeg(logger=logger, progress_callback=progress_callback)


def update_managed_ffmpeg_if_needed(
    logger=None,
    progress_callback=None,
    force: bool = False,
    extra_paths: list[Path] | None = None,
) -> tuple[str | None, str | None, bool]:
    """Ensure FFmpeg exists and update it when a newer release appears or force is requested."""
    custom_ffmpeg, custom_ffprobe = get_custom_ffmpeg_paths()
    if custom_ffmpeg is not None and custom_ffprobe is not None and not force:
        if verify_ffmpeg_binaries(custom_ffmpeg, custom_ffprobe, logger=logger):
            if logger:
                logger(f"Using custom FFmpeg path: {custom_ffmpeg}")
            return str(custom_ffmpeg), str(custom_ffprobe), False

    ffmpeg_path, ffprobe_path = ensure_managed_ffmpeg(
        extra_paths=extra_paths,
        logger=logger,
        progress_callback=progress_callback,
    )
    if not ffmpeg_path or not ffprobe_path:
        return ffmpeg_path, ffprobe_path, False
    if custom_ffmpeg is not None:
        return ffmpeg_path, ffprobe_path, False
    if not IS_WINDOWS:
        return ffmpeg_path, ffprobe_path, False

    latest_release = fetch_latest_ffmpeg_release_info(logger=logger)
    if not latest_release:
        return ffmpeg_path, ffprobe_path, False

    latest_tag = str(latest_release.get("tag_name", "")).strip()
    if not latest_tag:
        return ffmpeg_path, ffprobe_path, False

    metadata = load_managed_ffmpeg_metadata()
    installed_tag = str(metadata.get("release_tag", "")).strip()

    if not installed_tag:
        if not force:
            # Avoid a forced re-download for existing installs; start tracking from now on.
            record_managed_ffmpeg_state(ffmpeg_path, ffprobe_path, release_tag=latest_tag)
            if logger:
                logger("Initialized FFmpeg release tracking for future background updates.")
            return ffmpeg_path, ffprobe_path, False
        if logger:
            logger("No tracked FFmpeg release found. Downloading the latest FFmpeg now...")

    if installed_tag == latest_tag and not force:
        if logger:
            logger("FFmpeg is already up to date.")
        return ffmpeg_path, ffprobe_path, False

    if logger:
        if force:
            logger(f"Force installing/updating FFmpeg to release {latest_tag}...")
        else:
            logger(f"Updating FFmpeg in background to release {latest_tag}...")

    updated_ffmpeg_path, updated_ffprobe_path = download_managed_ffmpeg(
        logger=logger,
        progress_callback=progress_callback,
        release_tag=latest_tag,
    )
    return updated_ffmpeg_path, updated_ffprobe_path, bool(updated_ffmpeg_path and updated_ffprobe_path)


def install_ffmpeg_with_winget(logger=None) -> tuple[str | None, str | None]:
    """Install FFmpeg with winget on Windows, then resolve the binaries."""
    if not IS_WINDOWS:
        raise RuntimeError(get_ffmpeg_install_help())

    winget = shutil.which("winget")
    if not winget:
        raise RuntimeError(
            "winget is not available on this PC.\n\n" + get_ffmpeg_install_help()
        )

    if logger:
        logger(f"Running: winget install {FFMPEG_WINGET_PACKAGE}")
    result = subprocess.run(
        [
            winget,
            "install",
            "--id",
            FFMPEG_WINGET_PACKAGE,
            "-e",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ],
        capture_output=True,
        text=True,
    )
    output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    if logger and output:
        logger(output[-800:])

    found_ffmpeg, found_ffprobe = find_existing_ffmpeg(logger=logger)
    if found_ffmpeg and found_ffprobe:
        return found_ffmpeg, found_ffprobe

    already_installed = "already installed" in output.lower()
    if result.returncode != 0 and not already_installed:
        raise RuntimeError(
            f"winget could not install FFmpeg (exit {result.returncode}).\n\n"
            + get_ffmpeg_install_help()
        )
    raise RuntimeError(
        "winget finished, but FFmpeg is not on PATH yet. Restart the app or choose the path manually.\n\n"
        + get_ffmpeg_install_help()
    )
