"""§17 Vision System — unit + integration tests."""
from __future__ import annotations

import sys
import os

# Add parent directory for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import pytest
import numpy as np


# ------------------------------------------------------------------ #
# §0 Contract Tests
# ------------------------------------------------------------------ #

class TestBBox:
    """Bounding box testlari."""

    def test_basic_properties(self):
        from vision.contracts import BBox
        b = BBox(10, 20, 110, 70)
        assert b.width == 100
        assert b.height == 50
        assert b.center == (60, 45)
        assert b.area == 5000

    def test_contains_point(self):
        from vision.contracts import BBox
        b = BBox(10, 20, 110, 70)
        assert b.contains_point(60, 45)
        assert not b.contains_point(5, 5)

    def test_overlaps(self):
        from vision.contracts import BBox
        b1 = BBox(10, 10, 100, 100)
        b2 = BBox(50, 50, 150, 150)
        assert b1.overlaps(b2)
        b3 = BBox(200, 200, 300, 300)
        assert not b1.overlaps(b3)

    def test_distance(self):
        from vision.contracts import BBox
        b1 = BBox(0, 0, 10, 10)
        b2 = BBox(30, 0, 40, 10)
        dist = b1.distance_to(b2)
        assert abs(dist - 30.0) < 1.0

    def test_serialization(self):
        from vision.contracts import BBox
        b = BBox(10, 20, 110, 70)
        d = b.to_dict()
        b2 = BBox.from_dict(d)
        assert b == b2


class TestDetectedObject:
    """DetectedObject testlari."""

    def test_creation(self):
        from vision.contracts import BBox, DetectedObject, ObjectType
        obj = DetectedObject(
            object_id="btn_1",
            object_type=ObjectType.BUTTON,
            bbox=BBox(100, 200, 200, 250),
            confidence=0.95,
            label="Search",
        )
        assert obj.object_id == "btn_1"
        assert obj.center == (150, 225)
        assert obj.is_interactive is False

    def test_serialization(self):
        from vision.contracts import BBox, DetectedObject, ObjectType
        obj = DetectedObject(
            object_id="inp_1",
            object_type=ObjectType.INPUT,
            bbox=BBox(10, 10, 100, 30),
            confidence=0.8,
            associated_text="Search...",
        )
        d = obj.to_dict()
        assert d["object_id"] == "inp_1"
        assert d["associated_text"] == "Search..."


class TestScene:
    """Scene testlari."""

    def test_scene_filters(self):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene, SceneType
        scene = Scene(
            scene_type=SceneType.BROWSER,
            objects=[
                DetectedObject("b1", ObjectType.BUTTON, BBox(10, 10, 100, 50), 0.9, is_interactive=True),
                DetectedObject("t1", ObjectType.TEXT, BBox(10, 60, 100, 80), 0.8, associated_text="Hello"),
                DetectedObject("i1", ObjectType.INPUT, BBox(10, 90, 200, 120), 0.85, is_interactive=True),
            ],
        )
        assert len(scene.get_objects_by_type(ObjectType.BUTTON)) == 1
        assert len(scene.get_interactive_objects()) == 2
        assert len(scene.get_objects_with_text()) == 1
        assert scene.get_object_by_id("b1") is not None
        assert scene.get_object_by_id("xxx") is None

    def test_find_by_text(self):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene, SceneType
        scene = Scene(
            objects=[
                DetectedObject("b1", ObjectType.BUTTON, BBox(0, 0, 10, 10), 0.9, associated_text="Search"),
                DetectedObject("b2", ObjectType.BUTTON, BBox(0, 0, 10, 10), 0.9, associated_text="Submit"),
            ]
        )
        found = scene.find_objects_by_text("search")
        assert len(found) == 1


# ------------------------------------------------------------------ #
# §2 Preprocessing Tests
# ------------------------------------------------------------------ #

