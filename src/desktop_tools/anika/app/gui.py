import tkinter as tk
import customtkinter as ctk
import os
import json
import math
import datetime
from app.config import config_db, TODO_FILE, PERSONALITY_PRESETS, get_gui_theme
from app.ui_theme import apply_ctk_appearance, enrich_theme
from app.menu_actions import (
    PET_FORCE_ACTIONS,
    PET_QUIT_ACTION,
    PET_TOOL_ACTIONS,
    run_pet_menu_action,
)

apply_ctk_appearance()

# Window tracking to prevent duplicates
_active_windows = {}


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


def _inactive_btn(theme, accent_hover):
    return {
        "fg_color": theme["btn_inactive_bg"],
        "hover_color": accent_hover,
        "text_color": theme["btn_inactive_text"],
    }


def _bring_to_front(win_key):
    if win_key in _active_windows and _active_windows[win_key].winfo_exists():
        _active_windows[win_key].lift()
        _active_windows[win_key].focus()
        return True
    return False


def _apply_theme(win, theme):
    """Apply theme fg_color to a CTkToplevel."""
    win.configure(fg_color=theme["bg"])


# ═══════════════════════════════════════════════════════════
#  SETTINGS WINDOW
# ═══════════════════════════════════════════════════════════
def open_settings_window(pet):
    if _bring_to_front("settings"):
        return

    win = ctk.CTkToplevel(pet)
    _active_windows["settings"] = win
    win.title("Anika — Settings")
    win.geometry("520x720")
    win.resizable(True, True)
    win.minsize(480, 640)
    win.attributes("-topmost", True)

    theme = enrich_theme(get_gui_theme())
    win.configure(fg_color=theme["bg"])
    accent = theme["accent"]
    accent_hover = theme["accent_hover"]
    border = theme.get("border", "#90A4AE")

    header = ctk.CTkFrame(win, fg_color=theme["frame"], corner_radius=10, border_width=1, border_color=border)
    header.pack(fill="x", padx=18, pady=(16, 8))
    ctk.CTkLabel(
        header, text="Anika — Mascot & Tools", font=("Segoe UI", 17, "bold"),
        text_color=theme["text"]
    ).pack(anchor="w", padx=14, pady=(12, 2))
    ctk.CTkLabel(
        header, text="Settings match the Media Downloader hub style.",
        font=("Segoe UI", 11), text_color=theme["text_dim"]
    ).pack(anchor="w", padx=14, pady=(0, 12))

    # ─ Tabview ─
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
    tabs.pack(fill="both", expand=True, padx=18, pady=8)

    tab_main = tabs.add("🎭 Appearance")
    tab_personality = tabs.add("🧠 Personality")
    tab_effects = tabs.add("✨ Effects")
    tab_break = tabs.add("⏰ Break")
    tab_menu = tabs.add("🎮 Actions")

    # ─ Appearance Tab ─
    _make_scale_slider(tab_main, pet, theme, accent, accent_hover)
    _make_opacity_slider(tab_main, pet, theme, accent, accent_hover)
    _make_lang_option(tab_main, pet, theme, accent, accent_hover)

    # ─ Personality Tab ─
    _make_personality_panel(tab_personality, pet, theme, accent, accent_hover)

    # ─ Effects Tab ─
    _make_effects_panel(tab_effects, pet, theme, accent, accent_hover)

    # ─ Break Reminder Tab ─
    _make_break_panel(tab_break, pet, theme, accent, accent_hover)

    # ─ Actions (same as right-click menu) ─
    _make_menu_panel(tab_menu, pet, theme, accent, accent_hover)

    # ─ Toggles (gravity, boundary) ─
    toggles_frame = ctk.CTkFrame(win, fg_color=theme["frame"], corner_radius=10)
    toggles_frame.pack(fill="x", padx=18, pady=8)

    gravity_switch = ctk.CTkSwitch(
        toggles_frame, text="Gravity (Fall Down)", font=("Segoe UI", 11, "bold"),
        text_color=theme["text"],
        progress_color=accent, button_color=theme["gold"], button_hover_color=accent
    )
    gravity_switch.select() if pet.pet_config.get("gravity_enabled") else gravity_switch.deselect()

    def on_gravity():
        pet.pet_config.set("gravity_enabled", gravity_switch.get() == 1)
        if not pet.pet_config.get("gravity_enabled"):
            pet.vy = 0

    gravity_switch.configure(command=on_gravity)
    gravity_switch.pack(anchor="w", padx=20, pady=(10, 5))

    bound_switch = ctk.CTkSwitch(
        toggles_frame, text="Keep Within Screen", font=("Segoe UI", 11, "bold"),
        text_color=theme["text"],
        progress_color=accent, button_color=theme["gold"], button_hover_color=accent
    )
    bound_switch.select() if pet.pet_config.get("boundary_keep") else bound_switch.deselect()
    bound_switch.configure(command=lambda: pet.pet_config.set("boundary_keep", bound_switch.get() == 1))
    bound_switch.pack(anchor="w", padx=20, pady=(0, 10))

    sound_switch = ctk.CTkSwitch(
        toggles_frame, text="Sound Effects", font=("Segoe UI", 11, "bold"),
        text_color=theme["text"],
        progress_color=accent, button_color=theme["gold"], button_hover_color=accent
    )
    sound_switch.select() if pet.pet_config.get("sound_enabled") else sound_switch.deselect()
    sound_switch.configure(command=lambda: pet.pet_config.set("sound_enabled", sound_switch.get() == 1))
    sound_switch.pack(anchor="w", padx=20, pady=(0, 10))

    _make_edge_hide_controls(toggles_frame, pet, theme, accent, accent_hover)

    ctk.CTkButton(
        win, text="✅ Done", font=("Segoe UI", 12, "bold"), command=win.destroy,
        **_primary_btn(theme, accent, accent_hover),
    ).pack(pady=(8, 15))


