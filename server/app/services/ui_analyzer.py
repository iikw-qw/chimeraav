"""
UI Analyzer: OpenCV + YOLOv8 для определения UI-элементов.
Определение и запоминание расположения кнопок каждой платформы.
Зависит от: redis_client, OpenCV, ultralytics
"""

import io
import json
import hashlib
from typing import Optional, Dict, Any, List, Tuple

import cv2
import numpy as np
import structlog

from app.services.redis_client import redis_client

logger = structlog.get_logger()

# Локаторы UI-элементов по платформам
DEFAULT_LOCATORS: Dict[str, Dict[str, Any]] = {
    "instagram": {
        "login_button": {"type": "text", "value": "Log in", "fallback_xpath": "//android.widget.Button[@text='Log in']"},
        "username_field": {"type": "resource_id", "value": "com.instagram.android:id/login_username"},
        "password_field": {"type": "resource_id", "value": "com.instagram.android:id/password"},
        "new_post_button": {"type": "content_desc", "value": "New post"},
        "share_button": {"type": "text", "value": "Share"},
        "caption_field": {"type": "resource_id", "value": "com.instagram.android:id/caption_text_view"},
    },
    "telegram": {
        "login_phone_field": {"type": "resource_id", "value": "org.telegram.messenger:id/phone_field"},
        "send_button": {"type": "content_desc", "value": "Send"},
    },
    "tiktok": {
        "login_button": {"type": "text", "value": "Log in"},
        "username_field": {"type": "resource_id", "value": "com.zhiliaoapp.musically:id/et_username"},
        "post_button": {"type": "content_desc", "value": "Post"},
    },
    "facebook": {
        "login_button": {"type": "resource_id", "value": "com.facebook.katana:id/login_button"},
        "email_field": {"type": "resource_id", "value": "com.facebook.katana:id/login_username"},
    },
}

# Пакеты приложений по платформам
APP_PACKAGES = {
    "instagram": "com.instagram.android",
    "telegram": "org.telegram.messenger",
    "tiktok": "com.zhiliaoapp.musically",
    "facebook": "com.facebook.katana",
    "twitter": "com.twitter.android",
    "linkedin": "com.linkedin.android",
    "vk": "com.vkontakte.android",
    "youtube": "com.google.android.youtube",
    "reddit": "com.reddit.frontpage",
    "threads": "com.instagram.barcelona",
}

# iOS Bundle IDs
IOS_BUNDLES = {
    "instagram": "com.burbn.instagram",
    "telegram": "ph.telegra.Telegraph",
    "tiktok": "com.zhiliaoapp.musically",
    "facebook": "com.facebook.Facebook",
    "twitter": "com.atebits.Tweetie2",
}


class UIAnalyzer:

    async def find_element(
        self, screenshot: bytes, platform: str, element_name: str, os_version: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Поиск UI-элемента на скриншоте"""
        # Сначала проверяем кеш в Redis
        cache_key = f"locator:{platform}:{element_name}:{os_version}"
        cached = await redis_client.get_cache(cache_key)
        if cached:
            return cached

        # Проверяем дефолтные локаторы
        platform_locators = DEFAULT_LOCATORS.get(platform, {})
        locator = platform_locators.get(element_name)
        if locator:
            await redis_client.set_cache(cache_key, locator, ttl=3600)
            return locator

        # Фолбэк на OCR
        result = await self._ocr_find(screenshot, element_name)
        if result:
            await redis_client.set_cache(cache_key, result, ttl=1800)
            return result

        logger.warning("ui.element_not_found", platform=platform, element=element_name)
        return None

    async def _ocr_find(self, screenshot: bytes, text: str) -> Optional[Dict[str, Any]]:
        """Поиск текста на скриншоте через OCR"""
        try:
            import pytesseract

            nparr = np.frombuffer(screenshot, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return None

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)

            for i, word in enumerate(data["text"]):
                if text.lower() in str(word).lower() and int(data["conf"][i]) > 60:
                    x = data["left"][i]
                    y = data["top"][i]
                    w = data["width"][i]
                    h = data["height"][i]
                    center_x = x + w // 2
                    center_y = y + h // 2

                    return {
                        "type": "ocr",
                        "value": text,
                        "x": center_x,
                        "y": center_y,
                        "width": w,
                        "height": h,
                        "confidence": int(data["conf"][i]),
                    }
        except Exception as e:
            logger.error("ocr.error", error=str(e))

        return None

    async def detect_ui_elements(self, screenshot: bytes) -> List[Dict[str, Any]]:
        """Определение всех UI-элементов на скриншоте через OpenCV"""
        nparr = np.frombuffer(screenshot, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return []

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        elements = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 500 or area > img.shape[0] * img.shape[1] * 0.5:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0

            element_type = "unknown"
            if 2.5 < aspect_ratio < 8.0 and h < 100:
                element_type = "button"
            elif 3.0 < aspect_ratio < 20.0 and h < 80:
                element_type = "input"
            elif 0.8 < aspect_ratio < 1.2 and area > 2000:
                element_type = "icon"

            if element_type != "unknown":
                elements.append({
                    "type": element_type,
                    "x": x + w // 2,
                    "y": y + h // 2,
                    "width": w,
                    "height": h,
                })

        logger.info("ui.elements_detected", count=len(elements))
        return elements

    async def detect_current_app(self, device_type: str = "android") -> Optional[str]:
        """Определение текущего открытого приложения (вызывается из агента)"""
        # Этот метод используется агентом, который отправляет package name
        return None

    def get_app_package(self, platform: str, device_type: str = "android") -> str:
        """Получить package name / bundle ID для платформы"""
        if device_type == "ios":
            return IOS_BUNDLES.get(platform, "")
        return APP_PACKAGES.get(platform, "")

    async def update_locator(self, platform: str, element_name: str, locator: Dict[str, Any]):
        """Обновить локатор и разослать всем агентам через краудсорсинг"""
        cache_key = f"locator:{platform}:{element_name}"
        await redis_client.set_cache(cache_key, locator, ttl=86400)

        # Рассылка через pub/sub
        await redis_client.publish("chimera:locator_updates", {
            "platform": platform,
            "element": element_name,
            "locator": locator,
        })

        logger.info("locator.updated", platform=platform, element=element_name)

    async def get_all_locators(self, platform: str) -> Dict[str, Any]:
        """Получить все локаторы для платформы"""
        locators = DEFAULT_LOCATORS.get(platform, {}).copy()

        # Добавить кешированные обновления
        for element_name in locators:
            cached = await redis_client.get_cache(f"locator:{platform}:{element_name}")
            if cached:
                locators[element_name] = cached

        return locators


ui_analyzer = UIAnalyzer()
