"""Import and entrypoint smoke checks for desktop tool architecture."""

from __future__ import annotations

import importlib


MODULES = [
    "desktop_tools.tools.media_downloader.main",
    "desktop_tools.tools.media_downloader.launchers",
    "desktop_tools.app.build_tools.manifest",
    "desktop_tools.app.build_tools.nuitka",
    "desktop_tools.app.build_tools.linux_appimage",
]


def main() -> None:
    for module_name in MODULES:
        importlib.import_module(module_name)
        print(f"OK import: {module_name}")

    from desktop_tools.app.build_tools import manifest

    if not callable(getattr(manifest, "main", None)):
        raise SystemExit("Expected desktop_tools.app.build_tools.manifest.main to be callable")
    print("OK callable: desktop_tools.app.build_tools.manifest.main")

    print("Smoke checks passed.")


if __name__ == "__main__":
    main()

