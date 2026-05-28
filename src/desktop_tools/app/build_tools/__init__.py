"""Organized build entrypoints for packaging scripts."""

from .linux_appimage import main as build_linux_appimage
from .manifest import main as build_manifest
from .nuitka import main as build_windows_installer

__all__ = [
    "build_windows_installer",
    "build_linux_appimage",
    "build_manifest",
]

