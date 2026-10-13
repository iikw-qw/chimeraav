"""AlertWatcher — auto-dismiss iOS popups/alerts via WDA."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.action_logger import log_info

logger = logging.getLogger("chimera.alert_watcher")

DISMISS_LABELS = [
    "OK", "Allow", "Allow Full Access", "Don't Allow", "Cancel",
    "Continue", "Not Now", "Later", "Dismiss", "Close",
    "Allow While Using App", "Allow Once", "I agree",
    "Accept", "Got It", "Skip", "No Thanks",
]

DISMISS_TIMEOUT = 5.0


class AlertWatcher:
    def __init__(self) -> None:
        self._active: dict[str, bool] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def is_active(self, device_name: str) -> bool:
        return self._active.get(device_name, False)

    async def enable(self, device_name: str, device_id: str | None = None, context: str = "") -> None:
        self._active[device_name] = True
        await log_info("alert_watcher_enabled", device_id=device_id,
                       device=device_name, context=context)

    async def disable(self, device_name: str, device_id: str | None = None, context: str = "") -> None:
        self._active[device_name] = False
        task = self._tasks.pop(device_name, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def start_watching(
        self,
        device_name: str,
        wda_port: int = 8100,
        device_id: str | None = None,
        poll_interval: float = 2.0,
    ) -> None:
        self._active[device_name] = True
        task = asyncio.create_task(
            self._watch_loop(device_name, wda_port, device_id, poll_interval)
        )
        self._tasks[device_name] = task

    async def _watch_loop(
        self,
        device_name: str,
        wda_port: int,
        device_id: str | None,
        poll_interval: float,
    ) -> None:
        import httpx

        while self._active.get(device_name, False):
            try:
                async with httpx.AsyncClient(timeout=DISMISS_TIMEOUT) as client:
                    resp = await client.get(f"http://127.0.0.1:{wda_port}/alert/text")
                    if resp.status_code == 200:
                        alert_data = resp.json()
                        alert_text = alert_data.get("value", "")
                        if alert_text:
                            for label in DISMISS_LABELS:
                                if label.lower() in alert_text.lower():
                                    await client.post(
                                        f"http://127.0.0.1:{wda_port}/alert/accept",
                                        json={"name": label},
                                    )
                                    await log_info(
                                        "alert_watcher_dismissed",
                                        device_id=device_id,
                                        device=device_name,
                                        alert=alert_text[:100],
                                        button=label,
                                    )
                                    break
            except Exception:
                pass
            await asyncio.sleep(poll_interval)

    async def auto_dismiss_alerts(
        self,
        device_name: str,
        wda_port: int = 8100,
        device_id: str | None = None,
        context: str = "",
    ) -> bool:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=DISMISS_TIMEOUT) as client:
                resp = await client.get(f"http://127.0.0.1:{wda_port}/alert/text")
                if resp.status_code == 200:
                    alert_data = resp.json()
                    alert_text = alert_data.get("value", "")
                    if alert_text:
                        if "Allow Full Access" in alert_text:
                            await client.post(
                                f"http://127.0.0.1:{wda_port}/alert/accept",
                                json={"name": "Allow Full Access"},
                            )
                            await log_info("alert_watcher_allow_access",
                                           device_id=device_id, device=device_name)
                            return True

                        await client.post(f"http://127.0.0.1:{wda_port}/alert/accept")
                        await log_info("alert_watcher_dismissed",
                                       device_id=device_id, device=device_name,
                                       alert=alert_text[:100], context=context)
                        return True
        except asyncio.TimeoutError:
            await log_info("alert_watcher_dismissed", device_id=device_id,
                           device=device_name, context=context, status="timeout")
        except Exception:
            pass
        return False

    def stop_all(self) -> None:
        self._active.clear()
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        self._tasks.clear()


alert_watcher = AlertWatcher()
