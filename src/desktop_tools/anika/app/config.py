import os
import json
import random
from datetime import datetime, timedelta

# App directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES_DIR = os.path.join(BASE_DIR, "resources")
def _resolve_anika_user_data_dir() -> str:
    """Use the hub app data folder when available; fall back for standalone Anika runs."""
    try:
        from desktop_tools.shared.user_data_paths import get_anika_user_dir

        return str(get_anika_user_dir())
    except Exception:
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            return os.path.join(local_appdata, "Media Downloader", "anika")
        return os.path.join(os.path.expanduser("~"), ".yamos_witch_mate")


USER_DATA_DIR = _resolve_anika_user_data_dir()
CONFIG_FILE = os.path.join(USER_DATA_DIR, "config.json")
TODO_FILE = os.path.join(USER_DATA_DIR, "todo.json")
SESSION_FILE = os.path.join(USER_DATA_DIR, "session.json")

# Ensure user data folder exists
os.makedirs(USER_DATA_DIR, exist_ok=True)

MIN_BREAK_INTERVAL_MINS = 1
MAX_BREAK_INTERVAL_MINS = 120
MIN_BREAK_STAY_SECS = 10
MAX_BREAK_STAY_SECS = 300
POMODORO_WORK_SECS = 25 * 60
POMODORO_BREAK_SECS = 5 * 60
TASK_REMIND_REPEAT_SECS = 30 * 60
WORKDAY_START_HOUR = 9
WORKDAY_LUNCH_HOUR = 12
WORKDAY_AFTERNOON_HOUR = 13
WORKDAY_END_HOUR = 18
DUE_PRESETS = {
    "now": "Now",
    "morning": "Morning",
    "afternoon": "Afternoon",
    "eod": "End of day",
    "later": "Tomorrow",
}
CUSTOM_TIMER_MIN_MINS = 1
CUSTOM_TIMER_MAX_MINS = 180
WORKDAY_BUCKETS = (
    ("morning", "Morning"),
    ("afternoon", "Afternoon"),
    ("eod", "End of day"),
    ("later", "Tomorrow"),
    ("done", "Done"),
)
WORKDAY_TIMER_PRESETS = {
    "Focus": {"secs": 25 * 60, "break_secs": 5 * 60, "auto_break": True},
    "Deep": {"secs": 50 * 60, "break_secs": 10 * 60, "auto_break": True},
    "Lunch": {"secs": 45 * 60, "break_secs": 0, "auto_break": False},
    "Wrap-up": {"secs": 15 * 60, "break_secs": 0, "auto_break": False},
}

DEFAULT_CONFIG = {
    "scale": 1.4,              # 0.5 to 2.5
    "opacity": 1.0,            # 0.1 to 1.0
    "volume": 0.8,             # 0.0 to 1.0
    "speech_rate": 0.5,        # Probability of talking on tick (0.0 to 1.0)
    "gravity_enabled": True,
    "boundary_keep": True,     # Keep pet inside screen bounds
    "language": "mix",         # "en" (English), "bn" (Bengali), "mix" (Banglish/Bilingual)
    "sound_enabled": False,
    # New in advanced upgrade:
    "theme": "hub_match",      # default UI matches Media Downloader hub
    "personality": "playful",  # "energetic", "calm", "shy", "mischievous", "playful"
    "weather_mode": "none",    # "none", "rain", "snow", "sunny"
    "hotkey": "ctrl+shift+m",
    "pomodoro_count": 0,       # Total completed pomodoros
    "fairy_dust_enabled": True,
    "magic_trail_enabled": True,
    "clock_announce": True,    # Speak the hour when the clock rolls over
    "last_custom_timer_mins": 20,
    # Break reminder:
    "break_interval_mins": 30, # How often Anika reminds you to take a break (minutes)
    "break_stay_secs": 10,     # How long Anika stays visible during break reminder (seconds)
    # Drag to screen edge:
    "edge_hide_enabled": True,
    "edge_hide_mins": 5,       # Minutes Anika stays away after drag-to-edge
    "edge_hide_offscreen_frac": 0.85,  # Fraction of sprite that must be off-screen to hide
}

# GUI Themes (hub_match = Media Downloader main app styling)
try:
    from app.ui_theme import HUB_MATCHED_THEME
except Exception:
    HUB_MATCHED_THEME = {
        "bg": "#ffffff",
        "frame": "#f5f5f5",
        "accent": "#2196F3",
        "accent_hover": "#1976D2",
        "text": "#333333",
        "text_dim": "#757575",
        "bubble_fill": "#ffffff",
        "bubble_text": "#333333",
        "gold": "#FFC107",
        "danger": "#F44336",
        "danger_hover": "#D32F2F",
        "success": "#4CAF50",
        "name": "Media Downloader",
    }

