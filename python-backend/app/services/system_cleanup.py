"""System cleanup — kill ios processes, clean ports, clear forwards (ОЧИСТКА)."""
from __future__ import annotations

import asyncio
import logging
import platform as plat
from typing import Any

from app.database import SessionLocal
from app.models.action_log import ActionLog
from app.api._hub import hub

logger = logging.getLogger("chimera.system_cleanup")


class SystemCleanup:
    async def full_cleanup(self) -> dict[str, Any]:
        await self._log("cleanup_start", "info", {"stage": "begin"})
        results: dict[str, Any] = {}
        results["ios_processes_killed"] = await self._kill_ios_processes()
        results["ports_cleaned"] = await self._clean_ports()
        results["forwards_cleared"] = await self._clear_forwards()
        await self._log("cleanup_complete", "info", results)
        return results

    async def _kill_ios_processes(self) -> int:
        await self._log("cleanup_kill_ios", "info", {"action": "killing ios processes"})
        try:
            if plat.system() == "Darwin":
                cmd = "pkill -f 'ios tunnel|ios forward|ios runwda' 2>/dev/null || true"
            else:
                cmd = "taskkill /F /IM ios.exe 2>nul & exit /b 0"
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            return stdout.decode().count("kill") if stdout else 0
        except Exception as e:
            logger.error("Kill ios processes: %s", e)
            return 0

    async def _clean_ports(self, ports: list[int] | None = None) -> int:
        if ports is None:
            ports = list(range(8100, 8111))
        cleaned = 0
        for port in ports:
            try:
                if plat.system() == "Darwin":
                    cmd = f"lsof -ti:{port} | xargs kill -9 2>/dev/null || true"
                else:
                    cmd = f'powershell -c "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"'
                proc = await asyncio.create_subprocess_shell(
                    cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=5)
                cleaned += 1
            except Exception:
                pass
        await self._log("cleanup_ports", "info", {"ports": ports, "cleaned": cleaned})
        return cleaned

    async def _clear_forwards(self) -> bool:
        await self._log("cleanup_forwards", "info", {"action": "clearing all forwards"})
        try:
            if plat.system() == "Darwin":
                cmd = "pkill -f 'ios forward' 2>/dev/null || true"
            else:
                cmd = 'taskkill /F /FI "WINDOWTITLE eq ios forward*" 2>nul & exit /b 0'
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10)
            return True
        except Exception as e:
            logger.error("Clear forwards: %s", e)
            return False

    async def cleanup_device(self, udid: str, port: int = 8100) -> dict[str, Any]:
        await self._log("cleanup_device", "info", {"udid": udid, "port": port})
        results: dict[str, Any] = {"udid": udid}

        for label, pattern in [("tunnel", f"ios tunnel.*{udid}"), ("wda", f"ios.*runwda.*{udid}")]:
            try:
                if plat.system() == "Darwin":
                    cmd = f"pkill -f '{pattern}' 2>/dev/null || true"
                else:
                    cmd = f'wmic process where "CommandLine like \'%{pattern}%\'" call terminate 2>nul & exit /b 0'
                proc = await asyncio.create_subprocess_shell(
                    cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=5)
                results[f"{label}_killed"] = True
            except Exception:
                results[f"{label}_killed"] = False

        try:
            if plat.system() == "Darwin":
                cmd = f"lsof -ti:{port} | xargs kill -9 2>/dev/null || true"
            else:
                cmd = f'powershell -c "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"'
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
            results["port_cleaned"] = True
        except Exception:
            results["port_cleaned"] = False

        await self._log("cleanup_device_done", "info", results)
        return results

    async def _log(self, action_type: str, level: str, details: dict) -> None:
        try:
            async with SessionLocal() as session:
                log = ActionLog(level=level, action_type=action_type, details=details)
                session.add(log)
                await session.commit()
                await session.refresh(log)
                await hub.broadcast("logs", {
                    "id": log.id, "created_at": log.created_at.isoformat(),
                    "level": log.level, "action_type": log.action_type,
                    "details": log.details,
                })
        except Exception as e:
            logger.error("Failed to log %s: %s", action_type, e)


system_cleanup = SystemCleanup()
