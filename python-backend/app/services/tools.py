"""Locate and provision external CLI tools (ADB, libimobiledevice).

Chimera does not require these utilities to be on the system PATH. We look in a
private install root under %LOCALAPPDATA%\\Chimera\\tools first, so the backend
can find adb/idevice_id that the app installed itself.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path


def tools_root() -> Path:
    """Return the Chimera-managed tools directory."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.local/share")
    return Path(base) / "Chimera" / "tools"


def _candidate_paths(binary: str) -> list[Path]:
    """Candidate locations to look for a binary, in priority order."""
    root = tools_root()
    candidates: list[Path] = []
    if binary == "adb":
        candidates.append(root / "platform-tools" / "adb.exe")
        candidates.append(root / "platform-tools" / "adb")
    elif binary == "scrcpy":
        candidates.append(root / "scrcpy" / "scrcpy.exe")
        candidates.append(root / "scrcpy" / "scrcpy")
    elif binary in {"idevice_id", "ideviceinfo"}:
        exe = f"{binary}.exe"
        candidates.append(root / "imobiledevice" / exe)
        candidates.append(root / "imobiledevice" / binary)
    return candidates


def resolve(binary: str) -> str | None:
    """Return an absolute path to the binary, or None if not found.

    Checks the private Chimera tools dir first, then falls back to PATH.
    """
    for candidate in _candidate_paths(binary):
        if candidate.exists():
            return str(candidate)
    which = shutil.which(binary)
    if which:
        return which
    # On Windows the stem may need .exe appended
    if os.name == "nt":
        which = shutil.which(f"{binary}.exe")
        if which:
            return which
    return None


def status() -> dict:
    """Snapshot of which tools Chimera currently sees."""
    adb = resolve("adb")
    idevice = resolve("idevice_id")
    return {
        "adb": {
            "available": adb is not None,
            "path": adb,
        },
        "ios": {
            "available": idevice is not None,
            "path": idevice,
        },
        "tools_root": str(tools_root()),
    }


def _installer_script() -> Path | None:
    """Locate installer/download-tools.ps1 next to the backend module."""
    here = Path(__file__).resolve()
    # python-backend layout: app/services/tools.py -> project/installer/…
    for parent in here.parents:
        candidate = parent / "installer" / "download-tools.ps1"
        if candidate.exists():
            return candidate
    return None


async def install(target: str = "all", timeout: float = 300.0) -> dict:
    """Run the PowerShell installer for the requested target.

    target: "all" | "adb" | "ios"
    """
    if target not in {"all", "adb", "ios"}:
        raise ValueError(f"invalid install target: {target}")
    script = _installer_script()
    if script is None:
        return {
            "ok": False,
            "error": "download-tools.ps1 not found",
            "target": target,
        }
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-Only",
        target,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return {"ok": False, "error": "powershell not available", "target": target}
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return {"ok": False, "error": "installer timeout", "target": target}
    ok = (proc.returncode or 0) == 0
    return {
        "ok": ok,
        "target": target,
        "returncode": proc.returncode,
        "stdout": stdout.decode("utf-8", errors="replace")[-4000:],
        "stderr": stderr.decode("utf-8", errors="replace")[-4000:],
        "status": status(),
    }
