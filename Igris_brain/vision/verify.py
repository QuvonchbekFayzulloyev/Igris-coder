"""§12 Action Verification — before/after comparison, success/failure detection."""
from __future__ import annotations

import time
from typing import Optional

from vision.contracts import (
    ActionVerdict, DetectedObject, Scene, VerificationResult,
)
from vision.temporal import FrameDiff, TemporalVision


class ActionVerifier:
    """Amal tasdig'i — before/after solishtirish."""

    def __init__(self):
        self._temporal = TemporalVision(max_history=5)

    def verify(self, before: Scene, after: Scene,
               expected_change: str = "") -> VerificationResult:
        """Before/after sahnalarni solishtirish."""
        result = VerificationResult(
            verdict=ActionVerdict.UNKNOWN,
            confidence=0.0,
            before_snapshot=before,
            after_snapshot=after,
        )

        diff = self._temporal._compare_scenes(before, after)
        result.appeared_objects = diff.appeared
        result.disappeared_objects = diff.disappeared
        result.changed_objects = diff.changed
        result.page_changed = diff.page_changed

        # NATIJA ANIQLASH
        if diff.page_changed:
            # Sahna butunlay o'zgardi — amal muvaffaqiyatli
            result.verdict = ActionVerdict.SUCCESS
            result.confidence = 0.8
        elif diff.appeared and not diff.disappeared:
            # Yangi obyektlar paydo bo'ldi
            result.verdict = ActionVerdict.SUCCESS
            result.confidence = 0.7
        elif diff.disappeared and not diff.appeared:
            # Obyektlar yo'q bo'ldi — dialog yopilgan bo'lishi mumkin
            result.verdict = ActionVerdict.SUCCESS
            result.confidence = 0.6
        elif diff.changed:
            # Obyektlar o'zgardi (enabled/disabled, text, etc.)
            result.verdict = ActionVerdict.SUCCESS
            result.confidence = 0.5
        elif diff.similarity_score > 0.95:
            # Hech narsa o'zgarmadi — amal ishlamadi
            result.verdict = ActionVerdict.FAILURE
            result.confidence = 0.7
            result.failure_reason = "No visual change detected"
            result.failure_class = "no_change"
        else:
            result.verdict = ActionVerdict.UNKNOWN
            result.confidence = 0.3

        # Expected change bo'yicha qo'shimcha tekshirish
        if expected_change and result.verdict == ActionVerdict.UNKNOWN:
            result = self._check_expected(result, before, after, expected_change)

        return result

    def verify_click(self, before: Scene, after: Scene,
                     target_id: str) -> VerificationResult:
        """Click amalini tasdiqlash."""
        result = self.verify(before, after)

        # Target obyekt o'zgarmagan bo'lsa — click ishlamagan
        target_before = before.get_object_by_id(target_id)
        target_after = after.get_object_by_id(target_id)

        if target_before and target_after:
            if target_before.bbox == target_after.bbox:
                if not result.page_changed:
                    result.confidence *= 0.5

        return result

    def verify_type(self, before: Scene, after: Scene,
                    target_id: str, expected_text: str) -> VerificationResult:
        """Type amalini tasdiqlash."""
        result = self.verify(before, after)

        # Target obyektning matni o'zgarganini tekshirish
        target_after = after.get_object_by_id(target_id)
        if target_after:
            if expected_text.lower() in target_after.associated_text.lower():
                result.verdict = ActionVerdict.SUCCESS
                result.confidence = 0.9
            else:
                result.confidence *= 0.7

        return result

    def verify_navigation(self, before: Scene, after: Scene,
                          expected_title: str = "") -> VerificationResult:
        """Navigatsiya amalini tasdiqlash."""
        result = self.verify(before, after)

        if expected_title:
            if expected_title.lower() in after.window_title.lower():
                result.verdict = ActionVerdict.SUCCESS
                result.confidence = 0.95
            else:
                result.verdict = ActionVerdict.FAILURE
                result.confidence = 0.8
                result.failure_reason = f"Expected title '{expected_title}' not found"
                result.failure_class = "wrong_page"

        return result

    def classify_failure(self, result: VerificationResult) -> str:
        """Xatolik turini aniqlash."""
        if result.verdict != ActionVerdict.FAILURE:
            return ""

        if result.failure_class:
            return result.failure_class

        if not result.page_changed and not result.changed_objects:
            return "no_change"

        if result.disappeared_objects:
            return "element_disappeared"

        return "unknown_failure"

    def should_retry(self, result: VerificationResult) -> bool:
        """Qayta urinish kerakligini aniqlash."""
        if result.verdict == ActionVerdict.SUCCESS:
            return False
        if result.failure_class in ("no_change", "timeout"):
            return True
        if result.failure_class == "ui_changed":
            return False  # UI o'zgargan — qayta aniqlash kerak
        return result.confidence < 0.5

    def _check_expected(self, result: VerificationResult, before: Scene,
                        after: Scene, expected: str) -> VerificationResult:
        """Kutilgan o'zgarishni tekshirish."""
        expected_lower = expected.lower()

        # Yangi matn paydo bo'ldimi?
        for obj in after.objects:
            if obj.associated_text and expected_lower in obj.associated_text.lower():
                if not any(o.associated_text == obj.associated_text
                          for o in before.objects if o.object_id == obj.object_id):
                    result.verdict = ActionVerdict.SUCCESS
                    result.confidence = 0.7
                    return result

        return result