THEMES = {
    "hub_match": {**HUB_MATCHED_THEME},
    "purple_night": {
        "bg": "#1a0a2e",
        "frame": "#2d1b5e",
        "accent": "#8a2be2",
        "accent_hover": "#6a1b9a",
        "text": "#e9d5ff",
        "text_dim": "#b39ddb",
        "bubble_fill": "#ffffff",
        "bubble_text": "#2d1b5e",
        "gold": "#ffd700",
        "danger": "#991b1b",
        "danger_hover": "#7f1d1d",
        "success": "#1a472a",
        "name": "🌙 Purple Night",
    },
    "dark": {
        "bg": "#111827",
        "frame": "#1f2937",
        "accent": "#3b82f6",
        "accent_hover": "#1d4ed8",
        "text": "#f9fafb",
        "text_dim": "#9ca3af",
        "bubble_fill": "#ffffff",
        "bubble_text": "#111827",
        "gold": "#fbbf24",
        "danger": "#991b1b",
        "danger_hover": "#7f1d1d",
        "success": "#065f46",
        "name": "🌑 Dark Blue",
    },
    "light": {
        "bg": "#f5f3ff",
        "frame": "#ede9fe",
        "accent": "#7c3aed",
        "accent_hover": "#5b21b6",
        "text": "#1e1b4b",
        "text_dim": "#4c1d95",
        "bubble_fill": "#ffffff",
        "bubble_text": "#1e1b4b",
        "gold": "#d97706",
        "danger": "#dc2626",
        "danger_hover": "#991b1b",
        "success": "#065f46",
        "name": "☀️ Light Lavender",
    },
    "forest": {
        "bg": "#0f1f0a",
        "frame": "#1a3310",
        "accent": "#4ade80",
        "accent_hover": "#16a34a",
        "text": "#d1fae5",
        "text_dim": "#6ee7b7",
        "bubble_fill": "#f0fdf4",
        "bubble_text": "#0f1f0a",
        "gold": "#fde68a",
        "danger": "#991b1b",
        "danger_hover": "#7f1d1d",
        "success": "#14532d",
        "name": "🌿 Enchanted Forest",
    },
}

def get_theme():
    return THEMES.get(config_db.get("theme"), THEMES["hub_match"])


def get_gui_theme():
    """Theme for settings / spellbook / timer windows (hub-aligned)."""
    try:
        from app.ui_theme import enrich_theme, get_ui_theme, load_hub_theme_from_desktop_tools

        loaded = load_hub_theme_from_desktop_tools()
        if loaded:
            return enrich_theme(loaded)
        return enrich_theme(get_ui_theme())
    except Exception:
        return get_theme()

# Personality presets — control behavior weights
PERSONALITY_PRESETS = {
    "energetic": {
        "speech_rate_mult": 1.8,
        "dance_prob": 0.15,
        "idle_prob": 0.05,
        "particle_mult": 1.5,
        "description": "Hyper and enthusiastic, lots of movement and particles",
    },
    "calm": {
        "speech_rate_mult": 0.5,
        "dance_prob": 0.03,
        "idle_prob": 0.60,
        "particle_mult": 0.5,
        "description": "Peaceful and serene, mostly stays idle and watches",
    },
    "shy": {
        "speech_rate_mult": 0.3,
        "dance_prob": 0.02,
        "idle_prob": 0.50,
        "particle_mult": 0.7,
        "description": "Bashful and quiet, hides often and blushes a lot",
    },
    "mischievous": {
        "speech_rate_mult": 1.2,
        "dance_prob": 0.08,
        "idle_prob": 0.15,
        "particle_mult": 1.2,
        "description": "Sneaky and playful, hides and chases more often",
    },
    "playful": {
        "speech_rate_mult": 1.0,
        "dance_prob": 0.08,
        "idle_prob": 0.30,
        "particle_mult": 1.0,
        "description": "Balanced and fun — the default Anika",
    },
}

def get_personality():
    return PERSONALITY_PRESETS.get(config_db.get("personality"), PERSONALITY_PRESETS["playful"])


class ConfigManager:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    # Migrate older tiny scale settings to new default
                    if "scale" in saved and saved["scale"] < 1.2:
                        saved["scale"] = 1.4
                    stay = saved.get("break_stay_secs")
                    if stay is not None:
                        try:
                            stay_i = int(stay)
                        except (TypeError, ValueError):
                            stay_i = MIN_BREAK_STAY_SECS
                        if stay_i > 0:
                            saved["break_stay_secs"] = max(MIN_BREAK_STAY_SECS, min(MAX_BREAK_STAY_SECS, stay_i))
                    self.config.update(saved)
            except Exception as e:
                print(f"Error loading config: {e}")

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key):
        return self.config.get(key, DEFAULT_CONFIG.get(key))

    def set(self, key, value):
        self.config[key] = value
        self.save()


# Global config instance
config_db = ConfigManager()


