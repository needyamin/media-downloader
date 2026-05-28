# Desktop Tools Architecture

This package contains the desktop product for Media Downloader.

## Folder map

```text
src/desktop_tools/
├── app/                           # Main app package
│   ├── media_download.py          # Main desktop hub window
│   ├── app_windowing.py           # Shared startup/window lifecycle helpers
│   ├── config/                    # Runtime flags and app settings helpers
│   ├── hub/                       # Hub-level UI actions
│   ├── platform/                  # Platform integration constants/helpers
│   ├── services/                  # Service-layer orchestration helpers
│   ├── ui/                        # Tool UIs + centralized UI launchers
│   │   ├── converter_app.py
│   │   ├── background_remover_app.py
│   │   ├── screenshot_app.py
│   │   ├── yscreenrecorder_app.py
│   │   └── launchers.py
│   ├── build_tools/               # Build scripts and module entrypoints
│   ├── assets/                    # Icons and images
│   ├── docs/                      # Tool-specific docs
│   └── installer/                 # Windows installer script
├── shared/                        # Reusable non-UI services (ffmpeg, capture, downloads)
└── tools/                         # Stable, import-friendly launch/entrypoint API
    └── media_downloader/
        ├── main.py                # Canonical main app entrypoint
        └── launchers.py           # Canonical tool launcher functions
```

## Recommended engineering workflow

- Keep concrete GUI logic in `app/`.
- Keep cross-tool reusable logic in `shared/`.
- Import from `tools/media_downloader` in scripts/tests/integrations to avoid hardcoding app file paths.
- Treat `tools/media_downloader` as the stable API surface; `app/` internals may change.

## Quick validation commands

- `python -c "import sys; sys.path.insert(0, 'src'); import desktop_tools.tools.architecture_guard as guard; guard.main()"`
- `python -c "import sys; sys.path.insert(0, 'src'); import desktop_tools.tools.smoke_checks as smoke; smoke.main()"`

