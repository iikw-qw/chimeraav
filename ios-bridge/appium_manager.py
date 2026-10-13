"""
Appium Manager для iOS: управление Appium сессиями и WebDriverAgent.
Зависит от: appium-python-client, libimobiledevice
"""

import asyncio
import subprocess
import json
from typing import Optional, Dict, Any, List

import structlog
import httpx

logger = structlog.get_logger()


class AppiumManager:
    def __init__(self, appium_host: str = "localhost", appium_port: int = 4723):
        self.appium_url = f"http://{appium_host}:{appium_port}"
        self.sessions: Dict[str, str] = {}  # device_udid → session_id

    async def create_session(self, udid: str, bundle_id: str = "") -> Optional[str]:
        """Создание новой Appium сессии для iOS устройства"""
        capabilities = {
            "platformName": "iOS",
            "automationName": "XCUITest",
            "udid": udid,
            "noReset": True,
            "newCommandTimeout": 3600,
            "wdaLaunchTimeout": 120000,
            "wdaConnectionTimeout": 120000,
        }
        if bundle_id:
            capabilities["bundleId"] = bundle_id

        payload = {
            "capabilities": {
                "alwaysMatch": capabilities,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.appium_url}/session",
                    json=payload,
                )
                if response.status_code == 200:
                    data = response.json()
                    session_id = data["value"]["sessionId"]
                    self.sessions[udid] = session_id
                    logger.info("appium.session_created", udid=udid, session_id=session_id)
                    return session_id
                else:
                    logger.error("appium.session_failed", udid=udid, status=response.status_code)
                    return None
        except Exception as e:
            logger.error("appium.connection_error", error=str(e))
            return None

    async def close_session(self, udid: str):
        """Закрытие Appium сессии"""
        session_id = self.sessions.pop(udid, None)
        if not session_id:
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.delete(f"{self.appium_url}/session/{session_id}")
            logger.info("appium.session_closed", udid=udid)
        except Exception as e:
            logger.error("appium.close_error", udid=udid, error=str(e))

    async def find_element(self, udid: str, strategy: str, selector: str) -> Optional[Dict]:
        """Поиск элемента на экране iOS"""
        session_id = self.sessions.get(udid)
        if not session_id:
            return None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.appium_url}/session/{session_id}/element",
                    json={"using": strategy, "value": selector},
                )
                if response.status_code == 200:
                    return response.json()["value"]
        except Exception as e:
            logger.error("appium.find_error", udid=udid, error=str(e))
        return None

    async def tap(self, udid: str, x: int, y: int):
        """Тап по координатам"""
        session_id = self.sessions.get(udid)
        if not session_id:
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{self.appium_url}/session/{session_id}/actions",
                    json={
                        "actions": [{
                            "type": "pointer",
                            "id": "finger1",
                            "parameters": {"pointerType": "touch"},
                            "actions": [
                                {"type": "pointerMove", "duration": 0, "x": x, "y": y},
                                {"type": "pointerDown", "button": 0},
                                {"type": "pause", "duration": 100},
                                {"type": "pointerUp", "button": 0},
                            ]
                        }]
                    },
                )
        except Exception as e:
            logger.error("appium.tap_error", udid=udid, error=str(e))

    async def swipe(self, udid: str, start_x: int, start_y: int, end_x: int, end_y: int, duration: int = 500):
        """Свайп на экране"""
        session_id = self.sessions.get(udid)
        if not session_id:
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{self.appium_url}/session/{session_id}/actions",
                    json={
                        "actions": [{
                            "type": "pointer",
                            "id": "finger1",
                            "parameters": {"pointerType": "touch"},
                            "actions": [
                                {"type": "pointerMove", "duration": 0, "x": start_x, "y": start_y},
                                {"type": "pointerDown", "button": 0},
                                {"type": "pointerMove", "duration": duration, "x": end_x, "y": end_y},
                                {"type": "pointerUp", "button": 0},
                            ]
                        }]
                    },
                )
        except Exception as e:
            logger.error("appium.swipe_error", udid=udid, error=str(e))

    async def type_text(self, udid: str, element_id: str, text: str):
        """Ввод текста в элемент"""
        session_id = self.sessions.get(udid)
        if not session_id:
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{self.appium_url}/session/{session_id}/element/{element_id}/value",
                    json={"text": text},
                )
        except Exception as e:
            logger.error("appium.type_error", udid=udid, error=str(e))

    async def screenshot(self, udid: str) -> Optional[bytes]:
        """Скриншот экрана"""
        session_id = self.sessions.get(udid)
        if not session_id:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.appium_url}/session/{session_id}/screenshot",
                )
                if response.status_code == 200:
                    import base64
                    b64 = response.json()["value"]
                    return base64.b64decode(b64)
        except Exception as e:
            logger.error("appium.screenshot_error", udid=udid, error=str(e))
        return None

    async def launch_app(self, udid: str, bundle_id: str):
        """Запуск приложения"""
        session_id = self.sessions.get(udid)
        if not session_id:
            return

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    f"{self.appium_url}/session/{session_id}/appium/device/activate_app",
                    json={"bundleId": bundle_id},
                )
            logger.info("appium.app_launched", udid=udid, bundle=bundle_id)
        except Exception as e:
            logger.error("appium.launch_error", udid=udid, error=str(e))

    async def get_page_source(self, udid: str) -> Optional[str]:
        """Получить XML дерево элементов"""
        session_id = self.sessions.get(udid)
        if not session_id:
            return None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.appium_url}/session/{session_id}/source",
                )
                if response.status_code == 200:
                    return response.json()["value"]
        except Exception as e:
            logger.error("appium.source_error", udid=udid, error=str(e))
        return None


appium_manager = AppiumManager()
