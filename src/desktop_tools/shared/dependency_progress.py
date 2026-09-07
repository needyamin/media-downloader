"""Reusable download/update progress panel for desktop tools."""

from __future__ import annotations

import re
import threading
import tkinter as tk
from tkinter import ttk

PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def parse_progress_percent(message=None, percent=None):
    """Return a 0-100 value from an explicit percent or a message like '42%'."""
    if percent is not None:
        try:
            value = float(percent)
        except (TypeError, ValueError):
            value = None
        else:
            if 0 <= value <= 100:
                return value
    if message:
        match = PERCENT_RE.search(str(message))
        if match:
            return float(match.group(1))
    return None


def invoke_progress_callback(callback, message, percent=None):
    """Call a progress callback that may accept (message) or (message, percent)."""
    if callback is None:
        return
    try:
        callback(message, percent)
    except TypeError:
        callback(message)


class DependencyProgressPanel:
    """Title + percent + bar + status, shown only while a download/update is running."""

    def __init__(
        self,
        parent,
        *,
        background=None,
        foreground=None,
        muted=None,
        title_style=None,
        status_style=None,
        bar_style=None,
        wraplength=460,
        use_ttk=True,
        layout="pack",
        layout_kwargs=None,
        before=None,
        on_visibility_change=None,
    ):
        self.parent = parent
        self.layout = layout
        self.layout_kwargs = dict(layout_kwargs or {})
        self.before = before
        self.on_visibility_change = on_visibility_change
        self._visible = False
        self._indeterminate = False
        self._use_ttk = use_ttk

        if use_ttk:
            self.frame = ttk.Frame(parent)
            header = ttk.Frame(self.frame)
            header.pack(fill="x")
            title_kwargs = {"text": "Downloading or updating"}
            if title_style:
                title_kwargs["style"] = title_style
            self.title_label = ttk.Label(header, **title_kwargs)
            self.title_label.pack(side="left")
            percent_kwargs = {"text": ""}
            if title_style:
                percent_kwargs["style"] = title_style
            self.percent_label = ttk.Label(header, **percent_kwargs)
            self.percent_label.pack(side="right")
            bar_kwargs = {"orient": "horizontal", "mode": "determinate", "maximum": 100}
            if bar_style:
                bar_kwargs["style"] = bar_style
            self.bar = ttk.Progressbar(self.frame, **bar_kwargs)
            self.bar.pack(fill="x", pady=(6, 4))
            status_kwargs = {"text": "", "wraplength": wraplength, "justify": "left"}
            if status_style:
                status_kwargs["style"] = status_style
            self.status_label = ttk.Label(self.frame, **status_kwargs)
            self.status_label.pack(anchor="w")
        else:
            bg = background or "#0B1628"
            fg = foreground or "#F8FAFC"
            mute = muted or "#94A3B8"
            self.frame = tk.Frame(parent, bg=bg)
            header = tk.Frame(self.frame, bg=bg)
            header.pack(fill="x")
            self.title_label = tk.Label(header, text="Downloading or updating", bg=bg, fg=fg, font=("Segoe UI", 10, "bold"))
            self.title_label.pack(side="left")
            self.percent_label = tk.Label(header, text="", bg=bg, fg=fg, font=("Segoe UI", 10, "bold"))
            self.percent_label.pack(side="right")
            bar_kwargs = {"orient": "horizontal", "mode": "determinate", "maximum": 100}
            if bar_style:
                bar_kwargs["style"] = bar_style
            self.bar = ttk.Progressbar(self.frame, **bar_kwargs)
            self.bar.pack(fill="x", pady=(6, 4))
            self.status_label = tk.Label(
                self.frame,
                text="",
                bg=bg,
                fg=mute,
                font=("Segoe UI", 9),
                wraplength=wraplength,
                justify="left",
                anchor="w",
            )
            self.status_label.pack(anchor="w")

    @property
    def visible(self):
        return self._visible

    def _apply_layout(self, before=None):
        kwargs = dict(self.layout_kwargs)
        target_before = before if before is not None else self.before
        if self.layout == "grid":
            if self.frame.winfo_manager() != "grid":
                self.frame.grid(**kwargs)
            else:
                self.frame.grid_configure(**kwargs)
            return
        if target_before is not None and getattr(target_before, "winfo_manager", lambda: "")():
            kwargs.setdefault("before", target_before)
        if self.frame.winfo_manager() != "pack":
            self.frame.pack(**kwargs)

    def _set_indeterminate(self, enabled):
        enabled = bool(enabled)
        if enabled == self._indeterminate:
            if enabled:
                try:
                    self.bar.start(12)
                except tk.TclError:
                    pass
            return
        self._indeterminate = enabled
        try:
            if enabled:
                self.bar.configure(mode="indeterminate")
                self.bar.start(12)
                self.percent_label.configure(text="…")
            else:
                self.bar.stop()
                self.bar.configure(mode="determinate")
        except tk.TclError:
            pass

    def show(self, title="Downloading or updating", message="Starting…", percent=None, indeterminate=False, before=None):
        if title:
            self.title_label.configure(text=title)
        if message:
            self.status_label.configure(text=message)
        parsed = parse_progress_percent(message, percent)
        if indeterminate or parsed is None:
            self._set_indeterminate(True)
        else:
            self._set_indeterminate(False)
            self.bar["value"] = parsed
            self.percent_label.configure(text=f"{parsed:.0f}%")
        if not self._visible:
            self._apply_layout(before=before)
            self._visible = True
            if self.on_visibility_change:
                self.on_visibility_change(True)

    def update(self, message=None, percent=None, title=None, indeterminate=None):
        if not self._visible:
            self.show(
                title=title or "Downloading or updating",
                message=message or "Working…",
                percent=percent,
                indeterminate=bool(indeterminate),
            )
            return
        if title:
            self.title_label.configure(text=title)
        if message:
            self.status_label.configure(text=message)
        parsed = parse_progress_percent(message, percent)
        if indeterminate is True or (indeterminate is None and parsed is None):
            self._set_indeterminate(True)
            return
        self._set_indeterminate(False)
        if parsed is not None:
            self.bar["value"] = parsed
            self.percent_label.configure(text=f"{parsed:.0f}%")

    def hide(self):
        if not self._visible:
            return
        self._set_indeterminate(False)
        try:
            self.bar["value"] = 0
            self.percent_label.configure(text="")
            self.status_label.configure(text="")
        except tk.TclError:
            pass
        try:
            if self.frame.winfo_manager() == "grid":
                self.frame.grid_remove()
            elif self.frame.winfo_manager() == "pack":
                self.frame.pack_forget()
        except tk.TclError:
            pass
        self._visible = False
        if self.on_visibility_change:
            self.on_visibility_change(False)

    def threadsafe_callback(self, widget=None, title=None, extra=None):
        """Return a worker-thread callback(message, percent=None)."""
        host = widget or self.frame

        def callback(message, percent=None):
            parsed = parse_progress_percent(message, percent)
            indeterminate = parsed is None

            def apply():
                if title:
                    self.update(message=message, percent=parsed, title=title, indeterminate=indeterminate)
                else:
                    self.update(message=message, percent=parsed, indeterminate=indeterminate)
                if extra:
                    extra(message, parsed)

            if threading.current_thread() is threading.main_thread():
                apply()
                return
            try:
                host.after(0, apply)
            except tk.TclError:
                pass

        return callback
