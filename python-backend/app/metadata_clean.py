"""Image metadata stripping helpers (EXIF / GPS / fingerprint nudge)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class CleanResult:
    file_path: str
    original_hash: str
    cleaned_hash: str
    exif_removed: bool
    gps_removed: bool
    digital_fingerprint_modified: bool


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_image_file(path: Path | str) -> CleanResult:
    p = Path(path)
    original_hash = _hash_file(p)
    had_exif = False
    had_gps = False

    with Image.open(p) as img:
        exif = img.getexif()
        if exif and len(exif) > 0:
            had_exif = True
            # GPS IFD lives at tag 34853.
            if 34853 in exif:
                had_gps = True
        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))
        save_kwargs: dict[str, object] = {}
        if p.suffix.lower() in {".jpg", ".jpeg"}:
            save_kwargs["quality"] = 92
            save_kwargs["optimize"] = True
        clean.save(p, **save_kwargs)

    cleaned_hash = _hash_file(p)
    return CleanResult(
        file_path=str(p),
        original_hash=original_hash,
        cleaned_hash=cleaned_hash,
        exif_removed=had_exif,
        gps_removed=had_gps,
        digital_fingerprint_modified=cleaned_hash != original_hash,
    )
