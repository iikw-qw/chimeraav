"""UI analyzer — detect UI elements on a screenshot (OpenCV + YOLOv8 + Tesseract)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.database import SessionLocal
from app.models.task import Task
from app.models.ui_locator import UILocator

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dep
    cv2 = None  # type: ignore

try:
    import pytesseract  # type: ignore
except Exception:  # pragma: no cover - optional dep
    pytesseract = None  # type: ignore

try:
    from ultralytics import YOLO  # type: ignore
except Exception:  # pragma: no cover - optional dep
    YOLO = None  # type: ignore


class UIAnalyzer:
    def __init__(self, *, model_path: str | None = None) -> None:
        self._model_path = model_path or "yolov8n.pt"
        self._yolo: Any = None

    def _load_yolo(self) -> Any:
        if self._yolo is None and YOLO is not None:
            try:
                self._yolo = YOLO(self._model_path)
            except Exception:
                self._yolo = None
        return self._yolo

    async def analyze_screenshot(self, image_path: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._analyze_sync, image_path)

    def _analyze_sync(self, image_path: str) -> dict[str, Any]:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(image_path)

        elements: list[dict[str, Any]] = []
        image = None
        if cv2 is not None:
            image = cv2.imread(str(path))

        yolo = self._load_yolo()
        if yolo is not None and image is not None:
            try:
                results = yolo.predict(image, verbose=False)
                for r in results:
                    for box in getattr(r, "boxes", []) or []:
                        xyxy = box.xyxy.cpu().numpy().tolist()[0]
                        cls_id = int(box.cls.cpu().numpy().tolist()[0])
                        conf = float(box.conf.cpu().numpy().tolist()[0])
                        elements.append(
                            {
                                "source": "yolo",
                                "class_id": cls_id,
                                "confidence": conf,
                                "bbox": xyxy,
                            }
                        )
            except Exception:
                pass

        text_blocks: list[dict[str, Any]] = []
        if pytesseract is not None and image is not None:
            try:
                data = pytesseract.image_to_data(
                    image, output_type=pytesseract.Output.DICT
                )
                for i, word in enumerate(data.get("text", [])):
                    if not word or not word.strip():
                        continue
                    text_blocks.append(
                        {
                            "text": word,
                            "bbox": [
                                data["left"][i],
                                data["top"][i],
                                data["left"][i] + data["width"][i],
                                data["top"][i] + data["height"][i],
                            ],
                            "confidence": float(data["conf"][i] or 0) / 100.0,
                        }
                    )
            except Exception:
                pass

        return {
            "image_path": str(path),
            "elements": elements,
            "text_blocks": text_blocks,
        }

    async def update_locator(
        self,
        platform: str,
        element_name: str,
        locator_type: str,
        locator_value: str,
        confidence: float = 1.0,
    ) -> UILocator:
        async with SessionLocal() as session:
            stmt = select(UILocator).where(
                UILocator.platform == platform,
                UILocator.element_name == element_name,
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing is None:
                locator = UILocator(
                    platform=platform,
                    element_name=element_name,
                    locator_type=locator_type,
                    locator_value=locator_value,
                    confidence=confidence,
                )
                session.add(locator)
            else:
                existing.locator_type = locator_type
                existing.locator_value = locator_value
                existing.confidence = confidence
                existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                locator = existing
            await session.commit()
            await session.refresh(locator)
            return locator

    async def crowdsource(self, reports: list[dict[str, Any]]) -> int:
        """Aggregate community-reported locators; keep the most-voted per key."""
        if not reports:
            return 0

        best: dict[tuple[str, str], dict[str, Any]] = {}
        counts: dict[tuple[str, str, str], int] = {}

        for report in reports:
            platform = report.get("platform")
            element = report.get("element_name")
            value = report.get("locator_value")
            loc_type = report.get("locator_type", "xpath")
            if not (platform and element and value):
                continue
            key = (platform, element)
            vote_key = (platform, element, value)
            counts[vote_key] = counts.get(vote_key, 0) + 1
            if counts[vote_key] > best.get(key, {"votes": 0}).get("votes", 0):
                best[key] = {
                    "platform": platform,
                    "element": element,
                    "locator_type": loc_type,
                    "locator_value": value,
                    "votes": counts[vote_key],
                }

        updated = 0
        for entry in best.values():
            total_votes_for_key = sum(
                v
                for k, v in counts.items()
                if k[0] == entry["platform"] and k[1] == entry["element"]
            )
            confidence = entry["votes"] / max(1, total_votes_for_key)
            await self.update_locator(
                platform=entry["platform"],
                element_name=entry["element"],
                locator_type=entry["locator_type"],
                locator_value=entry["locator_value"],
                confidence=confidence,
            )
            updated += 1
        return updated

    async def retrain_from_failure(self, task: Task) -> None:
        """Hook invoked when a DLQ task fails with a locator error."""
        payload = task.payload or {}
        platform = payload.get("platform") or "instagram"
        element = payload.get("element") or "unknown"
        await self.update_locator(
            platform=platform,
            element_name=element,
            locator_type=payload.get("locator_type", "xpath"),
            locator_value=payload.get("locator_value", ""),
            confidence=0.1,
        )


ui_analyzer = UIAnalyzer()
