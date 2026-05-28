"""Stable app-internal entrypoints for individual desktop tool windows."""

from __future__ import annotations

from desktop_tools.app.ui.background_remover_app import open_background_remover
from desktop_tools.app.ui.converter_app import open_converter_window as _open_converter_window
from desktop_tools.app.ui.screenshot_app import open_screenshot_studio
from desktop_tools.app.ui.yscreenrecorder_app import open_yscreenrecorder

__all__ = [
    "open_converter_window",
    "open_background_remover",
    "open_screenshot_studio",
    "open_yscreenrecorder",
]


def open_converter_window(parent=None, default_output_dir=None):
    return _open_converter_window(parent=parent, default_output_dir=default_output_dir)

