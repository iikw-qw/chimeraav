"""Human cursor engine — tap, swipe, chaotic swipe, type with tremor."""
from __future__ import annotations

import asyncio
import math
import random

from utils.adb_utils import adb_cmd, adb_input as _adb_input_async, adb_shell


def _sh(serial: str, cmd: str) -> None:
    adb_cmd(serial, ["shell"] + cmd.split(), timeout=10)


async def _get_screen(serial: str) -> tuple[int, int]:
    try:
        out = await adb_shell(serial, "wm size")
        m = __import__("re").search(r"(\d+)x(\d+)", out)
        if m:
            return int(m.group(1)), int(m.group(2))
    except Exception:
        pass
    return 1080, 2400


async def human_tap(
    serial: str, x: float, y: float,
    w: float = 60, h: float = 60,
    screen_w: int = 1080, screen_h: int = 2400,
) -> None:
    tap_x = x + random.uniform(-w * 0.33, w * 0.33)
    tap_y = y + random.uniform(-h * 0.33, h * 0.33)
    tap_x += random.gauss(0, 1.5)
    tap_y += random.gauss(0, 1.5)
    tap_x = max(5, min(screen_w - 5, tap_x))
    tap_y = max(5, min(screen_h - 5, tap_y))
    _sh(serial, f"input tap {tap_x:.0f} {tap_y:.0f}")


async def human_swipe(
    serial: str, direction: str = "up",
    screen_w: int = 1080, screen_h: int = 2400,
) -> None:
    start_x = random.uniform(0.25, 0.75) * screen_w
    start_y = random.uniform(0.55, 0.75) * screen_h
    end_x = start_x + random.uniform(-0.12, 0.12) * screen_w

    if direction == "up":
        end_y = start_y - random.uniform(0.28, 0.48) * screen_h
    elif direction == "down":
        end_y = start_y + random.uniform(0.28, 0.48) * screen_h
    elif direction == "left":
        start_x = random.uniform(0.6, 0.85) * screen_w
        end_x = random.uniform(0.1, 0.3) * screen_w
        end_y = start_y + random.uniform(-0.05, 0.05) * screen_h
    elif direction == "right":
        start_x = random.uniform(0.15, 0.4) * screen_w
        end_x = random.uniform(0.7, 0.9) * screen_w
        end_y = start_y + random.uniform(-0.05, 0.05) * screen_h
    else:
        end_y = start_y - random.uniform(0.28, 0.48) * screen_h

    mid_x = (start_x + end_x) / 2 + random.uniform(-30, 30)
    duration = random.randint(300, 700)

    points = [(start_x, start_y), (mid_x, (start_y + end_y) / 2), (end_x, end_y)]
    for i in range(len(points) - 1):
        sx, sy = points[i]
        ex, ey = points[i + 1]
        ex += random.gauss(0, 2.5)
        ey += random.gauss(0, 2.5)
        seg_dur = duration // (len(points) - 1)
        _sh(serial, f"input swipe {sx:.0f} {sy:.0f} {ex:.0f} {ey:.0f} {seg_dur}")
        await asyncio.sleep(random.uniform(0.02, 0.08))


async def chaotic_swipe(
    serial: str,
    screen_w: int = 1080, screen_h: int = 2400,
) -> None:
    count = random.randint(3, 7)
    for _ in range(count):
        n_points = random.randint(3, 5)
        points = [
            (random.uniform(0.1, 0.9) * screen_w, random.uniform(0.1, 0.9) * screen_h)
            for _ in range(n_points)
        ]
        for i in range(len(points) - 1):
            sx, sy = points[i]
            ex, ey = points[i + 1]
            dur = random.randint(80, 220)
            _sh(serial, f"input swipe {sx:.0f} {sy:.0f} {ex:.0f} {ey:.0f} {dur}")
            await asyncio.sleep(random.uniform(0.05, 0.15))
        await asyncio.sleep(random.uniform(0.3, 1.2))


async def human_tap_advanced(
    serial: str, x: float, y: float,
    w: float = 60, h: float = 60,
    tap_type: str = "normal",
) -> dict:
    """Tap with biometric realism: pressure curve, hold time, micro-drift."""
    sw, sh = await _get_screen(serial)

    tap_x = x + random.uniform(-w * 0.33, w * 0.33)
    tap_y = y + random.uniform(-h * 0.33, h * 0.33)
    tap_x += random.gauss(0, 1.5)
    tap_y += random.gauss(0, 1.5)
    tap_x = max(5, min(sw - 5, tap_x))
    tap_y = max(5, min(sh - 5, tap_y))

    if tap_type == "quick":
        hold_ms = random.randint(40, 80)
        _sh(serial, f"input swipe {tap_x:.0f} {tap_y:.0f} {tap_x:.0f} {tap_y:.0f} {hold_ms}")
    elif tap_type == "long":
        hold_ms = random.randint(500, 800)
        drift_x = tap_x + random.gauss(0, 3)
        drift_y = tap_y + random.gauss(0, 3)
        _sh(serial, f"input swipe {tap_x:.0f} {tap_y:.0f} {drift_x:.0f} {drift_y:.0f} {hold_ms}")
    else:
        hold_ms = int(random.gauss(120, 30))
        hold_ms = max(80, min(200, hold_ms))
        _sh(serial, f"input swipe {tap_x:.0f} {tap_y:.0f} {tap_x:.0f} {tap_y:.0f} {hold_ms}")

    return {"x": tap_x, "y": tap_y, "hold_ms": hold_ms,
            "offset_x": tap_x - x, "offset_y": tap_y - y}


