"""CI helpers: sync version from git tags, checksums, and release metadata."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

try:
    from .build_manifest import (
        APP_FLAGS_PATH,
        REPO_ROOT,
        WINDOWS_RELEASE_DIR,
        LINUX_RELEASE_DIR,
    )
except ImportError:
    from build_manifest import (
        APP_FLAGS_PATH,
        REPO_ROOT,
        WINDOWS_RELEASE_DIR,
        LINUX_RELEASE_DIR,
    )


WINDOWS_INSTALLER_NAME = "MediaDownloader_Setup.exe"
LINUX_APPIMAGE_NAME = "Media-Downloader-x86_64.AppImage"
VERSION_TAG_PATTERN = re.compile(r"^v?(\d+\.\d+\.\d+)(?:[-+].*)?$", re.IGNORECASE)


def normalize_release_version(value: str) -> str:
    """Parse v2.0.1 or 2.0.1 into 2.0.1."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError("Release version is empty")
    match = VERSION_TAG_PATTERN.match(cleaned)
    if not match:
        raise ValueError(f"Invalid release version tag: {value!r} (expected vX.Y.Z)")
    return match.group(1)


def version_from_github_ref() -> str:
    """Read version from GITHUB_REF (refs/tags/v1.2.3) or MD_RELEASE_VERSION."""
    override = os.environ.get("MD_RELEASE_VERSION", "").strip()
    if override:
        return normalize_release_version(override)

    github_ref = os.environ.get("GITHUB_REF", "").strip()
    if github_ref.startswith("refs/tags/"):
        return normalize_release_version(github_ref.rsplit("/", 1)[-1])

    raise ValueError(
        "Could not determine release version. Set MD_RELEASE_VERSION or push a tag like v2.0.0."
    )


def read_current_version_from_flags(flags_path: Path = APP_FLAGS_PATH) -> str:
    """Read media_downloader version from app_flags.json."""
    if not flags_path.is_file():
        return "0.0.0"
    with flags_path.open("r", encoding="utf-8") as handle:
        flags = json.load(handle)
    return str(flags.get("versions", {}).get("media_downloader", "0.0.0"))


def sync_app_flags_version(version: str, flags_path: Path = APP_FLAGS_PATH) -> None:
    """Write the release version into app_flags.json before compiling."""
    version = normalize_release_version(version)
    flags: dict = {}
    if flags_path.is_file():
        with flags_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            flags = loaded

    versions = flags.setdefault("versions", {})
    if not isinstance(versions, dict):
        versions = {}
        flags["versions"] = versions
    versions["media_downloader"] = version

    updates = flags.setdefault("updates", {})
    if isinstance(updates, dict):
        updates.setdefault("packaged_auto_update", True)
        updates.setdefault("source_auto_pull", False)

    with flags_path.open("w", encoding="utf-8") as handle:
        json.dump(flags, handle, indent=2)
        handle.write("\n")
    print(f"Synced app version to {version} in {flags_path}")


def write_build_info(version: str, output_dir: Path) -> Path:
    """Emit build-info.json next to release artifacts for support and update checks."""
    version = normalize_release_version(version)
    output_dir.mkdir(parents=True, exist_ok=True)
    info_path = output_dir / "build-info.json"
    payload = {
        "app": "Media Downloader",
        "version": version,
        "repository": "needyamin/media-downloader",
        "windows_installer": WINDOWS_INSTALLER_NAME,
        "linux_appimage": LINUX_APPIMAGE_NAME,
        "update_url": "https://github.com/needyamin/media-downloader/releases/latest",
        "packaging": {
            "windows": "nuitka-standalone + inno-setup",
            "linux": "pyinstaller + appimage",
            "source_in_release": False,
        },
        "github_sha": os.environ.get("GITHUB_SHA", ""),
        "github_ref": os.environ.get("GITHUB_REF", ""),
    }
    info_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {info_path}")
    return info_path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums_file(
    artifact_paths: list[Path],
    output_path: Path,
) -> Path:
    """Write SHA256SUMS.txt for GitHub release assets."""
    lines: list[str] = []
    for path in artifact_paths:
        if not path.is_file():
            continue
        lines.append(f"{_sha256_file(path)}  {path.name}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote checksums: {output_path}")
    return output_path


def collect_release_artifacts() -> list[Path]:
    """Default release outputs from local/CI build directories."""
    candidates = [
        WINDOWS_RELEASE_DIR / WINDOWS_INSTALLER_NAME,
        LINUX_RELEASE_DIR / LINUX_APPIMAGE_NAME,
        WINDOWS_RELEASE_DIR / "build-info.json",
        LINUX_RELEASE_DIR / "build-info.json",
    ]
    return [path for path in candidates if path.is_file()]


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        raise SystemExit("Usage: release_ci.py <sync-version|write-build-info|write-checksums>")

    command = argv[0]
    if command == "sync-version":
        version = version_from_github_ref()
        sync_app_flags_version(version)
        os.environ["MD_RELEASE_VERSION"] = version
        return

    if command == "write-build-info":
        version = version_from_github_ref()
        write_build_info(version, WINDOWS_RELEASE_DIR)
        write_build_info(version, LINUX_RELEASE_DIR)
        return

    if command == "write-checksums":
        output = Path(argv[1]) if len(argv) > 1 else REPO_ROOT / "release" / "SHA256SUMS.txt"
        artifacts = collect_release_artifacts()
        if not artifacts:
            raise SystemExit("No release artifacts found to checksum")
        write_checksums_file(artifacts, output)
        return

    raise SystemExit(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