def _make_edge_hide_controls(parent, pet, theme, accent, accent_hover):
    """Drag-to-screen-edge hide duration (Appearance toggles section)."""
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(fill="x", padx=8, pady=(4, 8))

    edge_sw = ctk.CTkSwitch(
        frame,
        text="Hide when dragged to screen edge",
        font=("Segoe UI", 11, "bold"),
        text_color=theme["text"],
        progress_color=accent,
        button_color=theme["gold"],
        button_hover_color=accent,
    )
    edge_sw.select() if pet.pet_config.get("edge_hide_enabled") else edge_sw.deselect()
    edge_sw.pack(anchor="w", padx=12, pady=(6, 4))

    mins_frame = ctk.CTkFrame(frame, fg_color=theme["frame"], corner_radius=8)
    mins_frame.pack(fill="x", padx=8, pady=(0, 6))

    cur_mins = int(float(pet.pet_config.get("edge_hide_mins") or 5))
    mins_lbl = ctk.CTkLabel(
        mins_frame,
        text=f"Stay away for: {cur_mins} min",
        font=("Segoe UI", 11, "bold"),
        text_color=theme["text"],
    )
    mins_lbl.pack(anchor="w", padx=12, pady=(8, 0))

    ctk.CTkLabel(
        mins_frame,
        text="Drag Anika to any edge of your screen; she leaves and returns after this time.",
        font=("Segoe UI", 9),
        text_color=theme["text_dim"],
        wraplength=400,
        justify="left",
    ).pack(anchor="w", padx=12, pady=(0, 4))

    def sync_mins_slider_state():
        state = "normal" if edge_sw.get() == 1 else "disabled"
        mins_sl.configure(state=state)
        mins_lbl.configure(text_color=theme["text"] if edge_sw.get() == 1 else theme["text_dim"])

    def on_mins(val):
        v = max(1, min(60, int(float(val))))
        mins_lbl.configure(text=f"Stay away for: {v} min")
        pet.pet_config.set("edge_hide_mins", v)

    mins_sl = ctk.CTkSlider(
        mins_frame,
        from_=1,
        to=60,
        number_of_steps=59,
        button_color=accent,
        button_hover_color=accent_hover,
        progress_color=accent,
    )
    mins_sl.set(cur_mins)
    mins_sl.configure(command=on_mins)
    mins_sl.pack(fill="x", padx=12, pady=(4, 10))

    hint = ctk.CTkFrame(mins_frame, fg_color="transparent")
    hint.pack(fill="x", padx=12, pady=(0, 8))
    ctk.CTkLabel(hint, text="1 min", font=("Segoe UI", 9), text_color=theme["text_dim"]).pack(side="left")
    ctk.CTkLabel(hint, text="60 min", font=("Segoe UI", 9), text_color=theme["text_dim"]).pack(side="right")

    def on_edge_toggle():
        pet.pet_config.set("edge_hide_enabled", edge_sw.get() == 1)
        sync_mins_slider_state()

    edge_sw.configure(command=on_edge_toggle)
    sync_mins_slider_state()


def _make_scale_slider(parent, pet, theme, accent, accent_hover):
    frame = ctk.CTkFrame(parent, fg_color=theme["frame"], corner_radius=10)
    frame.pack(fill="x", padx=8, pady=6)
    lbl = ctk.CTkLabel(frame, text=f"📏 Mascot Size: {pet.pet_config.get('scale'):.1f}x",
                        font=("Segoe UI", 11, "bold"), text_color=theme["text"])
    lbl.pack(anchor="w", padx=15, pady=(8, 0))

    def on_change(val):
        val = round(val, 1)
        lbl.configure(text=f"📏 Mascot Size: {val}x")
        pet.pet_config.set("scale", val)
        pet.update_dimensions()
        pet.assets.clear_cache()
        pet.render_pet()

    sl = ctk.CTkSlider(frame, from_=0.5, to=2.5, number_of_steps=20,
                        button_color=accent, button_hover_color=accent_hover, progress_color=accent)
    sl.set(pet.pet_config.get("scale"))
    sl.configure(command=on_change)
    sl.pack(fill="x", padx=15, pady=(5, 12))


def _make_opacity_slider(parent, pet, theme, accent, accent_hover):
    frame = ctk.CTkFrame(parent, fg_color=theme["frame"], corner_radius=10)
    frame.pack(fill="x", padx=8, pady=6)
    lbl = ctk.CTkLabel(frame, text=f"👁️ Opacity: {int(pet.pet_config.get('opacity') * 100)}%",
                        font=("Segoe UI", 11, "bold"), text_color=theme["text"])
    lbl.pack(anchor="w", padx=15, pady=(8, 0))

    def on_change(val):
        lbl.configure(text=f"👁️ Opacity: {int(val * 100)}%")
        pet.pet_config.set("opacity", val)
        pet.config_window_transparency()

    sl = ctk.CTkSlider(frame, from_=0.2, to=1.0,
                        button_color=accent, button_hover_color=accent_hover, progress_color=accent)
    sl.set(pet.pet_config.get("opacity"))
    sl.configure(command=on_change)
    sl.pack(fill="x", padx=15, pady=(5, 12))


