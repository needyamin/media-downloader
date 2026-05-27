"""Direct file download helpers with pause/resume support."""

from __future__ import annotations

from dataclasses import dataclass
import json
import mimetypes
from pathlib import Path
import re
import shutil
import threading
import time
from urllib.parse import unquote, urlparse

import requests


DOWNLOADABLE_EXTENSIONS = {
    ".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".wmv", ".flv",
    ".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz",
    ".pdf", ".epub", ".apk", ".exe", ".msi", ".dmg", ".iso",
}
DOWNLOADABLE_CONTENT_TYPES = {
    "application/octet-stream",
    "application/pdf",
    "application/zip",
    "application/x-zip-compressed",
    "application/x-rar-compressed",
    "application/x-7z-compressed",
}


class DirectDownloadError(Exception):
    """Raised when a direct file download cannot be started or resumed."""


@dataclass
class DirectDownloadProbe:
    final_url: str
    filename: str
    content_type: str
    total_size: int
    supports_resume: bool


def sanitize_filename(name: str) -> str:
    """Return a filesystem-safe filename."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(name).strip())
    cleaned = cleaned.rstrip(". ")
    return cleaned or "download.bin"


def parse_content_disposition_filename(content_disposition: str) -> str | None:
    """Extract a filename from a Content-Disposition header."""
    if not content_disposition:
        return None

    match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition, flags=re.I)
    if match:
        return unquote(match.group(1))

    match = re.search(r'filename="?([^";]+)"?', content_disposition, flags=re.I)
    if match:
        return match.group(1)

    return None


def infer_filename(url: str, headers: dict[str, str]) -> str:
    """Choose a filename using headers first, then the URL path."""
    header_name = parse_content_disposition_filename(headers.get("content-disposition", ""))
    if header_name:
        return sanitize_filename(header_name)

    parsed = urlparse(url)
    path_name = Path(unquote(parsed.path)).name
    if path_name:
        return sanitize_filename(path_name)

    content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
    extension = mimetypes.guess_extension(content_type) or ".bin"
    return sanitize_filename(f"download{extension}")


def looks_like_direct_file(url: str, headers: dict[str, str]) -> bool:
    """Best-effort check for whether a URL points at a file instead of a page."""
    content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
    content_disposition = headers.get("content-disposition", "").lower()
    suffix = Path(unquote(urlparse(url).path)).suffix.lower()

    if "attachment" in content_disposition or "filename=" in content_disposition:
        return True
    if suffix in DOWNLOADABLE_EXTENSIONS:
        return True
    if content_type.startswith(("audio/", "video/", "image/")):
        return True
    if content_type in DOWNLOADABLE_CONTENT_TYPES:
        return True
    if content_type.startswith(("application/vnd.", "application/x-")) and "html" not in content_type:
        return True

    return False


def unique_path(path: Path) -> Path:
    """Return a non-conflicting file path."""
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem} ({counter}){suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def probe_direct_download(url: str, timeout: int = 15) -> DirectDownloadProbe:
    """Inspect a URL and determine whether it looks like a direct file download."""
    session = requests.Session()
    response = None
    final_url = url

    try:
        try:
            response = session.head(url, allow_redirects=True, timeout=timeout)
            final_url = response.url or url
            headers = {k.lower(): v for k, v in response.headers.items()}
            if response.status_code >= 400 or not looks_like_direct_file(final_url, headers):
                response.close()
                response = None
        except requests.RequestException:
            response = None

        if response is None:
            response = session.get(url, allow_redirects=True, timeout=timeout, stream=True)
            final_url = response.url or url
            headers = {k.lower(): v for k, v in response.headers.items()}
        else:
            headers = {k.lower(): v for k, v in response.headers.items()}

        response.raise_for_status()

        if not looks_like_direct_file(final_url, headers):
            raise DirectDownloadError(
                "This URL looks like a webpage or streaming page, not a direct file. "
                "Use the site downloader for video pages, or use a direct media/file link here."
            )

        total_size = int(headers.get("content-length", "0") or 0)
        supports_resume = "bytes" in headers.get("accept-ranges", "").lower()
        filename = infer_filename(final_url, headers)
        content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()

        return DirectDownloadProbe(
            final_url=final_url,
            filename=filename,
            content_type=content_type,
            total_size=total_size,
            supports_resume=supports_resume,
        )
    except requests.RequestException as exc:
        raise DirectDownloadError(f"Network error probing direct link: {exc}") from exc
    finally:
        if response is not None:
            response.close()
        session.close()


class DirectDownloadTask:
    """Download a direct file with pause, resume, and cancel support."""

    def __init__(
        self,
        url: str,
        output_dir: Path,
        log_callback=None,
        progress_callback=None,
        state_callback=None,
        chunk_size: int = 256 * 1024,
        delete_partial_on_cancel: bool = False,
    ) -> None:
        self.url = str(url).strip()
        self.output_dir = Path(output_dir)
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.state_callback = state_callback
        self.chunk_size = chunk_size
        self.delete_partial_on_cancel = bool(delete_partial_on_cancel)

        self.thread: threading.Thread | None = None
        self.pause_requested = threading.Event()
        self.cancel_requested = threading.Event()
        self.lock = threading.Lock()

        self.state = "idle"
        self.probe: DirectDownloadProbe | None = None
        self.total_size = 0
        self.downloaded_bytes = 0
        self.final_path: Path | None = None
        self.part_path: Path | None = None
        self.meta_path: Path | None = None
        self.error_message = ""

    def _log(self, message: str) -> None:
        if self.log_callback:
            self.log_callback(message)

    def _set_state(self, state: str, payload=None) -> None:
        self.state = state
        if self.state_callback:
            self.state_callback(state, payload)

    def _report_progress(self, percent: float | None, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(percent, message)

    def is_busy(self) -> bool:
        return self.state in {"probing", "downloading", "paused"}

    def start(self) -> bool:
        with self.lock:
            if self.thread is not None and self.thread.is_alive():
                return False

            self.cancel_requested.clear()
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            return True

    def pause(self) -> None:
        if self.state == "downloading":
            self.pause_requested.set()
            self._log("Pause requested for direct download.")

    def resume(self) -> bool:
        if self.state != "paused":
            return False
        self.pause_requested.clear()
        self._log("Resuming direct download...")
        return self.start()

    def cancel(self) -> None:
        self.cancel_requested.set()
        self.pause_requested.clear()
        self._log("Cancellation requested for direct download.")

    def _load_resume_metadata(self) -> dict:
        if self.meta_path and self.meta_path.exists():
            try:
                return json.loads(self.meta_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _write_resume_metadata(self, metadata: dict) -> None:
        if self.meta_path is not None:
            self.meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    def _remove_resume_metadata(self) -> None:
        if self.meta_path and self.meta_path.exists():
            self.meta_path.unlink(missing_ok=True)

    def _prepare_paths(self, probe: DirectDownloadProbe) -> tuple[Path, Path, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        part_path = self.output_dir / f"{probe.filename}.part"
        meta_path = self.output_dir / f"{probe.filename}.part.json"

        if meta_path.exists():
            metadata = self._load_resume_metadata()
            final_name = metadata.get("final_name")
            if metadata.get("url") == self.url and final_name:
                final_path = self.output_dir / final_name
            else:
                final_path = unique_path(self.output_dir / probe.filename)
        else:
            final_path = unique_path(self.output_dir / probe.filename)

        return final_path, part_path, meta_path

    def _cleanup_cancelled_files(self) -> None:
        if self.part_path and self.part_path.exists():
            self.part_path.unlink(missing_ok=True)
        self._remove_resume_metadata()

    def _run(self) -> None:
        response = None
        try:
            self._set_state("probing")
            self._log("Inspecting direct link...")
            probe = probe_direct_download(self.url)
            self.probe = probe

            final_path, part_path, meta_path = self._prepare_paths(probe)
            self.final_path = final_path
            self.part_path = part_path
            self.meta_path = meta_path

            metadata = self._load_resume_metadata()
            resume_offset = part_path.stat().st_size if part_path.exists() else 0
            if metadata.get("url") != self.url:
                resume_offset = 0

            if resume_offset and not probe.supports_resume:
                self._log("Server does not support resume. Restarting from the beginning.")
                part_path.unlink(missing_ok=True)
                resume_offset = 0

            headers = {}
            if resume_offset:
                headers["Range"] = f"bytes={resume_offset}-"
                self._log(f"Resuming direct download from byte {resume_offset}.")
            else:
                self._log(f"Starting direct download: {probe.filename}")

            self._set_state("downloading")
            response = requests.get(probe.final_url, stream=True, timeout=30, headers=headers)

            if resume_offset and response.status_code != 206:
                self._log("Server ignored resume request. Restarting direct download from the beginning.")
                response.close()
                response = requests.get(probe.final_url, stream=True, timeout=30)
                response.raise_for_status()
                part_path.unlink(missing_ok=True)
                resume_offset = 0

            response.raise_for_status()

            server_size = int(response.headers.get("content-length", "0") or 0)
            total_size = resume_offset + server_size if server_size else probe.total_size
            self.total_size = total_size
            self.downloaded_bytes = resume_offset

            self._write_resume_metadata(
                {
                    "url": self.url,
                    "final_url": probe.final_url,
                    "final_name": final_path.name,
                    "filename": probe.filename,
                    "content_type": probe.content_type,
                    "total_size": total_size,
                    "supports_resume": probe.supports_resume,
                }
            )

            started_at = time.monotonic()
            last_report_at = 0.0
            last_report_bytes = resume_offset
            file_mode = "ab" if resume_offset else "wb"

            with open(part_path, file_mode) as output_file:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if self.cancel_requested.is_set():
                        if self.delete_partial_on_cancel:
                            self._cleanup_cancelled_files()
                        self._set_state("cancelled")
                        self._report_progress(0.0, "Direct download cancelled")
                        return

                    if self.pause_requested.is_set():
                        self._set_state("paused")
                        self._report_progress(
                            (self.downloaded_bytes / total_size) * 100 if total_size else None,
                            "Direct download paused",
                        )
                        return

                    if not chunk:
                        continue

                    output_file.write(chunk)
                    self.downloaded_bytes += len(chunk)

                    now = time.monotonic()
                    if now - last_report_at >= 0.35:
                        elapsed = max(now - started_at, 0.001)
                        average_speed = self.downloaded_bytes / elapsed
                        latest_speed = (self.downloaded_bytes - last_report_bytes) / max(now - max(last_report_at, started_at), 0.001)
                        speed = latest_speed if last_report_at else average_speed
                        percent = (self.downloaded_bytes / total_size) * 100 if total_size else None
                        if total_size:
                            message = (
                                f"Direct download: {percent:.1f}% | "
                                f"{self.downloaded_bytes / 1024 / 1024:.1f}/{total_size / 1024 / 1024:.1f} MB | "
                                f"{speed / 1024 / 1024:.2f} MB/s"
                            )
                        else:
                            message = (
                                f"Direct download: {self.downloaded_bytes / 1024 / 1024:.1f} MB | "
                                f"{speed / 1024 / 1024:.2f} MB/s"
                            )
                        self._report_progress(percent, message)
                        last_report_at = now
                        last_report_bytes = self.downloaded_bytes

            shutil.move(str(part_path), str(final_path))
            self._remove_resume_metadata()
            self._report_progress(100.0, f"Direct download complete: {final_path.name}")
            self._log(f"Direct file saved to: {final_path}")
            self._set_state("completed", final_path)
        except Exception as exc:
            self.error_message = str(exc)
            self._log(f"Direct download failed: {exc}")
            self._set_state("error", str(exc))
        finally:
            if response is not None:
                response.close()
