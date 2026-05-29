import tkinter as tk
import ctypes
from ctypes import wintypes
import random
import math
import os
import sys
import datetime
import time

from app.config import config_db, get_speech_bubble, get_time_aware_speech, session_memory, get_personality
from app.assets import AssetManager, BASE_SPRITE_HEIGHT
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


def play_sound(sound_type):
    """Play Windows system sound if sound is enabled."""
    if not config_db.get("sound_enabled"):
        return
    try:
        import winsound
        if sound_type == "click":
            return
            
        sounds = {
            "spell":    winsound.MB_ICONEXCLAMATION,
            "complete": winsound.MB_ICONASTERISK,
            "alarm":    winsound.MB_ICONHAND,
            "error":    winsound.MB_ICONHAND,
        }
        winsound.MessageBeep(sounds.get(sound_type, winsound.MB_OK))
    except Exception:
        pass


class DesktopPet(tk.Tk):
    def __init__(self):
        super().__init__()

        # Load config & personality
        self.pet_config = config_db
        self.personality = get_personality()

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

        # Speech bubble
        self.speech_bubble_id = None
        self.speech_text_id = None
        self.speech_pointer_id = None
        self.speech_timer = None
        self.speech_color = "#ffffff"  # Dynamic bubble color

        # Boredom escalation tracker
        self.boredom_level = 0        # 0=normal 1=yawn 2=sleep 3=snore
        self.session_reminder_sent = False

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
        """Resize the transparent window to fit the scaled mascot (not just the canvas)."""
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

    # ─── Session Reminder ─────────────────────────────────────────────
    def _check_session_reminder(self):
        mins = session_memory.get_session_minutes()
        if mins >= 60 and not self.session_reminder_sent:
            self.session_reminder_sent = True
            lang = self.pet_config.get("language")
            # Build personalized message with session time
            msg = f"তুমি {mins} মিনিট ধরে কাজ করছো!\nএকটু বিরতি নাও! 🧙‍♀️"
            if lang == "en":
                msg = f"You've been working for {mins} minutes!\nTake a break! 🧙‍♀️"
            self.show_speech_bubble(msg, color="#fbbf24", duration=5000)
            self.set_state("tea")
        elif mins >= 120:
            # Remind every hour after the first
            self.session_reminder_sent = False
        self.after(5 * 60000, self._check_session_reminder)  # Check every 5 minutes

    # ─── Break Reminder ───────────────────────────────────────────────
    def _break_settings_tuple(self):
        return (
            int(self.pet_config.get("break_interval_mins") or 0),
            int(self.pet_config.get("break_stay_secs") or 8),
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
        if getattr(self, "_break_timer_job", None):
            try:
                self.after_cancel(self._break_timer_job)
            except Exception:
                pass
            self._break_timer_job = None

        self.pet_config.load()
        interval_mins = self.pet_config.get("break_interval_mins")
        self._break_settings_signature = self._break_settings_tuple()
        if interval_mins and interval_mins > 0:
            self._break_timer_job = self.after(int(interval_mins * 60000), self._trigger_break_reminder)

    def _trigger_break_reminder(self):
        """Anika pops up in the centre of screen to announce a break."""
        self.pet_config.load()
        lang = self.pet_config.get("language")
        stay_secs = max(10, self.pet_config.get("break_stay_secs") or 8)

        # Move to centre of screen so she is always visible
        wl, wt, wr, wb = get_work_area()
        self.x = int((wl + wr) / 2 - self.width / 2)
        self.y = int((wt + wb) / 2 - self.height / 2)
        self.geometry(f"+{self.x}+{self.y}")

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

        # After stay_secs, return to idle and schedule next reminder
        self.after(stay_secs * 1000, lambda: [
            self.set_state("idle") if self.state == "waving" else None,
            self._start_break_timer()
        ])

    # ─── Drag & Drop ─────────────────────────────────────────────────
    def _edge_hide_delay_ms(self) -> int:
        mins = float(self.pet_config.get("edge_hide_mins") or 5)
        mins = max(1.0, min(60.0, mins))
        return int(mins * 60 * 1000)

    def _is_dragged_to_screen_edge(self, wl, wt, wr, wb) -> bool:
        """True when the pet was released against a screen edge (works with boundary_keep)."""
        if not self.pet_config.get("edge_hide_enabled"):
            return False
        margin = max(10, int(self.pet_config.get("edge_hide_threshold_px") or 36))
        return (
            self.x <= wl + margin
            or self.x + self.width >= wr - margin
            or self.y <= wt + margin
            or self.y + self.height >= wb - margin
        )

    def _begin_edge_hide(self) -> None:
        """Hide Anika after the user drags her to a screen edge."""
        self.set_state("drag_hidden")
        self.vx = 0
        self.vy = 0
        mins = max(1, int(float(self.pet_config.get("edge_hide_mins") or 5)))
        lang = self.pet_config.get("language")
        if lang == "en":
            msg = f"Okay! I'll be back in {mins} minutes."
        elif lang == "bn":
            msg = f"ঠিক আছে! {mins} মিনিট পর ফিরব।"
        else:
            msg = f"Okay! {mins} min পর ফিরছি / Back in {mins} min!"
        self.show_speech_bubble(msg, color="#c084fc", duration=2800)
        if self._drag_hidden_timer:
            try:
                self.after_cancel(self._drag_hidden_timer)
            except Exception:
                pass
        self._drag_hidden_timer = self.after(self._edge_hide_delay_ms(), self._recover_from_drag_hidden)

    def start_drag(self, event):
        self.is_dragging = True
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
            wl, wt, wr, wb = self.get_boundaries()
            self.x = max(wl, min(self.x, wr))
            self.y = max(wt, min(self.y, wb))

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
            half_w = self.width // 2
            half_h = self.height // 2

            # Drag to screen edge → hide for configured minutes
            if self._is_dragged_to_screen_edge(wl, wt, wr, wb):
                self._begin_edge_hide()
                return

            # Fallback when boundaries are off: fully off-screen release
            if not self.pet_config.get("boundary_keep") and (
                self.x + self.width < wl + half_w
                or self.x > wr + half_w
                or self.y + self.height < wt + half_h
                or self.y > wb + half_h
            ):
                self._begin_edge_hide()
                return

            # Check if dragged onto the bottom taskbar edge to sit/anchor
            if self.y + self.height >= wb - 20:
                self.is_anchored = True
                self.set_state("tea")
                self.show_speech_bubble("আমি এখানেই বসে থাকবো!\n(I'll sit right here!)", color="#bbf7d0", duration=2500)
                self.vx = 0
                self.vy = 0
                return

            # Dragged away from taskbar — clear anchor
            self.is_anchored = False
            
            if self.pet_config.get("gravity_enabled"):
                self.state = "idle"
            else:
                self.set_state("idle")

    def _recover_from_drag_hidden(self):
        if self.state == "drag_hidden":
            wl, wt, wr, wb = get_work_area()
            self.x = int((wl + wr) / 2 - self.width / 2)
            self.y = wb - self.height
            self.vx = 0
            self.vy = 0
            self._drag_hidden_timer = None
            self.set_state("idle")
            self.geometry(f"+{self.x}+{self.y}")
            self.particles.add_sparks(self.width / 2, self.height / 2, count=8)
            self.show_speech_bubble("তা-দা! আমি ফিরে এসেছি!\n(Ta-da! I'm back!)", color="#c084fc", duration=3000)

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
    def update_loop(self):
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
                mx = self.winfo_pointerx()
                my = self.winfo_pointery()
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
            if self.pet_config.get("boundary_keep") and self.state != "drag_hidden":
                if self.state != "peek" and self.state != "hide":
                    self.x = max(wl, min(self.x, wr))
                self.y = max(wt, min(self.y, wb))

            # Hard off-screen guard: always recover if completely invisible
            # (even when boundary_keep is off, or peek/hide/broom overshoot)
            # Allow up to half the pet width/height offscreen as a generous margin
            # Skip states that are intentionally off-screen
            if self.state not in ["drag_hidden", "hide", "peek"]:
                half_w = self.width // 2
                half_h = self.height // 2
                screen_wl, screen_wt, screen_wr, screen_wb = get_work_area()
                if (self.x + self.width < screen_wl + half_w or  # too far left
                        self.x > screen_wr + half_w or            # too far right
                        self.y + self.height < screen_wt + half_h or  # too far up
                        self.y > screen_wb + half_h):             # too far down
                    # Snap back to bottom-centre
                    self.x = int((screen_wl + screen_wr) / 2 - self.width / 2)
                    self.y = screen_wb - self.height
                    self.vx = 0
                    self.vy = 0
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

        self.after(16, self.update_loop)

    # ─── State Machine AI (3–7s tick) ────────────────────────────────
    def state_machine_loop(self):
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
            if self.state not in ["drag", "action", "sleeping", "drag_hidden"] and not self.is_dragging:
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

        self.after(random.randint(3000, 7000), self.state_machine_loop)

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
        elif self.state in ["peek", "hide"]:
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
        try:
            mx = self.winfo_pointerx()
            cx = self.x + self.width // 2
            # Only track when idle/calm (not dragging or mid-action)
            if self.state in ["idle", "study", "tea", "focus", "blush", "laugh"] and not self.is_dragging:
                target = (mx < cx)
                # Smooth interpolation: only flip facing if mouse is clearly on that side
                if mx < cx - 30:
                    self.facing_left = True
                elif mx > cx + 30:
                    self.facing_left = False
        except Exception:
            pass

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
