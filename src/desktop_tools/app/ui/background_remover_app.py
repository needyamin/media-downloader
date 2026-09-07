import hashlib
import os
import queue
import threading
import tkinter as tk
from tkinter import Tk, filedialog, ttk, StringVar, TclError, messagebox, Toplevel
from tkinter.messagebox import showinfo, showerror
import importlib
from PIL import Image, ImageDraw, ImageTk
import requests
import sys
import subprocess
from pathlib import Path
import shutil
import time

try:
    from desktop_tools.app.app_windowing import ensure_src_on_path
except Exception:
    from app_windowing import ensure_src_on_path

ensure_src_on_path(__file__)

from desktop_tools.shared.resources import apply_window_icon, center_window
from desktop_tools.shared.user_data_paths import get_bg_remover_diagnostics_path, get_rembg_models_dir
from desktop_tools.shared.capture_support import copy_image_to_clipboard, grab_clipboard_image
from desktop_tools.app.config.runtime_flags import get_tool_theme

MISSING_DEPENDENCIES = []
DEPENDENCY_ERRORS = {}
IS_WINDOWS = os.name == "nt"
DEPENDENCY_DIAGNOSTICS_REPORT = None


def configure_rembg_home() -> Path:
    """Point rembg at the app model folder so downloads and the UI use the same files."""
    target = get_rembg_models_dir()
    os.environ["U2NET_HOME"] = str(target)
    os.environ.setdefault("REMBG_HOME", str(target))
    return target


configure_rembg_home()


def register_dependency_error(name, exc):
    """Track dependency import failures so packaged builds show the real cause."""
    if name not in MISSING_DEPENDENCIES:
        MISSING_DEPENDENCIES.append(name)
    if exc is not None:
        DEPENDENCY_ERRORS[name] = f"{type(exc).__name__}: {exc}"

try:
    from rembg import new_session, remove as rembg_remove

    REMBG_AVAILABLE = True
except BaseException as exc:
    rembg_remove = None
    new_session = None
    REMBG_AVAILABLE = False
    register_dependency_error("rembg", exc)

background_remover_window = None

BACKGROUND_REMOVER_THEME_DEFAULTS = {
    "PRIMARY_BG": "#07111F",
    "SURFACE_BG": "#0F1C2E",
    "CARD_BG": "#132238",
    "CARD_BORDER": "#243B5A",
    "CANVAS_BG": "#091423",
    "ACCENT": "#60A5FA",
    "ACCENT_HOVER": "#3B82F6",
    "SUCCESS": "#22C55E",
    "SUCCESS_HOVER": "#16A34A",
    "DANGER": "#EF4444",
    "DANGER_HOVER": "#DC2626",
    "SECONDARY_BUTTON": "#16263B",
    "SECONDARY_BUTTON_HOVER": "#213552",
    "SECONDARY_BUTTON_BORDER": "#345072",
    "HEADER_BADGE_BG": "#102742",
    "HEADER_BADGE_BORDER": "#2A4B73",
    "TEXT_MAIN": "#F8FAFC",
    "TEXT_MUTED": "#B6C2D5",
    "TEXT_SOFT": "#7F91AB",
    "DANGER_TEXT": "#FCA5A5",
    "CHECKER_DARK": "#0C1526",
    "CHECKER_LIGHT": "#172235",
}
BACKGROUND_REMOVER_THEME = get_tool_theme("background_remover", BACKGROUND_REMOVER_THEME_DEFAULTS)
PRIMARY_BG = BACKGROUND_REMOVER_THEME["PRIMARY_BG"]
SURFACE_BG = BACKGROUND_REMOVER_THEME["SURFACE_BG"]
CARD_BG = BACKGROUND_REMOVER_THEME["CARD_BG"]
CARD_BORDER = BACKGROUND_REMOVER_THEME["CARD_BORDER"]
CANVAS_BG = BACKGROUND_REMOVER_THEME["CANVAS_BG"]
ACCENT = BACKGROUND_REMOVER_THEME["ACCENT"]
ACCENT_HOVER = BACKGROUND_REMOVER_THEME["ACCENT_HOVER"]
SUCCESS = BACKGROUND_REMOVER_THEME["SUCCESS"]
SUCCESS_HOVER = BACKGROUND_REMOVER_THEME["SUCCESS_HOVER"]
DANGER = BACKGROUND_REMOVER_THEME["DANGER"]
DANGER_HOVER = BACKGROUND_REMOVER_THEME["DANGER_HOVER"]
SECONDARY_BUTTON = BACKGROUND_REMOVER_THEME["SECONDARY_BUTTON"]
SECONDARY_BUTTON_HOVER = BACKGROUND_REMOVER_THEME["SECONDARY_BUTTON_HOVER"]
SECONDARY_BUTTON_BORDER = BACKGROUND_REMOVER_THEME["SECONDARY_BUTTON_BORDER"]
HEADER_BADGE_BG = BACKGROUND_REMOVER_THEME["HEADER_BADGE_BG"]
HEADER_BADGE_BORDER = BACKGROUND_REMOVER_THEME["HEADER_BADGE_BORDER"]
TEXT_MAIN = BACKGROUND_REMOVER_THEME["TEXT_MAIN"]
TEXT_MUTED = BACKGROUND_REMOVER_THEME["TEXT_MUTED"]
TEXT_SOFT = BACKGROUND_REMOVER_THEME["TEXT_SOFT"]
DANGER_TEXT = BACKGROUND_REMOVER_THEME["DANGER_TEXT"]
CHECKER_DARK = BACKGROUND_REMOVER_THEME["CHECKER_DARK"]
CHECKER_LIGHT = BACKGROUND_REMOVER_THEME["CHECKER_LIGHT"]

# rembg models: "classic" (smaller u2net family) vs "premium" (large optional downloads).
REMBG_MODEL_INFO: dict[str, dict[str, object]] = {
    "u2net": {
        "short": "Classic",
        "tier": "classic",
        "download_mb": 176,
        "detail": "Default remover. Small one-time download, then works offline.",
    },
    "u2net_human_seg": {
        "short": "People (fast)",
        "tier": "classic",
        "download_mb": 176,
        "detail": "Optimized for portraits and people.",
    },
    "u2netp": {
        "short": "Lightweight",
        "tier": "classic",
        "download_mb": 4,
        "detail": "Fastest classic model; lower quality on hard edges.",
    },
    "birefnet-general": {
        "short": "Best quality (BiRefNet)",
        "tier": "premium",
        "download_mb": 973,
        "detail": "Highest quality. Downloaded from the internet only when you select it and confirm.",
    },
    "bria-rmbg": {
        "short": "BRIA RMBG",
        "tier": "premium",
        "download_mb": 1024,
        "detail": "Strong alternative to BiRefNet; same optional download rules.",
    },
    "birefnet-portrait": {
        "short": "Portraits (BiRefNet)",
        "tier": "premium",
        "download_mb": 973,
        "detail": "Premium portrait model; optional large download.",
    },
}
REMBG_MODEL_MENU_ORDER = (
    "u2net",
    "u2net_human_seg",
    "u2netp",
    "birefnet-general",
    "bria-rmbg",
    "birefnet-portrait",
)
PREMIUM_REMBG_MODELS = frozenset(
    key for key, info in REMBG_MODEL_INFO.items() if info["tier"] == "premium"
)
CLASSIC_REMBG_MODELS = frozenset(
    key for key, info in REMBG_MODEL_INFO.items() if info["tier"] == "classic"
)
CLASSIC_MODEL_FALLBACKS = ("u2net", "u2net_human_seg", "u2netp")
PREMIUM_MODEL_FALLBACKS = ("birefnet-general", "bria-rmbg", "birefnet-portrait")
DEFAULT_REMBG_MODEL = "u2net"
MAX_INFERENCE_SIDE = 2048
DOWNLOAD_CONNECT_TIMEOUT_SEC = 30
DOWNLOAD_READ_TIMEOUT_SEC = 600
DOWNLOAD_PROGRESS_INTERVAL_SEC = 0.12

# Official rembg release URLs (same as rembg session classes).
REMBG_MODEL_DOWNLOADS: dict[str, dict[str, str | None]] = {
    "u2net": {
        "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx",
        "hash": "md5:60024c5c889badc19c04ad937298a77b",
    },
    "u2net_human_seg": {
        "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx",
        "hash": "md5:c09ddc2e0104f800e3e1bb4652583d1f",
    },
    "u2netp": {
        "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx",
        "hash": "md5:8e83ca70e441ab06c318d82300c84806",
    },
    "birefnet-general": {
        "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/BiRefNet-general-epoch_244.onnx",
        "hash": "md5:7a35a0141cbbc80de11d9c9a28f52697",
    },
    "bria-rmbg": {
        "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/bria-rmbg-2.0.onnx",
        "hash": "sha256:5b486f08200f513f460da46dd701db5fbb47d79b4be4b708a19444bcd4e79958",
    },
    "birefnet-portrait": {
        "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/BiRefNet-portrait-epoch_150.onnx",
        "hash": "md5:c3a64a6abf20250d090cd055f12a3b67",
    },
}
_REMBG_SESSION_CACHE: dict[str, object] = {}
_REMBG_SESSION_LOCK = threading.Lock()