def _make_lang_option(parent, pet, theme, accent, accent_hover):
    frame = ctk.CTkFrame(parent, fg_color=theme["frame"], corner_radius=10)
    frame.pack(fill="x", padx=8, pady=6)
    ctk.CTkLabel(frame, text="🗣️ Speech Language:", font=("Segoe UI", 11, "bold"),
                  text_color=theme["text"]).pack(side="left", padx=15, pady=12)
    opt = ctk.CTkOptionMenu(
        frame, values=["mix", "bn", "en"],
        button_color=accent, button_hover_color=accent_hover,
        dropdown_hover_color=accent_hover,
        fg_color=theme["btn_secondary_bg"],
        text_color=theme["btn_secondary_text"],
        dropdown_fg_color=theme["bg"],
        dropdown_text_color=theme["text"],
    )
    opt.set(pet.pet_config.get("language"))
    opt.configure(command=lambda val: pet.pet_config.set("language", val))
    opt.pack(side="right", padx=15, pady=12)


def _refresh_personality_cards(cards: dict, active_key: str, theme, accent, accent_hover) -> None:
    for key, widgets in cards.items():
        is_active = key == active_key
        widgets["frame"].configure(fg_color=accent if is_active else theme["frame"])
        widgets["title"].configure(
            text_color=theme["text_on_accent"] if is_active else theme["text"],
        )
        widgets["desc"].configure(
            text_color=theme["text_on_accent_dim"] if is_active else theme["text_dim"],
        )
        widgets["btn"].configure(
            text="✓ Selected" if is_active else "Select",
            **_primary_btn(theme, accent, accent_hover) if is_active else _inactive_btn(theme, accent_hover),
        )


def _select_personality(pet, key, cards, theme, accent, accent_hover):
    config_db.set("personality", key)
    from app.config import get_personality

    pet.personality = get_personality()
    _refresh_personality_cards(cards, key, theme, accent, accent_hover)


def _make_personality_panel(parent, pet, theme, accent, accent_hover):
    ctk.CTkLabel(parent, text="Choose Anika's Personality", font=("Segoe UI", 13, "bold"),
                  text_color=theme["text"]).pack(pady=(10, 5))

    cards: dict = {}
    current = config_db.get("personality")
    emoji_map = {
        "energetic": "⚡",
        "calm": "🌿",
        "shy": "🌸",
        "mischievous": "😈",
        "playful": "🎉",
    }
    for key, preset in PERSONALITY_PRESETS.items():
        is_active = key == current
        frame = ctk.CTkFrame(parent, fg_color=accent if is_active else theme["frame"], corner_radius=10)
        frame.pack(fill="x", padx=10, pady=4)

        title_lbl = ctk.CTkLabel(
            frame,
            text=f"{emoji_map.get(key, '✨')} {key.capitalize()}",
            font=("Segoe UI", 12, "bold"),
            text_color=theme["text_on_accent"] if is_active else theme["text"],
        )
        title_lbl.pack(side="left", padx=12, pady=8)

        desc_lbl = ctk.CTkLabel(
            frame,
            text=preset["description"],
            font=("Segoe UI", 10),
            text_color=theme["text_on_accent_dim"] if is_active else theme["text_dim"],
        )
        desc_lbl.pack(side="left", padx=4)

        select_btn = ctk.CTkButton(
            frame,
            text="✓ Selected" if is_active else "Select",
            width=80,
            height=30,
            font=("Segoe UI", 10, "bold"),
            command=lambda k=key: _select_personality(pet, k, cards, theme, accent, accent_hover),
            **(_primary_btn(theme, accent, accent_hover) if is_active else _inactive_btn(theme, accent_hover)),
        )
        select_btn.pack(side="right", padx=10)
        cards[key] = {"frame": frame, "title": title_lbl, "desc": desc_lbl, "btn": select_btn}


def _make_effects_panel(parent, pet, theme, accent, accent_hover):
    ctk.CTkLabel(parent, text="Visual Effects", font=("Segoe UI", 13, "bold"),
                  text_color=theme["text"]).pack(pady=(10, 5))

    effects = [
        ("fairy_dust_enabled", "🧚 Fairy Dust (idle sparkles)"),
        ("magic_trail_enabled", "✨ Magic Trail (while moving)"),
    ]
    for key, label in effects:
        sw = ctk.CTkSwitch(
            parent, text=label, font=("Segoe UI", 11, "bold"),
            text_color=theme["text"],
            progress_color=accent, button_color=theme["gold"],
            button_hover_color=accent,
        )
        sw.select() if config_db.get(key) else sw.deselect()
        sw.configure(command=lambda k=key, s=sw: config_db.set(k, s.get() == 1))
        sw.pack(anchor="w", padx=15, pady=6)

    # Weather mode
    weather_btns = {}
    ctk.CTkLabel(parent, text="🌦️ Weather Particles:", font=("Segoe UI", 11, "bold"),
                  text_color=theme["text"]).pack(anchor="w", padx=15, pady=(12, 4))

    weather_frame = ctk.CTkFrame(parent, fg_color="transparent")
    weather_frame.pack(fill="x", padx=10)

    def set_weather(val):
        config_db.set("weather_mode", val)
        for v, btn in weather_btns.items():
            selected = v == val
            btn.configure(
                fg_color=accent if selected else theme["btn_inactive_bg"],
                text_color=theme["text_on_accent"] if selected else theme["btn_inactive_text"],
            )

    weather_options = [("none", "☀️ Off"), ("rain", "🌧️ Rain"), ("snow", "❄️ Snow"), ("sunny", "✨ Sunny")]
    for val, label in weather_options:
        selected = config_db.get("weather_mode") == val
        btn = ctk.CTkButton(
            weather_frame, text=label, width=80, height=32,
            hover_color=accent_hover, font=("Segoe UI", 10, "bold"),
            fg_color=accent if selected else theme["btn_inactive_bg"],
            text_color=theme["text_on_accent"] if selected else theme["btn_inactive_text"],
            command=lambda v=val: set_weather(v),
        )
        btn.pack(side="left", padx=3, expand=True)
        weather_btns[val] = btn


