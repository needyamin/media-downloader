"""Compatibility forwarders to canonical desktop tool launchers."""

from __future__ import annotations

from desktop_tools.tools.media_downloader.launchers import (
    open_background_remover as _open_background_remover,
    open_converter as _open_converter,
    open_screenshot_studio as _open_screenshot_studio,
    open_anika as _open_anika,
    open_anika_settings as _open_anika_settings,
    open_yscreenrecorder as _open_yscreenrecorder,
)
from desktop_tools.tools.media_downloader.main import run_main_app


def open_main_hub() -> None:
    """Run the main Media Downloader hub UI (forwarded)."""
    run_main_app()


def open_converter(parent=None):
    return _open_converter(parent=parent)


def open_background_remover(parent=None):
    return _open_background_remover(parent=parent)


def open_screenshot_studio(parent=None):
    return _open_screenshot_studio(parent=parent)


def open_yscreenrecorder(parent=None):
    return _open_yscreenrecorder(parent=parent)


def open_anika(parent=None):
    return _open_anika(parent=parent)


def open_anika_settings(parent=None):
    return _open_anika_settings(parent=parent)