class TestPreprocessor:
    """Image preprocessing testlari."""

    def test_resize(self):
        from vision.preprocess import ImagePreprocessor
        prep = ImagePreprocessor()
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        resized = prep.resize(img, 50, 25)
        assert resized.shape[0] == 25
        assert resized.shape[1] == 50

    def test_crop(self):
        from vision.contracts import BBox
        from vision.preprocess import ImagePreprocessor
        prep = ImagePreprocessor()
        img = np.ones((100, 200, 3), dtype=np.uint8) * 128
        cropped = prep.crop(img, BBox(50, 25, 150, 75))
        assert cropped.shape[0] == 50
        assert cropped.shape[1] == 100

    def test_normalize(self):
        from vision.preprocess import ImagePreprocessor
        prep = ImagePreprocessor()
        img = np.array([[0, 128, 255]], dtype=np.uint8)
        normed = prep.normalize(img)
        assert normed.min() >= 0.0
        assert normed.max() <= 1.0

    def test_to_grayscale(self):
        from vision.preprocess import ImagePreprocessor
        prep = ImagePreprocessor()
        img = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        gray = prep.to_grayscale(img)
        assert len(gray.shape) == 2

    def test_downscale_if_large(self):
        from vision.preprocess import ImagePreprocessor
        prep = ImagePreprocessor()
        img = np.zeros((3000, 4000, 3), dtype=np.uint8)
        downscaled = prep.downscale_if_large(img, max_dim=1920)
        assert max(downscaled.shape[:2]) <= 1920

    def test_apply_chain(self):
        from vision.preprocess import ImagePreprocessor
        prep = ImagePreprocessor()
        img = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        result = prep.apply(img, ["grayscale", "normalize"])
        assert result.min() >= 0.0


# ------------------------------------------------------------------ #
# §5 Spatial Tests
# ------------------------------------------------------------------ #

class TestSpatialEngine:
    """Spatial understanding testlari."""

    def _make_objects(self):
        from vision.contracts import BBox, DetectedObject, ObjectType
        return [
            DetectedObject("a", ObjectType.BUTTON, BBox(10, 10, 100, 50), 0.9),
            DetectedObject("b", ObjectType.BUTTON, BBox(200, 10, 300, 50), 0.9),
            DetectedObject("c", ObjectType.INPUT, BBox(10, 200, 200, 250), 0.8),
        ]

    def test_compute_relations(self):
        from vision.spatial import SpatialEngine
        engine = SpatialEngine()
        objects = self._make_objects()
        relations = engine.compute_relations(objects)
        assert len(relations) > 0

    def test_find_nearest(self):
        from vision.contracts import ObjectType
        from vision.spatial import SpatialEngine
        engine = SpatialEngine()
        objects = self._make_objects()
        nearest = engine.find_nearest(objects[0], objects)
        assert nearest is not None
        assert nearest.object_id != "a"

    def test_find_by_text(self):
        from vision.contracts import DetectedObject, BBox, ObjectType
        from vision.spatial import SpatialEngine
        engine = SpatialEngine()
        objects = [
            DetectedObject("b1", ObjectType.BUTTON, BBox(0, 0, 10, 10), 0.9, associated_text="Search"),
        ]
        found = engine.find_by_text("Search", objects)
        assert found is not None
        assert found.object_id == "b1"


# ------------------------------------------------------------------ #
# §8 Context Builder Tests
# ------------------------------------------------------------------ #

class TestVisionContextBuilder:
    """Context builder testlari."""

    def _make_scene(self):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene, SceneType
        return Scene(
            scene_type=SceneType.BROWSER,
            width=1920, height=1080,
            window_title="Google - Chrome",
            objects=[
                DetectedObject("b1", ObjectType.BUTTON, BBox(100, 50, 200, 80), 0.9,
                              associated_text="Search", is_interactive=True),
                DetectedObject("i1", ObjectType.INPUT, BBox(100, 100, 400, 130), 0.85,
                              associated_text="Type here", is_interactive=True),
            ],
        )

    def test_build_text_context(self):
        from vision.context import VisionContextBuilder
        builder = VisionContextBuilder()
        scene = self._make_scene()
        ctx = builder.build_text_context(scene)
        assert "browser" in ctx.lower()
        assert "button" in ctx.lower() or "Button" in ctx

    def test_build_json_context(self):
        from vision.context import VisionContextBuilder
        builder = VisionContextBuilder()
        scene = self._make_scene()
        ctx = builder.build_json_context(scene)
        assert "scene_type" in ctx
        assert len(ctx["objects"]) == 2

    def test_compact_summary(self):
        from vision.context import VisionContextBuilder
        builder = VisionContextBuilder()
        scene = self._make_scene()
        summary = builder.compact_summary(scene)
        assert "browser" in summary.lower()

    def test_rank_by_relevance(self):
        from vision.context import VisionContextBuilder
        builder = VisionContextBuilder()
        scene = self._make_scene()
        ranked = builder.rank_by_relevance(scene, "search button")
        assert len(ranked) > 0
        assert ranked[0].object_id == "b1"


