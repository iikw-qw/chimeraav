"""
Антидетект: очистка метаданных, ротация fingerprint, invisible watermark removal.
Зависит от: config, redis_client, Pillow
"""

import io
import os
import random
import struct
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import structlog
from PIL import Image, ExifTags

from app.config import settings
from app.services.redis_client import redis_client

logger = structlog.get_logger()

# Список моделей камер для подмены EXIF
CAMERA_MODELS = [
    ("Apple", "iPhone 13 Pro"), ("Apple", "iPhone 14"), ("Apple", "iPhone 15 Pro Max"),
    ("Samsung", "Galaxy S23"), ("Samsung", "Galaxy S24 Ultra"), ("Samsung", "Galaxy A54"),
    ("Google", "Pixel 7"), ("Google", "Pixel 8 Pro"), ("Xiaomi", "Redmi Note 12"),
    ("OnePlus", "11"), ("Huawei", "P60 Pro"), ("Sony", "Xperia 1 V"),
]

# GPS координаты крупных городов для рандомизации
CITIES_GPS = [
    (55.7558, 37.6173), (48.8566, 2.3522), (40.7128, -74.0060),
    (51.5074, -0.1278), (35.6762, 139.6503), (34.0522, -118.2437),
    (41.9028, 12.4964), (52.5200, 13.4050), (37.7749, -122.4194),
]


