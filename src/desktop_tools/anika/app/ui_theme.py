"""UI theme for Anika windows — aligned with Media Downloader hub styling."""

from __future__ import annotations

# Matches media_download.py THEME_DEFAULTS / hub tool windows.
HUB_MATCHED_THEME = {
    "bg": "#ffffff",
    "frame": "#ECEFF1",
    "accent": "#2196F3",
    "accent_hover": "#1565C0",
    "text": "#1a1a1a",
    "text_dim": "#424242",
    "text_on_accent": "#ffffff",
    "text_on_accent_dim": "#E3F2FD",
    "btn_secondary_bg": "#E3F2FD",
    "btn_secondary_hover": "#BBDEFB",
    "btn_secondary_text": "#0D47A1",
    "btn_inactive_bg": "#CFD8DC",
    "btn_inactive_text": "#263238",
    "tab_inactive_bg": "#ECEFF1",
    "tab_inactive_text": "#37474F",
    "bubble_fill": "#ffffff",
    "bubble_text": "#1a1a1a",
    "gold": "#F57F17",
    "danger": "#D32F2F",
    "danger_hover": "#B71C1C",
    "success": "#2E7D32",
    "border": "#90A4AE",
    "name": "Media Downloader",
}


def enrich_theme(theme: dict) -> dict:
    """Add contrast-safe keys used by settings dialogs."""
    merged = {**HUB_MATCHED_THEME, **theme}
    return {
        **merged,
        "text_on_accent": merged.get("text_on_accent", "#ffffff"),
        "text_on_accent_dim": merged.get("text_on_accent_dim", "#E3F2FD"),
        "btn_secondary_bg": merged.get("btn_secondary_bg", "#E3F2FD"),
        "btn_secondary_hover": merged.get("btn_secondary_hover", "#BBDEFB"),
        "btn_secondary_text": merged.get("btn_secondary_text", "#0D47A1"),
        "btn_inactive_bg": merged.get("btn_inactive_bg", "#CFD8DC"),
        "btn_inactive_text": merged.get("btn_inactive_text", "#263238"),
        "tab_inactive_bg": merged.get("tab_inactive_bg", merged.get("frame", "#ECEFF1")),
        "tab_inactive_text": merged.get("tab_inactive_text", "#37474F"),
    }

# Flat keys for hub break-settings window (tkinter).
HUB_FLAT_THEME = {
    "PRIMARY_BG": HUB_MATCHED_THEME["bg"],
    "SURFACE_BG": HUB_MATCHED_THEME["frame"],
    "CARD_BG": HUB_MATCHED_THEME["bg"],
    "BORDER": HUB_MATCHED_THEME["border"],
    "ACCENT": HUB_MATCHED_THEME["accent"],
    "ACCENT_HOVER": HUB_MATCHED_THEME["accent_hover"],
    "TEXT_MAIN": HUB_MATCHED_THEME["text"],
    "TEXT_MUTED": HUB_MATCHED_THEME["text_dim"],
    "SUCCESS": HUB_MATCHED_THEME["success"],
    "DANGER": HUB_MATCHED_THEME["danger"],
}


def get_ui_theme() -> dict:
    """Return the theme dict used by CustomTkinter Anika dialogs."""
    return HUB_MATCHED_THEME.copy()


def apply_ctk_appearance() -> None:
    """Match Media Downloader light hub appearance."""
    try:
        import customtkinter as ctk

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
    except Exception:
        pass


def load_hub_theme_from_desktop_tools() -> dict | None:
    """Load hub theme from desktop_tools when running inside the monorepo."""
    try:
        import sys
        from pathlib import Path

        anika_dir = Path(__file__).resolve().parents[1]
        src_dir = anika_dir.parent.parent
        src_str = str(src_dir)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)
        from desktop_tools.app.config.runtime_flags import get_tool_theme

        hub = get_tool_theme(
            "media_downloader",
            {
                "bg": "#ffffff",
                "fg": "#333333",
                "primary": "#2196F3",
                "secondary": "#1976D2",
                "success": "#4CAF50",
                "error": "#F44336",
                "warning": "#FFC107",
                "gray": "#757575",
                "light_gray": "#f5f5f5",
                "border": "#e0e0e0",
            },
        )
        return {
            "bg": hub.get("bg", HUB_MATCHED_THEME["bg"]),
            "frame": hub.get("light_gray", HUB_MATCHED_THEME["frame"]),
            "accent": hub.get("primary", HUB_MATCHED_THEME["accent"]),
            "accent_hover": hub.get("secondary", HUB_MATCHED_THEME["accent_hover"]),
            "text": hub.get("fg", HUB_MATCHED_THEME["text"]),
            "text_dim": hub.get("gray", HUB_MATCHED_THEME["text_dim"]),
            "bubble_fill": hub.get("bg", "#ffffff"),
            "bubble_text": hub.get("fg", HUB_MATCHED_THEME["text"]),
            "gold": hub.get("warning", HUB_MATCHED_THEME["gold"]),
            "danger": hub.get("error", HUB_MATCHED_THEME["danger"]),
            "danger_hover": "#D32F2F",
            "success": hub.get("success", HUB_MATCHED_THEME["success"]),
            "border": hub.get("border", HUB_MATCHED_THEME["border"]),
            "name": "Media Downloader",
        }
    except Exception:
        return None
