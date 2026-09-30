"""§5 Spatial Understanding — bounding boxes, relative positions, nearest object."""
from __future__ import annotations

from typing import Optional

from vision.contracts import (
    BBox, DetectedObject, ObjectType, SpatialOp, SpatialRelation,
)


class SpatialEngine:
    """Obyektlar orasidagi joylashuv munosabatlarini hisoblash."""

    def compute_relations(self, objects: list[DetectedObject]) -> list[SpatialRelation]:
        """Barcha obyektlar orasidagi munosabatlarni hisoblash."""
        relations = []
        for i, a in enumerate(objects):
            for j, b in enumerate(objects):
                if i >= j:
                    continue
                rels = self._compute_pair(a, b)
                relations.extend(rels)
        return relations

    def compute_relations_for(self, target: DetectedObject,
                               objects: list[DetectedObject]) -> list[SpatialRelation]:
        """Bitta obyekt uchun boshqa obyektlar bilan munosabatlar."""
        relations = []
        for other in objects:
            if other.object_id == target.object_id:
                continue
            rels = self._compute_pair(target, other)
            relations.extend(rels)
        return relations

    def find_nearest(self, obj: DetectedObject,
                     objects: list[DetectedObject],
                     relation: Optional[SpatialOp] = None) -> Optional[DetectedObject]:
        """Eng yaqin obyektni topish (ixtiyoriy yo'nalish bo'yicha)."""
        nearest = None
        min_dist = float("inf")
        for other in objects:
            if other.object_id == obj.object_id:
                continue
            dist = obj.bbox.distance_to(other.bbox)
            if dist < min_dist:
                if relation is not None:
                    if self._check_relation(obj, other, relation):
                        min_dist = dist
                        nearest = other
                else:
                    min_dist = dist
                    nearest = other
        return nearest

    def find_by_relation(self, source: DetectedObject,
                         relation: SpatialOp,
                         objects: list[DetectedObject]) -> list[DetectedObject]:
        """Berilgan munosabatga mos obyektlarni topish."""
        results = []
        for other in objects:
            if other.object_id == source.object_id:
                continue
            if self._check_relation(source, other, relation):
                results.append(other)
        return results

    def find_by_text(self, text: str, scene_objects: list[DetectedObject]) -> Optional[DetectedObject]:
        """Matn bo'yicha obyektni topish."""
        text_lower = text.lower()
        for obj in scene_objects:
            if text_lower in obj.associated_text.lower():
                return obj
            if text_lower in obj.label.lower():
                return obj
        return None

    def get_bounding_box(self, objects: list[DetectedObject]) -> Optional[BBox]:
        """Obyektlar guruhining umumiy bounding box'ini olish."""
        if not objects:
            return None
        x1 = min(o.bbox.x1 for o in objects)
        y1 = min(o.bbox.y1 for o in objects)
        x2 = max(o.bbox.x2 for o in objects)
        y2 = max(o.bbox.y2 for o in objects)
        return BBox(x1, y1, x2, y2)

    def compute_group_center(self, objects: list[DetectedObject]) -> Optional[tuple[int, int]]:
        """Obyektlar guruhining markazini hisoblash."""
        if not objects:
            return None
        xs = [o.center[0] for o in objects]
        ys = [o.center[1] for o in objects]
        return (sum(xs) // len(xs), sum(ys) // len(ys))

    # --- Private helpers ---

    def _compute_pair(self, a: DetectedObject, b: DetectedObject) -> list[SpatialRelation]:
        """Ikki obyekt orasidagi barcha munosabatlarni aniqlash."""
        relations = []
        acx, acy = a.bbox.center
        bcx, bcy = b.bbox.center
        dist = a.bbox.distance_to(b.bbox)

        # Chap / O'ng
        if acx < bcx - 10:
            relations.append(SpatialRelation(a.object_id, b.object_id, SpatialOp.LEFT_OF, dist))
        if acx > bcx + 10:
            relations.append(SpatialRelation(a.object_id, b.object_id, SpatialOp.RIGHT_OF, dist))

        # Yuqori / Past
        if acy < bcy - 10:
            relations.append(SpatialRelation(a.object_id, b.object_id, SpatialOp.ABOVE, dist))
        if acy > bcy + 10:
            relations.append(SpatialRelation(a.object_id, b.object_id, SpatialOp.BELOW, dist))

        # Ichida / Tashqarida
        if a.bbox.contains_point(b.bbox.x1, b.bbox.y1):
            relations.append(SpatialRelation(a.object_id, b.object_id, SpatialOp.CONTAINS, dist))
        if b.bbox.contains_point(a.bbox.x1, a.bbox.y1):
            relations.append(SpatialRelation(b.object_id, a.object_id, SpatialOp.INSIDE, dist))

        # Overlaps
        if a.bbox.overlaps(b.bbox):
            relations.append(SpatialRelation(a.object_id, b.object_id, SpatialOp.OVERLAPS, dist))

        # Near (< 100px)
        if dist < 100:
            relations.append(SpatialRelation(a.object_id, b.object_id, SpatialOp.NEAR, dist))

        return relations

    def _check_relation(self, source: DetectedObject, target: DetectedObject,
                        relation: SpatialOp) -> bool:
        """Aniq munosabat mavjudligini tekshirish."""
        acx, acy = source.bbox.center
        bcx, bcy = target.bbox.center

        if relation == SpatialOp.LEFT_OF:
            return acx < bcx - 10
        if relation == SpatialOp.RIGHT_OF:
            return acx > bcx + 10
        if relation == SpatialOp.ABOVE:
            return acy < bcy - 10
        if relation == SpatialOp.BELOW:
            return acy > bcy + 10
        if relation == SpatialOp.INSIDE:
            return target.bbox.contains_point(source.bbox.x1, source.bbox.y1)
        if relation == SpatialOp.CONTAINS:
            return source.bbox.contains_point(target.bbox.x1, target.bbox.y1)
        if relation == SpatialOp.OVERLAPS:
            return source.bbox.overlaps(target.bbox)
        if relation == SpatialOp.NEAR:
            return source.bbox.distance_to(target.bbox) < 100
        return False