# ------------------------------------------------------------------ #
# §10 Action Bridge Tests
# ------------------------------------------------------------------ #

class TestActionBridge:
    """Action bridge testlari."""

    def _make_scene(self):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene, SceneType
        return Scene(
            scene_type=SceneType.BROWSER,
            objects=[
                DetectedObject("b1", ObjectType.BUTTON, BBox(100, 200, 250, 250), 0.9,
                              label="Search", is_interactive=True),
                DetectedObject("i1", ObjectType.INPUT, BBox(100, 300, 400, 340), 0.85,
                              is_interactive=True),
            ],
        )

    def test_resolve_target(self):
        from vision.action_bridge import ActionBridge
        bridge = ActionBridge(safety_enabled=False)
        scene = self._make_scene()
        target = bridge.resolve_target(scene, "b1")
        assert target is not None
        assert target.object_id == "b1"
        assert target.center == (175, 225)

    def test_resolve_not_found(self):
        from vision.action_bridge import ActionBridge
        bridge = ActionBridge()
        scene = self._make_scene()
        target = bridge.resolve_target(scene, "xxx")
        assert target is None

    def test_resolve_by_text(self):
        from vision.action_bridge import ActionBridge
        bridge = ActionBridge(safety_enabled=False)
        scene = self._make_scene()
        target = bridge.resolve_by_text(scene, "Search")
        assert target is not None

    def test_safety_check(self):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene
        from vision.action_bridge import ActionBridge
        bridge = ActionBridge(safety_enabled=True)
        # Disabled element
        scene = Scene(
            objects=[
                DetectedObject("d1", ObjectType.BUTTON, BBox(0, 0, 10, 10), 0.9,
                              is_enabled=False),
            ]
        )
        target = bridge.resolve_target(scene, "d1")
        assert target.is_safe is False


# ------------------------------------------------------------------ #
# §11 Temporal Vision Tests
# ------------------------------------------------------------------ #

class TestTemporalVision:
    """Temporal vision testlari."""

    def test_first_frame(self):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene
        from vision.temporal import TemporalVision
        tv = TemporalVision()
        scene = Scene(objects=[
            DetectedObject("a", ObjectType.BUTTON, BBox(0, 0, 10, 10), 0.9),
        ])
        diff = tv.update(scene)
        assert len(diff.appeared) == 1

    def test_frame_comparison(self):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene
        from vision.temporal import TemporalVision
        tv = TemporalVision()

        scene1 = Scene(objects=[
            DetectedObject("a", ObjectType.BUTTON, BBox(0, 0, 10, 10), 0.9),
        ])
        tv.update(scene1)

        scene2 = Scene(objects=[
            DetectedObject("a", ObjectType.BUTTON, BBox(0, 0, 10, 10), 0.9),
            DetectedObject("b", ObjectType.INPUT, BBox(50, 50, 100, 70), 0.8),
        ])
        diff = tv.update(scene2)
        assert len(diff.appeared) == 1
        assert diff.appeared[0].object_id == "b"

    def test_page_change_detection(self):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene
        from vision.temporal import TemporalVision
        tv = TemporalVision()

        scene1 = Scene(objects=[
            DetectedObject("a", ObjectType.BUTTON, BBox(0, 0, 10, 10), 0.9),
            DetectedObject("b", ObjectType.BUTTON, BBox(20, 20, 30, 30), 0.9),
        ])
        tv.update(scene1)

        scene2 = Scene(objects=[
            DetectedObject("c", ObjectType.BUTTON, BBox(100, 100, 200, 200), 0.9),
            DetectedObject("d", ObjectType.INPUT, BBox(150, 150, 250, 250), 0.8),
        ])
        diff = tv.update(scene2)
        assert diff.page_changed is True


