"""Shared desktop capture helpers for screenshot and recorder tools."""

from __future__ import annotations

import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageGrab

IS_WINDOWS = os.name == "nt"
IS_LINUX = sys.platform.startswith("linux")


def get_linux_session_type() -> str | None:
    """Return the active Linux session type when available."""
    if not IS_LINUX:
        return None

    session_type = (os.environ.get("XDG_SESSION_TYPE") or "").strip().lower()
    if session_type in {"x11", "wayland"}:
        return session_type
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return None


def is_linux_wayland() -> bool:
    return get_linux_session_type() == "wayland"


def is_linux_x11() -> bool:
    return get_linux_session_type() == "x11"


def get_linux_display_name() -> str | None:
    """Return the current X11 display, if present."""
    display = (os.environ.get("DISPLAY") or "").strip()
    return display or None


def _capture_with_imagegrab() -> Image.Image:
    try:
        return ImageGrab.grab(all_screens=True).convert("RGBA")
    except TypeError:
        return ImageGrab.grab().convert("RGBA")


def _run_capture_to_tempfile(command: list[str]) -> Image.Image:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
            temp_path = Path(handle.name)

        result = subprocess.run(
            [*command, str(temp_path)],
            capture_output=True,
            text=True,
            creationflags=creationflags,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "Screen capture command failed.").strip())

        with Image.open(temp_path) as image:
            return image.convert("RGBA")
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass


def _capture_with_linux_tools() -> Image.Image:
    attempts: list[list[str]] = []
    if shutil.which("grim"):
        attempts.append(["grim"])
    if shutil.which("gnome-screenshot"):
        attempts.append(["gnome-screenshot", "-f"])
    if shutil.which("scrot"):
        attempts.append(["scrot", "-o"])
    if shutil.which("import"):
        attempts.append(["import", "-window", "root"])

    last_error = ""
    for command in attempts:
        try:
            return _run_capture_to_tempfile(command)
        except Exception as exc:
            last_error = str(exc)

    if attempts:
        raise RuntimeError(last_error or "Linux screenshot tools failed.")

    if is_linux_wayland():
        raise RuntimeError(
            "Could not capture the screen on Wayland. Install grim or gnome-screenshot, or run the app in an X11 session."
        )
    raise RuntimeError(
        "Could not capture the screen on Linux. Install gnome-screenshot, scrot, or ImageMagick 'import'."
    )


def capture_desktop_snapshot(fallback_window=None) -> tuple[Image.Image, int, int, int, int]:
    """Capture the current desktop and return image plus virtual geometry."""
    if IS_WINDOWS:
        x = y = 0
        width = height = 0
        try:
            user32 = __import__("ctypes").windll.user32
            x = int(user32.GetSystemMetrics(76))
            y = int(user32.GetSystemMetrics(77))
            width = int(user32.GetSystemMetrics(78))
            height = int(user32.GetSystemMetrics(79))
        except Exception:
            pass

        image = _capture_with_imagegrab()
        if width <= 0 or height <= 0:
            width, height = image.size
        if image.size != (width, height):
            image = image.resize((width, height), Image.LANCZOS)
        return image, x, y, width, height

    last_error = ""
    for capture_attempt in (_capture_with_imagegrab, _capture_with_linux_tools if IS_LINUX else None):
        if capture_attempt is None:
            continue
        try:
            image = capture_attempt()
            width, height = image.size
            return image, 0, 0, width, height
        except Exception as exc:
            last_error = str(exc)

    if fallback_window is not None:
        width = fallback_window.winfo_screenwidth()
        height = fallback_window.winfo_screenheight()
        if width > 0 and height > 0:
            try:
                image = _capture_with_imagegrab()
                if image.size != (width, height):
                    image = image.resize((width, height), Image.LANCZOS)
                return image, 0, 0, width, height
            except Exception:
                pass

    raise RuntimeError(last_error or "Could not capture the screen on this platform.")


def copy_image_to_linux_clipboard(image: Image.Image) -> None:
    """Copy an image to the Linux clipboard using common desktop tools."""
    if not IS_LINUX:
        raise RuntimeError("Linux clipboard helpers are only available on Linux.")

    clipboard_bytes = io.BytesIO()
    image.save(clipboard_bytes, "PNG")
    payload = clipboard_bytes.getvalue()
    clipboard_bytes.close()

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    commands: list[list[str]] = []
    if is_linux_wayland() and shutil.which("wl-copy"):
        commands.append(["wl-copy", "--type", "image/png"])
    if shutil.which("xclip"):
        commands.append(["xclip", "-selection", "clipboard", "-t", "image/png", "-i"])

    if not commands:
        if is_linux_wayland():
            raise RuntimeError("Install wl-clipboard to copy images on Wayland.")
        raise RuntimeError("Install xclip to copy images on Linux.")

    last_error = ""
    for command in commands:
        try:
            result = subprocess.run(
                command,
                input=payload,
                capture_output=True,
                creationflags=creationflags,
            )
            if result.returncode == 0:
                return
            last_error = (result.stderr or result.stdout or b"Clipboard command failed.").decode(errors="ignore").strip()
        except Exception as exc:
            last_error = str(exc)

    raise RuntimeError(last_error or "Could not copy the image to the Linux clipboard.")
