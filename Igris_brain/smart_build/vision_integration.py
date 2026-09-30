"""Vision-Smart Build Integration — Vision System ni Smart Build bilan bog'lash.

Core principle: Vision orqali real tizim holatini tekshirish, Smart Build evidence'ini to'ldirish.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from vision.contracts import Scene, DetectedObject, ObjectType
from smart_build.deterministic_executor import ExecutionEvidence, ExecutionAction, ExecutionStatus
from smart_build.verifier import Evidence as VerifierEvidence


class VisionCheckType(str, Enum):
    """Vision tekshiruv turlari."""
    UI_ELEMENT_EXISTS = "ui_element_exists"
    UI_ELEMENT_VISIBLE = "ui_element_visible"
    UI_ELEMENT_CLICKED = "ui_element_clicked"
    UI_ELEMENT_TYPED = "ui_element_typed"
    PAGE_LOADED = "page_loaded"
    ERROR_VISIBLE = "error_visible"
    SUCCESS_VISIBLE = "success_visible"
    TEXT_MATCHES = "text_matches"
    STATE_CHANGED = "state_changed"


@dataclass
class VisionEvidence:
    """Vision-based evidence."""
    check_type: VisionCheckType
    status: ExecutionStatus
    description: str = ""
    object_id: str = ""
    confidence: float = 0.0
    screenshot_path: str = ""
    details: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "check_type": self.check_type.value,
            "status": self.status.value,
            "description": self.description,
            "object_id": self.object_id,
            "confidence": round(self.confidence, 3),
        }

    def to_verifier_evidence(self) -> VerifierEvidence:
        """VerifierEvidence ga aylantirish."""
        return VerifierEvidence(
            evidence_type="vision",
            description=self.description,
            passed=self.status == ExecutionStatus.SUCCESS,
            details=self.details,
        )


@dataclass
class VisionVerificationResult:
    """Vision verification natijasi."""
    task: str
    checks: list[VisionEvidence] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    total: int = 0
    confidence: float = 0.0
    screenshot_before: str = ""
    screenshot_after: str = ""

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "checks": [c.to_dict() for c in self.checks],
            "passed": self.passed,
            "failed": self.failed,
            "total": self.total,
            "confidence": round(self.confidence, 3),
        }


class VisionSmartBuildIntegration:
    """Vision System + Smart Build integratsiya.

    Vision orqali:
    1. UI element mavjudligini tekshirish
    2. Click/Type amalini bajarish va tasdiqlash
    3. Error/Success messageni aniqlash
    4. State o'zgarishini tekshirish
    """

    def __init__(self, vision_engine=None):
        self._vision = vision_engine

    def check_ui_element(self, description: str, action: str = "exists") -> VisionEvidence:
        """UI element mavjudligini/e'lon qilishini tekshirish."""
        if not self._vision:
            return VisionEvidence(
                check_type=VisionCheckType.UI_ELEMENT_EXISTS,
                status=ExecutionStatus.UNKNOWN,
                description="Vision engine not available",
            )

        try:
            scene = self._vision.observe()
            target = self._vision.find_target(scene, description)

            if target is None:
                return VisionEvidence(
                    check_type=VisionCheckType.UI_ELEMENT_EXISTS,
                    status=ExecutionStatus.FAILED,
                    description=f"UI element '{description}' not found",
                )

            return VisionEvidence(
                check_type=VisionCheckType.UI_ELEMENT_EXISTS,
                status=ExecutionStatus.SUCCESS,
                description=f"UI element '{description}' found",
                object_id=target.object_id,
                confidence=target.confidence,
            )
        except Exception as e:
            return VisionEvidence(
                check_type=VisionCheckType.UI_ELEMENT_EXISTS,
                status=ExecutionStatus.FAILED,
                description=f"Vision check failed: {e}",
            )

    def click_element(self, description: str) -> VisionEvidence:
        """UI elementni bosish."""
        if not self._vision:
            return VisionEvidence(
                check_type=VisionCheckType.UI_ELEMENT_CLICKED,
                status=ExecutionStatus.UNKNOWN,
                description="Vision engine not available",
            )

        try:
            scene = self._vision.observe()
            target = self._vision.find_target(scene, description)

            if target is None:
                return VisionEvidence(
                    check_type=VisionCheckType.UI_ELEMENT_CLICKED,
                    status=ExecutionStatus.FAILED,
                    description=f"Target '{description}' not found for click",
                )

            if not target.is_safe:
                return VisionEvidence(
                    check_type=VisionCheckType.UI_ELEMENT_CLICKED,
                    status=ExecutionStatus.FAILED,
                    description=f"Unsafe click: {target.safety_reason}",
                )

            from vision.action_bridge import ActionBridge
            bridge = ActionBridge(safety_enabled=True)
            result = bridge.click(target)

            return VisionEvidence(
                check_type=VisionCheckType.UI_ELEMENT_CLICKED,
                status=ExecutionStatus.SUCCESS if result.success else ExecutionStatus.FAILED,
                description=f"Clicked '{description}': {result.message}",
                object_id=target.object_id,
                confidence=target.confidence,
                details=str(result.to_dict()),
            )
        except Exception as e:
            return VisionEvidence(
                check_type=VisionCheckType.UI_ELEMENT_CLICKED,
                status=ExecutionStatus.FAILED,
                description=f"Click failed: {e}",
            )

    def type_text(self, target_description: str, text: str) -> VisionEvidence:
        """UI elementga matn kiritish."""
        if not self._vision:
            return VisionEvidence(
                check_type=VisionCheckType.UI_ELEMENT_TYPED,
                status=ExecutionStatus.UNKNOWN,
                description="Vision engine not available",
            )

        try:
            scene = self._vision.observe()
            target = self._vision.find_target(scene, target_description)

            if target is None:
                return VisionEvidence(
                    check_type=VisionCheckType.UI_ELEMENT_TYPED,
                    status=ExecutionStatus.FAILED,
                    description=f"Target '{target_description}' not found for typing",
                )

            from vision.action_bridge import ActionBridge
            bridge = ActionBridge(safety_enabled=True)
            result = bridge.type_text(target, text)

            return VisionEvidence(
                check_type=VisionCheckType.UI_ELEMENT_TYPED,
                status=ExecutionStatus.SUCCESS if result.success else ExecutionStatus.FAILED,
                description=f"Typed in '{target_description}': {result.message}",
                object_id=target.object_id,
                confidence=target.confidence,
            )
        except Exception as e:
            return VisionEvidence(
                check_type=VisionCheckType.UI_ELEMENT_TYPED,
                status=ExecutionStatus.FAILED,
                description=f"Type failed: {e}",
            )

    def check_error_visible(self, error_text: str = "") -> VisionEvidence:
        """Error message ko'rinayotganini tekshirish."""
        if not self._vision:
            return VisionEvidence(
                check_type=VisionCheckType.ERROR_VISIBLE,
                status=ExecutionStatus.UNKNOWN,
                description="Vision engine not available",
            )

        try:
            scene = self._vision.observe()
            # Error elements qidirish
            error_indicators = ["error", "xato", "failed", "exception", "warning"]
            for obj in scene.objects:
                text = (obj.associated_text or "").lower()
                if any(ind in text for ind in error_indicators):
                    if not error_text or error_text.lower() in text:
                        return VisionEvidence(
                            check_type=VisionCheckType.ERROR_VISIBLE,
                            status=ExecutionStatus.FAILED,
                            description=f"Error visible: {obj.associated_text}",
                            object_id=obj.object_id,
                            confidence=obj.confidence,
                        )

            return VisionEvidence(
                check_type=VisionCheckType.ERROR_VISIBLE,
                status=ExecutionStatus.SUCCESS,
                description="No error visible",
            )
        except Exception as e:
            return VisionEvidence(
                check_type=VisionCheckType.ERROR_VISIBLE,
                status=ExecutionStatus.UNKNOWN,
                description=f"Error check failed: {e}",
            )

    def check_success_visible(self, success_text: str = "") -> VisionEvidence:
        """Success message ko'rinayotganini tekshirish."""
        if not self._vision:
            return VisionEvidence(
                check_type=VisionCheckType.SUCCESS_VISIBLE,
                status=ExecutionStatus.UNKNOWN,
                description="Vision engine not available",
            )

        try:
            scene = self._vision.observe()
            success_indicators = ["success", "muvaffaqiyat", "completed", "done", "tayyor"]
            for obj in scene.objects:
                text = (obj.associated_text or "").lower()
                if any(ind in text for ind in success_indicators):
                    if not success_text or success_text.lower() in text:
                        return VisionEvidence(
                            check_type=VisionCheckType.SUCCESS_VISIBLE,
                            status=ExecutionStatus.SUCCESS,
                            description=f"Success visible: {obj.associated_text}",
                            object_id=obj.object_id,
                            confidence=obj.confidence,
                        )

            return VisionEvidence(
                check_type=VisionCheckType.SUCCESS_VISIBLE,
                status=ExecutionStatus.FAILED,
                description="No success message visible",
            )
        except Exception as e:
            return VisionEvidence(
                check_type=VisionCheckType.SUCCESS_VISIBLE,
                status=ExecutionStatus.UNKNOWN,
                description=f"Success check failed: {e}",
            )

    def verify_action(self, before_scene: dict, action: str) -> VisionVerificationResult:
        """Amal tasdig'i — oldingi va hozirgi sahnani solishtirish."""
        result = VisionVerificationResult(task=action)

        if not self._vision:
            result.checks.append(VisionEvidence(
                check_type=VisionCheckType.STATE_CHANGED,
                status=ExecutionStatus.UNKNOWN,
                description="Vision engine not available",
            ))
            result.total = 1
            return result

        try:
            after_scene = self._vision.observe()
            verification = self._vision.verify_action(before_scene, after_scene, action)

            result.passed = 1 if verification.success else 0
            result.failed = 0 if verification.success else 1
            result.total = 1
            result.confidence = verification.confidence

            result.checks.append(VisionEvidence(
                check_type=VisionCheckType.STATE_CHANGED,
                status=ExecutionStatus.SUCCESS if verification.success else ExecutionStatus.FAILED,
                description=f"Action '{action}': {verification.message}",
                confidence=verification.confidence,
            ))

        except Exception as e:
            result.checks.append(VisionEvidence(
                check_type=VisionCheckType.STATE_CHANGED,
                status=ExecutionStatus.FAILED,
                description=f"Verification failed: {e}",
            ))
            result.failed = 1
            result.total = 1

        return result

    def get_performance(self) -> dict:
        """Vision performansini olish."""
        if not self._vision:
            return {"error": "Vision engine not available"}
        return self._vision.get_performance()


def create_vision_smart_build(vision_engine=None) -> VisionSmartBuildIntegration:
    """Vision-Smart Build integratsiyasini yaratish."""
    return VisionSmartBuildIntegration(vision_engine)