def _make_menu_panel(parent, pet, theme, accent, accent_hover):
    """Buttons for every right-click menu item (tools, force actions, quit)."""
    ctk.CTkLabel(
        parent,
        text="Same options as right-clicking Anika on your desktop",
        font=("Segoe UI", 10),
        text_color=theme["text_dim"],
        wraplength=400,
    ).pack(pady=(10, 8))

    tools_frame = ctk.CTkFrame(parent, fg_color=theme["frame"], corner_radius=10)
    tools_frame.pack(fill="x", padx=8, pady=(0, 8))
    ctk.CTkLabel(
        tools_frame,
        text="Tools",
        font=("Segoe UI", 12, "bold"),
        text_color=theme["text"],
    ).pack(anchor="w", padx=12, pady=(10, 6))

    for action_key, label in PET_TOOL_ACTIONS:
        ctk.CTkButton(
            tools_frame,
            text=label,
            anchor="w",
            font=("Segoe UI", 11, "bold"),
            command=lambda k=action_key: run_pet_menu_action(pet, k),
            **_primary_btn(theme, accent, accent_hover),
        ).pack(fill="x", padx=12, pady=3)

    ctk.CTkButton(
        tools_frame,
        text="⚙️ Mascot Settings (this window)",
        anchor="w",
        font=("Segoe UI", 11, "bold"),
        command=lambda: _bring_to_front("settings"),
        **_secondary_btn(theme, accent, accent_hover),
    ).pack(fill="x", padx=12, pady=(3, 10))

    ctk.CTkLabel(
        parent,
        text="🎭 Force Action",
        font=("Segoe UI", 12, "bold"),
        text_color=theme["text"],
    ).pack(anchor="w", padx=12, pady=(4, 4))

    scroll = ctk.CTkScrollableFrame(parent, fg_color=theme["frame"], corner_radius=10, height=260)
    scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    for action_key, label in PET_FORCE_ACTIONS:
        ctk.CTkButton(
            scroll,
            text=label,
            anchor="w",
            font=("Segoe UI", 11, "bold"),
            command=lambda k=action_key: run_pet_menu_action(pet, k),
            **_secondary_btn(theme, accent, accent_hover),
        ).pack(fill="x", padx=8, pady=3)

    quit_key, quit_label = PET_QUIT_ACTION
    ctk.CTkButton(
        parent,
        text=quit_label,
        fg_color=theme["danger"],
        hover_color=theme["danger_hover"],
        text_color=theme["text_on_accent"],
        font=("Segoe UI", 11, "bold"),
        command=lambda: run_pet_menu_action(pet, quit_key),
    ).pack(fill="x", padx=8, pady=(0, 10))


