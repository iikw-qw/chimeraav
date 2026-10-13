"""ADB-based H.264 stream producer.

Launches ``adb exec-out screenrecord --output-format=h264 -`` for a device
and splits the raw Annex-B byte stream into individual NAL units, feeding
each one into stream_manager via the existing relay pipeline.

screenrecord has a 180-second hard limit on most Android builds, so the
producer automatically restarts the subprocess when it exits cleanly.
"""

from __future__ import annotations

import asyncio
import logging
from typing import ClassVar

from app.services import tools as tools_svc
from app.services.stream_manager import ActiveStream, stream_manager
from app.services.stream_relay import handle_producer_frame

logger = logging.getLogger("chimera.adb_producer")

_START_CODE_4 = b"\x00\x00\x00\x01"
_START_CODE_3 = b"\x00\x00\x01"
_READ_SIZE = 65_536
_MAX_BUF = 2_000_000


class AdbStreamProducer:
    _active: ClassVar[dict[str, AdbStreamProducer]] = {}

    def __init__(self, device_id: str, serial: str) -> None:
        self.device_id = device_id
        self.serial = serial
        self._task: asyncio.Task | None = None
        self._proc: asyncio.subprocess.Process | None = None

    # ── public API ────────────────────────────────────────────────────

    @classmethod
    async def start(cls, device_id: str, serial: str) -> dict:
        existing = cls._active.get(device_id)
        if existing and existing._task and not existing._task.done():
            return {"ok": True, "message": "Стриминг уже запущен", "device_id": device_id}

        adb = tools_svc.resolve("adb")
        if adb is None:
            return {"ok": False, "message": "adb не найден"}

        producer = cls(device_id, serial)
        cls._active[device_id] = producer
        producer._task = asyncio.create_task(producer._loop(adb))

        await asyncio.sleep(0.3)
        if producer._task.done():
            cls._active.pop(device_id, None)
            try:
                producer._task.result()
            except Exception as exc:
                return {"ok": False, "message": str(exc)}
            return {"ok": False, "message": "Producer exited immediately"}

        return {
            "ok": True,
            "message": f"Стриминг запущен на {device_id}",
            "device_id": device_id,
            "method": "screenrecord",
        }

    @classmethod
    async def stop(cls, device_id: str) -> None:
        producer = cls._active.pop(device_id, None)
        if producer is None:
            return
        if producer._task and not producer._task.done():
            producer._task.cancel()
        if producer._proc and producer._proc.returncode is None:
            producer._proc.kill()
        if producer._task:
            try:
                await producer._task
            except (asyncio.CancelledError, Exception):
                pass

    @classmethod
    def is_running(cls, device_id: str) -> bool:
        p = cls._active.get(device_id)
        return p is not None and p._task is not None and not p._task.done()

    @classmethod
    async def stop_all(cls) -> None:
        for did in list(cls._active):
            await cls.stop(did)

    # ── internals ─────────────────────────────────────────────────────

    async def _get_resolution(self, adb: str) -> str | None:
        try:
            proc = await asyncio.create_subprocess_exec(
                adb, "-s", self.serial, "shell", "wm", "size",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            text = out.decode("utf-8", errors="replace").strip()
            for line in text.splitlines():
                if "x" in line:
                    parts = line.split(":")[-1].strip()
                    return parts
        except Exception:
            pass
        return None

    async def _loop(self, adb: str) -> None:
        stream: ActiveStream | None = None
        try:
            stream = await stream_manager.register_producer(self.device_id)
            res = await self._get_resolution(adb)
            stream.metadata = {
                "device_id": self.device_id,
                "source": "adb_screenrecord",
                "resolution": res,
            }
            if res:
                stream.stats.resolution = res
            logger.info("producer started: %s (serial=%s)", self.device_id, self.serial)

            while True:
                exited = await self._run_once(adb, stream)
                if not exited:
                    break
                logger.info("screenrecord exited (180s limit?), restarting: %s", self.device_id)
                await asyncio.sleep(0.2)

        except asyncio.CancelledError:
            logger.info("producer cancelled: %s", self.device_id)
        except Exception as exc:
            logger.error("producer error %s: %s", self.device_id, exc)
        finally:
            if stream is not None:
                await stream_manager.unregister_producer(self.device_id)
            self.__class__._active.pop(self.device_id, None)
            logger.info("producer stopped: %s", self.device_id)

    async def _run_once(self, adb: str, stream: ActiveStream) -> bool:
        """Run one screenrecord session. Returns True if exited cleanly
        (restart needed), False on error (stop)."""
        try:
            self._proc = await asyncio.create_subprocess_exec(
                adb, "-s", self.serial, "exec-out",
                "screenrecord", "--output-format=h264",
                "--bit-rate", "4000000",
                "-",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            logger.error("adb binary not found")
            return False

        assert self._proc.stdout is not None
        try:
            await self._read_and_relay(self._proc.stdout, stream)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("relay error %s: %s", self.device_id, exc)

        if self._proc.returncode is None:
            self._proc.kill()
        try:
            await self._proc.wait()
        except Exception:
            pass

        rc = self._proc.returncode or 0
        self._proc = None
        return rc == 0

    async def _read_and_relay(
        self, reader: asyncio.StreamReader, stream: ActiveStream,
    ) -> None:
        buf = bytearray()

        while True:
            data = await reader.read(_READ_SIZE)
            if not data:
                break
            buf.extend(data)

            while True:
                nal, rest = _split_next_nal(buf)
                if nal is None:
                    break
                buf = rest
                await handle_producer_frame(stream, nal)

        if len(buf) > 4:
            await handle_producer_frame(stream, bytes(buf))


def _split_next_nal(buf: bytearray) -> tuple[bytes | None, bytearray]:
    """Try to extract one complete NAL unit from *buf*.

    Returns ``(nal_bytes, remaining)`` or ``(None, buf)`` if no complete
    NAL is available yet.
    """
    if len(buf) < 8:
        return None, buf

    start = 0
    if buf[:4] == _START_CODE_4:
        start = 4
    elif buf[:3] == _START_CODE_3:
        start = 3
    else:
        idx4 = buf.find(_START_CODE_4)
        idx3 = buf.find(_START_CODE_3)
        if idx4 < 0 and idx3 < 0:
            if len(buf) > _MAX_BUF:
                return None, bytearray()
            return None, buf
        if idx4 >= 0 and idx3 >= 0:
            start = min(idx4, idx3)
        elif idx4 >= 0:
            start = idx4
        else:
            start = idx3
        del buf[:start]
        start = 4 if buf[:4] == _START_CODE_4 else 3

    idx4 = buf.find(_START_CODE_4, start)
    idx3 = buf.find(_START_CODE_3, start)

    if idx4 < 0 and idx3 < 0:
        if len(buf) > _MAX_BUF:
            return None, bytearray()
        return None, buf

    if idx4 >= 0 and idx3 >= 0:
        end = min(idx4, idx3)
    elif idx4 >= 0:
        end = idx4
    else:
        end = idx3

    nal = bytes(buf[:end])
    remaining = bytearray(buf[end:])
    return nal, remaining
