import tkinter as tk
import customtkinter as ctk
import datetime
from app.config import (
    DUE_PRESETS,
    MAX_BREAK_INTERVAL_MINS,
    MAX_BREAK_STAY_SECS,
    MIN_BREAK_INTERVAL_MINS,
    MIN_BREAK_STAY_SECS,
    PERSONALITY_PRESETS,
    WORKDAY_BUCKETS,
    WORKDAY_TIMER_PRESETS,
    clamp_break_interval_mins,
    clamp_break_stay_secs,
    config_db,
    clamp_custom_timer_mins,
    default_meridian,
    default_task_slot,
    due_from_slot_and_clock,
    due_preview_label,
    ends_at_label,
    format_clock_label,
    format_task_when,
    get_gui_theme,
    load_tasks,
    next_half_hour_parts,
    parse_clock_text,
    save_tasks,
    slot_key_from_label,
    suggested_workday_block,
    task_sort_key,
    task_workday_bucket,
    workday_headline,
    workday_period,
    workday_subline,
    clock_display_parts,
)
from app.ui_theme import apply_ctk_appearance, enrich_theme
from app.window_icon import apply_app_icon, install_app_icon_hook

apply_ctk_appearance()
install_app_icon_hook()

_active_windows = {}

_LANG_LABELS = {"mix": "Mixed", "bn": "Bengali", "en": "English"}
_LANG_VALUES = {label: key for key, label in _LANG_LABELS.items()}
_WEATHER_LABELS = {"none": "Off", "rain": "Rain", "snow": "Snow", "sunny": "Sunny"}
_WEATHER_VALUES = {label: key for key, label in _WEATHER_LABELS.items()}


def _theme():
    return enrich_theme(get_gui_theme())


def _primary_btn(theme, accent, accent_hover):
    return {
        "fg_color": accent,
        "hover_color": accent_hover,
        "text_color": theme["text_on_accent"],
    }


def _secondary_btn(theme, accent, accent_hover):
    return {
        "fg_color": theme["btn_secondary_bg"],
        "hover_color": theme["btn_secondary_hover"],
        "text_color": theme["btn_secondary_text"],
        "border_width": 1,
        "border_color": accent,
    }


def _bring_to_front(win_key):
    win = _active_windows.get(win_key)
    if win is not None:
        try:
            if win.winfo_exists():
                win.lift()
                win.focus()
                return True
        except Exception:
            pass
        _active_windows.pop(win_key, None)
    return False


def _track_window(win_key, win, on_close=None):
    apply_app_icon(win)
    _active_windows[win_key] = win

    def _close():
        if on_close is not None:
            try:
                on_close()
            except Exception:
                pass
        if _active_windows.get(win_key) is win:
            _active_windows.pop(win_key, None)
        try:
            win.destroy()
        except Exception:
            pass

    win.protocol("WM_DELETE_WINDOW", _close)
    return _close


def _card(parent, theme):
    frame = ctk.CTkFrame(parent, fg_color=theme["frame"], corner_radius=8, border_width=1, border_color=theme["border"])
    frame.pack(fill="x", padx=12, pady=6)
    return frame


def _label(parent, text, theme, *, size=12, bold=False, dim=False, **pack):
    font = ("Segoe UI", size, "bold") if bold else ("Segoe UI", size)
    color = theme["text_dim"] if dim else theme["text"]
    widget = ctk.CTkLabel(parent, text=text, font=font, text_color=color)
    widget.pack(**({"anchor": "w", "padx": 14, "pady": (10, 0)} | pack))
    return widget


def _slider(parent, theme, accent, accent_hover, *, from_, to, steps, value, on_change):
    slider = ctk.CTkSlider(
        parent,
        from_=from_,
        to=to,
        number_of_steps=steps,
        button_color=accent,
        button_hover_color=accent_hover,
        progress_color=accent,
    )
    slider.set(value)
    slider.configure(command=on_change)
    slider.pack(fill="x", padx=14, pady=(6, 12))
    return slider


def _switch(parent, theme, accent, text, enabled, on_toggle, **pack):
    switch = ctk.CTkSwitch(
        parent,
        text=text,
        font=("Segoe UI", 11),
        text_color=theme["text"],
        progress_color=accent,
        button_color=accent,
        button_hover_color=theme["accent_hover"],
    )
    switch.select() if enabled else switch.deselect()
    switch.configure(command=on_toggle)
    switch.pack(anchor="w", padx=14, pady=6, **pack)
    return switch


