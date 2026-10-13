from utils.adb_utils import adb_cmd


class AntiDetect:
    def __init__(self, serial):
        self.serial = serial

    def _sh(self, c):
        return adb_cmd(self.serial, ["shell"] + c.split(), timeout=10).stdout.strip()

    def fingerprint(self):
        return {
            "android_id": self._sh("settings get secure android_id"),
            "serial": self._sh("getprop ro.serialno"),
            "model": self._sh("getprop ro.product.model"),
            "brand": self._sh("getprop ro.product.brand"),
            "mac": self._sh("cat /sys/class/net/wlan0/address 2>/dev/null"),
            "build": self._sh("getprop ro.build.fingerprint"),
        }

    def test(self):
        fp = self.fingerprint()
        r = {}
        for k, v in fp.items():
            r[k] = {"value": v, "ok": bool(v)}
        return r
