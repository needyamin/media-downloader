import hashlib
import os
import queue
import threading
import tkinter as tk
from tkinter import Tk, filedialog, ttk, StringVar, TclError, messagebox, Menu, Toplevel
from tkinter.messagebox import showinfo, showerror
import importlib
from PIL import Image, ImageDraw, ImageTk
import requests
import tempfile
import sys
import subprocess
from pathlib import Path
import time
import traceback

try:
    from desktop_tools.app.app_windowing import ensure_src_on_path
except Exception:
    from app_windowing import ensure_src_on_path

APP_DIR = Path(__file__).resolve().parent
SRC_DIR = ensure_src_on_path(__file__)

from desktop_tools.shared.resources import apply_window_icon, center_window
from desktop_tools.shared.user_data_paths import get_bg_remover_diagnostics_path, get_rembg_models_dir
from desktop_tools.app.config.runtime_flags import APP_VERSION_BG_REMOVER, get_tool_theme

MISSING_DEPENDENCIES = []
DEPENDENCY_ERRORS = {}
IS_WINDOWS = os.name == "nt"
DEPENDENCY_DIAGNOSTICS_REPORT = None


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

try:
    import customtkinter as ctk
except BaseException as exc:
    ctk = None
    register_dependency_error("customtkinter", exc)

