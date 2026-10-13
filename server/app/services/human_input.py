"""
Имитация человеческого ввода: курсор, клавиатура, свайпы.
Зависит от: config (параметры конфигурируемы)
"""

import math
import random
from typing import List, Tuple, Dict, Any, Optional

import structlog

logger = structlog.get_logger()

# Параметры по умолчанию (конфигурируемые через настройки)
DEFAULT_CONFIG = {
    "cursor_control_points": 4,
    "cursor_random_offset": 20,
    "cursor_overshoot_px": 3,
    "pre_click_pause_min_ms": 100,
    "pre_click_pause_max_ms": 300,
    "tremor_amplitude_px": 1.5,
    "tremor_frequency_hz": 10,
    "swipe_deviation_px": 5,
    "typing_delay_mean_ms": 70,
    "typing_delay_std_ms": 20,
    "typo_probability": 1 / 15,
    "word_pause_min_ms": 150,
    "word_pause_max_ms": 300,
}


class HumanInput:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}

    def bezier_curve(
        self, start: Tuple[float, float], end: Tuple[float, float], num_points: int = 20
    ) -> List[Tuple[int, int]]:
        """Генерация кривой Безье с 3-4 контрольными точками и рандомом"""
        sx, sy = start
        ex, ey = end
        offset = self.config["cursor_random_offset"]
        n_controls = self.config["cursor_control_points"]

        # Контрольные точки с рандомным смещением
        controls = [start]
        for i in range(1, n_controls - 1):
            t = i / (n_controls - 1)
            cx = sx + (ex - sx) * t + random.uniform(-offset, offset)
            cy = sy + (ey - sy) * t + random.uniform(-offset, offset)
            controls.append((cx, cy))
        controls.append(end)

        # De Casteljau algorithm
        points = []
        for step in range(num_points + 1):
            t = step / num_points
            pts = list(controls)
            while len(pts) > 1:
                pts = [
                    (pts[i][0] * (1 - t) + pts[i + 1][0] * t,
                     pts[i][1] * (1 - t) + pts[i + 1][1] * t)
                    for i in range(len(pts) - 1)
                ]
            points.append((int(pts[0][0]), int(pts[0][1])))

        return points

    def apply_speed_profile(self, points: List[Tuple[int, int]]) -> List[Tuple[int, int, int]]:
        """Добавление профиля скорости: ускорение → замедление → overshoot → return.
        Возвращает (x, y, delay_ms)"""
        n = len(points)
        result = []
        overshoot = self.config["cursor_overshoot_px"]

        for i, (x, y) in enumerate(points):
            t = i / max(n - 1, 1)

            # Профиль скорости: быстро в начале, медленно в конце
            if t < 0.3:
                speed_factor = 0.5 + t * 3.0  # Ускорение
            elif t < 0.8:
                speed_factor = 1.4  # Крейсерская
            else:
                speed_factor = 1.4 - (t - 0.8) * 4.0  # Замедление

            delay = max(2, int(10 / max(speed_factor, 0.3)))
            result.append((x, y, delay))

        # Overshoot на последних точках
        if len(result) > 3 and overshoot > 0:
            last_x, last_y = result[-1][0], result[-1][1]
            prev_x, prev_y = result[-3][0], result[-3][1]

            dx = last_x - prev_x
            dy = last_y - prev_y
            dist = math.sqrt(dx * dx + dy * dy) or 1

            overshoot_x = last_x + int(dx / dist * overshoot)
            overshoot_y = last_y + int(dy / dist * overshoot)

            result.append((overshoot_x, overshoot_y, 15))
            result.append((last_x, last_y, 20))

        return result

    def add_tremor(self, x: int, y: int, hold_duration_ms: int) -> List[Tuple[int, int, int]]:
        """Тремор при удержании: ±1-2px синусоида 8-12Hz"""
        amp = self.config["tremor_amplitude_px"]
        freq = self.config["tremor_frequency_hz"]
        steps = hold_duration_ms // 10
        points = []

        for i in range(steps):
            t = i * 0.01
            tx = x + int(amp * math.sin(2 * math.pi * freq * t + random.uniform(0, 0.5)))
            ty = y + int(amp * math.cos(2 * math.pi * freq * t * 0.7 + random.uniform(0, 0.5)))
            points.append((tx, ty, 10))

        return points

    def generate_click(self, x: int, y: int) -> Dict[str, Any]:
        """Генерация параметров клика с пре-паузой"""
        pause = random.randint(
            self.config["pre_click_pause_min_ms"],
            self.config["pre_click_pause_max_ms"],
        )
        hold = random.randint(50, 150)

        return {
            "x": x,
            "y": y,
            "pre_pause_ms": pause,
            "hold_ms": hold,
            "tremor": self.add_tremor(x, y, hold),
        }

    def generate_move_and_click(
        self, from_pos: Tuple[int, int], to_pos: Tuple[int, int]
    ) -> Dict[str, Any]:
        """Полная генерация: движение курсором + клик"""
        path = self.bezier_curve(from_pos, to_pos)
        path_with_speed = self.apply_speed_profile(path)
        click = self.generate_click(to_pos[0], to_pos[1])

        return {
            "path": path_with_speed,
            "click": click,
            "total_duration_ms": sum(p[2] for p in path_with_speed) + click["pre_pause_ms"] + click["hold_ms"],
        }

    def generate_swipe(
        self, start: Tuple[int, int], end: Tuple[int, int], duration_ms: int = 500
    ) -> List[Tuple[int, int, int]]:
        """Генерация свайпа с инерцией и отклонением"""
        deviation = self.config["swipe_deviation_px"]
        steps = max(10, duration_ms // 15)

        points = []
        for i in range(steps + 1):
            t = i / steps
            # Интерполяция с отклонением от прямой
            x = start[0] + (end[0] - start[0]) * t + random.uniform(-deviation, deviation)
            y = start[1] + (end[1] - start[1]) * t + random.uniform(-deviation, deviation)

            # Инерция: ускорение в начале, замедление в конце
            if t < 0.2:
                delay = int(15 * (1 - t * 3))
            elif t > 0.8:
                delay = int(15 * (1 + (t - 0.8) * 5))
            else:
                delay = 8

            points.append((int(x), int(y), max(3, delay)))

        return points

    def generate_typing(self, text: str) -> List[Dict[str, Any]]:
        """Генерация ввода текста с задержками и опечатками"""
        actions = []
        typo_prob = self.config["typo_probability"]
        mean = self.config["typing_delay_mean_ms"]
        std = self.config["typing_delay_std_ms"]

        for i, char in enumerate(text):
            # Пауза между словами
            if char == " ":
                pause = random.randint(
                    self.config["word_pause_min_ms"],
                    self.config["word_pause_max_ms"],
                )
                actions.append({"type": "key", "char": char, "delay_ms": pause})
                continue

            # Опечатка
            if random.random() < typo_prob and char.isalpha():
                wrong_char = chr(ord(char) + random.choice([-1, 1]))
                actions.append({
                    "type": "key",
                    "char": wrong_char,
                    "delay_ms": max(30, int(random.gauss(mean, std))),
                })
                # Задержка перед исправлением
                actions.append({"type": "key", "char": "BACKSPACE", "delay_ms": random.randint(200, 500)})

            delay = max(30, int(random.gauss(mean, std)))
            actions.append({"type": "key", "char": char, "delay_ms": delay})

        return actions

    def generate_scroll(self, direction: str = "down", distance: int = 500) -> List[Tuple[int, int, int]]:
        """Генерация скроллинга"""
        screen_center_x = 540
        if direction == "down":
            return self.generate_swipe(
                (screen_center_x, 1200), (screen_center_x, 1200 - distance), 400
            )
        else:
            return self.generate_swipe(
                (screen_center_x, 600), (screen_center_x, 600 + distance), 400
            )


    def generate_clear_and_type(self, text: str) -> List[Dict[str, Any]]:
        """Очистить поле (Ctrl+A, Delete) и ввести текст заново."""
        actions = []
        actions.append({"type": "key", "char": "CTRL_A", "delay_ms": 100})
        actions.append({"type": "key", "char": "DELETE", "delay_ms": 100})
        actions.extend(self.generate_typing(text))
        return actions


human_input = HumanInput()
