"""Make photos/videos unique so platforms don't flag duplicates.

Applies subtle, invisible modifications: crop, brightness, contrast,
saturation, rotation, LSB pixel flipping, EXIF stripping, JPEG quality.
"""

from __future__ import annotations

import hashlib
import logging
import random
import subprocess
from pathlib import Path

logger = logging.getLogger("chimera.content_uniqueizer")

try:
    from PIL import Image, ImageEnhance
except ImportError:
    Image = None  # type: ignore[assignment,misc]
    ImageEnhance = None  # type: ignore[assignment,misc]


class ContentUniqueizer:
    def uniqueize_photo(self, input_path: str, output_path: str) -> dict:
        if Image is None:
            return {"error": "Pillow not installed"}
        img = Image.open(input_path)
        h_before = self._file_hash(input_path)
        changes: list[str] = []

        w, h = img.size
        crop_pct = random.uniform(0.01, 0.03)
        left = int(w * crop_pct * random.uniform(0.5, 1.5))
        top = int(h * crop_pct * random.uniform(0.5, 1.5))
        right = w - int(w * crop_pct * random.uniform(0.5, 1.5))
        bottom = h - int(h * crop_pct * random.uniform(0.5, 1.5))
        img = img.crop((left, top, right, bottom))
        changes.append(f"crop {crop_pct:.1%}")

        factor = random.uniform(0.92, 1.08)
        img = ImageEnhance.Brightness(img).enhance(factor)
        changes.append(f"brightness {factor:.2f}")

        factor = random.uniform(0.95, 1.05)
        img = ImageEnhance.Contrast(img).enhance(factor)
        changes.append(f"contrast {factor:.2f}")

        factor = random.uniform(0.95, 1.05)
        img = ImageEnhance.Color(img).enhance(factor)
        changes.append(f"saturation {factor:.2f}")

        angle = random.uniform(-1.5, 1.5)
        img = img.rotate(angle, expand=False, fillcolor=(255, 255, 255))
        changes.append(f"rotate {angle:.1f}")

        quality = random.randint(85, 95)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        pixels = img.load()
        for _ in range(random.randint(50, 200)):
            px = random.randint(0, img.width - 1)
            py = random.randint(0, img.height - 1)
            r, g, b = pixels[px, py][:3]
            pixels[px, py] = (r ^ 1, g, b)
        changes.append("lsb_mod")

        clean = Image.new(img.mode, img.size)
        clean.paste(img)
        clean.save(output_path, "JPEG", quality=quality)
        changes.append(f"quality={quality}, no_exif")

        return {
            "hash_before": h_before,
            "hash_after": self._file_hash(output_path),
            "changes": changes,
            "output": output_path,
        }

    def uniqueize_video(self, input_path: str, output_path: str) -> dict:
        changes: list[str] = []
        filters: list[str] = []

        br = random.uniform(-0.05, 0.05)
        ct = random.uniform(0.95, 1.05)
        filters.append(f"eq=brightness={br}:contrast={ct}")
        changes.append(f"brightness={br:.3f}, contrast={ct:.2f}")

        crop_px = random.randint(2, 6)
        filters.append(f"crop=iw-{crop_px * 2}:ih-{crop_px * 2}:{crop_px}:{crop_px}")
        changes.append(f"crop={crop_px}px")

        speed = random.uniform(0.98, 1.02)
        filters.append(f"setpts={1 / speed}*PTS")
        changes.append(f"speed={speed:.3f}")

        vf = ",".join(filters)
        try:
            subprocess.run(
                [
                    "ffmpeg", "-i", input_path,
                    "-vf", vf,
                    "-map_metadata", "-1",
                    "-y", output_path,
                ],
                capture_output=True, timeout=300,
            )
        except FileNotFoundError:
            return {"error": "ffmpeg not found", "changes": changes}
        except subprocess.TimeoutExpired:
            return {"error": "ffmpeg timeout", "changes": changes}

        return {"changes": changes, "output": output_path}

    @staticmethod
    def _file_hash(path: str) -> str:
        return hashlib.md5(Path(path).read_bytes()).hexdigest()[:12]
