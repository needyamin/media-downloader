"""Runtime checks for the Anika desktop assistant package."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
ANIKA_DIR = REPO_ROOT / "src" / "desktop_tools" / "anika"


def _anika_import(name: str):
    anika_path = str(ANIKA_DIR)
    if anika_path not in sys.path:
        sys.path.insert(0, anika_path)
    return importlib.import_module(name)


def check_modules_import() -> None:
    modules = [
        "main",
        "app.config",
        "app.menu_actions",
        "app.ui_theme",
        "app.assets",
        "app.particles",
        "app.window_detector",
        "app.hotkey",
        "app.tray",
        "app.gui",
        "app.window_icon",
    ]
    for name in modules:
        _anika_import(name)
        print(f"OK import: {name}")


def check_menu_actions() -> None:
    menu_actions = _anika_import("app.menu_actions")
    keys = {k for k, _ in menu_actions.PET_TOOL_ACTIONS}
    keys |= {k for k, _ in menu_actions.PET_FORCE_ACTIONS}
    keys.add(menu_actions.PET_QUIT_ACTION[0])
    expected_force = {
        "action", "sleeping", "dance", "waving", "crying", "eating",
        "study", "tea", "broom", "blush", "laugh", "shocked", "peek", "focus", "chase", "hide",
    }
    if keys - {"spellbook", "timer", "magic_clean", "quit"} != expected_force:
        raise SystemExit(f"Unexpected menu action keys: {keys}")
    print("OK menu_actions: action keys")


def check_reminder_helpers() -> None:
    from datetime import datetime, timedelta

    config = _anika_import("app.config")
    if config.DEFAULT_CONFIG["break_stay_secs"] < config.MIN_BREAK_STAY_SECS:
        raise SystemExit("Default break stay is below the minimum")
    if config.clamp_break_stay_secs(8) != config.MIN_BREAK_STAY_SECS:
        raise SystemExit("Short stay seconds should clamp to the minimum")
    if config.clamp_break_interval_mins(0) != 0:
        raise SystemExit("Disabled break interval should stay 0")
    if config.session_reminder_milestone(59) != 0:
        raise SystemExit("Session reminder must wait for 60 minutes")
    if config.session_reminder_milestone(125) != 120:
        raise SystemExit("Session reminder should use whole-hour milestones")
    if not config.should_send_session_reminder(60, 0):
        raise SystemExit("First hour session reminder missing")
    if config.should_send_session_reminder(90, 60):
        raise SystemExit("Session reminder should not repeat before the next hour")
    if not config.should_send_session_reminder(120, 60):
        raise SystemExit("Second hour session reminder missing")

    now = datetime(2026, 9, 8, 13, 0, 0)
    if config.workday_period(now) != "afternoon":
        raise SystemExit("13:00 should be the afternoon workday slot")
    if config.workday_hours_left(now) != 5:
        raise SystemExit("Hours left in the workday look wrong")
    if config.default_task_slot(now) != "afternoon":
        raise SystemExit("Default task slot should follow the workday")
    due = config.due_from_preset("now", now=now)
    if due != "2026-09-08T13:20":
        raise SystemExit(f"Unexpected now preset: {due}")
    afternoon = config.due_from_preset("afternoon", now=now)
    if afternoon != "2026-09-08T16:00":
        raise SystemExit(f"Unexpected afternoon due: {afternoon}")
    evening = config.due_from_preset("eod", now=now)
    if evening != "2026-09-08T17:30":
        raise SystemExit(f"Unexpected end-of-day due: {evening}")
    late = config.due_from_preset("eod", now=datetime(2026, 9, 8, 19, 0, 0))
    if late != "2026-09-09T17:30":
        raise SystemExit(f"End of day should roll to tomorrow: {late}")
    morning = config.due_from_preset("morning", now=now)
    if morning != "2026-09-09T11:30":
        raise SystemExit(f"Past morning should roll to tomorrow: {morning}")
    if config.due_from_preset("30m", now=now) != "2026-09-08T13:30":
        raise SystemExit("Legacy 30m due preset should still work")
    if config.task_workday_bucket({"slot": "eod", "done": False, "due": evening}, now) != "eod":
        raise SystemExit("Task bucket should follow the workday slot")
    if config.workday_timer_preset("Deep")["secs"] != 50 * 60:
        raise SystemExit("Deep work block should be 50 minutes")
    parsed = config.parse_clock_text("3:30", now=now, meridian="PM")
    if parsed is None or parsed.hour != 15 or parsed.minute != 30:
        raise SystemExit("3:30 PM should be 15:30")
    morning = config.parse_clock_text("9:15", now=now, meridian="AM")
    if morning is None or morning.hour != 9 or morning.minute != 15:
        raise SystemExit("9:15 AM should stay in the morning")
    if config.default_meridian(now=now, slot="morning") != "AM":
        raise SystemExit("Morning slot should default to AM")
    custom_due, custom_slot = config.due_from_slot_and_clock("afternoon", "4:00", now=now, meridian="PM")
    if custom_due != "2026-09-08T16:00" or custom_slot != "afternoon":
        raise SystemExit(f"Custom task time failed: {custom_due} {custom_slot}")
    if config.clamp_custom_timer_mins(999) != 180:
        raise SystemExit("Custom timer should cap at 180 minutes")
    later_due, later_slot = config.due_from_slot_and_clock("later", "", now=now)
    if later_slot != "later" or not later_due.startswith("2026-09-09"):
        raise SystemExit("Tomorrow slot should land on the next day")
    compact = config.parse_clock_text("330", now=now, meridian="PM")
    if compact is None or compact.hour != 15 or compact.minute != 30:
        raise SystemExit("330 should become 3:30 PM")
    hint, mer = config.next_half_hour_parts(now)
    if hint != "1:30" or mer != "PM":
        raise SystemExit(f"Next half hour should be 1:30 PM, got {hint} {mer}")
    if config.suggested_workday_block(now) != "Deep":
        raise SystemExit("Afternoon should suggest Deep work")
    if "1:20 PM" not in config.ends_at_label(20 * 60, now):
        raise SystemExit("Timer end label should include AM/PM")

    overdue = {"text": "Write report", "done": False, "due": (now - timedelta(minutes=5)).isoformat(timespec="minutes")}
    if not config.should_remind_task(overdue, now):
        raise SystemExit("Overdue task should remind")
    overdue["reminded_at"] = now.isoformat(timespec="minutes")
    if config.should_remind_task(overdue, now):
        raise SystemExit("Task reminder should not spam immediately")
    overdue["reminded_at"] = (now - timedelta(minutes=31)).isoformat(timespec="minutes")
    if not config.should_remind_task(overdue, now):
        raise SystemExit("Task reminder should repeat after the cooldown")
    if config.task_is_due({"done": True, "due": overdue["due"]}, now):
        raise SystemExit("Completed tasks must not stay due")

    clock = config.format_clock_label(now)
    if "1:00:00 PM" not in clock and "01:00:00 PM" not in clock:
        raise SystemExit(f"Clock label looks wrong: {clock}")
    speech = config.get_clock_speech("en", now)
    if "1:00 PM" not in speech:
        raise SystemExit(f"Clock speech missing the time: {speech}")
    print("OK reminders: session, break, task due, clock")


def check_window_icon() -> None:
    window_icon = _anika_import("app.window_icon")
    icon_path = window_icon.resolve_app_icon_path()
    if not icon_path.is_file():
        raise SystemExit(f"App icon missing for Anika windows: {icon_path}")
    gui_src = (ANIKA_DIR / "app" / "gui.py").read_text(encoding="utf-8")
    if "apply_app_icon" not in gui_src or "install_app_icon_hook" not in gui_src:
        raise SystemExit("Anika GUI windows are not applying the app icon")
    pet_src = (ANIKA_DIR / "app" / "pet.py").read_text(encoding="utf-8")
    if "apply_app_icon" not in pet_src:
        raise SystemExit("Anika main window is not applying the app icon")
    print(f"OK window icon: {icon_path.name}")


def check_pet_reminder_api() -> None:
    pet = _anika_import("app.pet")
    required = (
        "_ensure_visible_for_alert",
        "_check_session_reminder",
        "_trigger_break_reminder",
        "_check_task_reminders",
        "_check_hourly_clock",
        "start_user_timer",
        "toggle_user_timer",
        "apply_workday_timer",
        "apply_custom_timer",
        "user_timer_snapshot",
        "open_spellbook",
        "open_timer",
    )
    missing = [name for name in required if not hasattr(pet.DesktopPet, name)]
    if missing:
        raise SystemExit(f"DesktopPet missing reminder APIs: {missing}")
    gui = _anika_import("app.gui")
    if not hasattr(gui, "show_timer_alert"):
        raise SystemExit("Timer alert helper missing")
    tray_src = (ANIKA_DIR / "app" / "tray.py").read_text(encoding="utf-8")
    for label in ("Today", "Workday"):
        if f'"{label}"' not in tray_src:
            raise SystemExit(f"Tray menu missing {label}")
    print("OK pet: reminder and clock APIs")


def check_theme_hub_match() -> None:
    ui_theme = _anika_import("app.ui_theme")
    theme = ui_theme.get_ui_theme()
    if theme["accent"] != "#2196F3" or theme["bg"] != "#ffffff":
        raise SystemExit(f"Hub theme mismatch: {theme}")
    config = _anika_import("app.config")
    gui_theme = config.get_gui_theme()
    if gui_theme["accent"] != "#2196F3":
        raise SystemExit(f"GUI theme mismatch: {gui_theme}")
    print("OK theme: hub-aligned colors")


def check_assets() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ANIKA_DIR)
    result = subprocess.run(
        [sys.executable, "-c", "from main import verify_assets; verify_assets()"],
        cwd=str(ANIKA_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise SystemExit((result.stderr or result.stdout or "verify_assets failed").strip())
    print("OK assets: verify_assets")


def main() -> None:
    if not ANIKA_DIR.is_dir():
        raise SystemExit(f"Anika directory missing: {ANIKA_DIR}")
    check_modules_import()
    check_menu_actions()
    check_reminder_helpers()
    check_window_icon()
    check_pet_reminder_api()
    check_theme_hub_match()
    check_assets()
    print("Anika checks passed.")


if __name__ == "__main__":
    main()
