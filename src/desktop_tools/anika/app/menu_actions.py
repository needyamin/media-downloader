"""Shared right-click menu actions for Anika (assistant window + settings GUI)."""

from __future__ import annotations

# (action_key, label)
PET_TOOL_ACTIONS: list[tuple[str, str]] = [
    ("spellbook", "🧙‍♀️ Spell Book (To-Do List)"),
    ("timer", "☕ Chaa Break (Timer)"),
    ("magic_clean", "🧹 Magic RAM Clean"),
]

PET_FORCE_ACTIONS: list[tuple[str, str]] = [
    ("action", "🪄 Cast a Spell"),
    ("sleeping", "💤 Go to Sleep"),
    ("dance", "💃 Cute Dance"),
    ("waving", "👋 Wave Hello"),
    ("crying", "😭 Cry"),
    ("eating", "🥪 Eat Sandwich"),
    ("study", "📖 Study Spells"),
    ("tea", "🍵 Sip Chaa (Tea)"),
    ("broom", "🧹 Broom Flight"),
    ("blush", "😊 Shy Blush"),
    ("laugh", "😂 Happy Laugh"),
    ("shocked", "😲 Feel Shocked"),
    ("peek", "👀 Peek From Edge"),
    ("focus", "🔍 Come into Focus"),
    ("chase", "🏃‍♀️ Chase Mouse"),
    ("hide", "🫣 Hide & Seek"),
]

PET_QUIT_ACTION: tuple[str, str] = ("quit", "👋 Goodbye Anika")


def run_pet_menu_action(pet, action_key: str) -> None:
    """Run a menu action by key (same behavior as the pet context menu)."""
    if action_key == "spellbook":
        pet.open_spellbook()
        return
    if action_key == "timer":
        pet.open_timer()
        return
    if action_key == "magic_clean":
        pet.trigger_magic_clean()
        return
    if action_key == "quit":
        pet.quit_app()
        return
    pet.set_state(action_key)


def populate_tk_context_menu(menu, pet) -> None:
    """Fill a tk.Menu with the same entries as the pet right-click menu."""
    import tkinter as tk

    for _key, label in PET_TOOL_ACTIONS:
        menu.add_command(label=label, command=lambda k=_key: run_pet_menu_action(pet, k))

    menu.add_separator()
    menu.add_command(label="⚙️ Assistant Settings", command=pet.open_settings)

    actions_menu = tk.Menu(menu, tearoff=0)
    for _key, label in PET_FORCE_ACTIONS:
        actions_menu.add_command(
            label=label,
            command=lambda k=_key: run_pet_menu_action(pet, k),
        )
    menu.add_cascade(label="🎭 Force Action", menu=actions_menu)

    menu.add_separator()
    _quit_key, quit_label = PET_QUIT_ACTION
    menu.add_command(label=quit_label, command=lambda: run_pet_menu_action(pet, _quit_key))