async def human_swipe_bezier(
    serial: str, direction: str = "up",
    amount: float = 0.38,
) -> dict:
    """Swipe with cubic Bezier trajectory: accelerate middle, decelerate end."""
    sw, sh = await _get_screen(serial)

    sx = random.uniform(0.25, 0.75) * sw
    sy = random.uniform(0.5, 0.7) * sh

    if direction == "up":
        ex = sx + random.uniform(-0.1, 0.1) * sw
        ey = sy - amount * sh
    elif direction == "down":
        ex = sx + random.uniform(-0.1, 0.1) * sw
        ey = sy + amount * sh
    elif direction == "left":
        ex = sx - amount * sw
        ey = sy + random.uniform(-0.05, 0.05) * sh
    else:
        ex = sx + amount * sw
        ey = sy + random.uniform(-0.05, 0.05) * sh

    ex = max(10, min(sw - 10, ex))
    ey = max(10, min(sh - 10, ey))

    cp1x = sx + (ex - sx) * 0.25 + random.uniform(-20, 20)
    cp1y = sy + (ey - sy) * 0.1 + random.uniform(-15, 15)
    cp2x = sx + (ex - sx) * 0.75 + random.uniform(-20, 20)
    cp2y = sy + (ey - sy) * 0.9 + random.uniform(-15, 15)

    n_points = random.randint(8, 12)
    points: list[tuple[float, float]] = []
    for i in range(n_points + 1):
        t = i / n_points
        bx = ((1 - t)**3 * sx + 3 * (1 - t)**2 * t * cp1x +
              3 * (1 - t) * t**2 * cp2x + t**3 * ex)
        by = ((1 - t)**3 * sy + 3 * (1 - t)**2 * t * cp1y +
              3 * (1 - t) * t**2 * cp2y + t**3 * ey)
        tremor = 1.5 * math.sin(math.pi * t)
        bx += random.gauss(0, tremor)
        by += random.gauss(0, tremor)
        points.append((max(5, min(sw - 5, bx)), max(5, min(sh - 5, by))))

    if random.random() < 0.4:
        overshoot = random.uniform(5, 12)
        if direction == "up":
            points.append((ex + random.gauss(0, 2), ey - overshoot))
        elif direction == "down":
            points.append((ex + random.gauss(0, 2), ey + overshoot))
        points.append((ex, ey))

    total_dur = random.randint(350, 750)
    for i in range(len(points) - 1):
        px, py = points[i]
        nx, ny = points[i + 1]
        t = i / max(len(points) - 1, 1)
        speed_factor = 0.5 + 0.5 * math.sin(math.pi * t)
        seg_dur = max(20, int((total_dur / len(points)) / max(speed_factor, 0.3)))
        _sh(serial, f"input swipe {px:.0f} {py:.0f} {nx:.0f} {ny:.0f} {seg_dur}")
        await asyncio.sleep(random.uniform(0.005, 0.02))

    return {"points": [(p[0], p[1]) for p in points],
            "duration_ms": total_dur, "direction": direction}


async def human_pinch(
    serial: str, center_x: float, center_y: float,
    zoom_in: bool = True, amount: float = 100,
) -> None:
    """Two-finger pinch gesture for zoom (fallback: single swipe)."""
    if zoom_in:
        f1_sx = center_x - 30
        f1_sy = center_y
        f1_ex = center_x - 30 - amount
        f1_ey = center_y + random.uniform(-10, 10)
    else:
        f1_sx = center_x - 30 - amount
        f1_sy = center_y
        f1_ex = center_x - 30
        f1_ey = center_y + random.uniform(-5, 5)

    dur = random.randint(300, 600)
    _sh(serial, f"input swipe {f1_sx:.0f} {f1_sy:.0f} {f1_ex:.0f} {f1_ey:.0f} {dur}")


async def human_type(serial: str, text: str) -> None:
    for i, char in enumerate(text):
        if random.random() < 0.07 and i > 0:
            wrong = random.choice("qwertyuiopasdfghjklzxcvbnm")
            _sh(serial, f"input text {wrong}")
            await asyncio.sleep(random.uniform(0.08, 0.18))
            _sh(serial, "input keyevent KEYCODE_DEL")
            await asyncio.sleep(random.uniform(0.05, 0.12))

        if char == " ":
            _sh(serial, "input keyevent 62")
            await asyncio.sleep(random.uniform(0.12, 0.28))
        else:
            escaped = char.replace("'", "'\\''")
            _sh(serial, f"input text '{escaped}'")
            await asyncio.sleep(max(0.03, random.gauss(0.08, 0.025)))
