"""§0 Architectural Contract — core protocols & data models.

Barcha vision komponentlari shu kontrakt orqali muloqot qiladi.
LLM hech qachon pixel koordinatasini o'zi taxmin qilmaydi.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ------------------------------------------------------------------ #
# Enums
# ------------------------------------------------------------------ #

class ObjectType(str, Enum):
    """Obyekt turlari."""
    BUTTON = "button"
    INPUT = "input"
    CHECKBOX = "checkbox"
    MENU = "menu"
    DIALOG = "dialog"
    ICON = "icon"
    IMAGE = "image"
    TEXT = "text"
    LINK = "link"
    DROPDOWN = "dropdown"
    TAB = "tab"
    TOOLBAR = "toolbar"
    PANEL = "panel"
    WINDOW = "window"
    UNKNOWN = "unknown"


class SpatialOp(str, Enum):
    """Joylashuv munosabatlari."""
    LEFT_OF = "left_of"
    RIGHT_OF = "right_of"
    ABOVE = "above"
    BELOW = "below"
    INSIDE = "inside"
    CONTAINS = "contains"
    OVERLAPS = "overlaps"
    NEAR = "near"


class SceneType(str, Enum):
    """Sahna turlari."""
    DESKTOP = "desktop"
    BROWSER = "browser"
    FILE_EXPLORER = "file_explorer"
    SETTINGS = "settings"
    TEXT_EDITOR = "text_editor"
    TERMINAL = "terminal"
    DIALOG = "dialog"
    APPLICATION = "application"
    UNKNOWN = "unknown"


class ActionVerdict(str, Enum):
    """Amal natijasi."""
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


class ElementType(str, Enum):
    """UI element turlari."""
    BUTTON = "button"
    INPUT = "input"
    TEXT_FIELD = "text_field"
    TEXT_AREA = "text_area"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    DROPDOWN = "dropdown"
    MENU = "menu"
    MENU_ITEM = "menu_item"
    LINK = "link"
    ICON = "icon"
    IMAGE = "image"
    LABEL = "label"
    TAB = "tab"
    TOOLBAR = "toolbar"
    PANEL = "panel"
    TREE = "tree"
    LIST = "list"
    TABLE = "table"
    SCROLLBAR = "scrollbar"
    WINDOW = "window"
    DIALOG = "dialog"
    UNKNOWN = "unknown"


# ------------------------------------------------------------------ #
# Data Classes
# ------------------------------------------------------------------ #

@dataclass
class BBox:
    """Bounding box — pixel koordinatalar."""
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def center(self) -> tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    @property
    def area(self) -> int:
        return self.width * self.height

    def contains_point(self, x: int, y: int) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    def overlaps(self, other: "BBox") -> bool:
        return not (self.x2 < other.x1 or self.x1 > other.x2 or
                    self.y2 < other.y1 or self.y1 > other.y2)

    def distance_to(self, other: "BBox") -> float:
        cx1, cy1 = self.center
        cx2, cy2 = other.center
        return ((cx2 - cx1) ** 2 + (cy2 - cy1) ** 2) ** 0.5

    def to_dict(self) -> dict:
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

    @classmethod
    def from_dict(cls, d: dict) -> "BBox":
        return cls(x1=d["x1"], y1=d["y1"], x2=d["x2"], y2=d["y2"])


@dataclass
class DetectedObject:
    """ aniqlangan obyekt — perception natijasi."""
    object_id: str
    object_type: ObjectType
    bbox: BBox
    confidence: float
    label: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    # OCR bilan bog'langan matn (agar mavjud bo'lsa)
    associated_text: str = ""
    text_confidence: float = 0.0
    # Interactive element ma'lumotlari
    is_interactive: bool = False
    is_enabled: bool = True
    is_focused: bool = False
    is_selected: bool = False
    # Vaqt belgisi
    detected_at: float = field(default_factory=time.time)

    @property
    def center(self) -> tuple[int, int]:
        return self.bbox.center

    def to_dict(self) -> dict:
        return {
            "object_id": self.object_id,
            "object_type": self.object_type.value,
            "bbox": self.bbox.to_dict(),
            "confidence": self.confidence,
            "label": self.label,
            "properties": self.properties,
            "associated_text": self.associated_text,
            "is_interactive": self.is_interactive,
            "is_enabled": self.is_enabled,
        }


@dataclass
class SpatialRelation:
    """Ikki obyekt orasidagi joylashuv munosabati."""
    source_id: str
    target_id: str
    relation: SpatialOp
    distance: float = 0.0
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation.value,
            "distance": self.distance,
        }


@dataclass
class Scene:
    """Sahna — bir vaqtdagi to'liq vizual holat."""
    scene_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    scene_type: SceneType = SceneType.UNKNOWN
    objects: list[DetectedObject] = field(default_factory=list)
    relations: list[SpatialRelation] = field(default_factory=list)
    raw_text: str = ""  # OCR dan olingan to'liq matn
    screenshot_path: str = ""
    timestamp: float = field(default_factory=time.time)
    width: int = 0
    height: int = 0
    # Application info
    app_name: str = ""
    window_title: str = ""
    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_objects_by_type(self, obj_type: ObjectType) -> list[DetectedObject]:
        return [o for o in self.objects if o.object_type == obj_type]

    def get_interactive_objects(self) -> list[DetectedObject]:
        return [o for o in self.objects if o.is_interactive]

    def get_object_by_id(self, object_id: str) -> Optional[DetectedObject]:
        for o in self.objects:
            if o.object_id == object_id:
                return o
        return None

    def get_objects_with_text(self) -> list[DetectedObject]:
        return [o for o in self.objects if o.associated_text.strip()]

    def find_objects_by_text(self, text: str) -> list[DetectedObject]:
        text_lower = text.lower()
        return [o for o in self.objects
                if text_lower in o.associated_text.lower()
                or text_lower in o.label.lower()]

    def to_dict(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "scene_type": self.scene_type.value,
            "objects": [o.to_dict() for o in self.objects],
            "relations": [r.to_dict() for r in self.relations],
            "raw_text": self.raw_text[:500],
            "width": self.width,
            "height": self.height,
            "app_name": self.app_name,
            "window_title": self.window_title,
            "timestamp": self.timestamp,
        }


