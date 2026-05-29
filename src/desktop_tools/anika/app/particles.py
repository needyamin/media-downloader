import random
import math


class Particle:
    def __init__(self, canvas, x, y, vx, vy, color, size, shape_type="circle", text="", max_life=30, alpha_decay=True):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.size = size
        self.shape_type = shape_type
        self.text = text
        self.life = max_life
        self.max_life = max_life
        self.alpha_decay = alpha_decay
        self.rotation = random.uniform(0, 360)
        self.rot_speed = random.uniform(-5, 5)
        self.is_rain = False  # explicit flag instead of colour check

        # Create canvas item
        self.canvas_id = None
        self.create_item()

    def create_item(self):
        hs = self.size / 2
        if self.shape_type == "circle":
            self.canvas_id = self.canvas.create_oval(
                self.x - hs, self.y - hs, self.x + hs, self.y + hs,
                fill=self.color, outline=""
            )
        elif self.shape_type == "rectangle":
            self.canvas_id = self.canvas.create_rectangle(
                self.x - hs, self.y - hs, self.x + hs, self.y + hs,
                fill=self.color, outline=""
            )
        elif self.shape_type in ["text", "heart", "zzz"]:
            if self.shape_type == "heart":
                disp_text = "♥"
            elif self.shape_type == "zzz":
                disp_text = self.text or "Zzz"
            else:
                disp_text = self.text
            font_size = max(6, int(self.size))
            self.canvas_id = self.canvas.create_text(
                self.x, self.y, text=disp_text, fill=self.color,
                font=("Segoe UI", font_size, "bold")
            )
        elif self.shape_type == "star":
            self._draw_star(self.size)
        elif self.shape_type == "fairy":
            # Tiny glowing dot with bright color
            self.canvas_id = self.canvas.create_oval(
                self.x - hs, self.y - hs, self.x + hs, self.y + hs,
                fill=self.color, outline=self._brighten(self.color), width=1
            )
        elif self.shape_type == "lightning":
            # Simple zigzag line segment
            pts = self._lightning_pts(self.x, self.y, self.size)
            self.canvas_id = self.canvas.create_line(
                *pts, fill=self.color, width=2
            )
        elif self.shape_type == "ribbon":
            # Small oval for ribbon/rainbow
            self.canvas_id = self.canvas.create_oval(
                self.x - hs * 2, self.y - hs * 0.5,
                self.x + hs * 2, self.y + hs * 0.5,
                fill=self.color, outline=""
            )
        elif self.shape_type == "firework":
            self._draw_star(self.size)
        elif self.shape_type == "magic_dot":
            # Glowing small circle for magic trail
            self.canvas_id = self.canvas.create_oval(
                self.x - hs, self.y - hs, self.x + hs, self.y + hs,
                fill=self.color, outline=""
            )

    def _draw_star(self, size):
        hs = size / 2
        points = [
            self.x, self.y - size,
            self.x + hs / 2, self.y - hs / 2,
            self.x + size, self.y,
            self.x + hs / 2, self.y + hs / 2,
            self.x, self.y + size,
            self.x - hs / 2, self.y + hs / 2,
            self.x - size, self.y,
            self.x - hs / 2, self.y - hs / 2
        ]
        self.canvas_id = self.canvas.create_polygon(points, fill=self.color, outline="")

    def _lightning_pts(self, x, y, size):
        return [x, y - size, x + size * 0.4, y, x, y + size]

    def _brighten(self, hex_color):
        """Returns a slightly brighter version of a hex color."""
        try:
            r = min(255, int(hex_color[1:3], 16) + 60)
            g = min(255, int(hex_color[3:5], 16) + 60)
            b = min(255, int(hex_color[5:7], 16) + 60)
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return hex_color

    def update(self):
        # Move
        self.x += self.vx
        self.y += self.vy
        self.rotation += self.rot_speed

        # Physics per shape type
        if self.shape_type in ["heart", "zzz", "text"]:
            self.vy -= 0.05   # Float upward
            self.vx += math.sin(self.life * 0.2) * 0.08
        elif self.is_rain:
            self.vy += 0.2   # Rain falls
        elif self.shape_type == "fairy":
            self.vx += math.sin(self.life * 0.3) * 0.12
            self.vy -= 0.03   # Slowly float up
        elif self.shape_type in ["firework", "star"]:
            self.vy += 0.12   # Light gravity
            self.vx *= 0.98   # Friction
        elif self.shape_type == "magic_dot":
            self.vy -= 0.02   # Slowly rise
            self.vx *= 0.97
        elif self.shape_type == "ribbon":
            self.vy -= 0.04
            self.vx *= 0.98
        elif self.shape_type == "lightning":
            pass   # Lightning doesn't move, just fades

        self.life -= 1

        # Update on canvas
        if self.canvas_id:
            ratio = max(0.01, self.life / self.max_life)
            curr_size = max(1, self.size * ratio)
            hs = curr_size / 2

            if self.shape_type in ["circle", "fairy", "magic_dot"]:
                self.canvas.coords(self.canvas_id, self.x - hs, self.y - hs, self.x + hs, self.y + hs)
            elif self.shape_type == "rectangle":
                self.canvas.coords(self.canvas_id, self.x - hs, self.y - hs, self.x + hs, self.y + hs)
            elif self.shape_type in ["text", "heart", "zzz"]:
                self.canvas.coords(self.canvas_id, self.x, self.y)
                font_size = max(6, int(curr_size))
                self.canvas.itemconfig(self.canvas_id, font=("Segoe UI", font_size, "bold"))
            elif self.shape_type in ["star", "firework"]:
                points = [
                    self.x, self.y - curr_size,
                    self.x + hs / 2, self.y - hs / 2,
                    self.x + curr_size, self.y,
                    self.x + hs / 2, self.y + hs / 2,
                    self.x, self.y + curr_size,
                    self.x - hs / 2, self.y + hs / 2,
                    self.x - curr_size, self.y,
                    self.x - hs / 2, self.y - hs / 2
                ]
                self.canvas.coords(self.canvas_id, *points)
            elif self.shape_type == "ribbon":
                self.canvas.coords(
                    self.canvas_id,
                    self.x - hs * 2, self.y - hs * 0.5,
                    self.x + hs * 2, self.y + hs * 0.5
                )
            elif self.shape_type == "lightning":
                pts = self._lightning_pts(self.x, self.y, curr_size)
                self.canvas.coords(self.canvas_id, *pts)

    def destroy(self):
        if self.canvas_id:
            try:
                self.canvas.delete(self.canvas_id)
            except:
                pass
            self.canvas_id = None


