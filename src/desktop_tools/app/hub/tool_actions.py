"""Reusable tool-launch actions used by the Media Downloader hub."""

from __future__ import annotations

from desktop_tools.tools.media_downloader.launchers import (
    open_background_remover as launch_background_remover_tool,
    open_converter as launch_converter_tool,
    open_screenshot_studio as launch_screenshot_tool,
    open_yscreenrecorder as launch_screenrecorder_tool,
)


def open_tool_window(*, launcher, root, log, messagebox_module, success_log_message, error_title, error_message):
    """Open a desktop tool and consistently handle logging and errors."""
    try:
        opened_window = launcher(root)
        if opened_window is not None:
            log(success_log_message)
    except Exception as exc:
        log(f"Error opening desktop tool ({success_log_message}): {exc}")
        messagebox_module.showerror(error_title, f"{error_message}:\n{exc}")


def open_converter(*, root, log, messagebox_module, default_output_dir=None):
    open_tool_window(
        launcher=lambda parent: launch_converter_tool(parent=parent, default_output_dir=default_output_dir),
        root=root,
        log=log,
        messagebox_module=messagebox_module,
        success_log_message="Opened Media Converter",
        error_title="Converter Error",
        error_message="Could not open the converter",
    )


def open_background_remover(*, root, log, messagebox_module):
    open_tool_window(
        launcher=launch_background_remover_tool,
        root=root,
        log=log,
        messagebox_module=messagebox_module,
        success_log_message="Opened Image Background Remover",
        error_title="Background Remover Error",
        error_message="Could not open the background remover",
    )


def open_screenshot_studio(*, root, log, messagebox_module):
    open_tool_window(
        launcher=launch_screenshot_tool,
        root=root,
        log=log,
        messagebox_module=messagebox_module,
        success_log_message="Opened YScreenshot",
        error_title="YScreenshot Error",
        error_message="Could not open YScreenshot",
    )


def open_yscreenrecorder(*, root, log, messagebox_module):
    open_tool_window(
        launcher=launch_screenrecorder_tool,
        root=root,
        log=log,
        messagebox_module=messagebox_module,
        success_log_message="Opened YScreenRecorder",
        error_title="YScreenRecorder Error",
        error_message="Could not open YScreenRecorder",
    )

