"""Desktop GUI testing MCP server.

Provides tools for:
- Screen capture and comparison (Pillow + OpenCV)
- Desktop GUI automation (PyAutoGUI: click, type, drag, keypress)
- Computer vision: template/image matching on screen
- OCR: read text from screen regions (Tesseract)
- Region-based element detection
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("desktop_testing")
SCREENSHOT_DIR = Path.cwd() / ".igris" / "screenshots"

# Lazy imports with fallback error messages

def _ensure_dir():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _screenshot_path(name: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    return SCREENSHOT_DIR / f"{safe}_{int(time.time())}.png"


# ---------------------------------------------------------------------------
# Screen capture
# ---------------------------------------------------------------------------

@mcp.tool()
async def capture_screen(region: str = "", name: str = "screen") -> str:
    """Capture the full screen or a region and save as PNG.

    Args:
        region: empty for full screen, or "x,y,w,h" pixel coordinates
        name: label for the saved file
    """
    _ensure_dir()
    try:
        import pyautogui
    except ImportError:
        return "ERROR: pyautogui not installed. Run: pip install pyautogui"

    try:
        if region:
            parts = [int(p.strip()) for p in region.split(",")]
            if len(parts) != 4:
                return "ERROR: region must be 'x,y,w,h' with 4 integers"
            img = pyautogui.screenshot(region=tuple(parts))
        else:
            img = pyautogui.screenshot()

        path = _screenshot_path(name)
        img.save(path)
        return f"Screenshot saved: {path} ({img.size[0]}x{img.size[1]}px)"
    except Exception as e:
        return f"ERROR: screen capture failed: {e}"


@mcp.tool()
async def screen_size() -> str:
    """Return the screen resolution and available displays."""
    try:
        import pyautogui
        w, h = pyautogui.size()
        return f"Screen: {w}x{h}"
    except ImportError:
        return "ERROR: pyautogui not installed"


# ---------------------------------------------------------------------------
# Desktop GUI automation
# ---------------------------------------------------------------------------

@mcp.tool()
async def desktop_click(x: int, y: int, button: str = "left", clicks: int = 1) -> str:
    """Click at screen coordinates.

    Args:
        x: x coordinate
        y: y coordinate
        button: left, right, middle
        clicks: number of clicks (1 or 2 for double-click)
    """
    try:
        import pyautogui
        pyautogui.click(x, y, button=button, clicks=clicks)
        return f"Clicked ({x},{y}) with {button} button"
    except ImportError:
        return "ERROR: pyautogui not installed"
    except Exception as e:
        return f"ERROR: click failed: {e}"


@mcp.tool()
async def desktop_type(text: str, interval: float = 0.05) -> str:
    """Type text at the current cursor position.

    Args:
        text: text to type
        interval: seconds between keystrokes
    """
    try:
        import pyautogui
        pyautogui.write(text, interval=interval)
        return f"Typed {len(text)} characters"
    except ImportError:
        return "ERROR: pyautogui not installed"
    except Exception as e:
        return f"ERROR: typing failed: {e}"


@mcp.tool()
async def desktop_press(key: str) -> str:
    """Press a keyboard key (e.g. enter, tab, escape, ctrl+c, alt+tab).

    Args:
        key: key name or combination (e.g. "enter", "ctrl+c", "alt+tab")
    """
    try:
        import pyautogui
        if "+" in key:
            modifiers = key.split("+")
            pyautogui.hotkey(*modifiers)
            return f"Pressed hotkey: {key}"
        else:
            pyautogui.press(key)
            return f"Pressed key: {key}"
    except ImportError:
        return "ERROR: pyautogui not installed"
    except Exception as e:
        return f"ERROR: keypress failed: {e}"


@mcp.tool()
async def desktop_drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> str:
    """Drag mouse from (x1,y1) to (x2,y2).

    Args:
        x1, y1: start coordinates
        x2, y2: end coordinates
        duration: drag duration in seconds
    """
    try:
        import pyautogui
        pyautogui.moveTo(x1, y1)
        pyautogui.drag(x2 - x1, y2 - y1, duration=duration)
        return f"Dragged from ({x1},{y1}) to ({x2},{y2})"
    except ImportError:
        return "ERROR: pyautogui not installed"
    except Exception as e:
        return f"ERROR: drag failed: {e}"


@mcp.tool()
async def desktop_scroll(clicks: int, x: int | None = None, y: int | None = None) -> str:
    """Scroll the mouse wheel.

    Args:
        clicks: positive = scroll up, negative = scroll down
        x, y: optional position to scroll at
    """
    try:
        import pyautogui
        if x is not None and y is not None:
            pyautogui.scroll(clicks, x, y)
        else:
            pyautogui.scroll(clicks)
        direction = "up" if clicks > 0 else "down"
        return f"Scrolled {direction} {abs(clicks)} clicks"
    except ImportError:
        return "ERROR: pyautogui not installed"
    except Exception as e:
        return f"ERROR: scroll failed: {e}"


@mcp.tool()
async def desktop_move(x: int, y: int, duration: float = 0.3) -> str:
    """Move mouse to coordinates.

    Args:
        x, y: target coordinates
        duration: movement duration in seconds
    """
    try:
        import pyautogui
        pyautogui.moveTo(x, y, duration=duration)
        return f"Moved mouse to ({x},{y})"
    except ImportError:
        return "ERROR: pyautogui not installed"
    except Exception as e:
        return f"ERROR: move failed: {e}"


@mcp.tool()
async def get_mouse_position() -> str:
    """Get the current mouse cursor position."""
    try:
        import pyautogui
        x, y = pyautogui.position()
        return f"Mouse position: ({x}, {y})"
    except ImportError:
        return "ERROR: pyautogui not installed"


@mcp.tool()
async def locate_on_screen(image_path: str, confidence: float = 0.8) -> str:
    """Find an image on screen and return its coordinates.

    Useful for finding buttons, icons, or UI elements by their appearance.

    Args:
        image_path: path to the reference image file
        confidence: matching threshold (0.0-1.0, higher = stricter)
    """
    try:
        import pyautogui
    except ImportError:
        return "ERROR: pyautogui not installed"

    try:
        path = Path(image_path)
        if not path.exists():
            return f"ERROR: image not found: {image_path}"
        location = pyautogui.locateOnScreen(str(path), confidence=confidence)
        if location:
            return f"Found at: left={location.left}, top={location.top}, width={location.width}, height={location.height}"
        return "Image not found on screen"
    except Exception as e:
        return f"ERROR: locate failed: {e}"


# ---------------------------------------------------------------------------
# Computer Vision (OpenCV)
# ---------------------------------------------------------------------------

@mcp.tool()
async def vision_match_template(screenshot: str, template: str, threshold: float = 0.8) -> str:
    """Find a template image within a screenshot using OpenCV template matching.

    Args:
        screenshot: path to the screenshot image
        template: path to the template image to find
        threshold: matching threshold (0.0-1.0)
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return "ERROR: opencv-python not installed. Run: pip install opencv-python"

    spath, tpath = Path(screenshot), Path(template)
    if not spath.exists():
        return f"ERROR: screenshot not found: {screenshot}"
    if not tpath.exists():
        return f"ERROR: template not found: {template}"

    try:
        img = cv2.imread(str(spath))
        tmpl = cv2.imread(str(tpath))
        if img is None or tmpl is None:
            return "ERROR: could not read image files"

        result = cv2.matchTemplate(img, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        h, w = tmpl.shape[:2]
        if max_val >= threshold:
            return (f"Template found at ({max_loc[0]},{max_loc[1]}) "
                    f"size={w}x{h} confidence={max_val:.2f}")
        return f"Template not found. Best match confidence: {max_val:.2f} (threshold: {threshold})"
    except Exception as e:
        return f"ERROR: template matching failed: {e}"


@mcp.tool()
async def vision_compare_images(image1: str, image2: str) -> str:
    """Compare two images and return their similarity score.

    Args:
        image1: path to first image
        image2: path to second image
    """
    try:
        import cv2
    except ImportError:
        return "ERROR: opencv-python not installed"

    p1, p2 = Path(image1), Path(image2)
    if not p1.exists() or not p2.exists():
        return "ERROR: one or both images not found"

    try:
        img1 = cv2.imread(str(p1))
        img2 = cv2.imread(str(p2))
        if img1 is None or img2 is None:
            return "ERROR: could not read image files"
        if img1.shape != img2.shape:
            return f"ERROR: images have different sizes: {img1.shape} vs {img2.shape}"

        diff = cv2.absdiff(img1, img2)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        mean_diff = gray_diff.mean()

        similarity = max(0, 100 - mean_diff)
        has_diff_pixels = int((gray_diff > 25).sum())

        return (f"Similarity: {similarity:.1f}% | "
                f"Different pixels: {has_diff_pixels} | "
                f"Mean difference: {mean_diff:.2f}")
    except Exception as e:
        return f"ERROR: comparison failed: {e}"


@mcp.tool()
async def vision_find_contours(image_path: str, min_area: int = 50) -> str:
    """Find visual elements (buttons, boxes) in a screenshot using contour detection.

    Args:
        image_path: path to the image
        min_area: minimum area in pixels for detected elements
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return "ERROR: opencv-python not installed"

    path = Path(image_path)
    if not path.exists():
        return f"ERROR: image not found: {image_path}"

    try:
        img = cv2.imread(str(path))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        elements = []
        for i, c in enumerate(contours):
            area = cv2.contourArea(c)
            if area >= min_area:
                x, y, w, h = cv2.boundingRect(c)
                elements.append({"index": i, "x": x, "y": y, "w": w, "h": h, "area": int(area)})

        return json.dumps(elements[:50], indent=2)
    except Exception as e:
        return f"ERROR: contour detection failed: {e}"


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

@mcp.tool()
async def ocr_read_text(image_path: str, lang: str = "eng") -> str:
    """Read text from an image using OCR (Tesseract).

    Args:
        image_path: path to the image
        lang: language code (eng, rus, uzb, etc.)
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return "ERROR: pytesseract not installed. Run: pip install pytesseract"

    path = Path(image_path)
    if not path.exists():
        return f"ERROR: image not found: {image_path}"

    try:
        img = Image.open(path)
        text = pytesseract.image_to_string(img, lang=lang)
        return text.strip() or "(no text detected)"
    except Exception as e:
        msg = str(e).lower()
        if "tesseract" in msg and "not" in msg:
            return ("ERROR: Tesseract OCR engine not found. "
                    "Install from: https://github.com/UB-Mannheim/tesseract/wiki")
        return f"ERROR: OCR failed: {e}"


@mcp.tool()
async def ocr_find_text(image_path: str, search_text: str, lang: str = "eng") -> str:
    """Search for specific text in an image using OCR.

    Args:
        image_path: path to the image
        search_text: text to search for
        lang: language code
    """
    import re
    result = await ocr_read_text(image_path, lang)
    if result.startswith("ERROR:"):
        return result

    found = search_text.lower() in result.lower()
    if found:
        # Find context around the match
        lines = result.split("\n")
        for i, line in enumerate(lines):
            if search_text.lower() in line.lower():
                ctx_start = max(0, i - 1)
                ctx_end = min(len(lines), i + 2)
                context = "\n".join(lines[ctx_start:ctx_end])
                return f"Text found!\nContext:\n{context}"
        return "Text found in image"
    return f"Text '{search_text}' not found in image"


@mcp.tool()
async def ocr_regions(image_path: str, lang: str = "eng") -> str:
    """Extract text with bounding boxes from an image.

    Returns each detected text block with its position.

    Args:
        image_path: path to the image
        lang: language code
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return "ERROR: pytesseract not installed"

    path = Path(image_path)
    if not path.exists():
        return f"ERROR: image not found: {image_path}"

    try:
        img = Image.open(path)
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
        blocks = []
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            if text and int(data["conf"][i]) > 30:
                blocks.append({
                    "text": text,
                    "x": data["left"][i],
                    "y": data["top"][i],
                    "w": data["width"][i],
                    "h": data["height"][i],
                    "confidence": int(data["conf"][i]),
                })
        return json.dumps(blocks, indent=2) if blocks else "(no text detected)"
    except Exception as e:
        msg = str(e).lower()
        if "tesseract" in msg and ("not" in msg or "found" in msg):
            return "ERROR: Tesseract OCR engine not found. Install from: https://github.com/UB-Mannheim/tesseract/wiki"
        return f"ERROR: OCR failed: {e}"


# ---------------------------------------------------------------------------
# Pixel/color inspection
# ---------------------------------------------------------------------------

@mcp.tool()
async def pixel_color(x: int, y: int) -> str:
    """Get the color of a pixel on screen at the given coordinates.

    Args:
        x, y: screen coordinates
    """
    try:
        import pyautogui
        color = pyautogui.pixel(x, y)
        hex_color = "#{:02x}{:02x}{:02x}".format(*color)
        return f"Pixel at ({x},{y}): RGB{color} ({hex_color})"
    except ImportError:
        return "ERROR: pyautogui not installed"


@mcp.tool()
async def pixel_matches_color(x: int, y: int, hex_color: str, tolerance: int = 10) -> str:
    """Check if a pixel on screen matches an expected color.

    Args:
        x, y: screen coordinates
        hex_color: expected color in hex format (e.g. "#ff0000")
        tolerance: allowed difference per channel (0-255)
    """
    try:
        import pyautogui
    except ImportError:
        return "ERROR: pyautogui not installed"

    try:
        hex_color = hex_color.lstrip("#")
        expected = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        actual = pyautogui.pixel(x, y)

        diff = sum(abs(a - e) for a, e in zip(actual, expected))
        match = diff <= tolerance * 3
        return (f"Pixel at ({x},{y}): expected=#{hex_color}, actual=RGB{actual}, "
                f"diff={diff}, match={'YES' if match else 'NO'}")
    except Exception as e:
        return f"ERROR: pixel check failed: {e}"


if __name__ == "__main__":
    mcp.run()
