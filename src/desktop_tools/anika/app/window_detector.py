"""
window_detector.py — Detects tops of visible desktop windows
so Anika can perch on them (Desktop Mate style).
Uses only Windows ctypes, no extra packages needed.
"""
import ctypes
import ctypes.wintypes as wt
import threading
import time

# Windows API constants
GW_HWNDNEXT = 2
SW_SHOWMINIMIZED = 2

user32 = ctypes.windll.user32

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)


class WindowDetector:
    """
    Polls visible foreground windows every 500ms and exposes
    a list of their screen rectangles so the pet can land on them.
    """

    # Windows to skip (our own pet window title keywords)
    _SKIP_TITLES = {
        "Anika",
        "Anika — Settings",
        "Anika — Break Reminder",
        "Spell Book",
        "Settings",
        "Chaa Break",
        "Desktop Mate",
        "Media Downloader",
    }

    def __init__(self):
        self._lock = threading.Lock()
        self._surfaces = []   # list of (left, top, right, bottom) window rects
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _poll_loop(self):
        while self._running:
            self._refresh()
            time.sleep(0.5)

    def _refresh(self):
        results = []

        def callback(hwnd, _lParam):
            try:
                if not user32.IsWindowVisible(hwnd):
                    return True
                # Skip minimized windows
                placement = ctypes.create_string_buffer(44)
                # Simple: check if iconic
                if user32.IsIconic(hwnd):
                    return True

                # Get window title, skip our own
                buf = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(hwnd, buf, 256)
                title = buf.value.strip()
                if not title:
                    return True
                for skip in self._SKIP_TITLES:
                    if skip.lower() in title.lower():
                        return True

                # Get rect
                rect = wt.RECT()
                if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                    # Skip tiny or off-screen windows
                    if w > 100 and h > 60:
                        results.append((rect.left, rect.top, rect.right, rect.bottom))
            except Exception:
                pass
            return True

        try:
            user32.EnumWindows(WNDENUMPROC(callback), 0)
        except Exception:
            pass

        with self._lock:
            self._surfaces = results

    def get_surfaces(self):
        """Returns a snapshot of visible window rects: list of (l, t, r, b)."""
        with self._lock:
            return list(self._surfaces)

    def find_landing_surface(self, pet_cx, pet_bottom, pet_width, floor_y):
        """
        Given the pet's center-x, bottom-y, and width,
        find the highest window top-edge that is:
          - Below or at pet_bottom (pet is above or touching it)
          - Horizontally overlapping the pet
          - Above the floor
        Returns the Y coordinate to land on, or floor_y if none found.
        """
        half_w = pet_width // 2
        pet_left = pet_cx - half_w
        pet_right = pet_cx + half_w

        best_y = floor_y
        with self._lock:
            for (wl, wt_, wr, wb) in self._surfaces:
                # Window top must be below current pet bottom (we're falling onto it)
                # and above floor
                if wt_ <= floor_y and wt_ >= pet_bottom - 5:
                    # Horizontal overlap check
                    if not (pet_right < wl or pet_left > wr):
                        if wt_ < best_y:
                            best_y = wt_
        return best_y
