"""Human-like cursor/finger movement for touchscreen automation."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


@dataclass
class CursorPoint:
    x: int
    y: int
    delay_ms: int


@dataclass
class TapResult:
    path: list[CursorPoint]
    pre_tap_pause: int
    hold: list[CursorPoint]


@dataclass
class TypeAction:
    action: str  # "type" or "backspace"
    char: str = ""
    delay_ms: int = 100


class HumanCursor:
    """Simulates human finger movement on a touchscreen."""

    def __init__(self, screen_width: int = 1080, screen_height: int = 2340) -> None:
        self.w = screen_width
        self.h = screen_height
        self.current_x = screen_width // 2
        self.current_y = screen_height // 2

    def move_to(self, target_x: int, target_y: int) -> list[CursorPoint]:
        distance = math.sqrt(
            (target_x - self.current_x) ** 2 + (target_y - self.current_y) ** 2
        )
        duration_ms = int(200 + distance * 0.5 + random.gauss(0, 50))
        duration_ms = max(150, min(800, duration_ms))
        num_points = max(10, duration_ms // 16)

        cp1_x = self.current_x + (target_x - self.current_x) * 0.3 + random.gauss(0, 15)
        cp1_y = self.current_y + (target_y - self.current_y) * 0.3 + random.gauss(0, 15)
        cp2_x = self.current_x + (target_x - self.current_x) * 0.7 + random.gauss(0, 15)
        cp2_y = self.current_y + (target_y - self.current_y) * 0.7 + random.gauss(0, 15)

        overshoot_px = random.uniform(2, 7)
        angle = math.atan2(target_y - self.current_y, target_x - self.current_x)
        overshoot_x = target_x + overshoot_px * math.cos(angle)
        overshoot_y = target_y + overshoot_px * math.sin(angle)

        path: list[CursorPoint] = []
        for i in range(num_points):
            t = i / (num_points - 1)
            t_ease = t * t * (3 - 2 * t)

            if t_ease < 0.85:
                t_local = t_ease / 0.85
                x = self._cubic_bezier(t_local, self.current_x, cp1_x, cp2_x, overshoot_x)
                y = self._cubic_bezier(t_local, self.current_y, cp1_y, cp2_y, overshoot_y)
            else:
                t_local = (t_ease - 0.85) / 0.15
                x = overshoot_x + (target_x - overshoot_x) * t_local
                y = overshoot_y + (target_y - overshoot_y) * t_local

            tremor_amplitude = 0.5 + 1.5 * t
            tremor_freq = random.uniform(8, 12)
            x += tremor_amplitude * math.sin(2 * math.pi * tremor_freq * t)
            y += tremor_amplitude * math.cos(2 * math.pi * tremor_freq * t * 1.3)

            delay = duration_ms // num_points + random.randint(-2, 2)
            path.append(CursorPoint(int(x), int(y), max(1, delay)))

        self.current_x = target_x
        self.current_y = target_y
        return path

    def tap(self, x: int, y: int) -> TapResult:
        path = self.move_to(x, y)
        pre_tap_pause = random.randint(80, 250)
        hold_duration = random.randint(50, 150)
        hold_tremor = [
            CursorPoint(
                int(x + random.gauss(0, 1.2)),
                int(y + random.gauss(0, 1.2)),
                16,
            )
            for _ in range(hold_duration // 16)
        ]
        return TapResult(path=path, pre_tap_pause=pre_tap_pause, hold=hold_tremor)

    def swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        speed: str = "medium",
    ) -> list[CursorPoint]:
        speeds = {"slow": (600, 1000), "medium": (300, 600), "fast": (150, 300)}
        lo, hi = speeds.get(speed, (300, 600))
        duration_ms = random.randint(lo, hi)
        num_points = max(15, duration_ms // 16)
        path: list[CursorPoint] = []
        for i in range(num_points):
            t = i / (num_points - 1)
            t_ease = 1 - (1 - t) * (1 - t)
            x = start_x + (end_x - start_x) * t_ease + random.gauss(0, 4)
            y = start_y + (end_y - start_y) * t_ease + random.gauss(0, 2)
            path.append(CursorPoint(int(x), int(y), duration_ms // num_points))
        return path

    def type_text(self, text: str) -> list[TypeAction]:
        actions: list[TypeAction] = []
        for i, char in enumerate(text):
            if random.random() < 0.067 and i > 0:
                wrong_char = chr(ord(char) + random.choice([-1, 1]))
                actions.append(TypeAction("type", wrong_char, int(random.gauss(100, 30))))
                actions.append(TypeAction("backspace", "", random.randint(100, 250)))

            delay = int(random.gauss(70, 20))
            if char == " ":
                delay = random.randint(150, 300)
            actions.append(TypeAction("type", char, max(30, delay)))
        return actions

    def scroll_feed(self, direction: str = "down", distance: int = 800) -> list[CursorPoint]:
        cx = self.w // 2 + random.randint(-50, 50)
        if direction == "down":
            start_y = self.h * 3 // 4 + random.randint(-30, 30)
            end_y = start_y - distance
        else:
            start_y = self.h // 4 + random.randint(-30, 30)
            end_y = start_y + distance
        return self.swipe(cx, start_y, cx + random.randint(-10, 10), end_y, "medium")

    @staticmethod
    def _cubic_bezier(t: float, p0: float, p1: float, p2: float, p3: float) -> float:
        return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3

    def to_dict_path(self, points: list[CursorPoint]) -> list[dict]:
        return [{"x": p.x, "y": p.y, "delay_ms": p.delay_ms} for p in points]


human_cursor = HumanCursor()


class ADBHumanCursor:
    """HumanCursor with real ADB execution — sends Bezier paths to a device."""

    def __init__(self, serial: str, screen_w: int = 1080, screen_h: int = 2400):
        self.serial = serial
        self.cursor = HumanCursor(screen_w, screen_h)

    def _adb(self, cmd: str) -> None:
        from utils.adb_utils import adb_cmd
        adb_cmd(self.serial, ["shell"] + cmd.split(), timeout=10)

    def human_tap(self, x: int, y: int) -> None:
        import time
        path = self.cursor.move_to(x, y)
        for i in range(len(path) - 1):
            px, py = path[i].x, path[i].y
            nx, ny = path[i + 1].x, path[i + 1].y
            dur = random.randint(8, 20)
            self._adb(f"input swipe {px} {py} {nx} {ny} {dur}")
        time.sleep(random.uniform(0.08, 0.25))
        tx = x + random.randint(-2, 2)
        ty = y + random.randint(-2, 2)
        self._adb(f"input tap {tx} {ty}")
        self.cursor.current_x = x
        self.cursor.current_y = y

    def human_type(self, text: str) -> None:
        import time
        actions = self.cursor.type_text(text)
        for action in actions:
            if action.action == "backspace":
                self._adb("input keyevent 67")
            elif action.char == " ":
                self._adb("input keyevent 62")
            else:
                escaped = action.char.replace("'", "'\\''").replace("&", "\\&").replace(";", "\\;")
                self._adb(f"input text '{escaped}'")
            time.sleep(action.delay_ms / 1000.0)

    def human_swipe(self, x1: int, y1: int, x2: int, y2: int,
                    speed: str = "medium") -> None:
        speeds = {"slow": (500, 900), "medium": (250, 500), "fast": (100, 250)}
        duration = random.randint(*speeds.get(speed, (250, 500)))
        self._adb(f"input swipe {x1} {y1} {x2} {y2} {duration}")

    def type_text_safe(self, text: str) -> None:
        """Clear field first, then type text."""
        import time
        self._adb("input keyevent 29")  # Ctrl+A
        time.sleep(0.05)
        self._adb("input keyevent 67")  # Delete
        time.sleep(0.1)
        self.human_type(text)

    def scroll_feed(self) -> None:
        w, h = self.cursor.w, self.cursor.h
        start_x = w // 2 + random.randint(-50, 50)
        start_y = int(h * 0.75) + random.randint(-50, 50)
        end_y = int(h * 0.25) + random.randint(-100, 100)
        duration = random.randint(200, 600)
        self._adb(
            f"input swipe {start_x} {start_y} "
            f"{start_x + random.randint(-10, 10)} {end_y} {duration}"
        )