@dataclass
class Target:
    """Action uchun maqsadli obyekt — LLM faqat object_id ayta oladi."""
    object_id: str
    bbox: BBox
    center: tuple[int, int]
    confidence: float
    label: str = ""
    object_type: ObjectType = ObjectType.UNKNOWN
    # Safety
    is_safe: bool = True
    safety_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "object_id": self.object_id,
            "bbox": self.bbox.to_dict(),
            "center": list(self.center),
            "confidence": self.confidence,
            "label": self.label,
            "object_type": self.object_type.value,
            "is_safe": self.is_safe,
        }


@dataclass
class VerificationResult:
    """Amal tasdig'i — before/after solishtirish natijasi."""
    verdict: ActionVerdict
    confidence: float
    before_snapshot: Optional[Scene] = None
    after_snapshot: Optional[Scene] = None
    # O'zgarishlar
    appeared_objects: list[DetectedObject] = field(default_factory=list)
    disappeared_objects: list[DetectedObject] = field(default_factory=list)
    changed_objects: list[dict] = field(default_factory=list)
    page_changed: bool = False
    # Xatolik
    failure_reason: str = ""
    failure_class: str = ""  # "timeout", "wrong_target", "ui_changed", etc.

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "confidence": self.confidence,
            "page_changed": self.page_changed,
            "appeared": len(self.appeared_objects),
            "disappeared": len(self.disappeared_objects),
            "changed": len(self.changed_objects),
            "failure_reason": self.failure_reason,
            "failure_class": self.failure_class,
        }


# ------------------------------------------------------------------ #
# Protocols (Interface contracts)
# ------------------------------------------------------------------ #

