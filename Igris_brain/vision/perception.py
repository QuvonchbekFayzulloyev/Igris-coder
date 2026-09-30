"""Perception Engine — barcha vision komponentlarini birlashtiruvchi yagona kirish nuqtasi.

Core contract:
    Vision.observe() -> Scene -> Objects -> Relations -> Target -> Action -> Verification
"""
from __future__ import annotations

import time
from typing import Any, Optional

from vision.contracts import (
    BBox, DetectedObject, Scene, SceneType, Target, VerificationResult,
)
from vision.capture import ScreenCapture, CaptureResult
from vision.preprocess import ImagePreprocessor
from vision.ocr import OCRBackend
from vision.detector import ObjectDetector
from vision.spatial import SpatialEngine
from vision.ui_analyzer import UIAnalyzer
from vision.context import VisionContextBuilder
from vision.temporal import TemporalVision, FrameDiff
from vision.verify import ActionVerifier
from vision.memory import VisionMemory
from vision.uncertainty import UncertaintyDetector
from vision.performance import (
    PerformanceMetrics, PerformanceTracker, ScreenshotCache,
)


class PerceptionEngine:
    """IGRIS Vision — text-only LLMga "ko'z beradi".

    Core contract:
        observe() -> Scene -> context_for_llm() -> LLM decides -> action_bridge.execute()
    """

    def __init__(
        self,
        save_dir: str = "",
        confidence_threshold: float = 0.6,
        cache_ttl: float = 1.0,
    ):
        # Backends
        self._capture = ScreenCapture(save_dir=save_dir)
        self._preprocessor = ImagePreprocessor()
        self._ocr = OCRBackend()
        self._detector = ObjectDetector()
        self._spatial = SpatialEngine()
        self._ui_analyzer = UIAnalyzer()

        # Processing
        self._context_builder = VisionContextBuilder()
        self._temporal = TemporalVision()
        self._verifier = ActionVerifier()
        self._memory = VisionMemory()
        self._uncertainty = UncertaintyDetector(confidence_threshold)

        # Performance
        self._tracker = PerformanceTracker()
        self._screenshot_cache = ScreenshotCache(ttl_seconds=cache_ttl)
        self._perception_cache: dict[str, Any] = {}

    def observe(self, source: str = "screen", **kwargs) -> Scene:
        """Sahna kuzatuvi — asosiy kirish nuqtasi.

        Args:
            source: "screen", "window", "region", "file"
            **kwargs: capture parametrlari (window_title, bbox, file_path)

        Returns:
            Scene — to'liq tahlil qilingan sahna
        """
        metrics = PerformanceMetrics()

        # 1. Screenshot olish
        t = self._tracker.start_timer()
        capture = self._do_capture(source, **kwargs)
        metrics.capture_ms = self._tracker.end_timer(t)

        if capture.image is None:
            return Scene(scene_type=SceneType.UNKNOWN)

        # 2. Preprocessing
        t = self._tracker.start_timer()
        processed = self._preprocessor.downscale_if_large(capture.image)
        metrics.preprocess_ms = self._tracker.end_timer(t)

        # 3. Object detection
        t = self._tracker.start_timer()
        objects = self._detector.detect_ui_elements(processed)
        metrics.detection_ms = self._tracker.end_timer(t)

        # 4. OCR
        t = self._tracker.start_timer()
        ocr_objects = self._ocr.extract_to_objects(processed)
        raw_text = " ".join(o.associated_text for o in ocr_objects)
        metrics.ocr_ms = self._tracker.end_timer(t)

        # 5. OCR + detection ni birlashtirish
        all_objects = self._merge_objects(objects, ocr_objects)

        # 6. Spatial relations
        t = self._tracker.start_timer()
        relations = self._spatial.compute_relations(all_objects)
        metrics.spatial_ms = self._tracker.end_timer(t)

        # 7. UI analysis
        t = self._tracker.start_timer()
        scene = Scene(
            objects=all_objects,
            relations=relations,
            raw_text=raw_text,
            screenshot_path=capture.saved_path,
            timestamp=capture.timestamp,
            width=capture.width,
            height=capture.height,
            window_title=capture.window_title,
            app_name=capture.app_name,
        )
        scene = self._ui_analyzer.analyze(scene, processed)
        metrics.ui_analysis_ms = self._tracker.end_timer(t)

        # 8. Temporal update
        diff = self._temporal.update(scene)

        # 9. Memory
        self._memory.store_scene(scene)

        # 10. Metrics
        metrics.total_ms = sum([
            metrics.capture_ms, metrics.preprocess_ms, metrics.detection_ms,
            metrics.ocr_ms, metrics.spatial_ms, metrics.ui_analysis_ms,
        ])
        self._tracker.record(metrics)

        return scene

    def observe_file(self, file_path: str) -> Scene:
        """Fayldan rasm yuklab tahlil qilish."""
        return self.observe(source="file", file_path=file_path)

    def observe_region(self, x1: int, y1: int, x2: int, y2: int) -> Scene:
        """Aniq hududni kuzatish."""
        return self.observe(source="region", bbox=BBox(x1, y1, x2, y2))

    def context_for_llm(self, scene: Scene, task: str = "") -> str:
        """LLM uchun text context yaratish."""
        if task:
            scene = self._context_builder.filter_irrelevant(scene, task)
        return self._context_builder.build_text_context(scene)

    def json_context_for_llm(self, scene: Scene, task: str = "") -> dict:
        """LLM uchun JSON context yaratish."""
        if task:
            scene = self._context_builder.filter_irrelevant(scene, task)
        return self._context_builder.build_json_context(scene)

    def find_target(self, scene: Scene, description: str) -> Optional[Target]:
        """Tavsif bo'yicha target topish."""
        # 1. Matn bo'yicha qidirish
        target = self._context_builder.rank_by_relevance(scene, description)
        if target:
            obj = target[0]
            t = Target(
                object_id=obj.object_id,
                bbox=obj.bbox,
                center=obj.center,
                confidence=obj.confidence,
                label=obj.label,
                object_type=obj.object_type,
            )
            # Safety check
            report = self._uncertainty.assess_target(t, scene)
            t.is_safe = report.recommendation in ("act", "retry")
            t.safety_reason = "; ".join(report.issues) if report.issues else ""
            return t

        return None

    def verify_action(self, before: Scene, after: Scene,
                      action: str = "") -> VerificationResult:
        """Amal tasdig'i."""
        return self._verifier.verify(before, after, action)

    def get_temporal_diff(self) -> Optional[FrameDiff]:
        """Oxirgi frame farqini olish."""
        if len(self._temporal._scenes) < 2:
            return None
        prev = self._temporal._scenes[-2]
        curr = self._temporal._scenes[-1]
        return self._temporal._compare_scenes(prev, curr)

    def get_performance(self) -> dict:
        """Sahna ko'rish performansini olish."""
        avg = self._tracker.get_average()
        return {
            "average": avg.to_dict(),
            "last": self._tracker.get_last().to_dict() if self._tracker.get_last() else None,
            "cache": self._screenshot_cache.get_stats(),
            "memory": self._memory.get_statistics(),
        }

    def get_memory(self) -> VisionMemory:
        """Vision memory'ga kirish."""
        return self._memory

    # --- Private ---

    def _do_capture(self, source: str, **kwargs) -> CaptureResult:
        """Capture bajarish."""
        if source == "window":
            title = kwargs.get("window_title")
            return self._capture.capture_window(title)
        elif source == "region":
            bbox = kwargs.get("bbox")
            if bbox:
                return self._capture.capture_region(bbox)
            return self._capture.capture_screen()
        elif source == "file":
            path = kwargs.get("file_path", "")
            return self._capture.capture_from_file(path)
        return self._capture.capture_screen()

    def _merge_objects(self, detected: list[DetectedObject],
                       ocr_objects: list[DetectedObject]) -> list[DetectedObject]:
        """Detection va OCR obyektlarini birlashtirish."""
        merged = list(detected)
        # OCR obyektlarini detection bilan bog'lash
        for ocr_obj in ocr_objects:
            best_match = None
            best_overlap = 0.0
            for det_obj in merged:
                if ocr_obj.bbox.overlaps(det_obj.bbox):
                    overlap = self._compute_overlap(ocr_obj.bbox, det_obj.bbox)
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_match = det_obj
            if best_match and best_overlap > 0.3:
                best_match.associated_text = ocr_obj.associated_text
                best_match.text_confidence = ocr_obj.text_confidence
            else:
                merged.append(ocr_obj)
        return merged

    def _compute_overlap(self, b1: BBox, b2: BBox) -> float:
        """IoU hisoblash."""
        x1 = max(b1.x1, b2.x1)
        y1 = max(b1.y1, b2.y1)
        x2 = min(b1.x2, b2.x2)
        y2 = min(b1.y2, b2.y2)
        if x2 <= x1 or y2 <= y1:
            return 0.0
        intersection = (x2 - x1) * (y2 - y1)
        union = b1.area + b2.area - intersection
        return intersection / union if union > 0 else 0.0
