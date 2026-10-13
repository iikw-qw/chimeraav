"""Image quality analysis — sharpness, brightness, contrast, resolution."""

from __future__ import annotations

import logging

logger = logging.getLogger("chimera.quality")


class QualityAnalyzer:
    def analyze(self, image_path: str) -> dict:
        try:
            from PIL import Image
            import numpy as np
        except ImportError:
            logger.debug("Pillow/numpy not available for quality analysis")
            return {"total": 50.0, "error": "dependencies not available"}

        img = Image.open(image_path).convert("RGB")
        arr = np.array(img, dtype=np.float64)
        scores: dict = {}

        scores["brightness"] = float(np.mean(arr))
        scores["contrast"] = float(np.std(arr))
        scores["resolution"] = img.width * img.height

        try:
            import cv2
            gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
            scores["sharpness"] = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        except ImportError:
            gray_arr = np.mean(arr, axis=2)
            lap = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
            from scipy.signal import convolve2d
            try:
                conv = convolve2d(gray_arr, lap, mode="valid")
                scores["sharpness"] = float(np.var(conv))
            except ImportError:
                scores["sharpness"] = 50.0

        sharp_score = min(100.0, scores["sharpness"] / 5.0)
        bright_score = max(0.0, 100.0 - abs(scores["brightness"] - 128.0) * 0.8)
        contrast_score = min(100.0, scores["contrast"] * 0.8)
        res_score = min(100.0, scores["resolution"] / 20_000.0)

        scores["total"] = round(
            sharp_score * 0.3 + bright_score * 0.3 +
            contrast_score * 0.2 + res_score * 0.2,
            2,
        )
        return scores