# ── Settings ──────────────────────────────────────────────
def open_settings_window(pet):
    if _bring_to_front("settings"):
        return

    win = ctk.CTkToplevel(pet)
    _track_window("settings", win)
    win.title("Anika Settings")
    win.geometry("420x560")
    win.resizable(True, True)
    win.minsize(400, 480)
    win.attributes("-topmost", True)

    theme = _theme()
    accent = theme["accent"]
    accent_hover = theme["accent_hover"]
    win.configure(fg_color=theme["bg"])

    header = ctk.CTkFrame(win, fg_color=theme["bg"])
    header.pack(fill="x", padx=16, pady=(14, 4))
    ctk.CTkLabel(header, text="Anika", font=("Segoe UI", 16, "bold"), text_color=theme["text"]).pack(anchor="w")
    ctk.CTkLabel(
        header,
        text="Desktop assistant settings",
        font=("Segoe UI", 11),
        text_color=theme["text_dim"],
    ).pack(anchor="w", pady=(0, 4))

    tabs = ctk.CTkTabview(
        win,
        fg_color=theme["bg"],
        text_color=theme["text"],
        segmented_button_fg_color=theme["tab_inactive_bg"],
        segmented_button_selected_color=accent,
        segmented_button_selected_hover_color=accent_hover,
        segmented_button_unselected_color=theme["tab_inactive_bg"],
        segmented_button_unselected_hover_color=theme["btn_secondary_hover"],
    )
    tabs.pack(fill="both", expand=True, padx=12, pady=4)

    _build_look_tab(tabs.add("Look"), pet, theme, accent, accent_hover)
    _build_behavior_tab(tabs.add("Behavior"), pet, theme, accent, accent_hover)
    _build_break_tab(tabs.add("Break"), pet, theme, accent, accent_hover)

    ctk.CTkButton(
        win,
        text="Done",
        font=("Segoe UI", 12, "bold"),
        command=win.destroy,
        **_primary_btn(theme, accent, accent_hover),
    ).pack(fill="x", padx=16, pady=(8, 16))


def _build_look_tab(parent, pet, theme, accent, accent_hover):
    parent = ctk.CTkScrollableFrame(parent, fg_color=theme["bg"])
    parent.pack(fill="both", expand=True)
    size_card = _card(parent, theme)
    size_lbl = _label(size_card, f"Size  {pet.pet_config.get('scale'):.1f}x", theme, bold=True)

    def on_size(val):
        val = round(float(val), 1)
        size_lbl.configure(text=f"Size  {val}x")
        pet.pet_config.set("scale", val)
        pet.update_dimensions()
        pet.assets.clear_cache()
        pet.render_pet()

    _slider(
        size_card, theme, accent, accent_hover,
        from_=0.5, to=2.5, steps=20, value=pet.pet_config.get("scale"), on_change=on_size,
    )

    opacity_card = _card(parent, theme)
    opacity_lbl = _label(opacity_card, f"Opacity  {int(pet.pet_config.get('opacity') * 100)}%", theme, bold=True)

    def on_opacity(val):
        opacity_lbl.configure(text=f"Opacity  {int(float(val) * 100)}%")
        pet.pet_config.set("opacity", float(val))
        pet.config_window_transparency()

    _slider(
        opacity_card, theme, accent, accent_hover,
        from_=0.2, to=1.0, steps=16, value=pet.pet_config.get("opacity"), on_change=on_opacity,
    )

    lang_card = _card(parent, theme)
    row = ctk.CTkFrame(lang_card, fg_color="transparent")
    row.pack(fill="x", padx=14, pady=12)
    ctk.CTkLabel(row, text="Language", font=("Segoe UI", 12, "bold"), text_color=theme["text"]).pack(side="left")
    lang_menu = ctk.CTkOptionMenu(
        row,
        values=list(_LANG_LABELS.values()),
        width=140,
        button_color=accent,
        button_hover_color=accent_hover,
        fg_color=theme["btn_secondary_bg"],
        text_color=theme["btn_secondary_text"],
        dropdown_fg_color=theme["bg"],
        dropdown_text_color=theme["text"],
        dropdown_hover_color=theme["btn_secondary_hover"],
        command=lambda label: pet.pet_config.set("language", _LANG_VALUES[label]),
    )
    lang_menu.set(_LANG_LABELS.get(pet.pet_config.get("language"), "Mixed"))
    lang_menu.pack(side="right")

    person_card = _card(parent, theme)
    _label(person_card, "Personality", theme, bold=True)
    person_menu = ctk.CTkOptionMenu(
        person_card,
        values=[key.capitalize() for key in PERSONALITY_PRESETS],
        button_color=accent,
        button_hover_color=accent_hover,
        fg_color=theme["btn_secondary_bg"],
        text_color=theme["btn_secondary_text"],
        dropdown_fg_color=theme["bg"],
        dropdown_text_color=theme["text"],
        dropdown_hover_color=theme["btn_secondary_hover"],
    )
    person_menu.set(str(config_db.get("personality") or "playful").capitalize())
    person_menu.pack(fill="x", padx=14, pady=(6, 4))
    desc_lbl = _label(
        person_card,
        PERSONALITY_PRESETS.get(config_db.get("personality"), PERSONALITY_PRESETS["playful"])["description"],
        theme,
        size=11,
        dim=True,
        pady=(0, 12),
    )

    def on_personality(label):
        key = label.lower()
        _set_personality(pet, key)
        desc_lbl.configure(text=PERSONALITY_PRESETS.get(key, PERSONALITY_PRESETS["playful"])["description"])

    person_menu.configure(command=on_personality)

    fx_card = _card(parent, theme)
    _label(fx_card, "Effects", theme, bold=True, pady=(10, 4))
    sparkle = _switch(fx_card, theme, accent, "Idle sparkles", bool(config_db.get("fairy_dust_enabled")), lambda: None)
    sparkle.configure(command=lambda: config_db.set("fairy_dust_enabled", sparkle.get() == 1))
    trail = _switch(fx_card, theme, accent, "Movement trail", bool(config_db.get("magic_trail_enabled")), lambda: None)
    trail.configure(command=lambda: config_db.set("magic_trail_enabled", trail.get() == 1))

    weather_row = ctk.CTkFrame(fx_card, fg_color="transparent")
    weather_row.pack(fill="x", padx=14, pady=(4, 12))
    ctk.CTkLabel(weather_row, text="Weather", font=("Segoe UI", 11), text_color=theme["text"]).pack(side="left")
    weather_menu = ctk.CTkOptionMenu(
        weather_row,
        values=list(_WEATHER_LABELS.values()),
        width=120,
        button_color=accent,
        button_hover_color=accent_hover,
        fg_color=theme["btn_secondary_bg"],
        text_color=theme["btn_secondary_text"],
        dropdown_fg_color=theme["bg"],
        dropdown_text_color=theme["text"],
        dropdown_hover_color=theme["btn_secondary_hover"],
        command=lambda label: config_db.set("weather_mode", _WEATHER_VALUES[label]),
    )
    weather_menu.set(_WEATHER_LABELS.get(config_db.get("weather_mode"), "Off"))
    weather_menu.pack(side="right")


