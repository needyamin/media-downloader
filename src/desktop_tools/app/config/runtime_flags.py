"""Runtime flags and domain policy helpers for desktop app behavior."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from desktop_tools.shared.resources import get_project_root


APP_FLAGS_PATH = get_project_root() / "app_flags.json"
DEFAULT_APP_FLAGS = {
    "debug_logging": False,
    "ui_queue_poll_ms": 150,
    "clipboard_poll_ms_active": 1200,
    "clipboard_poll_ms_background": 2500,
    "clipboard_recent_limit": 10,
    "progress_log_min_interval_ms": 1500,
    "progress_ui_min_interval_ms": 250,
    "max_log_lines": 400,
    "disabled_domains": [],
    "hotkeys": {
        "converter": "Ctrl+Shift+V",
        "background_remover": "Ctrl+Shift+B",
        "screenshot": "Ctrl+Shift+Y",
        "screen_recorder": "Ctrl+Shift+R",
        "anika": "Ctrl+Shift+A",
        "record_pause": "Ctrl+Shift+P",
        "record_finish": "Ctrl+Shift+S",
    },
    "versions": {
        "media_downloader": "3.0.0",
        "background_remover": "1.0.0",
    },
    "paths": {
        "download_root_dirname": "AnsNewTech Downloads",
        "screen_recorder_output_dirname": "YScreenRecorder",
    },
    "ui": {
        "screenshot_dim_alpha": 0.42,
    },
    "themes": {
        "media_downloader": {},
        "converter": {},
        "background_remover": {},
        "screenshot": {},
        "screen_recorder": {},
    },
    "updates": {
        "source_auto_pull": True,
        "source_auto_restart_after_pull": False,
        "source_remote": "origin",
        "source_branch": "auto",
    },
}


def load_app_flags(app_flags_path: Path = APP_FLAGS_PATH) -> dict:
    """Load runtime flags from disk with safe defaults."""
    flags = DEFAULT_APP_FLAGS.copy()
    try:
        if app_flags_path.exists():
            with app_flags_path.open("r", encoding="utf-8") as flag_file:
                loaded_flags = json.load(flag_file)
            if isinstance(loaded_flags, dict):
                flags.update(loaded_flags)
    except Exception:
        pass
    return flags


def normalize_domain_name(domain: str | None) -> str:
    """Normalize a domain name for blocklist checks."""
    if not domain:
        return ""
    normalized = str(domain).strip().lower().rstrip(".")
    while normalized.startswith("."):
        normalized = normalized[1:]
    if normalized.startswith("www."):
        normalized = normalized[4:]
    return normalized


def compute_disabled_domains(flags: dict) -> list[str]:
    """Return normalized disabled domains from app flags."""
    return [
        normalized
        for normalized in (
            normalize_domain_name(domain)
            for domain in flags.get("disabled_domains", [])
            if isinstance(domain, str)
        )
        if normalized
    ]


def get_disabled_domain_match(url: str, disabled_domains: list[str]) -> str | None:
    """Return the blocked domain that matches a URL, if any."""
    try:
        hostname = normalize_domain_name(urlparse(url).hostname)
        if not hostname:
            return None
        for blocked_domain in disabled_domains:
            if hostname == blocked_domain or hostname.endswith(f".{blocked_domain}"):
                return blocked_domain
    except Exception:
        return None
    return None


def get_hotkey_combo(flags: dict, key: str, default_combo: str) -> str:
    """Return normalized hotkey combo string from flags."""
    hotkeys = flags.get("hotkeys", {})
    if not isinstance(hotkeys, dict):
        return default_combo
    value = hotkeys.get(key, default_combo)
    if not isinstance(value, str):
        return default_combo
    normalized = value.strip()
    return normalized if normalized else default_combo


def get_nested_flag(flags: dict, keys: tuple[str, ...], default):
    """Fetch nested config value by key path."""
    current = flags
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def get_tool_theme(tool_name: str, defaults: dict) -> dict:
    """Merge theme override from app flags on top of defaults."""
    override = get_nested_flag(APP_FLAGS, ("themes", tool_name), {})
    if not isinstance(override, dict):
        return defaults.copy()
    merged = defaults.copy()
    merged.update({k: v for k, v in override.items() if isinstance(k, str)})
    return merged


def get_ui_setting(key: str, default):
    """Read ui.* setting with fallback."""
    value = get_nested_flag(APP_FLAGS, ("ui", key), default)
    return value


def get_path_setting(key: str, default: str) -> str:
    """Read paths.* setting with fallback."""
    value = get_nested_flag(APP_FLAGS, ("paths", key), default)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def get_version_setting(key: str, default: str) -> str:
    """Read versions.* setting with fallback."""
    value = get_nested_flag(APP_FLAGS, ("versions", key), default)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


APP_FLAGS = load_app_flags()
DEBUG_MODE = bool(APP_FLAGS.get("debug_logging", False))
UI_QUEUE_POLL_MS = max(50, int(APP_FLAGS.get("ui_queue_poll_ms", 150)))
CLIPBOARD_POLL_MS_ACTIVE = max(250, int(APP_FLAGS.get("clipboard_poll_ms_active", 1200)))
CLIPBOARD_POLL_MS_BACKGROUND = max(500, int(APP_FLAGS.get("clipboard_poll_ms_background", 2500)))
CLIPBOARD_RECENT_LIMIT = max(1, int(APP_FLAGS.get("clipboard_recent_limit", 10)))
PROGRESS_LOG_MIN_INTERVAL_MS = max(250, int(APP_FLAGS.get("progress_log_min_interval_ms", 1500)))
PROGRESS_UI_MIN_INTERVAL_MS = max(100, int(APP_FLAGS.get("progress_ui_min_interval_ms", 250)))
MAX_LOG_LINES = max(50, int(APP_FLAGS.get("max_log_lines", 400)))
DISABLED_DOMAINS = compute_disabled_domains(APP_FLAGS)
HOTKEY_CONVERTER = get_hotkey_combo(APP_FLAGS, "converter", "Ctrl+Shift+V")
HOTKEY_BACKGROUND_REMOVER = get_hotkey_combo(APP_FLAGS, "background_remover", "Ctrl+Shift+B")
HOTKEY_SCREENSHOT = get_hotkey_combo(APP_FLAGS, "screenshot", "Ctrl+Shift+Y")
HOTKEY_SCREENRECORDER = get_hotkey_combo(APP_FLAGS, "screen_recorder", "Ctrl+Shift+R")
HOTKEY_ANIKA = get_hotkey_combo(
    APP_FLAGS,
    "anika",
    get_hotkey_combo(APP_FLAGS, "yfun", "Ctrl+Shift+A"),
)
HOTKEY_RECORD_PAUSE = get_hotkey_combo(APP_FLAGS, "record_pause", "Ctrl+Shift+P")
HOTKEY_RECORD_FINISH = get_hotkey_combo(APP_FLAGS, "record_finish", "Ctrl+Shift+S")
APP_VERSION_MAIN = get_version_setting("media_downloader", "3.0.0")
APP_VERSION_BG_REMOVER = get_version_setting("background_remover", "1.0.0")
DOWNLOAD_ROOT_DIRNAME = get_path_setting("download_root_dirname", "AnsNewTech Downloads")
SCREEN_RECORDER_OUTPUT_DIRNAME = get_path_setting("screen_recorder_output_dirname", "YScreenRecorder")
SCREENSHOT_DIM_ALPHA = float(get_ui_setting("screenshot_dim_alpha", 0.42))

