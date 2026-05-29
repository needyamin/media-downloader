"""Entrypoints for the Media Downloader desktop suite."""

from .launchers import (
    open_background_remover,
    open_converter,
    open_screenshot_studio,
    open_anika,
    open_anika_settings,
    open_yscreenrecorder,
)
from .main import run_main_app

__all__ = [
    "run_main_app",
    "open_converter",
    "open_background_remover",
    "open_screenshot_studio",
    "open_anika",
    "open_anika_settings",
    "open_yscreenrecorder",
]