# ------------------------------------------------------------------ #
# §12 Verification Tests
# ------------------------------------------------------------------ #

class TestActionVerifier:
    """Action verification testlari."""

    def _make_scene(self, objects_data):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene
        objects = []
        for od in objects_data:
            obj = DetectedObject(
                object_id=od["id"],
                object_type=ObjectType(od.get("type", "button")),
                bbox=BBox(*od["bbox"]),
                confidence=od.get("confidence", 0.9),
                is_enabled=od.get("enabled", True),
            )
            objects.append(obj)
        return Scene(objects=objects)

    def test_no_change(self):
        from vision.contracts import ActionVerdict
        from vision.verify import ActionVerifier
        verifier = ActionVerifier()
        scene_data = [{"id": "a", "bbox": (0, 0, 10, 10)}]
        before = self._make_scene(scene_data)
        after = self._make_scene(scene_data)
        result = verifier.verify(before, after)
        assert result.verdict == ActionVerdict.FAILURE

    def test_page_changed(self):
        from vision.contracts import ActionVerdict
        from vision.verify import ActionVerifier
        verifier = ActionVerifier()
        before = self._make_scene([{"id": "a", "bbox": (0, 0, 10, 10)}])
        after = self._make_scene([
            {"id": "x", "bbox": (100, 100, 200, 200)},
            {"id": "y", "bbox": (300, 300, 400, 400)},
        ])
        result = verifier.verify(before, after)
        assert result.verdict == ActionVerdict.SUCCESS
        assert result.page_changed is True

    def test_retry_needed(self):
        from vision.verify import ActionVerifier
        from vision.contracts import ActionVerdict
        verifier = ActionVerifier()
        result = verifier.verify(
            self._make_scene([{"id": "a", "bbox": (0, 0, 10, 10)}]),
            self._make_scene([{"id": "a", "bbox": (0, 0, 10, 10)}]),
        )
        assert verifier.should_retry(result) is True


# ------------------------------------------------------------------ #
# §13 Vision Memory Tests
# ------------------------------------------------------------------ #

class TestVisionMemory:
    """Vision memory testlari."""

    def test_store_and_retrieve(self):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene
        from vision.memory import VisionMemory
        mem = VisionMemory(max_scenes=5)
        scene = Scene(objects=[
            DetectedObject("a", ObjectType.BUTTON, BBox(0, 0, 10, 10), 0.9),
        ])
        mem.store_scene(scene)
        assert mem.get_current_scene() is not None
        assert mem.get_previous_scene() is None

    def test_history(self):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene
        from vision.memory import VisionMemory
        mem = VisionMemory(max_scenes=3)
        for i in range(5):
            scene = Scene(objects=[
                DetectedObject(f"obj_{i}", ObjectType.BUTTON, BBox(0, 0, 10, 10), 0.9),
            ])
            mem.store_scene(scene)
        assert len(mem.get_scene_history(3)) == 3

    def test_object_history(self):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene
        from vision.memory import VisionMemory
        mem = VisionMemory()
        for i in range(3):
            scene = Scene(objects=[
                DetectedObject("a", ObjectType.BUTTON, BBox(0, 0, 10, 10), 0.9),
            ])
            mem.store_scene(scene)
        history = mem.get_object_history("a")
        assert len(history) == 3

    def test_forget(self):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene
        from vision.memory import VisionMemory
        mem = VisionMemory()
        scene = Scene(objects=[
            DetectedObject("a", ObjectType.BUTTON, BBox(0, 0, 10, 10), 0.9),
        ])
        mem.store_scene(scene)
        mem.forget_irrelevant(max_age_seconds=0.01)
        time.sleep(0.02)
        mem.forget_irrelevant(max_age_seconds=0.01)
        assert mem.get_current_scene() is None


# ------------------------------------------------------------------ #
# §14 Uncertainty Tests
# ------------------------------------------------------------------ #