def _make_break_panel(parent, pet, theme, accent, accent_hover):
    """Break reminder settings — interval and how long Anika stays visible."""
    ctk.CTkLabel(parent, text="⏰ Break Reminder", font=("Segoe UI", 13, "bold"),
                  text_color=theme["text"]).pack(pady=(12, 4))

    ctk.CTkLabel(
        parent,
        text="Anika will pop up in the centre of your screen\nand wave to remind you to take a break.",
        font=("Segoe UI", 10), text_color=theme["text_dim"], justify="center"
    ).pack(pady=(0, 10))

    is_enabled = (pet.pet_config.get("break_interval_mins") or 0) > 0
    enable_sw = ctk.CTkSwitch(
        parent,
        text="Enable break reminders",
        font=("Segoe UI", 11, "bold"),
        text_color=theme["text"],
        progress_color=accent,
        button_color=theme["gold"],
        button_hover_color=accent,
    )
    enable_sw.select() if is_enabled else enable_sw.deselect()
    enable_sw.pack(anchor="w", padx=15, pady=(0, 8))

    # ── Interval slider ──────────────────────────────────────
    interval_frame = ctk.CTkFrame(parent, fg_color=theme["frame"], corner_radius=10)
    interval_frame.pack(fill="x", padx=10, pady=6)

    cur_interval = pet.pet_config.get("break_interval_mins") or 30
    if not is_enabled:
        cur_interval = 30
    interval_lbl = ctk.CTkLabel(
        interval_frame,
        text=f"🕐 Remind every: {int(cur_interval)} min",
        font=("Segoe UI", 11, "bold"), text_color=theme["text"]
    )
    interval_lbl.pack(anchor="w", padx=15, pady=(8, 0))

    def on_interval(val):
        v = int(val)
        interval_lbl.configure(text=f"🕐 Remind every: {v} min")
        if enable_sw.get() == 1:
            pet.pet_config.set("break_interval_mins", v)
            pet._start_break_timer()

    interval_sl = ctk.CTkSlider(
        interval_frame, from_=5, to=120, number_of_steps=23,
        button_color=accent, button_hover_color=accent_hover, progress_color=accent
    )
    interval_sl.set(cur_interval)
    interval_sl.configure(command=on_interval)
    interval_sl.pack(fill="x", padx=15, pady=(5, 12))

    # Helper labels
    hint_frame = ctk.CTkFrame(interval_frame, fg_color="transparent")
    hint_frame.pack(fill="x", padx=15, pady=(0, 8))
    ctk.CTkLabel(hint_frame, text="5 min", font=("Segoe UI", 9),
                  text_color=theme["text_dim"]).pack(side="left")
    ctk.CTkLabel(hint_frame, text="120 min", font=("Segoe UI", 9),
                  text_color=theme["text_dim"]).pack(side="right")

    # ── Stay duration slider ─────────────────────────────────
    stay_frame = ctk.CTkFrame(parent, fg_color=theme["frame"], corner_radius=10)
    stay_frame.pack(fill="x", padx=10, pady=6)

    cur_stay = pet.pet_config.get("break_stay_secs") or 8
    stay_lbl = ctk.CTkLabel(
        stay_frame,
        text=f"⏱ Stay visible for: {int(cur_stay)} sec",
        font=("Segoe UI", 11, "bold"), text_color=theme["text"]
    )
    stay_lbl.pack(anchor="w", padx=15, pady=(8, 0))

    def on_stay(val):
        v = int(val)
        stay_lbl.configure(text=f"⏱ Stay visible for: {v} sec")
        pet.pet_config.set("break_stay_secs", v)

    stay_sl = ctk.CTkSlider(
        stay_frame, from_=10, to=60, number_of_steps=10,
        button_color=accent, button_hover_color=accent_hover, progress_color=accent
    )
    stay_sl.set(cur_stay)
    stay_sl.configure(command=on_stay)
    stay_sl.pack(fill="x", padx=15, pady=(5, 12))

    hint_frame2 = ctk.CTkFrame(stay_frame, fg_color="transparent")
    hint_frame2.pack(fill="x", padx=15, pady=(0, 8))
    ctk.CTkLabel(hint_frame2, text="10 sec", font=("Segoe UI", 9),
                  text_color=theme["text_dim"]).pack(side="left")
    ctk.CTkLabel(hint_frame2, text="60 sec", font=("Segoe UI", 9),
                  text_color=theme["text_dim"]).pack(side="right")

    def on_toggle():
        if enable_sw.get() == 1:
            pet.pet_config.set("break_interval_mins", int(interval_sl.get()))
            pet.pet_config.set("break_stay_secs", int(stay_sl.get()))
        else:
            pet.pet_config.set("break_interval_mins", 0)
        pet._start_break_timer()

    enable_sw.configure(command=on_toggle)

    # ── Test button ──────────────────────────────────────────
    ctk.CTkButton(
        parent, text="🔔 Test Break Reminder Now",
        font=("Segoe UI", 11, "bold"),
        command=lambda: pet._trigger_break_reminder(),
        **_primary_btn(theme, accent, accent_hover),
    ).pack(pady=(10, 6))