class CaptureBackend:
    """§1 Screenshot capture backend interfeysi."""

    def capture_screen(self) -> tuple[Any, dict]:
        """To'liq ekran suratini olish. Returns (image_array, metadata)."""
        raise NotImplementedError

    def capture_window(self, window_id: str) -> tuple[Any, dict]:
        """Aniq oynani suratini olish."""
        raise NotImplementedError

    def capture_region(self, x1: int, y1: int, x2: int, y2: int) -> tuple[Any, dict]:
        """Aniq hududni suratini olish."""
        raise NotImplementedError

    def get_active_window(self) -> dict:
        """Joriy faol oyna haqida ma'lumot."""
        raise NotImplementedError


class PreprocessorBackend:
    """§2 Image preprocessing backend interfeysi."""

    def resize(self, image: Any, width: int, height: int) -> Any:
        raise NotImplementedError

    def crop(self, image: Any, bbox: BBox) -> Any:
        raise NotImplementedError

    def normalize(self, image: Any) -> Any:
        raise NotImplementedError

    def to_grayscale(self, image: Any) -> Any:
        raise NotImplementedError


class ObjectDetectorBackend:
    """§3 Object detection backend interfeysi."""

    def detect(self, image: Any) -> list[DetectedObject]:
        """Obyektlarni aniqlash."""
        raise NotImplementedError

    def detect_ui_elements(self, image: Any) -> list[DetectedObject]:
        """UI elementlarini aniqlash."""
        raise NotImplementedError


class OCRBackend:
    """§4 OCR backend interfeysi."""

    def extract_text(self, image: Any) -> list[dict]:
        """Matnni ajratib olish. Returns list of {text, bbox, confidence, language}."""
        raise NotImplementedError

    def extract_text_blocks(self, image: Any) -> list[dict]:
        """Matn bloklarini ajratib olish."""
        raise NotImplementedError


class SpatialEngine:
    """§5 Spatial understanding engine."""

    def compute_relations(self, objects: list[DetectedObject]) -> list[SpatialRelation]:
        """Obyektlar orasidagi munosabatlarni hisoblash."""
        raise NotImplementedError

    def find_nearest(self, obj: DetectedObject, objects: list[DetectedObject],
                     relation: Optional[SpatialOp] = None) -> Optional[DetectedObject]:
        """Eng yaqin obyektni topish."""
        raise NotImplementedError


class SceneAnalyzer:
    """§6 UI/Desktop scene analyzer."""

    def analyze(self, scene: Scene) -> Scene:
        """Sahnani tahlil qilish — app/window identification, UI hierarchy."""
        raise NotImplementedError

    def identify_application(self, scene: Scene) -> str:
        """Ilovani aniqlash."""
        raise NotImplementedError

    def identify_ui_elements(self, scene: Scene) -> list[DetectedObject]:
        """UI elementlarini aniqlash va belgilash."""
        raise NotImplementedError


class ActionBridgeInterface:
    """§10 Action bridge interfeysi."""

    def resolve_target(self, scene: Scene, description: str) -> Optional[Target]:
        """Tavsifdan maqsadli obyektni aniqlash."""
        raise NotImplementedError

    def click(self, target: Target) -> dict:
        raise NotImplementedError

    def double_click(self, target: Target) -> dict:
        raise NotImplementedError

    def right_click(self, target: Target) -> dict:
        raise NotImplementedError

    def type_text(self, target: Target, text: str) -> dict:
        raise NotImplementedError

    def scroll(self, target: Target, direction: str, amount: int) -> dict:
        raise NotImplementedError


class VerifierInterface:
    """§12 Action verification interfeysi."""

    def verify(self, before: Scene, after: Scene,
               expected_change: str = "") -> VerificationResult:
        raise NotImplementedError


class VisionMemoryInterface:
    """§13 Vision memory interfeysi."""

    def store_scene(self, scene: Scene) -> None:
        raise NotImplementedError

    def get_previous_scene(self) -> Optional[Scene]:
        raise NotImplementedError

    def get_object_history(self, object_id: str) -> list[dict]:
        raise NotImplementedError

    def forget_irrelevant(self, max_age_seconds: float = 300.0) -> None:
        raise NotImplementedError
