"""Generate Chimera application icons from the source logo.

Creates:
    resources/icon.ico       (multi-size Windows icon)
    resources/icon.png       (512x512 hi-res for Linux/macOS)
    resources/tray-icon.png  (16x16 Windows tray)

Usage:
    python scripts/convert-icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src" / "assets" / "logo.jfif"
OUT_DIR = ROOT / "resources"


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Source logo not found: {SOURCE}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    img = Image.open(SOURCE)
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    ico_path = OUT_DIR / "icon.ico"
    img.save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    img.resize((512, 512), Image.LANCZOS).save(OUT_DIR / "icon.png")
    img.resize((16, 16), Image.LANCZOS).save(OUT_DIR / "tray-icon.png")

    print(f"Wrote {ico_path}")
    print(f"Wrote {OUT_DIR / 'icon.png'}")
    print(f"Wrote {OUT_DIR / 'tray-icon.png'}")


if __name__ == "__main__":
    main()
