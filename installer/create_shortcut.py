"""Create desktop shortcut for Chimera with chimerafoto icon."""

import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def get_desktop_path() -> Path:
    system = platform.system()
    if system == "Windows":
        import ctypes.wintypes
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x0000, None, 0, buf)
        desktop = Path(buf.value) / "Desktop"
        if not desktop.exists():
            desktop = Path(os.environ.get("USERPROFILE", "~")) / "Desktop"
        if not desktop.exists():
            desktop = Path(os.environ.get("USERPROFILE", "~")) / "OneDrive" / "Рабочий стол"
        return desktop
    elif system == "Darwin":
        return Path.home() / "Desktop"
    else:
        return Path.home() / "Desktop"


def create_windows_shortcut(desktop: Path) -> None:
    try:
        import win32com.client  # type: ignore
        shell = win32com.client.Dispatch("WScript.Shell")
    except ImportError:
        ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$shortcut = $WshShell.CreateShortcut("{desktop / 'Chimera Desktop.lnk'}")
$shortcut.TargetPath = "{ROOT / 'run-desktop.bat'}"
$shortcut.WorkingDirectory = "{ROOT}"
$shortcut.IconLocation = "{ROOT / 'resources' / 'icon.ico'},0"
$shortcut.Description = "Chimera Desktop v9.0"
$shortcut.Save()
'''
        subprocess.run(
            ["powershell", "-Command", ps_script],
            check=True,
            capture_output=True,
        )
        print(f"Shortcut created: {desktop / 'Chimera Desktop.lnk'}")
        return

    shortcut_path = str(desktop / "Chimera Desktop.lnk")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = str(ROOT / "run-desktop.bat")
    shortcut.WorkingDirectory = str(ROOT)
    icon_path = ROOT / "resources" / "icon.ico"
    if icon_path.exists():
        shortcut.IconLocation = f"{icon_path},0"
    shortcut.Description = "Chimera Desktop v9.0"
    shortcut.save()
    print(f"Shortcut created: {shortcut_path}")


def create_linux_shortcut(desktop: Path) -> None:
    desktop_entry = f"""[Desktop Entry]
Name=Chimera
Comment=Chimera Desktop v9.0
Exec=bash -c "cd '{ROOT}' && npm run dev"
Icon={ROOT / 'resources' / 'icon.png'}
Type=Application
Categories=Utility;
Terminal=false
"""
    entry_path = desktop / "chimera.desktop"
    entry_path.write_text(desktop_entry)
    entry_path.chmod(0o755)
    print(f"Desktop entry created: {entry_path}")


def create_macos_shortcut(desktop: Path) -> None:
    app_dir = Path("/Applications/Chimera.app/Contents/MacOS")
    app_dir.mkdir(parents=True, exist_ok=True)

    script = f"""#!/bin/bash
cd "{ROOT}"
npm run dev
"""
    script_path = app_dir / "chimera"
    script_path.write_text(script)
    script_path.chmod(0o755)

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>chimera</string>
    <key>CFBundleName</key>
    <string>Chimera</string>
    <key>CFBundleIdentifier</key>
    <string>com.chimera.desktop</string>
    <key>CFBundleVersion</key>
    <string>9.0.0</string>
    <key>CFBundleIconFile</key>
    <string>icon</string>
</dict>
</plist>"""
    plist_path = app_dir.parent / "Info.plist"
    plist_path.write_text(plist)
    print("macOS .app created at /Applications/Chimera.app")


def main() -> None:
    system = platform.system()
    desktop = get_desktop_path()
    print(f"Platform: {system}")
    print(f"Desktop: {desktop}")
    print(f"Project: {ROOT}")

    if system == "Windows":
        create_windows_shortcut(desktop)
    elif system == "Linux":
        create_linux_shortcut(desktop)
    elif system == "Darwin":
        create_macos_shortcut(desktop)
    else:
        print(f"Unsupported platform: {system}")
        sys.exit(1)


if __name__ == "__main__":
    main()
