"""§1 Input/Capture Layer — screenshot, window, region capture.

Platform-agnostic capture interface. Windows uchun msscreenshot/dxcam,
boshqa platformalar uchun Pillow/grab."""
from __future__ import annotations

import io
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from vision.contracts import BBox


@dataclass
class CaptureResult:
    """Capture natijasi — image + metadata."""
    image: Any  # numpy array yoki PIL Image
    width: int = 0
    height: int = 0
    timestamp: float = field(default_factory=time.time)
    capture_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source: str = "screen"  # screen, window, region, file
    window_title: str = ""
    app_name: str = ""
    # File path (agar save qilinsa)
    saved_path: str = ""

    def to_dict(self) -> dict:
        return {
            "capture_id": self.capture_id,
            "width": self.width,
            "height": self.height,
            "timestamp": self.timestamp,
            "source": self.source,
            "window_title": self.window_title,
            "app_name": self.app_name,
        }


class ScreenCapture:
    """Ekran, oyna yoki hududni suratga olish."""

    def __init__(self, save_dir: str = ""):
        self._save_dir = Path(save_dir) if save_dir else Path.cwd() / "vision_captures"
        self._save_dir.mkdir(parents=True, exist_ok=True)
        self._backend = self._init_backend()

    def _init_backend(self) -> str:
        """Mavjud backend'ni aniqlash."""
        try:
            import dxcam
            return "dxcam"
        except ImportError:
            pass
        try:
            from PIL import ImageGrab
            return "pillow"
        except ImportError:
            pass
        return "fallback"

    def capture_screen(self) -> CaptureResult:
        """To'liq ekran suratini olish."""
        if self._backend == "dxcam":
            return self._capture_dxcam()
        elif self._backend == "pillow":
            return self._capture_pillow()
        else:
            return self._capture_fallback()

    def capture_window(self, window_title: Optional[str] = None) -> CaptureResult:
        """Aniq oynani suratini olish."""
        try:
            import pygetwindow as gw
            if window_title:
                windows = gw.getWindowsWithTitle(window_title)
            else:
                windows = gw.getActiveWindow()
                windows = [windows] if windows else []

            if windows:
                win = windows[0]
                bbox = BBox(win.left, win.top, win.right, win.bottom)
                return self.capture_region(bbox)
        except ImportError:
            pass
        return self.capture_screen()

    def capture_region(self, bbox: BBox) -> CaptureResult:
        """Aniq hududni suratini olish."""
        if self._backend == "dxcam":
            return self._capture_dxcam_region(bbox)
        elif self._backend == "pillow":
            return self._capture_pillow_region(bbox)
        else:
            return self._capture_fallback()

    def capture_active_window(self) -> CaptureResult:
        """Joriy faol oynani suratini olish."""
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            if win:
                bbox = BBox(win.left, win.top, win.right, win.bottom)
                result = self.capture_region(bbox)
                result.window_title = win.title
                return result
        except ImportError:
            pass
        return self.capture_screen()

    def capture_from_file(self, file_path: str) -> CaptureResult:
        """Fayldan rasm yuklash."""
        try:
            from PIL import Image
            import numpy as np
            img = Image.open(file_path)
            arr = np.array(img)
            return CaptureResult(
                image=arr,
                width=arr.shape[1] if len(arr.shape) > 1 else 0,
                height=arr.shape[0] if len(arr.shape) > 0 else 0,
                timestamp=time.time(),
                source="file",
                saved_path=file_path,
            )
        except Exception:
            return CaptureResult(image=None, source="file")

    def save_capture(self, result: CaptureResult, name: str = "") -> str:
        """Capture'ni faylga saqlash."""
        try:
            from PIL import Image
            import numpy as np
            if result.image is None:
                return ""
            fname = name or f"capture_{result.capture_id}.png"
            path = self._save_dir / fname
            if isinstance(result.image, np.ndarray):
                Image.fromarray(result.image).save(str(path))
            else:
                result.image.save(str(path))
            result.saved_path = str(path)
            return str(path)
        except Exception:
            return ""

    # --- Backend implementations ---

    def _capture_dxcam(self) -> CaptureResult:
        try:
            import dxcam
            import numpy as np
            cam = dxcam.create(output_color="BGR")
            img = cam.grab()
            if img is None:
                return CaptureResult(image=None, source="screen")
            h, w = img.shape[:2]
            return CaptureResult(image=img, width=w, height=h, source="screen")
        except Exception:
            return CaptureResult(image=None, source="screen")

    def _capture_dxcam_region(self, bbox: BBox) -> CaptureResult:
        try:
            import dxcam
            cam = dxcam.create(output_color="BGR")
            region = (bbox.x1, bbox.y1, bbox.x2, bbox.y2)
            img = cam.grab(region=region)
            if img is None:
                return CaptureResult(image=None, source="region")
            return CaptureResult(
                image=img, width=bbox.width, height=bbox.height, source="region"
            )
        except Exception:
            return CaptureResult(image=None, source="region")

    def _capture_pillow(self) -> CaptureResult:
        try:
            from PIL import ImageGrab
            import numpy as np
            img = ImageGrab.grab()
            arr = np.array(img)
            h, w = arr.shape[:2]
            return CaptureResult(image=arr, width=w, height=h, source="screen")
        except Exception:
            return CaptureResult(image=None, source="screen")

    def _capture_pillow_region(self, bbox: BBox) -> CaptureResult:
        try:
            from PIL import ImageGrab
            import numpy as np
            img = ImageGrab.grab(bbox=(bbox.x1, bbox.y1, bbox.x2, bbox.y2))
            arr = np.array(img)
            return CaptureResult(
                image=arr, width=bbox.width, height=bbox.height, source="region"
            )
        except Exception:
            return CaptureResult(image=None, source="region")

    def _capture_fallback(self) -> CaptureResult:
        """Backend yo'q — placeholder."""
        return CaptureResult(image=None, source="screen")
