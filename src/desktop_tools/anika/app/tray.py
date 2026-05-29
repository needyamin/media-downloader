"""
tray.py — System tray icon for Anika using pystray.
Runs in a background thread. Provides Show/Hide/Quit.
"""
import threading
from PIL import Image, ImageDraw


def _make_tray_icon_image():
    """Generate a simple witch-hat icon for the system tray."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Hat brim (dark purple ellipse)
    brim_color = (90, 20, 160)
    draw.ellipse([4, 44, 60, 58], fill=brim_color)

    # Hat cone (dark purple triangle)
    hat_color = (70, 10, 130)
    cone_points = [(32, 4), (8, 46), (56, 46)]
    draw.polygon(cone_points, fill=hat_color)

    # Hat band (gold stripe)
    band_color = (255, 200, 0)
    draw.rectangle([10, 40, 54, 47], fill=band_color)

    # Star on hat
    star_color = (255, 220, 50)
    draw.ellipse([27, 18, 37, 28], fill=star_color)

    return img


class TrayIcon:
    def __init__(self, pet_ref_getter):
        """
        pet_ref_getter: callable that returns the DesktopPet instance
        (needed because the pet is created after the tray)
        """
        self._get_pet = pet_ref_getter
        self._icon = None
        self._thread = None
        self._visible = True

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            import pystray

            def on_show(icon, item):
                pet = self._get_pet()
                if pet:
                    pet.after(0, pet.deiconify)
                    pet.after(0, lambda: pet.wm_attributes("-topmost", True))
                self._visible = True

            def on_hide(icon, item):
                pet = self._get_pet()
                if pet:
                    pet.after(0, pet.withdraw)
                self._visible = False

            def on_settings(icon, item):
                pet = self._get_pet()
                if pet:
                    pet.after(0, pet.open_settings)

            def on_quit(icon, item):
                pet = self._get_pet()
                if pet:
                    pet.after(0, pet.quit_app)
                icon.stop()

            def on_double_click(icon):
                pet = self._get_pet()
                if pet:
                    if self._visible:
                        pet.after(0, pet.withdraw)
                        self._visible = False
                    else:
                        pet.after(0, pet.deiconify)
                        pet.after(0, lambda: pet.wm_attributes("-topmost", True))
                        self._visible = True

            menu = pystray.Menu(
                pystray.MenuItem("🧙‍♀️ Show Anika", on_show, default=True),
                pystray.MenuItem("🙈 Hide Anika", on_hide),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("⚙️ Settings", on_settings),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("👋 Quit", on_quit),
            )

            img = _make_tray_icon_image()
            self._icon = pystray.Icon(
                "Anika",
                img,
                "Anika — Bangladeshi Witch Desktop Assistant",
                menu=menu
            )
            self._icon.run()
        except ImportError:
            print("[Tray] pystray not installed — tray disabled")
        except Exception as e:
            print(f"[Tray] Error: {e}")

    def stop(self):
        if self._icon:
            try:
                self._icon.stop()
            except:
                pass
