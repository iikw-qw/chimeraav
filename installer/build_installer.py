"""Build Chimera installer package.

Builds the Electron desktop app, bundles the Python backend sidecar, and
creates platform-specific installers.
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist-electron"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"  > {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=cwd or ROOT)


def check_prerequisites() -> None:
    print("[1/5] Checking prerequisites...")
    for tool in ["node", "npm", "py" if os.name == "nt" else "python3"]:
        if shutil.which(tool) is None:
            print(f"  ERROR: {tool} not found in PATH")
            sys.exit(1)
        print(f"  {tool} OK")


def install_dependencies() -> None:
    print("[2/5] Installing dependencies...")
    run(["npm", "install"])
    pip_cmd = ["py", "-m", "pip"] if os.name == "nt" else ["python3", "-m", "pip"]
    req = ROOT / "python-backend" / "requirements.txt"
    if req.exists():
        run([*pip_cmd, "install", "-r", str(req)])


def build_frontend() -> None:
    print("[3/5] Building frontend...")
    run(["npm", "run", "build"])


def build_electron() -> None:
    print("[4/5] Building Electron installer...")
    env = os.environ.copy()
    env["CSC_IDENTITY_AUTO_DISCOVERY"] = "false"
    subprocess.check_call(["npx", "electron-builder", "--win"], cwd=ROOT, env=env)


def copy_icon() -> None:
    print("[5/5] Copying chimerafoto icon...")
    chimerafoto = ROOT / "chimerafoto.jfif"
    if chimerafoto.exists():
        from PIL import Image

        img = Image.open(chimerafoto)
        sizes = [16, 24, 32, 48, 64, 128, 256]
        img_256 = img.resize((256, 256), Image.LANCZOS)
        img_256.save(ROOT / "resources" / "icon.png", "PNG")
        img_32 = img.resize((32, 32), Image.LANCZOS)
        img_32.save(ROOT / "resources" / "tray-icon.png", "PNG")
        ico_images = [img.resize((s, s), Image.LANCZOS) for s in sizes]
        ico_images[0].save(
            ROOT / "resources" / "icon.ico",
            format="ICO",
            sizes=[(s, s) for s in sizes],
            append_images=ico_images[1:],
        )
        print("  Icons generated from chimerafoto")
    else:
        print("  chimerafoto not found, using existing icons")


def main() -> None:
    print("=" * 50)
    print("  Chimera Installer Builder v9.0")
    print("=" * 50)

    check_prerequisites()
    install_dependencies()
    copy_icon()
    build_frontend()
    build_electron()

    setup_exe = BUILD_DIR / "Chimera-9.0.0-Setup.exe"
    if setup_exe.exists():
        size_mb = setup_exe.stat().st_size / (1024 * 1024)
        print(f"\nBuild successful: {setup_exe} ({size_mb:.1f} MB)")
    else:
        print("\nBuild completed. Check the 'build' directory for output.")


if __name__ == "__main__":
    main()
