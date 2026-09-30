"""§15 Backend Abstraction — OCR/detector/tracker interface + fallback chain."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from vision.contracts import (
    CaptureBackend, ObjectDetectorBackend, OCRBackend, PreprocessorBackend,
    SpatialEngine, SceneAnalyzer,
)


@dataclass
class BackendStatus:
    """Backend holati."""
    name: str
    available: bool
    version: str = ""
    error: str = ""
    priority: int = 0  # qancha past bo'lsa, shuncha afzal


class BackendRegistry:
    """Backend'larni ro'yxatdan o'tkazish va boshqarish."""

    def __init__(self):
        self._backends: dict[str, list[BackendStatus]] = {
            "capture": [],
            "ocr": [],
            "detector": [],
            "preprocessor": [],
            "spatial": [],
            "scene_analyzer": [],
        }
        self._instances: dict[str, Any] = {}

    def register(self, category: str, status: BackendStatus, instance: Any = None) -> None:
        """Backend ro'yxatdan o'tkazish."""
        if category not in self._backends:
            self._backends[category] = []
        self._backends[category].append(status)
        self._backends[category].sort(key=lambda b: b.priority)
        if instance:
            self._instances[status.name] = instance

    def get_best(self, category: str) -> Optional[Any]:
        """Eng yaxshi backend'ni olish."""
        backends = self._backends.get(category, [])
        for b in backends:
            if b.available:
                return self._instances.get(b.name)
        return None

    def get_all(self, category: str) -> list[BackendStatus]:
        """Barcha backend'larni olish."""
        return self._backends.get(category, [])

    def get_status(self) -> dict:
        """Umumiy holat."""
        status = {}
        for cat, backends in self._backends.items():
            status[cat] = [
                {"name": b.name, "available": b.available, "priority": b.priority}
                for b in backends
            ]
        return status


class BackendFactory:
    """Backend yaratish — avtomatik aniqlash va fallback."""

    def __init__(self):
        self.registry = BackendRegistry()
        self._detect_all()

    def _detect_all(self) -> None:
        """Barcha backend'larni aniqlash."""
        self._detect_capture()
        self._detect_ocr()
        self._detect_detector()

    def _detect_capture(self) -> None:
        """Capture backend aniqlash."""
        # dxcam
        try:
            import dxcam
            self.registry.register(
                "capture",
                BackendStatus(name="dxcam", available=True, priority=0),
            )
        except ImportError:
            self.registry.register(
                "capture",
                BackendStatus(name="dxcam", available=False, error="Not installed"),
            )

        # Pillow
        try:
            from PIL import ImageGrab
            self.registry.register(
                "capture",
                BackendStatus(name="pillow", available=True, priority=1),
            )
        except ImportError:
            self.registry.register(
                "capture",
                BackendStatus(name="pillow", available=False, error="Not installed"),
            )

    def _detect_ocr(self) -> None:
        """OCR backend aniqlash."""
        # Tesseract
        try:
            import pytesseract
            self.registry.register(
                "ocr",
                BackendStatus(name="tesseract", available=True, priority=0),
            )
        except ImportError:
            self.registry.register(
                "ocr",
                BackendStatus(name="tesseract", available=False, error="Not installed"),
            )

        # EasyOCR
        try:
            import easyocr
            self.registry.register(
                "ocr",
                BackendStatus(name="easyocr", available=True, priority=1),
            )
        except ImportError:
            self.registry.register(
                "ocr",
                BackendStatus(name="easyocr", available=False, error="Not installed"),
            )

    def _detect_detector(self) -> None:
        """Object detection backend aniqlash."""
        try:
            import cv2
            self.registry.register(
                "detector",
                BackendStatus(name="opencv", available=True, priority=0),
            )
        except ImportError:
            self.registry.register(
                "detector",
                BackendStatus(name="opencv", available=False, error="Not installed"),
            )

    def get_capture_backend(self) -> Optional[str]:
        """Eng yaxshi capture backend nomini olish."""
        best = self.registry.get_best("capture")
        if best:
            return "dxcam" if hasattr(best, 'grab') else "pillow"
        return None

    def get_ocr_backend(self) -> Optional[str]:
        """Eng yaxshi OCR backend nomini olish."""
        best = self.registry.get_best("ocr")
        if best:
            return "tesseract" if hasattr(best, 'image_to_data') else "easyocr"
        return None

    def get_status(self) -> dict:
        """Backend holatini olish."""
        return self.registry.get_status()
