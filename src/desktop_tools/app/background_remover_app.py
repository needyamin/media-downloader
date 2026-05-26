import os
import threading
import tkinter as tk
from tkinter import Tk, filedialog, ttk, StringVar, TclError, messagebox, Menu, Toplevel
from tkinter.messagebox import showinfo, showerror
from PIL import Image, ImageTk
import requests
import tempfile
import sys
import subprocess
from pathlib import Path
import time
import traceback

APP_DIR = Path(__file__).resolve().parent
SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from desktop_tools.shared.resources import apply_window_icon, center_window

MISSING_DEPENDENCIES = []
DEPENDENCY_ERRORS = {}
IS_WINDOWS = os.name == "nt"


def register_dependency_error(name, exc):
    """Track dependency import failures so packaged builds show the real cause."""
    if name not in MISSING_DEPENDENCIES:
        MISSING_DEPENDENCIES.append(name)
    if exc is not None:
        DEPENDENCY_ERRORS[name] = f"{type(exc).__name__}: {exc}"

try:
    from rembg import remove as remove_background
except BaseException as exc:
    remove_background = None
    register_dependency_error("rembg", exc)

try:
    import customtkinter as ctk
except BaseException as exc:
    ctk = None
    register_dependency_error("customtkinter", exc)

# Constants for version checking
CURRENT_VERSION = "1.0.0"  # Update this with your current version
GITHUB_API_URL = "https://api.github.com/repos/needyamin/img-background-remover/releases/latest"
REPO_OWNER = "needyamin"
REPO_NAME = "img-background-remover"
APP_ID = "mycompany.backgroundremover.1.0"
background_remover_window = None

PRIMARY_BG = "#07111F"
SURFACE_BG = "#0F1C2E"
CARD_BG = "#132238"
CARD_BORDER = "#243B5A"
CANVAS_BG = "#091423"
ACCENT = "#60A5FA"
ACCENT_HOVER = "#3B82F6"
SUCCESS = "#22C55E"
SUCCESS_HOVER = "#16A34A"
DANGER = "#EF4444"
DANGER_HOVER = "#DC2626"
SECONDARY_BUTTON = "#16263B"
SECONDARY_BUTTON_HOVER = "#213552"
SECONDARY_BUTTON_BORDER = "#345072"
HEADER_BADGE_BG = "#102742"
HEADER_BADGE_BORDER = "#2A4B73"
TEXT_MAIN = "#F8FAFC"
TEXT_MUTED = "#B6C2D5"
TEXT_SOFT = "#7F91AB"
DANGER_TEXT = "#FCA5A5"
CHECKER_DARK = "#0C1526"
CHECKER_LIGHT = "#172235"

def log(message):
    """Simple logging function"""
    print(f"[LOG] {message}")

def compare_versions(version1, version2):
    """Compare two version strings. Returns True if version1 > version2"""
    def normalize(v):
        return [int(x) for x in v.split(".")]
    try:
        return normalize(version1) > normalize(version2)
    except (AttributeError, TypeError, ValueError):
        return False

def get_base_path():
    """Return the app base path for source and PyInstaller builds."""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

def get_asset_path(*parts):
    return os.path.join(get_base_path(), "assets", *parts)

def show_startup_error(title, message):
    """Show a GUI error when possible and fall back to stderr-friendly output."""
    try:
        root = Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except TclError:
        print(f"{title}: {message}")

class BackgroundRemoverApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Background Remover Studio")
        self.master.geometry("1240x860")
        self.master.minsize(980, 720)
        self.master.configure(bg=PRIMARY_BG)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.style = ttk.Style(self.master)
        self._configure_style()

        # Create Menu Bar
        self.create_menu_bar()
        self._configure_window_icon()

        # Add keyboard shortcuts
        self.master.bind('<Control-o>', lambda e: self.upload_image())
        self.master.bind('<Control-s>', lambda e: self.save_processed_image())

        # Initialize variables
        self.current_image = None
        self.processed_image = None
        self.original_path = None
        self._redraw_job = None
        self.status_var = StringVar(value="Ready to process an image")
        self.original_details_var = StringVar(
            value="Upload a photo to preview the original composition."
        )
        self.processed_details_var = StringVar(
            value="The cutout result will appear here with a transparent preview."
        )

        self._build_ui()
        self._refresh_preview_panels()

        self.master.after_idle(lambda: center_window(self.master, self.master.master if isinstance(self.master, Toplevel) else None))

    def _configure_style(self):
        try:
            self.style.theme_use("clam")
        except TclError:
            pass

        self.style.configure(
            "Modern.Horizontal.TProgressbar",
            troughcolor=CANVAS_BG,
            background=ACCENT,
            bordercolor=CANVAS_BG,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
            thickness=8,
        )

    def _button_palette(self, variant):
        palettes = {
            "primary": {
                "fg_color": ACCENT,
                "hover_color": ACCENT_HOVER,
                "border_color": ACCENT_HOVER,
                "text_color": "#06111E",
                "text_color_disabled": TEXT_SOFT,
                "border_width": 0,
            },
            "success": {
                "fg_color": SUCCESS,
                "hover_color": SUCCESS_HOVER,
                "border_color": SUCCESS_HOVER,
                "text_color": "#F8FFF9",
                "text_color_disabled": TEXT_SOFT,
                "border_width": 0,
            },
            "secondary": {
                "fg_color": SECONDARY_BUTTON,
                "hover_color": SECONDARY_BUTTON_HOVER,
                "border_color": SECONDARY_BUTTON_BORDER,
                "text_color": TEXT_MAIN,
                "text_color_disabled": TEXT_SOFT,
                "border_width": 1,
            },
            "danger-soft": {
                "fg_color": SECONDARY_BUTTON,
                "hover_color": "#2B2130",
                "border_color": "#6B2F43",
                "text_color": DANGER_TEXT,
                "text_color_disabled": TEXT_SOFT,
                "border_width": 1,
            },
        }
        return palettes[variant]

    def _create_action_button(self, parent, text, command, variant, width):
        palette = self._button_palette(variant)
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=44,
            corner_radius=14,
            fg_color=palette["fg_color"],
            hover_color=palette["hover_color"],
            border_color=palette["border_color"],
            border_width=palette["border_width"],
            text_color=palette["text_color"],
            text_color_disabled=palette["text_color_disabled"],
            font=("Segoe UI", 13, "bold"),
        )

    def _create_toolbar_chip(self, parent, text):
        chip = ctk.CTkFrame(
            parent,
            fg_color=SECONDARY_BUTTON,
            corner_radius=999,
            border_width=1,
            border_color=SECONDARY_BUTTON_BORDER,
        )
        chip.pack(side='left', padx=(0, 8))
        ctk.CTkLabel(
            chip,
            text=text,
            text_color=TEXT_MUTED,
            font=("Segoe UI", 10, "bold"),
        ).pack(padx=12, pady=6)
        return chip

    def _set_save_button_enabled(self, enabled):
        variant = "success" if enabled else "secondary"
        palette = self._button_palette(variant)
        self.save_button.configure(
            state='normal' if enabled else 'disabled',
            fg_color=palette["fg_color"],
            hover_color=palette["hover_color"],
            border_color=palette["border_color"],
            border_width=palette["border_width"],
            text_color=palette["text_color"],
            text_color_disabled=palette["text_color_disabled"],
        )

    def _build_ui(self):
        self.main_frame = ctk.CTkFrame(self.master, fg_color=PRIMARY_BG, corner_radius=0)
        self.main_frame.pack(fill='both', expand=True, padx=24, pady=24)

        self.header_card = ctk.CTkFrame(
            self.main_frame,
            fg_color=SURFACE_BG,
            corner_radius=24,
            border_width=1,
            border_color=CARD_BORDER,
        )
        self.header_card.pack(fill='x')
        self.header_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.header_card,
            text="Background Remover Studio",
            text_color=TEXT_MAIN,
            font=("Segoe UI", 28, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(22, 4))

        ctk.CTkLabel(
            self.header_card,
            text="A cleaner, faster workspace for uploading, previewing, and exporting transparent cutouts.",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 13),
        ).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 22))

        self.badge_frame = ctk.CTkFrame(
            self.header_card,
            fg_color=HEADER_BADGE_BG,
            corner_radius=999,
            border_width=1,
            border_color=HEADER_BADGE_BORDER,
        )
        self.badge_frame.grid(row=0, column=1, rowspan=2, sticky="e", padx=24, pady=24)

        ctk.CTkLabel(
            self.badge_frame,
            text="AI Cutout Workspace",
            text_color=ACCENT,
            font=("Segoe UI", 11, "bold"),
        ).pack(padx=18, pady=(10, 2))
        ctk.CTkLabel(
            self.badge_frame,
            text="Cleaner buttons and preview flow",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 10),
        ).pack(padx=18, pady=(0, 10))

        self.toolbar_card = ctk.CTkFrame(
            self.main_frame,
            fg_color=SURFACE_BG,
            corner_radius=22,
            border_width=1,
            border_color=CARD_BORDER,
        )
        self.toolbar_card.pack(fill='x', pady=(18, 18))

        self.toolbar_row = ctk.CTkFrame(self.toolbar_card, fg_color="transparent")
        self.toolbar_row.pack(fill='x', padx=20, pady=(20, 10))

        self.action_buttons = ctk.CTkFrame(self.toolbar_row, fg_color="transparent")
        self.action_buttons.pack(side='left')

        self.upload_button = self._create_action_button(
            self.action_buttons,
            text="Choose Image",
            command=self.upload_image,
            variant="primary",
            width=160,
        )
        self.upload_button.pack(side='left', padx=(0, 12))

        self.save_button = self._create_action_button(
            self.action_buttons,
            text="Save PNG",
            command=self.save_processed_image,
            variant="success",
            width=140,
        )
        self.save_button.pack(side='left', padx=(0, 12))

        self.clear_button = self._create_action_button(
            self.action_buttons,
            text="Reset Workspace",
            command=self.clear_images,
            variant="danger-soft",
            width=156,
        )
        self.clear_button.pack(side='left')

        self.progress_bar = ttk.Progressbar(
            self.toolbar_row,
            mode='indeterminate',
            length=220,
            style="Modern.Horizontal.TProgressbar",
        )
        self.progress_bar.pack(side='right', padx=(16, 0), pady=8)

        self.toolbar_chips = ctk.CTkFrame(self.toolbar_card, fg_color="transparent")
        self.toolbar_chips.pack(fill='x', padx=22, pady=(0, 12))
        self._create_toolbar_chip(self.toolbar_chips, "Smart preview fit")
        self._create_toolbar_chip(self.toolbar_chips, "Transparent PNG export")
        self._create_toolbar_chip(self.toolbar_chips, "Fast local workflow")

        ctk.CTkLabel(
            self.toolbar_card,
            textvariable=self.status_var,
            text_color=TEXT_MAIN,
            anchor="w",
            justify="left",
            font=("Segoe UI", 13, "bold"),
        ).pack(fill='x', padx=22, pady=(0, 4))

        ctk.CTkLabel(
            self.toolbar_card,
            text="Supports PNG, JPG, JPEG, BMP, and WEBP files. Export stays in transparent PNG format.",
            text_color=TEXT_SOFT,
            anchor="w",
            justify="left",
            font=("Segoe UI", 11),
        ).pack(fill='x', padx=22, pady=(0, 18))
        self._set_save_button_enabled(False)

        self.image_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.image_frame.pack(fill='both', expand=True)
        self.image_frame.grid_columnconfigure(0, weight=1)
        self.image_frame.grid_columnconfigure(1, weight=1)
        self.image_frame.grid_rowconfigure(0, weight=1)

        self.original_card = self._create_preview_card(
            self.image_frame,
            title="Original Image",
            details_var=self.original_details_var,
            column=0,
        )
        self.original_canvas = self.original_card["canvas"]

        self.processed_card = self._create_preview_card(
            self.image_frame,
            title="Background Removed",
            details_var=self.processed_details_var,
            column=1,
        )
        self.removed_canvas = self.processed_card["canvas"]

        self.footer_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.footer_frame.pack(fill='x', pady=(16, 0))

        self.center_frame = tk.Frame(self.footer_frame, bg=PRIMARY_BG)
        self.center_frame.pack(expand=True)

        self.credit_prefix = tk.Label(
            self.center_frame,
            text="Created by ",
            bg=PRIMARY_BG,
            fg=TEXT_SOFT,
            font=("Segoe UI", 10),
        )
        self.credit_prefix.pack(side='left', pady=2)

        self.name_link = tk.Label(
            self.center_frame,
            text="Md. Yamin Hossain",
            bg=PRIMARY_BG,
            fg=ACCENT,
            font=("Segoe UI", 10, "underline"),
            cursor="hand2",
        )
        self.name_link.pack(side='left', pady=2)
        self.name_link.bind("<Button-1>", lambda e: self.open_link("https://needyamin.github.io"))

        self.separator = tk.Label(
            self.center_frame,
            text="  |  ",
            bg=PRIMARY_BG,
            fg=TEXT_SOFT,
            font=("Segoe UI", 10),
        )
        self.separator.pack(side='left', pady=2)

        self.github_link = tk.Label(
            self.center_frame,
            text="GitHub",
            bg=PRIMARY_BG,
            fg=ACCENT,
            font=("Segoe UI", 10, "underline"),
            cursor="hand2",
        )
        self.github_link.pack(side='left', pady=2)
        self.github_link.bind("<Button-1>", lambda e: self.open_link("https://github.com/needyamin/img-background-remover"))

    def _create_preview_card(self, parent, title, details_var, column):
        card = ctk.CTkFrame(
            parent,
            fg_color=CARD_BG,
            corner_radius=22,
            border_width=1,
            border_color=CARD_BORDER,
        )

        horizontal_pad = (0, 10) if column == 0 else (10, 0)
        card.grid(row=0, column=column, sticky="nsew", padx=horizontal_pad)

        ctk.CTkLabel(
            card,
            text=title,
            text_color=TEXT_MAIN,
            font=("Segoe UI", 18, "bold"),
            anchor="w",
        ).pack(fill='x', padx=20, pady=(18, 4))

        ctk.CTkLabel(
            card,
            textvariable=details_var,
            text_color=TEXT_MUTED,
            font=("Segoe UI", 11),
            justify="left",
            anchor="w",
        ).pack(fill='x', padx=20, pady=(0, 14))

        canvas_shell = ctk.CTkFrame(
            card,
            fg_color=CANVAS_BG,
            corner_radius=18,
            border_width=1,
            border_color=CARD_BORDER,
        )
        canvas_shell.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        canvas = tk.Canvas(
            canvas_shell,
            bg=CANVAS_BG,
            highlightthickness=0,
            bd=0,
            relief='flat',
        )
        canvas.pack(fill='both', expand=True, padx=1, pady=1)
        canvas.bind("<Configure>", self._schedule_preview_refresh)

        return {"card": card, "canvas": canvas}

    def _schedule_preview_refresh(self, _event=None):
        if self._redraw_job is not None:
            self.master.after_cancel(self._redraw_job)
        self._redraw_job = self.master.after(120, self._refresh_preview_panels)

    def _refresh_preview_panels(self):
        self._redraw_job = None

        if self.current_image is None:
            self._show_canvas_placeholder(
                self.original_canvas,
                title="Drop in a photo",
                subtitle="Your original image will appear here with a large fit-to-view preview.",
                transparent=False,
            )
        else:
            self.display_image(self.current_image, self.original_canvas, maintain_aspect=True, transparent=False)

        if self.processed_image is None:
            self._show_canvas_placeholder(
                self.removed_canvas,
                title="Transparent result",
                subtitle="Once processed, the cutout preview will be shown on a checkerboard background.",
                transparent=True,
            )
        else:
            self.display_image(self.processed_image, self.removed_canvas, maintain_aspect=True, transparent=True)

    def _paint_canvas_background(self, canvas, transparent=False):
        width = max(canvas.winfo_width(), int(canvas.cget("width")) or 1)
        height = max(canvas.winfo_height(), int(canvas.cget("height")) or 1)

        if transparent:
            tile = 18
            for x in range(0, width, tile):
                for y in range(0, height, tile):
                    color = CHECKER_LIGHT if ((x // tile) + (y // tile)) % 2 else CHECKER_DARK
                    canvas.create_rectangle(
                        x,
                        y,
                        x + tile,
                        y + tile,
                        fill=color,
                        outline=color,
                        tags="background",
                    )
        else:
            canvas.create_rectangle(
                0,
                0,
                width,
                height,
                fill=CANVAS_BG,
                outline=CANVAS_BG,
                tags="background",
            )

    def _show_canvas_placeholder(self, canvas, title, subtitle, transparent=False):
        canvas.delete("all")
        self._paint_canvas_background(canvas, transparent=transparent)

        width = max(canvas.winfo_width(), 320)
        height = max(canvas.winfo_height(), 320)
        inset = max(min(width, height) * 0.08, 24)

        canvas.create_rectangle(
            inset,
            inset,
            width - inset,
            height - inset,
            outline=CARD_BORDER,
            width=1,
            dash=(7, 8),
            tags="foreground",
        )
        canvas.create_text(
            width / 2,
            height / 2 - 16,
            text=title,
            fill=TEXT_MAIN,
            font=("Segoe UI", 18, "bold"),
            tags="foreground",
        )
        canvas.create_text(
            width / 2,
            height / 2 + 22,
            text=subtitle,
            fill=TEXT_SOFT,
            width=max(width - 140, 180),
            justify="center",
            font=("Segoe UI", 10),
            tags="foreground",
        )

    def _update_preview_details(self):
        if self.current_image is not None and self.original_path:
            self.original_details_var.set(
                f"{Path(self.original_path).name}  •  {self.current_image.width} x {self.current_image.height}"
            )
        else:
            self.original_details_var.set(
                "Upload a photo to preview the original composition."
            )

        if self.processed_image is not None:
            self.processed_details_var.set(
                f"Transparent PNG preview  •  {self.processed_image.width} x {self.processed_image.height}"
            )
        else:
            self.processed_details_var.set(
                "The cutout result will appear here with a transparent preview."
            )

    def _configure_window_icon(self):
        """Apply the shared Media Downloader icon."""
        try:
            apply_window_icon(self.master, app_id="needyamin.media_downloader")
        except Exception as e:
            log(f"Could not load application icon: {e}")

    # Add method to open URLs
    def open_url(self, url):
        import webbrowser
        webbrowser.open(url)

    def open_link(self, url):
        """Open the given URL in the default web browser"""
        import webbrowser
        webbrowser.open(url)

    def create_menu_bar(self):
        """Create the main menu bar"""
        menubar = Menu(self.master)
        self.master.config(menu=menubar)

        # File Menu
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Image", command=self.upload_image, accelerator="Ctrl+O")
        file_menu.add_command(label="Save Image", command=self.save_processed_image, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close_window)

        # Edit Menu
        edit_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Clear Images", command=self.clear_images)

        # Help Menu
        help_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Check for Updates", command=self.check_for_updates)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.show_about)

    def close_window(self):
        """Close only this tool window."""
        global background_remover_window

        if background_remover_window is not None and self.master == background_remover_window:
            background_remover_window.destroy()
            background_remover_window = None
            return

        self.master.destroy()

    def clear_images(self):
        """Clear both canvases"""
        self.current_image = None
        self.processed_image = None
        self.original_path = None
        self.original_canvas.image = None
        self.removed_canvas.image = None
        self._set_save_button_enabled(False)
        self.status_var.set("Ready to process an image")
        self._update_preview_details()
        self._refresh_preview_panels()

    def show_about(self):
        """Show about dialog"""
        about_text = f"""Background Remover Studio v{CURRENT_VERSION}

Created by Md. Yamin Hossain

This application helps you remove backgrounds from images 
using advanced AI technology.

© 2025 All rights reserved."""
        messagebox.showinfo("About", about_text)

    def upload_image(self, event=None):
        file_path = filedialog.askopenfilename(
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.webp")]
        )
        if file_path:
            self.process_image(file_path)

    def process_image(self, file_path):
        self.original_path = file_path
        self.status_var.set("Removing the background... Please wait")
        self.progress_bar.start()
        
        def process():
            try:
                # Load image data off the UI thread, then marshal UI work back to Tk.
                original = Image.open(file_path)
                original.load()

                # Remove background while preserving quality
                output = remove_background(original)
                self.master.after(0, lambda: self._finish_processing(original, output))
                
            except Exception as e:
                self.master.after(0, lambda: self._handle_processing_error(str(e)))
            finally:
                self.master.after(0, self.progress_bar.stop)

        threading.Thread(target=process, daemon=True).start()

    def _finish_processing(self, original, output):
        self.current_image = original
        self.processed_image = output
        self._update_preview_details()
        self._refresh_preview_panels()
        self.status_var.set("Background removed successfully. Your PNG is ready to save.")
        self._set_save_button_enabled(True)

    def _handle_processing_error(self, error_message):
        self.status_var.set(f"Error: {error_message}")
        showerror("Error", f"Failed to process image: {error_message}")

    def save_processed_image(self, event=None):
        if self.processed_image is None:
            showerror("Error", "No processed image to save!")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")],
            initialfile="background_removed.png"
        )
        
        if save_path:
            try:
                # Save with original quality
                self.processed_image.save(save_path, "PNG", quality=100)
                showinfo("Success", "Image saved successfully!")
                self.status_var.set(f"Saved PNG to {Path(save_path).name}")
            except Exception as e:
                showerror("Error", f"Failed to save image: {str(e)}")

    def display_image(self, image, canvas, maintain_aspect=True, transparent=False):
        canvas.update_idletasks()

        # Get canvas dimensions
        canvas_width = max(canvas.winfo_width(), 320)
        canvas_height = max(canvas.winfo_height(), 320)
        preview_padding = 28
        available_width = max(canvas_width - (preview_padding * 2), 1)
        available_height = max(canvas_height - (preview_padding * 2), 1)

        # Calculate scaling factor while maintaining aspect ratio
        if maintain_aspect:
            # Calculate scaling factors for both dimensions
            width_ratio = available_width / image.width
            height_ratio = available_height / image.height
            
            # Use the smaller ratio to ensure image fits in canvas
            scale_factor = min(width_ratio, height_ratio)
            
            new_width = max(1, int(image.width * scale_factor))
            new_height = max(1, int(image.height * scale_factor))
        else:
            new_width = available_width
            new_height = available_height

        # Resize image while maintaining quality
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Convert to PhotoImage and display
        tk_image = ImageTk.PhotoImage(resized_image)
        canvas.delete("all")  # Clear previous image
        self._paint_canvas_background(canvas, transparent=transparent)
        
        canvas.image = tk_image  # Keep a reference
        canvas.create_image(canvas_width / 2, canvas_height / 2, image=tk_image)

    def create_ico_from_png(self, png_path):
        """Create an ICO file from a PNG file if it doesn't exist"""
        ico_path = png_path.replace('.png', '.ico')
        if not os.path.exists(ico_path):
            try:
                # Open PNG and convert to RGBA if necessary
                img = Image.open(png_path)
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # Create ICO file with multiple sizes
                icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
                img.save(ico_path, format='ICO', sizes=icon_sizes)
            except Exception as e:
                print(f"Could not create ICO file: {e}")
        return ico_path

    def check_for_updates(self):
        """Check for updates on GitHub and return the latest version if available."""
        try:
            log("=== Starting Update Check ===")
            self.status_var.set("Checking for updates...")
            
            # Make the request with headers to avoid rate limiting
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': f'background-remover/{CURRENT_VERSION}'
            }
            
            response = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
            log(f"GitHub API Response Status: {response.status_code}")
            
            if response.status_code != 200:
                log(f"GitHub API Error: {response.text}")
                self.status_var.set("Failed to check for updates")
                return None
                
            latest_release = response.json()
            
            # Check if there's a valid release
            if 'tag_name' not in latest_release:
                log("No tag_name found in release")
                self.status_var.set("No updates found")
                return None
                
            # Get the latest version number (strip v prefix if present)
            latest_version = latest_release.get('tag_name', '').lstrip('v')
            log(f"Latest version on GitHub: {latest_version}")
            
            if not latest_version:
                log("Empty version tag found in release")
                self.status_var.set("No valid update found")
                return None
            
            if compare_versions(latest_version, CURRENT_VERSION):
                log(f"New version {latest_version} is available!")
                self.status_var.set(f"New version {latest_version} available!")
                if messagebox.askyesno("Update Available", 
                                     f"Version {latest_version} is available. Would you like to update now?"):
                    self.download_and_install_update(latest_release)
            else:
                log("You have the latest version")
                self.status_var.set("You have the latest version")
                messagebox.showinfo("No Updates", "You have the latest version installed!")
                return None
                
        except requests.exceptions.RequestException as e:
            log(f"Network error checking for updates: {e}")
            self.status_var.set("Network error checking for updates")
            messagebox.showerror("Update Error", f"Network error checking for updates: {e}")
            return None
        except Exception as e:
            log(f"Unexpected error checking for updates: {e}")
            self.status_var.set("Error checking for updates")
            messagebox.showerror("Update Error", f"Error checking for updates: {e}")
            return None

    def download_and_install_update(self, release):
        """Download and install the latest release."""
        try:
            self.status_var.set("Downloading update...")
            latest_version = release.get('tag_name', '').lstrip('v')

            if not IS_WINDOWS or not getattr(sys, "frozen", False):
                release_url = release.get('html_url') or "https://github.com/needyamin/img-background-remover/releases/latest"
                self.status_var.set("Open release page for update")
                messagebox.showinfo(
                    "Manual Update",
                    "Automatic self-install is currently only supported for the packaged Windows build.\n\n"
                    "The latest release page will open in your browser instead.",
                )
                self.open_link(release_url)
                return False
            
            # Find the asset with .exe extension
            assets = release.get('assets', [])
            exe_asset = None
            for asset in assets:
                if asset.get('name', '').lower().endswith('.exe'):
                    exe_asset = asset
                    break
                    
            if not exe_asset:
                raise Exception("No executable found in release assets")
            
            # Create temporary directory for download
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                exe_path = temp_path / exe_asset['name']
                
                # Download the new version
                download_url = exe_asset['browser_download_url']
                log(f"Downloading from: {download_url}")
                
                # Show a message to inform the user that download is in progress
                self.status_var.set(f"Downloading version {latest_version}...")
                
                # Download with progress tracking
                response = requests.get(download_url, stream=True)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(exe_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        downloaded += len(chunk)
                        f.write(chunk)
                
                self.status_var.set("Installing update...")
                
                # Create update script
                update_script = temp_path / "update.bat"
                current_exe = sys.executable
                
                with open(update_script, 'w') as f:
                    f.write(f"""@echo off
echo Waiting for application to close...
timeout /t 2 /nobreak
echo Updating Background Remover...
del "{current_exe}"
if exist "{current_exe}" (
    echo Retrying with force delete...
    taskkill /f /im "{os.path.basename(current_exe)}" 2>nul
    timeout /t 1 /nobreak
    del /f "{current_exe}"
)
echo Copying new version...
copy "{exe_path}" "{current_exe}"
if exist "{current_exe}" (
    echo Starting new version...
    start "" "{current_exe}"
) else (
    echo ERROR: Failed to copy new version.
    pause
)
""")
                
                # Run update script and exit
                subprocess.Popen([str(update_script)], shell=True)
                time.sleep(1)
                sys.exit(0)
                
        except Exception as e:
            error_msg = str(e)
            log(f"Error installing update: {error_msg}")
            self.status_var.set("Update failed")
            messagebox.showerror("Update Error", f"Failed to install update: {error_msg}")
            return False

def ensure_background_remover_dependencies(parent=None):
    """Check required packages before opening the remover UI."""
    if not MISSING_DEPENDENCIES:
        return True

    missing_list = ", ".join(MISSING_DEPENDENCIES)
    details = "\n".join(
        f"- {name}: {error}"
        for name, error in DEPENDENCY_ERRORS.items()
    )
    install_hint = (
        "Required packages are missing: "
        f"{missing_list}\n\n"
        "Install them with:\n"
        "python -m pip install -r src\\desktop_tools\\app\\requirements.txt"
    )
    if details:
        install_hint += f"\n\nDependency load details:\n{details}"

    if parent is None:
        show_startup_error("Missing Dependencies", install_hint)
    else:
        messagebox.showerror("Missing Dependencies", install_hint, parent=parent)
    return False

def open_background_remover(parent=None):
    """Open the background remover in its own window."""
    global background_remover_window

    if not ensure_background_remover_dependencies(parent):
        return None

    if parent is None:
        root = Tk()
        BackgroundRemoverApp(root)
        root.mainloop()
        return root

    if background_remover_window is not None and background_remover_window.winfo_exists():
        background_remover_window.deiconify()
        center_window(background_remover_window, parent)
        background_remover_window.lift()
        background_remover_window.focus_force()
        return background_remover_window

    background_remover_window = Toplevel(parent)
    BackgroundRemoverApp(background_remover_window)

    def _close_window():
        global background_remover_window
        if background_remover_window is not None and background_remover_window.winfo_exists():
            background_remover_window.destroy()
        background_remover_window = None

    background_remover_window.protocol("WM_DELETE_WINDOW", _close_window)
    background_remover_window.transient(parent)
    background_remover_window.after_idle(lambda: center_window(background_remover_window, parent))
    background_remover_window.lift()
    background_remover_window.focus_force()
    return background_remover_window

if __name__ == "__main__":
    open_background_remover()
