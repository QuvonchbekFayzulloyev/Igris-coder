"""§4 OCR/Text Perception — matn ajratib olish, bounding boxes, confidence."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from vision.contracts import BBox, DetectedObject, ObjectType


@dataclass
class OCRResult:
    """Bitta matn bloki natijasi."""
    text: str
    bbox: BBox
    confidence: float
    language: str = "eng"
    words: list[dict] = field(default_factory=list)


class OCRBackend:
    """OCR backend — matnni rasmdan ajratib olish."""

    def __init__(self):
        self._engine = self._init_engine()

    def _init_engine(self) -> str:
        """Mavjud OCR engine'ni aniqlash."""
        try:
            import pytesseract
            return "tesseract"
        except ImportError:
            pass
        try:
            import easyocr
            return "easyocr"
        except ImportError:
            pass
        return "fallback"

    def extract_text(self, image: Any) -> list[OCRResult]:
        """Rasmdan matnni ajratib olish."""
        if image is None:
            return []
        if self._engine == "tesseract":
            return self._extract_tesseract(image)
        elif self._engine == "easyocr":
            return self._extract_easyocr(image)
        return self._extract_fallback(image)

    def extract_text_blocks(self, image: Any) -> list[OCRResult]:
        """Matn bloklarini ajratib olish (paragraph-level)."""
        results = self.extract_text(image)
        # Gaplar bo'yicha guruhlash
        blocks: list[OCRResult] = []
        current_text = ""
        current_bbox = None
        current_conf = 0.0

        for r in results:
            if current_bbox is None:
                current_text = r.text
                current_bbox = r.bbox
                current_conf = r.confidence
            elif self._is_same_line(current_bbox, r.bbox):
                current_text += " " + r.text
                current_conf = min(current_conf, r.confidence)
            else:
                blocks.append(OCRResult(
                    text=current_text, bbox=current_bbox,
                    confidence=current_conf, language=r.language,
                ))
                current_text = r.text
                current_bbox = r.bbox
                current_conf = r.confidence

        if current_text:
            blocks.append(OCRResult(
                text=current_text, bbox=current_bbox,
                confidence=current_conf, language=r.language if results else "eng",
            ))
        return blocks

    def extract_to_objects(self, image: Any) -> list[DetectedObject]:
        """OCR natijasini DetectedObject formatiga o'tkazish."""
        results = self.extract_text(image)
        objects = []
        for i, r in enumerate(results):
            obj = DetectedObject(
                object_id=f"ocr_{i}",
                object_type=ObjectType.TEXT,
                bbox=r.bbox,
                confidence=r.confidence,
                label=r.text[:50],
                associated_text=r.text,
                text_confidence=r.confidence,
                is_interactive=False,
            )
            objects.append(obj)
        return objects

    def find_text(self, image: Any, target: str) -> Optional[OCRResult]:
        """Rasmda aniq matnni qidirish."""
        results = self.extract_text(image)
        target_lower = target.lower()
        for r in results:
            if target_lower in r.text.lower():
                return r
        return None

    def _is_same_line(self, b1: BBox, b2: BBox, threshold: float = 0.5) -> bool:
        """Ikki bbox bir qatorda ekanligini tekshirish."""
        h1, h2 = b1.height, b2.height
        avg_h = (h1 + h2) / 2
        y_overlap = max(0, min(b1.y2, b2.y2) - max(b1.y1, b2.y1))
        return y_overlap / avg_h > threshold

    # --- Engine implementations ---

    def _extract_tesseract(self, image: Any) -> list[OCRResult]:
        try:
            import pytesseract
            from PIL import Image
            if isinstance(image, np.ndarray):
                img = Image.fromarray(image)
            else:
                img = image
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            results = []
            n = len(data["text"])
            for i in range(n):
                text = data["text"][i].strip()
                conf = float(data["conf"][i])
                if text and conf > 0:
                    x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
                    results.append(OCRResult(
                        text=text,
                        bbox=BBox(x, y, x + w, y + h),
                        confidence=conf / 100.0,
                        language=data.get("lang", ["eng"])[i] if "lang" in data else "eng",
                    ))
            return results
        except Exception:
            return []

    def _extract_easyocr(self, image: Any) -> list[OCRResult]:
        try:
            import easyocr
            reader = easyocr.Reader(["en"], gpu=False)
            if isinstance(image, np.ndarray):
                if len(image.shape) == 2:
                    img = image
                else:
                    img = image[:, :, ::-1]  # BGR -> RGB
            else:
                img = np.array(image)
            results_raw = reader.readtext(img)
            results = []
            for (bbox_pts, text, conf) in results_raw:
                pts = np.array(bbox_pts, dtype=int)
                x1, y1 = pts[:, 0].min(), pts[:, 1].min()
                x2, y2 = pts[:, 0].max(), pts[:, 1].max()
                results.append(OCRResult(
                    text=text,
                    bbox=BBox(int(x1), int(y1), int(x2), int(y2)),
                    confidence=float(conf),
                ))
            return results
        except Exception:
            return []

    def _extract_fallback(self, image: Any) -> list[OCRResult]:
        """OCR mavjud emas — placeholder."""
        return []
