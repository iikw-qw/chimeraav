"""
Интеграция с 2Captcha: обнаружение и решение капчи.
Зависит от: config, redis_client, notification_service, httpx
"""

import asyncio
import base64
from typing import Optional, Dict, Any

import httpx
import structlog

from app.config import settings
from app.services.redis_client import redis_client

logger = structlog.get_logger()

TWOCAPTCHA_API = "https://2captcha.com"


class CaptchaSolver:
    def __init__(self):
        self.api_key: str = ""
        self.poll_interval: float = 5.0
        self.max_wait: int = 120

    async def _get_api_key(self) -> str:
        """Получение API-ключа из настроек или конфига"""
        if self.api_key:
            return self.api_key

        cached = await redis_client.get_cache("settings:captcha_api_key")
        if cached:
            self.api_key = cached
            return cached

        key = getattr(settings, "twocaptcha_api_key", "") or ""
        if key:
            self.api_key = key
        return key

    async def solve_image_captcha(self, image_base64: str, extra: Optional[Dict] = None) -> Dict[str, Any]:
        """Решение капчи по изображению (base64)"""
        api_key = await self._get_api_key()
        if not api_key:
            logger.warning("captcha.no_api_key")
            return {"success": False, "error": "2Captcha API key not configured"}

        payload = {
            "key": api_key,
            "method": "base64",
            "body": image_base64,
            "json": 1,
        }
        if extra:
            payload.update(extra)

        async with httpx.AsyncClient(timeout=30) as client:
            # Отправка капчи
            resp = await client.post(f"{TWOCAPTCHA_API}/in.php", data=payload)
            data = resp.json()

            if data.get("status") != 1:
                error = data.get("request", "Unknown error")
                logger.error("captcha.submit_failed", error=error)
                return {"success": False, "error": error}

            task_id = data["request"]
            logger.info("captcha.submitted", task_id=task_id)

            # Ожидание результата
            result = await self._poll_result(client, api_key, task_id)
            return result

    async def solve_recaptcha_v2(
        self, site_key: str, page_url: str, invisible: bool = False
    ) -> Dict[str, Any]:
        """Решение reCAPTCHA v2 через токен"""
        api_key = await self._get_api_key()
        if not api_key:
            return {"success": False, "error": "2Captcha API key not configured"}

        payload = {
            "key": api_key,
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": page_url,
            "json": 1,
        }
        if invisible:
            payload["invisible"] = 1

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{TWOCAPTCHA_API}/in.php", data=payload)
            data = resp.json()

            if data.get("status") != 1:
                error = data.get("request", "Unknown error")
                logger.error("captcha.recaptcha_submit_failed", error=error)
                return {"success": False, "error": error}

            task_id = data["request"]
            logger.info("captcha.recaptcha_submitted", task_id=task_id)

            result = await self._poll_result(client, api_key, task_id)
            return result

    async def solve_hcaptcha(self, site_key: str, page_url: str) -> Dict[str, Any]:
        """Решение hCaptcha"""
        api_key = await self._get_api_key()
        if not api_key:
            return {"success": False, "error": "2Captcha API key not configured"}

        payload = {
            "key": api_key,
            "method": "hcaptcha",
            "sitekey": site_key,
            "pageurl": page_url,
            "json": 1,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{TWOCAPTCHA_API}/in.php", data=payload)
            data = resp.json()

            if data.get("status") != 1:
                error = data.get("request", "Unknown error")
                logger.error("captcha.hcaptcha_submit_failed", error=error)
                return {"success": False, "error": error}

            task_id = data["request"]
            logger.info("captcha.hcaptcha_submitted", task_id=task_id)

            result = await self._poll_result(client, api_key, task_id)
            return result

    async def solve_coordinates(self, image_base64: str, comment: str = "") -> Dict[str, Any]:
        """Решение капчи по координатам (клик по изображению)"""
        api_key = await self._get_api_key()
        if not api_key:
            return {"success": False, "error": "2Captcha API key not configured"}

        payload = {
            "key": api_key,
            "method": "base64",
            "body": image_base64,
            "coordinatescaptcha": 1,
            "json": 1,
        }
        if comment:
            payload["textinstructions"] = comment

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{TWOCAPTCHA_API}/in.php", data=payload)
            data = resp.json()

            if data.get("status") != 1:
                error = data.get("request", "Unknown error")
                logger.error("captcha.coordinates_submit_failed", error=error)
                return {"success": False, "error": error}

            task_id = data["request"]
            result = await self._poll_result(client, api_key, task_id)
            return result

    async def _poll_result(
        self, client: httpx.AsyncClient, api_key: str, task_id: str
    ) -> Dict[str, Any]:
        """Опрос статуса задачи до получения результата"""
        elapsed = 0
        await asyncio.sleep(10)
        elapsed += 10

        while elapsed < self.max_wait:
            resp = await client.get(
                f"{TWOCAPTCHA_API}/res.php",
                params={"key": api_key, "action": "get", "id": task_id, "json": 1},
            )
            data = resp.json()

            if data.get("status") == 1:
                logger.info("captcha.solved", task_id=task_id)
                return {"success": True, "answer": data["request"], "task_id": task_id}

            if data.get("request") != "CAPCHA_NOT_READY":
                error = data.get("request", "Unknown error")
                logger.error("captcha.failed", task_id=task_id, error=error)
                return {"success": False, "error": error, "task_id": task_id}

            await asyncio.sleep(self.poll_interval)
            elapsed += self.poll_interval

        logger.error("captcha.timeout", task_id=task_id)
        return {"success": False, "error": "Timeout waiting for captcha solution", "task_id": task_id}

    async def report_correct(self, task_id: str) -> bool:
        """Сообщить 2Captcha о правильном решении"""
        api_key = await self._get_api_key()
        if not api_key:
            return False

        async with httpx.AsyncClient(timeout=10) as client:
            await client.get(
                f"{TWOCAPTCHA_API}/res.php",
                params={"key": api_key, "action": "reportgood", "id": task_id},
            )
        return True

    async def report_incorrect(self, task_id: str) -> bool:
        """Сообщить 2Captcha о неправильном решении (возврат средств)"""
        api_key = await self._get_api_key()
        if not api_key:
            return False

        async with httpx.AsyncClient(timeout=10) as client:
            await client.get(
                f"{TWOCAPTCHA_API}/res.php",
                params={"key": api_key, "action": "reportbad", "id": task_id},
            )
        return True

    async def get_balance(self) -> Optional[float]:
        """Получение баланса 2Captcha"""
        api_key = await self._get_api_key()
        if not api_key:
            return None

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{TWOCAPTCHA_API}/res.php",
                params={"key": api_key, "action": "getbalance", "json": 1},
            )
            data = resp.json()
            if data.get("status") == 1:
                return float(data["request"])
        return None

    async def detect_captcha_on_screenshot(self, screenshot_base64: str) -> Dict[str, Any]:
        """Обнаружение капчи на скриншоте через OCR и паттерны"""
        import cv2
        import numpy as np

        img_bytes = base64.b64decode(screenshot_base64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return {"detected": False, "error": "Failed to decode image"}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Поиск характерных элементов капчи
        captcha_indicators = {
            "recaptcha": False,
            "hcaptcha": False,
            "image_captcha": False,
        }

        try:
            import pytesseract
            text = pytesseract.image_to_string(gray, lang="eng+rus").lower()

            recaptcha_keywords = ["i'm not a robot", "я не робот", "recaptcha", "verify"]
            hcaptcha_keywords = ["hcaptcha", "select all", "выберите все"]
            generic_keywords = ["captcha", "капча", "введите код", "enter code"]

            for kw in recaptcha_keywords:
                if kw in text:
                    captcha_indicators["recaptcha"] = True
                    break

            for kw in hcaptcha_keywords:
                if kw in text:
                    captcha_indicators["hcaptcha"] = True
                    break

            for kw in generic_keywords:
                if kw in text:
                    captcha_indicators["image_captcha"] = True
                    break

        except Exception as e:
            logger.warning("captcha.ocr_failed", error=str(e))

        detected = any(captcha_indicators.values())
        captcha_type = "none"
        if captcha_indicators["recaptcha"]:
            captcha_type = "recaptcha_v2"
        elif captcha_indicators["hcaptcha"]:
            captcha_type = "hcaptcha"
        elif captcha_indicators["image_captcha"]:
            captcha_type = "image"

        if detected:
            logger.info("captcha.detected", type=captcha_type)

        return {
            "detected": detected,
            "type": captcha_type,
            "indicators": captcha_indicators,
        }


captcha_solver = CaptchaSolver()
