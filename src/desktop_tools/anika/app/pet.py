import tkinter as tk
import ctypes
import random
import math
import os
import sys
import time

from app.config import (
    clamp_break_interval_mins,
    clamp_break_stay_secs,
    config_db,
    due_tasks_to_remind,
    format_due_label,
    get_clock_speech,
    get_personality,
    get_speech_bubble,
    get_time_aware_speech,
    load_tasks,
    pending_task_count,
    POMODORO_BREAK_SECS,
    POMODORO_WORK_SECS,
    save_tasks,
    session_memory,
    should_send_session_reminder,
)
from app.assets import AssetManager, BASE_SPRITE_HEIGHT
from app.edge_hide import (
    classify_edge_hide,
    hide_threshold_px,
    pointer_exit_side,
    sprite_offscreen_amounts as edge_sprite_offscreen_amounts,
    sprite_screen_bounds,
)
from app.particles import ParticleSystem
from app.window_detector import WindowDetector
from app.tray import TrayIcon
from app.hotkey import GlobalHotkey


# Windows API structure for getting the usable work area (excluding taskbar)
class RECT(ctypes.Structure):
    _fields_ = [
        ('left', ctypes.c_long),
        ('top', ctypes.c_long),
        ('right', ctypes.c_long),
        ('bottom', ctypes.c_long)
    ]


def get_work_area():
    if sys.platform == "win32":
        try:
            rect = RECT()
            ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
            return rect.left, rect.top, rect.right, rect.bottom
        except Exception as e:
            print(f"Error getting work area: {e}")
    return 0, 0, 1920, 1040


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_uint),
        ('dwTime', ctypes.c_uint)
    ]


def get_idle_duration():
    if sys.platform == "win32":
        try:
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return millis / 1000.0
        except:
            pass
    return 0.0


def play_sound(_sound_type):
    """Anika stays quiet — Windows system beeps are not used."""
    return


