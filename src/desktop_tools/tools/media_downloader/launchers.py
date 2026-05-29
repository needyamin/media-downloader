"""Stable launcher functions for desktop tool windows."""

from __future__ import annotations

from desktop_tools.app.ui.entrypoints import (
    open_background_remover as _open_background_remover,
    open_converter_window as _open_converter_window,
    open_screenshot_studio as _open_screenshot_studio,
    open_anika as _open_anika,
    open_anika_settings as _open_anika_settings,
    open_yscreenrecorder as _open_yscreenrecorder,
)


def open_converter(parent=None, default_output_dir=None):
    """Open the converter tool window."""
    return _open_converter_window(parent=parent, default_output_dir=default_output_dir)


def open_background_remover(parent=None):
    """Open the background remover tool window."""
    return _open_background_remover(parent)


def open_screenshot_studio(parent=None):
    """Open the screenshot tool window."""
    return _open_screenshot_studio(parent)


def open_yscreenrecorder(parent=None):
    """Open the recorder tool window."""
    return _open_yscreenrecorder(parent)


def open_anika(parent=None):
    """Open the Anika desktop assistant."""
    return _open_anika(parent)


def open_anika_settings(parent=None):
    """Open Anika break reminder settings."""
    return _open_anika_settings(parent)

