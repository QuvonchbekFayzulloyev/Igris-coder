"""§8 Vision Context Builder — LLM uchun text/JSON representation yaratish.

LLM pixel koordinatasini o'zi taxmin qilmaydi — faqat object_id ishlatadi.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from vision.contracts import (
    BBox, DetectedObject, ObjectType, Scene, SceneType, SpatialRelation,
)


class VisionContextBuilder:
    """Perception natijasini LLM uchun text context ga aylantirish."""

    def build_text_context(self, scene: Scene, max_objects: int = 30) -> str:
        """Sahnani LLM uchun matn representation sifatida yaratish."""
        lines = []
        lines.append(f"[SCENE] {scene.scene_type.value} | {scene.width}x{scene.height}")
        if scene.window_title:
            lines.append(f"[WINDOW] {scene.window_title}")

        # Interactive obyektlar
        interactive = scene.get_interactive_objects()
        if interactive:
            lines.append(f"\n[INTERACTIVE ELEMENTS] ({len(interactive)} ta)")
            for obj in interactive[:max_objects]:
                line = self._format_object_line(obj)
                lines.append(f"  {line}")

        # Matn bloklari
        text_objects = scene.get_objects_with_text()
        if text_objects:
            lines.append(f"\n[TEXT ELEMENTS] ({len(text_objects)} ta)")
            for obj in text_objects[:max_objects]:
                lines.append(f"  {obj.object_id}: \"{obj.associated_text[:80]}\"")

        # Sahna matni (OCR)
        if scene.raw_text:
            preview = scene.raw_text[:500].replace("\n", " ")
            lines.append(f"\n[SCREEN TEXT]\n  {preview}")

        # Muhim obyektlar (yuqori confidence)
        important = [o for o in scene.objects if o.confidence > 0.8
                     and o not in interactive]
        if important:
            lines.append(f"\n[OTHER OBJECTS] ({len(important)} ta)")
            for obj in important[:10]:
                lines.append(f"  {self._format_object_line(obj)}")

        return "\n".join(lines)

    def build_json_context(self, scene: Scene, max_objects: int = 30) -> dict:
        """Sahnani JSON representation sifatida yaratish."""
        context = {
            "scene_type": scene.scene_type.value,
            "dimensions": {"width": scene.width, "height": scene.height},
            "window_title": scene.window_title,
            "objects": [],
            "relations": [],
        }

        # Interactive obyektlar birinchi
        interactive = scene.get_interactive_objects()
        other = [o for o in scene.objects if o not in interactive]

        for obj in (interactive + other)[:max_objects]:
            context["objects"].append({
                "id": obj.object_id,
                "type": obj.object_type.value,
                "label": obj.label,
                "text": obj.associated_text[:100] if obj.associated_text else "",
                "interactive": obj.is_interactive,
                "enabled": obj.is_enabled,
                "confidence": round(obj.confidence, 2),
            })

        for rel in scene.relations[:50]:
            context["relations"].append(rel.to_dict())

        return context

    def build_action_prompt(self, scene: Scene, task: str) -> str:
        """Action uchun prompt yaratish — LLM faqat object_id ayta oladi."""
        context = self.build_text_context(scene, max_objects=20)
        return f"""Current screen state:
{context}

Task: {task}

Instructions:
- Identify which object_id matches the task target
- Reply with ONLY the object_id (e.g., "button_3")
- If no matching object, reply with "NOT_FOUND"
- Do NOT guess pixel coordinates"""

    def build_verification_prompt(self, before: Scene, after: Scene,
                                   action: str) -> str:
        """Verification uchun prompt yaratish."""
        before_ctx = self.build_text_context(before, max_objects=15)
        after_ctx = self.build_text_context(after, max_objects=15)
        return f"""Before state:
{before_ctx}

Action taken: {action}

After state:
{after_ctx}

Compare before and after states. Did the action succeed?
Reply with ONE word: SUCCESS, FAILURE, or UNKNOWN"""

    def rank_by_relevance(self, scene: Scene, task: str) -> list[DetectedObject]:
        """Task'ga eng mos obyektlarni saralash."""
        scored = []
        task_lower = task.lower()
        for obj in scene.objects:
            score = 0.0
            # Matn mosligi
            if obj.associated_text:
                text_lower = obj.associated_text.lower()
                for word in task_lower.split():
                    if word in text_lower:
                        score += 2.0
            # Label mosligi
            if obj.label:
                label_lower = obj.label.lower()
                for word in task_lower.split():
                    if word in label_lower:
                        score += 1.0
            # Interaktiv obyektlarga ustunlik
            if obj.is_interactive:
                score += 0.5
            # Confidence
            score += obj.confidence * 0.3
            if score > 0:
                scored.append((score, obj))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [obj for _, obj in scored]

    def filter_irrelevant(self, scene: Scene, task: str) -> Scene:
        """Task'ga aloqasiz obyektlarni chiqarib tashlash."""
        relevant = self.rank_by_relevance(scene, task)
        # Faqat yuqori balli obyektlarni qoldiramiz
        threshold = 0.5
        filtered = [obj for obj in relevant
                    if self._relevance_score(obj, task) > threshold]
        if not filtered:
            filtered = relevant[:5]  # Kamida 5 ta qoldiramiz

        scene.objects = filtered
        scene.relations = [r for r in scene.relations
                           if r.source_id in {o.object_id for o in filtered}
                           and r.target_id in {o.object_id for o in filtered}]
        return scene

    def compact_summary(self, scene: Scene) -> str:
        """Qisqa sahna xulosasi — 1-2 jumlada."""
        interactive = scene.get_interactive_objects()
        text_count = len(scene.get_objects_with_text())
        return (f"{scene.scene_type.value}: {len(scene.objects)} objects, "
                f"{len(interactive)} interactive, {text_count} text elements")

    # --- Private ---

    def _format_object_line(self, obj: DetectedObject) -> str:
        parts = [f"{obj.object_id} ({obj.object_type.value})"]
        if obj.associated_text:
            parts.append(f'"{obj.associated_text[:40]}"')
        if not obj.is_enabled:
            parts.append("[disabled]")
        if obj.is_focused:
            parts.append("[focused]")
        parts.append(f"conf={obj.confidence:.0%}")
        return " ".join(parts)

    def _relevance_score(self, obj: DetectedObject, task: str) -> float:
        score = 0.0
        task_lower = task.lower()
        if obj.associated_text:
            for word in task_lower.split():
                if word in obj.associated_text.lower():
                    score += 2.0
        if obj.label:
            for word in task_lower.split():
                if word in obj.label.lower():
                    score += 1.0
        if obj.is_interactive:
            score += 0.5
        return score
