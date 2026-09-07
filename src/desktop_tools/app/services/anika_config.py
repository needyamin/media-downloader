"""Read/write Anika assistant settings (shared with the Anika desktop assistant process)."""

from __future__ import annotations

import json

from desktop_tools.shared.user_data_paths import get_anika_user_dir

ANIKA_USER_DIR = get_anika_user_dir()
ANIKA_CONFIG_FILE = ANIKA_USER_DIR / "config.json"

DEFAULT_BREAK_INTERVAL_MINS = 30
DEFAULT_BREAK_STAY_SECS = 10
MIN_BREAK_INTERVAL_MINS = 1
MAX_BREAK_INTERVAL_MINS = 120
MIN_BREAK_STAY_SECS = 10
MAX_BREAK_STAY_SECS = 300


def _default_config() -> dict:
    return {
        "break_interval_mins": DEFAULT_BREAK_INTERVAL_MINS,
        "break_stay_secs": DEFAULT_BREAK_STAY_SECS,
    }


def load_anika_config() -> dict:
    """Load Anika config from disk, merging with defaults."""
    config = _default_config()
    ANIKA_USER_DIR.mkdir(parents=True, exist_ok=True)
    if not ANIKA_CONFIG_FILE.is_file():
        return config
    try:
        with ANIKA_CONFIG_FILE.open("r", encoding="utf-8") as handle:
            saved = json.load(handle)
        if isinstance(saved, dict):
            config.update(saved)
    except Exception:
        pass
    return config


def save_anika_config(updates: dict) -> None:
    """Merge updates into the on-disk Anika config."""
    config = load_anika_config()
    config.update(updates)
    ANIKA_USER_DIR.mkdir(parents=True, exist_ok=True)
    with ANIKA_CONFIG_FILE.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=4)


def get_break_settings() -> tuple[bool, int, int]:
    """Return (enabled, interval_minutes, stay_seconds)."""
    config = load_anika_config()
    interval = int(config.get("break_interval_mins") or 0)
    stay = int(config.get("break_stay_secs") or DEFAULT_BREAK_STAY_SECS)
    stay = max(MIN_BREAK_STAY_SECS, min(MAX_BREAK_STAY_SECS, stay))
    enabled = interval > 0
    if enabled:
        interval = max(MIN_BREAK_INTERVAL_MINS, min(MAX_BREAK_INTERVAL_MINS, interval))
    return enabled, interval, stay


def save_break_settings(*, enabled: bool, interval_mins: int, stay_secs: int) -> None:
    """Persist break reminder timing."""
    if enabled:
        interval_mins = max(MIN_BREAK_INTERVAL_MINS, min(MAX_BREAK_INTERVAL_MINS, int(interval_mins)))
    else:
        interval_mins = 0
    stay_secs = max(MIN_BREAK_STAY_SECS, min(MAX_BREAK_STAY_SECS, int(stay_secs)))
    save_anika_config(
        {
            "break_interval_mins": interval_mins,
            "break_stay_secs": stay_secs,
        }
    )