# ═══════════════════════════════════════════════════════════
#  SPELL BOOK (TO-DO)
# ═══════════════════════════════════════════════════════════
def open_spellbook_window(pet):
    if _bring_to_front("spellbook"):
        return

    win = ctk.CTkToplevel(pet)
    _active_windows["spellbook"] = win
    win.title("📜 Spell Book — Magical Tasks")
    win.geometry("520x600")
    win.resizable(False, False)
    win.attributes("-topmost", True)

    theme = get_gui_theme()
    accent = theme["accent"]
    accent_hover = theme["accent_hover"]

    # Load tasks
    tasks = []
    if os.path.exists(TODO_FILE):
        try:
            with open(TODO_FILE, "r", encoding="utf-8") as f:
                tasks = json.load(f)
        except:
            pass

    # Migrate old tasks to new schema
    for t in tasks:
        if "priority" not in t:
            t["priority"] = "normal"
        if "category" not in t:
            t["category"] = "work"
        if "due" not in t:
            t["due"] = ""

    def save_tasks():
        try:
            with open(TODO_FILE, "w", encoding="utf-8") as f:
                json.dump(tasks, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving tasks: {e}")

    # ─ Header ─
    header_frame = ctk.CTkFrame(win, fg_color=theme["frame"], corner_radius=0)
    header_frame.pack(fill="x")

    ctk.CTkLabel(
        header_frame, text="🧙‍♀️ Spell Book of Tasks",
        font=("Segoe UI", 17, "bold"), text_color=theme["gold"]
    ).pack(side="left", padx=20, pady=14)

    # Stats label
    done_today = sum(1 for t in tasks if t.get("done_today"))
    stats_lbl = ctk.CTkLabel(
        header_frame,
        text=f"✅ {done_today} done today",
        font=("Segoe UI", 11), text_color=theme["text_dim"]
    )
    stats_lbl.pack(side="right", padx=20)

    # ─ Progress bar ─
    total = len(tasks)
    done = sum(1 for t in tasks if t.get("done"))
    progress_frame = ctk.CTkFrame(win, fg_color=theme["bg"], corner_radius=0)
    progress_frame.pack(fill="x", padx=0)

    progress_bar = ctk.CTkProgressBar(progress_frame, height=8, progress_color=accent,
                                       fg_color=theme["frame"])
    progress_bar.set(done / total if total > 0 else 0)
    progress_bar.pack(fill="x", padx=18, pady=6)

    progress_lbl = ctk.CTkLabel(
        progress_frame,
        text=f"{done}/{total} spells cast  🪄",
        font=("Segoe UI", 10), text_color=theme["text_dim"]
    )
    progress_lbl.pack(pady=(0, 4))

    # ─ Add task row ─
    input_frame = ctk.CTkFrame(win, fg_color=theme["frame"], corner_radius=10)
    input_frame.pack(fill="x", padx=18, pady=(8, 4))

    task_entry = ctk.CTkEntry(
        input_frame, placeholder_text="✍️ Write a magical task...",
        font=("Segoe UI", 11), width=200
    )
    task_entry.pack(side="left", padx=(12, 6), pady=10)

    # Priority selector
    priority_var = ctk.StringVar(value="normal")
    priority_opt = ctk.CTkOptionMenu(
        input_frame, values=["urgent", "normal", "chill"],
        variable=priority_var, width=90,
        button_color=accent, button_hover_color=accent_hover,
        fg_color=theme["frame"]
    )
    priority_opt.pack(side="left", padx=4, pady=10)

    # Category selector
    category_var = ctk.StringVar(value="work")
    category_opt = ctk.CTkOptionMenu(
        input_frame, values=["work", "study", "magic", "personal"],
        variable=category_var, width=90,
        button_color=accent, button_hover_color=accent_hover,
        fg_color=theme["frame"]
    )
    category_opt.pack(side="left", padx=4, pady=10)

    # ─ Tab categories ─
    tab_view = ctk.CTkTabview(win, fg_color=theme["frame"],
                               segmented_button_selected_color=accent,
                               segmented_button_selected_hover_color=accent_hover)
    tab_view.pack(fill="both", expand=True, padx=18, pady=6)

    cat_tabs = {
        "all": tab_view.add("📋 All"),
        "work": tab_view.add("💼 Work"),
        "study": tab_view.add("📖 Study"),
        "magic": tab_view.add("🪄 Magic"),
        "personal": tab_view.add("💖 Personal"),
    }

    scroll_frames = {}
    for cat_key, tab in cat_tabs.items():
        sf = ctk.CTkScrollableFrame(tab, fg_color=theme["bg"], label_text="")
        sf.pack(fill="both", expand=True)
        scroll_frames[cat_key] = sf

    def render_tasks():
        nonlocal total, done
        total = len(tasks)
        done = sum(1 for t in tasks if t.get("done"))
        progress_bar.set(done / total if total > 0 else 0)
        progress_lbl.configure(text=f"{done}/{total} spells cast  🪄")
        done_today_n = sum(1 for t in tasks if t.get("done_today"))
        stats_lbl.configure(text=f"✅ {done_today_n} done today")

        for sf in scroll_frames.values():
            for w in sf.winfo_children():
                w.destroy()

        priority_colors = {
            "urgent": "#ef4444",
            "normal": theme["accent"],
            "chill": "#4ade80",
        }
        priority_emojis = {
            "urgent": "🔴",
            "normal": "🟡",
            "chill": "🟢",
        }
        category_emojis = {
            "work": "💼",
            "study": "📖",
            "magic": "🪄",
            "personal": "💖",
        }

        for index, task in enumerate(tasks):
            cat = task.get("category", "work")
            prio = task.get("priority", "normal")
            for target_cat in ["all", cat]:
                sf = scroll_frames.get(target_cat)
                if not sf:
                    continue

                row = ctk.CTkFrame(sf, fg_color=theme["frame"], corner_radius=8)
                row.pack(fill="x", pady=3, padx=4)

                # Priority stripe
                stripe = ctk.CTkLabel(row, text=priority_emojis[prio], width=24,
                                       font=("Segoe UI", 13))
                stripe.pack(side="left", padx=(8, 4))

                cat_lbl = ctk.CTkLabel(row, text=category_emojis.get(cat, "📌"),
                                        width=24, font=("Segoe UI", 13))
                cat_lbl.pack(side="left", padx=(0, 4))

                def make_complete(idx=index):
                    return lambda: complete_task(idx)

                txt_color = "#6b7280" if task.get("done") else theme["text"]
                chk = ctk.CTkCheckBox(
                    row, text=task["text"],
                    font=("Segoe UI", 11),
                    text_color=txt_color,
                    command=make_complete(),
                    fg_color=priority_colors[prio],
                    hover_color=accent_hover,
                    width=20
                )
                if task.get("done"):
                    chk.select()
                chk.pack(side="left", padx=6, pady=8, fill="x", expand=True)

                # Due date label
                due = task.get("due", "")
                if due:
                    try:
                        due_dt = datetime.datetime.strptime(due, "%Y-%m-%d").date()
                        today = datetime.date.today()
                        overdue = due_dt < today and not task.get("done")
                        due_color = "#ef4444" if overdue else theme["text_dim"]
                        due_str = "OVERDUE!" if overdue else due_dt.strftime("%b %d")
                    except:
                        due_str = due
                        due_color = theme["text_dim"]
                    ctk.CTkLabel(row, text=due_str, font=("Segoe UI", 9),
                                  text_color=due_color).pack(side="left", padx=4)

                def make_delete(idx=index):
                    return lambda: delete_task(idx)

                ctk.CTkButton(
                    row, text="🗑", width=28, height=26,
                    fg_color=theme["danger"], hover_color=theme["danger_hover"],
                    command=make_delete()
                ).pack(side="right", padx=8, pady=6)

    def add_task():
        text = task_entry.get().strip()
        if text:
            tasks.append({
                "text": text,
                "done": False,
                "done_today": False,
                "priority": priority_var.get(),
                "category": category_var.get(),
                "due": "",
                "created": datetime.datetime.now().isoformat()
            })
            save_tasks()
            task_entry.delete(0, "end")
            render_tasks()
            pet.particles.add_sparks(pet.width / 2, pet.height / 2, count=6)

    def delete_task(idx):
        if 0 <= idx < len(tasks):
            tasks.pop(idx)
            save_tasks()
            render_tasks()

    def complete_task(idx):
        if 0 <= idx < len(tasks):
            tasks[idx]["done"] = True
            tasks[idx]["done_today"] = True
            save_tasks()
            render_tasks()
            # Trigger pet celebration
            pet.trigger_task_complete_celebration()
            win.after(500, lambda: delete_task(idx))

    add_btn = ctk.CTkButton(
        input_frame, text="➕ Add", fg_color=accent, hover_color=accent_hover,
        font=("Segoe UI", 11, "bold"), width=70, command=add_task
    )
    add_btn.pack(side="right", padx=(4, 12), pady=10)
    task_entry.bind("<Return>", lambda e: add_task())

    render_tasks()


# ═══════════════════════════════════════════════════════════
#  TIMER / POMODORO WINDOW
# ═══════════════════════════════════════════════════════════
def open_timer_window(pet):
    if _bring_to_front("timer"):
        return

    win = ctk.CTkToplevel(pet)
    _active_windows["timer"] = win
    win.title("☕ Chaa Break — Pomodoro Timer")
    win.geometry("420x500")
    win.resizable(False, False)
    win.attributes("-topmost", True)

    theme = get_gui_theme()
    accent = theme["accent"]
    accent_hover = theme["accent_hover"]

    # ─ Header ─
    ctk.CTkLabel(win, text="☕ Chaa Break Timer",
                  font=("Segoe UI", 18, "bold"), text_color=theme["gold"]).pack(pady=(18, 4))

    # ─ Mode toggle ─
    mode_frame = ctk.CTkFrame(win, fg_color=theme["frame"], corner_radius=10)
    mode_frame.pack(fill="x", padx=20, pady=8)

    pomodoro_mode = ctk.BooleanVar(value=False)

    pomo_btn = ctk.CTkButton(mode_frame, text="🍅 Pomodoro (25/5)", width=160, height=30,
                              fg_color=accent if pomodoro_mode.get() else theme["bg"],
                              hover_color=accent_hover, font=("Segoe UI", 10, "bold"))
    pomo_btn.pack(side="left", padx=12, pady=10)

    custom_btn = ctk.CTkButton(mode_frame, text="⏱ Custom Timer", width=140, height=30,
                                fg_color=accent if not pomodoro_mode.get() else theme["bg"],
                                hover_color=accent_hover, font=("Segoe UI", 10, "bold"))
    custom_btn.pack(side="left", padx=4, pady=10)

    # ─ Visual ring canvas ─
    ring_canvas = tk.Canvas(win, width=200, height=200, bg="#1a0a2e",
                             highlightthickness=0)
    ring_canvas.pack(pady=10)

    ring_arc_id = None
    ring_text_id = None
    ring_label_id = None

    def draw_ring(fraction, time_str, label_str=""):
        nonlocal ring_arc_id, ring_text_id, ring_label_id
        ring_canvas.delete("all")
        # Background circle
        ring_canvas.create_oval(20, 20, 180, 180, outline=theme["frame"], width=14)
        # Progress arc
        if fraction > 0:
            extent = -fraction * 359.9
            ring_canvas.create_arc(20, 20, 180, 180, start=90, extent=extent,
                                    outline=accent, width=14, style="arc")
        # Center text
        ring_canvas.create_text(100, 90, text=time_str, fill=theme["gold"],
                                  font=("Segoe UI", 28, "bold"))
        ring_canvas.create_text(100, 130, text=label_str, fill=theme["text_dim"],
                                  font=("Segoe UI", 11))

    draw_ring(1.0, "05:00", "Ready")

    # ─ Duration buttons ─
    dur_frame = ctk.CTkFrame(win, fg_color="transparent")
    dur_frame.pack(fill="x", padx=20, pady=4)

    durations = [1, 5, 10, 15, 25, 30]
    remaining_secs = [5 * 60]
    total_secs = [5 * 60]
    timer_job = [None]
    is_break = [False]
    pomo_count = [0]

    def set_duration(mins):
        remaining_secs[0] = mins * 60
        total_secs[0] = mins * 60
        draw_ring(1.0, f"{mins:02d}:00", "Ready")

    for d in durations:
        ctk.CTkButton(
            dur_frame, text=f"{d}m", width=52, height=28,
            fg_color=theme["frame"], hover_color=accent_hover,
            font=("Segoe UI", 10, "bold"),
            command=lambda v=d: set_duration(v)
        ).pack(side="left", expand=True, padx=2)

    # Custom input
    custom_frame = ctk.CTkFrame(win, fg_color="transparent")
    custom_frame.pack(pady=4)
    custom_entry = ctk.CTkEntry(custom_frame, width=70, placeholder_text="mins",
                                 font=("Segoe UI", 11))
    custom_entry.pack(side="left", padx=6)
    ctk.CTkButton(custom_frame, text="Set", width=50, height=28,
                   fg_color=theme["frame"], hover_color=accent_hover,
                   font=("Segoe UI", 10),
                   command=lambda: set_duration(int(custom_entry.get() or 5))
                   ).pack(side="left")

    set_duration(5)

    # ─ Pomodoro stats ─
    pomo_lbl = ctk.CTkLabel(win, text=f"🍅 Pomodoros completed: {config_db.get('pomodoro_count')}",
                             font=("Segoe UI", 11), text_color=theme["text_dim"])
    pomo_lbl.pack(pady=4)

    def alarm_fire():
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONHAND)
        except:
            pass

        if pomodoro_mode.get() and not is_break[0]:
            # Switch to break
            is_break[0] = True
            pomo_count[0] += 1
            total_pomo = config_db.get("pomodoro_count") + 1
            config_db.set("pomodoro_count", total_pomo)
            pomo_lbl.configure(text=f"🍅 Pomodoros completed: {total_pomo}")
            # Start 5-min break
            remaining_secs[0] = 5 * 60
            total_secs[0] = 5 * 60
            update_timer()
            # Pet reaction
            from app.config import get_speech_bubble, get_personality
            lang = pet.pet_config.get("language")
            pet.particles.add_fireworks_burst(pet.width / 2, pet.height / 2, count=20)
            pet.show_speech_bubble(get_speech_bubble("pomodoro_done", lang),
                                    color="#fde68a", duration=5000)
            # Break suggestion
            win.after(5000, lambda: pet.show_speech_bubble(
                get_speech_bubble("break_suggestion", lang), color="#bbf7d0", duration=5000
            ))
            control_btn.configure(text="⏸ Pause Break", fg_color=theme["danger"])
            return
        elif pomodoro_mode.get() and is_break[0]:
            is_break[0] = False
            draw_ring(1.0, "25:00", "Start when ready")
            control_btn.configure(text="▶ Start Brew", fg_color=accent)
            _show_alert(win, pet, theme, accent, accent_hover, break_over=True)
            return

        # Normal alarm
        pet.set_state("waving")
        pet.particles.add_sparks(pet.width / 2, pet.height / 2, count=30)
        from app.config import get_speech_bubble
        lang = pet.pet_config.get("language")
        pet.show_speech_bubble(get_speech_bubble("alarm", lang), color="#fde68a", duration=5000)
        control_btn.configure(text="▶ Start Brew", fg_color=accent)
        _show_alert(win, pet, theme, accent, accent_hover)

    def update_timer():
        if remaining_secs[0] > 0:
            remaining_secs[0] -= 1
            m = remaining_secs[0] // 60
            s = remaining_secs[0] % 60
            frac = remaining_secs[0] / total_secs[0] if total_secs[0] > 0 else 0
            label = "☕ Break!" if (pomodoro_mode.get() and is_break[0]) else "🍅 Focus!" if pomodoro_mode.get() else "⏱ Timer"
            draw_ring(frac, f"{m:02d}:{s:02d}", label)
            timer_job[0] = win.after(1000, update_timer)
        else:
            draw_ring(0.0, "00:00", "Done! 🎉")
            alarm_fire()

    def toggle_timer():
        if timer_job[0]:
            win.after_cancel(timer_job[0])
            timer_job[0] = None
            control_btn.configure(text="▶ Resume Brew", fg_color=accent)
        else:
            if remaining_secs[0] <= 0:
                if pomodoro_mode.get():
                    set_duration(25)
                else:
                    set_duration(5)
            control_btn.configure(text="⏸ Pause Brew", fg_color=theme["danger"])
            update_timer()

    def toggle_pomodoro():
        pomodoro_mode.set(not pomodoro_mode.get())
        if pomodoro_mode.get():
            pomo_btn.configure(fg_color=accent)
            custom_btn.configure(fg_color=theme["bg"])
            set_duration(25)
        else:
            pomo_btn.configure(fg_color=theme["bg"])
            custom_btn.configure(fg_color=accent)
            set_duration(5)
        if timer_job[0]:
            win.after_cancel(timer_job[0])
            timer_job[0] = None
            control_btn.configure(text="▶ Start Brew", fg_color=accent)

    pomo_btn.configure(command=toggle_pomodoro)
    custom_btn.configure(command=toggle_pomodoro)

    control_btn = ctk.CTkButton(
        win, text="▶ Start Brew", fg_color=accent, hover_color=accent_hover,
        font=("Segoe UI", 13, "bold"), command=toggle_timer
    )
    control_btn.pack(pady=14)

    def on_close():
        if timer_job[0]:
            win.after_cancel(timer_job[0])
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_close)


def _show_alert(win, pet, theme, accent, accent_hover, break_over=False):
    """Show a styled alert popup."""
    alert = ctk.CTkToplevel(win)
    alert.title("⏰ Chaa Break!" if not break_over else "💪 Back to Work!")
    alert.geometry("320x160")
    alert.resizable(False, False)
    alert.attributes("-topmost", True)

    msg = "☕ Time for a Chaa break!\nTake a short rest — you earned it!" if not break_over else "💪 Break is over!\nTime to get back to it!"
    ctk.CTkLabel(alert, text=msg, font=("Segoe UI", 12, "bold"),
                  justify="center", text_color=theme["text"]).pack(expand=True, pady=14)

    ctk.CTkButton(
        alert,
        text="Enjoy Tea ☕" if not break_over else "Let's go! 💪",
        fg_color=accent, hover_color=accent_hover,
        command=lambda: [alert.destroy(), pet.set_state("idle")]
    ).pack(pady=(0, 16))