def get_rembg_cache_dir() -> Path:
    """Directory where rembg stores downloaded ONNX weights."""
    return configure_rembg_home()


def rembg_model_dest_path(model_name: str) -> Path:
    """Path rembg actually loads: `<home>/models/<name>/<name>.onnx`."""
    return get_rembg_cache_dir() / "models" / model_name / f"{model_name}.onnx"


def rembg_usable_model_paths(model_name: str) -> list[Path]:
    """Files rembg will accept without downloading again (current U2NET_HOME)."""
    home = get_rembg_cache_dir()
    return [
        rembg_model_dest_path(model_name),
        home / f"{model_name}.onnx",
    ]


def rembg_model_paths(model_name: str) -> list[Path]:
    """All known cache locations, including leftovers we may delete."""
    return rembg_usable_model_paths(model_name) + [
        Path.home() / ".u2net" / f"{model_name}.onnx",
        Path.home() / ".rembg" / "models" / model_name / f"{model_name}.onnx",
    ]


def is_rembg_model_cached(model_name: str) -> bool:
    """True only when rembg itself would reuse an existing file."""
    if model_name not in REMBG_MODEL_INFO:
        return False
    return any(path.is_file() and path.stat().st_size > 0 for path in rembg_usable_model_paths(model_name))


def growing_model_bytes(model_name: str) -> int:
    """Largest in-progress or finished model file rembg may be writing."""
    seen: set[Path] = set()
    largest = 0
    parents = {rembg_model_dest_path(model_name).parent, get_rembg_cache_dir()}
    for parent in parents:
        if not parent.is_dir():
            continue
        for path in parent.iterdir():
            if not path.is_file():
                continue
            name = path.name.lower()
            if model_name.lower() not in name and not name.endswith((".part", ".tmp", ".download")):
                continue
            try:
                resolved = path.resolve()
                size = path.stat().st_size
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            largest = max(largest, size)
    return largest


def downloaded_model_size_bytes(model_name: str) -> int:
    """Total bytes on disk for a model across known cache locations."""
    seen: set[Path] = set()
    total = 0
    for path in rembg_model_paths(model_name):
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen or not path.is_file():
            continue
        seen.add(resolved)
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


def list_downloaded_rembg_models() -> list[tuple[str, int]]:
    """Return downloaded models as (model_key, size_bytes), largest first."""
    found = []
    for model_name in REMBG_MODEL_MENU_ORDER:
        size = downloaded_model_size_bytes(model_name)
        if size > 0:
            found.append((model_name, size))
    return found


def delete_rembg_model(model_name: str) -> int:
    """Delete cached ONNX files for one model and drop its loaded session. Returns bytes removed."""
    removed = 0
    for path in rembg_model_paths(model_name):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
            path.unlink()
            removed += size
        except OSError:
            continue
        parent = path.parent
        if parent.name == model_name:
            try:
                parent.rmdir()
            except OSError:
                pass
    with _REMBG_SESSION_LOCK:
        _REMBG_SESSION_CACHE.pop(model_name, None)
    return removed


def delete_all_rembg_models() -> tuple[int, int]:
    """Delete every known rembg model. Returns (count, bytes)."""
    count = 0
    removed = 0
    for model_name, _size in list_downloaded_rembg_models():
        deleted = delete_rembg_model(model_name)
        if deleted:
            count += 1
            removed += deleted
    return count, removed


def is_premium_rembg_model(model_name: str) -> bool:
    return model_name in PREMIUM_REMBG_MODELS


def model_short_label(model_name: str) -> str:
    info = REMBG_MODEL_INFO.get(model_name)
    if not info:
        return model_name
    return str(info["short"])


def model_menu_label(model_name: str) -> str:
    """Human-readable dropdown label (static; see status line for install state)."""
    info = REMBG_MODEL_INFO.get(model_name)
    if not info:
        return model_name
    short = str(info["short"])
    download_mb = int(info["download_mb"])
    if info["tier"] == "premium":
        return f"{short} — optional ~{download_mb} MB download"
    return f"{short} — classic (~{download_mb} MB first run)"


REMBG_MODEL_MENU_LABELS = {key: model_menu_label(key) for key in REMBG_MODEL_MENU_ORDER}
REMBG_LABEL_TO_MODEL_KEY = {label: key for key, label in REMBG_MODEL_MENU_LABELS.items()}


def resolve_model_key(selection: str | None = None) -> str:
    """Map a dropdown label (or raw key) to a rembg model id."""
    if not selection:
        return DEFAULT_REMBG_MODEL
    if selection in REMBG_MODEL_INFO:
        return selection
    return REMBG_LABEL_TO_MODEL_KEY.get(selection, DEFAULT_REMBG_MODEL)


def _fallback_models_for(model_name: str) -> tuple[str, ...]:
    """Only fall back within the same tier — never auto-download premium for classic users."""
    if is_premium_rembg_model(model_name):
        pool = PREMIUM_MODEL_FALLBACKS
    else:
        pool = CLASSIC_MODEL_FALLBACKS
    chain: list[str] = []
    for candidate in (model_name, *pool):
        if candidate in REMBG_MODEL_INFO and candidate not in chain:
            chain.append(candidate)
    return tuple(chain)


def describe_model_choice(model_name: str) -> str:
    info = REMBG_MODEL_INFO.get(model_name, {})
    detail = str(info.get("detail", ""))
    if is_rembg_model_cached(model_name):
        path = next(p for p in rembg_usable_model_paths(model_name) if p.is_file())
        size_mb = path.stat().st_size / (1024 * 1024)
        return (
            f"{model_short_label(model_name)} is already downloaded on this PC "
            f"({size_mb:.0f} MB at {path}). No download needed. {detail}"
        )
    download_mb = int(info.get("download_mb", 0))
    return (
        f"{model_short_label(model_name)} is not downloaded yet (~{download_mb} MB). "
        f"The blue download progress bar in this window will appear when you process an image. {detail}"
    )


def model_ready_message(model_name: str) -> str:
    """Message when weights are already on disk."""
    path = next((p for p in rembg_usable_model_paths(model_name) if p.is_file()), rembg_model_dest_path(model_name))
    size_mb = path.stat().st_size / (1024 * 1024) if path.is_file() else 0
    return (
        f"{model_short_label(model_name)} is already downloaded.\n\n"
        f"Folder: {path.parent}\n"
        f"File: {path.name}\n"
        f"Size: about {size_mb:.0f} MB\n\n"
        "No internet download is required. Click OK to start removing the background."
    )


def _throttled_progress(on_progress, interval: float = DOWNLOAD_PROGRESS_INTERVAL_SEC):
    """Wrap a progress callback so the UI is not flooded with thousands of updates."""
    if on_progress is None:
        return None

    state = {"last_time": 0.0, "last_pct": -1.0}

    def report(percent: float | None, message: str, *, force: bool = False):
        now = time.monotonic()
        if not force and percent is not None:
            if (
                now - state["last_time"] < interval
                and abs(percent - state["last_pct"]) < 0.4
                and percent < 99.9
            ):
                return
            state["last_pct"] = percent
        state["last_time"] = now
        on_progress(percent, message)

    return report


def _parse_known_hash(known_hash: str | None) -> tuple[str | None, str | None]:
    if not known_hash:
        return None, None
    if ":" in known_hash:
        algorithm, digest = known_hash.split(":", 1)
        return algorithm.lower(), digest.lower()
    return "md5", known_hash.lower()