class ParticleSystem:
    def __init__(self, canvas):
        self.canvas = canvas
        self.particles = []

    # ─── Core Effects ──────────────────────────────────────────────
    def add_sparks(self, x, y, count=10):
        """Magical star/polygon sparks shooting outward."""
        colors = ["#ffd700", "#ff69b4", "#ff8c00", "#00ffff", "#ee82ee", "#a855f7", "#f43f5e"]
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(2, 6)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            color = random.choice(colors)
            size = random.uniform(8, 18)
            life = random.randint(15, 35)
            self.particles.append(Particle(
                self.canvas, x, y, vx, vy, color, size, "star", max_life=life
            ))

    def add_hearts(self, x, y, count=3):
        """Floating hearts."""
        colors = ["#ff4b4b", "#ff7b7b", "#ff1493", "#ff69b4", "#fb7185"]
        for _ in range(count):
            vx = random.uniform(-1.2, 1.2)
            vy = random.uniform(-2.2, -0.6)
            color = random.choice(colors)
            size = random.uniform(14, 24)
            life = random.randint(30, 50)
            self.particles.append(Particle(
                self.canvas, x, y, vx, vy, color, size, "heart", max_life=life
            ))

    def add_sleep_zzz(self, x, y):
        """Floating Zzz text."""
        vx = random.uniform(0.5, 1.5)
        vy = random.uniform(-1.5, -0.5)
        color = "#e6e6fa"
        size = random.uniform(10, 18)
        life = random.randint(40, 65)
        self.particles.append(Particle(
            self.canvas, x, y, vx, vy, color, size, "zzz", text="Zzz", max_life=life
        ))

    def add_dizzy_stars(self, x, y, count=1):
        """Orbiting dizzy stars."""
        angle = random.uniform(0, 2 * math.pi)
        vx = math.cos(angle) * 1.5
        vy = -random.uniform(0.5, 1.5)
        color = "#ffff33"
        size = random.uniform(6, 12)
        life = random.randint(15, 25)
        self.particles.append(Particle(
            self.canvas, x, y, vx, vy, color, size, "star", max_life=life
        ))

    def add_weather_rain(self, width, count=2):
        """Falling rain at the top."""
        for _ in range(count):
            x = random.uniform(0, width)
            y = 0
            vx = random.uniform(-0.5, 0.5)
            vy = random.uniform(4, 7)
            color = "#87ceeb"
            size = random.uniform(4, 8)
            life = random.randint(30, 50)
            p = Particle(
                self.canvas, x, y, vx, vy, color, size, "rectangle", max_life=life
            )
            p.is_rain = True
            self.particles.append(p)

    def add_weather_snow(self, width, count=1):
        """Falling snowflakes."""
        for _ in range(count):
            x = random.uniform(0, width)
            y = 0
            vx = random.uniform(-1, 1)
            vy = random.uniform(1, 2.5)
            color = "#ffffff"
            size = random.uniform(4, 10)
            life = random.randint(60, 100)
            self.particles.append(Particle(
                self.canvas, x, y, vx, vy, color, size, "circle", max_life=life
            ))

    def add_weather_sunny(self, width, count=1):
        """Sunny sparkle motes drifting upward."""
        for _ in range(count):
            x = random.uniform(0, width)
            y = random.uniform(0, 100)
            vx = random.uniform(-0.5, 0.5)
            vy = random.uniform(-0.5, -0.2)
            colors = ["#fde68a", "#fcd34d", "#fbbf24", "#fffbeb"]
            color = random.choice(colors)
            size = random.uniform(3, 7)
            life = random.randint(40, 80)
            self.particles.append(Particle(
                self.canvas, x, y, vx, vy, color, size, "circle", max_life=life
            ))

    # ─── Advanced Effects ───────────────────────────────────────────
    def add_fairy_dust(self, x, y, count=2):
        """Tiny glowing fairy-dust motes around the hat during idle."""
        colors = ["#c084fc", "#e879f9", "#f0abfc", "#fde68a", "#a5f3fc", "#6ee7b7"]
        for _ in range(count):
            ox = random.uniform(-30, 30)
            oy = random.uniform(-50, 10)
            vx = random.uniform(-0.6, 0.6)
            vy = random.uniform(-1.2, -0.3)
            color = random.choice(colors)
            size = random.uniform(3, 6)
            life = random.randint(25, 45)
            self.particles.append(Particle(
                self.canvas, x + ox, y + oy, vx, vy, color, size, "fairy", max_life=life
            ))

    def add_magic_trail(self, x, y):
        """Short fading trail particle for walking/flying."""
        colors = ["#c084fc", "#818cf8", "#38bdf8", "#4ade80"]
        color = random.choice(colors)
        size = random.uniform(4, 9)
        vx = random.uniform(-0.3, 0.3)
        vy = random.uniform(-0.5, 0.2)
        life = random.randint(8, 18)
        self.particles.append(Particle(
            self.canvas, x, y, vx, vy, color, size, "magic_dot", max_life=life
        ))

    def add_fireworks_burst(self, x, y, count=30):
        """Celebration fireworks for task completion."""
        color_sets = [
            ["#ffd700", "#ff8c00", "#ff4500"],
            ["#00ff7f", "#00fa9a", "#98fb98"],
            ["#ff69b4", "#ff1493", "#db7093"],
            ["#00bfff", "#87ceeb", "#4169e1"],
            ["#da70d6", "#ee82ee", "#dda0dd"],
        ]
        chosen = random.choice(color_sets)
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(3, 9)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            color = random.choice(chosen)
            size = random.uniform(6, 14)
            life = random.randint(25, 50)
            self.particles.append(Particle(
                self.canvas, x, y, vx, vy, color, size, "firework", max_life=life
            ))

    def add_rainbow_ribbon(self, x, y, count=6):
        """Rainbow arc ribbon during dance."""
        rainbow = ["#ff0000", "#ff7700", "#ffff00", "#00ff00", "#0077ff", "#8800ff"]
        for i, color in enumerate(rainbow):
            ox = (i - 3) * 10
            vx = random.uniform(-0.8, 0.8)
            vy = random.uniform(-2.5, -1.0)
            size = random.uniform(8, 14)
            life = random.randint(20, 35)
            self.particles.append(Particle(
                self.canvas, x + ox, y, vx, vy, color, size, "ribbon", max_life=life
            ))

    def add_lightning_bolt(self, x, y, count=3):
        """Short lightning bolt particles for annoyance reaction."""
        for _ in range(count):
            ox = random.uniform(-20, 20)
            oy = random.uniform(-30, 10)
            vx = random.uniform(-1, 1)
            vy = random.uniform(-2, -0.5)
            color = random.choice(["#fef08a", "#fde047", "#facc15", "#ffffff"])
            size = random.uniform(10, 20)
            life = random.randint(8, 16)
            self.particles.append(Particle(
                self.canvas, x + ox, y + oy, vx, vy, color, size, "lightning", max_life=life
            ))

    def add_teardrops(self, x, y, count=3):
        """Teardrop particles falling from crying Anika."""
        for _ in range(count):
            ox = random.uniform(-20, 20)
            oy = random.uniform(-30, 10)
            vx = random.uniform(-0.4, 0.4)
            vy = random.uniform(2, 5)
            color = random.choice(["#93c5fd", "#bfdbfe", "#dbeafe", "#a5f3fc"])
            size = random.uniform(5, 10)
            life = random.randint(25, 45)
            p = Particle(
                self.canvas, x + ox, y + oy, vx, vy, color, size, "circle", max_life=life
            )
            p.is_rain = True
            self.particles.append(p)

    def add_magic_circle_sparkles(self, x, y, radius=40, count=8):
        """Sparks orbiting in a circle (for magic circle effect)."""
        colors = ["#c084fc", "#e879f9", "#818cf8", "#fbbf24"]
        for i in range(count):
            angle = (2 * math.pi / count) * i + random.uniform(-0.3, 0.3)
            px = x + math.cos(angle) * radius
            py = y + math.sin(angle) * radius
            vx = math.cos(angle + math.pi / 2) * 1.5
            vy = math.sin(angle + math.pi / 2) * 1.5
            color = random.choice(colors)
            size = random.uniform(4, 9)
            life = random.randint(20, 35)
            self.particles.append(Particle(
                self.canvas, px, py, vx, vy, color, size, "fairy", max_life=life
            ))

    # ─── Update & Clear ─────────────────────────────────────────────
    def update(self):
        remaining = []
        for p in self.particles:
            p.update()
            if p.life > 0:
                remaining.append(p)
            else:
                p.destroy()
        self.particles = remaining

    def clear(self):
        for p in self.particles:
            p.destroy()
        self.particles = []

    def count(self):
        return len(self.particles)