# Constants for version checking
CURRENT_VERSION = APP_VERSION_BG_REMOVER
GITHUB_API_URL = "https://api.github.com/repos/needyamin/img-background-remover/releases/latest"
REPO_OWNER = "needyamin"
REPO_NAME = "img-background-remover"
APP_ID = "mycompany.backgroundremover.1.0"
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
    override = os.environ.get("U2NET_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    return get_rembg_models_dir()


def is_rembg_model_cached(model_name: str) -> bool:
    """Return True when the ONNX file for this model is already on disk."""
    if model_name not in REMBG_MODEL_INFO:
        return False
    model_path = get_rembg_cache_dir() / f"{model_name}.onnx"
    return model_path.is_file() and model_path.stat().st_size > 0


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
        path = get_rembg_cache_dir() / f"{model_name}.onnx"
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
    path = get_rembg_cache_dir() / f"{model_name}.onnx"
    size_mb = path.stat().st_size / (1024 * 1024)
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

    return get_rembg_cache_dir() / f"{model_name}.onnx"


def ensure_rembg_model_downloaded(
    model_name: str,
    on_progress=None,
) -> Path:
    """
    Download rembg ONNX weights if missing. Calls on_progress(percent, message)
    where percent may be None when total size is unknown.
    """
    model_path = get_rembg_cache_dir() / f"{model_name}.onnx"
    if model_path.is_file() and model_path.stat().st_size > 0:
        reporter = _throttled_progress(on_progress)
        if reporter:
            reporter(100.0, "Model already on this PC — skipping download.", force=True)
        return model_path

    if not REMBG_AVAILABLE:
        raise RuntimeError("rembg is not available")

    spec = REMBG_MODEL_DOWNLOADS.get(model_name)
    if spec and spec.get("url"):
        _download_url_to_file(str(spec["url"]), model_path, on_progress=on_progress)
        _verify_model_file_hash(model_path, spec.get("hash"), on_progress=on_progress)
    else:
        model_path = _download_via_rembg_pooch(model_name, on_progress=on_progress)

    if not model_path.is_file():
        raise RuntimeError(f"Download finished but model file is missing: {model_path}")

    reporter = _throttled_progress(on_progress)
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
        session = new_session(model_name)
        _REMBG_SESSION_CACHE[model_name] = session
        return session


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

    raise RuntimeError(f"Background removal failed: {last_error}")


def log(message):
    """Simple logging function"""
    print(f"[LOG] {message}")

def compare_versions(version1, version2):
    """Compare two version strings. Returns True if version1 > version2"""
    def normalize(v):
        return [int(x) for x in v.split(".")]
    try:
        return normalize(version1) > normalize(version2)
    except (AttributeError, TypeError, ValueError):
        return False

def get_base_path():
    """Return the app base path for source and PyInstaller builds."""
    if getattr(sys, "_MEIPASS", None):
        return sys._MEIPASS
    return str(Path(__file__).resolve().parents[1])

def is_packaged_runtime():
    """Return True when running from a packaged executable instead of source."""
    executable_name = Path(sys.executable).name.lower()
    return (
        bool(getattr(sys, "frozen", False))
        or globals().get("__compiled__") is not None
    ) and executable_name not in {"python.exe", "pythonw.exe"}

def get_asset_path(*parts):
    return os.path.join(get_base_path(), "assets", *parts)

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
        ("customtkinter", "customtkinter", ()),
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

class BackgroundRemoverApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Background Remover Studio")
        self.master.geometry("1240x860")
        self.master.minsize(980, 720)
        self.master.configure(bg=PRIMARY_BG)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.style = ttk.Style(self.master)
        self._configure_style()

        # Create Menu Bar
        self.create_menu_bar()
        self._configure_window_icon()

        # Add keyboard shortcuts
        self.master.bind('<Control-o>', lambda e: self.upload_image())
        self.master.bind('<Control-s>', lambda e: self.save_processed_image())

        # Initialize variables
        self.current_image = None
        self.processed_image = None
        self.original_path = None
        self._redraw_job = None
        self.status_var = StringVar(value="Ready to process an image")
        self.original_details_var = StringVar(
            value="Upload a photo to preview the original composition."
        )
        self.processed_details_var = StringVar(
            value="The cutout result will appear here with a transparent preview."
        )
        self.model_var = StringVar(value=REMBG_MODEL_MENU_LABELS[DEFAULT_REMBG_MODEL])
        self.model_hint_var = StringVar(value=describe_model_choice(DEFAULT_REMBG_MODEL))
        self.refine_edges_var = tk.BooleanVar(value=True)
        self._last_model_key = DEFAULT_REMBG_MODEL
        self._premium_download_approved: set[str] = {
            key for key in PREMIUM_REMBG_MODELS if is_rembg_model_cached(key)
        }
        self._notified_installed_models: set[str] = set()
        self._worker_queue: queue.Queue = queue.Queue()
        self._worker_poll_job = None

        self._build_ui()
        self._refresh_preview_panels()
        self._start_worker_queue_polling()

        self.master.after_idle(lambda: center_window(self.master, self.master.master if isinstance(self.master, Toplevel) else None))

    def _configure_style(self):
        try:
            self.style.theme_use("clam")
        except TclError:
            pass

        self.style.configure(
            "Modern.Horizontal.TProgressbar",
            troughcolor=CANVAS_BG,
            background=ACCENT,
            bordercolor=CANVAS_BG,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
            thickness=8,
        )

    def _button_palette(self, variant):
        palettes = {
            "primary": {
                "fg_color": ACCENT,
                "hover_color": ACCENT_HOVER,
                "border_color": ACCENT_HOVER,
                "text_color": "#06111E",
                "text_color_disabled": TEXT_SOFT,
                "border_width": 0,
            },
            "success": {
                "fg_color": SUCCESS,
                "hover_color": SUCCESS_HOVER,
                "border_color": SUCCESS_HOVER,
                "text_color": "#F8FFF9",
                "text_color_disabled": TEXT_SOFT,
                "border_width": 0,
            },
            "secondary": {
                "fg_color": SECONDARY_BUTTON,
                "hover_color": SECONDARY_BUTTON_HOVER,
                "border_color": SECONDARY_BUTTON_BORDER,
                "text_color": TEXT_MAIN,
                "text_color_disabled": TEXT_SOFT,
                "border_width": 1,
            },
            "danger-soft": {
                "fg_color": SECONDARY_BUTTON,
                "hover_color": "#2B2130",
                "border_color": "#6B2F43",
                "text_color": DANGER_TEXT,
                "text_color_disabled": TEXT_SOFT,
                "border_width": 1,
            },
        }
        return palettes[variant]

    def _create_action_button(self, parent, text, command, variant, width):
        palette = self._button_palette(variant)
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=44,
            corner_radius=14,
            fg_color=palette["fg_color"],
            hover_color=palette["hover_color"],
            border_color=palette["border_color"],
            border_width=palette["border_width"],
            text_color=palette["text_color"],
            text_color_disabled=palette["text_color_disabled"],
            font=("Segoe UI", 13, "bold"),
        )

    def _create_toolbar_chip(self, parent, text):
        chip = ctk.CTkFrame(
            parent,
            fg_color=SECONDARY_BUTTON,
            corner_radius=999,
            border_width=1,
            border_color=SECONDARY_BUTTON_BORDER,
        )
        chip.pack(side='left', padx=(0, 8))
        ctk.CTkLabel(
            chip,
            text=text,
            text_color=TEXT_MUTED,
            font=("Segoe UI", 10, "bold"),
        ).pack(padx=12, pady=6)
        return chip

    def _set_save_button_enabled(self, enabled):
        variant = "success" if enabled else "secondary"
        palette = self._button_palette(variant)
        self.save_button.configure(
            state='normal' if enabled else 'disabled',
            fg_color=palette["fg_color"],
            hover_color=palette["hover_color"],
            border_color=palette["border_color"],
            border_width=palette["border_width"],
            text_color=palette["text_color"],
            text_color_disabled=palette["text_color_disabled"],
        )

    def _build_ui(self):
        self.main_frame = ctk.CTkFrame(self.master, fg_color=PRIMARY_BG, corner_radius=0)
        self.main_frame.pack(fill='both', expand=True, padx=24, pady=24)

        self.header_card = ctk.CTkFrame(
            self.main_frame,
            fg_color=SURFACE_BG,
            corner_radius=24,
            border_width=1,
            border_color=CARD_BORDER,
        )
        self.header_card.pack(fill='x')
        self.header_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.header_card,
            text="Background Remover Studio",
            text_color=TEXT_MAIN,
            font=("Segoe UI", 26, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(20, 4))

        ctk.CTkLabel(
            self.header_card,
            text=(
                "Classic rembg models work out of the box (small first-time download). "
                "BiRefNet / BRIA are optional best-quality models — large download only if you pick them."
            ),
            text_color=TEXT_SOFT,
            font=("Segoe UI", 11),
            wraplength=920,
            justify="left",
        ).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 16))

        self.toolbar_card = ctk.CTkFrame(
            self.main_frame,
            fg_color=SURFACE_BG,
            corner_radius=22,
            border_width=1,
            border_color=CARD_BORDER,
        )
        self.toolbar_card.pack(fill='x', pady=(18, 18))

        self.toolbar_row = ctk.CTkFrame(self.toolbar_card, fg_color="transparent")
        self.toolbar_row.pack(fill='x', padx=20, pady=(18, 10))

        self.action_buttons = ctk.CTkFrame(self.toolbar_row, fg_color="transparent")
        self.action_buttons.pack(side='left')

        self.upload_button = self._create_action_button(
            self.action_buttons,
            text="Choose Image",
            command=self.upload_image,
            variant="primary",
            width=150,
        )
        self.upload_button.pack(side='left', padx=(0, 12))

        self.save_button = self._create_action_button(
            self.action_buttons,
            text="Save PNG",
            command=self.save_processed_image,
            variant="success",
            width=130,
        )
        self.save_button.pack(side='left', padx=(0, 12))

        self.clear_button = self._create_action_button(
            self.action_buttons,
            text="Reset Workspace",
            command=self.clear_images,
            variant="danger-soft",
            width=146,
        )
        self.clear_button.pack(side='left')

        self.settings_row = ctk.CTkFrame(self.toolbar_card, fg_color="transparent")
        self.settings_row.pack(fill='x', padx=20, pady=(0, 6))

        ctk.CTkLabel(
            self.settings_row,
            text="AI model",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 11, "bold"),
        ).pack(side='left', padx=(0, 10))

        self.model_menu = ctk.CTkOptionMenu(
            self.settings_row,
            variable=self.model_var,
            values=[REMBG_MODEL_MENU_LABELS[key] for key in REMBG_MODEL_MENU_ORDER],
            width=340,
            height=34,
            corner_radius=12,
            fg_color=SECONDARY_BUTTON,
            button_color=ACCENT,
            button_hover_color=ACCENT_HOVER,
            dropdown_fg_color=SURFACE_BG,
            dropdown_hover_color=SECONDARY_BUTTON_HOVER,
            text_color=TEXT_MAIN,
            font=("Segoe UI", 11),
            command=self._on_model_changed,
        )
        self.model_menu.pack(side='left', padx=(0, 14))
        self._sync_model_menu_to_key(DEFAULT_REMBG_MODEL)
        self._update_model_hint(DEFAULT_REMBG_MODEL)

        self.refine_switch = ctk.CTkSwitch(
            self.settings_row,
            text="Refine edges (hair & fine detail)",
            variable=self.refine_edges_var,
            onvalue=True,
            offvalue=False,
            font=("Segoe UI", 11),
            text_color=TEXT_MAIN,
            progress_color=ACCENT,
            button_color=ACCENT,
            button_hover_color=ACCENT_HOVER,
        )
        self.refine_switch.pack(side='left', padx=(0, 12))

        self._create_toolbar_chip(
            self.settings_row,
            "Classic default · premium optional",
        )

        self.model_hint_label = ctk.CTkLabel(
            self.toolbar_card,
            textvariable=self.model_hint_var,
            text_color=TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=1100,
            font=("Segoe UI", 11),
        )
        self.model_hint_label.pack(fill='x', padx=22, pady=(0, 6))

        self.download_panel = ctk.CTkFrame(
            self.toolbar_card,
            fg_color=HEADER_BADGE_BG,
            corner_radius=14,
            border_width=2,
            border_color=ACCENT,
        )
        self.download_title_var = StringVar(value="Downloading AI model")
        self.download_percent_var = StringVar(value="0%")
        self.download_status_var = StringVar(value="Preparing download…")

        download_inner = ctk.CTkFrame(self.download_panel, fg_color="transparent")
        download_inner.pack(fill="x", padx=18, pady=16)

        header_row = ctk.CTkFrame(download_inner, fg_color="transparent")
        header_row.pack(fill="x")

        ctk.CTkLabel(
            header_row,
            textvariable=self.download_title_var,
            text_color=TEXT_MAIN,
            font=("Segoe UI", 15, "bold"),
        ).pack(side="left")

        ctk.CTkLabel(
            header_row,
            textvariable=self.download_percent_var,
            text_color=ACCENT,
            font=("Segoe UI", 22, "bold"),
        ).pack(side="right")

        self.download_progress = ctk.CTkProgressBar(
            download_inner,
            height=22,
            corner_radius=10,
            progress_color=ACCENT,
            fg_color=CANVAS_BG,
        )
        self.download_progress.pack(fill="x", pady=(12, 8))
        self.download_progress.set(0)

        ctk.CTkLabel(
            download_inner,
            textvariable=self.download_status_var,
            text_color=TEXT_MUTED,
            font=("Segoe UI", 11),
            anchor="w",
            justify="left",
        ).pack(fill="x")

        self.progress_bar = ttk.Progressbar(
            self.toolbar_row,
            mode='indeterminate',
            length=220,
            style="Modern.Horizontal.TProgressbar",
        )
        self.progress_bar.pack(side='right', padx=(12, 0), pady=8)

        self.status_label = ctk.CTkLabel(
            self.toolbar_card,
            textvariable=self.status_var,
            text_color=TEXT_MAIN,
            anchor="w",
            justify="left",
            font=("Segoe UI", 12, "bold"),
        )
        self.status_label.pack(fill='x', padx=22, pady=(0, 14))
        self._set_save_button_enabled(False)

        self.image_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.image_frame.pack(fill='both', expand=True)
        self.image_frame.grid_columnconfigure(0, weight=1)
        self.image_frame.grid_columnconfigure(1, weight=1)
        self.image_frame.grid_rowconfigure(0, weight=1)

        self.original_card = self._create_preview_card(
            self.image_frame,
            title="Original Image",
            details_var=self.original_details_var,
            column=0,
        )
        self.original_canvas = self.original_card["canvas"]

        self.processed_card = self._create_preview_card(
            self.image_frame,
            title="Background Removed",
            details_var=self.processed_details_var,
            column=1,
        )
        self.removed_canvas = self.processed_card["canvas"]

        self.footer_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent", height=8)
        self.footer_frame.pack(fill='x', pady=(10, 0))

    def _create_preview_card(self, parent, title, details_var, column):
        card = ctk.CTkFrame(
            parent,
            fg_color=CARD_BG,
            corner_radius=22,
            border_width=1,
            border_color=CARD_BORDER,
        )

        horizontal_pad = (0, 10) if column == 0 else (10, 0)
        card.grid(row=0, column=column, sticky="nsew", padx=horizontal_pad)

        ctk.CTkLabel(
            card,
            text=title,
            text_color=TEXT_MAIN,
            font=("Segoe UI", 18, "bold"),
            anchor="w",
        ).pack(fill='x', padx=20, pady=(18, 4))

        ctk.CTkLabel(
            card,
            textvariable=details_var,
            text_color=TEXT_MUTED,
            font=("Segoe UI", 11),
            justify="left",
            anchor="w",
        ).pack(fill='x', padx=20, pady=(0, 14))

        canvas_shell = ctk.CTkFrame(
            card,
            fg_color=CANVAS_BG,
            corner_radius=18,
            border_width=1,
            border_color=CARD_BORDER,
        )
        canvas_shell.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        canvas = tk.Canvas(
            canvas_shell,
            bg=CANVAS_BG,
            highlightthickness=0,
            bd=0,
            relief='flat',
        )
        canvas.pack(fill='both', expand=True, padx=1, pady=1)
        canvas.bind("<Configure>", self._schedule_preview_refresh)

        return {"card": card, "canvas": canvas}

    def _start_worker_queue_polling(self):
        """Poll worker callbacks on the Tk main thread (required on Python 3.14+)."""
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
                self._worker_poll_job = self.master.after(100, self._poll_worker_queue)
        except TclError:
            self._worker_poll_job = None

    def _run_on_ui_thread(self, callback):
        """Schedule UI work from a background thread without calling Tkinter off-thread."""
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
        """Update hint once per session when the user picks an already-local model."""
        if model_key in self._notified_installed_models:
            return
        if not is_rembg_model_cached(model_key):
            return
        self._notified_installed_models.add(model_key)
        self._update_model_hint(model_key)

    def _show_download_panel(self, model_key: str):
        """Show the large in-window download progress bar (always visible in this tool)."""
        info = REMBG_MODEL_INFO.get(model_key, {})
        short = model_short_label(model_key)
        download_mb = int(info.get("download_mb", 0))
        self.download_title_var.set(f"Downloading {short} (~{download_mb} MB)")
        self.download_percent_var.set("0%")
        self.download_status_var.set("Connecting to GitHub…")
        self.download_progress.set(0)
        self.download_panel.pack(fill="x", padx=22, pady=(4, 10), before=self.status_label)
        self.upload_button.configure(state="disabled")
        self.model_menu.configure(state="disabled")
        self.master.update_idletasks()

    def _hide_download_panel(self):
        self.download_panel.pack_forget()
        self.upload_button.configure(state="normal")
        self.model_menu.configure(state="normal")

    def _update_download_panel(self, percent: float | None, message: str):
        self.download_status_var.set(message)
        self.status_var.set(f"Download in progress — {message}")
        if percent is None:
            self.download_percent_var.set("…")
            self.download_progress.set(0.08)
        else:
            pct = max(0.0, min(100.0, percent))
            self.download_percent_var.set(f"{pct:.1f}%")
            self.download_progress.set(pct / 100.0)
        try:
            self.master.update_idletasks()
        except TclError:
            pass

    def _set_processing_phase(self, model_label: str):
        """Reuse the same panel while the image is being cut out (after download)."""
        self.download_title_var.set(f"Removing background — {model_label}")
        self.download_percent_var.set("")
        self.download_status_var.set("Running AI on your image…")
        self.download_progress.set(0)
        if not self.download_panel.winfo_ismapped():
            self.download_panel.pack(fill="x", padx=22, pady=(4, 10), before=self.status_label)

    def _make_download_progress_callback(self):
        def on_progress(percent: float | None, message: str):
            self._run_on_ui_thread(lambda: self._update_download_panel(percent, message))

        return on_progress

    def _premium_download_message(self, model_key: str) -> str:
        info = REMBG_MODEL_INFO[model_key]
        return (
            f"{info['short']} is an optional high-quality model.\n\n"
            f"Size: about {int(info['download_mb'])} MB\n"
            f"Source: downloaded once from the internet (GitHub / rembg releases)\n"
            f"After that it runs fully offline.\n\n"
            "Download this model now?"
        )

    def _ensure_premium_download_allowed(self, model_key: str, *, confirm: bool = True) -> bool:
        """Return True when a premium model may be loaded (cached or user approved)."""
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
            "Download optional AI model?",
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
            self.status_var.set(
                f"{model_short_label(model_key)} is already downloaded — ready to use."
            )
        elif is_premium_rembg_model(model_key):
            self.status_var.set(
                f"Selected {model_short_label(model_key)}. "
                "A download progress bar will appear in this window when you choose an image."
            )
        else:
            self.status_var.set(
                f"Selected {model_short_label(model_key)}. "
                "First use shows the download bar below (~{0} MB).".format(
                    int(REMBG_MODEL_INFO[model_key]["download_mb"])
                )
            )

    def _schedule_preview_refresh(self, _event=None):
        if self._redraw_job is not None:
            self.master.after_cancel(self._redraw_job)
        self._redraw_job = self.master.after(120, self._refresh_preview_panels)

    def _refresh_preview_panels(self):
        self._redraw_job = None

        if self.current_image is None:
            self._show_canvas_placeholder(
                self.original_canvas,
                title="Drop in a photo",
                subtitle="Your original image will appear here with a large fit-to-view preview.",
                transparent=False,
            )
        else:
            self.display_image(self.current_image, self.original_canvas, maintain_aspect=True, transparent=False)

        if self.processed_image is None:
            self._show_canvas_placeholder(
                self.removed_canvas,
                title="Transparent result",
                subtitle="Once processed, the cutout preview will be shown on a checkerboard background.",
                transparent=True,
            )
        else:
            self.display_image(self.processed_image, self.removed_canvas, maintain_aspect=True, transparent=True)

    def _paint_canvas_background(self, canvas, transparent=False):
        width = max(canvas.winfo_width(), int(canvas.cget("width")) or 1)
        height = max(canvas.winfo_height(), int(canvas.cget("height")) or 1)

        if transparent:
            tile = 18
            for x in range(0, width, tile):
                for y in range(0, height, tile):
                    color = CHECKER_LIGHT if ((x // tile) + (y // tile)) % 2 else CHECKER_DARK
                    canvas.create_rectangle(
                        x,
                        y,
                        x + tile,
                        y + tile,
                        fill=color,
                        outline=color,
                        tags="background",
                    )
        else:
            canvas.create_rectangle(
                0,
                0,
                width,
                height,
                fill=CANVAS_BG,
                outline=CANVAS_BG,
                tags="background",
            )

    def _show_canvas_placeholder(self, canvas, title, subtitle, transparent=False):
        canvas.delete("all")
        self._paint_canvas_background(canvas, transparent=transparent)

        width = max(canvas.winfo_width(), 320)
        height = max(canvas.winfo_height(), 320)
        inset = max(min(width, height) * 0.08, 24)

        canvas.create_rectangle(
            inset,
            inset,
            width - inset,
            height - inset,
            outline=CARD_BORDER,
            width=1,
            dash=(7, 8),
            tags="foreground",
        )
        canvas.create_text(
            width / 2,
            height / 2 - 16,
            text=title,
            fill=TEXT_MAIN,
            font=("Segoe UI", 18, "bold"),
            tags="foreground",
        )
        canvas.create_text(
            width / 2,
            height / 2 + 22,
            text=subtitle,
            fill=TEXT_SOFT,
            width=max(width - 140, 180),
            justify="center",
            font=("Segoe UI", 10),
            tags="foreground",
        )

    def _update_preview_details(self):
        if self.current_image is not None and self.original_path:
            self.original_details_var.set(
                f"{Path(self.original_path).name}  •  {self.current_image.width} x {self.current_image.height}"
            )
        else:
            self.original_details_var.set(
                "Upload a photo to preview the original composition."
            )

        if self.processed_image is not None:
            model_label = model_short_label(self._resolve_model_key())
            refine = "refined edges" if self.refine_edges_var.get() else "standard edges"
            self.processed_details_var.set(
                f"Transparent PNG  •  {self.processed_image.width} x {self.processed_image.height}"
                f"  •  {model_label}  •  {refine}"
            )
        else:
            self.processed_details_var.set(
                "The cutout result will appear here with a transparent preview."
            )

    def _configure_window_icon(self):
        """Apply the shared Media Downloader icon."""
        try:
            apply_window_icon(self.master, app_id="needyamin.media_downloader")
        except Exception as e:
            log(f"Could not load application icon: {e}")

    # Add method to open URLs
    def open_url(self, url):
        import webbrowser
        webbrowser.open(url)

    def open_link(self, url):
        """Open the given URL in the default web browser"""
        import webbrowser
        webbrowser.open(url)

    def create_menu_bar(self):
        """Create the main menu bar"""
        menubar = Menu(self.master)
        self.master.config(menu=menubar)

        # File Menu
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Image", command=self.upload_image, accelerator="Ctrl+O")
        file_menu.add_command(label="Save Image", command=self.save_processed_image, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close_window)

        # Edit Menu
        edit_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Clear Images", command=self.clear_images)

        # Help Menu
        help_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Check for Updates", command=self.check_for_updates)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.show_about)

    def close_window(self):
        """Close only this tool window."""
        global background_remover_window

        self._stop_worker_queue_polling()
        self._hide_download_panel()

        if background_remover_window is not None and self.master == background_remover_window:
            background_remover_window.destroy()
            background_remover_window = None
            return

        self.master.destroy()

    def clear_images(self):
        """Clear both canvases"""
        self.current_image = None
        self.processed_image = None
        self.original_path = None
        self.original_canvas.image = None
        self.removed_canvas.image = None
        self._set_save_button_enabled(False)
        self.status_var.set("Ready to process an image")
        self._update_preview_details()
        self._refresh_preview_panels()

    def show_about(self):
        """Show about dialog"""
        about_text = f"""Background Remover Studio v{CURRENT_VERSION}

Created by Md. Yamin Hossain

This application removes backgrounds locally with rembg.

Classic u2net models are the default. BiRefNet and BRIA are
optional premium models — they download from the internet only
if you select them and confirm. Edge refinement helps hair and
fine detail on any model.

© 2025 All rights reserved."""
        messagebox.showinfo("About", about_text)

    def upload_image(self, event=None):
        file_path = filedialog.askopenfilename(
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.webp")]
        )
        if file_path:
            self.process_image(file_path)

    def process_image(self, file_path):
        self.original_path = file_path
        model_name = self._resolve_model_key()
        if not self._ensure_premium_download_allowed(model_name):
            self.status_var.set("Processing cancelled — premium model not downloaded.")
            return

        alpha_matting = bool(self.refine_edges_var.get())
        model_label = model_short_label(model_name)
        model_cached = is_rembg_model_cached(model_name)

        needs_download_ui = not model_cached
        allow_download = (
            not is_premium_rembg_model(model_name)
            or model_name in self._premium_download_approved
        )

        if model_cached:
            self.status_var.set(f"Using downloaded {model_label} — removing background…")
            self._set_processing_phase(model_label)
            self.progress_bar.start()
        else:
            self.status_var.set(
                f"Watch the blue download bar below — {model_label} "
                f"(~{int(REMBG_MODEL_INFO[model_name]['download_mb'])} MB)"
            )
            self._show_download_panel(model_name)

        def process():
            try:
                progress_cb = self._make_download_progress_callback() if needs_download_ui else None

                original = Image.open(file_path)
                original.load()

                if needs_download_ui:
                    self._run_on_ui_thread(
                        lambda: self._set_processing_phase(model_label)
                    )
                    self._run_on_ui_thread(self.progress_bar.start)

                output = remove_image_background(
                    original,
                    model_name=model_name,
                    alpha_matting=alpha_matting,
                    allow_model_download=allow_download,
                    on_download_progress=progress_cb,
                )
                self._run_on_ui_thread(lambda: self._finish_processing(original, output))
            except Exception as e:
                error_message = str(e)
                self._run_on_ui_thread(lambda: self._handle_processing_error(error_message))
            finally:
                def cleanup():
                    self._hide_download_panel()
                    self.progress_bar.stop()

                self._run_on_ui_thread(cleanup)

        threading.Thread(target=process, daemon=True).start()

    def _finish_processing(self, original, output):
        self.current_image = original
        self.processed_image = output
        self._update_preview_details()
        self._refresh_preview_panels()
        self.status_var.set("Background removed successfully. Your PNG is ready to save.")
        self._set_save_button_enabled(True)

    def _handle_processing_error(self, error_message):
        self.status_var.set(f"Error: {error_message}")
        showerror("Error", f"Failed to process image: {error_message}")

    def save_processed_image(self, event=None):
        if self.processed_image is None:
            showerror("Error", "No processed image to save!")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")],
            initialfile="background_removed.png"
        )
        
        if save_path:
            try:
                # Save with original quality
                self.processed_image.save(save_path, "PNG", quality=100)
                showinfo("Success", "Image saved successfully!")
                self.status_var.set(f"Saved PNG to {Path(save_path).name}")
            except Exception as e:
                showerror("Error", f"Failed to save image: {str(e)}")

    def _compose_on_checkerboard(self, image: Image.Image) -> Image.Image:
        """Flatten RGBA onto a checkerboard so Tk preview shows transparency correctly."""
        if image.mode != "RGBA":
            return image.convert("RGB")

        width, height = image.size
        background = Image.new("RGB", (width, height), CHECKER_DARK)
        tile = 14
        draw = ImageDraw.Draw(background)
        for x in range(0, width, tile):
            for y in range(0, height, tile):
                color = CHECKER_LIGHT if ((x // tile) + (y // tile)) % 2 else CHECKER_DARK
                draw.rectangle(
                    (x, y, min(x + tile, width), min(y + tile, height)),
                    fill=color,
                )
        background.paste(image, mask=image.split()[3])
        return background

    def display_image(self, image, canvas, maintain_aspect=True, transparent=False):
        canvas.update_idletasks()

        # Get canvas dimensions
        canvas_width = max(canvas.winfo_width(), 320)
        canvas_height = max(canvas.winfo_height(), 320)
        preview_padding = 28
        available_width = max(canvas_width - (preview_padding * 2), 1)
        available_height = max(canvas_height - (preview_padding * 2), 1)

        # Calculate scaling factor while maintaining aspect ratio
        if maintain_aspect:
            # Calculate scaling factors for both dimensions
            width_ratio = available_width / image.width
            height_ratio = available_height / image.height
            
            # Use the smaller ratio to ensure image fits in canvas
            scale_factor = min(width_ratio, height_ratio)
            
            new_width = max(1, int(image.width * scale_factor))
            new_height = max(1, int(image.height * scale_factor))
        else:
            new_width = available_width
            new_height = available_height

        # Resize image while maintaining quality
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        if transparent and resized_image.mode == "RGBA":
            resized_image = self._compose_on_checkerboard(resized_image)
        elif resized_image.mode not in ("RGB", "L"):
            resized_image = resized_image.convert("RGB")
        
        # Convert to PhotoImage and display
        tk_image = ImageTk.PhotoImage(resized_image)
        canvas.delete("all")  # Clear previous image
        self._paint_canvas_background(canvas, transparent=transparent)
        
        canvas.image = tk_image  # Keep a reference
        canvas.create_image(canvas_width / 2, canvas_height / 2, image=tk_image)

    def create_ico_from_png(self, png_path):
        """Create an ICO file from a PNG file if it doesn't exist"""
        ico_path = png_path.replace('.png', '.ico')
        if not os.path.exists(ico_path):
            try:
                # Open PNG and convert to RGBA if necessary
                img = Image.open(png_path)
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # Create ICO file with multiple sizes
                icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
                img.save(ico_path, format='ICO', sizes=icon_sizes)
            except Exception as e:
                print(f"Could not create ICO file: {e}")
        return ico_path

    def check_for_updates(self):
        """Check for updates on GitHub and return the latest version if available."""
        try:
            log("=== Starting Update Check ===")
            self.status_var.set("Checking for updates...")
            
            # Make the request with headers to avoid rate limiting
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': f'background-remover/{CURRENT_VERSION}'
            }
            
            response = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
            log(f"GitHub API Response Status: {response.status_code}")
            
            if response.status_code != 200:
                log(f"GitHub API Error: {response.text}")
                self.status_var.set("Failed to check for updates")
                return None
                
            latest_release = response.json()
            
            # Check if there's a valid release
            if 'tag_name' not in latest_release:
                log("No tag_name found in release")
                self.status_var.set("No updates found")
                return None
                
            # Get the latest version number (strip v prefix if present)
            latest_version = latest_release.get('tag_name', '').lstrip('v')
            log(f"Latest version on GitHub: {latest_version}")
            
            if not latest_version:
                log("Empty version tag found in release")
                self.status_var.set("No valid update found")
                return None
            
            if compare_versions(latest_version, CURRENT_VERSION):
                log(f"New version {latest_version} is available!")
                self.status_var.set(f"New version {latest_version} available!")
                if messagebox.askyesno("Update Available", 
                                     f"Version {latest_version} is available. Would you like to update now?"):
                    self.download_and_install_update(latest_release)
            else:
                log("You have the latest version")
                self.status_var.set("You have the latest version")
                messagebox.showinfo("No Updates", "You have the latest version installed!")
                return None
                
        except requests.exceptions.RequestException as e:
            log(f"Network error checking for updates: {e}")
            self.status_var.set("Network error checking for updates")
            messagebox.showerror("Update Error", f"Network error checking for updates: {e}")
            return None
        except Exception as e:
            log(f"Unexpected error checking for updates: {e}")
            self.status_var.set("Error checking for updates")
            messagebox.showerror("Update Error", f"Error checking for updates: {e}")
            return None

    def download_and_install_update(self, release):
        """Download and install the latest release."""
        try:
            self.status_var.set("Downloading update...")
            latest_version = release.get('tag_name', '').lstrip('v')

            if not IS_WINDOWS or not getattr(sys, "frozen", False):
                release_url = release.get('html_url') or "https://github.com/needyamin/img-background-remover/releases/latest"
                self.status_var.set("Open release page for update")
                messagebox.showinfo(
                    "Manual Update",
                    "Automatic self-install is currently only supported for the packaged Windows build.\n\n"
                    "The latest release page will open in your browser instead.",
                )
                self.open_link(release_url)
                return False
            
            # Find the asset with .exe extension
            assets = release.get('assets', [])
            exe_asset = None
            for asset in assets:
                if asset.get('name', '').lower().endswith('.exe'):
                    exe_asset = asset
                    break
                    
            if not exe_asset:
                raise Exception("No executable found in release assets")
            
            # Create temporary directory for download
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                exe_path = temp_path / exe_asset['name']
                
                # Download the new version
                download_url = exe_asset['browser_download_url']
                log(f"Downloading from: {download_url}")
                
                # Show a message to inform the user that download is in progress
                self.status_var.set(f"Downloading version {latest_version}...")
                
                # Download with progress tracking
                response = requests.get(download_url, stream=True)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(exe_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        downloaded += len(chunk)
                        f.write(chunk)
                
                self.status_var.set("Installing update...")
                
                # Create update script
                update_script = temp_path / "update.bat"
                current_exe = sys.executable
                
                with open(update_script, 'w') as f:
                    f.write(f"""@echo off
echo Waiting for application to close...
timeout /t 2 /nobreak
echo Updating Background Remover...
del "{current_exe}"
if exist "{current_exe}" (
    echo Retrying with force delete...
    taskkill /f /im "{os.path.basename(current_exe)}" 2>nul
    timeout /t 1 /nobreak
    del /f "{current_exe}"
)
echo Copying new version...
copy "{exe_path}" "{current_exe}"
if exist "{current_exe}" (
    echo Starting new version...
    start "" "{current_exe}"
) else (
    echo ERROR: Failed to copy new version.
    pause
)
""")
                
                # Run update script and exit
                subprocess.Popen([str(update_script)], shell=True)
                time.sleep(1)
                sys.exit(0)
                
        except Exception as e:
            error_msg = str(e)
            log(f"Error installing update: {error_msg}")
            self.status_var.set("Update failed")
            messagebox.showerror("Update Error", f"Failed to install update: {error_msg}")
            return False

def ensure_background_remover_dependencies(parent=None):
    """Check required packages before opening the remover UI."""
    if not MISSING_DEPENDENCIES:
        return True

    missing_list = ", ".join(MISSING_DEPENDENCIES)
    details = "\n".join(
        f"- {name}: {error}"
        for name, error in DEPENDENCY_ERRORS.items()
    )
    nested_diagnostics = collect_dependency_diagnostics()
    report_sections = []
    if details:
        report_sections.append("Dependency load details:\n" + details)
    if nested_diagnostics:
        report_sections.append("Nested runtime checks:\n" + nested_diagnostics)
    full_report = "\n\n".join(report_sections)
    diagnostics_path = write_dependency_diagnostics_report(full_report) if full_report else None

    if is_packaged_runtime():
        install_hint = (
            "The packaged BG Remover runtime could not be loaded.\n\n"
            f"Failed dependency import: {missing_list}\n\n"
            "This usually means the installer build did not bundle one of rembg's nested runtime files "
            "correctly. End users should not need to run pip inside an installed build."
        )
    else:
        install_hint = (
            "Required packages are missing: "
            f"{missing_list}\n\n"
            "Install them with:\n"
            "python -m pip install -r src\\desktop_tools\\app\\requirements.txt"
        )
    if full_report:
        install_hint += f"\n\n{full_report}"
    if diagnostics_path is not None:
        install_hint += f"\n\nDiagnostic report saved to:\n{diagnostics_path}"

    if parent is None:
        show_startup_error("Missing Dependencies", install_hint)
    else:
        messagebox.showerror("Missing Dependencies", install_hint, parent=parent)
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
