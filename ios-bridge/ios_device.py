"""
iOS Device: управление iOS устройством через libimobiledevice.
Зависит от: libimobiledevice (idevice* commands)
"""

import asyncio
import json
from typing import Optional, Dict, Any, List

import structlog

logger = structlog.get_logger()


class IOSDevice:
    def __init__(self, udid: str):
        self.udid = udid
        self.info: Dict[str, Any] = {}

    async def get_device_info(self) -> Dict[str, Any]:
        """Получить информацию об устройстве"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ideviceinfo", "-u", self.udid, "-k", "ProductType",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            product_type = stdout.decode().strip()

            info_items = ["DeviceName", "ProductVersion", "UniqueDeviceID",
                          "SerialNumber", "ModelNumber", "HardwareModel"]
            info = {"product_type": product_type}

            for key in info_items:
                proc = await asyncio.create_subprocess_exec(
                    "ideviceinfo", "-u", self.udid, "-k", key,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                info[key.lower()] = stdout.decode().strip()

            self.info = info
            logger.info("ios.device_info", udid=self.udid, info=info)
            return info
        except FileNotFoundError:
            logger.error("ios.libimobiledevice_not_found")
            return {}
        except Exception as e:
            logger.error("ios.info_error", udid=self.udid, error=str(e))
            return {}

    async def get_battery_level(self) -> int:
        """Получить уровень заряда батареи"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ideviceinfo", "-u", self.udid, "-q", "com.apple.mobile.battery", "-k", "BatteryCurrentCapacity",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return int(stdout.decode().strip())
        except Exception:
            return -1

    async def screenshot(self) -> Optional[bytes]:
        """Скриншот через idevicescreenshot"""
        try:
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                tmppath = f.name

            proc = await asyncio.create_subprocess_exec(
                "idevicescreenshot", "-u", self.udid, tmppath,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            if os.path.exists(tmppath):
                with open(tmppath, "rb") as f:
                    data = f.read()
                os.unlink(tmppath)
                return data
        except Exception as e:
            logger.error("ios.screenshot_error", udid=self.udid, error=str(e))
        return None

    async def install_app(self, ipa_path: str) -> bool:
        """Установить приложение"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ideviceinstaller", "-u", self.udid, "-i", ipa_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            success = proc.returncode == 0
            logger.info("ios.app_installed", udid=self.udid, path=ipa_path, success=success)
            return success
        except Exception as e:
            logger.error("ios.install_error", error=str(e))
            return False

    async def list_apps(self) -> List[str]:
        """Получить список установленных приложений"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ideviceinstaller", "-u", self.udid, "-l",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            apps = [line.strip() for line in stdout.decode().splitlines() if line.strip()]
            return apps
        except Exception:
            return []

    async def reboot(self):
        """Перезагрузка устройства"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "idevicediagnostics", "-u", self.udid, "restart",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            logger.info("ios.rebooted", udid=self.udid)
        except Exception as e:
            logger.error("ios.reboot_error", udid=self.udid, error=str(e))


class IOSDeviceDiscovery:
    """Обнаружение подключённых iOS устройств"""

    @staticmethod
    async def discover() -> List[str]:
        """Получить список UDID подключённых устройств"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "idevice_id", "-l",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            udids = [line.strip() for line in stdout.decode().splitlines() if line.strip()]
            logger.info("ios.discovered", count=len(udids))
            return udids
        except FileNotFoundError:
            logger.warning("ios.libimobiledevice_not_installed")
            return []
        except Exception as e:
            logger.error("ios.discovery_error", error=str(e))
            return []