def _set_personality(pet, key):
    config_db.set("personality", key)
    from app.config import get_personality

    pet.personality = get_personality()


def _build_behavior_tab(parent, pet, theme, accent, accent_hover):
    parent = ctk.CTkScrollableFrame(parent, fg_color=theme["bg"])
    parent.pack(fill="both", expand=True)
    card = _card(parent, theme)
    _label(card, "Movement", theme, bold=True, pady=(10, 4))

    gravity = _switch(card, theme, accent, "Gravity", bool(pet.pet_config.get("gravity_enabled")), lambda: None)

    def on_gravity():
        pet.pet_config.set("gravity_enabled", gravity.get() == 1)
        if not pet.pet_config.get("gravity_enabled"):
            pet.vy = 0

    gravity.configure(command=on_gravity)

    bound = _switch(card, theme, accent, "Keep on screen", bool(pet.pet_config.get("boundary_keep")), lambda: None)
    bound.configure(command=lambda: pet.pet_config.set("boundary_keep", bound.get() == 1))

    clock = _switch(
        card, theme, accent, "Announce the hour",
        bool(pet.pet_config.get("clock_announce") if pet.pet_config.get("clock_announce") is not None else True),
        lambda: None,
    )
    clock.configure(command=lambda: pet.pet_config.set("clock_announce", clock.get() == 1))

    edge_card = _card(parent, theme)
    _label(edge_card, "Hide at screen edge", theme, bold=True, pady=(10, 4))
    _label(
        edge_card,
        "Drag Anika to an edge to hide her for a while.",
        theme,
        size=11,
        dim=True,
        pady=(0, 4),
    )

    edge = _switch(
        edge_card, theme, accent, "Enable edge hide",
        bool(pet.pet_config.get("edge_hide_enabled")),
        lambda: None,
    )
    cur_mins = int(float(pet.pet_config.get("edge_hide_mins") or 5))
    mins_lbl = _label(edge_card, f"Stay hidden  {cur_mins} min", theme, bold=True, pady=(4, 0))

    def on_mins(val):
        value = max(1, min(60, int(float(val))))
        mins_lbl.configure(text=f"Stay hidden  {value} min")
        pet.pet_config.set("edge_hide_mins", value)

    mins_sl = _slider(
        edge_card, theme, accent, accent_hover,
        from_=1, to=60, steps=59, value=cur_mins, on_change=on_mins,
    )

    def sync_edge():
        enabled = edge.get() == 1
        pet.pet_config.set("edge_hide_enabled", enabled)
        mins_sl.configure(state="normal" if enabled else "disabled")
        mins_lbl.configure(text_color=theme["text"] if enabled else theme["text_dim"])

    edge.configure(command=sync_edge)
    sync_edge()


