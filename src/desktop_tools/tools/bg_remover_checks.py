"""Smoke and logic checks for the background remover engine and UI."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from PIL import Image, ImageDraw


def _ensure_src_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def check_model_tiers() -> None:
    from desktop_tools.app.ui.background_remover_app import (
        CLASSIC_REMBG_MODELS,
        DEFAULT_REMBG_MODEL,
        PREMIUM_REMBG_MODELS,
        REMBG_LABEL_TO_MODEL_KEY,
        REMBG_MODEL_MENU_LABELS,
        REMBG_MODEL_MENU_ORDER,
        _fallback_models_for,
        describe_model_choice,
        is_premium_rembg_model,
        is_rembg_model_cached,
        model_ready_message,
        resolve_model_key,
    )

    assert DEFAULT_REMBG_MODEL == "u2net"
    assert is_premium_rembg_model("birefnet-general")
    assert not is_premium_rembg_model("u2net")
    assert CLASSIC_REMBG_MODELS.isdisjoint(PREMIUM_REMBG_MODELS)

    classic_chain = _fallback_models_for("u2net")
    assert "u2net" in classic_chain
    assert "birefnet-general" not in classic_chain

    premium_chain = _fallback_models_for("birefnet-general")
    assert "birefnet-general" in premium_chain
    assert "u2net" not in premium_chain

    label = REMBG_MODEL_MENU_LABELS["u2net"]
    assert resolve_model_key(label) == "u2net"
    assert resolve_model_key("u2net") == "u2net"
    assert len(REMBG_MODEL_MENU_ORDER) >= 4
    assert len(REMBG_LABEL_TO_MODEL_KEY) == len(REMBG_MODEL_MENU_LABELS)
    if is_rembg_model_cached("u2net"):
        assert "already downloaded" in describe_model_choice("u2net").lower()
        assert "already downloaded" in model_ready_message("u2net").lower()
    print("OK bg_remover: model tiers and fallback chains")


def check_ui_builds() -> None:
    import tkinter as tk

    from desktop_tools.app.ui.background_remover_app import BackgroundRemoverApp

    root = tk.Tk()
    root.withdraw()
    try:
        window = tk.Toplevel(root)
        app = BackgroundRemoverApp(window)
        root.update()
        assert app._resolve_model_key() == "u2net"
        assert "classic" in app.model_hint_var.get().lower() or "Classic" in app.model_hint_var.get()
        window.destroy()
    finally:
        root.destroy()
    print("OK bg_remover: UI builds with classic default")


def check_classic_removal() -> None:
    from desktop_tools.app.ui.background_remover_app import (
        REMBG_AVAILABLE,
        remove_image_background,
    )

    if not REMBG_AVAILABLE:
        print("SKIP bg_remover: rembg not installed")
        return

    image = Image.new("RGB", (96, 96), (120, 180, 200))
    draw = ImageDraw.Draw(image)
    draw.ellipse((24, 24, 72, 72), fill=(210, 70, 50))

    output = remove_image_background(
        image,
        model_name="u2net",
        alpha_matting=False,
        allow_model_download=True,
    )
    assert output.mode == "RGBA"
    assert output.size == (96, 96)
    assert output.getbbox() is not None
    print("OK bg_remover: classic u2net inference")


def check_premium_blocked_without_consent() -> None:
    from desktop_tools.app.ui.background_remover_app import (
        REMBG_AVAILABLE,
        is_rembg_model_cached,
        remove_image_background,
    )

    if not REMBG_AVAILABLE:
        print("SKIP bg_remover: premium consent check (no rembg)")
        return

    if is_rembg_model_cached("birefnet-general"):
        print("SKIP bg_remover: premium consent check (birefnet already cached)")
        return

    image = Image.new("RGB", (32, 32), (200, 100, 50))
    try:
        remove_image_background(
            image,
            model_name="birefnet-general",
            alpha_matting=False,
            allow_model_download=False,
        )
        raise AssertionError("Expected premium model without consent to fail")
    except RuntimeError as exc:
        message = str(exc).lower()
        assert "not installed" in message or "confirm" in message
    print("OK bg_remover: premium download blocked without consent")


def check_ui_thread_queue() -> None:
    import tkinter as tk

    from desktop_tools.app.ui.background_remover_app import BackgroundRemoverApp

    root = tk.Tk()
    try:
        app = BackgroundRemoverApp(root)
        seen: list[str] = []

        def worker():
            app._run_on_ui_thread(lambda: seen.append("ok"))

        threading.Thread(target=worker, daemon=True).start()
        for _ in range(40):
            root.update()
            if seen:
                break
            time.sleep(0.05)
        assert seen == ["ok"], f"UI queue did not run callback: {seen}"
    finally:
        root.destroy()
    print("OK bg_remover: main-thread UI queue")


def main() -> None:
    _ensure_src_on_path()
    check_model_tiers()
    check_premium_blocked_without_consent()
    check_ui_builds()
    check_ui_thread_queue()
    check_classic_removal()
    print("Background remover checks passed.")


if __name__ == "__main__":
    main()