class TestUncertaintyDetector:
    """Uncertainty detection testlari."""

    def test_low_confidence(self):
        from vision.contracts import BBox, ObjectType, Scene, Target
        from vision.uncertainty import UncertaintyDetector
        det = UncertaintyDetector()
        target = Target(
            object_id="x", bbox=BBox(0, 0, 10, 10),
            center=(5, 5), confidence=0.2, label="x",
        )
        scene = Scene(objects=[])
        report = det.assess_target(target, scene)
        assert report.is_certain is False
        assert "low confidence" in report.issues[0].lower() or report.confidence < 0.3

    def test_ambiguous_target(self):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene, Target
        from vision.uncertainty import UncertaintyDetector
        det = UncertaintyDetector()
        scene = Scene(objects=[
            DetectedObject("a", ObjectType.BUTTON, BBox(0, 0, 10, 10), 0.9, label="OK"),
            DetectedObject("b", ObjectType.BUTTON, BBox(50, 50, 100, 100), 0.85, label="OK"),
        ])
        target = Target(
            object_id="a", bbox=BBox(0, 0, 10, 10),
            center=(5, 5), confidence=0.9, label="OK",
        )
        report = det.assess_target(target, scene)
        assert any("ambiguous" in i.lower() for i in report.issues)

    def test_scene_assessment(self):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene
        from vision.uncertainty import UncertaintyDetector
        det = UncertaintyDetector()
        empty_scene = Scene(objects=[])
        report = det.assess_scene(empty_scene)
        assert report.is_certain is False


# ------------------------------------------------------------------ #
# §16 Performance Tests
# ------------------------------------------------------------------ #

class TestPerformance:
    """Performance tracking testlari."""

    def test_tracker(self):
        from vision.performance import PerformanceMetrics, PerformanceTracker
        tracker = PerformanceTracker()
        start = tracker.start_timer()
        time.sleep(0.01)
        elapsed = tracker.end_timer(start)
        assert elapsed > 0

        metrics = PerformanceMetrics(capture_ms=10.0, total_ms=50.0)
        tracker.record(metrics)
        assert tracker.get_last() is not None
        avg = tracker.get_average()
        assert avg.total_ms == 50.0

    def test_screenshot_cache(self):
        from vision.performance import ScreenshotCache
        cache = ScreenshotCache(ttl_seconds=1.0)
        assert cache.get() is None  # miss
        cache.put("test_image")
        assert cache.get() == "test_image"  # hit
        stats = cache.get_stats()
        assert stats["hits"] == 1

    def test_is_slow(self):
        from vision.performance import PerformanceMetrics, PerformanceTracker
        tracker = PerformanceTracker()
        metrics = PerformanceMetrics(total_ms=2000.0)
        tracker.record(metrics)
        assert tracker.is_slow(threshold_ms=1000.0) is True


# ------------------------------------------------------------------ #
# §15 Backend Factory Tests
# ------------------------------------------------------------------ #

class TestBackendFactory:
    """Backend factory testlari."""

    def test_factory_creation(self):
        from vision.backends import BackendFactory
        factory = BackendFactory()
        status = factory.get_status()
        assert "capture" in status
        assert "ocr" in status
        assert "detector" in status

    def test_registry(self):
        from vision.backends import BackendRegistry, BackendStatus
        registry = BackendRegistry()
        registry.register("test_cat", BackendStatus(name="test", available=True, priority=0))
        all_backends = registry.get_all("test_cat")
        assert len(all_backends) == 1
        assert all_backends[0].name == "test"


# ------------------------------------------------------------------ #
# §7 PerceptionEngine Integration
# ------------------------------------------------------------------ #

class TestPerceptionEngine:
    """PerceptionEngine integration testlari."""

    def test_engine_creation(self):
        from vision.perception import PerceptionEngine
        engine = PerceptionEngine()
        assert engine is not None

    def test_context_for_llm(self):
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene, SceneType
        from vision.perception import PerceptionEngine
        engine = PerceptionEngine()
        scene = Scene(
            scene_type=SceneType.BROWSER,
            objects=[
                DetectedObject("b1", ObjectType.BUTTON, BBox(100, 200, 250, 250), 0.9,
                              associated_text="Search", is_interactive=True),
            ],
        )
        ctx = engine.context_for_llm(scene, "search button")
        assert "button" in ctx.lower() or "search" in ctx.lower()

    def test_performance(self):
        from vision.perception import PerceptionEngine
        engine = PerceptionEngine()
        perf = engine.get_performance()
        assert "average" in perf
        assert "cache" in perf


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
