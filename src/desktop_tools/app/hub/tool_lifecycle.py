"""Close desktop tools launched from the Media Downloader hub."""

from __future__ import annotations


def close_all_hub_tools() -> None:
    """Shut down Anika and every hub tool window/process."""
    from desktop_tools.app.ui.anika_app import terminate_anika
    from desktop_tools.app.ui.anika_settings_app import force_close_anika_settings_if_open
    from desktop_tools.app.ui.background_remover_app import force_close_background_remover_if_open
    from desktop_tools.app.ui.converter_app import force_close_converter_if_open
    from desktop_tools.app.ui.screenshot_app import force_close_screenshot_if_open
    from desktop_tools.app.ui.yscreenrecorder_app import force_close_yscreenrecorder_if_open

    for closer in (
        terminate_anika,
        force_close_anika_settings_if_open,
        force_close_converter_if_open,
        force_close_background_remover_if_open,
        force_close_screenshot_if_open,
        force_close_yscreenrecorder_if_open,
    ):
        try:
            closer()
        except Exception:
            pass
