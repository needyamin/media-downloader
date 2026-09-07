"""Launch the Anika desktop assistant in an isolated subprocess."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_ANIKA_PROCESS: subprocess.Popen | None = None
_ANIKA_EXE_NAMES = ("Anika.exe", "Anika", "anika.exe")


def _is_frozen() -> bool:
    if getattr(sys, "frozen", False) or globals().get("__compiled__") is not None:
        return True
    if sys.platform == "win32":
        executable_name = Path(sys.executable).name.lower()
        return executable_name.endswith(".exe") and executable_name not in {"python.exe", "pythonw.exe"}
    return False


def _bundle_root() -> Path | None:
    try:
        from desktop_tools.shared.resources import get_project_root

        return get_project_root()
    except Exception:
        return None


def _resolve_anika_dir() -> Path:
    """Locate the anika package directory in development or packaged layouts."""
    candidates: list[Path] = [
        Path(__file__).resolve().parents[2] / "anika",
    ]
    bundle_root = _bundle_root()
    if bundle_root is not None:
        candidates.extend(
            [
                bundle_root / "desktop_tools" / "anika",
                bundle_root / "anika",
                bundle_root / "src" / "desktop_tools" / "anika",
            ]
        )

    for candidate in candidates:
        if (candidate / "main.py").is_file():
            return candidate
    return candidates[0]


def _find_packaged_anika_exe() -> Path | None:
    """Return Anika.exe shipped beside the hub binary in packaged Windows builds."""
    if not _is_frozen():
        return None

    search_roots: list[Path] = []
    if getattr(sys, "executable", None):
        search_roots.append(Path(sys.executable).resolve().parent)

    seen: set[Path] = set()
    for root in search_roots:
        if root in seen:
            continue
        seen.add(root)
        for name in _ANIKA_EXE_NAMES:
            candidate = root / name
            if candidate.is_file():
                return candidate
    return None


def _launch_command(anika_dir: Path) -> list[str]:
    if sys.platform == "win32":
        packaged_exe = _find_packaged_anika_exe()
        if packaged_exe is not None:
            return [str(packaged_exe)]
    if _is_frozen():
        raise FileNotFoundError(
            "Anika assistant executable was not found in this packaged build. "
            "Rebuild the installer so Anika.exe is included beside Media-Downloader.exe."
        )

    main_script = anika_dir / "main.py"
    if not main_script.is_file():
        raise FileNotFoundError(f"Anika entry script not found: {main_script}")
    return [sys.executable, "-u", str(main_script)]


def _show_message(parent, title: str, message: str, *, kind: str = "info") -> None:
    if parent is None:
        return
    try:
        from tkinter import messagebox

        if kind == "error":
            messagebox.showerror(title, message, parent=parent)
        else:
            messagebox.showinfo(title, message, parent=parent)
    except Exception:
        pass


def _bring_process_to_front(pid: int) -> bool:
    """Try to focus any top-level window owned by the Anika process."""
    if sys.platform != "win32" or pid <= 0:
        return False

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        found: list[int] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def callback(hwnd, _lparam):
            window_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            if int(window_pid.value) != pid:
                return True
            if not user32.IsWindowVisible(hwnd):
                return True
            found.append(int(hwnd))
            return True

        user32.EnumWindows(callback, 0)
        if not found:
            return False

        hwnd = found[-1]
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def _active_anika_process() -> subprocess.Popen | None:
    global _ANIKA_PROCESS
    proc = _ANIKA_PROCESS
    if proc is None:
        return None
    if proc.poll() is not None:
        _ANIKA_PROCESS = None
        return None
    return proc


def _verify_anika_started(parent, proc: subprocess.Popen) -> None:
    """If Anika exits immediately, show the subprocess error to the user."""
    if proc.poll() is not None:
        detail = ""
        if proc.stderr is not None:
            try:
                detail = proc.stderr.read().decode("utf-8", errors="replace").strip()
            except Exception:
                detail = ""
        message = "Anika closed right after launch."
        if detail:
            message = f"{message}\n\n{detail[:1200]}"
        _show_message(parent, "Anika Error", message, kind="error")
        return

    if _bring_process_to_front(proc.pid):
        return

    _show_message(
        parent,
        "Anika",
        "Anika is running.\n\n"
        "Look at the bottom-right of your screen for her sprite. "
        "If you dragged her to a screen edge, move your mouse there to peek.",
    )


def open_anika(parent=None) -> str:
    """Start Anika in a separate process (avoids `app` package name clashes with desktop_tools.app).

    Returns:
        ``started`` — new process launched
        ``already_running`` — existing Anika process was focused
        ``failed`` — launch failed after verification
    """
    global _ANIKA_PROCESS

    if sys.platform != "win32":
        _show_message(
            parent,
            "Anika",
            "Anika is available on Windows desktop builds.\n"
            "This Linux build ships her assets, but the desktop assistant runs on Windows only.",
        )
        return "failed"

    existing = _active_anika_process()
    if existing is not None:
        if _bring_process_to_front(existing.pid):
            return "already_running"
        _show_message(
            parent,
            "Anika",
            "Anika is already running.\n\n"
            "Check the bottom-right of your screen, or drag your cursor to a screen edge "
            "if you hid her there earlier.",
        )
        return "already_running"

    anika_dir = _resolve_anika_dir()
    command = _launch_command(anika_dir)

    env = os.environ.copy()
    capture_output = len(command) > 1
    if capture_output:
        path_parts = [str(anika_dir)]
        src_dir = anika_dir.parents[1]
        if (src_dir / "desktop_tools").is_dir():
            path_parts.append(str(src_dir))
        existing = env.get("PYTHONPATH", "")
        if existing:
            path_parts.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(path_parts)
    env.setdefault("ANIKA_NO_TRAY", "1")

    cwd = str(anika_dir)
    packaged_exe = _find_packaged_anika_exe()
    if packaged_exe is not None and command[0] == str(packaged_exe):
        cwd = str(packaged_exe.parent)

    popen_kwargs: dict = {
        "cwd": cwd,
        "env": env,
    }
    if capture_output:
        popen_kwargs["stderr"] = subprocess.PIPE

    _ANIKA_PROCESS = subprocess.Popen(command, **popen_kwargs)

    if parent is not None:
        try:
            parent.after(1500, lambda: _verify_anika_started(parent, _ANIKA_PROCESS))
        except Exception:
            _verify_anika_started(parent, _ANIKA_PROCESS)
    else:
        _verify_anika_started(parent, _ANIKA_PROCESS)

    if _ANIKA_PROCESS.poll() is not None:
        _verify_anika_started(parent, _ANIKA_PROCESS)
        _ANIKA_PROCESS = None
        return "failed"

    return "started"


def terminate_anika() -> None:
    """Stop the Anika assistant process if the hub launched it."""
    global _ANIKA_PROCESS
    proc = _ANIKA_PROCESS
    _ANIKA_PROCESS = None
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception:
        pass
