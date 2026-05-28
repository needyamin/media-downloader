"""Shared runtime/window helpers for desktop tool apps."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path


def ensure_src_on_path(file_path: str) -> Path:
    """Ensure the repository src directory is importable for script launches."""
    src_dir = Path(file_path).resolve().parents[2]
    src_dir_str = str(src_dir)
    if src_dir_str not in sys.path:
        sys.path.insert(0, src_dir_str)
    return src_dir


def create_hidden_root(parent: tk.Tk | tk.Toplevel | None) -> tuple[tk.Tk | tk.Toplevel, tk.Tk | None]:
    """Return parent window plus optional hidden root for standalone mode."""
    if parent is not None:
        return parent, None
    standalone_root = tk.Tk()
    standalone_root.withdraw()
    return standalone_root, standalone_root


def cleanup_hidden_root(root: tk.Tk | None) -> None:
    """Destroy hidden standalone root safely."""
    if root is None:
        return
    try:
        root.destroy()
    except Exception:
        pass
