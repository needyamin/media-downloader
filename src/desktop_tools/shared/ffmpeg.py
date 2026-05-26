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
    managed_ffmpeg, managed_ffprobe = get_managed_ffmpeg_paths()
    potential_ffmpeg_paths = [managed_ffmpeg]
    if logger:
        logger("Searching for an existing FFmpeg installation...")
    if extra_paths:
        potential_ffmpeg_paths.extend(extra_paths)
    if IS_WINDOWS:
        potential_ffmpeg_paths.extend(
            [
                Path(os.environ.get("PROGRAMFILES", "")) / "ffmpeg" / "bin" / "ffmpeg.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "ffmpeg" / "bin" / "ffmpeg.exe",
            ]
        )
    else:
        ffmpeg_on_path = shutil.which("ffmpeg")
        if ffmpeg_on_path:
            potential_ffmpeg_paths.append(Path(ffmpeg_on_path))
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
        ffprobe_path = ffmpeg_path.parent / "ffprobe.exe"
        if logger:
            logger(f"Checking FFmpeg path: {ffmpeg_path}")
        if ffmpeg_path.exists() and verify_ffmpeg_binaries(ffmpeg_path, ffprobe_path, logger=logger):
            if logger:
                logger(f"Using FFmpeg from: {ffmpeg_path}")
            return str(ffmpeg_path), str(ffprobe_path)

    if logger:
        logger("No working FFmpeg installation was found.")
    return None, None


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
            logger("Automatic FFmpeg download is currently only bundled for Windows builds. Install ffmpeg from your Linux package manager.")
        return None, None

    for download_url in FFMPEG_DOWNLOAD_URLS:
        try:
            if logger:
                logger(f"Downloading FFmpeg into: {ffmpeg_dir}")
                logger(f"Attempting to download FFmpeg from: {download_url}")

            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            block_size = 1024
            zip_path = ffmpeg_dir / "ffmpeg.zip"

            with open(zip_path, "wb") as zip_file:
                for data in response.iter_content(block_size):
                    downloaded += len(data)
                    zip_file.write(data)
                    if progress_callback and total_size:
                        percent = int(100 * downloaded / total_size)
                        progress_callback(
                            f"Downloading FFmpeg... {percent}% ({downloaded}/{total_size} bytes)"
                        )

            if progress_callback:
                progress_callback("Extracting FFmpeg files...")

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
        logger("FFmpeg not found. Starting automatic download...")
    return download_managed_ffmpeg(logger=logger, progress_callback=progress_callback)


def update_managed_ffmpeg_if_needed(
    logger=None,
    progress_callback=None,
    force: bool = False,
    extra_paths: list[Path] | None = None,
) -> tuple[str | None, str | None, bool]:
    """Ensure FFmpeg exists and update it when a newer release appears or force is requested."""
    ffmpeg_path, ffprobe_path = ensure_managed_ffmpeg(
        extra_paths=extra_paths,
        logger=logger,
        progress_callback=progress_callback,
    )
    if not ffmpeg_path or not ffprobe_path:
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
