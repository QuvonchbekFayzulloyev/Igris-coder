"""IGRIS Vision — LLM-independent Custom Vision System.

Istalgan text-only LLMga "ko'z beradi". Vision alohida modelning
ichki funksiyasi emas — IGRIS'ning umumiy sensor subsystemi.

Core contract:
    Vision.observe() -> Scene -> Objects -> Relations -> Target -> Action -> New Scene -> Verification
"""

from vision.contracts import (
    BBox,
    DetectedObject,
    Scene,
    SpatialRelation,
    Target,
    VerificationResult,
)
from vision.perception import PerceptionEngine
from vision.context import VisionContextBuilder
from vision.action_bridge import ActionBridge
from vision.verify import ActionVerifier

__all__ = [
    "BBox",
    "DetectedObject",
    "Scene",
    "SpatialRelation",
    "Target",
    "VerificationResult",
    "PerceptionEngine",
    "VisionContextBuilder",
    "ActionBridge",
    "ActionVerifier",
]
