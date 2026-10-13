"""
iOS Command Executor: выполнение команд на iOS через Appium.
Зависит от: appium_manager, ios_device
"""

import asyncio
from typing import Dict, Any, Optional

import structlog

from ios_bridge.appium_manager import appium_manager
from ios_bridge.ios_device import IOSDevice

logger = structlog.get_logger()

IOS_BUNDLES = {
    "instagram": "com.burbn.instagram",
    "telegram": "ph.telegra.Telegraph",
    "tiktok": "com.zhiliaoapp.musically",
    "facebook": "com.facebook.Facebook",
    "twitter": "com.atebits.Tweetie2",
    "linkedin": "com.linkedin.LinkedIn",
    "youtube": "com.google.ios.youtube",
    "reddit": "com.reddit.Reddit",
    "threads": "com.burbn.barcelona",
    "vk": "com.vk.vkclient",
}


class IOSCommandExecutor:
    def __init__(self):
        self.devices: Dict[str, IOSDevice] = {}

    async def execute(self, udid: str, command: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить команду на iOS устройстве"""
        cmd_type = command.get("type", "")

        handlers = {
            "tap": self._tap,
            "swipe": self._swipe,
            "type": self._type_text,
            "screenshot": self._screenshot,
            "open_app": self._open_app,
            "scroll": self._scroll,
            "reboot": self._reboot,
            "get_info": self._get_info,
        }

        handler = handlers.get(cmd_type)
        if not handler:
            return {"success": False, "error": f"Unknown command: {cmd_type}"}

        try:
            result = await handler(udid, command)
            return {"success": True, **result}
        except Exception as e:
            logger.error("ios.command_error", udid=udid, command=cmd_type, error=str(e))
            return {"success": False, "error": str(e)}

    async def _tap(self, udid: str, cmd: Dict) -> Dict:
        x, y = cmd.get("x", 0), cmd.get("y", 0)
        await appium_manager.tap(udid, x, y)
        return {"action": "tap", "x": x, "y": y}

    async def _swipe(self, udid: str, cmd: Dict) -> Dict:
        await appium_manager.swipe(
            udid,
            cmd.get("start_x", 200), cmd.get("start_y", 500),
            cmd.get("end_x", 200), cmd.get("end_y", 200),
            cmd.get("duration", 500),
        )
        return {"action": "swipe"}

    async def _type_text(self, udid: str, cmd: Dict) -> Dict:
        element_id = cmd.get("element_id", "")
        text = cmd.get("text", "")
        if element_id:
            await appium_manager.type_text(udid, element_id, text)
        return {"action": "type", "text": text}

    async def _screenshot(self, udid: str, cmd: Dict) -> Dict:
        data = await appium_manager.screenshot(udid)
        if data:
            return {"action": "screenshot", "size": len(data)}
        return {"action": "screenshot", "error": "Failed to capture"}

    async def _open_app(self, udid: str, cmd: Dict) -> Dict:
        platform = cmd.get("platform", "")
        bundle_id = cmd.get("bundle_id") or IOS_BUNDLES.get(platform, "")
        if bundle_id:
            await appium_manager.launch_app(udid, bundle_id)
            return {"action": "open_app", "bundle": bundle_id}
        return {"action": "open_app", "error": "Unknown platform"}

    async def _scroll(self, udid: str, cmd: Dict) -> Dict:
        direction = cmd.get("direction", "down")
        if direction == "down":
            await appium_manager.swipe(udid, 200, 600, 200, 200, 300)
        else:
            await appium_manager.swipe(udid, 200, 200, 200, 600, 300)
        return {"action": "scroll", "direction": direction}

    async def _reboot(self, udid: str, cmd: Dict) -> Dict:
        device = self.devices.get(udid) or IOSDevice(udid)
        await device.reboot()
        return {"action": "reboot"}

    async def _get_info(self, udid: str, cmd: Dict) -> Dict:
        device = self.devices.get(udid) or IOSDevice(udid)
        self.devices[udid] = device
        info = await device.get_device_info()
        return {"action": "get_info", "info": info}


ios_executor = IOSCommandExecutor()
