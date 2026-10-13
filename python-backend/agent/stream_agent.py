"""Chimera Agent — ADB-based screen streaming and agent deployment.

Provides a fallback streaming path via ADB screenrecord for devices
that don't have the full scrcpy-based H.264 pipeline running.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import threading

from utils.adb_utils import adb_cmd, adb_devices, find_adb

logger = logging.getLogger(__name__)

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class StreamAgent:

    def __init__(self) -> None:
        self.streams: dict[str, subprocess.Popen] = {}
        self.buffers: dict[str, bytes] = {}

    def start(self, serial: str) -> bool:
        if serial in self.streams and self.streams[serial].poll() is None:
            return True
        try:
            adb = find_adb()
            proc = subprocess.Popen(
                [
                    adb, "-s", serial, "shell",
                    "screenrecord", "--output-format=h264",
                    "--size=720x1280", "--bit-rate=2000000", "-",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=_CREATE_NO_WINDOW,
            )
            self.streams[serial] = proc
            self.buffers[serial] = b""

            def _reader() -> None:
                assert proc.stdout is not None
                while proc.poll() is None:
                    chunk = proc.stdout.read(4096)
                    if chunk:
                        self.buffers[serial] = chunk
                    else:
                        break

            threading.Thread(target=_reader, daemon=True).start()
            logger.info("Stream started: %s", serial)
            return True
        except Exception as exc:
            logger.error("Stream failed %s: %s", serial, exc)
            return False

    def stop(self, serial: str) -> None:
        proc = self.streams.pop(serial, None)
        if proc is not None:
            proc.terminate()
        self.buffers.pop(serial, None)

    def get_frame(self, serial: str) -> bytes:
        return self.buffers.get(serial, b"")

    def screenshot(self, serial: str) -> bytes:
        tmp = os.path.join(tempfile.gettempdir(), f"chimera_shot_{serial}.png")
        try:
            adb_cmd(serial, ["shell", "screencap", "-p", "/sdcard/chimera_shot.png"], timeout=10)
            adb_cmd(serial, ["pull", "/sdcard/chimera_shot.png", tmp], timeout=10)
            with open(tmp, "rb") as f:
                return f.read()
        except Exception:
            return b""

    def is_streaming(self, serial: str) -> bool:
        return serial in self.streams and self.streams[serial].poll() is None

    def list_active(self) -> list[str]:
        return [s for s, p in self.streams.items() if p.poll() is None]

    def install_on_device(self, serial: str) -> dict:
        jar = os.path.join(os.path.dirname(__file__), "scrcpy-server.jar")

        if not os.path.exists(jar):
            return {"ok": False, "error": "scrcpy-server.jar not found in agent/"}

        check = adb_cmd(serial, ["get-state"], timeout=5)

        if "device" not in check.stdout:
            return {"ok": False, "error": f"Device {serial} not connected"}

        result = adb_cmd(serial, ["push", jar, "/data/local/tmp/scrcpy-server.jar"], timeout=30)
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip()}

        return {"ok": True, "message": f"Agent installed on {serial}"}

    def install_on_all(self) -> list[dict]:
        devs = adb_devices()
        serials = [d["serial"] for d in devs if d["state"] == "device"]
        return [
            {**self.install_on_device(serial), "serial": serial}
            for serial in serials
        ]


stream_agent = StreamAgent()
