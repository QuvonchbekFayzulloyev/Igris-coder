"""§6 UI/Desktop Understanding — application/window identification, UI hierarchy."""
from __future__ import annotations

import time
from typing import Any, Optional

import numpy as np

from vision.contracts import (
    BBox, DetectedObject, ObjectType, Scene, SceneType,
)


class UIAnalyzer:
    """Sahnani tahlil qilish — ilova, oyna, UI elementlarini aniqlash."""

    # Mashhur ilovalar ro'yxati
    KNOWN_APPS = {
        "chrome": SceneType.BROWSER,
        "firefox": SceneType.BROWSER,
        "edge": SceneType.BROWSER,
        "explorer": SceneType.FILE_EXPLORER,
        "file explorer": SceneType.FILE_EXPLORER,
        "code": SceneType.TEXT_EDITOR,
        "visual studio": SceneType.TEXT_EDITOR,
        "notepad": SceneType.TEXT_EDITOR,
        "settings": SceneType.SETTINGS,
        "control panel": SceneType.SETTINGS,
        "terminal": SceneType.TERMINAL,
        "cmd": SceneType.TERMINAL,
        "powershell": SceneType.TERMINAL,
        "wt": SceneType.TERMINAL,
        "word": SceneType.APPLICATION,
        "excel": SceneType.APPLICATION,
        "powerpoint": SceneType.APPLICATION,
    }

    def analyze(self, scene: Scene, image: Any = None) -> Scene:
        """Sahnani to'liq tahlil qilish."""
        # 1. Ilovani aniqlash
        scene.scene_type = self.identify_application(scene)

        # 2. UI elementlarini belgilash
        if image is not None:
            scene.objects = self._annotate_ui_elements(scene.objects, image)

        # 3. Window info
        self._extract_window_info(scene)

        return scene

    def identify_application(self, scene: Scene) -> SceneType:
        """Oyna sarlavhasidan ilovani aniqlash."""
        title = scene.window_title.lower()
        for keyword, scene_type in self.KNOWN_APPS.items():
            if keyword in title:
                return scene_type
        # Window title bo'yicha aniqlab bo'lmasa
        return scene.scene_type

    def identify_ui_elements(self, objects: list[DetectedObject]) -> list[DetectedObject]:
        """Obyektlarga UI element turlarini tayinlash."""
        for obj in objects:
            if obj.object_type == ObjectType.UNKNOWN:
                obj.object_type = self._guess_type_from_properties(obj)
            obj.is_interactive = self._is_interactive(obj)
        return objects

    def detect_focused_element(self, objects: list[DetectedObject]) -> Optional[DetectedObject]:
        """Fokuslangan elementni topish."""
        for obj in objects:
            if obj.is_focused:
                return obj
        return None

    def detect_disabled_elements(self, objects: list[DetectedObject]) -> list[DetectedObject]:
        """O'chirilgan elementlarni topish."""
        return [o for o in objects if not o.is_enabled]

    def detect_error_messages(self, scene: Scene) -> list[DetectedObject]:
        """Xabar xatolarini topish."""
        errors = []
        error_keywords = ["error", "xato", "fail", "warning", "diqqat", "muvaffaqiyatsiz"]
        for obj in scene.objects:
            text = obj.associated_text.lower()
            if any(kw in text for kw in error_keywords):
                errors.append(obj)
        return errors

    def detect_modals(self, objects: list[DetectedObject]) -> list[DetectedObject]:
        """Modal dialoglarni topish."""
        return [o for o in objects if o.object_type == ObjectType.DIALOG]

    def get_ui_hierarchy(self, objects: list[DetectedObject]) -> dict:
        """UI elementlarining ierarxiyasini yaratish."""
        hierarchy = {"windows": [], "elements": []}
        for obj in objects:
            if obj.object_type == ObjectType.WINDOW:
                hierarchy["windows"].append(obj.to_dict())
            else:
                hierarchy["elements"].append(obj.to_dict())
        return hierarchy

    def classify_scene(self, scene: Scene) -> str:
        """Sahna turini aniqlash — qaysi dastur ishlatilmoqda."""
        if scene.scene_type == SceneType.BROWSER:
            return "browser"
        if scene.scene_type == SceneType.FILE_EXPLORER:
            return "file_manager"
        if scene.scene_type == SceneType.TEXT_EDITOR:
            return "code_editor"
        if scene.scene_type == SceneType.TERMINAL:
            return "terminal"
        if scene.scene_type == SceneType.SETTINGS:
            return "system_settings"
        return "application"

    # --- Private helpers ---

    def _annotate_ui_elements(self, objects: list[DetectedObject],
                               image: Any) -> list[DetectedObject]:
        """Obyektlarni qo'shimcha ma'lumotlar bilan to'ldirish."""
        try:
            import cv2
            if not isinstance(image, np.ndarray):
                return objects

            for obj in objects:
                if obj.bbox.area == 0:
                    continue
                roi = image[obj.bbox.y1:obj.bbox.y2, obj.bbox.x1:obj.bbox.x2]
                if roi.size == 0:
                    continue

                # Matn mavjudligini tekshirish
                if len(roi.shape) == 3:
                    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                else:
                    gray = roi

                # Edge density — matn borligini ko'rsatadi
                edges = cv2.Canny(gray, 50, 150)
                edge_ratio = np.count_nonzero(edges) / edges.size if edges.size > 0 else 0

                if edge_ratio > 0.05:
                    obj.properties["has_text"] = True
                    obj.is_interactive = True

                # Rang analizi — knopka rangini aniqlash
                if len(roi.shape) == 3:
                    mean_color = roi.mean(axis=(0, 1))
                    if mean_color[2] > 150 and mean_color[1] < 100:  # Qizil
                        obj.properties["color_hint"] = "red"
                    elif mean_color[1] > 150:  # Yashil
                        obj.properties["color_hint"] = "green"
                    elif mean_color[0] > 150:  # Ko'k
                        obj.properties["color_hint"] = "blue"

        except ImportError:
            pass
        return objects

    def _extract_window_info(self, scene: Scene) -> None:
        """Oyna ma'lumotlarini ajratib olish."""
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            if win:
                scene.window_title = win.title or ""
                scene.app_name = win.title.split(" - ")[-1] if " - " in win.title else win.title
        except ImportError:
            pass

    def _guess_type_from_properties(self, obj: DetectedObject) -> ObjectType:
        """Xususiyatlar bo'yicha turini aniqlash."""
        props = obj.properties
        if props.get("has_text"):
            if obj.bbox.height < 50:
                return ObjectType.BUTTON
            return ObjectType.INPUT
        if obj.bbox.area < 1000:
            return ObjectType.ICON
        return ObjectType.UNKNOWN

    def _is_interactive(self, obj: DetectedObject) -> bool:
        """Element interaktiv ekanligini aniqlash."""
        interactive = {
            ObjectType.BUTTON, ObjectType.INPUT, ObjectType.TEXT_FIELD,
            ObjectType.CHECKBOX, ObjectType.MENU, ObjectType.MENU_ITEM,
            ObjectType.LINK, ObjectType.DROPDOWN, ObjectType.TAB,
        }
        return obj.object_type in interactive or obj.properties.get("has_text", False)
