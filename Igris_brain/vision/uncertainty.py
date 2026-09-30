"""§14 Uncertainty/Safety — confidence threshold, ambiguous targets, do-not-act state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from vision.contracts import BBox, DetectedObject, Scene, Target


@dataclass
class UncertaintyReport:
    """Noaniqlik hisoboti."""
    is_certain: bool
    confidence: float
    issues: list[str]
    recommendation: str  # "act", "retry", "ask_human", "do_not_act"

    def to_dict(self) -> dict:
        return {
            "is_certain": self.is_certain,
            "confidence": round(self.confidence, 3),
            "issues": self.issues,
            "recommendation": self.recommendation,
        }


class UncertaintyDetector:
    """Noaniqlik va xavfsizlikni aniqlash."""

    # Confidence threshold'lari
    HIGH_CONFIDENCE = 0.85
    MEDIUM_CONFIDENCE = 0.6
    LOW_CONFIDENCE = 0.3

    def __init__(self, confidence_threshold: float = 0.6):
        self._threshold = confidence_threshold

    def assess_target(self, target: Target, scene: Scene) -> UncertaintyReport:
        """Target xavfsizligini va ishonchliligini baholash."""
        issues = []
        confidence = target.confidence

        # 1. Past confidence
        if confidence < self.LOW_CONFIDENCE:
            issues.append(f"Very low confidence: {confidence:.0%}")

        # 2. Bir nechta mos obyekt
        if target.label:
            matches = scene.find_objects_by_text(target.label)
            if len(matches) > 1:
                issues.append(f"Ambiguous: {len(matches)} objects match '{target.label}'")

        # 3. Obyekt hali ko'rinishda yo'q
        obj = scene.get_object_by_id(target.object_id)
        if obj is None:
            issues.append("Target object not found in current scene")

        # 4. Coordinate uncertainty (obyekt juda katta yoki kichik)
        if target.bbox.area > 100000:
            issues.append("Very large target — may be imprecise")
        if target.bbox.area < 100:
            issues.append("Very small target — hard to click accurately")

        # 5. Stale screenshot
        screenshot_age = target.bbox.area  # placeholder
        if scene.timestamp:
            import time
            age = time.time() - scene.timestamp
            if age > 5.0:
                issues.append(f"Screenshot is {age:.1f}s old")

        # 6. O'chirilgan element
        obj = scene.get_object_by_id(target.object_id)
        if obj and not obj.is_enabled:
            issues.append("Target element is disabled")

        # NATIJA
        is_certain = len(issues) == 0 and confidence >= self._threshold
        avg_confidence = confidence

        if not issues and confidence >= self.HIGH_CONFIDENCE:
            recommendation = "act"
        elif confidence >= self.MEDIUM_CONFIDENCE and not issues:
            recommendation = "act"
        elif issues and any("not found" in i for i in issues):
            recommendation = "retry"
        elif issues and any("disabled" in i for i in issues):
            recommendation = "do_not_act"
        elif confidence < self.LOW_CONFIDENCE:
            recommendation = "ask_human"
        else:
            recommendation = "retry"

        return UncertaintyReport(
            is_certain=is_certain,
            confidence=avg_confidence,
            issues=issues,
            recommendation=recommendation,
        )

    def assess_scene(self, scene: Scene) -> UncertaintyReport:
        """Sahna umumiy noaniqligini baholash."""
        issues = []

        # 1. Juda kam obyekt
        if len(scene.objects) == 0:
            issues.append("No objects detected in scene")

        # 2. Barcha obyektlar past confidence
        if scene.objects:
            avg_conf = sum(o.confidence for o in scene.objects) / len(scene.objects)
            if avg_conf < self.LOW_CONFIDENCE:
                issues.append(f"Average confidence very low: {avg_conf:.0%}")
        else:
            avg_conf = 0.0

        # 3. Interaktiv element yo'q
        interactive = scene.get_interactive_objects()
        if not interactive:
            issues.append("No interactive elements found")

        # 4. Matn topilmadi
        if not scene.raw_text and not scene.get_objects_with_text():
            issues.append("No text detected on screen")

        is_certain = len(issues) == 0 and avg_conf >= self._threshold

        if not issues:
            recommendation = "act"
        elif len(issues) <= 1:
            recommendation = "retry"
        else:
            recommendation = "ask_human"

        return UncertaintyReport(
            is_certain=is_certain,
            confidence=avg_conf,
            issues=issues,
            recommendation=recommendation,
        )

    def find_best_target(self, candidates: list[Target], scene: Scene) -> Optional[Target]:
        """Eng ishonchli target'ni topish."""
        if not candidates:
            return None

        scored = []
        for target in candidates:
            report = self.assess_target(target, scene)
            score = target.confidence * 0.6
            if report.recommendation == "act":
                score += 0.4
            elif report.recommendation == "retry":
                score += 0.2
            scored.append((score, target))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def is_do_not_act(self, scene: Scene) -> bool:
        """Hozir harakat qilmaslik kerakligini aniqlash."""
        # 1. Ekran bo'sh
        if len(scene.objects) == 0:
            return True
        # 2. Barcha obyektlar past confidence
        if scene.objects:
            avg = sum(o.confidence for o in scene.objects) / len(scene.objects)
            if avg < self.LOW_CONFIDENCE:
                return True
        return False
