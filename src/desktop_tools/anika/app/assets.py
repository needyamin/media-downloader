import os
from PIL import Image, ImageTk
from app.config import RESOURCES_DIR

# Rendered sprite height at scale 1.0 (must match layout in pet.py)
BASE_SPRITE_HEIGHT = 220


class AssetManager:
    def __init__(self):
        self.raw_images = {}
        self.scaled_images = {}
        self.tk_images = {}
        self.current_scale = 0.8
        self.load_all()

    def load_all(self):
        # Load processed transparent images from resources folder
        self.image_files = {
            "idle": "idle.png",
            "dragged": "dragged.png",
            "action": "action.png",
            "sleeping": "sleeping.png",
            "happy": "happy.png",
            "study": "study.png",
            "tea": "tea.png",
            "broom": "broom.png",
            "blush": "blush.png",
            "laugh": "laugh.png",
            "shocked": "shocked.png",
            "peek": "peek.png",
            "focus": "focus.png",
            "waving": "waving.png",
            "crying": "crying.png",
            "eating": "eating.png"
        }
        


        # Legacy full-frame walk images (used as animated alternating frames)
        self.image_files["walk1"] = "walk1.png"
        self.image_files["walk2"] = "walk2.png"
            
        # Load sliced dancing cycle frames
        for i in range(4):
            self.image_files[f"dance_{i}"] = f"dance_{i}.png"

        # Static dance pose (used as opening frame before cycle begins)
        self.image_files["dance_static"] = "dance.png"
        
        for key, filename in self.image_files.items():
            path = os.path.join(RESOURCES_DIR, filename)
            if os.path.exists(path):
                try:
                    self.raw_images[key] = Image.open(path)
                    print(f"Loaded asset: {key} ({self.raw_images[key].size})")
                except Exception as e:
                    print(f"Error loading asset {key} from {path}: {e}")
            else:
                print(f"Warning: Asset file not found: {path}")

    def get_image(self, key, scale=0.8, flip_horizontal=False, squash_x=1.0, squash_y=1.0):
        # Round squash to 1 decimal place to prevent cache bloat
        sx = round(squash_x, 1)
        sy = round(squash_y, 1)
        
        # Cache key based on state, scale, direction, and squash
        cache_key = (key, scale, flip_horizontal, sx, sy)
        if cache_key in self.tk_images:
            return self.tk_images[cache_key]

        # Load raw image
        raw_img = self.raw_images.get(key)
        if not raw_img:
            # Return placeholder or first available
            if self.raw_images:
                raw_img = list(self.raw_images.values())[0]
            else:
                return None

        # Calculate new size (base size is around 180px height)
        # We preserve aspect ratio
        w, h = raw_img.size
        aspect = w / h
        
        base_height = BASE_SPRITE_HEIGHT
        target_height = int(base_height * scale * sy)
        target_width = int(base_height * scale * aspect * sx)
        
        # Avoid zero dimensions
        target_width = max(10, target_width)
        target_height = max(10, target_height)

        # Scale image
        scaled_img = raw_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # Threshold the alpha channel to 1-bit (0 or 255) to prevent semi-transparency.
        # This is critical in Tkinter on Windows because any pixel with alpha 1-254
        # is blended with the window trans_color, causing dark/noisy edge halos.
        if scaled_img.mode == "RGBA":
            r, g, b, a = scaled_img.split()
            # Threshold at 128: alpha >= 128 becomes 255, < 128 becomes 0
            a = a.point(lambda p: 255 if p >= 128 else 0)
            scaled_img = Image.merge("RGBA", (r, g, b, a))
            
        # Flip when facing right (sprites face left in source art)
        if flip_horizontal:
            scaled_img = scaled_img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

        # Convert to Tkinter PhotoImage
        tk_img = ImageTk.PhotoImage(scaled_img)
        self.tk_images[cache_key] = tk_img
        
        return tk_img

    def clear_cache(self):
        self.tk_images.clear()
