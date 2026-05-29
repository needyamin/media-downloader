"""Stable app-internal entrypoints for individual desktop tool windows."""

from __future__ import annotations

from desktop_tools.app.ui.background_remover_app import open_background_remover
from desktop_tools.app.ui.converter_app import open_converter_window as _open_converter_window
from desktop_tools.app.ui.screenshot_app import open_screenshot_studio
from desktop_tools.app.ui.yscreenrecorder_app import open_yscreenrecorder
from desktop_tools.app.ui.anika_app import open_anika
from desktop_tools.app.ui.anika_settings_app import open_anika_settings

__all__ = [
    "open_converter_window",
    "open_background_remover",
    "open_screenshot_studio",
    "open_yscreenrecorder",
    "open_anika",
    "open_anika_settings",
]


def open_converter_window(parent=None, default_output_dir=None):
    return _open_converter_window(parent=parent, default_output_dir=default_output_dir)

