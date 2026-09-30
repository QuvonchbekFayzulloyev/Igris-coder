"""§11 Temporal Vision — frame comparison, object tracking, state changes."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from vision.contracts import BBox, DetectedObject, Scene


@dataclass
class FrameDiff:
    """Ikki frame orasidagi farq."""
    appeared: list[DetectedObject] = field(default_factory=list)
    disappeared: list[DetectedObject] = field(default_factory=list)
    moved: list[dict] = field(default_factory=list)  # {id, old_pos, new_pos}
    changed: list[dict] = field(default_factory=list)  # {id, field, old, new}
    page_changed: bool = False
    similarity_score: float = 1.0  # 1.0 = bir xil, 0.0 = butunlay boshqa

    def to_dict(self) -> dict:
        return {
            "appeared": len(self.appeared),
            "disappeared": len(self.disappeared),
            "moved": len(self.moved),
            "changed": len(self.changed),
            "page_changed": self.page_changed,
            "similarity": round(self.similarity_score, 3),
        }


class TemporalVision:
    """Frame'lararo taqqoslash va tracking."""

    def __init__(self, max_history: int = 10):
        self._scenes: list[Scene] = []
        self._max_history = max_history
        # Object tracking — ID saqlab qolish
        self._tracked_objects: dict[str, list[DetectedObject]] = {}

    def update(self, scene: Scene) -> FrameDiff:
        """Yangi scene qo'shish va farqni hisoblash."""
        diff = FrameDiff()

        if not self._scenes:
            self._scenes.append(scene)
            diff.appeared = list(scene.objects)
            return diff

        prev = self._scenes[-1]
        diff = self._compare_scenes(prev, scene)

        self._scenes.append(scene)
        if len(self._scenes) > self._max_history:
            self._scenes.pop(0)

        return diff

    def get_previous_scene(self) -> Optional[Scene]:
        """Oldingi sahnani olish."""
        if len(self._scenes) >= 2:
            return self._scenes[-2]
        return None

    def get_current_scene(self) -> Optional[Scene]:
        """Joriy sahnani olish."""
        if self._scenes:
            return self._scenes[-1]
        return None

    def get_scene_by_index(self, index: int) -> Optional[Scene]:
        """Indeksga ko'ra sahna olish."""
        if 0 <= index < len(self._scenes):
            return self._scenes[index]
        return None

    def get_object轨迹(self, object_id: str) -> list[DetectedObject]:
        """Obyektning ko'rish tarixini olish."""
        trajectory = []
        for scene in self._scenes:
            obj = scene.get_object_by_id(object_id)
            if obj:
                trajectory.append(obj)
        return trajectory

    def detect_state_change(self, object_id: str, field: str) -> Optional[dict]:
        """Obyektning holat o'zgarishini aniqlash."""
        if len(self._scenes) < 2:
            return None

        prev_obj = self._scenes[-2].get_object_by_id(object_id)
        curr_obj = self._scenes[-1].get_object_by_id(object_id)

        if prev_obj is None or curr_obj is None:
            return None

        old_val = getattr(prev_obj, field, None)
        new_val = getattr(curr_obj, field, None)
        if old_val != new_val:
            return {"object_id": object_id, "field": field,
                    "old": old_val, "new": new_val}
        return None

    def _compare_scenes(self, prev: Scene, curr: Scene) -> FrameDiff:
        """Ikki sahnani taqqoslash."""
        diff = FrameDiff()

        prev_ids = {o.object_id for o in prev.objects}
        curr_ids = {o.object_id for o in curr.objects}

        # Paydo bo'lgan obyektlar
        for obj in curr.objects:
            if obj.object_id not in prev_ids:
                diff.appeared.append(obj)

        # Yo'q bo'lgan obyektlar
        for obj in prev.objects:
            if obj.object_id not in curr_ids:
                diff.disappeared.append(obj)

        # O'zgargan obyektlar
        for obj in curr.objects:
            if obj.object_id in prev_ids:
                prev_obj = prev.get_object_by_id(obj.object_id)
                changes = self._compare_objects(prev_obj, obj)
                if changes:
                    diff.changed.extend(changes)

        # Sahna o'zgarganini aniqlash
        common_ids = prev_ids & curr_ids
        if len(common_ids) < max(len(prev_ids), len(curr_ids)) * 0.3:
            diff.page_changed = True

        # Similarity
        if prev_ids or curr_ids:
            intersection = len(prev_ids & curr_ids)
            union = len(prev_ids | curr_ids)
            diff.similarity_score = intersection / union if union > 0 else 0.0

        return diff

    def _compare_objects(self, prev: DetectedObject, curr: DetectedObject) -> list[dict]:
        """Ikki obyektni taqqoslash."""
        changes = []
        fields_to_check = ["bbox", "confidence", "is_enabled",
                           "is_focused", "is_selected", "associated_text"]
        for field_name in fields_to_check:
            old_val = getattr(prev, field_name, None)
            new_val = getattr(curr, field_name, None)
            if old_val != new_val:
                changes.append({
                    "object_id": curr.object_id,
                    "field": field_name,
                    "old": str(old_val)[:100],
                    "new": str(new_val)[:100],
                })
        return changes
