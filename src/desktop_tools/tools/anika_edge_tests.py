"""Tests for Anika drag-to-edge hide rules."""

from __future__ import annotations

import sys
from pathlib import Path

ANIKA_DIR = Path(__file__).resolve().parents[1] / "anika"
if str(ANIKA_DIR) not in sys.path:
    sys.path.insert(0, str(ANIKA_DIR))

from app.edge_hide import (  # noqa: E402
    classify_edge_hide,
    hide_threshold_px,
    pointer_exit_side,
    sprite_offscreen_amounts,
    sprite_screen_bounds,
)


def _bounds_at_left_edge(w=520, h=400, char_w=308, char_h=308, wl=0, wt=0, wr=1920, wb=1040):
    """Window clamped to left boundary — sprite still mostly on screen."""
    x = wl
    y = wb - h
    sl, st, sr, sb = sprite_screen_bounds(x, y, w, h, char_w, char_h)
    amounts = sprite_offscreen_amounts(sl, st, sr, sb, wl, wt, wr, wb)
    return x, y, amounts


def test_boundary_drag_does_not_hide() -> None:
    """Dragging to the screen edge with cursor still on-screen must not hide."""
    x, y, (left_off, right_off, top_off, bottom_off) = _bounds_at_left_edge()
    thresh = hide_threshold_px(308)
    assert left_off < thresh, f"left_off={left_off} should be below threshold {thresh}"
    result = classify_edge_hide(
        edge_hide_enabled=True,
        cursor_offscreen=False,
        exit_side=None,
        dist_moved=120,
        min_drag_px=80,
        left_off=left_off,
        right_off=right_off,
        top_off=top_off,
        threshold_px=thresh,
    )
    assert result is None, f"expected no hide at boundary, got {result}"


def test_cursor_offscreen_but_sprite_not_far_enough() -> None:
    """Cursor off-screen alone is not enough — sprite must mostly leave too."""
    w, h, char_w, char_h = 520, 400, 308, 308
    wl, wt, wr, wb = 0, 0, 1920, 1040
    x = wl - 80
    y = wb - h
    sl, st, sr, sb = sprite_screen_bounds(x, y, w, h, char_w, char_h)
    amounts = sprite_offscreen_amounts(sl, st, sr, sb, wl, wt, wr, wb)
    thresh = hide_threshold_px(char_h)
    assert amounts[0] < thresh
    result = classify_edge_hide(
        edge_hide_enabled=True,
        cursor_offscreen=True,
        exit_side="left",
        dist_moved=150,
        min_drag_px=80,
        left_off=amounts[0],
        right_off=amounts[1],
        top_off=amounts[2],
        threshold_px=thresh,
    )
    assert result is None


def test_forceful_left_hide() -> None:
    """Cursor off left + most of sprite off left => hide."""
    w, h, char_w, char_h = 520, 400, 308, 308
    wl, wt, wr, wb = 0, 0, 1920, 1040
    x = wl - 400
    y = wb - h
    sl, st, sr, sb = sprite_screen_bounds(x, y, w, h, char_w, char_h)
    amounts = sprite_offscreen_amounts(sl, st, sr, sb, wl, wt, wr, wb)
    thresh = hide_threshold_px(char_h)
    assert amounts[0] >= thresh
    result = classify_edge_hide(
        edge_hide_enabled=True,
        cursor_offscreen=True,
        exit_side="left",
        dist_moved=200,
        min_drag_px=80,
        left_off=amounts[0],
        right_off=amounts[1],
        top_off=amounts[2],
        threshold_px=thresh,
    )
    assert result == "hide_left"


def test_bottom_never_hides() -> None:
    """Dragging toward taskbar must never trigger edge hide."""
    assert pointer_exit_side(960, 1100, 0, 0, 1920, 1040) is None
    result = classify_edge_hide(
        edge_hide_enabled=True,
        cursor_offscreen=True,
        exit_side="bottom",
        dist_moved=200,
        min_drag_px=80,
        left_off=0,
        right_off=0,
        top_off=0,
        threshold_px=100,
    )
    assert result is None


def test_short_drag_never_hides() -> None:
    result = classify_edge_hide(
        edge_hide_enabled=True,
        cursor_offscreen=True,
        exit_side="left",
        dist_moved=20,
        min_drag_px=80,
        left_off=300,
        right_off=0,
        top_off=0,
        threshold_px=100,
    )
    assert result is None


def main() -> None:
    test_boundary_drag_does_not_hide()
    test_cursor_offscreen_but_sprite_not_far_enough()
    test_forceful_left_hide()
    test_bottom_never_hides()
    test_short_drag_never_hides()
    print("Anika edge-hide tests passed.")


if __name__ == "__main__":
    main()
