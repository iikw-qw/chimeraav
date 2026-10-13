from utils.adb_utils import adb_cmd


class ProxySetup:
    def __init__(self, serial):
        self.serial = serial

    def _sh(self, c):
        return adb_cmd(self.serial, ["shell"] + c.split(), timeout=10).stdout

    def set_wifi(self, host, port):
        self._sh(f"settings put global http_proxy {host}:{port}")
        return {"ok": True}

    def clear(self):
        self._sh("settings put global http_proxy :0")

    def check_ip(self):
        return self._sh("curl -s ifconfig.me 2>/dev/null||curl -s api.ipify.org 2>/dev/null").strip()

    def find_vpn_apps(self):
        apps = self._sh("pm list packages")
        vpns = [
            p.replace("package:", "")
            for p in apps.split("\n")
            if any(v in p for v in ["happ", "v2ray", "wireguard", "openvpn", "clash", "surfshark", "nord"])
        ]
        return vpns
