"""§2 Image Preprocessing — resize, crop, normalize, OCR/UI uchun tayyorlash."""
from __future__ import annotations

from typing import Any, Optional

import numpy as np

from vision.contracts import BBox


class ImagePreprocessor:
    """Rasmni tayyorlash — detection, OCR, UI analysis uchun."""

    def resize(self, image: Any, width: int, height: int) -> Any:
        """Rasmni o'lchamga kattartish/kichiklashtirish."""
        if image is None:
            return None
        try:
            from PIL import Image
            if isinstance(image, np.ndarray):
                img = Image.fromarray(image)
            else:
                img = image
            resized = img.resize((width, height), Image.Resampling.LANCZOS)
            return np.array(resized)
        except ImportError:
            return self._cv2_resize(image, width, height)

    def crop(self, image: Any, bbox: BBox) -> Any:
        """Rasmni hududga qirqish."""
        if image is None:
            return None
        if isinstance(image, np.ndarray):
            return image[bbox.y1:bbox.y2, bbox.x1:bbox.x2].copy()
        return image

    def normalize(self, image: Any) -> Any:
        """Rasmni 0-1 oralig'iga normallashtirish."""
        if image is None:
            return None
        arr = np.array(image, dtype=np.float32)
        if arr.max() > 1.0:
            arr = arr / 255.0
        return arr

    def to_grayscale(self, image: Any) -> Any:
        """Rasmni kulrang rangga aylantirish (OCR uchun)."""
        if image is None:
            return None
        if isinstance(image, np.ndarray):
            if len(image.shape) == 3:
                return np.dot(image[..., :3], [0.2989, 0.5870, 0.1140]).astype(np.uint8)
            return image
        return image

    def enhance_for_ocr(self, image: Any) -> Any:
        """OCR uchun rasmni yaxshilash — contrast, sharpening."""
        if image is None:
            return None
        try:
            from PIL import Image, ImageEnhance, ImageFilter
            if isinstance(image, np.ndarray):
                img = Image.fromarray(image)
            else:
                img = image
            # Contrast oshirish
            img = ImageEnhance.Contrast(img).enhance(2.0)
            # Sharpness oshirish
            img = ImageEnhance.Sharpness(img).enhance(2.0)
            # Binarization (Otsu threshold)
            img = img.convert("L")
            arr = np.array(img)
            threshold = self._otsu_threshold(arr)
            arr = np.where(arr > threshold, 255, 0).astype(np.uint8)
            return arr
        except ImportError:
            return self._cv2_enhance_for_ocr(image)

    def enhance_for_ui_detection(self, image: Any) -> Any:
        """UI detection uchun rasmni tayyorlash."""
        if image is None:
            return None
        try:
            from PIL import Image, ImageEnhance
            if isinstance(image, np.ndarray):
                img = Image.fromarray(image)
            else:
                img = image
            # Contrast biroz oshirish
            img = ImageEnhance.Contrast(img).enhance(1.5)
            return np.array(img)
        except ImportError:
            return image

    def downscale_if_large(self, image: Any, max_dim: int = 1920) -> Any:
        """Katta rasmni kichiklashtirish (tezlik uchun)."""
        if image is None:
            return None
        if isinstance(image, np.ndarray):
            h, w = image.shape[:2]
            if max(h, w) <= max_dim:
                return image
            scale = max_dim / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            return self.resize(image, new_w, new_h)
        return image

    def apply(self, image: Any, operations: list[str]) -> Any:
        """Ketma-ket amallar bajarmish."""
        result = image
        for op in operations:
            if op == "grayscale":
                result = self.to_grayscale(result)
            elif op == "normalize":
                result = self.normalize(result)
            elif op == "enhance_ocr":
                result = self.enhance_for_ocr(result)
            elif op == "enhance_ui":
                result = self.enhance_for_ui_detection(result)
        return result

    # --- Helpers ---

    def _otsu_threshold(self, arr: np.ndarray) -> int:
        """Otsu threshold hisoblash."""
        hist, _ = np.histogram(arr.flatten(), bins=256, range=(0, 256))
        total = arr.size
        sum_total = np.dot(np.arange(256), hist)
        sum_bg = 0.0
        weight_bg = 0
        max_variance = 0.0
        threshold = 0
        for i in range(256):
            weight_bg += hist[i]
            if weight_bg == 0:
                continue
            weight_fg = total - weight_bg
            if weight_fg == 0:
                break
            sum_bg += i * hist[i]
            mean_bg = sum_bg / weight_bg
            mean_fg = (sum_total - sum_bg) / weight_fg
            variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
            if variance > max_variance:
                max_variance = variance
                threshold = i
        return threshold

    def _cv2_resize(self, image: Any, width: int, height: int) -> Any:
        try:
            import cv2
            if isinstance(image, np.ndarray):
                return cv2.resize(image, (width, height))
        except ImportError:
            pass
        return image

    def _cv2_enhance_for_ocr(self, image: Any) -> Any:
        try:
            import cv2
            if isinstance(image, np.ndarray):
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                return binary
        except ImportError:
            pass
        return image
