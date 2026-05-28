"""Lightweight architecture boundary checks for desktop_tools."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src" / "desktop_tools"
SHARED_ROOT = SRC_ROOT / "shared"
TOOLS_ROOT = SRC_ROOT / "tools"


def _iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _collect_imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def run_checks() -> list[str]:
    errors: list[str] = []

    for path in _iter_python_files(SHARED_ROOT):
        for module_name in _collect_imports(path):
            if module_name.startswith("desktop_tools.app") or module_name.startswith("desktop_tools.tools"):
                errors.append(f"{path}: shared layer must not import app/tools ({module_name})")

    allowed_tool_app_prefixes = {
        "desktop_tools.app.ui.entrypoints",
        "desktop_tools.app.build_tools",
    }
    for path in _iter_python_files(TOOLS_ROOT):
        for module_name in _collect_imports(path):
            if module_name.startswith("desktop_tools.app") and not any(
                module_name.startswith(prefix) for prefix in allowed_tool_app_prefixes
            ):
                errors.append(f"{path}: tools layer import not allowed ({module_name})")

    return errors


def main() -> None:
    errors = run_checks()
    if errors:
        print("Architecture boundary check failed:")
        for error in errors:
            print(f" - {error}")
        raise SystemExit(1)
    print("Architecture boundary check passed.")


if __name__ == "__main__":
    main()

