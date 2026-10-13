"""iOS device manager — device discovery, supervised pairing, tunnel, WDA, port forwarding.

Implements all device lifecycle operations from back60.md:
ЗАГРУЗКА, АВТОЗАПУСК, ОЧИСТКА, TUNNEL, WDA, IMAGE, ПОДГОТОВКА, ОСТАНОВКА, ПЕРЕЗАПУСК.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.action_logger import log_info, log_warning, log_error

logger = logging.getLogger("chimera.ios_device_manager")

TUNNEL_MAX_RETRIES = 3
TUNNEL_WAIT_SECONDS = 10
WDA_WAIT_SECONDS = 15
REBOOT_WAIT_SECONDS = 90
DEFAULT_WDA_PORT = 8100


async def _run_cmd(cmd: str, timeout: float = 30.0) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="replace")
        return proc.returncode or 0, output
    except asyncio.TimeoutError:
        return 124, "timeout"
    except Exception as exc:
        return 1, str(exc)


@dataclass
class DeviceInfo:
    udid: str
    model: str
    name: str
    wda_port: int = DEFAULT_WDA_PORT
    tunnel_pid: int = -1
    wda_pid: int = -1
    forward_pid: int = -1
    status: str = "disconnected"


@dataclass
class IOSDeviceManager:
    devices: dict[str, DeviceInfo] = field(default_factory=dict)
    _recovery_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _ios_bin: str = "ios"
    _cfg_dir: str = ""

    async def scan_devices(self) -> list[DeviceInfo]:
        await log_info("device_scan", command="ios list --details")
        code, output = await _run_cmd(f"{self._ios_bin} list --details")
        if code != 0:
            await log_error("device_scan", error=output)
            return []

        found: list[DeviceInfo] = []
        import json
        try:
            data = json.loads(output)
            device_list = data.get("deviceList", []) if isinstance(data, dict) else data
            for d in device_list:
                udid = d.get("serialNumber", d.get("udid", ""))
                model = d.get("productType", d.get("deviceName", "unknown"))
                if udid:
                    info = DeviceInfo(udid=udid, model=model, name=model)
                    found.append(info)
                    self.devices[udid] = info
                    await log_info("device_found", device=model, udid=udid[:20] + "...")
        except json.JSONDecodeError:
            for line in output.strip().splitlines():
                if "iPhone" in line or "iPad" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        model = parts[0]
                        udid = parts[1].strip("()")
                        info = DeviceInfo(udid=udid, model=model, name=model)
                        found.append(info)
                        self.devices[udid] = info
                        await log_info("device_found", device=model, udid=udid[:20] + "...")

        await log_info("device_scan", total=len(found))
        return found

    async def load_devices(self, device_configs: list[dict[str, Any]]) -> list[DeviceInfo]:
        loaded: list[DeviceInfo] = []
        for cfg in device_configs:
            udid = cfg.get("udid", "")
            model = cfg.get("model", "unknown")
            port = cfg.get("wda_port", DEFAULT_WDA_PORT)
            info = DeviceInfo(udid=udid, model=model, name=model, wda_port=port)
            self.devices[udid] = info
            loaded.append(info)
            await log_info("device_loaded", device=model, udid=udid[:20] + "...")
        await log_info("device_loaded", count=len(loaded))
        return loaded

    async def supervised_pair(
        self,
        udid: str,
        p12_file: str | None = None,
        password: str = "go-ios-auto",
        force: bool = False,
        device_id: str | None = None,
    ) -> bool:
        short_udid = udid[:20] + "..."
        action = "supervised_pair_force" if force else "supervised_pair"
        await log_info(action, device_id=device_id, udid=short_udid)

        p12 = p12_file or f"{self._cfg_dir}/{udid}/supervision_cert.p12"
        cmd = f"{self._ios_bin} pair --udid={udid} --p12file={p12} --password={password}"
        await log_info("supervised_pair", device_id=device_id, command=cmd)

        code, output = await _run_cmd(cmd)
        if code == 0 or "success" in output.lower():
            await log_info("supervised_pair_ok", device_id=device_id, udid=short_udid)
            return True

        await log_error("supervised_pair", device_id=device_id,
                        udid=short_udid, error=output)
        return False

    async def cleanup_system(self, device_id: str | None = None) -> None:
        await log_info("cleanup_start", device_id=device_id)

        await log_info("cleanup_kill_processes", device_id=device_id)
        await _run_cmd("pkill -f 'ios tunnel' || true")
        await _run_cmd("pkill -f 'ios runwda' || true")
        await _run_cmd("pkill -f 'ios forward' || true")

        await log_info("cleanup_ports", device_id=device_id)
        for port in [8100, 8101, 8102, 8103]:
            await _run_cmd(f"lsof -ti:{port} | xargs kill -9 2>/dev/null || true")

        await log_info("cleanup_forwards", device_id=device_id)
        await _run_cmd(f"{self._ios_bin} forward --remove-all 2>/dev/null || true")
        await log_info("cleanup_forwards", device_id=device_id, status="cleared")

        await log_info("cleanup_complete", device_id=device_id)

    async def cleanup_port(self, port: int, device_id: str | None = None) -> None:
        await log_info("port_cleanup", device_id=device_id, port=port)
        await _run_cmd(f"lsof -ti:{port} | xargs kill -9 2>/dev/null || true")
        await log_info("port_cleanup", device_id=device_id, port=port, status="cleaned")

    async def setup_tunnel(
        self,
        udid: str,
        device_id: str | None = None,
    ) -> tuple[bool, int]:
        await log_info("tunnel_start", device_id=device_id, step=1)

        short_udid = udid[:20] + "..."
        await log_info("tunnel_check", device_id=device_id, udid=short_udid)

        code, output = await _run_cmd(f"{self._ios_bin} tunnel ls")
        if udid in output:
            await log_info("tunnel_existing", device_id=device_id, udid=short_udid)
            if udid in self.devices:
                self.devices[udid].tunnel_pid = -1
            return True, -1

        for attempt in range(1, TUNNEL_MAX_RETRIES + 1):
            await log_info("tunnel_attempt", device_id=device_id,
                           attempt=attempt, udid=short_udid)

            cmd = f"{self._ios_bin} tunnel start --userspace --udid={udid}"
            await log_info("tunnel_start", device_id=device_id, command=cmd)

            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            await log_info("tunnel_start", device_id=device_id,
                           status="waiting_init")

            try:
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(), timeout=TUNNEL_WAIT_SECONDS
                )
                output = stdout.decode("utf-8", errors="replace")

                if proc.returncode == 0:
                    pid = proc.pid or -1
                    await log_info("tunnel_running", device_id=device_id,
                                   pid=pid, attempt=attempt)
                    if udid in self.devices:
                        self.devices[udid].tunnel_pid = pid
                    return True, pid

                await log_warning("tunnel_failed", device_id=device_id,
                                  code=proc.returncode, attempt=attempt)

            except asyncio.TimeoutError:
                code_check, ls_output = await _run_cmd(f"{self._ios_bin} tunnel ls")
                if udid in ls_output:
                    await log_info("tunnel_existing", device_id=device_id,
                                   udid=short_udid, attempt=attempt)
                    return True, proc.pid or -1

                await log_warning("tunnel_failed", device_id=device_id,
                                  attempt=attempt, tunnel_ls=ls_output[:200])

        await log_error("tunnel_failed", device_id=device_id,
                        message="All attempts exhausted")
        return False, -1

    async def mount_developer_image(
        self,
        udid: str,
        device_id: str | None = None,
    ) -> bool:
        await log_info("image_mount", device_id=device_id)

        code, output = await _run_cmd(
            f"{self._ios_bin} image mount --udid={udid}", timeout=30.0
        )
        if code == 0 or "already" in output.lower() or "ok" in output.lower():
            await log_info("image_mount_ok", device_id=device_id)
            return True

        await log_error("image_mount", device_id=device_id, error=output)
        return False

    async def start_wda(
        self,
        udid: str,
        wda_port: int = DEFAULT_WDA_PORT,
        bundle_id: str = "com.secretup.app.xctrunner",
        xc_test_config: str = "SecretUploader.xctest",
        device_id: str | None = None,
    ) -> tuple[bool, int]:
        await log_info("wda_start", device_id=device_id, step=2)

        if not await self.mount_developer_image(udid, device_id):
            return False, -1

        cmd = (
            f"{self._ios_bin} --verbose runwda --udid={udid} "
            f"--bundleid={bundle_id} --testrunnerbundleid={bundle_id} "
            f"--xctestconfig={xc_test_config}"
        )
        await log_info("wda_start", device_id=device_id, command=cmd)

        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await log_info("wda_start", device_id=device_id,
                       status="waiting_app_load")

        try:
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=WDA_WAIT_SECONDS
            )
            output = stdout.decode("utf-8", errors="replace")

            if proc.returncode == 0 and ("ServerURL" in output or "WebDriverAgent" in output):
                pid = proc.pid or -1
                await log_info("wda_running", device_id=device_id, pid=pid)
                if udid in self.devices:
                    self.devices[udid].wda_pid = pid
                return True, pid

            await log_info("wda_log_received", device_id=device_id)

            if proc.returncode is not None and proc.returncode != 0:
                await log_error("wda_failed", device_id=device_id,
                                code=proc.returncode)
                return False, -1

            pid = proc.pid or -1
            await log_info("wda_running", device_id=device_id, pid=pid)
            return True, pid

        except asyncio.TimeoutError:
            if proc.returncode is None:
                pid = proc.pid or -1
                await log_info("wda_running", device_id=device_id, pid=pid)
                return True, pid
            await log_error("wda_failed", device_id=device_id, error="timeout")
            return False, -1

    async def setup_port_forward(
        self,
        udid: str,
        local_port: int = DEFAULT_WDA_PORT,
        remote_port: int = DEFAULT_WDA_PORT,
        device_id: str | None = None,
    ) -> tuple[bool, int]:
        await log_info("port_forward_start", device_id=device_id,
                       step=3, local=local_port, remote=remote_port)

        await self.cleanup_port(local_port, device_id)

        cmd = f"{self._ios_bin} forward {local_port} {remote_port} --udid={udid}"
        await log_info("port_forward_start", device_id=device_id, command=cmd)

        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await asyncio.sleep(3.0)

        if proc.returncode is None:
            pid = proc.pid or -1
            await log_info("port_forward_running", device_id=device_id, pid=pid)
            if udid in self.devices:
                self.devices[udid].forward_pid = pid
            return True, pid

        await log_error("port_forward_start", device_id=device_id,
                        code=proc.returncode)
        return False, -1

    async def check_wda_responsive(self, port: int = DEFAULT_WDA_PORT) -> bool:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"http://localhost:{port}/status")
                if resp.status_code == 200:
                    return True
        except Exception:
            pass
        return False

    async def launch_device(
        self,
        udid: str,
        wda_port: int = DEFAULT_WDA_PORT,
        device_id: str | None = None,
    ) -> bool:
        device = self.devices.get(udid)
        device_name = device.name if device else udid[:15]

        await log_info("device_launch", device_id=device_id,
                       device=device_name, udid=udid, port=wda_port)

        await self.cleanup_port(wda_port, device_id)

        tunnel_ok, tunnel_pid = await self.setup_tunnel(udid, device_id)
        if not tunnel_ok:
            await log_error("tunnel_failed", device_id=device_id,
                            device=device_name, step=1)
            return False

        wda_ok, wda_pid = await self.start_wda(udid, wda_port, device_id=device_id)
        if not wda_ok:
            await log_error("wda_failed", device_id=device_id,
                            device=device_name, step=2)
            return False

        fwd_ok, fwd_pid = await self.setup_port_forward(
            udid, wda_port, wda_port, device_id
        )
        if not fwd_ok:
            await log_error("port_forward_start", device_id=device_id,
                            device=device_name, step=3)
            return False

        responsive = await self.check_wda_responsive(wda_port)
        if responsive:
            await log_info("wda_recovery_complete", device_id=device_id,
                           device=device_name, url=f"http://localhost:{wda_port}")

        if device:
            device.status = "online"
            device.tunnel_pid = tunnel_pid
            device.wda_pid = wda_pid
            device.forward_pid = fwd_pid

        return True

    async def stop_device(
        self,
        udid: str,
        device_id: str | None = None,
    ) -> None:
        device = self.devices.get(udid)
        device_name = device.name if device else udid[:15]
        wda_port = device.wda_port if device else DEFAULT_WDA_PORT

        await log_info("stop_device", device_id=device_id,
                       device=device_name, port=wda_port)

        if device and device.tunnel_pid > 0:
            await log_info("stop_tunnel", device_id=device_id, pid=device.tunnel_pid)
            await _run_cmd(f"kill {device.tunnel_pid} 2>/dev/null || true")
            await log_info("stop_tunnel", device_id=device_id, status="terminated")

        if device and device.wda_pid > 0:
            await log_info("stop_wda", device_id=device_id, pid=device.wda_pid)
            await _run_cmd(f"kill {device.wda_pid} 2>/dev/null || true")
            await log_info("stop_wda", device_id=device_id, status="terminated")

        if device and device.forward_pid > 0:
            await log_info("stop_forward", device_id=device_id, pid=device.forward_pid)
            await _run_cmd(f"kill {device.forward_pid} 2>/dev/null || true")
            await log_info("stop_forward", device_id=device_id, status="terminated")

        await self.cleanup_port(wda_port, device_id)

        if device:
            device.status = "disconnected"
            device.tunnel_pid = -1
            device.wda_pid = -1
            device.forward_pid = -1

        await log_info("stop_complete", device_id=device_id, device=device_name)

    async def restart_device(
        self,
        udid: str,
        device_id: str | None = None,
    ) -> bool:
        device = self.devices.get(udid)
        device_name = device.name if device else udid[:15]

        await log_info("restart_start", device_id=device_id, device=device_name)

        async with self._recovery_lock:
            await log_info("restart_recovery_lock", device_id=device_id,
                           device=device_name)

            await log_info("restart_cleanup", device_id=device_id, device=device_name)
            await self.cleanup_system(device_id)

            await self.supervised_pair(udid, device_id=device_id)

            success = await self.launch_device(udid, device_id=device_id)

            if not success:
                await log_info("restart_fallback", device_id=device_id,
                               device=device_name)
                wda_port = device.wda_port if device else DEFAULT_WDA_PORT
                await self.cleanup_port(wda_port, device_id)
                await self.supervised_pair(udid, device_id=device_id)
                success = await self.launch_device(udid, device_id=device_id)

            if success:
                await log_info("restart_complete", device_id=device_id,
                               device=device_name)
            else:
                await log_error("restart_error", device_id=device_id,
                                device=device_name)

            return success

    async def wda_recovery(
        self,
        udid: str,
        reason: str = "connection_refused",
        device_id: str | None = None,
    ) -> bool:
        device = self.devices.get(udid)
        device_name = device.name if device else udid[:15]

        if reason == "connection_reset":
            await log_info("wda_connection_reset", device_id=device_id,
                           device=device_name)
        else:
            await log_info("wda_connection_refused", device_id=device_id,
                           device=device_name)

        await log_info("wda_recovery", device_id=device_id, device=device_name)

        await self.supervised_pair(udid, force=True, device_id=device_id)

        success = await self.launch_device(udid, device_id=device_id)

        if success:
            await log_info("wda_recovery_complete", device_id=device_id,
                           device=device_name)
        else:
            await log_error("wda_recovery_failed", device_id=device_id,
                            device=device_name)

        return success

    async def autostart_devices(
        self,
        device_id: str | None = None,
    ) -> dict[str, Any]:
        await log_info("autostart_check", device_id=device_id)

        found = await self.scan_devices()
        if not found:
            return {"success": 0, "errors": 0, "devices": []}

        total = len(found)
        await log_info("autostart_begin", device_id=device_id, count=total)

        success = 0
        errors = 0
        results: list[dict[str, Any]] = []

        for device in found:
            await log_info("autostart_device", device_id=device_id,
                           device=device.name)

            await self.supervised_pair(device.udid, device_id=device_id)

            ok = await self.launch_device(device.udid, device.wda_port, device_id)
            if ok:
                success += 1
                results.append({"device": device.name, "status": "ok"})
            else:
                errors += 1
                results.append({"device": device.name, "status": "error"})

        await log_info("autostart_complete", device_id=device_id,
                       success=success, errors=errors)

        return {"success": success, "errors": errors, "devices": results}

    async def wait_for_device_reboot(
        self,
        udid: str,
        timeout: float = REBOOT_WAIT_SECONDS,
        device_id: str | None = None,
    ) -> bool:
        await log_info("device_reboot_wait", device_id=device_id)

        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(5.0)
            code, output = await _run_cmd(f"{self._ios_bin} list")
            if udid in output:
                await log_info("device_usb_found", device_id=device_id)
                return True

        await log_warning("device_reboot_wait", device_id=device_id,
                          status="timeout")
        return False


ios_device_manager = IOSDeviceManager()
