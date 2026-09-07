"""Global hotkey constants shared by desktop hub features."""

from __future__ import annotations

from desktop_tools.app.config.runtime_flags import (
    HOTKEY_BACKGROUND_REMOVER,
    HOTKEY_CONVERTER,
    HOTKEY_RECORD_FINISH,
    HOTKEY_RECORD_PAUSE,
    HOTKEY_SCREENRECORDER,
    HOTKEY_SCREENSHOT,
    HOTKEY_ANIKA,
)

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_ALT = 0x0001
MOD_NOREPEAT = 0x4000

CONVERTER_HOTKEY_ID = 0x5943
BG_REMOVER_HOTKEY_ID = 0x5942
SCREENSHOT_HOTKEY_ID = 0x594D
SCREENRECORDER_HOTKEY_ID = 0x5952
ANIKA_HOTKEY_ID = 0x5955
YSCREENRECORDER_FINISH_HOTKEY_ID = 0x5953
YSCREENRECORDER_PAUSE_HOTKEY_ID = 0x5950


def _parse_hotkey(combo: str, fallback_label: str) -> tuple[int, int, str]:
    """Parse hotkey combo text into Win32 modifiers, VK code, and label."""
    if not isinstance(combo, str):
        combo = fallback_label
    normalized = combo.strip()
    if not normalized:
        normalized = fallback_label

    parts = [part.strip() for part in normalized.replace(" ", "").split("+") if part.strip()]
    if not parts:
        parts = fallback_label.replace(" ", "").split("+")

    modifiers = MOD_NOREPEAT
    key_part = parts[-1]
    modifier_parts = parts[:-1]

    for modifier in modifier_parts:
        upper = modifier.upper()
        if upper in {"CTRL", "CONTROL"}:
            modifiers |= MOD_CONTROL
        elif upper == "SHIFT":
            modifiers |= MOD_SHIFT
        elif upper == "ALT":
            modifiers |= MOD_ALT

    if len(key_part) == 1 and key_part.isprintable():
        vk_code = ord(key_part.upper())
    else:
        vk_code = ord(fallback_label[-1].upper())

    label_parts = []
    if modifiers & MOD_CONTROL:
        label_parts.append("Ctrl")
    if modifiers & MOD_SHIFT:
        label_parts.append("Shift")
    if modifiers & MOD_ALT:
        label_parts.append("Alt")
    label_parts.append(chr(vk_code))
    label = "+".join(label_parts)
    return modifiers, vk_code, label


CONVERTER_HOTKEY_MODIFIERS, CONVERTER_HOTKEY_VK, CONVERTER_HOTKEY_LABEL = _parse_hotkey(
    HOTKEY_CONVERTER,
    "Ctrl+Shift+V",
)
BG_REMOVER_HOTKEY_MODIFIERS, BG_REMOVER_HOTKEY_VK, BG_REMOVER_HOTKEY_LABEL = _parse_hotkey(
    HOTKEY_BACKGROUND_REMOVER,
    "Ctrl+Shift+B",
)
SCREENSHOT_HOTKEY_MODIFIERS, SCREENSHOT_HOTKEY_VK, SCREENSHOT_HOTKEY_LABEL = _parse_hotkey(
    HOTKEY_SCREENSHOT,
    "Ctrl+Shift+Y",
)
SCREENRECORDER_HOTKEY_MODIFIERS, SCREENRECORDER_HOTKEY_VK, SCREENRECORDER_HOTKEY_LABEL = _parse_hotkey(
    HOTKEY_SCREENRECORDER,
    "Ctrl+Shift+R",
)
ANIKA_HOTKEY_MODIFIERS, ANIKA_HOTKEY_VK, ANIKA_HOTKEY_LABEL = _parse_hotkey(
    HOTKEY_ANIKA,
    "Ctrl+Shift+A",
)
YSCREENRECORDER_PAUSE_HOTKEY_MODIFIERS, YSCREENRECORDER_PAUSE_HOTKEY_VK, YSCREENRECORDER_PAUSE_HOTKEY_LABEL = _parse_hotkey(
    HOTKEY_RECORD_PAUSE,
    "Ctrl+Shift+P",
)
YSCREENRECORDER_FINISH_HOTKEY_MODIFIERS, YSCREENRECORDER_FINISH_HOTKEY_VK, YSCREENRECORDER_FINISH_HOTKEY_LABEL = _parse_hotkey(
    HOTKEY_RECORD_FINISH,
    "Ctrl+Shift+S",
)

