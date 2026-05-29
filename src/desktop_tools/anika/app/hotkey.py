"""
hotkey.py — Global hotkey listener for Anika.
Ctrl+Shift+M toggles show/hide.
Uses keyboard library with graceful fallback if unavailable/no admin.
"""
import threading


class GlobalHotkey:
    def __init__(self, hotkey, callback):
        self._hotkey = hotkey
        self._callback = callback
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def _listen(self):
        try:
            import keyboard
            keyboard.add_hotkey(self._hotkey, self._callback)
            keyboard.wait()  # Block this thread forever
        except ImportError:
            print(f"[Hotkey] keyboard library not installed — hotkey disabled")
        except Exception as e:
            print(f"[Hotkey] Could not register '{self._hotkey}': {e}")
            print("[Hotkey] Try running as Administrator for global hotkeys")
