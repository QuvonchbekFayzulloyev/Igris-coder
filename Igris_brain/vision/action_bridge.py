"""§10 Action Bridge — coordinate conversion, click/type/scroll targets.

LLM faqat object_id beradi — ActionBridge pixel koordinataga aylantiradi.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from vision.contracts import BBox, DetectedObject, ObjectType, Scene, Target


@dataclass
class ActionResult:
    """Amal natijasi."""
    success: bool
    action: str
    target_id: str
    coordinates: tuple[int, int] = (0, 0)
    error: str = ""
    timestamp: float = field(default_factory=time.time)
    # Safety
    was_safe: bool = True
    safety_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "action": self.action,
            "target_id": self.target_id,
            "coordinates": list(self.coordinates),
            "error": self.error,
            "was_safe": self.was_safe,
        }


class ActionBridge:
    """Object ID → pixel coordinate → amal bajarish."""

    def __init__(self, safety_enabled: bool = True):
        self.safety_enabled = safety_enabled
        self._executor = self._init_executor()

    def _init_executor(self) -> str:
        """Mavjud executor'ni aniqlash."""
        try:
            import pyautogui
            return "pyautogui"
        except ImportError:
            pass
        return "fallback"

    def resolve_target(self, scene: Scene, object_id: str) -> Optional[Target]:
        """Object ID dan Target yaratish."""
        obj = scene.get_object_by_id(object_id)
        if obj is None:
            return None

        target = Target(
            object_id=obj.object_id,
            bbox=obj.bbox,
            center=obj.center,
            confidence=obj.confidence,
            label=obj.label,
            object_type=obj.object_type,
        )

        # Safety check
        if self.safety_enabled:
            target.is_safe, target.safety_reason = self._check_safety(obj, scene)

        return target

    def resolve_by_text(self, scene: Scene, text: str) -> Optional[Target]:
        """Matn bo'yicha target topish."""
        objects = scene.find_objects_by_text(text)
        if not objects:
            return None
        # Eng yuqori confidence
        best = max(objects, key=lambda o: o.confidence)
        return self.resolve_target(scene, best.object_id)

    def click(self, target: Target) -> ActionResult:
        """Obyektni bosish."""
        if not target.is_safe:
            return ActionResult(
                success=False, action="click",
                target_id=target.object_id,
                error=f"Safety: {target.safety_reason}",
                was_safe=False,
            )
        return self._execute_action("click", target)

    def double_click(self, target: Target) -> ActionResult:
        """Iki marta bosish."""
        return self._execute_action("double_click", target)

    def right_click(self, target: Target) -> ActionResult:
        """O'ng tugmani bosish."""
        return self._execute_action("right_click", target)

    def type_text(self, target: Target, text: str) -> ActionResult:
        """Matn kiritish."""
        # Avval bosamiz, keyin yozamiz
        click_result = self._execute_action("click", target)
        if not click_result.success:
            return click_result
        return self._execute_type(target, text)

    def scroll(self, target: Target, direction: str = "down", amount: int = 3) -> ActionResult:
        """Skrollash."""
        return self._execute_action("scroll", target, direction=direction, amount=amount)

    def drag(self, source: Target, destination: Target) -> ActionResult:
        """Obyektni ko'chirish."""
        return self._execute_drag(source, destination)

    def press_key(self, key: str) -> ActionResult:
        """Tugmani bosish."""
        try:
            import pyautogui
            pyautogui.press(key)
            return ActionResult(success=True, action="press_key", target_id=key)
        except Exception as e:
            return ActionResult(success=False, action="press_key", target_id=key, error=str(e))

    def hotkey(self, *keys: str) -> ActionResult:
        """Shortcut kombinatsiyasi."""
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return ActionResult(success=True, action="hotkey", target_id="+".join(keys))
        except Exception as e:
            return ActionResult(success=False, action="hotkey",
                               target_id="+".join(keys), error=str(e))

    # --- Private ---

    def _execute_action(self, action: str, target: Target, **kwargs) -> ActionResult:
        """Amalni bajarish."""
        try:
            import pyautogui
            x, y = target.center
            if action == "click":
                pyautogui.click(x, y)
            elif action == "double_click":
                pyautogui.doubleClick(x, y)
            elif action == "right_click":
                pyautogui.rightClick(x, y)
            elif action == "scroll":
                direction = kwargs.get("direction", "down")
                amount = kwargs.get("amount", 3)
                scroll_amount = amount if direction == "up" else -amount
                pyautogui.scroll(scroll_amount, x, y)
            return ActionResult(
                success=True, action=action,
                target_id=target.object_id, coordinates=(x, y),
            )
        except Exception as e:
            return ActionResult(
                success=False, action=action,
                target_id=target.object_id, error=str(e),
            )

    def _execute_type(self, target: Target, text: str) -> ActionResult:
        """Matn yozish."""
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=0.02)
            return ActionResult(
                success=True, action="type_text",
                target_id=target.object_id,
                coordinates=target.center,
            )
        except Exception as e:
            return ActionResult(
                success=False, action="type_text",
                target_id=target.object_id, error=str(e),
            )

    def _execute_drag(self, source: Target, dest: Target) -> ActionResult:
        """Drag and drop."""
        try:
            import pyautogui
            sx, sy = source.center
            dx, dy = dest.center
            pyautogui.moveTo(sx, sy)
            pyautogui.mouseDown()
            pyautogui.moveTo(dx, dy, duration=0.5)
            pyautogui.mouseUp()
            return ActionResult(
                success=True, action="drag",
                target_id=f"{source.object_id}->{dest.object_id}",
                coordinates=(dx, dy),
            )
        except Exception as e:
            return ActionResult(
                success=False, action="drag",
                target_id=source.object_id, error=str(e),
            )

    def _check_safety(self, obj: DetectedObject, scene: Scene) -> tuple[bool, str]:
        """Xavfsizlik tekshiruvi."""
        # 1. O'chirilgan element
        if not obj.is_enabled:
            return False, "Element is disabled"

        # 2. Juda katta obyekt (to'liq ekran)
        if obj.bbox.area > (scene.width * scene.height * 0.8):
            return False, "Object covers >80% of screen"

        # 3. Unknown turdagi katta obyekt
        if obj.object_type == ObjectType.UNKNOWN and obj.bbox.area > 50000:
            return False, "Large unknown object — may be dangerous"

        return True, ""

    def _click_pyautogui(self, x: int, y: int) -> None:
        try:
            import pyautogui
            pyautogui.click(x, y)
        except ImportError:
            pass
