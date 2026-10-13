"""One-click full device setup: agent + platforms + accessibility + self-test."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time

from utils.adb_utils import adb_cmd, adb_devices, find_adb, is_adb_available
from utils.ws_manager import ws_manager

logger = logging.getLogger(__name__)

AGENT_APK_PATH = os.path.join(os.path.dirname(__file__), "..", "agent", "chimera-agent.apk")
SCRCPY_JAR_PATH = os.path.join(os.path.dirname(__file__), "..", "agent", "scrcpy-server.jar")
AGENT_PACKAGE = "com.chimera.agent"

_setup_cancelled: dict[str, bool] = {}


async def _run_with_timeout(coro, timeout_sec: int, default=None):
    try:
        return await asyncio.wait_for(coro, timeout=timeout_sec)
    except asyncio.TimeoutError:
        logger.warning("Operation timed out after %ds", timeout_sec)
        return default


async def cancel_setup(serial: str):
    _setup_cancelled[serial] = True


async def _check_package_installed(serial: str, package: str) -> bool:
    try:
        result = adb_cmd(serial, ["shell", "pm", "list", "packages"], timeout=10)
        return package in result.stdout
    except Exception:
        return False


async def fix_everything(serial: str) -> dict:
    """Fast 15-second device bootstrap."""
    from services.platform_detector import detect_and_save_platforms

    room = f"setup_{serial}"
    results: dict = {"steps": [], "success": True, "elapsed_ms": 0}
    start = time.time()
    _setup_cancelled.pop(serial, None)

    # Step 1: verify connection (0.5s max)
    await ws_manager.broadcast(room, {
        "step": 1, "total": 7, "label": "Finding device...", "percent": 5,
    })

    state = adb_cmd(serial, ["get-state"], timeout=3)

    if "device" not in state.stdout:
        try:
            from utils.adb_utils import adb_restart
            await adb_restart()
            state = adb_cmd(serial, ["get-state"], timeout=3)
        except Exception:
            state = type("R", (), {"stdout": ""})()

        if "device" not in state.stdout:
            results["success"] = False
            results["steps"].append({
                "step": 1, "status": "failed",
                "message": "Device not responding",
            })
            await ws_manager.broadcast(room, {
                "step": 1, "label": "Device not found", "percent": 5,
                "status": "error",
                "instructions": [
                    "Disconnect and reconnect USB cable",
                    "On phone: Settings → Developer Options → USB Debugging ON",
                    "Tap 'Allow' on the debugging prompt",
                    "If no Developer Options: About Phone → tap Build Number 7 times",
                ],
            })
            return results

    results["steps"].append({"step": 1, "status": "ok"})
    await ws_manager.broadcast(room, {
        "step": 1, "label": f"Device found: {serial}", "percent": 15,
    })

    # Cancellation check
    if _setup_cancelled.get(serial, False):
        _setup_cancelled.pop(serial, None)
        await ws_manager.broadcast(room, {"step": 2, "label": "Setup cancelled", "percent": 0, "status": "cancelled"})
        return {"success": False, "cancelled": True}

    # Step 2: check agent + install if missing (2s max)
    await ws_manager.broadcast(room, {
        "step": 2, "label": "Checking Chimera Agent...", "percent": 20,
    })

    agent_check = adb_cmd(serial, ["shell", "pm", "list", "packages"], timeout=5)
    agent_installed = "chimera" in agent_check.stdout

    if not agent_installed:
        await ws_manager.broadcast(room, {
            "step": 2, "label": "Installing agent...", "percent": 25,
        })

        if os.path.exists(AGENT_APK_PATH):
            r = adb_cmd(serial, ["install", "-r", "-g", AGENT_APK_PATH], timeout=30)
            agent_installed = r.returncode == 0

        if os.path.exists(SCRCPY_JAR_PATH):
            adb_cmd(serial, ["push", SCRCPY_JAR_PATH,
                 "/data/local/tmp/scrcpy-server.jar"], timeout=15)
        elif not os.path.exists(SCRCPY_JAR_PATH):
            try:
                from agent.chimera_agent import download_scrcpy_if_missing
                await download_scrcpy_if_missing()
                if os.path.exists(SCRCPY_JAR_PATH):
                    adb_cmd(serial, ["push", SCRCPY_JAR_PATH,
                         "/data/local/tmp/scrcpy-server.jar"], timeout=15)
            except Exception:
                pass

    status = "ok" if agent_installed else "warning"
    results["steps"].append({"step": 2, "status": status})
    await ws_manager.broadcast(room, {
        "step": 2,
        "label": "Agent ready" if agent_installed else "scrcpy-server installed",
        "percent": 40,
    })

    # Step 3: start agent + foreground service (1s)
    await ws_manager.broadcast(room, {
        "step": 3, "label": "Starting agent...", "percent": 45,
    })

    if agent_installed:
        adb_cmd(serial, ["shell", "am", "force-stop", AGENT_PACKAGE], timeout=3)
        await asyncio.sleep(0.3)
        adb_cmd(serial, ["shell", "am", "start",
                "-n", f"{AGENT_PACKAGE}/.MainActivity"], timeout=5)

    results["steps"].append({"step": 3, "status": "ok"})

    # Cancellation check
    if _setup_cancelled.get(serial, False):
        _setup_cancelled.pop(serial, None)
        await ws_manager.broadcast(room, {"step": 4, "label": "Setup cancelled", "percent": 0, "status": "cancelled"})
        return {"success": False, "cancelled": True}

    # Step 4: accessibility check (try auto, fallback manual)
    await ws_manager.broadcast(room, {
        "step": 4, "label": "Configuring accessibility...", "percent": 55,
    })

    adb_cmd(serial, ["shell", "settings", "put", "secure",
            "enabled_accessibility_services",
            f"{AGENT_PACKAGE}/{AGENT_PACKAGE}.AccessibilityService"], timeout=3)
    adb_cmd(serial, ["shell", "settings", "put", "secure",
            "accessibility_enabled", "1"], timeout=3)

    acc_check = adb_cmd(serial, ["shell", "settings", "get", "secure",
                        "enabled_accessibility_services"], timeout=3)
    acc_ok = "chimera" in acc_check.stdout.lower()

    if not acc_ok:
        adb_cmd(serial, ["shell", "am", "start",
                "-a", "android.settings.ACCESSIBILITY_SETTINGS"], timeout=5)
        results["steps"].append({
            "step": 4, "status": "manual",
            "requires_user_action": True,
            "message": "Enable Chimera Agent in Accessibility on phone",
        })
        await ws_manager.broadcast(room, {
            "step": 4, "label": "Enable accessibility on phone",
            "percent": 60, "status": "manual",
            "instructions": [
                "Look at your phone screen",
                "Find 'Chimera Agent' in the list",
                "Toggle the switch ON",
                "Tap 'Allow' on confirmation",
            ],
        })
    else:
        results["steps"].append({"step": 4, "status": "ok"})
        await ws_manager.broadcast(room, {
            "step": 4, "label": "Accessibility enabled", "percent": 65,
        })

    # Step 5: detect platforms (0.5s)
    await ws_manager.broadcast(room, {
        "step": 5, "label": "Scanning platforms...", "percent": 70,
    })

    platforms = await detect_and_save_platforms(serial)
    installed = [p for p in platforms if p.get("installed")]

    if not installed:
        results["steps"].append({
            "step": 5, "status": "warning",
            "message": "No social apps found",
            "hint": "Install Instagram/TikTok from Play Store",
        })
        await ws_manager.broadcast(room, {
            "step": 5, "label": "No social apps found", "percent": 75,
            "status": "warning",
            "instructions": [
                "Open Google Play Store on phone",
                "Install: Instagram, TikTok, Threads",
                "Then click 'Detect Again'",
            ],
        })
    else:
        names = ", ".join(p.get("name", p.get("platform", "?")) for p in installed)
        results["steps"].append({
            "step": 5, "status": "ok",
            "message": f"Found: {names}",
        })
        await ws_manager.broadcast(room, {
            "step": 5, "label": f"Found {len(installed)} apps: {names}",
            "percent": 85,
        })

    # Step 6: get device info
    model = adb_cmd(serial, ["shell", "getprop", "ro.product.model"], timeout=3).stdout.strip()
    android = adb_cmd(serial, ["shell", "getprop", "ro.build.version.release"], timeout=3).stdout.strip()

    results["device"] = {"model": model, "android": android, "serial": serial}
    results["platforms"] = installed

    # Cancellation check
    if _setup_cancelled.get(serial, False):
        _setup_cancelled.pop(serial, None)
        await ws_manager.broadcast(room, {"step": 7, "label": "Setup cancelled", "percent": 0, "status": "cancelled"})
        return {"success": False, "cancelled": True}

    # Step 7: self-test
    await ws_manager.broadcast(room, {
        "step": 7, "label": "Running self-test...", "percent": 92,
    })

    test_results = await run_agent_self_test(serial)
    results["self_test"] = test_results

    await ws_manager.broadcast(room, {
        "step": 7, "label": f"Self-test: {test_results['summary']}",
        "percent": 98,
        "status": "ok" if test_results["all_passed"] else "warning",
        "tests": test_results,
    })

    # Final
    elapsed = int((time.time() - start) * 1000)
    results["elapsed_ms"] = elapsed
    overall = "ok" if len(installed) > 0 else "partial"
    results["success"] = overall == "ok"

    await ws_manager.broadcast(room, {
        "step": 8, "label": f"Ready! {model} (Android {android}) — {elapsed}ms",
        "percent": 100, "status": overall,
        "platforms": [p.get("name", p.get("platform", "")) for p in installed],
        "elapsed_ms": elapsed,
    })

    logger.info("Device setup complete for %s in %dms: %d platforms",
                serial, elapsed, len(installed))
    return results


async def fix_all_devices() -> list[dict]:
    """Run fix_everything on ALL connected devices."""
    try:
        serials = [d["serial"] for d in adb_devices() if d["state"] == "device"]
    except Exception:
        serials = []

    results = []
    for serial in serials:
        r = await fix_everything(serial)
        results.append(r)
    return results


async def run_agent_self_test(serial: str) -> dict:
    """Run quick tests to verify agent capabilities."""
    from services.platform_detector import get_screen_size

    results: dict = {}
    sw, sh = get_screen_size(serial)

    # Test 1: tap (in safe corner)
    try:
        adb_cmd(serial, ["shell", "input", "tap", "10", "10"], timeout=3)
        results["tap"] = "ok"
    except Exception:
        results["tap"] = "fail"

    # Test 2: swipe
    try:
        adb_cmd(serial, ["shell", "input", "swipe",
                str(sw // 2), str(sh // 2), str(sw // 2), str(sh // 2 - 100), "300"], timeout=3)
        results["swipe"] = "ok"
    except Exception:
        results["swipe"] = "fail"

    # Test 3: screenshot
    try:
        png = adb_cmd(serial, ["shell", "screencap", "-p"], timeout=5)
        results["screenshot"] = "ok" if len(png.stdout) > 1000 else "fail"
        results["screenshot_size"] = len(png.stdout)
    except Exception:
        results["screenshot"] = "fail"
        results["screenshot_size"] = 0

    # Test 4: uiautomator dump
    try:
        dump = adb_cmd(serial, ["shell", "uiautomator", "dump", "/dev/stdout"], timeout=8)
        results["uiautomator"] = "ok" if "<hierarchy" in dump.stdout else "fail"
    except Exception:
        results["uiautomator"] = "fail"

    # Test 5: text input
    try:
        adb_cmd(serial, ["shell", "input", "text", "test"], timeout=3)
        for _ in range(4):
            adb_cmd(serial, ["shell", "input", "keyevent", "KEYCODE_DEL"], timeout=2)
        results["text_input"] = "ok"
    except Exception:
        results["text_input"] = "fail"

    passed = sum(1 for v in results.values() if v == "ok")
    total = sum(1 for k in results if not k.endswith("_size"))
    results["summary"] = f"{passed}/{total} tests passed"
    results["all_passed"] = passed == total

    logger.info("Self-test for %s: %s", serial, results["summary"])
    return results


async def troubleshoot() -> dict:
    """Run comprehensive ADB diagnostics."""
    result: dict = {
        "adb_installed": False,
        "adb_version": "",
        "devices": [],
        "suggestions": [],
    }

    if not is_adb_available():
        result["suggestions"].append("ADB is not installed. Download Android Platform Tools and add to PATH.")
        return result

    try:
        adb = find_adb()
        import subprocess
        ver = subprocess.run(
            [adb, "version"], capture_output=True, text=True, timeout=5,
        )
        if ver.returncode == 0:
            result["adb_installed"] = True
            m = re.search(r"(\d+\.\d+\.\d+)", ver.stdout)
            if m:
                result["adb_version"] = m.group(1)
        else:
            result["suggestions"].append("ADB found but returned error. Reinstall Android Platform Tools.")
            return result
    except Exception:
        result["suggestions"].append("Could not run ADB. Check installation.")
        return result

    try:
        devs = adb_devices()
        for d in devs:
            serial = d["serial"]
            state = d["state"]
            result["devices"].append({"serial": serial, "state": state})

            if state == "unauthorized":
                result["suggestions"].append(
                    f"Device {serial} is 'unauthorized'. Tap 'Allow' on the phone's USB debugging prompt."
                )
                result["suggestions"].append(
                    "If no prompt appears: revoke USB debugging in Developer Options, then re-enable."
                )
            elif state == "offline":
                result["suggestions"].append(
                    f"Device {serial} is 'offline'. Try disconnecting and reconnecting USB."
                )
            elif state == "no permissions":
                result["suggestions"].append(
                    f"Device {serial} has no permissions. On Linux, check udev rules. On Windows, install USB drivers."
                )
    except Exception:
        result["suggestions"].append("Could not list devices.")

    if not result["devices"]:
        result["suggestions"].append("No devices found. Check USB cable and USB debugging settings.")

    return result
