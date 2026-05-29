"""Pure edge-hide rules for Anika (testable without Tk)."""

from __future__ import annotations


def sprite_screen_bounds(
    window_x: float,
    window_y: float,
    window_w: float,
    window_h: float,
    char_w: float,
    char_h: float,
) -> tuple[float, float, float, float]:
    """Return sprite left, top, right, bottom in screen coordinates."""
    cx = window_w / 2
    cy = window_h - (char_h / 2) - 10
    return (
        window_x + cx - (char_w / 2),
        window_y + cy - (char_h / 2),
        window_x + cx + (char_w / 2),
        window_y + cy + (char_h / 2),
    )


def sprite_offscreen_amounts(
    sl: float,
    st: float,
    sr: float,
    sb: float,
    wl: float,
    wt: float,
    wr: float,
    wb: float,
) -> tuple[float, float, float, float]:
    return (
        max(0.0, wl - sl),
        max(0.0, sr - wr),
        max(0.0, wt - st),
        max(0.0, sb - wb),
    )


def hide_threshold_px(sprite_h: float, frac: float = 0.85) -> int:
    frac = max(0.75, min(0.95, frac))
    return max(100, int(sprite_h * frac))


def pointer_exit_side(px: float, py: float, wl: float, wt: float, wr: float, wb: float) -> str | None:
    """Which screen edge the cursor crossed (never bottom/taskbar)."""
    if px < wl:
        return "left"
    if px > wr:
        return "right"
    if py < wt:
        return "top"
    return None


def classify_edge_hide(
    *,
    edge_hide_enabled: bool,
    cursor_offscreen: bool,
    exit_side: str | None,
    dist_moved: float,
    min_drag_px: float,
    left_off: float,
    right_off: float,
    top_off: float,
    threshold_px: int,
    at_taskbar: bool = False,
) -> str | None:
    """
    Return hide_left/right/top, taskbar, or None.

    Hide only when the user drags the cursor off-screen and most of the sprite
    follows past that same edge.
    """
    if not edge_hide_enabled:
        return "taskbar" if at_taskbar else None

    if not cursor_offscreen or exit_side not in ("left", "right", "top"):
        if at_taskbar:
            return "taskbar"
        return None
    if dist_moved < min_drag_px:
        return None

    if exit_side == "left" and left_off >= threshold_px:
        return "hide_left"
    if exit_side == "right" and right_off >= threshold_px:
        return "hide_right"
    if exit_side == "top" and top_off >= threshold_px:
        return "hide_top"
    if at_taskbar:
        return "taskbar"
    return None
