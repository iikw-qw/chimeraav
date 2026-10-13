"""
iOS Screenshot Streaming: периодические скриншоты → MJPEG-стриминг.
Зависит от: ios_device, appium_manager, asyncio, websockets
"""

import asyncio
import base64
import io
import time
from typing import Dict, Optional, Set

import structlog

from ios_bridge.ios_device import IOSDevice
from ios_bridge.appium_manager import appium_manager

logger = structlog.get_logger()


class ScreenshotService:
    def __init__(self):
        self.active_streams: Dict[str, asyncio.Task] = {}
        self.viewers: Dict[str, Set] = {}
        self.fps_targets: Dict[str, int] = {}
        self.last_frames: Dict[str, bytes] = {}
        self.stats: Dict[str, Dict] = {}

    async def start_stream(self, udid: str, fps: int = 5, use_appium: bool = True):
        """Запуск стриминга скриншотов для iOS-устройства"""
        if udid in self.active_streams:
            logger.warning("ios_stream.already_active", udid=udid)
            return

        self.fps_targets[udid] = min(fps, 15)
        self.viewers[udid] = set()
        self.stats[udid] = {
            "frames_sent": 0,
            "start_time": time.time(),
            "avg_capture_ms": 0,
            "last_frame_time": 0,
        }

        task = asyncio.create_task(self._stream_loop(udid, use_appium))
        self.active_streams[udid] = task
        logger.info("ios_stream.started", udid=udid, fps=fps)

    async def stop_stream(self, udid: str):
        """Остановка стриминга"""
        task = self.active_streams.pop(udid, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.viewers.pop(udid, None)
        self.fps_targets.pop(udid, None)
        self.last_frames.pop(udid, None)
        self.stats.pop(udid, None)
        logger.info("ios_stream.stopped", udid=udid)

    async def _stream_loop(self, udid: str, use_appium: bool):
        """Основной цикл захвата скриншотов"""
        device = IOSDevice(udid)
        interval = 1.0 / self.fps_targets.get(udid, 5)

        while True:
            start = time.monotonic()

            try:
                if use_appium:
                    # Через Appium — base64 → JPEG
                    screenshot_b64 = await appium_manager.screenshot(udid)
                    if screenshot_b64:
                        frame_data = base64.b64decode(screenshot_b64)
                    else:
                        await asyncio.sleep(interval)
                        continue
                else:
                    # Через libimobiledevice — PNG → конвертация в JPEG
                    png_data = await device.screenshot()
                    if png_data:
                        frame_data = await self._convert_to_jpeg(png_data)
                    else:
                        await asyncio.sleep(interval)
                        continue

                capture_ms = (time.monotonic() - start) * 1000
                self.last_frames[udid] = frame_data

                # Обновление статистики
                stats = self.stats.get(udid, {})
                stats["frames_sent"] = stats.get("frames_sent", 0) + 1
                stats["last_frame_time"] = time.time()
                prev_avg = stats.get("avg_capture_ms", capture_ms)
                stats["avg_capture_ms"] = prev_avg * 0.9 + capture_ms * 0.1

                # Рассылка фрейма подключенным зрителям
                await self._broadcast_frame(udid, frame_data)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("ios_stream.capture_error", udid=udid, error=str(e))

            elapsed = time.monotonic() - start
            sleep_time = max(0, interval - elapsed)
            await asyncio.sleep(sleep_time)

    async def _convert_to_jpeg(self, png_data: bytes, quality: int = 75) -> bytes:
        """Конвертация PNG → JPEG для экономии трафика"""
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(png_data))
            if img.mode == "RGBA":
                img = img.convert("RGB")

            output = io.BytesIO()
            img.save(output, format="JPEG", quality=quality, optimize=True)
            return output.getvalue()
        except Exception:
            return png_data

    async def _broadcast_frame(self, udid: str, frame_data: bytes):
        """Отправка фрейма всем зрителям через WebSocket"""
        viewers = self.viewers.get(udid, set())
        if not viewers:
            return

        dead = set()
        for ws in viewers:
            try:
                await ws.send_bytes(frame_data)
            except Exception:
                dead.add(ws)

        viewers -= dead

    def add_viewer(self, udid: str, ws):
        """Добавление зрителя"""
        if udid not in self.viewers:
            self.viewers[udid] = set()
        self.viewers[udid].add(ws)
        logger.info("ios_stream.viewer_added", udid=udid, total=len(self.viewers[udid]))

    def remove_viewer(self, udid: str, ws):
        """Удаление зрителя"""
        viewers = self.viewers.get(udid, set())
        viewers.discard(ws)
        logger.info("ios_stream.viewer_removed", udid=udid, total=len(viewers))

    def get_last_frame(self, udid: str) -> Optional[bytes]:
        """Получение последнего кадра"""
        return self.last_frames.get(udid)

    def get_stream_info(self, udid: str) -> Optional[Dict]:
        """Информация о стриме"""
        if udid not in self.active_streams:
            return None

        stats = self.stats.get(udid, {})
        elapsed = time.time() - stats.get("start_time", time.time())
        frames = stats.get("frames_sent", 0)

        return {
            "udid": udid,
            "active": True,
            "fps_target": self.fps_targets.get(udid, 5),
            "fps_actual": round(frames / max(elapsed, 1), 1),
            "viewers": len(self.viewers.get(udid, set())),
            "frames_sent": frames,
            "avg_capture_ms": round(stats.get("avg_capture_ms", 0), 1),
            "uptime_seconds": int(elapsed),
        }

    def get_all_streams(self) -> list:
        """Список всех активных стримов"""
        return [
            self.get_stream_info(udid)
            for udid in self.active_streams
        ]

    async def set_fps(self, udid: str, fps: int):
        """Изменение FPS стрима"""
        if udid in self.fps_targets:
            self.fps_targets[udid] = min(fps, 15)
            # Перезапуск стрима с новым FPS
            await self.stop_stream(udid)
            await self.start_stream(udid, fps)

    async def take_screenshot(self, udid: str) -> Optional[bytes]:
        """Одиночный скриншот вне стрима"""
        # Если стрим уже идёт — вернуть последний кадр
        last = self.last_frames.get(udid)
        if last:
            return last

        try:
            screenshot_b64 = await appium_manager.screenshot(udid)
            if screenshot_b64:
                return base64.b64decode(screenshot_b64)
        except Exception as e:
            logger.error("ios_stream.screenshot_error", udid=udid, error=str(e))

        return None

    async def stop_all(self):
        """Остановка всех стримов"""
        udids = list(self.active_streams.keys())
        for udid in udids:
            await self.stop_stream(udid)


screenshot_service = ScreenshotService()
