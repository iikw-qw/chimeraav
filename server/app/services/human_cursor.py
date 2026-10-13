"""
Человекоподобный курсор: дуга по перпендикуляру + зигзаг-синусоида
+ хаотичный тремор + overshoot. Seed меняется каждый вызов.
"""

import hashlib
import math
import random
import subprocess
import time
from typing import List, Tuple


class HumanCursor:
    def __init__(self, serial: str, w: int = 1080, h: int = 2400):
        self.serial = serial
        self.w, self.h = w, h
        self.cx, self.cy = w // 2, h // 2
        self._seed = int(hashlib.md5(serial.encode()).hexdigest()[:8], 16)

    def tap(self, x: int, y: int):
        path = self._path(self.cx, self.cy, x, y)
        for i in range(0, len(path) - 1, 2):
            p1 = path[i]
            p2 = path[min(i + 2, len(path) - 1)]
            d = random.randint(6, 16)
            self._sh(f"input swipe {p1[0]} {p1[1]} {p2[0]} {p2[1]} {d}")
        time.sleep(random.uniform(0.06, 0.2))
        self._sh(f"input tap {x + random.randint(-2, 2)} {y + random.randint(-2, 2)}")
        self.cx, self.cy = x, y

    def swipe(self, x1: int, y1: int, x2: int, y2: int, intensity: str = "medium"):
        durations = {"soft": (400, 700), "medium": (200, 400), "hard": (80, 200)}
        dur = random.randint(*durations.get(intensity, (200, 400)))
        self._sh(
            f"input swipe {x1} {y1} "
            f"{x2 + random.randint(-8, 8)} {y2 + random.randint(-8, 8)} {dur}"
        )

    def scroll_feed(self, intensity: str = "medium"):
        mult = {"soft": 0.3, "medium": 0.5, "hard": 0.7}.get(intensity, 0.5)
        sx = self.w // 2 + random.randint(-50, 50)
        sy = int(self.h * (0.6 + random.uniform(0, 0.15)))
        ey = int(self.h * (0.6 - mult) + random.randint(-40, 40))
        dur = random.randint(150, 400)
        self._sh(f"input swipe {sx} {sy} {sx + random.randint(-12, 12)} {ey} {dur}")

    def type_text(self, text: str):
        for i, c in enumerate(text):
            if random.random() < 0.06 and i > 2 and c.isalpha():
                wrong = chr(ord(c) + random.choice([-1, 1]))
                self._sh(f"input text '{wrong}'")
                time.sleep(random.uniform(0.12, 0.25))
                self._sh("input keyevent 67")
                time.sleep(random.uniform(0.06, 0.12))
            if c == " ":
                self._sh("input keyevent 62")
                time.sleep(random.uniform(0.12, 0.25))
            else:
                esc = c.replace("'", "'\\''").replace("&", "\\&").replace(";", "\\;")
                self._sh(f"input text '{esc}'")
                time.sleep(max(0.03, random.gauss(0.07, 0.02)))

    def _path(self, x0: int, y0: int, x3: int, y3: int, n: int = 16) -> List[Tuple[int, int]]:
        self._seed = (self._seed * 1103515245 + 12345) & 0x7FFFFFFF
        rng = random.Random(self._seed)

        dx, dy = x3 - x0, y3 - y0
        dist = math.sqrt(dx * dx + dy * dy) + 1

        perp_x, perp_y = -dy / dist, dx / dist
        arc_strength = rng.uniform(15, 50) * rng.choice([-1, 1])

        cp1x = x0 + dx * 0.3 + perp_x * arc_strength + rng.gauss(0, 8)
        cp1y = y0 + dy * 0.3 + perp_y * arc_strength + rng.gauss(0, 8)
        cp2x = x0 + dx * 0.7 + perp_x * arc_strength * 0.5 + rng.gauss(0, 8)
        cp2y = y0 + dy * 0.7 + perp_y * arc_strength * 0.5 + rng.gauss(0, 8)

        angle = math.atan2(dy, dx)
        ov = rng.uniform(2, 7)
        ox, oy = x3 + ov * math.cos(angle), y3 + ov * math.sin(angle)

        pts: List[Tuple[int, int]] = []
        for i in range(n):
            t = i / (n - 1)
            t_ease = t * t * (3 - 2 * t)

            if t_ease < 0.85:
                s = t_ease / 0.85
                bx = (1 - s) ** 3 * x0 + 3 * (1 - s) ** 2 * s * cp1x + 3 * (1 - s) * s ** 2 * cp2x + s ** 3 * ox
                by = (1 - s) ** 3 * y0 + 3 * (1 - s) ** 2 * s * cp1y + 3 * (1 - s) * s ** 2 * cp2y + s ** 3 * oy
            else:
                s = (t_ease - 0.85) / 0.15
                bx = ox + (x3 - ox) * s
                by = oy + (y3 - oy) * s

            zigzag_amp = rng.uniform(1, 4) * (1 - t)
            zigzag_freq = rng.uniform(3, 7)
            bx += perp_x * zigzag_amp * math.sin(zigzag_freq * t * math.pi)
            by += perp_y * zigzag_amp * math.sin(zigzag_freq * t * math.pi)

            tremor = 0.3 + 1.5 * t
            bx += rng.gauss(0, tremor)
            by += rng.gauss(0, tremor)

            pts.append((int(bx), int(by)))
        return pts

    def _sh(self, cmd: str):
        subprocess.run(
            ["adb", "-s", self.serial, "shell", cmd],
            capture_output=True, timeout=10,
        )