class AntidetectService:

    async def clean_exif(self, image_data: bytes) -> bytes:
        """Полное удаление EXIF метаданных из изображения"""
        img = Image.open(io.BytesIO(image_data))
        clean_img = Image.new(img.mode, img.size)
        clean_img.putdata(list(img.getdata()))
        output = io.BytesIO()
        quality = random.randint(85, 95)
        clean_img.save(output, format="JPEG", quality=quality)
        logger.info("exif.cleaned", original_size=len(image_data), clean_size=output.tell())
        return output.getvalue()

    async def spoof_exif(self, image_data: bytes) -> bytes:
        """Подмена EXIF на случайные правдоподобные данные"""
        img = Image.open(io.BytesIO(image_data))
        from PIL.ExifTags import Base as ExifBase

        manufacturer, model = random.choice(CAMERA_MODELS)
        random_date = datetime.now() - timedelta(days=random.randint(1, 365))
        date_str = random_date.strftime("%Y:%m:%d %H:%M:%S")

        exif_dict = {
            ExifBase.Make: manufacturer,
            ExifBase.Model: model,
            ExifBase.DateTime: date_str,
            ExifBase.DateTimeOriginal: date_str,
            ExifBase.Software: f"{manufacturer} Camera",
        }

        output = io.BytesIO()
        quality = random.randint(87, 95)
        img.save(output, format="JPEG", quality=quality)
        logger.info("exif.spoofed", make=manufacturer, model=model)
        return output.getvalue()

    async def modify_lsb(self, image_data: bytes) -> bytes:
        """Модификация LSB пикселей для удаления invisible watermark"""
        img = Image.open(io.BytesIO(image_data))
        if img.mode != "RGB":
            img = img.convert("RGB")

        pixels = list(img.getdata())
        modified = []
        for r, g, b in pixels:
            # Случайная модификация младшего бита
            if random.random() < 0.3:
                r = r ^ 1
            if random.random() < 0.3:
                g = g ^ 1
            if random.random() < 0.3:
                b = b ^ 1
            modified.append((r, g, b))

        img.putdata(modified)
        output = io.BytesIO()
        quality = random.randint(88, 96)
        img.save(output, format="JPEG", quality=quality)
        logger.info("lsb.modified", pixels_total=len(pixels))
        return output.getvalue()

    async def full_clean(self, image_data: bytes) -> bytes:
        """Полная очистка: EXIF + LSB + пересохранение с другим quality"""
        cleaned = await self.clean_exif(image_data)
        cleaned = await self.modify_lsb(cleaned)

        # Финальное пересохранение с другим quality для изменения hash
        img = Image.open(io.BytesIO(cleaned))
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=random.randint(82, 94))

        original_hash = hashlib.md5(image_data).hexdigest()
        new_hash = hashlib.md5(output.getvalue()).hexdigest()
        logger.info("antidetect.full_clean", original_hash=original_hash, new_hash=new_hash)
        return output.getvalue()

    def generate_android_fingerprint(self, seed: Optional[str] = None) -> Dict[str, str]:
        """Генерация случайного Android fingerprint"""
        rng = random.Random(seed) if seed else random

        manufacturers = ["Samsung", "Xiaomi", "OnePlus", "Google", "Huawei", "Oppo", "Vivo"]
        models = {
            "Samsung": ["SM-G991B", "SM-G998B", "SM-S918B", "SM-A546B"],
            "Xiaomi": ["M2102J20SG", "2201123G", "23078PKD5T"],
            "OnePlus": ["LE2125", "NE2215", "CPH2449"],
            "Google": ["Pixel 7", "Pixel 7 Pro", "Pixel 8"],
            "Huawei": ["NOH-NX9", "ABR-LX9"],
            "Oppo": ["CPH2399", "CPH2449"],
            "Vivo": ["V2145", "V2219"],
        }

        manufacturer = rng.choice(manufacturers)
        model = rng.choice(models.get(manufacturer, ["Unknown"]))

        # Генерация уникальных ID
        device_id = "".join(rng.choices("0123456789abcdef", k=16))
        android_id = "".join(rng.choices("0123456789abcdef", k=16))
        imei = "".join(rng.choices("0123456789", k=15))
        serial = "".join(rng.choices("0123456789ABCDEF", k=12))
        mac = ":".join(["".join(rng.choices("0123456789ABCDEF", k=2)) for _ in range(6)])

        return {
            "manufacturer": manufacturer,
            "model": model,
            "device_id": device_id,
            "android_id": android_id,
            "imei": imei,
            "serial": serial,
            "mac_address": mac,
            "build_fingerprint": f"{manufacturer}/{model}/generic:13/TP1A.220905.004/{rng.randint(1000000, 9999999)}:user/release-keys",
        }

    def generate_ios_fingerprint(self, seed: Optional[str] = None) -> Dict[str, str]:
        """Генерация случайного iOS fingerprint"""
        rng = random.Random(seed) if seed else random

        models = ["iPhone14,2", "iPhone14,3", "iPhone15,2", "iPhone15,3", "iPhone16,1", "iPhone16,2"]
        model = rng.choice(models)

        udid = "".join(rng.choices("0123456789ABCDEF", k=40))
        serial = "".join(rng.choices("0123456789ABCDEFGHJKLMNPQRSTUVWXYZ", k=12))

        return {
            "model": model,
            "udid": udid,
            "serial": serial,
            "ios_version": f"{rng.choice([15, 16, 17])}.{rng.randint(0, 6)}.{rng.randint(0, 3)}",
        }

    async def rotate_fingerprint(self, device_id: str, device_type: str) -> Dict[str, str]:
        """Ротация fingerprint устройства и сохранение в Redis"""
        if device_type == "android":
            fp = self.generate_android_fingerprint(f"{device_id}-{datetime.now().strftime('%Y%m%d')}")
        else:
            fp = self.generate_ios_fingerprint(f"{device_id}-{datetime.now().strftime('%Y%m%d')}")

        await redis_client.set_cache(f"fingerprint:{device_id}", fp, ttl=86400)
        logger.info("fingerprint.rotated", device_id=device_id, type=device_type)
        return fp

    async def get_fingerprint(self, device_id: str) -> Optional[Dict]:
        """Получить текущий fingerprint устройства"""
        return await redis_client.get_cache(f"fingerprint:{device_id}")


antidetect_service = AntidetectService()