def _verify_model_file_hash(
    model_path: Path,
    known_hash: str | None,
    on_progress=None,
) -> None:
    algorithm, expected = _parse_known_hash(known_hash)
    if not algorithm or not expected:
        return

    reporter = _throttled_progress(on_progress)
    if reporter:
        reporter(None, f"Verifying {algorithm.upper()} checksum…", force=True)

    hasher = hashlib.new(algorithm)
    total_size = model_path.stat().st_size
    bytes_read = 0
    with open(model_path, "rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            hasher.update(chunk)
            bytes_read += len(chunk)
            if reporter and total_size > 0:
                pct = 100.0 * bytes_read / total_size
                done_mb = bytes_read / (1024 * 1024)
                total_mb = total_size / (1024 * 1024)
                reporter(
                    pct,
                    f"Verifying… {done_mb:.1f} / {total_mb:.1f} MB ({pct:.1f}%)",
                )

    if hasher.hexdigest() != expected:
        try:
            model_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError(
            "Downloaded model file failed checksum verification. "
            "Check your internet connection and try again."
        )


def _download_url_to_file(
    url: str,
    dest_path: Path,
    on_progress=None,
) -> None:
    """Stream-download a model file with real byte progress (GitHub releases)."""
    reporter = _throttled_progress(on_progress)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(dest_path.suffix + ".part")
    if temp_path.exists():
        try:
            temp_path.unlink()
        except OSError:
            pass

    if reporter:
        reporter(0.0, "Connecting to GitHub…", force=True)

    try:
        response = requests.get(
            url,
            stream=True,
            timeout=(DOWNLOAD_CONNECT_TIMEOUT_SEC, DOWNLOAD_READ_TIMEOUT_SEC),
            headers={"User-Agent": "MediaDownloader-BackgroundRemover/1.0"},
        )
        response.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(
            "Connection to the download server timed out. Check your internet and try again."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Could not reach the download server: {exc}") from exc

    total_size = int(response.headers.get("content-length", 0))
    downloaded = 0

    if reporter and total_size <= 0:
        reporter(None, "Downloading… total size unknown, please wait…", force=True)

    try:
        with open(temp_path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=256 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                downloaded += len(chunk)
                if reporter and total_size > 0:
                    pct = min(100.0, 100.0 * downloaded / total_size)
                    done_mb = downloaded / (1024 * 1024)
                    total_mb = total_size / (1024 * 1024)
                    reporter(
                        pct,
                        f"Downloading… {done_mb:.1f} / {total_mb:.1f} MB ({pct:.1f}%)",
                    )
                elif reporter:
                    done_mb = downloaded / (1024 * 1024)
                    reporter(None, f"Downloading… {done_mb:.1f} MB received")
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(
            "Download stalled or timed out. Check your internet and try again."
        ) from exc
    finally:
        response.close()

    if downloaded <= 0:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError("Download returned no data from the server.")

    temp_path.replace(dest_path)
    if reporter:
        reporter(100.0, "Download complete — verifying file…", force=True)


def _download_via_rembg_pooch(model_name: str, on_progress=None) -> Path:
    """Fallback: use rembg's built-in pooch downloader."""
    from rembg.sessions import sessions_class

    session_class = None
    for candidate in sessions_class:
        if candidate.name() == model_name:
            session_class = candidate
            break
    if session_class is None:
        raise ValueError(f"Unknown rembg model: {model_name}")

    reporter = _throttled_progress(on_progress)
    if reporter:
        reporter(0.0, "Connecting (rembg downloader)…", force=True)

    class _PoochProgressBridge:
        def __init__(self):
            self.total = 0
            self.count = 0

        def update(self, n):
            self.count = min(self.count + n, self.total or self.count + n)
            if reporter and self.total > 0:
                pct = min(100.0, 100.0 * self.count / self.total)
                done_mb = self.count / (1024 * 1024)
                total_mb = self.total / (1024 * 1024)
                reporter(
                    pct,
                    f"Downloading… {done_mb:.1f} / {total_mb:.1f} MB ({pct:.1f}%)",
                )

        def reset(self):
            self.count = 0

        def close(self):
            if reporter:
                reporter(100.0, "Download complete — verifying file…", force=True)

    import pooch

    original_retrieve = pooch.retrieve
    bridge = _PoochProgressBridge()

    def retrieve_with_progress(*args, progressbar=False, **kwargs):
        return original_retrieve(*args, progressbar=bridge, **kwargs)

    pooch.retrieve = retrieve_with_progress
    try:
        session_class.download_models()
    finally:
        pooch.retrieve = original_retrieve

    return rembg_model_dest_path(model_name)


def _reuse_or_promote_cached_model(model_name: str) -> Path | None:
    """Return a rembg-usable file, copying a leftover into the official folder if needed."""
    dest = rembg_model_dest_path(model_name)
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    for path in rembg_model_paths(model_name):
        if path == dest or not path.is_file() or path.stat().st_size <= 0:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(path, dest)
        except OSError:
            return path
        return dest
    return None


def ensure_rembg_model_downloaded(
    model_name: str,
    on_progress=None,
) -> Path:
    """
    Download rembg ONNX weights if missing. Calls on_progress(percent, message)
    where percent may be None when total size is unknown.
    """
    reporter = _throttled_progress(on_progress)
    existing = _reuse_or_promote_cached_model(model_name)
    if existing is not None:
        if reporter:
            reporter(100.0, "Model already on this PC — skipping download.", force=True)
        return existing

    if not REMBG_AVAILABLE:
        raise RuntimeError("rembg is not available")

    model_path = rembg_model_dest_path(model_name)
    spec = REMBG_MODEL_DOWNLOADS.get(model_name)
    if spec and spec.get("url"):
        _download_url_to_file(str(spec["url"]), model_path, on_progress=on_progress)
        _verify_model_file_hash(model_path, spec.get("hash"), on_progress=on_progress)
    else:
        model_path = _download_via_rembg_pooch(model_name, on_progress=on_progress)

    if not model_path.is_file():
        raise RuntimeError(f"Download finished but model file is missing: {model_path}")

    if reporter:
        reporter(100.0, "Model saved — ready to use.", force=True)
    return model_path


def _normalize_input_image(image: Image.Image) -> Image.Image:
    """Convert any mode to RGB for rembg (flatten alpha onto white)."""
    if image.mode == "RGBA":
        flat = Image.new("RGB", image.size, (255, 255, 255))
        flat.paste(image, mask=image.split()[3])
        return flat
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def _resize_for_inference(image: Image.Image, max_side: int = MAX_INFERENCE_SIDE) -> tuple[Image.Image, float]:
    """Downscale very large photos so inference stays fast and stable."""
    width, height = image.size
    longest = max(width, height)
    if longest <= max_side:
        return image, 1.0
    scale = max_side / float(longest)
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS), scale


def _get_rembg_session(
    model_name: str,
    *,
    allow_download: bool = True,
    on_download_progress=None,
):
    """Load and cache an ONNX session."""
    if not REMBG_AVAILABLE or new_session is None:
        raise RuntimeError("rembg is not available")

    if (
        is_premium_rembg_model(model_name)
        and not allow_download
        and not is_rembg_model_cached(model_name)
    ):
        raise RuntimeError(
            f"{model_short_label(model_name)} is not installed. "
            "Select it in the model menu and confirm the download, or choose a classic model."
        )

    if allow_download and not is_rembg_model_cached(model_name):
        ensure_rembg_model_downloaded(model_name, on_progress=on_download_progress)

    with _REMBG_SESSION_LOCK:
        cached = _REMBG_SESSION_CACHE.get(model_name)
        if cached is not None:
            return cached
        if on_download_progress and not is_rembg_model_cached(model_name):
            on_download_progress(None, "Downloading model…")
        session = _new_session_with_progress(model_name, on_download_progress)
        _REMBG_SESSION_CACHE[model_name] = session
        return session


def _new_session_with_progress(model_name: str, on_progress=None):
    """Create a rembg session, forwarding pooch download ticks to the UI."""
    if on_progress is None or new_session is None:
        return new_session(model_name)

    reporter = _throttled_progress(on_progress)
    if reporter:
        reporter(None, "Loading model…", force=True)

    class _PoochProgressBridge:
        def __init__(self):
            self.total = 0
            self.count = 0

        def update(self, n):
            self.count = min(self.count + n, self.total or self.count + n)
            if reporter and self.total > 0:
                pct = min(100.0, 100.0 * self.count / self.total)
                done_mb = self.count / (1024 * 1024)
                total_mb = self.total / (1024 * 1024)
                reporter(
                    pct,
                    f"Downloading… {done_mb:.1f} / {total_mb:.1f} MB ({pct:.1f}%)",
                )
            elif reporter:
                done_mb = self.count / (1024 * 1024)
                reporter(None, f"Downloading… {done_mb:.1f} MB received")

        def reset(self):
            self.count = 0

        def close(self):
            if reporter:
                reporter(None, "Loading model…", force=True)

    import pooch

    original_retrieve = pooch.retrieve
    bridge = _PoochProgressBridge()

    def retrieve_with_progress(*args, progressbar=False, **kwargs):
        return original_retrieve(*args, progressbar=bridge, **kwargs)

    pooch.retrieve = retrieve_with_progress
    try:
        return new_session(model_name)
    finally:
        pooch.retrieve = original_retrieve


def remove_image_background(
    image: Image.Image,
    *,
    model_name: str = DEFAULT_REMBG_MODEL,
    alpha_matting: bool = True,
    allow_model_download: bool = True,
    on_download_progress=None,
) -> Image.Image:
    """
    Remove background using rembg.

    Classic models (u2net family) are used by default. Premium models (BiRefNet, BRIA)
    are only loaded when allow_model_download is True (user confirmed in the GUI).
  """
    if not REMBG_AVAILABLE or rembg_remove is None:
        raise RuntimeError("rembg is not available")

    if model_name not in REMBG_MODEL_INFO:
        model_name = DEFAULT_REMBG_MODEL

    original_size = image.size
    rgb = _normalize_input_image(image)
    work, scale = _resize_for_inference(rgb)

    models_to_try = _fallback_models_for(model_name)
    last_error: Exception | None = None
    for candidate in models_to_try:
        if (
            is_premium_rembg_model(candidate)
            and not allow_model_download
            and not is_rembg_model_cached(candidate)
        ):
            continue
        try:
            session = _get_rembg_session(
                candidate,
                allow_download=allow_model_download,
                on_download_progress=on_download_progress,
            )
            if on_download_progress:
                on_download_progress(None, "Removing background…")
            output = rembg_remove(
                work,
                session=session,
                alpha_matting=alpha_matting,
                alpha_matting_foreground_threshold=240,
                alpha_matting_background_threshold=10,
                alpha_matting_erode_size=10,
                post_process_mask=True,
            )
            if not isinstance(output, Image.Image):
                output = Image.fromarray(output)
            if output.mode != "RGBA":
                output = output.convert("RGBA")
            if scale < 1.0:
                output = output.resize(original_size, Image.Resampling.LANCZOS)
            return output
        except Exception as exc:
            last_error = exc
            with _REMBG_SESSION_LOCK:
                _REMBG_SESSION_CACHE.pop(candidate, None)
            log(f"rembg model '{candidate}' failed: {exc}")

    if last_error is None and is_premium_rembg_model(model_name) and not allow_model_download:
        raise RuntimeError(
            f"{model_short_label(model_name)} is not installed. "
            "Select it in the model menu and confirm the download, or choose a classic model."
        )
    raise RuntimeError(f"Background removal failed: {last_error}")


def log(message):
    """Simple logging function"""
    print(f"[LOG] {message}")

def is_packaged_runtime():
    """Return True when running from a packaged executable instead of source."""
    executable_name = Path(sys.executable).name.lower()
    return (
        bool(getattr(sys, "frozen", False))
        or globals().get("__compiled__") is not None
    ) and executable_name not in {"python.exe", "pythonw.exe"}

def show_startup_error(title, message):
    """Show a GUI error when possible and fall back to stderr-friendly output."""
    try:
        root = Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except TclError:
        print(f"{title}: {message}")

def collect_dependency_diagnostics():
    """Probe the BG remover import chain and return a detailed diagnostic report."""
    checks = [
        ("onnxruntime", "onnxruntime", ()),
        ("onnxruntime.capi._pybind_state", "onnxruntime.capi._pybind_state", ()),
        ("onnxruntime.capi.onnxruntime_pybind11_state", "onnxruntime.capi.onnxruntime_pybind11_state", ()),
        ("numpy", "numpy", ()),
        ("scipy.ndimage", "scipy.ndimage", ("binary_erosion", "gaussian_filter")),
        ("skimage.morphology", "skimage.morphology", ("disk", "opening")),
        ("pymatting.alpha.estimate_alpha_cf", "pymatting.alpha.estimate_alpha_cf", ("estimate_alpha_cf",)),
        ("pymatting.foreground.estimate_foreground_ml", "pymatting.foreground.estimate_foreground_ml", ("estimate_foreground_ml",)),
        ("pymatting.util.util", "pymatting.util.util", ("stack_images",)),
        ("pooch", "pooch", ()),
        ("Pillow", "PIL.Image", ("Image",)),
    ]

    lines = []
    for label, module_name, attrs in checks:
        try:
            module = importlib.import_module(module_name)
            for attr_name in attrs:
                getattr(module, attr_name)
            lines.append(f"- {label}: OK")
        except BaseException as exc:
            lines.append(f"- {label}: {type(exc).__name__}: {exc}")

    return "\n".join(lines)

def write_dependency_diagnostics_report(details_text):
    """Persist BG remover diagnostics to a temp file for packaged-build debugging."""
    global DEPENDENCY_DIAGNOSTICS_REPORT

    try:
        report_path = get_bg_remover_diagnostics_path()
        report_path.write_text(details_text, encoding="utf-8")
        DEPENDENCY_DIAGNOSTICS_REPORT = report_path
        return report_path
    except Exception:
        DEPENDENCY_DIAGNOSTICS_REPORT = None
        return None


REQUIRED_PIP_PACKAGES = (
    ("rembg", "rembg"),
    ("onnxruntime", "onnxruntime"),
)
WINDOW_WIDTH = 920
WINDOW_HEIGHT = 680


class BlueProgressBar(tk.Canvas):
    """Windows-safe blue bar. ttk Progressbar often stays blank on dark themes."""

    def __init__(self, parent, *, height=18, trough=CANVAS_BG, fill=ACCENT):
        super().__init__(parent, height=height, highlightthickness=0, bd=0, bg=trough)
        self._trough = trough
        self._fill = fill
        self._value = 0.0
        self._indeterminate = False
        self._anim_job = None
        self._anim_pos = 0
        self.bind("<Configure>", lambda _e: self._redraw())

    def set_value(self, percent: float):
        self._indeterminate = False
        self._stop_anim()
        self._value = max(0.0, min(100.0, float(percent)))
        self._redraw()

    def start_indeterminate(self):
        if self._indeterminate and self._anim_job is not None:
            return
        self._indeterminate = True
        self._tick()

    def stop(self):
        self._indeterminate = False
        self._stop_anim()
        self._value = 0.0
        self._redraw()

    def _stop_anim(self):
        job = self._anim_job
        self._anim_job = None
        if job is None:
            return
        try:
            self.after_cancel(job)
        except TclError:
            pass

    def _tick(self):
        if not self._indeterminate:
            return
        width = max(self.winfo_width(), 40)
        self._anim_pos = (self._anim_pos + max(6, width // 24)) % (width + width // 3)
        self._redraw()
        try:
            self._anim_job = self.after(40, self._tick)
        except TclError:
            self._anim_job = None

    def _redraw(self):
        try:
            self.delete("all")
        except TclError:
            return
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        self.create_rectangle(0, 0, width, height, fill=self._trough, outline="")
        if self._indeterminate:
            bar_w = max(48, width // 4)
            x = self._anim_pos - bar_w
            self.create_rectangle(x, 2, x + bar_w, height - 2, fill=self._fill, outline="")
        else:
            fill_w = int(width * self._value / 100.0)
            if fill_w > 0:
                self.create_rectangle(0, 2, fill_w, height - 2, fill=self._fill, outline="")


def try_load_rembg() -> bool:
    """Import rembg if it is installed, and refresh the module-level flags."""
    global rembg_remove, new_session, REMBG_AVAILABLE
    try:
        from rembg import new_session as loaded_session, remove as loaded_remove

        rembg_remove = loaded_remove
        new_session = loaded_session
        REMBG_AVAILABLE = True
        if "rembg" in MISSING_DEPENDENCIES:
            MISSING_DEPENDENCIES.remove("rembg")
        DEPENDENCY_ERRORS.pop("rembg", None)
        return True
    except BaseException as exc:
        rembg_remove = None
        new_session = None
        REMBG_AVAILABLE = False
        register_dependency_error("rembg", exc)
        return False


def install_python_package(pip_name: str, logger=None) -> None:
    """Install one dependency with pip (source runs only)."""
    if logger:
        logger(f"Downloading dependency: {pip_name}...")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--user", pip_name],
        capture_output=True,
        text=True,
        creationflags=creationflags,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-400:]
        raise RuntimeError(f"Could not install {pip_name}.\n{detail}")
    if logger:
        logger(f"{pip_name} installed.")


def install_missing_bg_remover_packages(logger=None) -> bool:
    """Install rembg and onnxruntime when they are missing."""
    if is_packaged_runtime():
        return try_load_rembg()
    missing = []
    for import_name, pip_name in REQUIRED_PIP_PACKAGES:
        try:
            importlib.import_module(import_name)
        except BaseException:
            missing.append(pip_name)
    for pip_name in missing:
        install_python_package(pip_name, logger=logger)
    return try_load_rembg()


class BackgroundRemoverApp:
    def __init__(self, master, auto_prepare=True):
        self.master = master
        self.master.title("Background Remover")
        self.master.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.master.minsize(760, 580)
        self.master.resizable(True, True)
        self.master.configure(bg=PRIMARY_BG)

        self.style = ttk.Style(self.master)
        self._configure_style()
        self._configure_window_icon()
        self.master.bind("<Control-o>", lambda e: self.upload_image())
        self.master.bind("<Control-s>", lambda e: self.save_processed_image())
        self.master.bind("<Control-v>", self.paste_clipboard_image)
        self.master.bind("<Control-V>", self.paste_clipboard_image)
        self.master.bind("<Control-c>", self.copy_result_image)
        self.master.bind("<Control-C>", self.copy_result_image)

        self.current_image = None
        self.processed_image = None
        self.original_path = None
        self._original_source_label = "Clipboard"
        self._redraw_job = None
        self.status_var = StringVar(value="Open an image or press Ctrl+V to paste one")
        self.dep_var = StringVar(value="")
        self.original_details_var = StringVar(value="Original")
        self.processed_details_var = StringVar(value="Result")
        self.model_var = StringVar(value=REMBG_MODEL_MENU_LABELS[DEFAULT_REMBG_MODEL])
        self.model_hint_var = StringVar(value=describe_model_choice(DEFAULT_REMBG_MODEL))
        self.refine_edges_var = tk.BooleanVar(value=True)
        self.download_title_var = StringVar(value="Downloading dependency")
        self.download_percent_var = StringVar(value="")
        self.download_status_var = StringVar(value="")
        self._last_model_key = DEFAULT_REMBG_MODEL
        self._premium_download_approved: set[str] = {
            key for key in PREMIUM_REMBG_MODELS if is_rembg_model_cached(key)
        }
        self._notified_installed_models: set[str] = set()
        self._warned_download = False
        self._prepare_thread = None
        self._worker_queue: queue.Queue = queue.Queue()
        self._worker_poll_job = None
        self._panel_holders: set[str] = set()
        self._watch_stop = threading.Event()
        self._watch_thread = None
        self._watch_model_key = None

        self._build_ui()
        self._refresh_preview_panels()
        self._start_worker_queue_polling()
        self.master.after_idle(
            lambda: center_window(
                self.master,
                self.master.master if isinstance(self.master, Toplevel) else None,
            )
        )
        if auto_prepare:
            self.master.after_idle(self._start_background_prepare)

    def _configure_style(self):
        try:
            self.style.theme_use("clam")
        except TclError:
            pass
        self.style.configure("TFrame", background=PRIMARY_BG)
        self.style.configure("Panel.TFrame", background=CARD_BG)
        self.style.configure("Section.TFrame", background=SURFACE_BG)
        self.style.configure("Warn.TFrame", background="#3A2A0A")
        self.style.configure("Header.TLabel", background=PRIMARY_BG, foreground=TEXT_MAIN, font=("Segoe UI", 14, "bold"))
        self.style.configure("SubHeader.TLabel", background=PRIMARY_BG, foreground=TEXT_MUTED, font=("Segoe UI", 9))
        self.style.configure("Warn.TLabel", background="#3A2A0A", foreground="#F59E0B", font=("Segoe UI", 8), wraplength=860)
        self.style.configure("FieldLabel.TLabel", background=SURFACE_BG, foreground=TEXT_MAIN, font=("Segoe UI", 9, "bold"))
        self.style.configure("Hint.TLabel", background=PRIMARY_BG, foreground=TEXT_MUTED, font=("Segoe UI", 8))
        self.style.configure("SectionHint.TLabel", background=SURFACE_BG, foreground=TEXT_MUTED, font=("Segoe UI", 8))
        self.style.configure("Card.TCheckbutton", background=SURFACE_BG, foreground=TEXT_MAIN)
        self.style.configure("CardTitle.TLabel", background=CARD_BG, foreground=TEXT_MAIN, font=("Segoe UI", 9, "bold"))
        self.style.configure(
            "Modern.TCombobox",
            fieldbackground=SECONDARY_BUTTON,
            background=SECONDARY_BUTTON,
            foreground=TEXT_MAIN,
            arrowcolor=ACCENT,
            padding=4,
        )
        self.style.map(
            "Modern.TCombobox",
            fieldbackground=[("readonly", SECONDARY_BUTTON)],
            selectbackground=[("readonly", SECONDARY_BUTTON)],
            selectforeground=[("readonly", TEXT_MAIN)],
            foreground=[("readonly", TEXT_MAIN)],
        )
        self.style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"), padding=(8, 6), borderwidth=0, background=ACCENT, foreground="#06111E")
        self.style.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", "#374151")])
        self.style.configure("Secondary.TButton", font=("Segoe UI", 9), padding=(8, 6), borderwidth=0, background=SECONDARY_BUTTON, foreground=TEXT_MAIN)
        self.style.map("Secondary.TButton", background=[("active", SECONDARY_BUTTON_HOVER), ("disabled", "#1E293B")])
        self.style.configure("Success.TButton", font=("Segoe UI", 9, "bold"), padding=(8, 6), borderwidth=0, background=SUCCESS, foreground="#F8FFF9")
        self.style.map("Success.TButton", background=[("active", SUCCESS_HOVER), ("disabled", "#374151")])
        self.style.configure("Danger.TButton", font=("Segoe UI", 9), padding=(8, 6), borderwidth=0, background=DANGER, foreground="#ffffff")
        self.style.map("Danger.TButton", background=[("active", DANGER_HOVER), ("disabled", "#374151")])
        self.style.configure(
            "Modern.Horizontal.TProgressbar",
            troughcolor=CANVAS_BG,
            background=ACCENT,
            bordercolor=CANVAS_BG,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
            thickness=16,
        )

    def _configure_window_icon(self):
        try:
            apply_window_icon(self.master, app_id="needyamin.media_downloader")
        except Exception as exc:
            log(f"Could not load application icon: {exc}")

    def _build_ui(self):
        root = ttk.Frame(self.master, style="TFrame")
        root.pack(fill="both", expand=True, padx=14, pady=12)

        ttk.Label(root, text="Background Remover", style="Header.TLabel").pack(anchor="w")
        ttk.Label(root, textvariable=self.status_var, style="SubHeader.TLabel", wraplength=860, justify="left").pack(
            anchor="w", pady=(2, 8)
        )

        self.dep_banner = ttk.Frame(root, style="Warn.TFrame", padding=(8, 6))
        ttk.Label(self.dep_banner, textvariable=self.dep_var, style="Warn.TLabel").pack(anchor="w")

        self.download_panel = ttk.Frame(root, style="Section.TFrame", padding=(8, 8))
        header = ttk.Frame(self.download_panel, style="Section.TFrame")
        header.pack(fill="x")
        ttk.Label(header, textvariable=self.download_title_var, style="FieldLabel.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self.download_percent_var, style="FieldLabel.TLabel").pack(side="right")
        self.download_progress = BlueProgressBar(self.download_panel)
        self.download_progress.pack(fill="x", pady=(8, 4))
        ttk.Label(self.download_panel, textvariable=self.download_status_var, style="SectionHint.TLabel", wraplength=840).pack(anchor="w")

        self.body = ttk.Frame(root, style="TFrame")
        self.body.pack(fill="both", expand=True)

        toolbar = ttk.Frame(self.body, style="TFrame")
        toolbar.pack(fill="x")
        self.upload_button = ttk.Button(toolbar, text="Open", style="Accent.TButton", command=self.upload_image)
        self.upload_button.pack(side="left")
        self.paste_button = ttk.Button(toolbar, text="Paste", style="Secondary.TButton", command=self.paste_clipboard_image)
        self.paste_button.pack(side="left", padx=(6, 0))
        self.save_button = ttk.Button(toolbar, text="Save PNG", style="Success.TButton", command=self.save_processed_image, state="disabled")
        self.save_button.pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Clear", style="Secondary.TButton", command=self.clear_images).pack(side="left", padx=(6, 0))

        options = ttk.Frame(self.body, style="Section.TFrame", padding=(10, 8))
        options.pack(fill="x", pady=(8, 0))
        options.columnconfigure(1, weight=1)
        ttk.Label(options, text="Model", style="FieldLabel.TLabel").grid(row=0, column=0, sticky="w")
        self.model_menu = ttk.Combobox(
            options,
            textvariable=self.model_var,
            values=[REMBG_MODEL_MENU_LABELS[key] for key in REMBG_MODEL_MENU_ORDER],
            state="readonly",
            style="Modern.TCombobox",
        )
        self.model_menu.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self.model_menu.bind("<<ComboboxSelected>>", lambda _e: self._on_model_changed(self.model_var.get()))
        ttk.Checkbutton(options, text="Refine edges", variable=self.refine_edges_var, style="Card.TCheckbutton").grid(
            row=0, column=2, sticky="e"
        )
        self.delete_models_button = ttk.Button(
            options,
            text="Delete models",
            style="Danger.TButton",
            command=self.open_delete_models_dialog,
        )
        self.delete_models_button.grid(row=0, column=3, sticky="e", padx=(8, 0))
        self._sync_model_menu_to_key(DEFAULT_REMBG_MODEL)
        self._update_model_hint(DEFAULT_REMBG_MODEL)

        ttk.Label(self.body, textvariable=self.model_hint_var, style="Hint.TLabel", wraplength=860, justify="left").pack(
            anchor="w", pady=(6, 0)
        )

        self.previews = ttk.Frame(self.body, style="TFrame")
        self.previews.pack(fill="both", expand=True, pady=(8, 0))
        self.previews.columnconfigure(0, weight=1)
        self.previews.columnconfigure(1, weight=1)
        self.previews.rowconfigure(0, weight=1)

        self.original_card = self._create_preview_card(self.previews, "Original", self.original_details_var, 0)
        self.original_canvas = self.original_card["canvas"]
        self.processed_card = self._create_preview_card(self.previews, "Result", self.processed_details_var, 1, copyable=True)
        self.removed_canvas = self.processed_card["canvas"]
        self.copy_result_button = self.processed_card["copy_button"]

    def _create_preview_card(self, parent, title, details_var, column, *, copyable=False):
        card = ttk.Frame(parent, style="Panel.TFrame", padding=(8, 8))
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 6) if column == 0 else (6, 0))
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, textvariable=details_var, style="CardTitle.TLabel", foreground=TEXT_MUTED).pack(anchor="w", pady=(0, 6))
        shell = ttk.Frame(card, style="Panel.TFrame")
        shell.pack(fill="both", expand=True)
        canvas = tk.Canvas(shell, bg=CANVAS_BG, highlightthickness=0, bd=0, height=320)
        canvas.pack(fill="both", expand=True)
        canvas.bind("<Configure>", self._schedule_preview_refresh)
        copy_button = None
        if copyable:
            copy_button = tk.Button(
                shell,
                text="⧉",
                command=self.copy_result_image,
                bg=ACCENT,
                fg="#06111E",
                activebackground=ACCENT_HOVER,
                activeforeground="#06111E",
                relief="flat",
                bd=0,
                font=("Segoe UI", 14, "bold"),
                width=3,
                cursor="hand2",
                state="disabled",
            )
            copy_button.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor="se")
            copy_button.bind("<Enter>", lambda _e: self._hint_copy_button())
        return {"card": card, "canvas": canvas, "copy_button": copy_button}

    def _hint_copy_button(self):
        if self.processed_image is not None:
            self.status_var.set("Copy the result image (Ctrl+C)")

    def _show_dep_banner(self, message):
        self.dep_var.set(message)
        if not self.dep_banner.winfo_manager():
            self.dep_banner.pack(fill="x", pady=(0, 8), before=self.body)

    def _hide_dep_banner(self):
        self.dep_var.set("")
        if self.dep_banner.winfo_manager():
            self.dep_banner.pack_forget()

    def _warn_dependency_download(self, message):
        self._show_dep_banner(message)
        self._warned_download = True

    def _start_background_prepare(self):
        if self._prepare_thread is not None and self._prepare_thread.is_alive():
            return
        if not REMBG_AVAILABLE:
            self._warn_dependency_download("Warning: rembg is missing. Downloading this dependency now.")
            self._show_install_panel("Installing rembg", "Downloading rembg and onnxruntime...")
        elif not is_rembg_model_cached(DEFAULT_REMBG_MODEL):
            info = REMBG_MODEL_INFO[DEFAULT_REMBG_MODEL]
            self._warn_dependency_download(
                f"Warning: Classic model is missing (~{int(info['download_mb'])} MB). Downloading this dependency now."
            )
            self._show_download_panel(DEFAULT_REMBG_MODEL)
        else:
            self._update_model_hint(DEFAULT_REMBG_MODEL)
            self.status_var.set("Ready.")
            return
        try:
            self.master.update_idletasks()
        except TclError:
            pass
        self._prepare_thread = threading.Thread(target=self._background_prepare, daemon=True)
        self._prepare_thread.start()

    def _background_prepare(self):
        def status(message):
            self._run_on_ui_thread(lambda msg=message: self.status_var.set(msg))
            self._run_on_ui_thread(lambda msg=message: self.download_status_var.set(msg))

        if not REMBG_AVAILABLE:
            try:
                if install_missing_bg_remover_packages(logger=status):
                    status("rembg installed. Checking the default model...")
                    self._run_on_ui_thread(lambda: self._hide_download_panel("install"))
                else:
                    self._run_on_ui_thread(lambda: self._hide_download_panel("install"))
                    self._run_on_ui_thread(
                        lambda: self._show_dep_banner("rembg install failed. Install rembg and onnxruntime, then retry.")
                    )
                    return
            except Exception as exc:
                self._run_on_ui_thread(lambda: self._hide_download_panel("install"))
                self._run_on_ui_thread(lambda: self._show_dep_banner(f"Dependency install failed: {exc}"))
                status(str(exc))
                return

        if is_rembg_model_cached(DEFAULT_REMBG_MODEL):
            self._run_on_ui_thread(lambda: self._hide_download_panel("download"))
            self._run_on_ui_thread(self._hide_dep_banner)
            self._run_on_ui_thread(lambda: self._update_model_hint(DEFAULT_REMBG_MODEL))
            status("Ready.")
            return

        info = REMBG_MODEL_INFO[DEFAULT_REMBG_MODEL]
        self._run_on_ui_thread(
            lambda: (
                self._warn_dependency_download(
                    f"Warning: Classic model is missing (~{int(info['download_mb'])} MB). Downloading this dependency now."
                ),
                self._show_download_panel(DEFAULT_REMBG_MODEL),
            )
        )
        try:
            ensure_rembg_model_downloaded(DEFAULT_REMBG_MODEL, on_progress=self._make_download_progress_callback())
            self._run_on_ui_thread(lambda: self._hide_download_panel("download"))
            self._run_on_ui_thread(self._hide_dep_banner)
            self._run_on_ui_thread(lambda: self._update_model_hint(DEFAULT_REMBG_MODEL))
            status("Classic model downloaded. Ready.")
        except Exception as exc:
            self._run_on_ui_thread(lambda: self._hide_download_panel("download"))
            self._run_on_ui_thread(lambda: self._show_dep_banner(f"Model download failed: {exc}"))
            status(str(exc))

    def _start_worker_queue_polling(self):
        self._poll_worker_queue()

    def _poll_worker_queue(self):
        while True:
            try:
                callback = self._worker_queue.get_nowait()
            except queue.Empty:
                break
            try:
                callback()
            except Exception as exc:
                log(f"Background remover UI callback failed: {exc}")
        try:
            if self.master.winfo_exists():
                self._worker_poll_job = self.master.after(33, self._poll_worker_queue)
        except TclError:
            self._worker_poll_job = None

    def _run_on_ui_thread(self, callback):
        if threading.current_thread() is threading.main_thread():
            try:
                callback()
                return
            except TclError:
                return
        try:
            self.master.after(0, callback)
        except (TclError, RuntimeError):
            self._worker_queue.put(callback)

    def _stop_worker_queue_polling(self):
        job = self._worker_poll_job
        self._worker_poll_job = None
        if job is None:
            return
        try:
            self.master.after_cancel(job)
        except TclError:
            pass

    def _resolve_model_key(self, selection: str | None = None) -> str:
        return resolve_model_key(selection or self.model_var.get())

    def _sync_model_menu_to_key(self, model_key: str):
        label = REMBG_MODEL_MENU_LABELS.get(model_key, model_menu_label(model_key))
        self.model_var.set(label)

    def _update_model_hint(self, model_key: str):
        self.model_hint_var.set(describe_model_choice(model_key))

    def _notify_model_already_downloaded(self, model_key: str):
        if model_key in self._notified_installed_models:
            return
        if not is_rembg_model_cached(model_key):
            return
        self._notified_installed_models.add(model_key)
        self._update_model_hint(model_key)

    def _pack_download_panel(self):
        if not self.download_panel.winfo_manager():
            self.download_panel.pack(fill="x", pady=(0, 8), before=self.body)
        try:
            self.download_panel.lift()
            self.master.update_idletasks()
            self.download_progress._redraw()
        except TclError:
            pass

    def _begin_panel_job(self, holder: str = "download"):
        self._panel_holders.add(holder)
        self._pack_download_panel()
        self.upload_button.configure(state="disabled")
        self.paste_button.configure(state="disabled")
        self.model_menu.configure(state="disabled")
        self.delete_models_button.configure(state="disabled")

    def _start_file_watcher(self, model_key: str):
        self._stop_file_watcher()
        expected = int(REMBG_MODEL_INFO.get(model_key, {}).get("download_mb", 0)) * 1024 * 1024
        self._watch_model_key = model_key
        self._watch_stop = threading.Event()

        def watch():
            last_size = -1
            while not self._watch_stop.wait(0.25):
                size = growing_model_bytes(model_key)
                if size <= 0 or size == last_size:
                    continue
                last_size = size
                done_mb = size / (1024 * 1024)
                if expected > 0:
                    pct = min(99.0, 100.0 * size / expected)
                    message = f"Downloading… {done_mb:.1f} / {expected / (1024 * 1024):.0f} MB ({pct:.1f}%)"
                    self._run_on_ui_thread(lambda p=pct, m=message: self._update_download_panel(p, m))
                else:
                    message = f"Downloading… {done_mb:.1f} MB received"
                    self._run_on_ui_thread(lambda m=message: self._update_download_panel(None, m))

        self._watch_thread = threading.Thread(target=watch, daemon=True)
        self._watch_thread.start()

    def _stop_file_watcher(self):
        self._watch_stop.set()
        self._watch_thread = None
        self._watch_model_key = None

    def _show_download_panel(self, model_key: str):
        info = REMBG_MODEL_INFO.get(model_key, {})
        short = model_short_label(model_key)
        download_mb = int(info.get("download_mb", 0))
        self.download_title_var.set(f"Downloading {short} (~{download_mb} MB)")
        self.download_percent_var.set("0%")
        self.download_status_var.set("Connecting…")
        self._set_progress_mode(determinate=True)
        self.download_progress.set_value(0)
        self._begin_panel_job("download")
        self._start_file_watcher(model_key)

    def _show_install_panel(self, title: str, message: str):
        self.download_title_var.set(title)
        self.download_percent_var.set("…")
        self.download_status_var.set(message)
        self._set_progress_mode(determinate=False)
        self._begin_panel_job("install")

    def _set_progress_mode(self, *, determinate: bool):
        if determinate:
            self.download_progress.set_value(getattr(self.download_progress, "_value", 0.0))
        else:
            self.download_progress.start_indeterminate()

    def _hide_download_panel(self, holder: str | None = None):
        if holder:
            self._panel_holders.discard(holder)
        else:
            self._panel_holders.clear()
        if self._panel_holders:
            return
        self._stop_file_watcher()
        self.download_progress.stop()
        if self.download_panel.winfo_manager():
            self.download_panel.pack_forget()
        self.upload_button.configure(state="normal")
        self.paste_button.configure(state="normal")
        self.model_menu.configure(state="readonly")
        self.delete_models_button.configure(state="normal")

    def _update_download_panel(self, percent: float | None, message: str):
        self._pack_download_panel()
        self.download_status_var.set(message)
        self.status_var.set(f"Dependency download — {message}")
        if percent is None:
            self._set_progress_mode(determinate=False)
            self.download_percent_var.set("…")
        else:
            pct = max(0.0, min(100.0, percent))
            self.download_percent_var.set(f"{pct:.0f}%")
            self.download_progress.set_value(pct)

    def _set_processing_phase(self, model_label: str):
        self.download_title_var.set(f"Removing background — {model_label}")
        self.download_percent_var.set("…")
        self.download_status_var.set("Working…")
        self._set_progress_mode(determinate=False)
        self._begin_panel_job("process")

    def _make_download_progress_callback(self):
        def on_progress(percent: float | None, message: str):
            self._run_on_ui_thread(lambda: self._update_download_panel(percent, message))

        return on_progress

    def _premium_download_message(self, model_key: str) -> str:
        info = REMBG_MODEL_INFO[model_key]
        return (
            f"{info['short']} is an optional high-quality model.\n\n"
            f"Size: about {int(info['download_mb'])} MB\n"
            "This is a one-time dependency download.\n"
            "After that it runs offline.\n\n"
            "Download this model now?"
        )

    def _ensure_premium_download_allowed(self, model_key: str, *, confirm: bool = True) -> bool:
        if not is_premium_rembg_model(model_key):
            return True
        if is_rembg_model_cached(model_key):
            self._premium_download_approved.add(model_key)
            return True
        if model_key in self._premium_download_approved:
            return True
        if not confirm:
            return False
        approved = messagebox.askyesno(
            "Dependency download",
            self._premium_download_message(model_key),
            parent=self.master,
        )
        if approved:
            self._premium_download_approved.add(model_key)
            return True
        return False

    def _on_model_changed(self, selection: str):
        model_key = self._resolve_model_key(selection)
        if is_premium_rembg_model(model_key) and not self._ensure_premium_download_allowed(model_key):
            self._sync_model_menu_to_key(self._last_model_key)
            self._update_model_hint(self._last_model_key)
            self.status_var.set("Kept classic model — premium download cancelled.")
            return

        self._last_model_key = model_key
        self._sync_model_menu_to_key(model_key)
        self._update_model_hint(model_key)
        if is_rembg_model_cached(model_key):
            self._notify_model_already_downloaded(model_key)
            self.status_var.set(f"{model_short_label(model_key)} is already downloaded — ready.")
        elif is_premium_rembg_model(model_key):
            self.status_var.set(f"Selected {model_short_label(model_key)}. It will download when you open an image.")
        else:
            self.status_var.set(
                f"Selected {model_short_label(model_key)}. First use downloads ~{int(REMBG_MODEL_INFO[model_key]['download_mb'])} MB."
            )

    def _format_model_size(self, size_bytes: int) -> str:
        megabytes = size_bytes / (1024 * 1024)
        if megabytes >= 10:
            return f"{megabytes:.0f} MB"
        return f"{megabytes:.1f} MB"

    def _forget_deleted_model(self, model_key: str):
        self._premium_download_approved.discard(model_key)
        self._notified_installed_models.discard(model_key)

    def _refresh_after_model_delete(self):
        model_key = self._resolve_model_key()
        self._update_model_hint(model_key)
        if is_rembg_model_cached(model_key):
            self.status_var.set(f"{model_short_label(model_key)} is still downloaded.")
        else:
            self.status_var.set(f"{model_short_label(model_key)} was deleted. It will download again when you use it.")

    def open_delete_models_dialog(self):
        """Let the user delete one downloaded model or all of them."""
        downloaded = list_downloaded_rembg_models()
        if not downloaded:
            messagebox.showinfo(
                "Delete models",
                "No downloaded models were found on this PC.",
                parent=self.master,
            )
            return

        dialog = Toplevel(self.master)
        dialog.title("Delete models")
        dialog.configure(bg=PRIMARY_BG)
        dialog.transient(self.master)
        dialog.resizable(False, False)
        apply_window_icon(dialog, app_id="needyamin.media_downloader")

        outer = ttk.Frame(dialog, style="TFrame", padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Downloaded models", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Deleting a model frees disk space. It will download again the next time you use it.",
            style="Hint.TLabel",
            wraplength=420,
        ).pack(anchor="w", pady=(4, 8))

        list_shell = ttk.Frame(outer, style="Section.TFrame", padding=8)
        list_shell.pack(fill="both", expand=True)
        listbox = tk.Listbox(
            list_shell,
            height=min(8, max(4, len(downloaded))),
            bg=CANVAS_BG,
            fg=TEXT_MAIN,
            selectbackground=ACCENT,
            selectforeground="#06111E",
            relief="flat",
            highlightthickness=0,
            font=("Segoe UI", 9),
        )
        listbox.pack(fill="both", expand=True)

        def refresh_list():
            listbox.delete(0, tk.END)
            items = list_downloaded_rembg_models()
            if not items:
                listbox.insert(tk.END, "No downloaded models left")
                listbox.configure(state="disabled")
                return items
            listbox.configure(state="normal")
            for model_key, size in items:
                listbox.insert(tk.END, f"{model_short_label(model_key)}  —  {self._format_model_size(size)}")
            return items

        refresh_list()

        def selected_model_key():
            items = list_downloaded_rembg_models()
            selection = listbox.curselection()
            if not items or not selection:
                return None
            index = selection[0]
            if index >= len(items):
                return None
            return items[index][0]

        def delete_selected():
            model_key = selected_model_key()
            if not model_key:
                messagebox.showinfo("Delete models", "Select a model to delete.", parent=dialog)
                return
            size = downloaded_model_size_bytes(model_key)
            confirmed = messagebox.askyesno(
                "Delete model",
                f"Delete {model_short_label(model_key)} ({self._format_model_size(size)}) from this PC?",
                parent=dialog,
            )
            if not confirmed:
                return
            removed = delete_rembg_model(model_key)
            self._forget_deleted_model(model_key)
            self._refresh_after_model_delete()
            leftover = refresh_list()
            if removed:
                self.status_var.set(
                    f"Deleted {model_short_label(model_key)} ({self._format_model_size(removed)})."
                )
            if not leftover:
                dialog.destroy()

        def delete_all():
            items = list_downloaded_rembg_models()
            if not items:
                dialog.destroy()
                return
            total = sum(size for _key, size in items)
            confirmed = messagebox.askyesno(
                "Delete all models",
                f"Delete all {len(items)} downloaded model(s) ({self._format_model_size(total)})?",
                parent=dialog,
            )
            if not confirmed:
                return
            count, removed = delete_all_rembg_models()
            for model_key, _size in items:
                self._forget_deleted_model(model_key)
            self._refresh_after_model_delete()
            self.status_var.set(f"Deleted {count} model(s) ({self._format_model_size(removed)}).")
            dialog.destroy()

        actions = ttk.Frame(outer, style="TFrame")
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Delete selected", style="Danger.TButton", command=delete_selected).pack(side="left")
        ttk.Button(actions, text="Delete all", style="Danger.TButton", command=delete_all).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Close", style="Secondary.TButton", command=dialog.destroy).pack(side="right")

        dialog.update_idletasks()
        center_window(dialog, self.master)
        dialog.grab_set()
        dialog.focus_force()

    def _schedule_preview_refresh(self, _event=None):
        if self._redraw_job is not None:
            self.master.after_cancel(self._redraw_job)
        self._redraw_job = self.master.after(120, self._refresh_preview_panels)

    def _refresh_preview_panels(self):
        self._redraw_job = None
        if self.current_image is None:
            self._show_canvas_placeholder(self.original_canvas, "Open a photo", False)
        else:
            self.display_image(self.current_image, self.original_canvas, transparent=False)
        if self.processed_image is None:
            self._show_canvas_placeholder(self.removed_canvas, "Result", True)
        else:
            self.display_image(self.processed_image, self.removed_canvas, transparent=True)

    def _canvas_pixel_size(self, canvas):
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 1:
            width = 360
        if height <= 1:
            height = 320
        return width, height

    def _paint_canvas_background(self, canvas, transparent=False):
        width, height = self._canvas_pixel_size(canvas)
        if transparent:
            tile = 16
            for x in range(0, width, tile):
                for y in range(0, height, tile):
                    color = CHECKER_LIGHT if ((x // tile) + (y // tile)) % 2 else CHECKER_DARK
                    canvas.create_rectangle(x, y, x + tile, y + tile, fill=color, outline=color)
        else:
            canvas.create_rectangle(0, 0, width, height, fill=CANVAS_BG, outline=CANVAS_BG)

    def _show_canvas_placeholder(self, canvas, title, transparent=False):
        canvas.delete("all")
        self._paint_canvas_background(canvas, transparent=transparent)
        width = max(canvas.winfo_width(), 120)
        height = max(canvas.winfo_height(), 120)
        canvas.create_text(width / 2, height / 2, text=title, fill=TEXT_SOFT, font=("Segoe UI", 10))

    def _update_preview_details(self):
        if self.current_image is not None:
            source = Path(self.original_path).name if self.original_path else getattr(self, "_original_source_label", "Clipboard")
            self.original_details_var.set(f"{source}  {self.current_image.width}x{self.current_image.height}")
        else:
            self.original_details_var.set("Original")
        if self.processed_image is not None:
            self.processed_details_var.set(f"{self.processed_image.width}x{self.processed_image.height}  PNG")
        else:
            self.processed_details_var.set("Result")
        self._set_copy_result_enabled(self.processed_image is not None)

    def _set_copy_result_enabled(self, enabled: bool):
        button = getattr(self, "copy_result_button", None)
        if button is None:
            return
        button.configure(state="normal" if enabled else "disabled")

    def close_window(self):
        global background_remover_window
        self._stop_worker_queue_polling()
        self._stop_file_watcher()
        self._hide_download_panel()
        if background_remover_window is not None and self.master == background_remover_window:
            background_remover_window.destroy()
            background_remover_window = None
            return
        self.master.destroy()

    def clear_images(self):
        self.current_image = None
        self.processed_image = None
        self.original_path = None
        self.original_canvas.image = None
        self.removed_canvas.image = None
        self.save_button.configure(state="disabled")
        self.status_var.set("Open an image or press Ctrl+V to paste one")
        self._update_preview_details()
        self._refresh_preview_panels()

    def upload_image(self, event=None):
        file_path = filedialog.askopenfilename(
            parent=self.master,
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.webp")],
        )
        if file_path:
            self.process_image(file_path)

    def paste_clipboard_image(self, event=None):
        """Open uses the file picker; Ctrl+V / Paste uses the copied image."""
        if str(self.upload_button.cget("state")) == "disabled":
            return "break"
        image = grab_clipboard_image()
        if image is None:
            self.status_var.set("Clipboard has no image. Copy a picture, then press Ctrl+V.")
            return "break"
        self.process_loaded_image(image, source_label="Clipboard")
        return "break"

    def copy_result_image(self, event=None):
        if self.processed_image is None:
            self.status_var.set("No result to copy yet.")
            return "break"
        try:
            copy_image_to_clipboard(self.processed_image)
            self.status_var.set("Result image copied. Paste it with Ctrl+V in another app.")
        except Exception as exc:
            showerror("Copy", f"Could not copy the result image:\n{exc}", parent=self.master)
        return "break"

    def process_loaded_image(self, image: Image.Image, source_label: str = "Clipboard"):
        loaded = image.copy()
        self.original_path = None
        self._original_source_label = source_label
        self._start_processing(loaded)

    def process_image(self, file_path):
        self.original_path = file_path
        self._original_source_label = Path(file_path).name
        try:
            original = Image.open(file_path)
            original.load()
        except Exception as exc:
            self._handle_processing_error(str(exc))
            return
        self._start_processing(original)

    def _start_processing(self, original: Image.Image):
        model_name = self._resolve_model_key()
        if not REMBG_AVAILABLE:
            self._start_background_prepare()
            messagebox.showwarning(
                "Dependency download",
                "rembg is still being installed. Wait until the warning clears, then open the image again.",
                parent=self.master,
            )
            return
        if not self._ensure_premium_download_allowed(model_name):
            self.status_var.set("Cancelled — premium model not downloaded.")
            return

        alpha_matting = bool(self.refine_edges_var.get())
        model_label = model_short_label(model_name)
        model_cached = is_rembg_model_cached(model_name)
        allow_download = not is_premium_rembg_model(model_name) or model_name in self._premium_download_approved

        if model_cached:
            self.status_var.set(f"Using {model_label}…")
            self._set_processing_phase(model_label)
        else:
            self._show_dep_banner(
                f"Warning: {model_label} is missing (~{int(REMBG_MODEL_INFO[model_name]['download_mb'])} MB). Downloading this dependency."
            )
            self.status_var.set(f"Downloading {model_label}…")
            self._show_download_panel(model_name)

        source_image = original.copy()

        def process():
            try:
                progress_cb = self._make_download_progress_callback()
                output = remove_image_background(
                    source_image,
                    model_name=model_name,
                    alpha_matting=alpha_matting,
                    allow_model_download=allow_download,
                    on_download_progress=progress_cb,
                )
                self._run_on_ui_thread(lambda: self._finish_processing(source_image, output))
            except Exception as exc:
                error_message = str(exc)
                self._run_on_ui_thread(lambda: self._handle_processing_error(error_message))
            finally:
                def cleanup():
                    self._hide_download_panel("process")
                    prepare = self._prepare_thread
                    if prepare is None or not prepare.is_alive():
                        self._hide_download_panel("download")
                        self._hide_dep_banner()

                self._run_on_ui_thread(cleanup)

        threading.Thread(target=process, daemon=True).start()

    def _finish_processing(self, original, output):
        self.current_image = original
        self.processed_image = output
        self._update_preview_details()
        self._refresh_preview_panels()
        self.status_var.set("Done. Click ⧉ on the result to copy, or save the PNG.")
        self.save_button.configure(state="normal")
        self._set_copy_result_enabled(True)

    def _handle_processing_error(self, error_message):
        self.status_var.set(f"Error: {error_message}")
        showerror("Error", f"Failed to process image: {error_message}", parent=self.master)

    def save_processed_image(self, event=None):
        if self.processed_image is None:
            showerror("Error", "No processed image to save.", parent=self.master)
            return
        save_path = filedialog.asksaveasfilename(
            parent=self.master,
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")],
            initialfile="background_removed.png",
        )
        if not save_path:
            return
        try:
            self.processed_image.save(save_path, "PNG")
            showinfo("Saved", "Image saved.", parent=self.master)
            self.status_var.set(f"Saved {Path(save_path).name}")
        except Exception as exc:
            showerror("Error", f"Failed to save image: {exc}", parent=self.master)

    def _compose_on_checkerboard(self, image: Image.Image) -> Image.Image:
        if image.mode != "RGBA":
            return image.convert("RGB")
        width, height = image.size
        background = Image.new("RGB", (width, height), CHECKER_DARK)
        tile = 14
        draw = ImageDraw.Draw(background)
        for x in range(0, width, tile):
            for y in range(0, height, tile):
                color = CHECKER_LIGHT if ((x // tile) + (y // tile)) % 2 else CHECKER_DARK
                draw.rectangle((x, y, min(x + tile, width), min(y + tile, height)), fill=color)
        background.paste(image, mask=image.split()[3])
        return background

    def display_image(self, image, canvas, maintain_aspect=True, transparent=False):
        canvas.update_idletasks()
        canvas_width = max(canvas.winfo_width(), 160)
        canvas_height = max(canvas.winfo_height(), 160)
        padding = 12
        available_width = max(canvas_width - padding * 2, 1)
        available_height = max(canvas_height - padding * 2, 1)
        if maintain_aspect:
            scale = min(available_width / image.width, available_height / image.height)
            new_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        else:
            new_size = (available_width, available_height)
        resized = image.resize(new_size, Image.Resampling.LANCZOS)
        if transparent and resized.mode == "RGBA":
            resized = self._compose_on_checkerboard(resized)
        elif resized.mode not in ("RGB", "L"):
            resized = resized.convert("RGB")
        photo = ImageTk.PhotoImage(resized)
        canvas.delete("all")
        self._paint_canvas_background(canvas, transparent=transparent)
        canvas.image = photo
        canvas.create_image(canvas_width / 2, canvas_height / 2, image=photo)


def ensure_background_remover_dependencies(parent=None):
    """Allow the window to open; source runs install rembg inside the UI with a progress bar."""
    if REMBG_AVAILABLE or try_load_rembg():
        return True

    if not is_packaged_runtime():
        return True

    missing_list = ", ".join(MISSING_DEPENDENCIES) or "rembg"
    details = "\n".join(f"- {name}: {error}" for name, error in DEPENDENCY_ERRORS.items())
    nested = collect_dependency_diagnostics()
    report = "\n\n".join(part for part in (details, nested) if part)
    path = write_dependency_diagnostics_report(report) if report else None
    hint = (
        "The packaged background remover could not load rembg.\n\n"
        f"Failed import: {missing_list}"
    )
    if report:
        hint += f"\n\n{report}"
    if path is not None:
        hint += f"\n\nDiagnostic report:\n{path}"
    if parent is None:
        show_startup_error("Missing Dependencies", hint)
    else:
        messagebox.showerror("Missing Dependencies", hint, parent=parent)
    return False


def open_background_remover(parent=None):
    """Open the background remover in its own window."""
    global background_remover_window

    if not ensure_background_remover_dependencies(parent):
        return None

    if parent is None:
        root = Tk()
        BackgroundRemoverApp(root)
        root.mainloop()
        return root

    if background_remover_window is not None and background_remover_window.winfo_exists():
        background_remover_window.deiconify()
        center_window(background_remover_window, parent)
        background_remover_window.lift()
        background_remover_window.focus_force()
        return background_remover_window

    background_remover_window = Toplevel(parent)
    apply_window_icon(background_remover_window, app_id="needyamin.media_downloader")
    BackgroundRemoverApp(background_remover_window)

    def _close_window():
        global background_remover_window
        if background_remover_window is not None and background_remover_window.winfo_exists():
            background_remover_window.destroy()
        background_remover_window = None

    background_remover_window.protocol("WM_DELETE_WINDOW", _close_window)
    background_remover_window.transient(parent)
    background_remover_window.after_idle(lambda: center_window(background_remover_window, parent))
    background_remover_window.lift()
    background_remover_window.focus_force()
    return background_remover_window


def force_close_background_remover_if_open() -> None:
    """Close the background remover without prompting (hub shutdown)."""
    global background_remover_window
    window = background_remover_window
    if window is None:
        return
    try:
        if window.winfo_exists():
            window.destroy()
    except Exception:
        pass
    background_remover_window = None


if __name__ == "__main__":
    open_background_remover()
