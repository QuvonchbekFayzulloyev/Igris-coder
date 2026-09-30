"""§3 Object Perception — UI element detection, object classification."""
from __future__ import annotations

import time
from typing import Any, Optional

import numpy as np

from vision.contracts import BBox, DetectedObject, ObjectType


class ObjectDetector:
    """Obyektlarni aniqlash — UI elementlari, knopkalar, inputlar va boshqalar."""

    def __init__(self):
        self._detector = self._init_detector()

    def _init_detector(self) -> str:
        """Mavjud detector'ni aniqlash."""
        try:
            import cv2
            return "cv2"
        except ImportError:
            pass
        return "fallback"

    def detect(self, image: Any) -> list[DetectedObject]:
        """Rasmdan obyektlarni aniqlash."""
        if image is None:
            return []
        if self._detector == "cv2":
            return self._detect_cv2(image)
        return self._detect_fallback(image)

    def detect_ui_elements(self, image: Any) -> list[DetectedObject]:
        """UI elementlarini aniqlash — knopkalar, inputlar, checkboxlar."""
        objects = self.detect(image)
        # Har bir obyektga UI element tipini tayinlash
        for obj in objects:
            obj.is_interactive = self._is_interactive(obj)
        return objects

    def detect_buttons(self, image: Any) -> list[DetectedObject]:
        """Faqat knopkalarni aniqlash."""
        objects = self.detect(image)
        return [o for o in objects if o.object_type == ObjectType.BUTTON]

    def detect_inputs(self, image: Any) -> list[DetectedObject]:
        """Faqat input maydonlarini aniqlash."""
        objects = self.detect(image)
        return [o for o in objects if o.object_type in (ObjectType.INPUT, ObjectType.TEXT_FIELD)]

    def _is_interactive(self, obj: DetectedObject) -> bool:
        """Obyekt interaktiv ekanligini aniqlash."""
        interactive_types = {
            ObjectType.BUTTON, ObjectType.INPUT, ObjectType.TEXT_FIELD,
            ObjectType.CHECKBOX, ObjectType.MENU, ObjectType.MENU_ITEM,
            ObjectType.LINK, ObjectType.DROPDOWN, ObjectType.TAB,
        }
        return obj.object_type in interactive_types

    def _detect_cv2(self, image: Any) -> list[DetectedObject]:
        """OpenCV yordamida obyektlarni aniqlash."""
        try:
            import cv2
            if isinstance(image, np.ndarray):
                if len(image.shape) == 3:
                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                else:
                    gray = image
            else:
                return []

            objects = []
            obj_counter = 0

            # 1. Knopkalar — contour detection
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 500:  # juda kichik
                    continue
                x, y, w, h = cv2.boundingRect(contour)
                aspect = w / h if h > 0 else 0

                obj_type = self._classify_by_shape(w, h, aspect)
                obj = DetectedObject(
                    object_id=f"obj_{obj_counter}",
                    object_type=obj_type,
                    bbox=BBox(x, y, x + w, y + h),
                    confidence=min(0.6 + area / 100000, 0.95),
                    label=obj_type.value,
                    is_interactive=self._is_interactive_type(obj_type),
                )
                objects.append(obj)
                obj_counter += 1

            # 2. Matn bloklari (text areas)
            text_regions = self._detect_text_regions(gray)
            for region in text_regions:
                obj = DetectedObject(
                    object_id=f"obj_{obj_counter}",
                    object_type=ObjectType.TEXT,
                    bbox=region,
                    confidence=0.7,
                    label="text_region",
                )
                objects.append(obj)
                obj_counter += 1

            return objects
        except Exception:
            return []

    def _detect_text_regions(self, gray: Any) -> list[BBox]:
        """Matn joylarini aniqlash."""
        try:
            import cv2
            # Morphological operations
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
            dilated = cv2.dilate(gray, kernel, iterations=2)
            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            regions = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                if w > 50 and h > 10:
                    regions.append(BBox(x, y, x + w, y + h))
            return regions
        except Exception:
            return []

    def _classify_by_shape(self, w: int, h: int, aspect: float) -> ObjectType:
        """Shakl bo'yicha obyekt turini aniqlash."""
        if 0.8 < aspect < 5.0 and 20 < h < 100:
            return ObjectType.BUTTON
        if aspect > 3.0 and h < 50:
            return ObjectType.INPUT
        if 0.8 < aspect < 1.2 and 10 < w < 40:
            return ObjectType.CHECKBOX
        return ObjectType.UNKNOWN

    def _is_interactive_type(self, obj_type: ObjectType) -> bool:
        return obj_type in {
            ObjectType.BUTTON, ObjectType.INPUT, ObjectType.CHECKBOX,
            ObjectType.MENU, ObjectType.LINK, ObjectType.DROPDOWN,
        }

    def _detect_fallback(self, image: Any) -> list[DetectedObject]:
        """Detector mavjud emas — placeholder."""
        return []