def _build_break_tab(parent, pet, theme, accent, accent_hover):
    card = _card(parent, theme)
    _label(card, "Break reminder", theme, bold=True)
    _label(
        card,
        "Anika appears in the center of the screen to remind you to rest.",
        theme,
        size=11,
        dim=True,
        pady=(0, 4),
    )

    is_enabled = clamp_break_interval_mins(pet.pet_config.get("break_interval_mins")) > 0
    enable = _switch(card, theme, accent, "Enable reminders", is_enabled, lambda: None)

    cur_interval = clamp_break_interval_mins(pet.pet_config.get("break_interval_mins")) or 30
    interval_lbl = _label(card, f"Every  {int(cur_interval)} min", theme, bold=True)

    def on_interval(val):
        value = int(float(val))
        interval_lbl.configure(text=f"Every  {value} min")
        if enable.get() == 1:
            pet.pet_config.set("break_interval_mins", value)
            pet._start_break_timer()

    interval_sl = _slider(
        card, theme, accent, accent_hover,
        from_=MIN_BREAK_INTERVAL_MINS,
        to=MAX_BREAK_INTERVAL_MINS,
        steps=MAX_BREAK_INTERVAL_MINS - MIN_BREAK_INTERVAL_MINS,
        value=cur_interval,
        on_change=on_interval,
    )

    cur_stay = clamp_break_stay_secs(pet.pet_config.get("break_stay_secs"))
    stay_lbl = _label(card, f"Stay visible  {int(cur_stay)} sec", theme, bold=True, pady=(0, 0))

    def on_stay(val):
        value = int(float(val))
        stay_lbl.configure(text=f"Stay visible  {value} sec")
        pet.pet_config.set("break_stay_secs", value)

    stay_sl = _slider(
        card, theme, accent, accent_hover,
        from_=MIN_BREAK_STAY_SECS,
        to=MAX_BREAK_STAY_SECS,
        steps=max(1, (MAX_BREAK_STAY_SECS - MIN_BREAK_STAY_SECS) // 5),
        value=cur_stay,
        on_change=on_stay,
    )

    def on_toggle():
        if enable.get() == 1:
            pet.pet_config.set("break_interval_mins", int(interval_sl.get()))
            pet.pet_config.set("break_stay_secs", int(stay_sl.get()))
        else:
            pet.pet_config.set("break_interval_mins", 0)
        pet._start_break_timer()

    enable.configure(command=on_toggle)

    ctk.CTkButton(
        parent,
        text="Test reminder",
        font=("Segoe UI", 11, "bold"),
        command=lambda: pet._trigger_break_reminder(),
        **_secondary_btn(theme, accent, accent_hover),
    ).pack(fill="x", padx=12, pady=(8, 12))


# ── Tasks ─────────────────────────────────────────────────
def open_spellbook_window(pet):
    if _bring_to_front("spellbook"):
        return

    win = ctk.CTkToplevel(pet)
    _track_window("spellbook", win)
    win.title("Today")
    win.geometry("500x640")
    win.resizable(False, False)
    win.attributes("-topmost", True)

    theme = _theme()
    accent = theme["accent"]
    accent_hover = theme["accent_hover"]
    win.configure(fg_color=theme["bg"])

    tasks = load_tasks()
    hint_clock, hint_mer = next_half_hour_parts()
    current_slot = default_task_slot()
    syncing = {"on": False}

    def persist():
        try:
            save_tasks(tasks)
        except Exception as exc:
            print(f"Error saving tasks: {exc}")

    header = ctk.CTkFrame(win, fg_color=theme["bg"])
    header.pack(fill="x", padx=18, pady=(16, 2))
    top = ctk.CTkFrame(header, fg_color="transparent")
    top.pack(fill="x")
    ctk.CTkLabel(top, text="Today", font=("Segoe UI", 18, "bold"), text_color=theme["text"]).pack(side="left")
    stats_lbl = ctk.CTkLabel(top, text="", font=("Segoe UI", 11), text_color=theme["text_dim"])
    stats_lbl.pack(side="right")
    day_lbl = ctk.CTkLabel(header, text=workday_headline(), font=("Segoe UI", 12), text_color=theme["text"])
    day_lbl.pack(anchor="w", pady=(2, 0))
    sub_lbl = ctk.CTkLabel(header, text=workday_subline(), font=("Segoe UI", 11), text_color=theme["text_dim"])
    sub_lbl.pack(anchor="w")
    progress = ctk.CTkProgressBar(win, height=6, progress_color=accent, fg_color=theme["frame"])
    progress.pack(fill="x", padx=18, pady=(8, 6))

    composer = _card(win, theme)
    task_entry = ctk.CTkEntry(composer, placeholder_text="What needs to get done?", font=("Segoe UI", 12), height=34)
    task_entry.pack(fill="x", padx=12, pady=(12, 8))

    meta = ctk.CTkFrame(composer, fg_color="transparent")
    meta.pack(fill="x", padx=12)
    slot_var = ctk.StringVar(value=DUE_PRESETS.get(current_slot, "Afternoon"))
    slot_menu = ctk.CTkOptionMenu(
        meta,
        values=list(DUE_PRESETS.values()),
        variable=slot_var,
        width=122,
        height=32,
        button_color=accent,
        button_hover_color=accent_hover,
        fg_color=theme["btn_secondary_bg"],
        text_color=theme["btn_secondary_text"],
        dropdown_fg_color=theme["bg"],
        dropdown_text_color=theme["text"],
    )
    slot_menu.pack(side="left")
    time_entry = ctk.CTkEntry(meta, placeholder_text=hint_clock, font=("Segoe UI", 12), height=32, width=68)
    time_entry.pack(side="left", padx=(8, 6))
    mer_var = ctk.StringVar(value=default_meridian(slot=current_slot) if current_slot != "later" else hint_mer)
    mer_btn = ctk.CTkSegmentedButton(
        meta,
        values=["AM", "PM"],
        variable=mer_var,
        width=88,
        height=32,
        font=("Segoe UI", 11, "bold"),
        selected_color=accent,
        selected_hover_color=accent_hover,
        unselected_color=theme["tab_inactive_bg"],
        unselected_hover_color=theme["btn_secondary_hover"],
        text_color=theme["text"],
    )
    mer_btn.set(mer_var.get())
    mer_btn.pack(side="left")
    add_btn = ctk.CTkButton(
        meta,
        text="Add",
        width=68,
        height=32,
        font=("Segoe UI", 12, "bold"),
        command=lambda: add_task(),
        **_primary_btn(theme, accent, accent_hover),
    )
    add_btn.pack(side="right")

    preview_lbl = ctk.CTkLabel(composer, text="", font=("Segoe UI", 11), text_color=theme["text_dim"])
    preview_lbl.pack(anchor="w", padx=12, pady=(6, 10))

    def current_slot_key():
        return slot_key_from_label(slot_var.get(), default_task_slot())

    def set_meridian(value):
        mer_var.set(value)
        mer_btn.set(value)

    def set_slot(key):
        slot_var.set(DUE_PRESETS.get(key, "Afternoon"))

    def composer_state():
        clock_text = time_entry.get().strip()
        meridian = mer_var.get()
        slot = current_slot_key()
        parsed = parse_clock_text(clock_text, meridian=meridian) if clock_text else None
        if clock_text and parsed is None:
            return None, slot, "Use a time like 3:30"
        due, resolved = due_from_slot_and_clock(slot, clock_text, meridian=meridian)
        return (due, resolved, clock_text, meridian, parsed), slot, due_preview_label(due)

    def refresh_preview(*_args):
        _state, _slot, message = composer_state()
        preview_lbl.configure(
            text=message,
            text_color=theme["danger"] if message.startswith("Use a time") else theme["text_dim"],
        )

    def on_slot_change(label):
        if syncing["on"]:
            return
        key = slot_key_from_label(label, default_task_slot())
        if not time_entry.get().strip():
            set_meridian(default_meridian(slot=key))
        refresh_preview()

    def on_time_blur(_event=None):
        if syncing["on"]:
            return
        clock_text = time_entry.get().strip()
        if not clock_text:
            refresh_preview()
            return
        parsed = parse_clock_text(clock_text, meridian=mer_var.get())
        if parsed is None:
            refresh_preview()
            return
        display, mer = clock_display_parts(parsed)
        syncing["on"] = True
        time_entry.delete(0, "end")
        time_entry.insert(0, display)
        set_meridian(mer)
        if current_slot_key() != "later":
            _due, resolved = due_from_slot_and_clock(current_slot_key(), display, meridian=mer)
            set_slot(resolved)
        syncing["on"] = False
        refresh_preview()

    def on_meridian_change(value):
        if syncing["on"]:
            return
        clock_text = time_entry.get().strip()
        if clock_text and current_slot_key() != "later":
            parsed = parse_clock_text(clock_text, meridian=value)
            if parsed is not None:
                _due, resolved = due_from_slot_and_clock(current_slot_key(), clock_text, meridian=value)
                syncing["on"] = True
                set_slot(resolved)
                syncing["on"] = False
        refresh_preview()

    slot_menu.configure(command=on_slot_change)
    mer_btn.configure(command=on_meridian_change)
    time_entry.bind("<FocusOut>", on_time_blur)
    time_entry.bind("<KeyRelease>", lambda _event: refresh_preview())

    def add_task():
        text = task_entry.get().strip()
        if not text:
            task_entry.focus()
            return
        state, _slot, message = composer_state()
        if state is None:
            preview_lbl.configure(text=message, text_color=theme["danger"])
            time_entry.focus()
            return
        due, slot, clock_text, meridian, parsed = state
        if parsed is not None:
            clock_text, meridian = clock_display_parts(parsed)
        tasks.append({
            "text": text,
            "done": False,
            "done_today": False,
            "priority": "normal",
            "category": "work",
            "slot": slot,
            "clock": bool(clock_text),
            "clock_text": clock_text,
            "meridian": meridian,
            "due": due,
            "reminded_at": "",
            "created": datetime.datetime.now().isoformat(),
        })
        persist()
        task_entry.delete(0, "end")
        time_entry.delete(0, "end")
        set_slot(default_task_slot())
        set_meridian(default_meridian(slot=default_task_slot()))
        refresh_preview()
        render_tasks()
        task_entry.focus()

    add_btn.configure(command=add_task)
    task_entry.bind("<Return>", lambda _event: add_task())
    time_entry.bind("<Return>", lambda _event: add_task())

    scroll = ctk.CTkScrollableFrame(win, fg_color=theme["bg"])
    scroll.pack(fill="both", expand=True, padx=10, pady=(0, 6))
    footer = ctk.CTkFrame(win, fg_color=theme["bg"])
    footer.pack(fill="x", padx=16, pady=(0, 14))
    clear_btn = ctk.CTkButton(
        footer,
        text="Clear done",
        font=("Segoe UI", 11),
        command=lambda: clear_done(),
        **_secondary_btn(theme, accent, accent_hover),
    )
    clear_btn.pack(fill="x")

    def render_tasks():
        open_count = sum(1 for task in tasks if not task.get("done"))
        done = sum(1 for task in tasks if task.get("done"))
        total = len(tasks)
        progress.set(done / total if total else 0)
        stats_lbl.configure(text=f"{open_count} left" if open_count else "All clear")
        day_lbl.configure(text=workday_headline())
        sub_lbl.configure(text=workday_subline())
        clear_btn.configure(state="normal" if done else "disabled")
        for child in scroll.winfo_children():
            child.destroy()

        if not tasks:
            ctk.CTkLabel(
                scroll,
                text="Add the few things that matter today.",
                font=("Segoe UI", 12),
                text_color=theme["text_dim"],
            ).pack(pady=28)
            return

        grouped = {key: [] for key, _label in WORKDAY_BUCKETS}
        for index, task in enumerate(tasks):
            grouped.setdefault(task_workday_bucket(task), []).append((index, task))

        live_slot = default_task_slot()
        if workday_period() == "lunch":
            live_slot = "afternoon"
        if workday_period() == "wrapup":
            live_slot = "eod"

        shown = 0
        for key, title in WORKDAY_BUCKETS:
            items = grouped.get(key) or []
            if not items:
                continue
            items.sort(key=lambda pair: (0 if format_task_when(pair[1]).startswith("Overdue") else 1, task_sort_key(pair[1])))
            shown += 1
            header_color = accent if key == live_slot else theme["text_dim"]
            label = title if key != live_slot else f"{title}  ·  now"
            ctk.CTkLabel(
                scroll,
                text=label,
                font=("Segoe UI", 11, "bold"),
                text_color=header_color,
            ).pack(anchor="w", padx=8, pady=(12 if shown > 1 else 4, 4))
            for index, task in items:
                row = ctk.CTkFrame(scroll, fg_color=theme["frame"], corner_radius=8, border_width=0)
                row.pack(fill="x", pady=3, padx=4)
                done_state = bool(task.get("done"))
                due_text = format_task_when(task)
                overdue = due_text.startswith("Overdue") and not done_state
                checkbox = ctk.CTkCheckBox(
                    row,
                    text=task.get("text") or "Task",
                    font=("Segoe UI", 11),
                    text_color=theme["text_dim"] if done_state else theme["text"],
                    fg_color=accent,
                    hover_color=accent_hover,
                    command=lambda idx=index: toggle_task(idx),
                )
                if done_state:
                    checkbox.select()
                checkbox.pack(side="left", padx=(10, 6), pady=8, fill="x", expand=True)
                ctk.CTkButton(
                    row,
                    text="✕",
                    width=32,
                    height=28,
                    font=("Segoe UI", 11),
                    fg_color=theme["frame"],
                    hover_color=theme["danger"],
                    text_color=theme["text_dim"],
                    command=lambda idx=index: delete_task(idx),
                ).pack(side="right", padx=(4, 8), pady=6)
                if not done_state:
                    move_var = ctk.StringVar(value=DUE_PRESETS.get(task.get("slot"), "Afternoon"))
                    ctk.CTkOptionMenu(
                        row,
                        values=list(DUE_PRESETS.values()),
                        variable=move_var,
                        width=108,
                        height=28,
                        font=("Segoe UI", 10),
                        button_color=accent,
                        button_hover_color=accent_hover,
                        fg_color=theme["btn_secondary_bg"],
                        text_color=theme["btn_secondary_text"],
                        dropdown_fg_color=theme["bg"],
                        dropdown_text_color=theme["text"],
                        command=lambda label, idx=index: move_task(idx, label),
                    ).pack(side="right", padx=(0, 4), pady=6)
                if due_text:
                    ctk.CTkLabel(
                        row,
                        text=due_text,
                        font=("Segoe UI", 10),
                        text_color=theme["danger"] if overdue else theme["text_dim"],
                    ).pack(side="right", padx=(0, 8), pady=8)

    def move_task(idx, label):
        if not (0 <= idx < len(tasks)):
            return
        key = slot_key_from_label(label, default_task_slot())
        task = tasks[idx]
        due, slot = due_from_slot_and_clock(
            key,
            task.get("clock_text") or "",
            meridian=task.get("meridian") or default_meridian(slot=key),
        )
        task["slot"] = slot
        task["due"] = due
        if not task.get("clock_text"):
            task["meridian"] = default_meridian(slot=slot)
        task["reminded_at"] = ""
        persist()
        render_tasks()

    def delete_task(idx):
        if 0 <= idx < len(tasks):
            tasks.pop(idx)
            persist()
            render_tasks()

    def toggle_task(idx):
        if not (0 <= idx < len(tasks)):
            return
        task = tasks[idx]
        if task.get("done"):
            task["done"] = False
            task["done_today"] = False
        else:
            task["done"] = True
            task["done_today"] = True
            pet.trigger_task_complete_celebration()
        persist()
        render_tasks()

    def clear_done():
        tasks[:] = [task for task in tasks if not task.get("done")]
        persist()
        render_tasks()

    refresh_preview()
    render_tasks()
    win.after(80, task_entry.focus)


# ── Timer ─────────────────────────────────────────────────
def open_timer_window(pet):
    if _bring_to_front("timer"):
        return

    win = ctk.CTkToplevel(pet)
    theme = _theme()
    accent = theme["accent"]
    accent_hover = theme["accent_hover"]
    win.title("Workday")
    win.geometry("400x600")
    win.resizable(False, False)
    win.attributes("-topmost", True)
    win.configure(fg_color=theme["bg"])

    def on_close():
        pet.remove_timer_listener(apply_snapshot)

    _track_window("timer", win, on_close=on_close)

    header = ctk.CTkFrame(win, fg_color=theme["bg"])
    header.pack(fill="x", padx=18, pady=(16, 2))
    ctk.CTkLabel(header, text="Workday", font=("Segoe UI", 18, "bold"), text_color=theme["text"]).pack(anchor="w")
    clock_lbl = ctk.CTkLabel(header, text=format_clock_label(seconds=False), font=("Segoe UI", 22, "bold"), text_color=theme["text"])
    clock_lbl.pack(anchor="w", pady=(4, 0))
    day_lbl = ctk.CTkLabel(header, text=workday_headline(), font=("Segoe UI", 12), text_color=theme["text_dim"])
    day_lbl.pack(anchor="w")
    left_lbl = ctk.CTkLabel(header, text=workday_subline(), font=("Segoe UI", 11), text_color=theme["text_dim"])
    left_lbl.pack(anchor="w")

    ring = tk.Canvas(win, width=188, height=188, bg=theme["bg"], highlightthickness=0)
    ring.pack(pady=8)

    def draw_ring(fraction, time_str, label_str=""):
        ring.delete("all")
        ring.create_oval(16, 16, 172, 172, outline=theme["frame"], width=12)
        if fraction > 0:
            ring.create_arc(
                16, 16, 172, 172,
                start=90,
                extent=-min(359.9, fraction * 359.9),
                outline=accent,
                width=12,
                style="arc",
            )
        ring.create_text(94, 84, text=time_str, fill=theme["text"], font=("Segoe UI", 26, "bold"))
        ring.create_text(94, 118, text=label_str, fill=theme["text_dim"], font=("Segoe UI", 11))

    ends_lbl = ctk.CTkLabel(win, text="", font=("Segoe UI", 11), text_color=theme["text_dim"])
    ends_lbl.pack()
    blocks_lbl = ctk.CTkLabel(win, text="", font=("Segoe UI", 11), text_color=theme["text_dim"])
    chip_buttons = {}
    suggested = suggested_workday_block()

    def style_chip(name, active):
        button = chip_buttons.get(name)
        if button is None:
            return
        if active:
            button.configure(**_primary_btn(theme, accent, accent_hover))
        else:
            button.configure(**_secondary_btn(theme, accent, accent_hover))

    def refresh_chips(snap):
        label = "Break" if snap.get("is_break") else (snap.get("label") or "")
        running = bool(snap.get("running"))
        for name in chip_buttons:
            is_active = name == label or (name == "Custom" and str(label).endswith("m"))
            style_chip(name, is_active)
            chip_buttons[name].configure(state="disabled" if running else "normal")

    def apply_snapshot(snap):
        if not win.winfo_exists():
            return
        remaining = int(snap.get("remaining") or 0)
        total = int(snap.get("total") or 0)
        minutes = remaining // 60
        seconds = remaining % 60
        fraction = remaining / total if total else 0
        label = "Break" if snap.get("is_break") else (snap.get("label") or "Focus")
        draw_ring(fraction, f"{minutes:02d}:{seconds:02d}", label)
        ends_lbl.configure(text=ends_at_label(remaining) if remaining else "Pick a block, then start")
        count = int(snap.get("pomodoro_count") or 0)
        blocks_lbl.configure(text=f"{count} focus block{'s' if count != 1 else ''} today")
        refresh_chips(snap)
        if snap.get("running"):
            control.configure(text="Pause")
        elif remaining > 0 and remaining < total:
            control.configure(text="Resume")
        else:
            control.configure(text="Start")

    chips = ctk.CTkFrame(win, fg_color="transparent")
    chips.pack(fill="x", padx=18, pady=(8, 4))
    for name in WORKDAY_TIMER_PRESETS:
        mins = WORKDAY_TIMER_PRESETS[name]["secs"] // 60
        mark = " ·" if name == suggested else ""
        button = ctk.CTkButton(
            chips,
            text=f"{name}{mark}\n{mins}m",
            width=80,
            height=48,
            font=("Segoe UI", 10),
            command=lambda value=name: choose_block(value),
            **_secondary_btn(theme, accent, accent_hover),
        )
        button.pack(side="left", expand=True, padx=3)
        chip_buttons[name] = button

    custom_card = _card(win, theme)
    custom = ctk.CTkFrame(custom_card, fg_color="transparent")
    custom.pack(fill="x", padx=10, pady=8)
    ctk.CTkLabel(custom, text="Custom", font=("Segoe UI", 11, "bold"), text_color=theme["text"]).pack(side="left")
    last_custom = clamp_custom_timer_mins(config_db.get("last_custom_timer_mins") or 20)
    custom_entry = ctk.CTkEntry(custom, font=("Segoe UI", 11), height=30, width=56)
    custom_entry.insert(0, str(last_custom))
    custom_entry.pack(side="left", padx=8)
    ctk.CTkLabel(custom, text="min", font=("Segoe UI", 11), text_color=theme["text_dim"]).pack(side="left")

    def choose_block(name):
        if pet.user_timer_snapshot().get("running"):
            return
        pet.apply_workday_timer(name)

    def set_custom_timer():
        if pet.user_timer_snapshot().get("running"):
            return
        pet.apply_custom_timer(custom_entry.get())
        custom_entry.delete(0, "end")
        custom_entry.insert(0, str(clamp_custom_timer_mins(pet.pet_config.get("last_custom_timer_mins"))))

    custom_btn = ctk.CTkButton(
        custom,
        text="Set",
        width=52,
        height=30,
        font=("Segoe UI", 11, "bold"),
        command=set_custom_timer,
        **_secondary_btn(theme, accent, accent_hover),
    )
    custom_btn.pack(side="right")
    chip_buttons["Custom"] = custom_btn
    custom_entry.bind("<Return>", lambda _event: set_custom_timer())

    blocks_lbl.pack(pady=(2, 0))
    ctk.CTkLabel(
        win,
        text="Keeps running if you close this window.",
        font=("Segoe UI", 10),
        text_color=theme["text_dim"],
    ).pack(pady=(2, 0))

    control = ctk.CTkButton(
        win,
        text="Start",
        font=("Segoe UI", 13, "bold"),
        command=pet.toggle_user_timer,
        **_primary_btn(theme, accent, accent_hover),
    )
    control.pack(fill="x", padx=22, pady=14)

    def tick_clock():
        if not win.winfo_exists():
            return
        clock_lbl.configure(text=format_clock_label(seconds=False))
        day_lbl.configure(text=workday_headline())
        left_lbl.configure(text=workday_subline())
        snap = pet.user_timer_snapshot()
        remaining = int(snap.get("remaining") or 0)
        if remaining:
            ends_lbl.configure(text=ends_at_label(remaining))
        win.after(1000, tick_clock)

    if not pet.user_timer_snapshot().get("running"):
        current = pet.user_timer_snapshot().get("label")
        if not current or current == "Focus":
            pet.apply_workday_timer(suggested)

    pet.add_timer_listener(apply_snapshot)
    apply_snapshot(pet.user_timer_snapshot())
    tick_clock()


def show_timer_alert(pet, break_over=False, label=""):
    theme = _theme()
    accent = theme["accent"]
    accent_hover = theme["accent_hover"]
    parent = pet
    timer_win = _active_windows.get("timer")
    if timer_win is not None:
        try:
            if timer_win.winfo_exists():
                parent = timer_win
        except Exception:
            pass
    _show_alert(parent, pet, theme, accent, accent_hover, break_over=break_over, label=label)


def _show_alert(win, pet, theme, accent, accent_hover, break_over=False, label=""):
    alert = ctk.CTkToplevel(win)
    apply_app_icon(alert)
    alert.title("Workday")
    alert.geometry("300x150")
    alert.resizable(False, False)
    alert.attributes("-topmost", True)
    alert.configure(fg_color=theme["bg"])

    if break_over:
        message = "Break is over. Ready for the next block."
        button = "Continue"
    elif label == "Lunch":
        message = "Lunch block is done."
        button = "OK"
    elif label == "Wrap-up":
        message = "Wrap-up is done. You can shut down."
        button = "OK"
    else:
        message = "Block complete. Take a short stretch."
        button = "OK"
    ctk.CTkLabel(alert, text=message, font=("Segoe UI", 12), text_color=theme["text"]).pack(expand=True, pady=16)
    ctk.CTkButton(
        alert,
        text=button,
        command=lambda: [alert.destroy(), pet.set_state("idle")],
        **_primary_btn(theme, accent, accent_hover),
    ).pack(fill="x", padx=20, pady=(0, 16))
