"""YScreenshot screenshot overlay with a compact floating toolbar."""

from __future__ import annotations

import io
import math
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox

from PIL import Image, ImageDraw, ImageFont, ImageTk

try:
    import win32clipboard
except Exception:
    win32clipboard = None

try:
    from desktop_tools.app.app_windowing import cleanup_hidden_root, create_hidden_root, ensure_src_on_path
except Exception:
    from app_windowing import cleanup_hidden_root, create_hidden_root, ensure_src_on_path

SRC_DIR = ensure_src_on_path(__file__)

from desktop_tools.shared.capture_support import capture_desktop_snapshot, copy_image_to_linux_clipboard
from desktop_tools.app.config.runtime_flags import SCREENSHOT_DIM_ALPHA, get_tool_theme

TOOL_SPECS = {
    "pen": {"icon": "✎", "label": "Pen"},
    "highlighter": {"icon": "🖍", "label": "Mark"},
    "line": {"icon": "／", "label": "Line"},
    "arrow": {"icon": "➜", "label": "Arrow"},
    "border": {"icon": "▭", "label": "Box"},
    "circle": {"icon": "◯", "label": "Circle"},
    "triangle": {"icon": "△", "label": "Tri"},
    "text": {"icon": "T", "label": "Text"},
}

ACTION_SPECS = {
    "color": {"icon": "◈", "label": "Color"},
    "size_down": {"icon": "－", "label": "Size -"},
    "size_up": {"icon": "＋", "label": "Size +"},
    "copy": {"icon": "⧉", "label": "Copy"},
    "undo": {"icon": "↶", "label": "Undo"},
    "redo": {"icon": "↷", "label": "Redo"},
    "save": {"icon": "⤓", "label": "Save"},
    "reset": {"icon": "⟲", "label": "Reset"},
    "close": {"icon": "✕", "label": "Close"},
}

QUICK_COLORS = ["#FF4D6D", "#F97316", "#FACC15", "#22C55E", "#38BDF8", "#8B5CF6", "#FFFFFF"]
STROKE_WIDTHS = [3, 6, 10]
TEXT_SIZES = [16, 22, 30, 40]

SCREENSHOT_THEME_DEFAULTS = {
    "HUD_BG": "#0B1220",
    "HUD_BORDER": "#253348",
    "HUD_ACTIVE": "#38BDF8",
    "HUD_PANEL": "#101826",
    "HUD_TEXT": "#F8FAFC",
    "HUD_MUTED": "#94A3B8",
    "SELECTION_OUTLINE": "#38BDF8",
}
SCREENSHOT_THEME = get_tool_theme("screenshot", SCREENSHOT_THEME_DEFAULTS)
SCREEN_DIM_ALPHA = SCREENSHOT_DIM_ALPHA
HUD_BG = SCREENSHOT_THEME["HUD_BG"]
HUD_BORDER = SCREENSHOT_THEME["HUD_BORDER"]
HUD_ACTIVE = SCREENSHOT_THEME["HUD_ACTIVE"]
HUD_PANEL = SCREENSHOT_THEME["HUD_PANEL"]
HUD_TEXT = SCREENSHOT_THEME["HUD_TEXT"]
HUD_MUTED = SCREENSHOT_THEME["HUD_MUTED"]
SELECTION_OUTLINE = SCREENSHOT_THEME["SELECTION_OUTLINE"]

screenshot_window = None


