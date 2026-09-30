"""§13 Vision Memory — scene history, object tracking, state persistence."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from vision.contracts import DetectedObject, Scene


@dataclass
class ObjectRecord:
    """Obyekt tarixi."""
    object_id: str
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    appearances: int = 1
    states: list[dict] = field(default_factory=list)
    # Identity — obyekt ID saqlab qolish
    label: str = ""
    object_type: str = ""

    def update(self, obj: DetectedObject) -> None:
        self.last_seen = time.time()
        self.appearances += 1
        self.states.append({
            "confidence": obj.confidence,
            "bbox": obj.bbox.to_dict(),
            "text": obj.associated_text,
            "enabled": obj.is_enabled,
            "timestamp": time.time(),
        })
        if len(self.states) > 50:
            self.states = self.states[-50:]


class VisionMemory:
    """Sahna tarixi va obyektlarni kuzatish."""

    def __init__(self, max_scenes: int = 20, max_objects: int = 200):
        self._scenes: list[Scene] = []
        self._max_scenes = max_scenes
        self._object_records: dict[str, ObjectRecord] = {}
        self._max_objects = max_objects

    def store_scene(self, scene: Scene) -> None:
        """Sahnani saqlash."""
        self._scenes.append(scene)
        if len(self._scenes) > self._max_scenes:
            self._scenes.pop(0)

        # Obyektlarni yangilash
        for obj in scene.objects:
            if obj.object_id in self._object_records:
                self._object_records[obj.object_id].update(obj)
            else:
                rec = ObjectRecord(
                    object_id=obj.object_id,
                    label=obj.label,
                    object_type=obj.object_type.value,
                )
                rec.update(obj)
                self._object_records[obj.object_id] = rec

        # Nazorat qilinmaydi
        if len(self._object_records) > self._max_objects:
            self._cleanup_old_records()

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

    def get_scene_history(self, count: int = 5) -> list[Scene]:
        """Oxirgi N ta sahnani olish."""
        return self._scenes[-count:]

    def get_object_history(self, object_id: str) -> list[dict]:
        """Obyekt tarixini olish."""
        rec = self._object_records.get(object_id)
        if rec:
            return rec.states
        return []

    def get_object_record(self, object_id: str) -> Optional[ObjectRecord]:
        """Obyekt record'ini olish."""
        return self._object_records.get(object_id)

    def find_persistent_objects(self, min_appearances: int = 3) -> list[ObjectRecord]:
        """Ko'p marta ko'rilgan obyektlarni topish."""
        return [rec for rec in self._object_records.values()
                if rec.appearances >= min_appearances]

    def find_recent_objects(self, max_age: float = 5.0) -> list[DetectedObject]:
        """Oxirgi soniyalarda ko'rilgan obyektlarni topish."""
        now = time.time()
        objects = []
        for scene in reversed(self._scenes):
            if now - scene.timestamp > max_age:
                break
            objects.extend(scene.objects)
        return objects

    def get_disappeared_objects(self, max_age: float = 10.0) -> list[ObjectRecord]:
        """Yo'q bo'lgan obyektlarni topish."""
        now = time.time()
        disappeared = []
        for rec in self._object_records.values():
            if now - rec.last_seen > max_age and rec.appearances > 1:
                disappeared.append(rec)
        return disappeared

    def forget_irrelevant(self, max_age_seconds: float = 300.0) -> None:
        """Eski ma'lumotlarni unutish."""
        now = time.time()
        # Eski sahnalar
        self._scenes = [s for s in self._scenes
                        if now - s.timestamp < max_age_seconds]
        # Eski obyekt record'lari
        to_delete = []
        for oid, rec in self._object_records.items():
            if now - rec.last_seen > max_age_seconds:
                to_delete.append(oid)
        for oid in to_delete:
            del self._object_records[oid]

    def get_statistics(self) -> dict:
        """Statistika."""
        return {
            "scenes_stored": len(self._scenes),
            "objects_tracked": len(self._object_records),
            "total_appearances": sum(r.appearances for r in self._object_records.values()),
        }

    def _cleanup_old_records(self) -> None:
        """Eng eski record'larni tozalash."""
        if len(self._object_records) <= self._max_objects:
            return
        sorted_records = sorted(
            self._object_records.items(),
            key=lambda x: x[1].last_seen,
        )
        to_remove = len(self._object_records) - self._max_objects
        for oid, _ in sorted_records[:to_remove]:
            del self._object_records[oid]
