"""
Автонастройка прокси на Android-устройстве через ADB.
Зависит от: adb_proxy
"""

import subprocess
import logging

logger = logging.getLogger(__name__)


class ProxySetup:
    def __init__(self, serial: str):
        self.serial = serial

    def _sh(self, cmd: str) -> str:
        try:
            r = subprocess.run(
                ["adb", "-s", self.serial, "shell", cmd],
                capture_output=True, text=True, timeout=10,
            )
            return r.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    def set_wifi_proxy(self, host: str, port: int) -> dict:
        self._sh(f"settings put global http_proxy {host}:{port}")
        return {"ok": True, "method": "wifi_proxy", "host": host, "port": port}

    def clear_proxy(self) -> dict:
        self._sh("settings put global http_proxy :0")
        return {"ok": True, "message": "Proxy cleared"}

    def set_vpn_app(self, app_package: str, server: str = "", port: int = 0) -> dict:
        installed = self._sh(f"pm list packages | grep {app_package}")
        if app_package not in installed:
            return {"ok": False, "err": f"{app_package} not installed"}
        self._sh(f"monkey -p {app_package} -c android.intent.category.LAUNCHER 1")
        return {"ok": True, "message": "VPN app launched"}

    def check_ip(self) -> str:
        ip = self._sh("curl -s ifconfig.me 2>/dev/null || curl -s api.ipify.org 2>/dev/null")
        return ip.strip()

    def get_proxy_status(self) -> dict:
        proxy = self._sh("settings get global http_proxy")
        return {
            "proxy": proxy if proxy and proxy != ":0" else None,
            "external_ip": self.check_ip(),
        }