class ScreenshotOverlay(tk.Toplevel):
    """A compact YScreenshot overlay for selecting and annotating screenshots."""

    def __init__(self, parent=None):
        parent, self._standalone_root = create_hidden_root(parent)

        super().__init__(parent)
        self.parent_window = parent if isinstance(parent, (tk.Tk, tk.Toplevel)) else None

        self.base_image, self.virtual_x, self.virtual_y, self.screen_width, self.screen_height = self._capture_screen()
        self.dimmed_image = Image.blend(
            self.base_image,
            Image.new("RGBA", self.base_image.size, (0, 0, 0, 255)),
            SCREEN_DIM_ALPHA,
        )

        self.background_photo = ImageTk.PhotoImage(self.dimmed_image)
        self.selection_photo = None
        self._preview_item = None

        self.active_tool = "pen"
        self.current_color = QUICK_COLORS[0]
        self.stroke_index = 1
        self.text_size_index = 1
        self.selection_box = None
        self.selection_anchor = None
        self.mode = "select"
        self.actions = []
        self.redo_stack = []
        self.drag_origin = None
        self.drag_points = []
        self.text_editor = None
        self.text_editor_window = None
        self.text_editor_origin = None
        self._text_focus_job = None

        self.toolbar_buttons = {}
        self.color_swatches = []
        self.size_down_button = None
        self.size_up_button = None
        self.size_value_label = None
        self.tool_window = None
        self.style_window = None
        self.action_window = None
        self.help_items = []
        self.selection_image_item = None
        self.selection_border_item = None
        self.selection_label_item = None
        self.selection_handles = []

        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry(f"{self.screen_width}x{self.screen_height}+{self.virtual_x}+{self.virtual_y}")
        self.configure(bg="black")

        self.canvas = tk.Canvas(
            self,
            width=self.screen_width,
            height=self.screen_height,
            highlightthickness=0,
            bd=0,
            cursor="crosshair",
            bg="black",
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, anchor="nw", image=self.background_photo)

        self._create_help_overlay()
        self._build_toolbar()
        self._bind_events()

        self.deiconify()
        self.lift()
        self.focus_force()

    def _capture_screen(self):
        try:
            return capture_desktop_snapshot(self)
        except Exception as exc:
            self.destroy()
            raise RuntimeError(f"Could not capture the screen: {exc}") from exc

    def _bind_events(self):
        self.bind("<Escape>", lambda event: self.on_close())
        self.bind("<Control-s>", lambda event: self.save_selection())
        self.bind("<Control-z>", lambda event: self.undo())
        self.bind("<Control-y>", lambda event: self.redo())
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    def _create_help_overlay(self):
        self.help_items.append(
            self.canvas.create_rectangle(20, 20, 420, 66, fill=HUD_BG, outline=HUD_BORDER, width=1)
        )
        self.help_items.append(
            self.canvas.create_text(
                40,
                42,
                anchor="w",
                fill=HUD_TEXT,
                font=("Segoe UI", 11, "bold"),
                text="YScreenshot: drag to select an area",
            )
        )
        self.help_items.append(
            self.canvas.create_text(
                40,
                57,
                anchor="w",
                fill=HUD_MUTED,
                font=("Segoe UI", 8),
                text="Use the side tools and bottom actions after selecting.",
            )
        )

    def _build_toolbar(self):
        self.tool_frame = tk.Frame(
            self.canvas,
            bg=HUD_PANEL,
            highlightbackground=HUD_BORDER,
            highlightthickness=1,
            bd=0,
            padx=4,
            pady=4,
        )

        for tool_name, meta in TOOL_SPECS.items():
            button = self._make_toolbar_button(
                self.tool_frame,
                meta["icon"],
                meta["label"],
                lambda name=tool_name: self.select_tool(name),
            )
            button.pack(fill="x", padx=2, pady=2)
            self.toolbar_buttons[tool_name] = button

        self.style_frame = tk.Frame(
            self.canvas,
            bg=HUD_PANEL,
            highlightbackground=HUD_BORDER,
            highlightthickness=1,
            bd=0,
            padx=6,
            pady=6,
        )

        size_frame = tk.Frame(self.style_frame, bg=HUD_PANEL)
        size_frame.pack(side="left", padx=(0, 6))

        self.size_down_button = self._make_compact_control_button(
            size_frame,
            ACTION_SPECS["size_down"]["icon"],
            self.decrease_stroke_width,
        )
        self.size_down_button.pack(side="left", padx=(0, 3))

        self.size_value_label = tk.Label(
            size_frame,
            text="Size 6 px",
            bg="#152238",
            fg=HUD_TEXT,
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=5,
        )
        self.size_value_label.pack(side="left", padx=(0, 3))

        self.size_up_button = self._make_compact_control_button(
            size_frame,
            ACTION_SPECS["size_up"]["icon"],
            self.increase_stroke_width,
        )
        self.size_up_button.pack(side="left")

        color_button = self._make_toolbar_button(
            self.style_frame,
            ACTION_SPECS["color"]["icon"],
            ACTION_SPECS["color"]["label"],
            self.choose_color,
        )
        color_button.pack(side="left", padx=(0, 4))

        copy_button = self._make_toolbar_button(
            self.style_frame,
            ACTION_SPECS["copy"]["icon"],
            ACTION_SPECS["copy"]["label"],
            self.copy_selection_to_clipboard,
        )
        copy_button.pack(side="left", padx=(0, 8))

        color_row = tk.Frame(self.style_frame, bg=HUD_PANEL)
        color_row.pack(side="left")

        for index, color in enumerate(QUICK_COLORS):
            swatch = tk.Button(
                color_row,
                bg=color,
                activebackground=color,
                width=2,
                height=1,
                relief="flat",
                bd=0,
                cursor="hand2",
                highlightthickness=2,
                command=lambda value=color: self.set_color(value),
            )
            swatch.grid(row=0, column=index, padx=2, pady=0)
            self.color_swatches.append((color, swatch))

        self.action_frame = tk.Frame(
            self.canvas,
            bg=HUD_PANEL,
            highlightbackground=HUD_BORDER,
            highlightthickness=1,
            bd=0,
            padx=4,
            pady=4,
        )

        self._make_toolbar_button(
            self.action_frame,
            ACTION_SPECS["undo"]["icon"],
            ACTION_SPECS["undo"]["label"],
            self.undo,
        ).pack(side="left", padx=2, pady=2)
        self._make_toolbar_button(
            self.action_frame,
            ACTION_SPECS["redo"]["icon"],
            ACTION_SPECS["redo"]["label"],
            self.redo,
        ).pack(side="left", padx=2, pady=2)
        self._make_toolbar_button(
            self.action_frame,
            ACTION_SPECS["save"]["icon"],
            ACTION_SPECS["save"]["label"],
            self.save_selection,
        ).pack(side="left", padx=2, pady=2)
        self._make_toolbar_button(
            self.action_frame,
            ACTION_SPECS["reset"]["icon"],
            ACTION_SPECS["reset"]["label"],
            self.reset_selection,
        ).pack(side="left", padx=2, pady=2)
        self._make_toolbar_button(
            self.action_frame,
            ACTION_SPECS["close"]["icon"],
            ACTION_SPECS["close"]["label"],
            self.on_close,
        ).pack(side="left", padx=2, pady=2)

        self.tool_window = self.canvas.create_window(0, 0, anchor="nw", window=self.tool_frame, state="hidden")
        self.style_window = self.canvas.create_window(0, 0, anchor="nw", window=self.style_frame, state="hidden")
        self.action_window = self.canvas.create_window(0, 0, anchor="nw", window=self.action_frame, state="hidden")
        self._refresh_toolbar_state()

    def _make_toolbar_button(self, parent, icon, label, command):
        return tk.Button(
            parent,
            text=f"{icon}\n{label}",
            command=command,
            bg=HUD_PANEL,
            fg=HUD_TEXT,
            activebackground="#152238",
            activeforeground=HUD_TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=4,
            pady=3,
            width=7,
            height=2,
            justify="center",
            font=("Segoe UI Symbol", 8, "bold"),
            highlightthickness=0,
            takefocus=0,
        )

    def _make_compact_control_button(self, parent, text, command):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg="#152238",
            fg=HUD_TEXT,
            activebackground=HUD_ACTIVE,
            activeforeground="#031925",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=6,
            pady=4,
            width=2,
            height=1,
            justify="center",
            font=("Segoe UI Symbol", 10, "bold"),
            highlightthickness=0,
            takefocus=0,
        )

    def _refresh_toolbar_state(self):
        for tool_name, button in self.toolbar_buttons.items():
            active = tool_name == self.active_tool
            button.configure(
                bg=HUD_ACTIVE if active else HUD_PANEL,
                fg="#031925" if active else HUD_TEXT,
                activebackground=HUD_ACTIVE if active else "#152238",
                activeforeground="#031925" if active else HUD_TEXT,
            )

        for color, swatch in self.color_swatches:
            swatch.configure(highlightbackground=HUD_ACTIVE if color == self.current_color else HUD_BG)

        if self.size_value_label is not None:
            if self.active_tool == "text":
                self.size_value_label.configure(text=f"Text {self._current_text_size()} px")
            else:
                self.size_value_label.configure(text=f"Size {STROKE_WIDTHS[self.stroke_index]} px")

    def _canvas_point(self, event):
        x = max(0, min(int(event.x), self.screen_width - 1))
        y = max(0, min(int(event.y), self.screen_height - 1))
        return (x, y)

    def _normalize_box(self, start, end, minimum_size=8):
        x0 = min(start[0], end[0])
        y0 = min(start[1], end[1])
        x1 = max(start[0], end[0])
        y1 = max(start[1], end[1])
        if x1 - x0 < minimum_size or y1 - y0 < minimum_size:
            return None
        return (x0, y0, x1, y1)

    def _point_in_selection(self, point):
        if self.selection_box is None:
            return False
        x0, y0, x1, y1 = self.selection_box
        return x0 <= point[0] <= x1 and y0 <= point[1] <= y1

    def _clamp_to_selection(self, point):
        if self.selection_box is None:
            return point
        x0, y0, x1, y1 = self.selection_box
        return (max(x0, min(point[0], x1)), max(y0, min(point[1], y1)))

    def _hide_toolbar(self):
        for window in (self.tool_window, self.style_window, self.action_window):
            if window is not None:
                self.canvas.itemconfigure(window, state="hidden")

    def _show_toolbar(self):
        self._refresh_toolbar_state()
        for window in (self.tool_window, self.style_window, self.action_window):
            if window is not None:
                self.canvas.itemconfigure(window, state="normal")
        self._position_toolbar()

    def _position_toolbar(self):
        if self.selection_box is None:
            self._hide_toolbar()
            return

        self.update_idletasks()
        tool_width = self.tool_frame.winfo_reqwidth()
        tool_height = self.tool_frame.winfo_reqheight()
        style_width = self.style_frame.winfo_reqwidth()
        style_height = self.style_frame.winfo_reqheight()
        action_width = self.action_frame.winfo_reqwidth()
        action_height = self.action_frame.winfo_reqheight()
        x0, y0, x1, y1 = self.selection_box

        tool_x = x1 + 10
        if tool_x + tool_width > self.screen_width - 8:
            tool_x = x0 - tool_width - 10
        tool_x = max(8, tool_x)
        tool_y = min(max(y0, 8), self.screen_height - tool_height - 8)

        bottom_y = y1 + 10
        if bottom_y + max(style_height, action_height) > self.screen_height - 8:
            bottom_y = y0 - max(style_height, action_height) - 10
        bottom_y = max(8, bottom_y)

        style_x = max(8, min(x0, self.screen_width - style_width - 8))
        action_x = max(8, min(x1 - action_width, self.screen_width - action_width - 8))

        self.canvas.coords(self.tool_window, tool_x, tool_y)
        self.canvas.coords(self.style_window, style_x, bottom_y)
        self.canvas.coords(self.action_window, action_x, bottom_y)

    def select_tool(self, tool_name):
        if tool_name not in TOOL_SPECS:
            return
        if self.active_tool == "text" and tool_name != "text":
            self._commit_text_editor()
        self.active_tool = tool_name
        self._sync_text_editor_style()
        self._refresh_toolbar_state()

    def set_color(self, color):
        self.current_color = color.upper()
        self._sync_text_editor_style()
        self._refresh_toolbar_state()

    def choose_color(self):
        dialog_parent = self.parent_window if self.parent_window and self.parent_window.winfo_exists() else self
        self.attributes("-topmost", False)
        try:
            chosen = colorchooser.askcolor(color=self.current_color, parent=dialog_parent)
        finally:
            self.attributes("-topmost", True)
            self.lift()
        if chosen and chosen[1]:
            self.set_color(chosen[1])

    def decrease_stroke_width(self):
        if self.active_tool == "text":
            if self.text_size_index > 0:
                self.text_size_index -= 1
        else:
            if self.stroke_index > 0:
                self.stroke_index -= 1
        self._sync_text_editor_style()
        self._refresh_toolbar_state()

    def increase_stroke_width(self):
        if self.active_tool == "text":
            if self.text_size_index < len(TEXT_SIZES) - 1:
                self.text_size_index += 1
        else:
            if self.stroke_index < len(STROKE_WIDTHS) - 1:
                self.stroke_index += 1
        self._sync_text_editor_style()
        self._refresh_toolbar_state()

    def _current_text_size(self):
        return TEXT_SIZES[self.text_size_index]

    def _load_text_font(self, size):
        for candidate in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(candidate, size=size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _sync_text_editor_style(self):
        if self.text_editor is None:
            return
        font_spec = ("Segoe UI", self._current_text_size(), "bold")
        self.text_editor.configure(fg=self.current_color, insertbackground=self.current_color, font=font_spec)

    def _destroy_text_editor(self):
        if self._text_focus_job is not None:
            try:
                self.after_cancel(self._text_focus_job)
            except Exception:
                pass
            self._text_focus_job = None
        if self.text_editor_window is not None:
            try:
                self.canvas.delete(self.text_editor_window)
            except Exception:
                pass
        if self.text_editor is not None:
            try:
                self.text_editor.destroy()
            except Exception:
                pass
        self.text_editor = None
        self.text_editor_window = None
        self.text_editor_origin = None

    def _cancel_text_editor(self):
        self._destroy_text_editor()

    def _commit_text_editor(self):
        if self.text_editor is None or self.text_editor_origin is None:
            return False

        raw_text = self.text_editor.get("1.0", "end-1c")
        text_value = raw_text.rstrip()
        position = self.text_editor_origin
        color = self.current_color
        font_size = self._current_text_size()
        self._destroy_text_editor()

        if not text_value.strip():
            return False

        self.actions.append(
            {
                "tool": "text",
                "position": position,
                "text": text_value,
                "color": color,
                "font_size": font_size,
            }
        )
        self.redo_stack = []
        self._refresh_selection_display()
        return True

    def _start_text_editor(self, point):
        if self.selection_box is None:
            return

        self._destroy_text_editor()
        point = self._clamp_to_selection(point)
        self.text_editor_origin = point
        font_spec = ("Segoe UI", self._current_text_size(), "bold")
        self.text_editor = tk.Text(
            self.canvas,
            width=20,
            height=3,
            wrap="word",
            undo=True,
            bd=0,
            relief="flat",
            highlightthickness=1,
            highlightbackground=HUD_BORDER,
            bg="#0F172A",
            fg=self.current_color,
            insertbackground=self.current_color,
            font=font_spec,
            padx=6,
            pady=6,
        )
        self.text_editor_window = self.canvas.create_window(
            point[0],
            point[1],
            anchor="nw",
            window=self.text_editor,
        )
        self.text_editor.bind("<Escape>", lambda event: (self._cancel_text_editor(), "break")[1])
        self.text_editor.bind("<Control-Return>", lambda event: (self._commit_text_editor(), "break")[1])
        self.text_editor.bind("<FocusOut>", lambda event: self.after(0, self._commit_text_editor))
        self.text_editor.bind("<MouseWheel>", self._on_text_editor_wheel)
        self._text_focus_job = self.after(10, self.text_editor.focus_force)

    def _on_text_editor_wheel(self, event):
        if event.delta > 0:
            self.increase_stroke_width()
        elif event.delta < 0:
            self.decrease_stroke_width()
        return "break"

    def _clear_preview(self):
        if self._preview_item is not None:
            self.canvas.delete(self._preview_item)
            self._preview_item = None

    def _clear_selection_items(self):
        self._destroy_text_editor()
        for item_name in ("selection_image_item", "selection_border_item", "selection_label_item"):
            item = getattr(self, item_name)
            if item is not None:
                self.canvas.delete(item)
                setattr(self, item_name, None)
        while self.selection_handles:
            self.canvas.delete(self.selection_handles.pop())
        self.selection_photo = None

    def _refresh_selection_display(self):
        self._clear_selection_items()
        self._clear_preview()

        if self.selection_box is None:
            self._hide_toolbar()
            return

        x0, y0, x1, y1 = self.selection_box
        crop = self._render_selection_crop()
        self.selection_photo = ImageTk.PhotoImage(crop)

        self.selection_image_item = self.canvas.create_image(x0, y0, anchor="nw", image=self.selection_photo)
        self.selection_border_item = self.canvas.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            outline=SELECTION_OUTLINE,
            width=2,
            dash=(8, 4),
        )
        self.selection_label_item = self.canvas.create_text(
            x0 + 10,
            max(14, y0 - 10),
            anchor="sw",
            fill=HUD_TEXT,
            font=("Segoe UI", 10, "bold"),
            text=f"{x1 - x0} x {y1 - y0}",
        )
        self._draw_selection_handles()
        self._show_toolbar()

    def _draw_selection_handles(self):
        if self.selection_box is None:
            return
        x0, y0, x1, y1 = self.selection_box
        for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            handle = self.canvas.create_rectangle(
                cx - 3,
                cy - 3,
                cx + 3,
                cy + 3,
                fill="white",
                outline=SELECTION_OUTLINE,
                width=1,
            )
            self.selection_handles.append(handle)

    def _render_selection_crop(self):
        if self.selection_box is None:
            return self.dimmed_image

        x0, y0, x1, y1 = self.selection_box
        crop = self.base_image.crop((x0, y0, x1, y1)).copy()
        draw = ImageDraw.Draw(crop)
        for action in self.actions:
            self._draw_action(draw, action, offset=(x0, y0), image=crop)
        return crop

    def _draw_action(self, draw, action, offset=(0, 0), image=None):
        ox, oy = offset
        tool = action["tool"]
        color = action["color"]
        width = action.get("width", 0)

        if tool in {"pen", "highlighter"}:
            points = [(px - ox, py - oy) for px, py in action["points"]]
            if tool == "highlighter" and image is not None:
                overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)
                fill_color = self._highlighter_rgba(color)
                if len(points) == 1:
                    x, y = points[0]
                    radius = max(2, width)
                    overlay_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill_color, outline=fill_color)
                else:
                    overlay_draw.line(points, fill=fill_color, width=max(width + 6, width))
                image.alpha_composite(overlay)
                return
            if len(points) == 1:
                x, y = points[0]
                radius = max(1, width // 2)
                draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color, outline=color)
            else:
                draw.line(points, fill=color, width=width)
            return

        if tool == "text":
            position = (action["position"][0] - ox, action["position"][1] - oy)
            font = self._load_text_font(action.get("font_size", self._current_text_size()))
            draw.multiline_text(position, action["text"], fill=color, font=font, spacing=4)
            return

        start = (action["start"][0] - ox, action["start"][1] - oy)
        end = (action["end"][0] - ox, action["end"][1] - oy)

        if tool == "line":
            draw.line((start[0], start[1], end[0], end[1]), fill=color, width=width)
            return

        if tool == "arrow":
            self._draw_arrow(draw, start, end, color, width)
            return

        box = self._normalize_box(start, end, minimum_size=2)
        if box is None:
            return

        if tool == "circle":
            draw.ellipse(box, outline=color, width=width)
        elif tool == "border":
            draw.rounded_rectangle(box, outline=color, width=width, radius=max(10, width * 2))
        elif tool == "triangle":
            points = self._triangle_points(start, end)
            draw.line(points + [points[0]], fill=color, width=width)

    def _draw_arrow(self, draw, start, end, color, width):
        x1, y1 = start
        x2, y2 = end
        if abs(x2 - x1) < 2 and abs(y2 - y1) < 2:
            return

        draw.line((x1, y1, x2, y2), fill=color, width=width)
        angle = math.atan2(y2 - y1, x2 - x1)
        head_length = max(14, width * 3)
        head_width = max(8, width * 1.8)
        left = (
            x2 - head_length * math.cos(angle) + head_width * math.sin(angle),
            y2 - head_length * math.sin(angle) - head_width * math.cos(angle),
        )
        right = (
            x2 - head_length * math.cos(angle) - head_width * math.sin(angle),
            y2 - head_length * math.sin(angle) + head_width * math.cos(angle),
        )
        draw.polygon([(x2, y2), left, right], fill=color)

    def _triangle_points(self, start, end):
        box = self._normalize_box(start, end, minimum_size=2)
        if box is None:
            return [start, end, end]
        x0, y0, x1, y1 = box
        return [((x0 + x1) / 2, y0), (x0, y1), (x1, y1)]

    def _start_selection(self, point):
        self.mode = "select"
        self.selection_anchor = point
        self.selection_box = None
        self.actions = []
        self.redo_stack = []
        self._clear_selection_items()
        self._hide_toolbar()

    def _update_selection(self, point):
        if self.selection_anchor is None:
            return
        self.selection_box = self._normalize_box(self.selection_anchor, point, minimum_size=2)
        self._refresh_selection_display()

    def _finish_selection(self, point):
        if self.selection_anchor is None:
            return
        self.selection_box = self._normalize_box(self.selection_anchor, point)
        self.selection_anchor = None
        self.mode = "ready"
        self._refresh_selection_display()

    def _start_annotation(self, point):
        if self.selection_box is None:
            return
        if self.active_tool == "text":
            self.mode = "ready"
            self._start_text_editor(point)
            return
        self.mode = "annotate"
        self.drag_origin = self._clamp_to_selection(point)
        self.drag_points = [self.drag_origin]
        self._clear_preview()
        color = self.current_color
        width = STROKE_WIDTHS[self.stroke_index]

        if self.active_tool in {"pen", "highlighter"}:
            self._preview_item = self.canvas.create_line(
                self.drag_origin[0],
                self.drag_origin[1],
                self.drag_origin[0],
                self.drag_origin[1],
                fill=color,
                width=width,
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
                smooth=True,
                splinesteps=20,
            )
            if self.active_tool == "highlighter":
                self.canvas.itemconfigure(self._preview_item, stipple="gray25")
        elif self.active_tool == "line":
            self._preview_item = self.canvas.create_line(
                self.drag_origin[0],
                self.drag_origin[1],
                self.drag_origin[0],
                self.drag_origin[1],
                fill=color,
                width=width,
            )
        elif self.active_tool == "arrow":
            self._preview_item = self.canvas.create_line(
                self.drag_origin[0],
                self.drag_origin[1],
                self.drag_origin[0],
                self.drag_origin[1],
                fill=color,
                width=width,
                arrow=tk.LAST,
                arrowshape=(14, 18, 6),
            )
        elif self.active_tool == "circle":
            self._preview_item = self.canvas.create_oval(
                self.drag_origin[0],
                self.drag_origin[1],
                self.drag_origin[0],
                self.drag_origin[1],
                outline=color,
                width=width,
            )
        elif self.active_tool == "border":
            self._preview_item = self.canvas.create_rectangle(
                self.drag_origin[0],
                self.drag_origin[1],
                self.drag_origin[0],
                self.drag_origin[1],
                outline=color,
                width=width,
            )
        elif self.active_tool == "triangle":
            self._preview_item = self.canvas.create_polygon(
                self.drag_origin[0],
                self.drag_origin[1],
                self.drag_origin[0],
                self.drag_origin[1],
                self.drag_origin[0],
                self.drag_origin[1],
                outline=color,
                fill="",
                width=width,
            )

    def _update_annotation(self, point):
        if self.drag_origin is None or self._preview_item is None:
            return

        point = self._clamp_to_selection(point)
        if self.active_tool in {"pen", "highlighter"}:
            self.drag_points.append(point)
            coords = []
            for px, py in self.drag_points:
                coords.extend((px, py))
            self.canvas.coords(self._preview_item, *coords)
            return

        if self.active_tool in {"line", "arrow", "circle", "border"}:
            self.canvas.coords(self._preview_item, self.drag_origin[0], self.drag_origin[1], point[0], point[1])
        elif self.active_tool == "triangle":
            points = self._triangle_points(self.drag_origin, point)
            coords = []
            for px, py in points:
                coords.extend((px, py))
            self.canvas.coords(self._preview_item, *coords)

    def _finish_annotation(self, point):
        if self.drag_origin is None:
            return

        point = self._clamp_to_selection(point)
        width = STROKE_WIDTHS[self.stroke_index]
        action = None

        if self.active_tool in {"pen", "highlighter"}:
            if self.drag_points:
                action = {
                    "tool": self.active_tool,
                    "points": list(self.drag_points),
                    "color": self.current_color,
                    "width": width,
                }
        elif self._normalize_box(self.drag_origin, point):
            action = {
                "tool": self.active_tool,
                "start": self.drag_origin,
                "end": point,
                "color": self.current_color,
                "width": width,
            }

        self.mode = "ready"
        self.drag_origin = None
        self.drag_points = []
        self._clear_preview()

        if action is None:
            return

        self.actions.append(action)
        self.redo_stack = []
        self._refresh_selection_display()

    def _highlighter_rgba(self, hex_color):
        base = hex_color.lstrip("#")
        if len(base) != 6:
            return (255, 235, 59, 90)
        return (
            int(base[0:2], 16),
            int(base[2:4], 16),
            int(base[4:6], 16),
            96,
        )

    def _on_press(self, event):
        point = self._canvas_point(event)
        if self.text_editor is not None:
            self._commit_text_editor()
        if self.selection_box is None or not self._point_in_selection(point):
            self._start_selection(point)
        else:
            self._start_annotation(point)

    def _on_drag(self, event):
        point = self._canvas_point(event)
        if self.mode == "select":
            self._update_selection(point)
        elif self.mode == "annotate":
            self._update_annotation(point)

    def _on_release(self, event):
        point = self._canvas_point(event)
        if self.mode == "select":
            self._finish_selection(point)
        elif self.mode == "annotate":
            self._finish_annotation(point)

    def reset_selection(self):
        self.mode = "select"
        self.selection_box = None
        self.selection_anchor = None
        self.drag_origin = None
        self.drag_points = []
        self.actions = []
        self.redo_stack = []
        self._clear_selection_items()
        self._hide_toolbar()

    def undo(self):
        self._commit_text_editor()
        if not self.actions:
            return
        self.redo_stack.append(self.actions.pop())
        self._refresh_selection_display()

    def redo(self):
        self._commit_text_editor()
        if not self.redo_stack:
            return
        self.actions.append(self.redo_stack.pop())
        self._refresh_selection_display()

    def save_selection(self):
        self._commit_text_editor()
        if self.selection_box is None:
            dialog_parent = self.parent_window if self.parent_window and self.parent_window.winfo_exists() else self
            messagebox.showinfo("YScreenshot", "Select an area first.", parent=dialog_parent)
            return

        dialog_parent = self.parent_window if self.parent_window and self.parent_window.winfo_exists() else self
        timestamp = time.strftime("%Y%m%d-%H%M%S")

        self.attributes("-topmost", False)
        try:
            file_path = filedialog.asksaveasfilename(
                parent=dialog_parent,
                title="Save annotated screenshot",
                defaultextension=".png",
                initialfile=f"screenshot-{timestamp}.png",
                filetypes=[
                    ("PNG", "*.png"),
                    ("JPEG", "*.jpg;*.jpeg"),
                    ("Bitmap", "*.bmp"),
                    ("WebP", "*.webp"),
                ],
            )
        finally:
            self.attributes("-topmost", True)
            self.lift()

        if not file_path:
            return

        try:
            output = self._render_selection_crop()
            suffix = Path(file_path).suffix.lower()
            if suffix in {".jpg", ".jpeg"}:
                output = output.convert("RGB")
            output.save(file_path)
        except Exception as exc:
            messagebox.showerror("Save Error", f"Could not save the screenshot:\n{exc}", parent=dialog_parent)

    def copy_selection_to_clipboard(self):
        self._commit_text_editor()
        if self.selection_box is None:
            dialog_parent = self.parent_window if self.parent_window and self.parent_window.winfo_exists() else self
            messagebox.showinfo("YScreenshot", "Select an area first.", parent=dialog_parent)
            return

        dialog_parent = self.parent_window if self.parent_window and self.parent_window.winfo_exists() else self

        try:
            image = self._render_selection_crop()
            if sys.platform.startswith("win") and win32clipboard is not None:
                output = io.BytesIO()
                image.convert("RGB").save(output, "BMP")
                data = output.getvalue()[14:]
                output.close()

                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                finally:
                    win32clipboard.CloseClipboard()
                return

            if sys.platform.startswith("linux"):
                copy_image_to_linux_clipboard(image)
                return

            messagebox.showinfo("YScreenshot", "Clipboard image copy is currently available on Windows and Linux only.", parent=dialog_parent)
        except Exception as exc:
            messagebox.showerror("YScreenshot", f"Could not copy the screenshot:\n{exc}", parent=dialog_parent)

    def on_close(self):
        global screenshot_window

        try:
            self.destroy()
        finally:
            if screenshot_window is self:
                screenshot_window = None
            if self._standalone_root is not None:
                cleanup_hidden_root(self._standalone_root)


def open_screenshot_studio(parent=None):
    """Open the YScreenshot overlay as a singleton."""
    global screenshot_window

    if screenshot_window is not None and screenshot_window.winfo_exists():
        screenshot_window.lift()
        screenshot_window.focus_force()
        return screenshot_window

    screenshot_window = ScreenshotOverlay(parent=parent)
    return screenshot_window


def force_close_screenshot_if_open() -> None:
    """Close YScreenshot without prompting (hub shutdown)."""
    global screenshot_window
    window = screenshot_window
    if window is None:
        return
    try:
        if not window.winfo_exists():
            screenshot_window = None
            return
        standalone = getattr(window, "_standalone_root", None)
        window.destroy()
        if standalone is not None:
            cleanup_hidden_root(standalone)
    except Exception:
        pass
    screenshot_window = None


if __name__ == "__main__":
    app = open_screenshot_studio()
    app.mainloop()
