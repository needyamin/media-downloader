"""UI-level launchers for desktop tools."""


def open_main_hub():
    from .launchers import open_main_hub as _open_main_hub
    return _open_main_hub()


def open_converter(parent=None):
    from .launchers import open_converter as _open_converter
    return _open_converter(parent=parent)


def open_background_remover(parent=None):
    from .launchers import open_background_remover as _open_background_remover
    return _open_background_remover(parent=parent)


def open_screenshot_studio(parent=None):
    from .launchers import open_screenshot_studio as _open_screenshot_studio
    return _open_screenshot_studio(parent=parent)


def open_yscreenrecorder(parent=None):
    from .launchers import open_yscreenrecorder as _open_yscreenrecorder
    return _open_yscreenrecorder(parent=parent)


def open_anika(parent=None):
    from .launchers import open_anika as _open_anika
    return _open_anika(parent=parent)


def open_anika_settings(parent=None):
    from .launchers import open_anika_settings as _open_anika_settings
    return _open_anika_settings(parent=parent)

__all__ = [
    "open_main_hub",
    "open_converter",
    "open_background_remover",
    "open_screenshot_studio",
    "open_anika",
    "open_anika_settings",
    "open_yscreenrecorder",
]