# Session memory: track how long Anika has been running and interaction count
class SessionMemory:
    def __init__(self):
        self.interaction_count = 0
        self.session_start = None
        self.click_times = []  # for rapid-click detection
        self.load()

    def load(self):
        import time
        self.session_start = time.time()
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.interaction_count = data.get("total_interactions", 0)
            except:
                pass

    def save(self):
        try:
            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump({"total_interactions": self.interaction_count}, f)
        except:
            pass

    def record_interaction(self):
        import time
        self.interaction_count += 1
        now = time.time()
        self.click_times.append(now)
        # Keep only last 5 seconds of clicks
        self.click_times = [t for t in self.click_times if now - t < 5.0]

    def is_rapid_clicking(self):
        """Returns True if 5+ clicks happened in the last 3 seconds."""
        import time
        now = time.time()
        recent = [t for t in self.click_times if now - t < 3.0]
        return len(recent) >= 5

    def get_session_minutes(self):
        import time
        return int((time.time() - self.session_start) / 60)


session_memory = SessionMemory()


def session_reminder_milestone(mins: int) -> int:
    """Largest whole hour of session time that should trigger a reminder."""
    mins = int(mins or 0)
    if mins < 60:
        return 0
    return (mins // 60) * 60


def should_send_session_reminder(mins: int, last_milestone: int) -> bool:
    milestone = session_reminder_milestone(mins)
    return milestone >= 60 and milestone > int(last_milestone or 0)


def clamp_break_stay_secs(value) -> int:
    try:
        stay = int(value or MIN_BREAK_STAY_SECS)
    except (TypeError, ValueError):
        stay = MIN_BREAK_STAY_SECS
    return max(MIN_BREAK_STAY_SECS, min(MAX_BREAK_STAY_SECS, stay))


def clamp_break_interval_mins(value) -> int:
    try:
        interval = int(value or 0)
    except (TypeError, ValueError):
        interval = 0
    if interval <= 0:
        return 0
    return max(MIN_BREAK_INTERVAL_MINS, min(MAX_BREAK_INTERVAL_MINS, interval))


def normalize_task(task: dict) -> dict:
    task.setdefault("text", "")
    task.setdefault("done", False)
    task.setdefault("done_today", False)
    task.setdefault("priority", "normal")
    task.setdefault("category", "work")
    task.setdefault("due", "")
    task.setdefault("reminded_at", "")
    task.setdefault("created", "")
    return task


def load_tasks() -> list:
    if not os.path.exists(TODO_FILE):
        return []
    try:
        with open(TODO_FILE, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [normalize_task(dict(task)) for task in raw if isinstance(task, dict)]


def save_tasks(tasks: list) -> None:
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    with open(TODO_FILE, "w", encoding="utf-8") as handle:
        json.dump(tasks, handle, indent=4, ensure_ascii=False)


def pending_task_count(tasks=None) -> int:
    items = tasks if tasks is not None else load_tasks()
    return sum(1 for task in items if not task.get("done"))


def parse_due(due) -> datetime | None:
    if not due:
        return None
    try:
        return datetime.fromisoformat(str(due))
    except (TypeError, ValueError):
        return None


def _at_hour(now: datetime, hour: int, minute: int = 0) -> datetime:
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _today_or_tomorrow(target: datetime, now: datetime) -> datetime:
    if target <= now:
        return target + timedelta(days=1)
    return target


def workday_period(now: datetime | None = None) -> str:
    now = now or datetime.now()
    hour = now.hour
    if hour < WORKDAY_LUNCH_HOUR:
        return "morning"
    if hour < WORKDAY_AFTERNOON_HOUR:
        return "lunch"
    if hour < WORKDAY_END_HOUR:
        return "afternoon"
    return "wrapup"


def default_task_slot(now: datetime | None = None) -> str:
    period = workday_period(now)
    if period == "morning":
        return "morning"
    if period in ("lunch", "afternoon"):
        return "afternoon"
    return "eod"


def workday_hours_left(now: datetime | None = None) -> int:
    now = now or datetime.now()
    end = _at_hour(now, WORKDAY_END_HOUR)
    leftover = (end - now).total_seconds()
    if leftover <= 0:
        return 0
    return max(1, int((leftover + 1799) // 3600))


def workday_headline(now: datetime | None = None) -> str:
    now = now or datetime.now()
    weekday = now.strftime("%A")
    labels = {
        "morning": "Morning",
        "lunch": "Lunch",
        "afternoon": "Afternoon",
        "wrapup": "Wrap-up",
    }
    return f"{weekday}  ·  {labels.get(workday_period(now), 'Today')}"


def workday_subline(now: datetime | None = None) -> str:
    now = now or datetime.now()
    hours = workday_hours_left(now)
    if workday_period(now) == "wrapup":
        return "Workday is done. Park leftover tasks for tomorrow."
    if workday_period(now) == "lunch":
        return "Lunch window. Keep the afternoon list short."
    if hours == 1:
        return "About 1 hour left today"
    return f"About {hours} hours left today"


def due_from_preset(preset: str, now: datetime | None = None) -> str:
    now = now or datetime.now()
    key = (preset or "now").strip().lower()
    if key in ("", "none", "no due"):
        key = default_task_slot(now)
    if key in ("15m", "30m", "1h", "2h"):
        minutes = {"15m": 15, "30m": 30, "1h": 60, "2h": 120}[key]
        return (now + timedelta(minutes=minutes)).isoformat(timespec="minutes")
    if key == "now":
        return (now + timedelta(minutes=20)).isoformat(timespec="minutes")
    if key == "morning":
        return _today_or_tomorrow(_at_hour(now, 11, 30), now).isoformat(timespec="minutes")
    if key == "afternoon":
        return _today_or_tomorrow(_at_hour(now, 16, 0), now).isoformat(timespec="minutes")
    if key in ("eod", "evening", "end of day"):
        return _today_or_tomorrow(_at_hour(now, 17, 30), now).isoformat(timespec="minutes")
    if key in ("later", "tomorrow"):
        return (_at_hour(now, 9, 30) + timedelta(days=1)).isoformat(timespec="minutes")
    return (now + timedelta(minutes=20)).isoformat(timespec="minutes")


def default_meridian(now: datetime | None = None, slot: str = "") -> str:
    key = str(slot or "").strip().lower()
    if key == "morning":
        return "AM"
    if key in ("afternoon", "eod", "evening"):
        return "PM"
    period = workday_period(now)
    return "AM" if period == "morning" else "PM"


def parse_clock_text(text: str, now: datetime | None = None, meridian: str | None = None) -> datetime | None:
    """Parse times like 3:30, 15:30, 3pm. Use meridian=AM/PM when the text has no AM/PM."""
    import re

    raw = str(text or "").strip().lower()
    if not raw:
        return None
    now = now or datetime.now()
    mer = None
    if "pm" in raw:
        mer = "pm"
    elif "am" in raw:
        mer = "am"
    elif str(meridian or "").strip().upper() == "PM":
        mer = "pm"
    elif str(meridian or "").strip().upper() == "AM":
        mer = "am"
    raw = raw.replace("a.m.", "").replace("p.m.", "").replace("am", "").replace("pm", "")
    raw = raw.replace(".", ":").strip()
    match = re.match(r"^(\d{1,2}):(\d{2})$", raw)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
    else:
        match = re.match(r"^(\d{3,4})$", raw)
        if match:
            digits = match.group(1)
            if len(digits) == 3:
                hour, minute = int(digits[0]), int(digits[1:])
            else:
                hour, minute = int(digits[:2]), int(digits[2:])
        else:
            match = re.match(r"^(\d{1,2})$", raw)
            if not match:
                return None
            hour, minute = int(match.group(1)), 0
    if minute > 59:
        return None
    if hour > 12:
        mer = None
    if mer == "pm" and 1 <= hour <= 11:
        hour += 12
    elif mer == "am" and hour == 12:
        hour = 0
    elif mer == "pm" and hour == 12:
        hour = 12
    elif mer is None and 1 <= hour <= 7:
        hour += 12
    if hour > 23:
        return None
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def due_from_slot_and_clock(
    slot: str,
    clock_text: str = "",
    now: datetime | None = None,
    meridian: str | None = None,
) -> tuple[str, str]:
    """Return (due_iso, slot) from a workday slot plus optional clock time."""
    now = now or datetime.now()
    key = (slot or default_task_slot(now)).strip().lower()
    if key in ("tomorrow",):
        key = "later"
    parsed = parse_clock_text(clock_text, now, meridian=meridian)
    if parsed is None:
        return due_from_preset(key, now), key
    target = parsed
    if key == "later":
        if target.date() <= now.date():
            target = target + timedelta(days=1)
        return target.isoformat(timespec="minutes"), "later"
    if target <= now:
        target = target + timedelta(days=1)
        return target.isoformat(timespec="minutes"), "later"
    if target.hour < 13:
        key = "morning"
    elif target.hour < 17:
        key = "afternoon"
    else:
        key = "eod"
    return target.isoformat(timespec="minutes"), key


def format_task_when(task: dict, now: datetime | None = None) -> str:
    now = now or datetime.now()
    due_at = parse_due(task.get("due"))
    if due_at is None:
        return format_due_label("", now, slot=str(task.get("slot") or ""))
    stamp = due_at.strftime("%I:%M %p").lstrip("0")
    if due_at <= now:
        return f"Overdue {stamp}"
    if due_at.date() > now.date():
        return f"Tomorrow {stamp}"
    return stamp


def clamp_custom_timer_mins(value) -> int:
    try:
        minutes = int(float(value))
    except (TypeError, ValueError):
        minutes = 20
    return max(CUSTOM_TIMER_MIN_MINS, min(CUSTOM_TIMER_MAX_MINS, minutes))


def task_workday_bucket(task: dict, now: datetime | None = None) -> str:
    now = now or datetime.now()
    if task.get("done"):
        return "done"
    due_at = parse_due(task.get("due"))
    if due_at is not None and due_at.date() > now.date():
        return "later"
    slot = str(task.get("slot") or "").strip().lower()
    if slot == "now":
        period = workday_period(now)
        return "afternoon" if period in ("lunch", "afternoon") else ("morning" if period == "morning" else "eod")
    if slot in ("morning", "afternoon", "eod", "later"):
        return slot
    if due_at is None:
        return default_task_slot(now)
    if due_at.hour < 13:
        return "morning"
    if due_at.hour < 17:
        return "afternoon"
    return "eod"


def task_is_due(task: dict, now: datetime | None = None) -> bool:
    if task.get("done"):
        return False
    due_at = parse_due(task.get("due"))
    if due_at is None:
        return False
    return due_at <= (now or datetime.now())


def should_remind_task(task: dict, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    if not task_is_due(task, now):
        return False
    last = parse_due(task.get("reminded_at"))
    if last is None:
        return True
    return (now - last).total_seconds() >= TASK_REMIND_REPEAT_SECS


def due_tasks_to_remind(tasks=None, now: datetime | None = None) -> list:
    items = tasks if tasks is not None else load_tasks()
    now = now or datetime.now()
    return [task for task in items if should_remind_task(task, now)]


def format_due_label(due, now: datetime | None = None, slot: str = "") -> str:
    now = now or datetime.now()
    due_at = parse_due(due)
    if due_at is not None and due_at <= now:
        return "Overdue"
    if due_at is not None and due_at.date() > now.date():
        return "Tomorrow"
    if due_at is not None and 0 <= (due_at - now).total_seconds() <= 45 * 60:
        return "Now"
    key = str(slot or "").strip().lower()
    labels = {"now": "Now", "morning": "Morning", "afternoon": "Afternoon", "eod": "End of day", "later": "Tomorrow"}
    if key in labels:
        return labels[key]
    if due_at is None:
        return ""
    if due_at.hour < 13:
        return "Morning"
    if due_at.hour < 17:
        return "Afternoon"
    return "End of day"


def workday_timer_preset(name: str) -> dict:
    return dict(WORKDAY_TIMER_PRESETS.get(name, WORKDAY_TIMER_PRESETS["Focus"]))


def format_clock_label(now: datetime | None = None, *, seconds: bool = True) -> str:
    now = now or datetime.now()
    stamp = now.strftime("%I:%M:%S %p" if seconds else "%I:%M %p")
    return stamp.lstrip("0")


def clock_display_parts(value: datetime) -> tuple[str, str]:
    hour = value.hour
    mer = "AM" if hour < 12 else "PM"
    return f"{(hour % 12) or 12}:{value.minute:02d}", mer


def next_half_hour_parts(now: datetime | None = None) -> tuple[str, str]:
    now = now or datetime.now()
    if now.minute >= 30:
        target = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    else:
        target = now.replace(minute=30, second=0, microsecond=0)
    return clock_display_parts(target)


def suggested_workday_block(now: datetime | None = None) -> str:
    period = workday_period(now)
    if period == "morning":
        return "Focus"
    if period == "lunch":
        return "Lunch"
    if period == "afternoon":
        return "Deep"
    return "Wrap-up"


def ends_at_label(remaining_secs: int, now: datetime | None = None) -> str:
    now = now or datetime.now()
    remaining_secs = max(0, int(remaining_secs or 0))
    finish = now + timedelta(seconds=remaining_secs)
    return f"Ends at {format_clock_label(finish, seconds=False)}"


def due_preview_label(due: str, now: datetime | None = None) -> str:
    now = now or datetime.now()
    due_at = parse_due(due)
    if due_at is None:
        return ""
    stamp = format_clock_label(due_at, seconds=False)
    if due_at.date() > now.date():
        return f"Tomorrow, {stamp}"
    if due_at <= now:
        return f"Overdue if left as {stamp}"
    return f"Today, {stamp}"


def task_sort_key(task: dict) -> tuple:
    due_at = parse_due(task.get("due"))
    if due_at is None:
        return (1, datetime.max)
    return (0, due_at)


def slot_key_from_label(label: str, fallback: str = "afternoon") -> str:
    for key, name in DUE_PRESETS.items():
        if name == label:
            return key
    return fallback


def get_clock_speech(lang="mix", now: datetime | None = None) -> str:
    now = now or datetime.now()
    time_str = now.strftime("%I:%M %p").lstrip("0")
    hour = now.hour
    if 5 <= hour < 12:
        period_en, period_bn = "Good morning", "সুপ্রভাত"
    elif 12 <= hour < 17:
        period_en, period_bn = "Good afternoon", "শুভ অপরাহ্ন"
    elif 17 <= hour < 21:
        period_en, period_bn = "Good evening", "শুভ সন্ধ্যা"
    else:
        period_en, period_bn = "It's late", "রাত হয়েছে"
    if lang == "en":
        return f"{period_en}! It's {time_str}."
    if lang == "bn":
        return f"{period_bn}! এখন {time_str}।"
    return f"{period_bn}! এখন {time_str}।\n({period_en}! It's {time_str}.)"


# Speech bubble lines database (Bilingual / Bengali / English)
SPEECH_LINES = {
    "idle": [
        # Bengali / Banglish
        {"bn": "আজকে একটু নতুন জাদু শিখবো নাকি?", "en": "Should I learn some new magic today?"},
        {"bn": "উফ! কী গরম! একটু লেবুর শরবত পেলে ভালো হতো...", "en": "Ugh, so hot! Lemon juice would be nice..."},
        {"bn": "তুমি শুধু কাজই করছো, আমার সাথে খেলবে না?", "en": "You're only working, won't you play with me?"},
        {"bn": "চা খাবে নাকি? এক কাপ লাল চা বানিয়ে দিই?", "en": "Want some tea? Let me make a cup of black tea!"},
        {"bn": "আমার ঝাড়ুটা কোথায় রাখলাম বলতো?", "en": "Where did I leave my broom?"},
        {"bn": "জাদুর কলসি রেডি, একটু জাদু দেখাবো?", "en": "Magic pot is ready, want to see a spell?"},
        {"bn": "কেমন আছো? ফাঁকি দিচ্ছ না তো?", "en": "How are you? Not slacking off, are you?"},
        {"bn": "আমার জাদুর মন্ত্রগুলো সব গুলিয়ে যাচ্ছে!", "en": "My magic spells are all getting mixed up!"},
        # English
        {"bn": "Hey! Need some magical help?", "en": "Hey! Need some magical help?"},
        {"bn": "Just floating around, watching you work.", "en": "Just floating around, watching you work."},
        {"bn": "Focus is magic. Keep it up!", "en": "Focus is magic. Keep it up!"}
    ],
    "idle_morning": [
        {"bn": "সুপ্রভাত! আজকের দিনটা জাদুর মতো হবে!\n(Good morning! Today will be magical!)", "en": "Good morning! Today will be magical!"},
        {"bn": "ঘুম থেকে উঠে গেছো? চলো মিলে কাজ শুরু করি!\n(You're up? Let's get to work together!)", "en": "You're up? Let's get to work together!"},
        {"bn": "☀️ সকালের মন্ত্র পাঠ করে নিই... প্রতিদিন একটু ভালো হই!\n(Morning spell done... getting better every day!)", "en": "Morning spell done! Getting better every day!"},
    ],
    "idle_night": [
        {"bn": "🌙 রাত অনেক হয়েছে... তুমি এখনো জাগছো?\n(It's late... you're still awake?)", "en": "It's late... you're still awake?"},
        {"bn": "তারাগুলো কিন্তু ঘুমিয়ে পড়েছে... তুমিও ঘুমাও!\n(Even the stars are asleep... you should sleep too!)", "en": "Even the stars are asleep... you should sleep too!"},
        {"bn": "🌟 রাতের জাদু সবচেয়ে শক্তিশালী... কিন্তু ঘুম দরকার!\n(Night magic is the strongest... but sleep is needed!)", "en": "Night magic is strongest... but sleep is needed!"},
    ],
    "idle_afternoon": [
        {"bn": "☀️ দুপুরের রোদ একটু বেশিই গরম! একটু বিশ্রাম নেবে?\n(Afternoon sun is hot! Want to rest a bit?)", "en": "Afternoon sun is too hot! Want to rest?"},
        {"bn": "ভাত ঘুম দিলে কেমন হয়? মানে... না না, কাজ করো!\n(How about a nap? No no, keep working!)", "en": "How about a nap? No no, keep working!"},
        {"bn": "দুপুরে একটু শরবত খেলে মাথা ঠান্ডা থাকে!\n(A cold drink in the afternoon keeps you fresh!)", "en": "A cold drink keeps you fresh!"},
    ],
    "idle_evening": [
        {"bn": "🌆 সন্ধ্যা হয়েছে! এক কাপ গরম চা দিই?\n(Evening time! Want a hot cup of tea?)", "en": "Evening time! Want a hot cup of tea?"},
        {"bn": "সূর্য ডুবছে... দিন শেষ হলো। কেমন গেলো আজকে?\n(Sun is setting... how was your day?)", "en": "Sun is setting... how was your day?"},
    ],
    "long_session": [
        {"bn": "তুমি অনেকক্ষণ ধরে কাজ করছো! একটু বিরতি নাও!\n(You've been working for so long! Take a break!)", "en": "You've been working for so long! Take a break!"},
        {"bn": "এত কাজ করলে মাথা গরম হয়ে যাবে! চা খাও!\n(Working this much will overheat your brain! Drink tea!)", "en": "Working this much will overheat you! Drink tea!"},
        {"bn": "🧙‍♀️ ম্যাজিশিয়ানরাও বিরতি নেয়! তুমিও নাও!\n(Even wizards take breaks! You should too!)", "en": "Even wizards take breaks! You should too!"},
    ],
    "annoyed": [
        {"bn": "😤 এতবার ক্লিক করলে কেন?! আমি মানুষ নাকি বাটন?!\n(Why clicking so many times?! Am I a button?!)", "en": "Why clicking so many times?! I'm not a button!"},
        {"bn": "⚡ আর ক্লিক করলে বিদ্যুৎ মারবো কিন্তু!\n(One more click and I'll zap you with lightning!)", "en": "One more click and I'll zap you with lightning!"},
        {"bn": "বাজ পড়বে! সাবধান! 😡\n(Thunder will strike! Be careful!)", "en": "Thunder will strike! Be careful!"},
    ],
    "click": [
        {"bn": "আরে! ধাক্কা দিলে কেন? জাদুর কলসি ফেটে যেত!", "en": "Hey! Why did you poke me? You could break my magic pot!"},
        {"bn": "কি খবর? কোনো সাহায্য লাগবে নাকি?", "en": "What's up? Need some help?"},
        {"bn": "হাহা, ওভাবে ধরলে আমার চুল এলোমেলো হয়ে যায়!", "en": "Haha, touching me like that messes up my hair!"},
        {"bn": "আব্রাকাডাব্রা! না না... ওটা তো অন্য দেশের মন্ত্র!", "en": "Abracadabra! Wait, no... that's a foreign spell!"},
        {"bn": "আমাকে বেশি বিরক্ত করলে ব্যাঙ বানিয়ে দেব কিন্তু!", "en": "If you annoy me too much, I will turn you into a frog!"}
    ],
    "drag": [
        {"bn": "ছেড়ে দাও! আমি পড়ে যাচ্ছি!", "en": "Let go! I am falling!"},
        {"bn": "ওরে বাবা! মাথা ঘুরছে!", "en": "Oh my! My head is spinning!"},
        {"bn": "ঝাড়ু ছাড়া উড়া বেশ কঠিন!", "en": "Flying without a broom is pretty hard!"},
        {"bn": "বাঁচাও! জাদুর নিয়ন্ত্রণ হারিয়েছি!", "en": "Help! I've lost control of my magic!"}
    ],
    "pet": [
        {"bn": "উফফ, অনেক আদর পেয়েছি! হিহিহি!", "en": "Oh, so much affection! Hehehe!"},
        {"bn": "খুব ভালো লাগছে... লক্ষ্মী সোনা!", "en": "Feels so good... sweet soul!"},
        {"bn": "তোমার হাতটা কি নরম! জাদুর ছোঁয়া আছে মনে হয়!", "en": "Your hand is so soft! Feels like a magical touch!"},
        {"bn": "আমি কিন্তু বিড়াল নই, ডাইনি! তবে আদর নিতে আপত্তি নেই...", "en": "I'm a witch, not a cat! But I don't mind the head pats..."}
    ],
    "cast_spell": [
        {"bn": "হুশ হুশ! সব জটলা কেটে যাক!", "en": "Hush hush! Let all constraints vanish!"},
        {"bn": "ঝাড়ু আর মন্ত্রের জোর, সাফ হোক মেমরির চোর!", "en": "Broom and spell align, clear the memory pipeline!"},
        {"bn": "চোখ বন্ধ করো, ম্যাজিক হচ্ছে!", "en": "Close your eyes, magic in progress!"},
        {"bn": "হিলিপিলিপতু! এবার কাজে মন দাও!", "en": "Hilipilipatu! Now focus on your work!"}
    ],
    "sleep": [
        {"bn": "ঘুম আসছে... ফু দিয়ে প্রদীপ নেভাও...", "en": "Feeling sleepy... blow out the lamp..."},
        {"bn": "জাদুর স্বপ্ন দেখছি... ডিস্টার্ব করবে না...", "en": "Dreaming magical dreams... do not disturb..."},
        {"bn": "ঘুমে চোখ লেগে আসছে... চা খেতে হবে জাগতে হলে...", "en": "Sleeping... need some tea to wake up..."}
    ],
    "alarm": [
        {"bn": "চা পানের সময় হয়েছে! গরম গরম লাল চা!", "en": "Time for tea! Hot black tea is ready!"},
        {"bn": "অ্যালার্ম বাজছে! উঠো জলদি!", "en": "Alarm ringing! Get up quickly!"},
        {"bn": "কাজ বন্ধ করো! এবার একটু জিরিয়ে নাও!", "en": "Stop working! Take a little break now!"}
    ],
    "todo_complete": [
        {"bn": "সাবাশ! কাজটা শেষ করে ফেলেছ!", "en": "Well done! You've finished the task!"},
        {"bn": "বাহ! তুমি তো জাদুকরের চেয়েও ফাস্ট!", "en": "Wow! You are faster than a wizard!"},
        {"bn": "🎉 অসাধারণ! আরো একটা মন্ত্র জয় করেছো!\n(Amazing! You've conquered another spell!)", "en": "Amazing! You've conquered another spell!"},
    ],
    "pomodoro_done": [
        {"bn": "⏰ পোমোডোরো শেষ! এবার ৫ মিনিট বিশ্রাম নাও!\n(Pomodoro done! Rest for 5 minutes!)", "en": "Pomodoro done! Rest for 5 minutes!"},
        {"bn": "🍅 একটা টমেটো শেষ! দারুণ কাজ করেছো!\n(One tomato done! Great work!)", "en": "One tomato done! Great work!"},
    ],
    "break_suggestion": [
        {"bn": "👁️ চোখে একটু পানি দাও আর দূরে তাকাও!\n(Splash water on your eyes and look far!)", "en": "Splash water on your eyes and look far away!"},
        {"bn": "🙆‍♀️ হাত-পা একটু ছড়িয়ে দাও! স্ট্রেচ করো!\n(Stretch your arms and legs!)", "en": "Stretch your arms and legs!"},
        {"bn": "💧 এক গ্লাস পানি খাও! শরীর ঠান্ডা রাখো!\n(Drink a glass of water! Keep your body cool!)", "en": "Drink a glass of water!"},
        {"bn": "🚶 একটু হেঁটে আসো! রক্ত চলাচল ভালো হবে!\n(Take a short walk! Improve circulation!)", "en": "Take a short walk to improve circulation!"},
    ],
    "task_due": [
        {"bn": "কাজ মনে আছে? সময় হয়ে গেছে!", "en": "Don't forget your task — it's time!"},
        {"bn": "একটা কাজ বাকি আছে! চলো শেষ করি!", "en": "A task is waiting! Let's finish it!"},
        {"bn": "রিমাইন্ডার! তোমার টাস্ক এখন করার সময়!", "en": "Reminder! That task is due now!"},
    ],
    "crying": [
        {"bn": "😭 উঁহুহু... কেউ আমাকে ভালোবাসে না!\n(Sniff... nobody loves me!)", "en": "Sniff... nobody loves me!"},
        {"bn": "💧 কান্না পাচ্ছে... কেন জানি না...\n(Feeling like crying... don't know why...)", "en": "Feeling like crying... don't know why..."},
        {"bn": "😢 একটু আদর করো... মন খারাপ আছে!\n(Give me a hug... I'm feeling sad!)", "en": "Give me a hug... I'm feeling sad!"},
    ],
    "eating": [
        {"bn": "🥪 ম্মম! এই স্যান্ডউইচটা অনেক মজাদার!\n(Mmm! This sandwich is so tasty!)", "en": "Mmm! This sandwich is so tasty!"},
        {"bn": "খিদা পেয়েছিল! একটু খেয়ে নিই...\n(I was hungry! Let me eat a bit...)", "en": "I was hungry! Let me eat a bit..."},
        {"bn": "🍔 তুমিও খেয়েছো তো? না খেলে শক্তি পাবে না!\n(Have you eaten too? You need energy!)", "en": "Have you eaten too? You need energy!"},
    ],
    "waving": [
        {"bn": "👋 হ্যালো হ্যালো! কেমন আছো বলো?\n(Hello hello! How are you doing?)", "en": "Hello hello! How are you doing?"},
        {"bn": "হাই! আমি এখানেই আছি! ভুলে যাওনি তো?\n(Hi! I'm right here! You haven't forgotten me?)", "en": "Hi! I'm right here! You haven't forgotten me?"},
        {"bn": "👋 হাত নাড়াচ্ছি... তুমিও নাড়াও!\n(I'm waving... you wave back!)", "en": "I'm waving... you wave back!"},
    ],
    "shocked": [
        {"bn": "😲 এইটা কী হলো?! আমি ভয় পেয়ে গেছি!\n(What just happened?! You startled me!)", "en": "What just happened?! You startled me!"},
        {"bn": "⚡ আরে বাবা! চমকে দিলে কেন?!\n(Oh my! Why did you scare me?!)", "en": "Oh my! Why did you scare me?!"},
        {"bn": "😱 হার্ট অ্যাটাক হয়ে যেত! কী ভয়!\n(I almost had a heart attack! So scary!)", "en": "I almost had a heart attack! So scary!"},
    ],
}


def get_speech_bubble(category, lang="mix"):
    lines = SPEECH_LINES.get(category, SPEECH_LINES["idle"])
    line = random.choice(lines)

    if lang == "bn":
        return line["bn"]
    elif lang == "en":
        return line["en"]
    else:  # mix: returns Bengali text with English translations sometimes, or just random
        return line["bn"] if random.random() > 0.4 else f"{line['bn']}\n({line['en']})"


def get_time_aware_speech(lang="mix"):
    """Returns speech category appropriate for current time of day."""
    import datetime
    hour = datetime.datetime.now().hour
    if 6 <= hour < 12:
        cat = "idle_morning"
    elif 12 <= hour < 18:
        cat = "idle_afternoon"
    elif 18 <= hour < 22:
        cat = "idle_evening"
    elif hour >= 22 or hour < 6:
        cat = "idle_night"
    else:
        cat = "idle"
    return get_speech_bubble(cat, lang)
