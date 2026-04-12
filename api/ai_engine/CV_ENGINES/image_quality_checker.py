"""
api/ai_engine/CV_ENGINES/image_quality_checker.py
==================================================
Image Quality Checker — blur, resolution, brightness check।
"""

import logging

logger = logging.getLogger(__name__)


class ImageQualityChecker:
    """Image quality assessment।"""

    def check(self, image_path: str = None, image_url: str = None) -> dict:
        try:
            from PIL import Image, ImageStat
            import requests
            from io import BytesIO
            import math

            if image_url:
                resp = requests.get(image_url, timeout=10)
                img = Image.open(BytesIO(resp.content))
            elif image_path:
                img = Image.open(image_path)
            else:
                return self._default_result()

            width, height = img.size
            is_blurry = self._check_blur(img)
            brightness = self._check_brightness(img)

            quality_score = 1.0
            if is_blurry:        quality_score -= 0.4
            if width < 300:      quality_score -= 0.3
            if brightness < 0.2: quality_score -= 0.2
            if brightness > 0.9: quality_score -= 0.2

            return {
                'quality_score':  round(max(0.0, quality_score), 3),
                'is_blurry':      is_blurry,
                'resolution':     f"{width}x{height}",
                'brightness':     round(brightness, 3),
                'is_acceptable':  quality_score >= 0.5,
            }
        except Exception as e:
            logger.error(f"Image quality check error: {e}")
            return self._default_result()

    def _check_blur(self, img) -> bool:
        try:
            import numpy as np
            gray = img.convert('L')
            arr = np.array(gray, dtype=float)
            laplacian = arr[1:-1, 1:-1] - 0.25 * (
                arr[:-2, 1:-1] + arr[2:, 1:-1] + arr[1:-1, :-2] + arr[1:-1, 2:]
            )
            variance = float(laplacian.var())
            return variance < 100
        except Exception:
            return False

    def _check_brightness(self, img) -> float:
        try:
            from PIL import ImageStat
            gray = img.convert('L')
            stat = ImageStat.Stat(gray)
            return stat.mean[0] / 255.0
        except Exception:
            return 0.5

    def _default_result(self) -> dict:
        return {'quality_score': 0.0, 'is_blurry': False, 'resolution': 'unknown',
                'brightness': 0.5, 'is_acceptable': False}
