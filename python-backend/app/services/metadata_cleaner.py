"""Remove EXIF/XMP, perturb image pixels, transcode videos to break fingerprints."""

from __future__ import annotations

import asyncio
import hashlib
import random
import shutil
import subprocess
from pathlib import Path

import numpy as np
import piexif
from PIL import Image

from app.database import SessionLocal
from app.models.metadata_cleaning import MetadataCleaning


class MetadataCleaner:
    async def clean_image(self, path: str) -> dict[str, str | bool]:
        return await asyncio.to_thread(self._clean_image_sync, path)

    def _clean_image_sync(self, path: str) -> dict[str, str | bool]:
        src = Path(path)
        if not src.exists():
            raise FileNotFoundError(path)

        original_hash = self._file_hash(src)
        exif_removed = False
        gps_removed = False

        image = Image.open(src)
        image = image.convert("RGB")

        try:
            piexif.remove(str(src))
            exif_removed = True
            gps_removed = True
        except Exception:
            exif_removed = False

        cleaned = self._strip_xmp(src.read_bytes())
        tmp_xmp = src.with_suffix(src.suffix + ".xmp.tmp")
        tmp_xmp.write_bytes(cleaned)
        image = Image.open(tmp_xmp).convert("RGB")
        tmp_xmp.unlink(missing_ok=True)

        arr = np.array(image)
        arr = self._random_crop(arr, 1, 3)
        arr = self._brightness_perturb(arr, 0.003)
        arr = self._flip_lsb(arr, random.randint(5, 10))

        cleaned_image = Image.fromarray(arr)
        quality = random.randint(87, 94)
        cleaned_image.save(src, format="JPEG", quality=quality, optimize=True)

        cleaned_hash = self._file_hash(src)

        _persist_task(
            MetadataCleaning(
                file_path=str(src),
                original_hash=original_hash,
                cleaned_hash=cleaned_hash,
                exif_removed=exif_removed,
                gps_removed=gps_removed,
                digital_fingerprint_modified=True,
            )
        )

        return {
            "file_path": str(src),
            "original_hash": original_hash,
            "cleaned_hash": cleaned_hash,
            "exif_removed": exif_removed,
            "gps_removed": gps_removed,
            "digital_fingerprint_modified": True,
        }

    async def clean_video(self, path: str) -> dict[str, str | bool]:
        return await asyncio.to_thread(self._clean_video_sync, path)

    def _clean_video_sync(self, path: str) -> dict[str, str | bool]:
        src = Path(path)
        if not src.exists():
            raise FileNotFoundError(path)

        original_hash = self._file_hash(src)
        crf = random.randint(19, 23)
        output = src.with_name(f"{src.stem}.clean{src.suffix}")

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-map_metadata",
            "-1",
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-c:a",
            "aac",
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")

        shutil.move(str(output), str(src))
        cleaned_hash = self._file_hash(src)

        _persist_task(
            MetadataCleaning(
                file_path=str(src),
                original_hash=original_hash,
                cleaned_hash=cleaned_hash,
                exif_removed=True,
                gps_removed=True,
                digital_fingerprint_modified=True,
            )
        )

        return {
            "file_path": str(src),
            "original_hash": original_hash,
            "cleaned_hash": cleaned_hash,
            "exif_removed": True,
            "gps_removed": True,
            "digital_fingerprint_modified": True,
        }

    async def clean_batch(
        self, paths: list[str]
    ) -> list[dict[str, str | bool] | Exception]:
        tasks = [self._clean_any(p) for p in paths]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _clean_any(self, path: str) -> dict[str, str | bool]:
        suffix = Path(path).suffix.lower()
        if suffix in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
            return await self.clean_video(path)
        return await self.clean_image(path)

    @staticmethod
    def _file_hash(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _strip_xmp(data: bytes) -> bytes:
        start = data.find(b"<x:xmpmeta")
        if start == -1:
            return data
        end = data.find(b"</x:xmpmeta>", start)
        if end == -1:
            return data
        return data[:start] + data[end + len(b"</x:xmpmeta>") :]

    @staticmethod
    def _random_crop(arr: np.ndarray, lo: int, hi: int) -> np.ndarray:
        h, w = arr.shape[:2]
        top = random.randint(lo, hi)
        bottom = random.randint(lo, hi)
        left = random.randint(lo, hi)
        right = random.randint(lo, hi)
        return arr[top : h - bottom, left : w - right]

    @staticmethod
    def _brightness_perturb(arr: np.ndarray, magnitude: float) -> np.ndarray:
        factor = 1.0 + random.uniform(-magnitude, magnitude)
        out = np.clip(arr.astype(np.float32) * factor, 0, 255).astype(np.uint8)
        return out

    @staticmethod
    def _flip_lsb(arr: np.ndarray, pixels: int) -> np.ndarray:
        h, w, _ = arr.shape
        out = arr.copy()
        for _ in range(pixels):
            y = random.randint(0, h - 1)
            x = random.randint(0, w - 1)
            c = random.randint(0, 2)
            out[y, x, c] ^= 1
        return out


def _persist_task(record: MetadataCleaning) -> None:
    async def _run() -> None:
        async with SessionLocal() as session:
            session.add(record)
            await session.commit()

    asyncio.run(_run())


metadata_cleaner = MetadataCleaner()
