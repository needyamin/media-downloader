"""Legacy launcher path for the Windows Nuitka build (kept for old docs/commands).

Preferred (from repo root):

    $env:PYTHONPATH = "src"
    python -m desktop_tools.app.build_tools.nuitka
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from desktop_tools.app.build_tools.nuitka_build import main

if __name__ == "__main__":
    main()
