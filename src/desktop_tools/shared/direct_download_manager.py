"""Persistent manager for IDM-style direct download list handling."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import threading
import time
from typing import Callable
from uuid import uuid4

from desktop_tools.shared.direct_download import DirectDownloadTask


@dataclass
class DirectDownloadRecord:
    id: str
    url: str
    added_at: float
    updated_at: float
    state: str = "queued"
    final_url: str = ""
    filename: str = ""
    final_name: str = ""
    content_type: str = ""
    total_size: int = 0
    downloaded_bytes: int = 0
    supports_resume: bool = False
    error_message: str = ""
    completed_at: float = 0.0
    final_path: str = ""
    part_path: str = ""
    meta_path: str = ""
    last_message: str = ""

    @property
    def progress_percent(self) -> float:
        if self.total_size > 0:
            return max(0.0, min(100.0, (self.downloaded_bytes / self.total_size) * 100.0))
        return 0.0


class DirectDownloadManager:
    """Manage persisted direct-download queue/history with one active task at a time."""

    def __init__(
        self,
        output_dir: Path,
        storage_path: Path,
        log_callback: Callable[[str], None] | None = None,
        can_start_downloads: Callable[[], bool] | None = None,
        on_change: Callable[[], None] | None = None,
        on_active_progress: Callable[[DirectDownloadRecord | None], None] | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.storage_path = Path(storage_path)
        self.log_callback = log_callback
        self.can_start_downloads = can_start_downloads or (lambda: True)
        self.on_change = on_change
        self.on_active_progress = on_active_progress
        self.lock = threading.RLock()
        self.records: list[DirectDownloadRecord] = []
        self.active_record_id: str | None = None
        self.active_task: DirectDownloadTask | None = None
        self._load()
        self._import_resume_sidecars()
        self._normalize_stale_records()

    def _log(self, message: str) -> None:
        if self.log_callback:
            self.log_callback(message)

    def _emit_change(self) -> None:
        if self.on_change:
            self.on_change()

    def _emit_active_progress(self, record: DirectDownloadRecord | None) -> None:
        if self.on_active_progress:
            self.on_active_progress(record)

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(record) for record in self.records]
        self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except Exception:
            payload = []
        if not isinstance(payload, list):
            return
        records: list[DirectDownloadRecord] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                records.append(DirectDownloadRecord(**item))
            except TypeError:
                continue
        self.records = records

    def _normalize_stale_records(self) -> None:
        changed = False
        for record in self.records:
            if record.state in {"probing", "downloading"}:
                record.state = "paused"
                record.last_message = "Recovered unfinished download from a previous session."
                record.updated_at = time.time()
                changed = True
        if changed:
            self._save()

    def _import_resume_sidecars(self) -> None:
        known_meta_paths = {record.meta_path for record in self.records if record.meta_path}
        changed = False
        for meta_path in self.output_dir.glob("*.part.json"):
            resolved_meta = str(meta_path.resolve())
            if resolved_meta in known_meta_paths:
                continue
            try:
                metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(metadata, dict):
                continue
            filename = str(metadata.get("filename") or meta_path.stem.replace(".part", "")).strip()
            final_name = str(metadata.get("final_name") or filename).strip()
            part_path = self.output_dir / f"{filename}.part"
            downloaded_bytes = part_path.stat().st_size if part_path.exists() else 0
            now = time.time()
            self.records.append(
                DirectDownloadRecord(
                    id=uuid4().hex,
                    url=str(metadata.get("url") or "").strip(),
                    added_at=now,
                    updated_at=now,
                    state="paused" if downloaded_bytes else "queued",
                    final_url=str(metadata.get("final_url") or metadata.get("url") or "").strip(),
                    filename=filename,
                    final_name=final_name,
                    content_type=str(metadata.get("content_type") or "").strip(),
                    total_size=int(metadata.get("total_size") or 0),
                    downloaded_bytes=downloaded_bytes,
                    supports_resume=bool(metadata.get("supports_resume")),
                    final_path=str((self.output_dir / final_name).resolve()),
                    part_path=str(part_path.resolve()),
                    meta_path=resolved_meta,
                    last_message="Recovered existing partial direct download.",
                )
            )
            known_meta_paths.add(resolved_meta)
            changed = True
        if changed:
            self._save()

    def get_records(self) -> list[DirectDownloadRecord]:
        with self.lock:
            return list(sorted(self.records, key=lambda item: item.added_at, reverse=True))

    def get_record(self, record_id: str) -> DirectDownloadRecord | None:
        with self.lock:
            for record in self.records:
                if record.id == record_id:
                    return record
        return None

    def get_active_record(self) -> DirectDownloadRecord | None:
        with self.lock:
            if self.active_record_id is None:
                return None
            return self.get_record(self.active_record_id)

    def has_active_download(self) -> bool:
        with self.lock:
            return self.active_record_id is not None

    def queue_download(self, url: str) -> DirectDownloadRecord:
        now = time.time()
        record = DirectDownloadRecord(
            id=uuid4().hex,
            url=str(url).strip(),
            added_at=now,
            updated_at=now,
            state="queued",
            last_message="Queued for direct download.",
        )
        with self.lock:
            self.records.append(record)
            self._save()
        self._emit_change()
        self.start_next_download()
        return record

    def _update_record(self, record: DirectDownloadRecord, **changes) -> None:
        for key, value in changes.items():
            setattr(record, key, value)
        record.updated_at = time.time()
        self._save()

    def _apply_task_snapshot(self, record: DirectDownloadRecord, task: DirectDownloadTask) -> None:
        probe = task.probe
        record.final_url = getattr(probe, "final_url", record.final_url) or record.final_url
        record.filename = getattr(probe, "filename", record.filename) or record.filename
        record.content_type = getattr(probe, "content_type", record.content_type) or record.content_type
        record.supports_resume = bool(getattr(probe, "supports_resume", record.supports_resume))
        record.total_size = int(getattr(task, "total_size", record.total_size) or record.total_size or 0)
        record.downloaded_bytes = int(getattr(task, "downloaded_bytes", record.downloaded_bytes) or 0)
        if task.final_path is not None:
            record.final_path = str(task.final_path.resolve())
            record.final_name = task.final_path.name
        if task.part_path is not None:
            record.part_path = str(task.part_path.resolve())
        if task.meta_path is not None:
            record.meta_path = str(task.meta_path.resolve())

    def _on_task_progress(self, record_id: str, task: DirectDownloadTask, percent: float | None, message: str) -> None:
        with self.lock:
            record = self.get_record(record_id)
            if record is None:
                return
            self._apply_task_snapshot(record, task)
            record.last_message = str(message or "").strip()
            self._save()
        self._emit_change()
        self._emit_active_progress(self.get_record(record_id))

    def _finalize_active_task(self, next_queue: bool = True, keep_active_record: bool = False) -> None:
        self.active_task = None
        if not keep_active_record:
            self.active_record_id = None
        self._emit_active_progress(None)
        if next_queue:
            self.start_next_download()

    def _on_task_state(self, record_id: str, task: DirectDownloadTask, state: str, payload=None) -> None:
        with self.lock:
            record = self.get_record(record_id)
            if record is None:
                return
            self._apply_task_snapshot(record, task)
            record.state = state
            if state == "completed":
                record.completed_at = time.time()
                record.error_message = ""
                record.last_message = f"Downloaded: {Path(payload).name}" if payload else "Download completed."
            elif state == "error":
                record.error_message = str(payload or task.error_message or "Download failed.")
                record.last_message = record.error_message
            elif state == "cancelled":
                record.last_message = "Download cancelled."
            elif state == "paused":
                record.last_message = "Download paused."
            elif state == "probing":
                record.last_message = "Inspecting direct link..."
            elif state == "downloading":
                record.last_message = "Downloading..."
            self._save()

        self._emit_change()
        active_record = self.get_record(record_id)
        if active_record is not None:
            self._emit_active_progress(active_record)

        if state in {"completed", "error", "cancelled"}:
            self._finalize_active_task(next_queue=True)
        elif state == "paused":
            self._finalize_active_task(next_queue=False, keep_active_record=True)

    def _start_record(self, record: DirectDownloadRecord) -> bool:
        if self.active_task is not None:
            return False
        if self.active_record_id is not None and self.active_record_id != record.id:
            return False
        if not self.can_start_downloads():
            return False

        record.state = "probing"
        record.error_message = ""
        record.last_message = "Preparing direct download..."
        record.updated_at = time.time()
        self._save()

        task = DirectDownloadTask(
            url=record.url,
            output_dir=self.output_dir,
            log_callback=lambda message, item_id=record.id: self._log(f"[List:{item_id[:6]}] {message}"),
            progress_callback=lambda percent, message, item_id=record.id: self._on_task_progress(item_id, task, percent, message),
            state_callback=lambda state, payload=None, item_id=record.id: self._on_task_state(item_id, task, state, payload),
            delete_partial_on_cancel=False,
        )
        self.active_task = task
        self.active_record_id = record.id
        started = task.start()
        if not started:
            self.active_task = None
            self.active_record_id = None
            record.state = "queued"
            record.last_message = "Waiting in queue."
            self._save()
            return False
        self._emit_change()
        self._emit_active_progress(record)
        return True

    def start_next_download(self) -> bool:
        with self.lock:
            if self.has_active_download() or not self.can_start_downloads():
                return False
            queued = sorted(
                (record for record in self.records if record.state == "queued"),
                key=lambda item: item.added_at,
            )
            if not queued:
                return False
            next_record = queued[0]
        return self._start_record(next_record)

    def resume_record(self, record_id: str) -> bool:
        with self.lock:
            record = self.get_record(record_id)
            if record is None:
                return False
            if record.state in {"completed", "downloading", "probing"}:
                return False
            if (self.active_record_id is not None and self.active_record_id != record.id) or not self.can_start_downloads():
                self._update_record(record, state="queued", last_message="Queued to resume.")
                self._emit_change()
                return True
        return self._start_record(record)

    def pause_record(self, record_id: str) -> bool:
        with self.lock:
            if self.active_record_id != record_id or self.active_task is None:
                record = self.get_record(record_id)
                if record is not None and record.state == "queued":
                    self._update_record(record, state="paused", last_message="Queued download paused.")
                    self._emit_change()
                    return True
                return False
            if self.active_task.state == "downloading":
                self.active_task.pause()
                return True
        return False

    def cancel_record(self, record_id: str) -> bool:
        with self.lock:
            record = self.get_record(record_id)
            if record is None:
                return False
            if self.active_record_id == record_id and self.active_task is not None:
                self.active_task.cancel()
                record.last_message = "Cancelling download..."
                self._save()
                self._emit_change()
                return True
            self._update_record(record, state="cancelled", last_message="Download cancelled.")
        self._emit_change()
        return True

    def replace_record_url(self, record_id: str, new_url: str) -> bool:
        with self.lock:
            record = self.get_record(record_id)
            if record is None:
                return False
            cleaned_url = str(new_url).strip()
            if not cleaned_url:
                return False
            record.url = cleaned_url
            record.error_message = ""
            record.last_message = "Direct link updated."
            record.updated_at = time.time()
            if record.meta_path:
                meta_path = Path(record.meta_path)
                if meta_path.exists():
                    try:
                        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                    except Exception:
                        metadata = {}
                    if not isinstance(metadata, dict):
                        metadata = {}
                    metadata["url"] = cleaned_url
                    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            self._save()
        self._emit_change()
        return True

    def delete_record(self, record_id: str, *, delete_files: bool = False) -> bool:
        with self.lock:
            if self.active_record_id == record_id and self.active_task is not None:
                return False
            record = self.get_record(record_id)
            if record is None:
                return False
            if delete_files:
                for path_value in (record.final_path, record.part_path, record.meta_path):
                    if path_value:
                        try:
                            Path(path_value).unlink(missing_ok=True)
                        except Exception:
                            pass
            self.records = [item for item in self.records if item.id != record_id]
            self._save()
        self._emit_change()
        return True

    def clear_finished(self, *, delete_files: bool = False) -> int:
        removable_states = {"completed", "cancelled", "error"}
        removed = 0
        with self.lock:
            keep_records: list[DirectDownloadRecord] = []
            for record in self.records:
                if record.state in removable_states and record.id != self.active_record_id:
                    removed += 1
                    if delete_files:
                        for path_value in (record.final_path, record.part_path, record.meta_path):
                            if path_value:
                                try:
                                    Path(path_value).unlink(missing_ok=True)
                                except Exception:
                                    pass
                else:
                    keep_records.append(record)
            if removed:
                self.records = keep_records
                self._save()
        if removed:
            self._emit_change()
        return removed