class DesktopPet(tk.Tk):
    def __init__(self):
        super().__init__()
        self._skip_auto_center = True

        # Load config & personality
        self.pet_config = config_db
        self.personality = get_personality()

        from app.window_icon import apply_app_icon, install_app_icon_hook

        install_app_icon_hook()
        apply_app_icon(self)

        # Windows styling configuration
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)

        # Transparent color key
        self.trans_color = "#123456"
        self.config_window_transparency()

        # Scale & window size (canvas must fit scaled sprite + speech bubble)
        self.base_width = BASE_SPRITE_HEIGHT + 140
        self.base_height = BASE_SPRITE_HEIGHT + 160
        self.update_dimensions()

        # Position at bottom-right of work area
        wl, wt, wr, wb = get_work_area()
        self.x = wr - self.width - 50
        self.y = wb - self.height

        self.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")

        # Canvas
        self.canvas = tk.Canvas(
            self, bg=self.trans_color, bd=0,
            highlightthickness=0, width=self.width, height=self.height
        )
        self.canvas.pack(fill="both", expand=True)

        # Sub-modules
        self.assets = AssetManager()
        self.particles = ParticleSystem(self.canvas)

        # Squash / stretch
        self.squash_x = 1.0
        self.squash_y = 1.0
        self.happy_time = 0.0

        # Pet state
        self.state = "idle"
        self.facing_left = True
        self.vx = 0.0
        self.vy = 0.0
        self.target_x = self.x
        self.target_y = self.y
        self.move_speed = 1.5

        # Perch: Y coordinate Anika is sitting on (window top or screen floor)
        self.perch_y = None   # None = use floor
        self.on_window_perch = False

        # Mouse head tracking (smooth interpolation)
        self.mouse_target_facing = True   # True = left
        self.mouse_lean = 0.0             # -1.0 (right) to +1.0 (left)

        # Drag velocity history for throw physics
        self._drag_history = []   # list of (x, y, timestamp)

        # Animation parameters
        self.anim_time = 0.0
        self.bobbing_height = 0.0
        self.tilt_angle = 0.0
        self.canvas_img_id = None

        # Visual layers (no shadow/aura - removed per user request)
        self.magic_circle_ids = []
        self.aura_id = None
        self.magic_circle_angle = 0.0

        # Drag & Drop
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_last_x = 0
        self.drag_last_y = 0
        self.drag_init_x = 0
        self.drag_init_y = 0
        self.is_dragging = False
        self._drag_hidden_timer = None
        self._edge_hide_side = None
        self._edge_return_phase = None
        self._edge_return_timer = 0.0
        self._edge_sneak_target_x = 0
        self._edge_jump_x = 0
        self._edge_sneak_target_y = 0
        self._edge_jump_y = 0
        self._edge_hide_min_drag_px = 80
        self._drag_cursor_offscreen = False
        self._drag_exit_side = None

        # Speech bubble
        self.speech_bubble_id = None
        self.speech_text_id = None
        self.speech_pointer_id = None
        self.speech_timer = None
        self.speech_color = "#ffffff"  # Dynamic bubble color

        # Boredom escalation tracker
        self.boredom_level = 0        # 0=normal 1=yawn 2=sleep 3=snore
        self.session_reminder_sent = False
        self._session_reminded_milestone = 0
        self._break_timer_job = None
        self._break_stay_job = None
        self._user_timer = {
            "remaining": POMODORO_WORK_SECS,
            "total": POMODORO_WORK_SECS,
            "running": False,
            "pomodoro": True,
            "is_break": False,
            "label": "Focus",
            "break_secs": POMODORO_BREAK_SECS,
            "work_secs": POMODORO_WORK_SECS,
            "work_label": "Focus",
            "job": None,
        }
        self._timer_listeners = []
        self._last_clock_hour = time.localtime().tm_hour

        # Fairy dust timer
        self.fairy_dust_timer = 0

        # Peek / hide state
        self.peek_edge = "left"
        self.peek_phase = "slide_in"
        self.peek_timer = 0.0
        self.peek_target_x = 0
        self.peek_exit_x = 0
        self.hide_timer = 0.0
        self.chase_timer = 0.0

        # Mouse event bindings
        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drag)
        self.canvas.bind("<Button-3>", self.show_context_menu)
        self.canvas.bind("<Enter>", self.on_mouse_enter)
        self.canvas.bind("<Leave>", self.on_mouse_leave)
        self.canvas.bind("<MouseWheel>", self.on_pet_scroll)

        # Context Menu
        self.menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 10))
        self.build_menu()

        # Window detector for perching
        self.win_detector = WindowDetector()
        self.win_detector.start()

        # System tray (skip when launched from Media Downloader — hub already has a tray)
        self._tray = None
        if not self._tray_disabled():
            self._tray = TrayIcon(lambda: self)
            self._tray.start()

        # Global hotkey
        self._hotkey = GlobalHotkey(
            config_db.get("hotkey") or "ctrl+shift+m",
            self._toggle_visibility
        )
        self._hotkey.start()
        self._visible = True

        # Draw initial frame
        self.render_pet()

        # Start loops
        self.update_loop()
        self.state_machine_loop()

        # Greet on startup with time-aware speech
        lang = self.pet_config.get("language")
        self.after(1000, lambda: self.show_speech_bubble(
            get_time_aware_speech(lang), color="#a78bfa"
        ))

        # Start session time monitor
        self.after(60000, self._check_session_reminder)

        # Start break reminder timer
        self._break_settings_signature = self._break_settings_tuple()
        self._start_break_timer()
        self.after(30000, self._poll_break_settings)
        self.after(20000, self._check_task_reminders)
        self.after(20000, self._check_hourly_clock)

        open_settings = os.environ.get("ANIKA_OPEN_SETTINGS", "") or os.environ.get(
            "YFUN_OPEN_SETTINGS", ""
        )
        if open_settings.strip().lower() in ("1", "true", "yes"):
            self.after(400, self.open_settings)

    # ─── Config & Dimensions ─────────────────────────────────────────
    @staticmethod
    def _tray_disabled() -> bool:
        flag = os.environ.get("ANIKA_NO_TRAY", "").strip().lower()
        return flag in ("1", "true", "yes")

    def config_window_transparency(self):
        self.configure(bg=self.trans_color)
        self.wm_attributes("-transparentcolor", self.trans_color)
        opacity = self.pet_config.get("opacity")
        self.attributes("-alpha", opacity)

    def update_dimensions(self, *, anchor_bottom=True):
        """Resize the transparent window to fit the scaled assistant character (not just the canvas)."""
        scale = float(self.pet_config.get("scale") or 1.4)
        scale = max(0.5, min(2.5, scale))

        char_h = int(BASE_SPRITE_HEIGHT * scale)
        # Square sprites; extra width covers wide poses and horizontal bob/tilt
        pad_side = int(70 * scale)
        pad_top = int(100 * scale)
        pad_bottom = int(28 * scale)

        new_w = max(int(self.base_width * scale), char_h + pad_side * 2)
        new_h = max(int(self.base_height * scale), char_h + pad_top + pad_bottom)

        old_w = int(getattr(self, "width", new_w))
        old_h = int(getattr(self, "height", new_h))

        if anchor_bottom and hasattr(self, "y"):
            self.y = int(self.y) - (new_h - old_h)
        if anchor_bottom and hasattr(self, "x"):
            self.x = int(self.x) - (new_w - old_w) // 2

        self.width = new_w
        self.height = new_h

        if hasattr(self, "canvas"):
            self.canvas.config(width=new_w, height=new_h)

        if hasattr(self, "canvas") and self.winfo_exists():
            wl, wt, wr, wb = get_work_area()
            self.x = min(max(wl, int(self.x)), max(wl, wr - new_w))
            self.y = min(max(wt, int(self.y)), max(wt, wb - new_h))
            self.geometry(f"{new_w}x{new_h}+{self.x}+{self.y}")
            self.update_idletasks()

    # ─── Context Menu ────────────────────────────────────────────────
    def build_menu(self):
        from app.menu_actions import populate_tk_context_menu

        self.menu.delete(0, "end")
        populate_tk_context_menu(self.menu, self)

    def show_context_menu(self, event):
        self.menu.post(event.x_root, event.y_root)

    # ─── Boundaries ──────────────────────────────────────────────────
    def get_boundaries(self):
        wl, wt, wr, wb = get_work_area()
        return wl, wt, wr - self.width, wb - self.height

    @staticmethod
    def _safe_randint(low, high):
        """random.randint that never raises when the range is empty or inverted."""
        lo = int(min(low, high))
        hi = int(max(low, high))
        if lo == hi:
            return lo
        return random.randint(lo, hi)

    # ─── Visibility for alerts ────────────────────────────────────────
    def _cancel_after(self, attr):
        job = getattr(self, attr, None)
        if not job:
            return
        try:
            self.after_cancel(job)
        except Exception:
            pass
        setattr(self, attr, None)

    def _ensure_visible_for_alert(self, *, center=False):
        """Bring Anika on-screen even if hidden, withdrawn, or edge-parked."""
        self._cancel_after("_drag_hidden_timer")
        self._edge_return_phase = None
        self._edge_hide_side = None
        self._visible = True
        try:
            self.deiconify()
            self.wm_attributes("-topmost", True)
            self.lift()
        except Exception:
            pass
        if center:
            wl, wt, wr, wb = get_work_area()
            self.x = int((wl + wr) / 2 - self.width / 2)
            self.y = int((wt + wb) / 2 - self.height / 2)
            try:
                self.geometry(f"+{self.x}+{self.y}")
            except Exception:
                pass

    # ─── Session Reminder ─────────────────────────────────────────────
    def _check_session_reminder(self):
        mins = session_memory.get_session_minutes()
        if should_send_session_reminder(mins, self._session_reminded_milestone):
            self._session_reminded_milestone = (mins // 60) * 60
            self.session_reminder_sent = True
            self._ensure_visible_for_alert()
            lang = self.pet_config.get("language")
            pending = pending_task_count()
            if lang == "en":
                msg = f"You've been working for {mins} minutes!\nTake a break!"
                if pending:
                    msg += f"\n{pending} task{'s' if pending != 1 else ''} still open."
            elif lang == "bn":
                msg = f"তুমি {mins} মিনিট ধরে কাজ করছো!\nএকটু বিরতি নাও!"
                if pending:
                    msg += f"\nএখনো {pending}টা কাজ বাকি।"
            else:
                msg = f"তুমি {mins} মিনিট ধরে কাজ করছো!\nএকটু বিরতি নাও!"
                if pending:
                    msg += f"\n{pending} task still open."
            self.show_speech_bubble(msg, color="#fbbf24", duration=5000)
            self.set_state("tea")
        self.after(60 * 1000, self._check_session_reminder)

    # ─── Break Reminder ───────────────────────────────────────────────
    def _break_settings_tuple(self):
        return (
            clamp_break_interval_mins(self.pet_config.get("break_interval_mins")),
            clamp_break_stay_secs(self.pet_config.get("break_stay_secs")),
        )

    def _poll_break_settings(self):
        """Pick up break timing saved by the hub or another process."""
        try:
            self.pet_config.load()
        except Exception:
            pass
        signature = self._break_settings_tuple()
        if signature != self._break_settings_signature:
            self._break_settings_signature = signature
            self._start_break_timer()
        self.after(30000, self._poll_break_settings)

    def _start_break_timer(self):
        """Schedule the next break reminder based on the configured interval."""
        self._cancel_after("_break_timer_job")
        try:
            self.pet_config.load()
        except Exception:
            pass
        interval_mins = clamp_break_interval_mins(self.pet_config.get("break_interval_mins"))
        self._break_settings_signature = self._break_settings_tuple()
        if interval_mins > 0:
            self._break_timer_job = self.after(int(interval_mins * 60000), self._trigger_break_reminder)

    def _trigger_break_reminder(self):
        """Anika pops up in the centre of screen to announce a break."""
        try:
            self.pet_config.load()
        except Exception:
            pass
        lang = self.pet_config.get("language")
        stay_secs = clamp_break_stay_secs(self.pet_config.get("break_stay_secs"))
        self._cancel_after("_break_stay_job")
        self._ensure_visible_for_alert(center=True)

        self.set_state("waving")
        self.particles.add_hearts(self.width / 2, self.height / 2, count=10)
        play_sound("alarm")

        if lang == "en":
            msg = f"Break time! Rest for a moment! ({stay_secs}s)"
        elif lang == "bn":
            msg = f"বিরতির সময়! একটু বিশ্রাম নাও! ({stay_secs}s)"
        else:
            msg = f"Break time! বিরতি নাও! ({stay_secs}s)"

        self.show_speech_bubble(msg, color="#fbbf24", duration=stay_secs * 1000)

        def _finish_break_popup():
            if self.state == "waving":
                self.set_state("idle")
            self._break_stay_job = None
            self._start_break_timer()

        self._break_stay_job = self.after(stay_secs * 1000, _finish_break_popup)

    # ─── Task reminders ───────────────────────────────────────────────
    def _check_task_reminders(self):
        try:
            tasks = load_tasks()
            due = due_tasks_to_remind(tasks)
            if due:
                now_iso = time.strftime("%Y-%m-%dT%H:%M")
                for task in due:
                    task["reminded_at"] = now_iso
                try:
                    save_tasks(tasks)
                except Exception:
                    pass
                self._ensure_visible_for_alert()
                lang = self.pet_config.get("language")
                first = due[0].get("text") or "task"
                extra = len(due) - 1
                if lang == "en":
                    msg = f"Don't forget: {first}"
                    if extra:
                        msg += f"\n+{extra} more due."
                elif lang == "bn":
                    msg = f"কাজ মনে আছে? {first}"
                    if extra:
                        msg += f"\nআরো {extra}টা কাজের সময় হয়েছে।"
                else:
                    msg = get_speech_bubble("task_due", lang)
                    msg += f"\n{first}"
                    if extra:
                        msg += f"\n+{extra} more."
                due_lbl = format_due_label(due[0].get("due"))
                if due_lbl:
                    msg += f"\n({due_lbl})"
                self.show_speech_bubble(msg, color="#fde68a", duration=6000)
                self.set_state("waving")
                play_sound("alarm")
        except Exception:
            pass
        self.after(60 * 1000, self._check_task_reminders)

    # ─── Hourly clock ─────────────────────────────────────────────────
    def _check_hourly_clock(self):
        try:
            if self.pet_config.get("clock_announce"):
                hour = time.localtime().tm_hour
                if hour != self._last_clock_hour:
                    self._last_clock_hour = hour
                    if session_memory.get_session_minutes() >= 2:
                        self._ensure_visible_for_alert()
                        lang = self.pet_config.get("language")
                        self.show_speech_bubble(get_clock_speech(lang), color="#a78bfa", duration=4000)
                else:
                    self._last_clock_hour = hour
            else:
                self._last_clock_hour = time.localtime().tm_hour
        except Exception:
            pass
        self.after(20 * 1000, self._check_hourly_clock)

    # ─── User timer / clock ───────────────────────────────────────────
    def user_timer_snapshot(self):
        timer = self._user_timer
        return {
            "remaining": int(timer.get("remaining") or 0),
            "total": int(timer.get("total") or 0),
            "running": bool(timer.get("running")),
            "pomodoro": bool(timer.get("pomodoro")),
            "is_break": bool(timer.get("is_break")),
            "label": timer.get("label") or "Focus",
            "break_secs": int(timer.get("break_secs") or POMODORO_BREAK_SECS),
            "pomodoro_count": int(self.pet_config.get("pomodoro_count") or 0),
        }

    def add_timer_listener(self, callback):
        if callback not in self._timer_listeners:
            self._timer_listeners.append(callback)

    def remove_timer_listener(self, callback):
        try:
            self._timer_listeners.remove(callback)
        except ValueError:
            pass

    def _notify_timer_listeners(self):
        snap = self.user_timer_snapshot()
        stale = []
        for callback in self._timer_listeners:
            try:
                callback(snap)
            except Exception:
                stale.append(callback)
        for callback in stale:
            self.remove_timer_listener(callback)

    def set_user_timer_duration(self, seconds, *, pomodoro=False, is_break=False, label=None, break_secs=None):
        seconds = max(1, int(seconds))
        self._cancel_after_timer_job()
        updates = {
            "remaining": seconds,
            "total": seconds,
            "running": False,
            "pomodoro": bool(pomodoro),
            "is_break": bool(is_break),
        }
        if label is not None:
            updates["label"] = label
            if not is_break:
                updates["work_label"] = label
                updates["work_secs"] = seconds
        if break_secs is not None:
            updates["break_secs"] = max(0, int(break_secs))
        self._user_timer.update(updates)
        self._notify_timer_listeners()

    def apply_workday_timer(self, name: str):
        from app.config import workday_timer_preset

        preset = workday_timer_preset(name)
        self.set_user_timer_duration(
            preset["secs"],
            pomodoro=bool(preset["auto_break"]),
            is_break=False,
            label=name,
            break_secs=preset["break_secs"],
        )

    def apply_custom_timer(self, minutes):
        from app.config import clamp_custom_timer_mins

        minutes = clamp_custom_timer_mins(minutes)
        self.pet_config.set("last_custom_timer_mins", minutes)
        self.set_user_timer_duration(
            minutes * 60,
            pomodoro=False,
            is_break=False,
            label=f"{minutes}m",
            break_secs=0,
        )

    def _cancel_after_timer_job(self):
        job = self._user_timer.get("job")
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._user_timer["job"] = None

    def start_user_timer(self, seconds=None, *, pomodoro=None, is_break=None):
        if seconds is not None:
            seconds = max(1, int(seconds))
            self._user_timer["remaining"] = seconds
            self._user_timer["total"] = seconds
        if pomodoro is not None:
            self._user_timer["pomodoro"] = bool(pomodoro)
        if is_break is not None:
            self._user_timer["is_break"] = bool(is_break)
        if int(self._user_timer.get("remaining") or 0) <= 0:
            default = int(self._user_timer.get("work_secs") or POMODORO_WORK_SECS)
            if self._user_timer.get("is_break"):
                default = int(self._user_timer.get("break_secs") or POMODORO_BREAK_SECS)
            self._user_timer["remaining"] = default
            self._user_timer["total"] = default
        self._cancel_after_timer_job()
        self._user_timer["running"] = True
        self._user_timer["job"] = self.after(1000, self._tick_user_timer)
        self._notify_timer_listeners()

    def pause_user_timer(self):
        self._cancel_after_timer_job()
        self._user_timer["running"] = False
        self._notify_timer_listeners()

    def toggle_user_timer(self):
        if self._user_timer.get("running"):
            self.pause_user_timer()
            return
        self.start_user_timer()

    def _tick_user_timer(self):
        if not self._user_timer.get("running"):
            self._user_timer["job"] = None
            return
        remaining = int(self._user_timer.get("remaining") or 0) - 1
        self._user_timer["remaining"] = max(0, remaining)
        if remaining > 0:
            self._user_timer["job"] = self.after(1000, self._tick_user_timer)
            self._notify_timer_listeners()
            return
        self._user_timer["running"] = False
        self._user_timer["job"] = None
        self._notify_timer_listeners()
        self._fire_user_timer()

    def _fire_user_timer(self):
        play_sound("alarm")
        self._ensure_visible_for_alert()
        lang = self.pet_config.get("language")
        pomodoro = bool(self._user_timer.get("pomodoro"))
        is_break = bool(self._user_timer.get("is_break"))
        if pomodoro and not is_break:
            total_pomo = int(self.pet_config.get("pomodoro_count") or 0) + 1
            self.pet_config.set("pomodoro_count", total_pomo)
            self.particles.add_fireworks_burst(self.width / 2, self.height / 2, count=20)
            self.show_speech_bubble(get_speech_bubble("pomodoro_done", lang), color="#fde68a", duration=5000)
            self.after(5000, lambda: self.show_speech_bubble(
                get_speech_bubble("break_suggestion", lang), color="#bbf7d0", duration=5000
            ))
            break_secs = int(self._user_timer.get("break_secs") or POMODORO_BREAK_SECS)
            self._user_timer["label"] = "Break"
            self.start_user_timer(break_secs, pomodoro=True, is_break=True)
            return
        if pomodoro and is_break:
            work_secs = int(self._user_timer.get("work_secs") or POMODORO_WORK_SECS)
            work_label = self._user_timer.get("work_label") or "Focus"
            self.set_user_timer_duration(
                work_secs,
                pomodoro=True,
                is_break=False,
                label=work_label,
                break_secs=int(self._user_timer.get("break_secs") or POMODORO_BREAK_SECS),
            )
            self.show_speech_bubble(get_speech_bubble("alarm", lang), color="#fde68a", duration=5000)
            self._show_timer_popup(break_over=True)
            return
        self.set_state("waving")
        self.particles.add_sparks(self.width / 2, self.height / 2, count=30)
        label = self._user_timer.get("label") or ""
        self.show_speech_bubble(get_speech_bubble("alarm", lang), color="#fde68a", duration=5000)
        self._show_timer_popup(break_over=False, label=label)

    def _show_timer_popup(self, *, break_over=False, label=""):
        try:
            from app.gui import show_timer_alert

            show_timer_alert(self, break_over=break_over, label=label)
        except Exception:
            pass

    # ─── Drag & Drop ─────────────────────────────────────────────────
    def _edge_hide_delay_ms(self) -> int:
        mins = float(self.pet_config.get("edge_hide_mins") or 5)
        mins = max(1.0, min(60.0, mins))
        return int(mins * 60 * 1000)

    def _sprite_metrics(self, img_key="dragged"):
        scale = float(self.pet_config.get("scale") or 1.4)
        flip_h = not self.facing_left
        tk_img = self.assets.get_image(img_key, scale, flip_h, self.squash_x, self.squash_y)
        if tk_img:
            return tk_img.width(), tk_img.height()
        char_size = int(BASE_SPRITE_HEIGHT * scale)
        return char_size, char_size

    def _sprite_offscreen_amounts(self, wl, wt, wr, wb):
        char_w, char_h = self._sprite_metrics("dragged")
        sl, st, sr, sb = sprite_screen_bounds(
            float(self.x), float(self.y), float(self.width), float(self.height),
            float(char_w), float(char_h),
        )
        return edge_sprite_offscreen_amounts(sl, st, sr, sb, wl, wt, wr, wb)

    def _hide_offscreen_threshold(self) -> int:
        _, char_h = self._sprite_metrics("dragged")
        frac = float(self.pet_config.get("edge_hide_offscreen_frac") or 0.85)
        return hide_threshold_px(char_h, frac)

    def _max_y_above_taskbar(self, wb) -> int:
        return wb - self.height

    def _clamp_on_screen(self) -> None:
        wl, wt, wr, wb = get_work_area()
        max_x = wr - self.width
        max_y = self._max_y_above_taskbar(wb)
        self.x = min(max(wl, int(self.x)), max(wl, max_x))
        self.y = min(max(wt, int(self.y)), max(wt, max_y))
        self.geometry(f"+{self.x}+{self.y}")

    def _classify_drag_drop(self, wl, wt, wr, wb):
        left_off, right_off, top_off, _bottom_off = self._sprite_offscreen_amounts(wl, wt, wr, wb)
        bl, bt, br, bb = self.get_boundaries()
        dist = math.sqrt((self.x - self.drag_init_x) ** 2 + (self.y - self.drag_init_y) ** 2)
        return classify_edge_hide(
            edge_hide_enabled=bool(self.pet_config.get("edge_hide_enabled")),
            cursor_offscreen=self._drag_cursor_offscreen,
            exit_side=self._drag_exit_side,
            dist_moved=dist,
            min_drag_px=self._edge_hide_min_drag_px,
            left_off=left_off,
            right_off=right_off,
            top_off=top_off,
            threshold_px=self._hide_offscreen_threshold(),
            at_taskbar=self.y >= bb - 6,
        )

    def _anchor_on_taskbar(self, wl, wt, wr, wb) -> None:
        self.is_anchored = True
        self.on_window_perch = False
        self.vx = 0
        self.vy = 0
        self.x = min(max(wl, self.x), max(wl, wr - self.width))
        self.y = wb - self.height
        self.geometry(f"+{self.x}+{self.y}")
        self.set_state("tea")
        self.show_speech_bubble(
            "আমি এখানেই বসে থাকবো!\n(I'll sit right here above the taskbar!)",
            color="#bbf7d0",
            duration=2500,
        )

    def _begin_side_edge_hide(self, side: str) -> None:
        self._edge_hide_side = side
        self.is_anchored = False
        self.on_window_perch = False
        self.vx = 0
        self.vy = 0

        wl, wt, wr, wb = get_work_area()
        if side == "left":
            self.x = wl - self.width + 5
            self.facing_left = False
        elif side == "right":
            self.x = wr - 5
            self.facing_left = True
        else:
            self.x = min(max(wl, self.x), max(wl, wr - self.width))
            self.y = wt - self.height + 5
        if side in ("left", "right"):
            self.y = self._safe_randint(max(wt, wb - self.height - 220), max(wt, wb - self.height))
        self.geometry(f"+{self.x}+{self.y}")
        self.clear_speech_bubble()
        self.set_state("drag_hidden")

        if self._drag_hidden_timer:
            try:
                self.after_cancel(self._drag_hidden_timer)
            except Exception:
                pass
        self._drag_hidden_timer = self.after(self._edge_hide_delay_ms(), self._edge_hide_sneak_return)

    def _edge_hide_sneak_return(self) -> None:
        if self.state != "drag_hidden":
            return

        side = self._edge_hide_side or "left"
        wl, wt, wr, wb = get_work_area()
        self._drag_hidden_timer = None
        self._edge_return_phase = "sneak_in"
        self._edge_return_timer = 0.0
        self.peek_edge = side

        sneak_amount = min(160, max(90, self.width // 2))
        if side == "left":
            self.x = wl - self.width + 8
            self._edge_sneak_target_x = wl - self.width + sneak_amount
            self._edge_jump_x = min(wr - self.width, wl + 40)
            self.facing_left = False
        elif side == "right":
            self.x = wr - 8
            self._edge_sneak_target_x = wr - sneak_amount
            self._edge_jump_x = max(wl, wr - self.width - 40)
            self.facing_left = True
        else:
            self.y = wt - self.height + 8
            self._edge_sneak_target_y = wt - self.height + sneak_amount
            self._edge_jump_y = min(wb - self.height, wt + 40)
            self.x = min(max(wl, self.x), max(wl, wr - self.width))

        if side in ("left", "right"):
            self.y = self._safe_randint(max(wt + 20, wb - self.height - 180), max(wt + 20, wb - self.height))
        self.vx = 0
        self.vy = 0
        self.set_state("edge_return")
        self.geometry(f"+{self.x}+{self.y}")

    def _finish_edge_jump_scare(self) -> None:
        lang = self.pet_config.get("language")
        if lang == "en":
            msg = "😲 BOO! Did I scare you?"
        elif lang == "bn":
            msg = "😲 ভূত! চমকে গেলে তো!"
        else:
            msg = "😲 BOO! চমকে গেলে? / Did I scare you?"
        play_sound("error")
        self.particles.add_lightning_bolt(self.width / 2, self.height / 2 - 20, count=6)
        self.particles.add_sparks(self.width / 2, self.height / 2, count=14)
        self.set_state("shocked")
        self.show_speech_bubble(msg, color="#fca5a5", duration=2800)
        self._edge_return_phase = "done"
        self._edge_hide_side = None
    def start_drag(self, event):
        if self._drag_hidden_timer:
            try:
                self.after_cancel(self._drag_hidden_timer)
            except Exception:
                pass
            self._drag_hidden_timer = None
        self.is_dragging = True
        self._drag_cursor_offscreen = False
        self._drag_exit_side = None
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.drag_init_x = self.winfo_x()
        self.drag_init_y = self.winfo_y()
        self.drag_last_x = self.winfo_x()
        self.drag_last_y = self.winfo_y()
        self._drag_history = []   # reset velocity history
        self.perch_y = None       # leave perch when grabbed
        self.on_window_perch = False
        self.set_state("drag")
        self.clear_speech_bubble()
        self.show_speech_bubble(get_speech_bubble("drag", self.pet_config.get("language")), duration=1500)

    def on_drag(self, event):
        if not self.is_dragging:
            return
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        self.x = self.winfo_x() + dx
        self.y = self.winfo_y() + dy

        if self.pet_config.get("boundary_keep"):
            screen_wl, screen_wt, screen_wr, screen_wb = get_work_area()
            max_y = self._max_y_above_taskbar(screen_wb)
            bl, bt, br, bb = self.get_boundaries()

            pos = self._safe_pointer_xy()
            if pos is None:
                px, py = self.x + event.x, self.y + event.y
            else:
                px, py = pos

            exit_side = pointer_exit_side(px, py, screen_wl, screen_wt, screen_wr, screen_wb)
            allow_offscreen = self.pet_config.get("edge_hide_enabled") and exit_side is not None

            if allow_offscreen:
                self._drag_cursor_offscreen = True
                self._drag_exit_side = exit_side
                peek = max(28, int(BASE_SPRITE_HEIGHT * float(self.pet_config.get("scale") or 1.4) * 0.08))
                if exit_side == "left":
                    self.x = max(screen_wl - self.width + peek, self.x)
                elif exit_side == "right":
                    self.x = min(screen_wr - peek, self.x)
                elif exit_side == "top":
                    self.y = max(screen_wt - self.height + peek, self.y)
                self.y = min(self.y, max_y)
            else:
                self.x = max(bl, min(self.x, br))
                self.y = max(bt, min(self.y, bb))

        self.geometry(f"+{self.x}+{self.y}")

        # Track velocity history (last 8 frames)
        now = time.time()
        self._drag_history.append((self.x, self.y, now))
        if len(self._drag_history) > 8:
            self._drag_history.pop(0)

        self.drag_last_x = self.x
        self.drag_last_y = self.y

    def stop_drag(self, event):
        self.is_dragging = False
        session_memory.record_interaction()

        # Check for annoyed rapid clicking
        if session_memory.is_rapid_clicking():
            self._trigger_annoyed()
            return

        # Compute throw velocity from drag history
        if len(self._drag_history) >= 2:
            x0, y0, t0 = self._drag_history[0]
            x1, y1, t1 = self._drag_history[-1]
            dt = max(t1 - t0, 0.001)
            self.vx = (x1 - x0) / dt * 0.06   # scale to pixel/frame
            self.vy = (y1 - y0) / dt * 0.06
            # Cap throw speed
            self.vx = max(-18, min(18, self.vx))
            self.vy = max(-18, min(18, self.vy))
        self._drag_history = []

        dist_moved = math.sqrt((self.x - self.drag_init_x) ** 2 + (self.y - self.drag_init_y) ** 2)
        if dist_moved < 5:
            self.vx = 0
            self.vy = 0
            # Simple click — check hide state first
            if self.state == "hide":
                self.particles.add_hearts(self.width / 2, self.height / 2, count=15)
                self.show_speech_bubble("😂 তুমি আমাকে খুঁজে পেয়েছো!\n(You found me!)", duration=3000)
                wl, wt, wr, wb = self.get_boundaries()
                if self.peek_edge == "left":
                    self.x += 100
                elif self.peek_edge == "right":
                    self.x -= 100
                elif self.peek_edge == "top":
                    self.y += 100
                self.geometry(f"+{self.x}+{self.y}")
                self.set_state("laugh")
                return

            play_sound("click")

            # Personality-weighted random click reaction
            roll = random.random()
            self.particles.add_sparks(self.width / 2, self.height / 2, count=10)

            if roll < 0.25:
                self.set_state("blush")
            elif roll < 0.45:
                self.set_state("laugh")
            elif roll < 0.60:
                self.set_state("dance")
            elif roll < 0.75:
                self.set_state("broom")
            elif roll < 0.90:
                self.set_state("action")
            else:
                self.set_state("shocked")
                self.show_speech_bubble(
                    "😲 ওরে বাবারে! চমকে দিলে তো!\n(Oh my! You startled me!)", duration=2000
                )
        else:
            wl, wt, wr, wb = get_work_area()
            drop = None
            if self.pet_config.get("edge_hide_enabled"):
                drop = self._classify_drag_drop(wl, wt, wr, wb)
            else:
                bl, bt, br, bb = self.get_boundaries()
                if dist_moved >= self._edge_hide_min_drag_px and self.y >= bb - 6:
                    drop = "taskbar"

            if drop == "taskbar":
                self._anchor_on_taskbar(wl, wt, wr, wb)
                return
            if drop == "hide_left":
                self._begin_side_edge_hide("left")
                return
            if drop == "hide_right":
                self._begin_side_edge_hide("right")
                return
            if drop == "hide_top":
                self._begin_side_edge_hide("top")
                return

            self.is_anchored = False

            if self.pet_config.get("gravity_enabled"):
                self.state = "idle"
            else:
                self.set_state("idle")

    def _trigger_annoyed(self):
        """Anika gets annoyed from rapid clicking."""
        self.particles.add_lightning_bolt(self.width / 2, self.height / 2 - 20, count=5)
        self.particles.add_sparks(self.width / 2, self.height / 2, count=8)
        self.show_speech_bubble(
            get_speech_bubble("annoyed", self.pet_config.get("language")),
            color="#ef4444", duration=3000
        )
        self.set_state("shocked")
        play_sound("error")

    # ─── Pet (Scroll) ──────────────────────────────────────────────
    def on_mouse_enter(self, event):
        pass

    def on_mouse_leave(self, event):
        pass

    def on_pet_scroll(self, event):
        self.particles.add_hearts(self.width / 2, self.height / 2 + 10, count=3)
        self.happy_time = 1.8
        if random.random() < 0.35:
            self.show_speech_bubble(
                get_speech_bubble("pet", self.pet_config.get("language")),
                color="#fb7185", duration=2000
            )

    # ─── State Machine ────────────────────────────────────────────────
    def set_state(self, state):
        self.state = state
        self.anim_time = 0.0

        if state == "idle":
            self.vx = 0
            self.vy = 0
            self._clear_magic_circle()
        elif state == "action":
            self.vx = 0
            self.vy = 0
            self.particles.add_sparks(self.width / 2, self.height / 2 + 10, count=20)
            self.particles.add_magic_circle_sparkles(self.width / 2, self.height - 30, count=10)
            self.show_speech_bubble(
                get_speech_bubble("cast_spell", self.pet_config.get("language")),
                color="#a78bfa", duration=2500
            )
            play_sound("spell")
            self.after(2500, lambda: self.set_state("idle") if self.state == "action" else None)
        elif state == "sleeping":
            self.vx = 0
            self.vy = 0
            self._clear_magic_circle()
            self.show_speech_bubble(
                get_speech_bubble("sleep", self.pet_config.get("language")),
                color="#c4b5fd", duration=3000
            )
        elif state == "dance":
            self.vx = 0
            self.vy = 0
            self.particles.add_sparks(self.width / 2, self.height / 2 + 10, count=12)
            self.particles.add_rainbow_ribbon(self.width / 2, self.height / 2, count=6)
            self.show_speech_bubble(
                "💃 হিহি, আমি একটু নেচে নিই!\n(Let me dance a bit!)",
                color="#f0abfc", duration=3000
            )
            self.after(4500, lambda: self.set_state("idle") if self.state == "dance" else None)
        elif state == "study":
            self.vx = 0
            self.vy = 0
            self.show_speech_bubble(
                "📖 মন্ত্রগুলো একটু ঝালিয়ে নিই...\n(Reviewing my magic spells...)",
                color="#93c5fd", duration=3500
            )
            self.after(6000, lambda: self.set_state("idle") if self.state == "study" else None)
        elif state == "tea":
            self.vx = 0
            self.vy = 0
            self.show_speech_bubble(
                "🍵 একটু চা খাই! মাটির কাপে গরম চা...\n(Ah, sipping hot tea in a clay cup!)",
                color="#fde68a", duration=3500
            )
            self.after(6000, lambda: self.set_state("idle") if self.state == "tea" else None)
        elif state == "broom":
            self.vy = 0
            wl, wt, wr, wb = self.get_boundaries()
            self.y = wb - 60
            self.vx = -4.5 if self.facing_left else 4.5
            self.show_speech_bubble(
                "🧹 জুম জুম! আমার ঝাড়ু কিন্তু খুব ফাস্ট!\n(Zoom zoom! My broom is super fast!)",
                color="#bbf7d0", duration=3000
            )
            self.after(8000, lambda: self.set_state("idle") if self.state == "broom" else None)
        elif state == "blush":
            self.vx = 0
            self.vy = 0
            self.particles.add_hearts(self.width / 2, self.height / 2 + 10, count=7)
            self.show_speech_bubble(
                get_speech_bubble("click", self.pet_config.get("language")),
                color="#fda4af", duration=2500
            )
            self.after(2500, lambda: self.set_state("idle") if self.state == "blush" else None)
        elif state == "laugh":
            self.vx = 0
            self.vy = 0
            self.particles.add_sparks(self.width / 2, self.height / 2 + 10, count=10)
            self.show_speech_bubble(
                "😂 হিহিহি! খুব মজা পেলাম!\n(Heehee! That was so funny!)",
                color="#fde68a", duration=2500
            )
            self.after(2500, lambda: self.set_state("idle") if self.state == "laugh" else None)
        elif state == "shocked":
            self.vx = 0
            self.vy = 0
            self.show_speech_bubble(
                get_speech_bubble("shocked", self.pet_config.get("language")),
                color="#fca5a5", duration=2500
            )
            self.after(2500, lambda: self.set_state("idle") if self.state == "shocked" else None)
        elif state == "waving":
            self.vx = 0
            self.vy = 0
            self.particles.add_hearts(self.width / 2, self.height / 2 + 10, count=5)
            self.show_speech_bubble(
                get_speech_bubble("waving", self.pet_config.get("language")),
                color="#bbf7d0", duration=3000
            )
            self.after(3500, lambda: self.set_state("idle") if self.state == "waving" else None)
        elif state == "crying":
            self.vx = 0
            self.vy = 0
            self.show_speech_bubble(
                get_speech_bubble("crying", self.pet_config.get("language")),
                color="#93c5fd", duration=4000
            )
            self.after(4500, lambda: self.set_state("idle") if self.state == "crying" else None)
        elif state == "eating":
            self.vx = 0
            self.vy = 0
            self.particles.add_sparks(self.width / 2, self.height / 2, count=5)
            self.show_speech_bubble(
                get_speech_bubble("eating", self.pet_config.get("language")),
                color="#fde68a", duration=4000
            )
            self.after(4500, lambda: self.set_state("idle") if self.state == "eating" else None)
        elif state == "peek":
            self.vx = 0
            self.vy = 0
            self.clear_speech_bubble()
            wl, wt, wr, wb = get_work_area()
            self.peek_edge = "left" if random.random() < 0.5 else "right"
            self.peek_phase = "slide_in"
            self.peek_timer = 0.0
            if self.peek_edge == "left":
                self.x = wl - self.width + 10
                self.peek_target_x = wl - self.width + 140
                self.peek_exit_x = wl + 20
                self.facing_left = False
            else:
                self.x = wr - 10
                self.peek_target_x = wr - 140
                self.peek_exit_x = wr - self.width - 20
                self.facing_left = True
            self.y = wb - self.height
            self.geometry(f"+{self.x}+{self.y}")
        elif state == "focus":
            self.vx = 0
            self.vy = 0
            self._clear_magic_circle()
            wl, wt, wr, wb = get_work_area()
            self.x = int((wl + wr) / 2 - self.width / 2)
            self.y = int((wt + wb) / 2 - self.height / 2)
            self.geometry(f"+{self.x}+{self.y}")
            self.particles.add_hearts(self.width / 2, self.height / 2, count=12)
            self.show_speech_bubble(
                "🔍 আমি তোমাকে দেখছি!\n(I am looking at you!)",
                color="#67e8f9", duration=4000
            )
            self.after(4000, lambda: self.set_state("idle") if self.state == "focus" else None)
        elif state == "chase":
            self.chase_timer = 0.0
            self.show_speech_bubble(
                "🏃‍♀️ ধরবো তোমাকে!\n(I'm gonna catch you!)",
                color="#fb923c", duration=3000
            )
        elif state == "hide":
            self.vx = 0
            self.vy = 0
            self.clear_speech_bubble()
            wl, wt, wr, wb = self.get_boundaries()
            edges = ["left", "right", "top"]
            self.peek_edge = random.choice(edges)
            self.hide_timer = 0.0
            if self.peek_edge == "left":
                self.x = wl - self.width + 40
                self.y = self._safe_randint(wt, wb)
                self.facing_left = False
            elif self.peek_edge == "right":
                self.x = wr + self.width - 40
                self.y = self._safe_randint(wt, wb)
                self.facing_left = True
            elif self.peek_edge == "top":
                self.x = self._safe_randint(wl, wr)
                self.y = wt - self.height + 60
            self.geometry(f"+{self.x}+{self.y}")
        elif state == "happy":
            self.vx = 0
            self.vy = 0

    def _clear_magic_circle(self):
        for cid in self.magic_circle_ids:
            try:
                self.canvas.delete(cid)
            except:
                pass
        self.magic_circle_ids = []

    # ─── Core Update Loop (60 FPS) ────────────────────────────────────
    def _safe_pointer_xy(self):
        """Return mouse position or None if the window/pointer is unavailable."""
        try:
            if not self.winfo_exists():
                return None
            return self.winfo_pointerx(), self.winfo_pointery()
        except (KeyboardInterrupt, tk.TclError):
            return None
        except Exception:
            return None

    def update_loop(self):
        try:
            if not self.winfo_exists():
                return
            self._update_loop_frame()
        except (KeyboardInterrupt, tk.TclError):
            return
        except Exception:
            pass

        try:
            if self.winfo_exists():
                self.after(16, self.update_loop)
        except (KeyboardInterrupt, tk.TclError):
            pass

    def _update_loop_frame(self):
        scale = self.pet_config.get("scale")

        # Squash/stretch interpolation
        self.squash_x += (1.0 - self.squash_x) * 0.15
        self.squash_y += (1.0 - self.squash_y) * 0.15

        # Happy pose timer
        if self.happy_time > 0:
            self.happy_time -= 0.016

        # Mouse head tracking
        self._update_mouse_tracking()

        wl, wt, wr, wb = self.get_boundaries()

        if not self.is_dragging:
            # ─ Gravity + Window Perching ─
            if self.pet_config.get("gravity_enabled") and self.state != "sleeping":
                # Find landing surface: window top or screen floor
                pet_cx = self.x + self.width // 2
                pet_bottom = self.y + self.height
                floor_y = wb   # wb = screen bottom - height (boundary)
                land_y = self.win_detector.find_landing_surface(
                    pet_cx, pet_bottom, self.width, floor_y
                )
                # land_y is expressed as window.top on screen;
                # convert to our pet.y coordinate (pet top)
                effective_floor = land_y - self.height if land_y < floor_y else floor_y

                if self.y < effective_floor:
                    self.vy += 0.8
                    self.y += int(self.vy)
                    if self.vy > 1:
                        self.squash_y = 1.15
                        self.squash_x = 0.85
                    if self.y >= effective_floor:
                        self.y = effective_floor
                        landed_on_window = (land_y < floor_y)
                        if self.vy > 3:
                            self.vy = -self.vy * 0.35
                            self.squash_y = 0.65
                            self.squash_x = 1.3
                            self.particles.add_sparks(self.width / 2, self.height - 20, count=5)
                            if landed_on_window:
                                self.set_state("blush")
                                self.show_speech_bubble(
                                    "😊 এই জানালায় বসে আছি!\n(Sitting on this window!)",
                                    color="#a78bfa", duration=2000
                                )
                                self.on_window_perch = True
                            else:
                                self.set_state("shocked")
                                self.show_speech_bubble(
                                    "😱 ওরে বাবারে! ধুপ করে পড়ে গেলাম!\n(Ouch! That was a hard fall!)",
                                    duration=2000
                                )
                        else:
                            self.vy = 0
                            if landed_on_window and not self.on_window_perch:
                                self.on_window_perch = True
                                if random.random() < 0.5:
                                    self.show_speech_bubble(
                                        "👀 এই জায়গা থেকে দেখতে ভালো!\n(Nice view from up here!)",
                                        color="#a5f3fc", duration=2500
                                    )
                else:
                    self.y = effective_floor
                    self.vy = 0
                    self.on_window_perch = (land_y < floor_y)
            else:
                self.vy *= 0.95
                self.on_window_perch = False

            # ─ Horizontal state movement ─
            if self.state == "chase":
                pos = self._safe_pointer_xy()
                if pos is None:
                    pass
                else:
                    mx, my = pos
                    cx = self.x + self.width / 2
                    cy = self.y + self.height / 2
                    dx = mx - cx
                    dy = my - cy
                    dist = math.sqrt(dx ** 2 + dy ** 2)
                    self.chase_timer += 0.016
                    if dist > 20:
                        speed = self.move_speed * 2.5
                        self.vx = (dx / dist) * speed
                        self.vy = (dy / dist) * speed
                        self.x += int(self.vx)
                        self.y += int(self.vy)
                        self.facing_left = (dx < 0)
                        if config_db.get("magic_trail_enabled") and random.random() < 0.4:
                            self.particles.add_magic_trail(self.width / 2, self.height - 30)
                    else:
                        self.vx = 0
                        self.vy = 0
                        if random.random() < 0.05:
                            self.particles.add_hearts(self.width / 2, self.height / 2, count=2)
                    if self.chase_timer > 10.0:
                        self.set_state("idle")

            elif self.state == "hide":
                self.hide_timer += 0.016
                if random.random() < 0.005:
                    self.particles.add_sparks(self.width / 2, self.height / 2, count=3)
                if self.hide_timer > 15.0:
                    wl2, wt2, wr2, wb2 = get_work_area()
                    self.x = int((wl2 + wr2) / 2 - self.width / 2)
                    self.y = wb2
                    self.geometry(f"+{self.x}+{self.y}")
                    self.particles.add_fireworks_burst(self.width / 2, self.height / 2, count=25)
                    self.set_state("happy")
                    self.show_speech_bubble(
                        "🎉 ইয়েহ! আমি জিতেছি! তুমি খুঁজে পাওনি!\n(Yay! I win! You couldn't find me!)",
                        color="#fde68a", duration=4000
                    )
                    self.after(4000, lambda: self.set_state("idle") if self.state == "happy" else None)

            elif self.state == "broom":
                self.x += int(self.vx)
                self.y = wb - 60
                if self.x <= wl:
                    self.x = wl
                    self.vx = 4.5
                    self.facing_left = False
                    self.particles.add_sparks(self.width / 2, self.height / 2, count=8)
                elif self.x >= wr:
                    self.x = wr
                    self.vx = -4.5
                    self.facing_left = True
                    self.particles.add_sparks(self.width / 2, self.height / 2, count=8)
                # Magic trail during broom flight
                if config_db.get("magic_trail_enabled") and random.random() < 0.4:
                    self.particles.add_magic_trail(self.width / 2, self.height - 30)

            elif self.state == "edge_return":
                phase = self._edge_return_phase
                side = self._edge_hide_side or "left"
                if phase == "sneak_in":
                    if side == "top":
                        dy = self._edge_sneak_target_y - self.y
                        if abs(dy) > 3:
                            self.y += 4 if dy > 0 else -4
                        else:
                            self.y = self._edge_sneak_target_y
                            self._edge_return_phase = "pause"
                            self._edge_return_timer = 0.0
                    else:
                        dx = self._edge_sneak_target_x - self.x
                        if abs(dx) > 3:
                            self.x += 4 if dx > 0 else -4
                        else:
                            self.x = self._edge_sneak_target_x
                            self._edge_return_phase = "pause"
                            self._edge_return_timer = 0.0
                elif phase == "pause":
                    self._edge_return_timer += 0.016
                    if self._edge_return_timer > 1.4:
                        self._edge_return_phase = "jump_scare"
                elif phase == "jump_scare":
                    if side == "top":
                        target = self._edge_jump_y
                        dy = target - self.y
                        if abs(dy) > 10:
                            self.y += int(dy * 0.45)
                        else:
                            self.y = target
                            self._finish_edge_jump_scare()
                    else:
                        target = self._edge_jump_x
                        dx = target - self.x
                        if abs(dx) > 10:
                            self.x += int(dx * 0.45)
                        else:
                            self.x = target
                            self._finish_edge_jump_scare()

            elif self.state == "peek":
                if self.peek_phase == "slide_in":
                    dx = self.peek_target_x - self.x
                    if abs(dx) > 2:
                        self.x += 3 if dx > 0 else -3
                    else:
                        self.x = self.peek_target_x
                        self.peek_phase = "stay"
                        self.peek_timer = 0.0
                        self.particles.add_sparks(self.width / 2, self.height / 2, count=5)
                        self.show_speech_bubble(
                            "👀 উঁকি মারছি! কী করছো তুমি?\n(Peeking! What are you doing?)",
                            color="#a5f3fc", duration=3000
                        )
                elif self.peek_phase == "stay":
                    self.peek_timer += 0.016
                    if self.peek_timer > 3.5:
                        if random.random() < 0.5:
                            self.peek_phase = "slide_out"
                        else:
                            self.peek_phase = "walk_out"
                            self.clear_speech_bubble()
                            self.show_speech_bubble(
                                "🚶 আমি বাইরে আসছি!\n(I'm coming out!)", duration=2000
                            )
                elif self.peek_phase == "slide_out":
                    wl2, wt2, wr2, wb2 = get_work_area()
                    target_hidden = (wl2 - self.width + 10) if self.peek_edge == "left" else (wr2 - 10)
                    dx = target_hidden - self.x
                    if abs(dx) > 2:
                        self.x += 3 if dx > 0 else -3
                    else:
                        self.x = target_hidden
                        self.set_state("idle")
                        self.x = int((wl2 + wr2) / 2 - self.width / 2)
                        self.y = wb2
                        self.geometry(f"+{self.x}+{self.y}")
                        self.particles.add_sparks(self.width / 2, self.height / 2, count=8)
                        self.show_speech_bubble(
                            "🔮 তা-দা! আমি আবার চলে এসেছি!\n(Ta-da! I'm back!)",
                            color="#c084fc", duration=2500
                        )
                elif self.peek_phase == "walk_out":
                    dx = self.peek_exit_x - self.x
                    if abs(dx) > 3:
                        self.facing_left = dx < 0
                        self.x += 4 if dx > 0 else -4
                    else:
                        self.x = self.peek_exit_x
                        self.set_state("idle")

            else:
                # Idle/sleep friction
                self.vx *= 0.8
                if abs(self.vx) > 0.5:
                    self.facing_left = self.vx < 0
                self.x += int(self.vx)

            # Boundary enforcement
            if self.pet_config.get("boundary_keep") and self.state not in ["drag_hidden", "edge_return"]:
                if self.state not in ["peek", "hide"]:
                    self.x = max(wl, min(self.x, wr))
                self.y = max(wt, min(self.y, wb))

            if self.state not in ["drag", "drag_hidden", "hide", "peek", "edge_return"]:
                screen_wl, screen_wt, screen_wr, screen_wb = get_work_area()
                char_w, char_h = self._sprite_metrics("idle")
                _, _, _, sb = sprite_screen_bounds(
                    float(self.x), float(self.y), float(self.width), float(self.height),
                    float(char_w), float(char_h),
                )
                below_taskbar = sb > screen_wb + 4
                off_left = self.x + self.width < screen_wl
                off_right = self.x > screen_wr
                off_top = self.y + self.height < screen_wt
                if below_taskbar or off_left or off_right or off_top:
                    self._clamp_on_screen()
                    self.vx = 0
                    self.vy = 0
                    if self.state not in ["sleeping", "shocked"]:
                        self.set_state("idle")

            self.geometry(f"+{self.x}+{self.y}")

        # ─ Particle updates ─
        self.particles.update()

        # ─ State-specific particle spawning ─
        self.anim_time += 0.05

        if self.state == "sleeping":
            if random.random() < 0.03:
                self.particles.add_sleep_zzz(self.width / 2 + 10, self.height / 2 - 20)
        elif self.state == "drag":
            if random.random() < 0.2:
                self.particles.add_dizzy_stars(
                    self.width / 2 + random.randint(-15, 15), self.height / 2 - 40
                )
        elif self.state == "dance":
            if random.random() < 0.15:
                self.particles.add_rainbow_ribbon(self.width / 2, self.height / 2)
        elif self.state == "crying":
            # Teardrop particles while crying
            if random.random() < 0.15:
                self.particles.add_teardrops(self.width / 2, self.height / 2 - 20, count=2)
        elif self.state in ["idle", "study", "tea", "focus"]:
            # Fairy dust during calm states
            if config_db.get("fairy_dust_enabled"):
                self.fairy_dust_timer += 1
                if self.fairy_dust_timer >= 6:
                    self.fairy_dust_timer = 0
                    p = get_personality()
                    count = max(1, int(2 * p.get("particle_mult", 1.0)))
                    self.particles.add_fairy_dust(self.width / 2, self.height / 2 - 30, count=count)
        elif self.state == "action":
            # Magic circle sparkles while casting
            if random.random() < 0.3:
                self.particles.add_magic_circle_sparkles(
                    self.width / 2, self.height - 40, radius=50, count=4
                )

        # Weather particles
        weather = self.pet_config.get("weather_mode")
        if weather == "rain" and random.random() < 0.4:
            self.particles.add_weather_rain(self.width, count=2)
        elif weather == "snow" and random.random() < 0.2:
            self.particles.add_weather_snow(self.width, count=1)
        elif weather == "sunny" and random.random() < 0.1:
            self.particles.add_weather_sunny(self.width, count=1)

        # ─ Render ─
        self.render_pet()

    # ─── State Machine AI (3–7s tick) ────────────────────────────────
    def state_machine_loop(self):
        try:
            if not self.winfo_exists():
                return
            self._state_machine_tick()
        except (KeyboardInterrupt, tk.TclError):
            return
        except Exception:
            pass

        try:
            if self.winfo_exists():
                self.after(random.randint(3000, 7000), self.state_machine_loop)
        except (KeyboardInterrupt, tk.TclError):
            pass

    def _state_machine_tick(self):
        idle_dur = get_idle_duration()
        lang = self.pet_config.get("language")
        p = get_personality()

        # Boredom escalation
        if idle_dur > 40.0:
            if self.state not in ["sleeping", "study", "drag"]:
                self.clear_speech_bubble()
                if idle_dur > 120.0:
                    # Very bored: sleep
                    if self.state != "sleeping":
                        self.set_state("sleeping")
                elif random.random() < 0.5:
                    self.set_state("sleeping")
                else:
                    self.set_state("study")
        else:
            # User returned
            if self.state == "sleeping":
                self.set_state("idle")
                self.happy_time = 2.0
                self.particles.add_hearts(self.width / 2, self.height / 2, count=5)
                self.show_speech_bubble(
                    "👋 তুমি ফিরে এসেছো! চলো খেলি!\n(You are back! Let's play!)",
                    color="#a78bfa", duration=3500
                )
            elif self.state == "study" and random.random() < 0.3:
                self.set_state("idle")
                self.show_speech_bubble(
                    "📖 পড়াশোনা শেষ! এবার কী করবে?\n(Finished studying! What's next?)",
                    color="#93c5fd", duration=3000
                )

            # Normal random behavior with personality weights
            if self.state not in ["drag", "action", "sleeping", "drag_hidden", "edge_return"] and not self.is_dragging:
                roll = random.random()

                if getattr(self, "is_anchored", False):
                    # Only allow sitting/calm states if anchored to taskbar
                    if self.state in ["dance", "broom", "chase", "hide", "peek"]:
                        self.set_state("idle")
                    else:
                        if roll < 0.2:
                            self.set_state("study")
                        elif roll < 0.4:
                            self.set_state("tea")
                        elif roll < 0.6:
                            self.set_state("focus")
                        elif roll < 0.8:
                            self.set_state("eating")
                        else:
                            self.set_state("idle")
                elif self.state == "idle":
                    if roll < 0.28:
                        self.set_state("action")
                    elif roll < 0.28 + p.get("dance_prob", 0.07):
                        self.set_state("dance")
                    elif roll < 0.40:
                        self.set_state("study")
                    elif roll < 0.45:
                        self.set_state("tea")
                    elif roll < 0.50:
                        self.set_state("broom")
                    elif roll < 0.56:
                        self.set_state("blush")
                    elif roll < 0.62:
                        self.set_state("laugh")
                    elif roll < 0.65:
                        self.set_state("peek")
                    elif roll < 0.68:
                        self.set_state("focus")
                    elif roll < 0.71:
                        self.set_state("waving")
                    elif roll < 0.75:
                        self.set_state("chase")
                    elif roll < 0.78:
                        self.set_state("hide")
                    elif roll < 0.81:
                        self.set_state("eating")
                    elif roll < 0.84:
                        self.set_state("crying")
                elif self.state in ["dance", "study", "tea", "broom", "blush",
                                     "laugh", "shocked", "peek", "focus", "chase", "hide",
                                     "waving", "eating", "crying"]:
                    if roll < 0.35:
                        self.set_state("idle")

                # Periodic speech with personality rate
                rate_mult = p.get("speech_rate_mult", 1.0)
                if random.random() < self.pet_config.get("speech_rate") * 0.4 * rate_mult:
                    self.show_speech_bubble(
                        get_speech_bubble(self.state if self.state in ["idle", "cast_spell", "sleep"] else "idle", lang)
                    )

    # ─── Rendering ────────────────────────────────────────────────────
    def render_pet(self):
        scale = self.pet_config.get("scale")

        # Map state to image key
        img_key = "idle"
        if self.state == "drag":
            img_key = "dragged"
        elif self.state == "action":
            img_key = "action"
        elif self.state == "sleeping":
            img_key = "sleeping"
        elif self.state == "blush":
            img_key = "blush"
        elif self.state == "laugh":
            img_key = "laugh"
        elif self.state == "shocked":
            img_key = "shocked"
        elif self.state in ["peek", "hide", "edge_return"]:
            img_key = "peek"
        elif self.state == "focus":
            img_key = "focus"
        elif self.happy_time > 0:
            img_key = "happy"
        elif self.state == "chase":
            img_key = "walk1" if int(self.anim_time * 3.0) % 2 == 0 else "walk2"
        elif self.state == "dance":
            # Use static dance pose for the first 0.5s before the cycle starts
            if self.anim_time < 0.5:
                img_key = "dance_static"
            else:
                step = int((self.anim_time - 0.5) * 2.0) % 4
                img_key = f"dance_{step}"
        elif self.state == "study":
            img_key = "study"
        elif self.state == "tea":
            img_key = "tea"
        elif self.state == "broom":
            img_key = "broom"
        elif self.state == "waving":
            img_key = "waving"
        elif self.state == "crying":
            img_key = "crying"
        elif self.state == "eating":
            img_key = "eating"

        elif self.state in ["drag_hidden"]:
            return  # don't render anything when hidden

        flip_h = not self.facing_left
        tk_img = self.assets.get_image(img_key, scale, flip_h, self.squash_x, self.squash_y)
        if not tk_img:
            return

        char_w = tk_img.width()
        char_h = tk_img.height()

        # Bobbing/tilt by state
        bob = 0.0
        tilt = 0.0

        if self.state in ["idle", "study", "tea", "focus"]:
            bob = math.sin(self.anim_time) * 3 * scale
            if self.happy_time > 0:
                tilt = math.sin(self.anim_time * 6.0) * 3
        elif self.state == "chase":
            bob = abs(math.sin(self.anim_time * 4.0)) * 4 * scale
            tilt = math.sin(self.anim_time * 4.0) * 4
        elif self.state == "dance":
            bob = abs(math.sin(self.anim_time * 4.0)) * 6 * scale
            tilt = math.sin(self.anim_time * 4.0) * 8
        elif self.state == "broom":
            bob = math.sin(self.anim_time * 3.0) * 5 * scale
            tilt = math.cos(self.anim_time * 3.0) * 6
        elif self.state == "drag":
            tilt = math.sin(self.anim_time * 5.0) * 10

        cx = self.width / 2
        cy = self.height - (char_h / 2) - 10 + bob

        # ─ Draw character ─
        if self.canvas_img_id is None:
            self.canvas_img_id = self.canvas.create_image(cx, cy, image=tk_img)
        else:
            self.canvas.itemconfig(self.canvas_img_id, image=tk_img)
            self.canvas.coords(self.canvas_img_id, cx, cy)

        # Always ensure character is above shadow and aura
        self.canvas.tag_raise(self.canvas_img_id)

        # ─ Raise speech bubble elements above everything ─
        if self.speech_bubble_id:
            self.canvas.tag_raise(self.speech_bubble_id)
        if self.speech_text_id:
            self.canvas.tag_raise(self.speech_text_id)
        if self.speech_pointer_id:
            self.canvas.tag_raise(self.speech_pointer_id)

    def _get_aura(self):
        """Returns (color, size_bonus) for mood aura based on current state."""
        aura_map = {
            "action":   ("#a78bfa", 12),
            "dance":    ("#f0abfc", 10),
            "broom":    ("#bbf7d0", 8),
            "blush":    ("#fda4af", 8),
            "laugh":    ("#fde68a", 8),
            "chase":    ("#fb923c", 10),
            "study":    ("#93c5fd", 6),
            "tea":      ("#fde68a", 6),
            "focus":    ("#67e8f9", 8),
            "shocked":  ("#fca5a5", 10),
        }
        if self.happy_time > 0:
            return "#fde68a", 14
        return aura_map.get(self.state, (None, 0))

    # ─── Speech Bubbles ───────────────────────────────────────────────
    def show_speech_bubble(self, text, duration=3500, color=None):
        """Display a stylized speech bubble above the character."""
        self.clear_speech_bubble()

        bubble_color = color or "#ffffff"
        text_color = "#2d1b5e" if bubble_color == "#ffffff" else "#1e1b4b"

        # Compute layout
        scale = self.pet_config.get("scale")
        margin = 15
        char_h = int(220 * scale)
        char_top = self.height - char_h - 10
        max_w = int(240 * scale)
        padding = int(10 * scale)

        bx1 = margin
        by1 = margin
        bx2 = self.width - margin
        by2 = char_top - int(16 * scale)

        if by2 - by1 < 40:
            by2 = by1 + 60

        # Write text
        self.speech_text_id = self.canvas.create_text(
            (bx1 + bx2) / 2, (by1 + by2) / 2,
            text=text, fill=text_color,
            font=("Segoe UI", int(9 * scale) if scale < 1.0 else 10),
            width=max_w - 10, justify="center"
        )

        # Tighten box around actual text
        try:
            tx1, ty1, tx2, ty2 = self.canvas.bbox(self.speech_text_id)
            bx1, by1 = tx1 - padding, ty1 - padding
            bx2, by2 = tx2 + padding, ty2 + padding
        except:
            pass

        # Pointer triangle
        px = self.width / 2
        py = by2
        ptr_w = int(8 * scale)
        ptr_h = char_top - by2 - int(4 * scale)
        points = [
            px - ptr_w, py - 1,
            px, py + ptr_h,
            px + ptr_w, py - 1
        ]
        self.speech_pointer_id = self.canvas.create_polygon(
            points, fill=bubble_color, outline=self._darken_color(bubble_color), width=1
        )

        # Rounded bubble
        self.speech_bubble_id = self._draw_rounded_rectangle(
            self.canvas, bx1, by1, bx2, by2, radius=int(12 * scale),
            fill=bubble_color, outline=self._darken_color(bubble_color), width=1
        )

        self.canvas.tag_raise(self.speech_text_id)

        self.speech_timer = self.after(duration, self.clear_speech_bubble)

    def _darken_color(self, hex_color):
        """Returns a slightly darker version of a hex color for the bubble outline."""
        try:
            r = max(0, int(hex_color[1:3], 16) - 40)
            g = max(0, int(hex_color[3:5], 16) - 40)
            b = max(0, int(hex_color[5:7], 16) - 40)
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return "#dddddd"

    def clear_speech_bubble(self):
        if self.speech_timer:
            self.after_cancel(self.speech_timer)
            self.speech_timer = None
        for attr in ["speech_bubble_id", "speech_text_id", "speech_pointer_id"]:
            cid = getattr(self, attr, None)
            if cid:
                try:
                    self.canvas.delete(cid)
                except:
                    pass
                setattr(self, attr, None)

    def _draw_rounded_rectangle(self, canvas, x1, y1, x2, y2, radius=10, **kwargs):
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1
        ]
        return canvas.create_polygon(points, **kwargs, smooth=True)

    # ─── Actions ──────────────────────────────────────────────────────
    def trigger_magic_clean(self):
        self.set_state("action")
        import gc
        freed = gc.collect()
        play_sound("spell")
        self.after(800, lambda: self.show_speech_bubble(
            f"🧹 জাদুমন্ত্রে মেমরি সাফ!\n{freed} অবজেক্ট ভ্যানিশ করা হলো!\n(Freed {freed} objects with magic!)",
            color="#a78bfa", duration=3500
        ))

    def trigger_task_complete_celebration(self):
        """Called when a task is marked complete from the spellbook."""
        self.particles.add_fireworks_burst(self.width / 2, self.height / 2, count=30)
        self.particles.add_hearts(self.width / 2, self.height / 2, count=8)
        self.happy_time = 3.0
        lang = self.pet_config.get("language")
        self.show_speech_bubble(
            get_speech_bubble("todo_complete", lang),
            color="#fde68a", duration=3500
        )
        play_sound("complete")

    # ─── Double-Click Petting ─────────────────────────────────────────
    def on_double_click(self, event):
        """Desktop Mate style: double-click = head pat."""
        self.happy_time = 3.0
        # Fun squash-bounce on head pat
        self.squash_y = 0.80
        self.squash_x = 1.15
        self.particles.add_hearts(self.width / 2, self.height / 2 - 20, count=8)
        self.particles.add_fairy_dust(self.width / 2, self.height / 2, count=5)
        lang = self.pet_config.get("language")
        msgs = {
            "mix": ["🥰 আহ~ এভাবে মাথায় হাত দিলে ভালো লাগে!\n(Ahh~ head pats feel nice!)",
                    "💕 আরো করো! আরো!\n(More! More pats!)",
                    "😊 তুমি খুব ভালো!\n(You are so kind!)"],
            "bn":  ["🥰 আহ~ মাথায় হাত দিলে ভালো লাগে!",
                    "💕 আরো করো! আরো!",
                    "😊 তুমি খুব ভালো!"],
            "en":  ["🥰 Ahh~ I love head pats!",
                    "💕 More! Don't stop!",
                    "😊 You are so sweet!"],
        }
        speech_list = msgs.get(lang, msgs["mix"])
        self.show_speech_bubble(random.choice(speech_list), color="#fda4af", duration=2500)
        play_sound("click")

    # ─── Toggle Visibility (hotkey / tray) ───────────────────────────
    def _toggle_visibility(self):
        """Called by global hotkey Ctrl+Shift+M."""
        if self._visible:
            self.after(0, self.withdraw)
            self._visible = False
        else:
            self.after(0, self.deiconify)
            self.after(0, lambda: self.wm_attributes("-topmost", True))
            self._visible = True

    # ─── Mouse Head Tracking ──────────────────────────────────────────
    def _update_mouse_tracking(self):
        """Smoothly update facing direction toward the mouse cursor."""
        pos = self._safe_pointer_xy()
        if pos is None:
            return
        mx, _my = pos
        cx = self.x + self.width // 2
        if self.state in ["idle", "study", "tea", "focus", "blush", "laugh"] and not self.is_dragging:
            if mx < cx - 30:
                self.facing_left = True
            elif mx > cx + 30:
                self.facing_left = False

    # ─── Open GUI Dialogs ─────────────────────────────────────────────
    def open_settings(self):
        from app.gui import open_settings_window
        open_settings_window(self)

    def open_spellbook(self):
        from app.gui import open_spellbook_window
        open_spellbook_window(self)

    def open_timer(self):
        from app.gui import open_timer_window
        open_timer_window(self)

    def quit_app(self):
        session_memory.save()
        self._cancel_after("_break_timer_job")
        self._cancel_after("_break_stay_job")
        self._cancel_after_timer_job()
        self.clear_speech_bubble()
        self.particles.clear()
        try:
            self.win_detector.stop()
        except Exception:
            pass
        if self._tray is not None:
            try:
                self._tray.stop()
            except Exception:
                pass
        self.destroy()
        sys.exit(0)
