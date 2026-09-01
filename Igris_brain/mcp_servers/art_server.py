"""
IGRIS BRAIN — Demo MCP Server: art
==================================
Model Context Protocol server (stdio) that exposes image-generation tools.
Run by the McpBridge as a subprocess. This is a *demo* MCP server — it proves
the MCP tool path end-to-end using only local Pillow drawing (no external API).

Tools:
    draw_object_png(subject, output)  -> draw a stylized picture of a simple
                                         object (apple, house, tree, cat, star,
                                         heart) to a PNG file.
"""

from __future__ import annotations

import os
import re
import sys

from mcp.server.fastmcp import FastMCP

# Skript rejimida ishga tushganda (python mcp_servers/art_server.py) Igris_brain
# papkasi sys.path'da bo'lmaydi — qo'shamiz (art_svg mutlaq import uchun).
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
_BRAIN_DIR = os.path.dirname(_SERVER_DIR)
if _BRAIN_DIR not in sys.path:
    sys.path.insert(0, _BRAIN_DIR)

mcp = FastMCP("art")


# ---------------------------------------------------------------------- #
# Color support — model istalgan rangda chiza oladi ("blue apple" kabi)
# ---------------------------------------------------------------------- #

COLOR_MAP = {
    "red": (200, 30, 40), "qizil": (200, 30, 40),
    "green": (40, 160, 60), "yashil": (40, 160, 60),
    "blue": (40, 100, 220), "kok": (40, 100, 220), "ko'k": (40, 100, 220),
    "yellow": (240, 200, 30), "sariq": (240, 200, 30),
    "orange": (240, 130, 30), "to'q sariq": (240, 130, 30),
    "purple": (140, 60, 200), "binafsha": (140, 60, 200),
    "pink": (240, 120, 150), "pushti": (240, 120, 150),
    "cyan": (60, 190, 200), "havorang": (60, 190, 200),
    "brown": (120, 80, 40), "jigarrang": (120, 80, 40),
    "black": (40, 40, 40), "qora": (40, 40, 40),
    "white": (245, 245, 245), "oq": (245, 245, 245),
    "gold": (240, 200, 30), "oltin": (240, 200, 30),
    "silver": (190, 195, 205), "gray": (130, 130, 130),
}

# Har bir shakl uchun standart rang (color berilmaganda)
DEFAULT_COLOR = {
    "apple": (200, 30, 40), "olma": (200, 30, 40),
    "house": (210, 180, 140), "uy": (210, 180, 140),
    "tree": (40, 150, 60), "daraxt": (40, 150, 60),
    "cat": (230, 190, 130), "mushuk": (230, 190, 130),
    "star": (240, 200, 30), "yulduz": (240, 200, 30),
    "heart": (220, 40, 70), "yurak": (220, 40, 70),
}


def _mix(c1, c2, t):
    """c1 -> c2 orasida aralashtirish (t=0 -> c1, t=1 -> c2)."""
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _darken(c, t=0.35):
    return _mix(c, (0, 0, 0), t)


def _lighten(c, t=0.5):
    return _mix(c, (255, 255, 255), t)


# ---------------------------------------------------------------------- #
# Shape library — stylized drawings of simple objects
# ---------------------------------------------------------------------- #

def _draw_apple(d, W, H, color=(200, 30, 40)):
    outline = _darken(color)
    # body
    d.ellipse([(0.21 * W, 0.19 * H), (0.79 * W, 0.77 * H)], fill=color, outline=outline, width=4)
    d.ellipse([(0.38 * W, 0.17 * H), (0.62 * W, 0.34 * H)], fill=color)
    # stem
    d.rectangle([(0.48 * W, 0.07 * H), (0.52 * W, 0.22 * H)], fill=(120, 80, 30))
    # leaf
    d.polygon([(0.50 * W, 0.11 * H), (0.70 * W, 0.07 * H), (0.59 * W, 0.25 * H)], fill=(40, 160, 60))
    # highlight
    d.ellipse([(0.29 * W, 0.29 * H), (0.41 * W, 0.43 * H)], fill=_lighten(color))


def _draw_house(d, W, H, color=(210, 180, 140)):
    d.rectangle([(0.25 * W, 0.45 * H), (0.75 * W, 0.85 * H)], fill=color, outline=_darken(color), width=4)
    d.polygon([(0.20 * W, 0.45 * H), (0.50 * W, 0.18 * H), (0.80 * W, 0.45 * H)], fill=(180, 40, 40), outline=(100, 20, 20), width=3)
    d.rectangle([(0.42 * W, 0.58 * H), (0.58 * W, 0.85 * H)], fill=(120, 70, 30), outline=(70, 40, 15), width=3)
    d.rectangle([(0.30 * W, 0.55 * H), (0.38 * W, 0.68 * H)], fill=(140, 190, 230), outline=(80, 110, 140), width=2)
    d.rectangle([(0.62 * W, 0.55 * H), (0.70 * W, 0.68 * H)], fill=(140, 190, 230), outline=(80, 110, 140), width=2)


def _draw_tree(d, W, H, color=(40, 150, 60)):
    d.rectangle([(0.46 * W, 0.55 * H), (0.54 * W, 0.9 * H)], fill=(120, 80, 40))
    d.ellipse([(0.25 * W, 0.2 * H), (0.75 * W, 0.65 * H)], fill=color, outline=_darken(color), width=3)
    d.ellipse([(0.42 * W, 0.1 * H), (0.78 * W, 0.45 * H)], fill=_lighten(color, 0.25))


def _draw_cat(d, W, H, color=(230, 190, 130)):
    d.ellipse([(0.28 * W, 0.3 * H), (0.72 * W, 0.8 * H)], fill=color, outline=_darken(color), width=4)
    d.polygon([(0.34 * W, 0.32 * H), (0.38 * W, 0.12 * H), (0.46 * W, 0.28 * H)], fill=color)
    d.polygon([(0.66 * W, 0.32 * H), (0.62 * W, 0.12 * H), (0.54 * W, 0.28 * H)], fill=color)
    d.ellipse([(0.40 * W, 0.48 * H), (0.48 * W, 0.58 * H)], fill=(40, 40, 40))
    d.ellipse([(0.52 * W, 0.48 * H), (0.60 * W, 0.58 * H)], fill=(40, 40, 40))
    d.polygon([(0.44 * W, 0.68 * H), (0.50 * W, 0.62 * H), (0.56 * W, 0.68 * H), (0.50 * W, 0.75 * H)], fill=(240, 120, 150))


def _draw_star(d, W, H, color=(240, 200, 30)):
    import math
    cx, cy, R = 0.5 * W, 0.5 * H, 0.33 * W
    pts = []
    for i in range(10):
        r = R if i % 2 == 0 else 0.45 * R
        ang = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    d.polygon(pts, fill=color, outline=_darken(color), width=3)


def _draw_heart(d, W, H, color=(220, 40, 70)):
    import math
    d.ellipse([(0.24 * W, 0.2 * H), (0.5 * W, 0.55 * H)], fill=color)
    d.ellipse([(0.5 * W, 0.2 * H), (0.76 * W, 0.55 * H)], fill=color)
    d.polygon([(0.24 * W, 0.46 * H), (0.76 * W, 0.46 * H), (0.5 * W, 0.86 * H)], fill=color)


def _draw_sun(d, W, H, color=(240, 200, 30)):
    import math
    cx, cy = 0.5 * W, 0.5 * H
    R1, R2 = 0.30 * W, 0.24 * W
    # nurlar
    for i in range(12):
        ang = i * 0.5236
        x1, y1 = cx + R1 * math.cos(ang), cy + R1 * math.sin(ang)
        x2, y2 = cx + R2 * math.cos(ang), cy + R2 * math.sin(ang)
        d.line([(x1, y1), (x2, y2)], fill=color, width=int(0.04 * W))
    d.ellipse([(cx - 0.19 * W, cy - 0.19 * W), (cx + 0.19 * W, cy + 0.19 * W)], fill=color, outline=_darken(color), width=3)
    d.ellipse([(cx - 0.08 * W, cy - 0.08 * W), (cx + 0.08 * W, cy + 0.08 * W)], fill=_lighten(color, 0.5))


def _draw_moon(d, W, H, color=(240, 200, 30)):
    cx, cy = 0.48 * W, 0.5 * H
    R = 0.25 * W
    d.ellipse([(cx - R, cy - R), (cx + R, cy + R)], fill=color, outline=_darken(color), width=4)
    # yarim oy kesmasi
    d.ellipse([(cx + 0.11 * W, cy - 0.20 * W), (cx + 0.38 * W, cy + 0.20 * W)], fill="white")
    d.ellipse([(cx - 0.12 * W, cy - 0.08 * W), (cx - 0.04 * W, cy + 0.0 * W)], fill=_lighten(color, 0.4))
    d.ellipse([(cx - 0.05 * W, cy + 0.09 * W), (cx + 0.01 * W, cy + 0.15 * W)], fill=_lighten(color, 0.3))


def _draw_bird(d, W, H, color=(230, 190, 130)):
    outline = _darken(color)
    d.ellipse([(0.30 * W, 0.38 * H), (0.72 * W, 0.68 * H)], fill=color, outline=outline, width=4)
    d.ellipse([(0.58 * W, 0.32 * H), (0.74 * W, 0.48 * H)], fill=color, outline=outline, width=3)
    d.polygon([(0.72 * W, 0.34 * H), (0.84 * W, 0.30 * H), (0.72 * W, 0.40 * H)], fill=(245, 166, 35))
    d.ellipse([(0.65 * W, 0.36 * H), (0.68 * W, 0.39 * H)], fill=(30, 30, 30))
    d.arc([(0.30 * W, 0.40 * H), (0.52 * W, 0.60 * H)], 180, 360, fill=color, width=int(0.05 * W))
    d.line([(0.44 * W, 0.66 * H), (0.40 * W, 0.78 * H)], fill=outline, width=4)
    d.line([(0.54 * W, 0.66 * H), (0.50 * W, 0.78 * H)], fill=outline, width=4)


def _draw_fish(d, W, H, color=(60, 190, 200)):
    outline = _darken(color)
    d.polygon([(0.16 * W, 0.5 * H), (0.28 * W, 0.22 * H), (0.70 * W, 0.5 * H), (0.28 * W, 0.78 * H)], fill=color, outline=outline, width=4)
    d.polygon([(0.64 * W, 0.5 * H), (0.84 * W, 0.38 * H), (0.84 * W, 0.62 * H)], fill=color, outline=outline, width=3)
    d.ellipse([(0.58 * W, 0.44 * H), (0.63 * W, 0.49 * H)], fill=(30, 30, 30))
    d.arc([(0.24 * W, 0.42 * H), (0.44 * W, 0.58 * H)], 200, 340, fill=_lighten(color, 0.5), width=int(0.03 * W))


def _draw_butterfly(d, W, H, color=(140, 60, 200)):
    outline = _darken(color)
    import math
    for ang, cx, cy, rx, ry in [(-0.35, 0.38, 0.38, 0.14, 0.19), (0.35, 0.62, 0.38, 0.14, 0.19),
                                (0.42, 0.42, 0.68, 0.10, 0.13), (-0.42, 0.58, 0.68, 0.10, 0.13)]:
        d.ellipse([(cx - rx, cy - ry), (cx + rx, cy + ry)], fill=color, outline=outline, width=3)
    d.rectangle([(0.49 * W, 0.28 * H), (0.51 * W, 0.72 * H)], fill=(90, 70, 48))
    d.ellipse([(0.485 * W, 0.24 * H), (0.515 * W, 0.31 * H)], fill=(30, 30, 30))


def _draw_mushroom(d, W, H, color=(200, 60, 60)):
    outline = _darken(color)
    d.polygon([(0.18 * W, 0.52 * H), (0.82 * W, 0.52 * H), (0.5 * W, 0.18 * H)], fill=color, outline=outline, width=4)
    d.rounded_rectangle([(0.42 * W, 0.50 * H), (0.58 * W, 0.88 * H)], radius=int(0.03 * W), fill=(232, 220, 200), outline=(184, 168, 144), width=3)
    d.ellipse([(0.32 * W, 0.44 * H), (0.40 * W, 0.52 * H)], fill="white")
    d.ellipse([(0.46 * W, 0.38 * H), (0.55 * W, 0.47 * H)], fill="white")
    d.ellipse([(0.62 * W, 0.44 * H), (0.69 * W, 0.51 * H)], fill="white")


def _draw_ball(d, W, H, color=(240, 130, 30)):
    outline = _darken(color)
    cx, cy = 0.5 * W, 0.5 * H
    R = 0.30 * W
    d.ellipse([(cx - R, cy - R), (cx + R, cy + R)], fill=color, outline=outline, width=5)
    d.arc([(cx - R, cy - R), (cx + R, cy + R)], 40, 140, fill=_lighten(color, 0.4), width=int(0.05 * W))
    d.arc([(cx - R * 0.7, cy - R), (cx + R * 0.7, cy + R)], 200, 320, fill=outline, width=4)
    d.ellipse([(cx - 0.14 * W, cy - 0.10 * W), (cx - 0.04 * W, cy + 0.02 * W)], fill=_lighten(color, 0.6))


SHAPES = {
    "apple": _draw_apple,
    "olma": _draw_apple,
    "house": _draw_house,
    "uy": _draw_house,
    "tree": _draw_tree,
    "daraxt": _draw_tree,
    "cat": _draw_cat,
    "mushuk": _draw_cat,
    "star": _draw_star,
    "yulduz": _draw_star,
    "heart": _draw_heart,
    "yurak": _draw_heart,
    "sun": _draw_sun,
    "quyosh": _draw_sun,
    "moon": _draw_moon,
    "oy": _draw_moon,
    "bird": _draw_bird,
    "qush": _draw_bird,
    "fish": _draw_fish,
    "baliq": _draw_fish,
    "butterfly": _draw_butterfly,
    "kapalak": _draw_butterfly,
    "mushroom": _draw_mushroom,
    "qo'ziqorin": _draw_mushroom,
    "ball": _draw_ball,
    "to'p": _draw_ball,
}


@mcp.tool()
def draw_object_png(subject: str, output: str = "art.png", color: str = "red") -> str:
    """Draw a stylized picture of a simple object and save it as a PNG file.

    Args:
        subject: object name - apple, house, tree, cat, star, heart, sun,
                 moon, bird, fish, butterfly, mushroom, ball
                 (also accepts Uzbek: olma, uy, daraxt, mushuk, yulduz, yurak,
                 quyosh, oy, qush, baliq, kapalak, qo'ziqorin, to'p)
                 (birlashgan ibora ham ishlaydi: "red apple", "qizil olma")
        output: output PNG filename (relative path, e.g. "apple.png")
        color: body color - red, green, blue, yellow, orange, purple, pink,
               cyan, brown, black, white, gold (also Uzbek: qizil=red,
               kok/ko'k=BLUE, yashil=green, sariq=yellow, binafsha=purple,
               pushti=pink, qora=black, oq=white). Default: red.

    Returns:
        the absolute path of the saved file, or an error message.
    """
    from PIL import Image, ImageDraw

    # Iboradan ob'ekt + rangni ajratib olamiz ("red apple" -> apple + red).
    # SHAPES faqat Pillow'da chiziladigan ob'ektlarni biladi — art_svg'ning
    # SCENE_OBJECTS ro'yxati kengroq, lekin bu yerda faqat SHAPES mos keladi.
    subj = str(subject).strip().lower()
    fn = SHAPES.get(subj)
    if fn is None:
        # ibora ichidan ob'ekt so'zini qidirish (art_svg parser'iga mos)
        import re as _re
        words = [w.strip().replace("'", "") for w in _re.split(r"[\s_,;\-]+", subj) if w.strip()]
        for w in words:
            if w in SHAPES:
                fn = SHAPES[w]
                subj = w
                break
    if fn is None:
        return f"NOT_SUPPORTED: unknown subject '{subject}'. Known: {', '.join(sorted(SHAPES))}. (SVG format uchun draw_scene_svg'ni sinang: u kengroq ro'yxatga ega.)"

    # Rang ham ibora ichida bo'lishi mumkin ("qizil olma")
    body = COLOR_MAP.get(str(color).strip().lower().replace("'", ""))
    if body is None:
        for w in [w.strip().replace("'", "") for w in subj.split()]:
            if w in COLOR_MAP:
                body = COLOR_MAP[w]
                break
    if body is None:
        body = DEFAULT_COLOR.get(subj) or COLOR_MAP["red"]

    # SMART DEFAULT: model `output` bermagan bo'lsa ("art.png" default qoladi) —
    # subject'dan aniq nom yaratamiz. Aks holda fayl workspace'ga emas, server
    # cwd'siga yozilib, frontend topa olmay qoladi (image kartasi ko'rinmaydi).
    import re as _re
    _out = str(output or "").strip()
    if not _out or os.path.basename(_out).lower() in ("art.png", "output.png"):
        _slug = _re.sub(r"[^a-z0-9]+", "_", subj).strip("_") or "art"
        output = _slug + ".png"

    # SMART DEFAULT: model `output` bermagan bo'lsa ("art.png" default qoladi) —
    # subject'dan aniq nom yaratamiz. Aks holda fayl workspace'ga emas, server
    # cwd'siga yozilib, frontend topa olmay qoladi (image kartasi ko'rinmaydi).
    import re as _re
    _out = str(output or "").strip()
    if not _out or os.path.basename(_out).lower() in ("art.png", "output.png"):
        _slug = _re.sub(r"[^a-z0-9]+", "_", subj).strip("_") or "art"
        output = _slug + ".png"

    # Supersample (2x) — chiziqlar silliqroq chiqadi (anti-aliasing), tez.
    W, H = 512, 512
    SS = 2
    img = Image.new("RGB", (W * SS, H * SS), "white")
    d = ImageDraw.Draw(img)
    fn(d, W * SS, H * SS, body)
    img = img.resize((W, H), Image.LANCZOS)

    out = os.path.abspath(output)
    os.makedirs(os.path.dirname(out), exist_ok=True) if os.path.dirname(out) else None
    img.save(out)
    return f"image saved to {out}"


# Canvas o'lchamlari — size argument'i uchun presetlar (viewBox asosida).
# DIQQAT: igris_agent._draw_size_from_request so'zlari bilan sinxron saqlanishi
# kerak (bir xil o'lcham so'zlari ikkala joyda ham).
SIZE_PRESETS = {
    "icon": (256, 256),
    "avatar": (512, 512),
    "standard": (512, 512),
    "card": (800, 450),
    "poster": (1080, 1920),
    "banner": (1920, 480),
}

SIZE_ALIASES = {
    "ikon": "icon", "ikonka": "icon", "ikonkacha": "icon", "belgi": "icon",
    "profil": "avatar", "profil rasmi": "avatar",
    "karta": "card", "kartochka": "card",
    "afisha": "poster", "plakat": "poster", "reklama": "poster",
    "standart": "standard", "oddiy": "standard",
}


def _svg_size_dimensions(size: str) -> tuple[int, int]:
    """size argument'ini (W, H) o'lchamga aylantiradi (default 512x512).

    Preset: icon / avatar / standard / card / poster / banner (aliaslar bilan).
    Maxsus: \"800x600\" kabi WxH — ikkita butun son (ajratgich: x, *, ×).
    Noto'g'ri qiymatda standard (512x512) qaytadi.
    """
    raw = str(size or "").strip().lower().replace("×", "x").replace("*", "x")
    if raw in SIZE_ALIASES:
        raw = SIZE_ALIASES[raw]
    if raw in SIZE_PRESETS:
        return SIZE_PRESETS[raw]
    m = re.match(r"^(\d{2,4})\s*x\s*(\d{2,4})$", raw)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if 32 <= w <= 4096 and 32 <= h <= 4096:
            return w, h
    return SIZE_PRESETS["standard"]


@mcp.tool()
def draw_custom_svg(svg: str, output: str = "drawing.svg", style: str = "cartoon",
                    size: str = "standard") -> str:
    """Save a CUSTOM SVG drawing that YOU (the model) generate yourself.

    This is the REAL drawing path: there is NO fixed subject list. You design
    the SVG markup for ANYTHING the user asks (a duck, a robot, a city, a
    fantasy creature, a logo...) and this tool writes it to a file that the
    chat shows as a picture.

    Base quality rules (all styles):
      - viewBox="0 0 512 512", soft background rect first
      - layered shapes: outline -> body -> details -> highlights -> shadows
      - pick a coherent palette; put every visual part as its own element so
        the UI can reveal the drawing piece by piece

    STYLE guidance — generate the SVG in the requested style:
      - style="cartoon"  (default): bold dark outlines (stroke-width 4-6),
        saturated happy colors, simple rounded shapes, exaggerated features,
        big eyes, playful — like a children's book illustration.
      - style="child": like a CHILD drew it — thick wobbly black outlines,
        bright flat colors, simple naive shapes, imperfect lines, playful.
      - style="bw": black & white monochrome — grayscale, strong black
        outlines, no color (white/black/gray only).
      - style="fantasy": magical — vivid saturated palette, glowing accents,
        soft golden glow, ornate/imaginary shapes, star/magic details.
      - style="anime": anime/manga — bold clean ink outlines, vibrant colors,
        shiny highlights, large expressive eyes.
      - style="realistic": soft linear/radial gradients, subtle shading and
        soft drop shadows (feDropShadow), natural muted palette, thin or no
        outlines, smooth bezier curves, fine details — believable proportions.
      - style="flat": NO gradients, NO shadows, solid fills only, geometric
        minimal shapes, crisp edges, modern design-system look, 2-3 colors.

    SIZE guidance — canvas & composition per use (viewBox asosida):
      - size="icon"    (256x256): tiny — simple bold shapes, thick outlines,
        NO fine detail; must read at 32-64px (favicon, button icon).
      - size="avatar"  (512x512): square — subject centered, fills ~70%,
        head/face focus, clean background (profile picture).
      - size="card"    (800x450): 16:9 landscape — subject left/center with
        breathing room, balanced wide composition.
      - size="standard" (512x512, default): classic square canvas.
      - size="poster"  (1080x1920): 9:16 portrait — subject fills ~80% of the
        height, vertical flow, leave a title band at top/bottom.
      - size="banner"  (1920x480): ultra-wide — subject left/center,
        horizontal flow, sky/ground/pattern fills the rest.
      - size="800x600" custom WxH also works (32-4096 each side).
      ALWAYS set viewBox="0 0 <W> <H>" to match the requested size and design
      the composition for that exact aspect ratio. The tool rescales old
      512x512-style markup to fit the new canvas, but a native composition is
      always better.

    Args:
        svg: the complete SVG markup ("<svg ...>...</svg>"). Required.
        output: output SVG filename (relative path, e.g. "duck.svg").
        style: cartoon | child | bw | fantasy | anime | realistic | flat
               (also Uzbek: multfilm, bola chizgandek, oq qora, fantastik,
               anime, realistik, tekis/minimal). Default: cartoon.
        size: icon | avatar | standard | card | poster | banner, or custom
              "WxH" (e.g. "800x600"). Uzbek: ikonka/ikon=icon, profil
              rasmi=avatar, karta=card, afisha/plakat=poster. Default: standard.

    Returns:
        the absolute path of the saved file, or an error message.
    """
    import re as _re

    svg_text = str(svg or "").strip()
    low = svg_text.lower()
    if "<svg" not in low or "</svg>" not in low:
        return (
            "error: the 'svg' argument must be a complete <svg>...</svg> document. "
            "Generate the full SVG markup and pass it as the svg argument — do not "
            "return it as chat text."
        )
    # </svg> dan keyingi qo'shimcha matnni olib tashlaymiz — keyingi wrap
    # jarayoni buzilmasligi uchun (model ba'zan izoh qo'shib yuboradi).
    svg_text = _re.sub(r"</svg>[\s\S]*$", "</svg>", svg_text, count=1, flags=_re.IGNORECASE)

    # style normalizatsiyasi: aliaslar + noma'lum qiymatda cartoon (default).
    # DIQQAT: bu aliaslar igris_agent._draw_style_from_request so'zlari bilan
    # sinxron saqlanishi kerak (bir xil uslub so'zlari ikkala joyda ham).
    style = str(style or "").strip().lower()
    style_aliases = {
        "multfilm": "cartoon", "cizgi": "cartoon", "kulgili": "cartoon",
        "realistik": "realistic", "fotorealistik": "realistic", "real": "realistic",
        "tekis": "flat", "minimal": "flat", "minimalist": "flat", "modern": "flat",
    }
    style = style_aliases.get(style, style)  # aniq kalit — substring emas
    if style not in ("cartoon", "realistic", "flat"):
        style = "cartoon"

    # output nomini tozalaymiz: faqat .svg, workspace'ga xavfsiz nom
    _out = str(output or "").strip()
    if not _out.lower().endswith(".svg"):
        base = os.path.splitext(os.path.basename(_out))[0] or "drawing"
        _out = _re.sub(r"[^a-zA-Z0-9_.\-]+", "_", base).strip("_") or "drawing"
        _out += ".svg"

    # ---- SIZE: canvas o'lchamini belgilaymiz (viewBox asosida) ----
    W, H = _svg_size_dimensions(size)

    # Modelning o'z viewBox'ini o'qiymiz — agar model boshqa o'lchamda
    # chizgan bo'lsa (masalan 512x512 shablon), kontentni yangi canvasga
    # MOSLASHTIRIB qo'yamiz: aspekt saqlanadi, markazda turadi, hech narsa
    # kesilmaydi. Model to'g'ridan-to'g'ri so'ralgan o'lchamda chizgan bo'lsa
    # (scale=1) transform qo'shilmaydi — fayl sof qoladi.
    vb_w = vb_h = None
    scale, tx, ty = 1.0, 0.0, 0.0
    _vb = _re.search(
        r"viewBox=[\"']\s*([\d.+-]+)\s+([\d.+-]+)\s+([\d.+-]+)\s+([\d.+-]+)\s*[\"']",
        svg_text, _re.IGNORECASE)
    if _vb:
        try:
            vb_w, vb_h = float(_vb.group(3)), float(_vb.group(4))
            if vb_w > 0 and vb_h > 0 and (abs(vb_w - W) > 1 or abs(vb_h - H) > 1):
                scale = min(W / vb_w, H / vb_h)
                tx = (W - vb_w * scale) / 2.0 - float(_vb.group(1)) * scale
                ty = (H - vb_h * scale) / 2.0 - float(_vb.group(2)) * scale
        except (ValueError, IndexError, TypeError):
            pass

    # <svg> tegini yangi o'lchamga o'rnatamiz (width/height/viewBox) — model
    # qaysi o'lchamda chizgan bo'lmasin, fayl so'ralgan o'lchamda bo'ladi.
    _tag_m = _re.search(r"<svg\b[^>]*>", svg_text, _re.IGNORECASE)
    if _tag_m:
        _tag = _tag_m.group(0)
        _new_tag = _re.sub(r"\s*(?:width|height|viewBox)=[\"'][^\"']*[\"']", "", _tag)
        _new_tag = _re.sub(r"\s*/?>$", "", _new_tag)  # closing > ni olib tashla (self-closing ham)
        _new_tag += f' width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
        svg_text = svg_text.replace(_tag, _new_tag, 1)

    # Uslub va o'lchamni faylga izoh sifatida yozamiz — UI/foydalanuvchi qaysi
    # uslub/o'lcham qo'llanganini ko'ra oladi (faylning o'zi o'zgarmaydi).
    # Eslatma: font-size: kabi atributlar bilan xato mos kelmasligi uchun
    # faqat IZOH formatini tekshiramiz (<!-- style: / <!-- size:).
    _head = svg_text[:220].lower()
    _notes = []
    if not _re.search(r"<!--\s*style:", _head):
        _notes.append("<!-- style: " + style + " -->")
    if not _re.search(r"<!--\s*size:", _head):
        _notes.append("<!-- size: " + str(W) + "x" + str(H) + " -->")

    # Kontentni yangi o'lchamga moslashtiramiz (faqat o'lcham farq qilsa).
    if scale != 1.0 and vb_w and vb_h:
        # 512x512 shablon poster/bannerda markazda kichik kvadrat bo'lib qolmasligi
        # uchun: modelning to'liq-o'lchamli FON rect'i bo'lsa, transform TASHQARISIDA
        # butun canvasni qoplaydigan fon qo'shamiz (bir xil rang — choksiz).
        _bg = _re.search(r"<rect\b[^>]*>", svg_text, _re.IGNORECASE)
        if _bg:
            _attrs = _bg.group(0)
            _fill = "#f4f1ea"
            _f = _re.search(r"fill=[\"']([^\"']+)[\"']", _attrs)
            if _f:
                _fill = _f.group(1)
            _rw = _re.search(r"width=[\"']([\d.]+)[\"']", _attrs)
            _rh = _re.search(r"height=[\"']([\d.]+)[\"']", _attrs)
            full_bleed = False
            try:
                if _rw and _rh and float(_rw.group(1)) >= 0.9 * vb_w and float(_rh.group(1)) >= 0.9 * vb_h:
                    full_bleed = True
            except ValueError:
                pass
            if full_bleed:
                # Single-quote atributlar: re.sub replacement'da \" literal
                # backslash bo'lib qolardi — SVG single-quote'ni ham qabul qiladi.
                svg_text = _re.sub(
                    r"(<svg\b[^>]*>)",
                    r"\1\n<rect width='" + str(W) + "' height='" + str(H)
                    + "' fill='" + _fill + "'/>",
                    svg_text, count=1)

    if _notes:
        svg_text = _re.sub(r"(<svg\b[^>]*>)", r"\1\n" + "\n".join(_notes),
                           svg_text, count=1)

    # Kontentni yangi o'lchamga moslashtiramiz (faqat o'lcham farq qilsa).
    if scale != 1.0:
        _inner = _re.sub(r"^<svg\b[^>]*>", "", svg_text, count=1)
        _inner = _re.sub(r"</svg>\s*$", "", _inner)
        svg_text = (
            _re.match(r"<svg\b[^>]*>", svg_text).group(0)
            + f'\n<g transform="translate({tx:.2f} {ty:.2f}) scale({scale:.5f})">'
            + _inner
            + "\n</g>\n</svg>"
        )

    from mcp_servers.art_svg import save_svg
    return save_svg(svg_text, _out)


@mcp.tool()
def list_subjects() -> str:
    """List the objects this server can draw."""
    return ", ".join(sorted(set(SHAPES)))


@mcp.tool()
def draw_scene_svg(subject: str, output: str = "scene.svg", color: str = "red",
                   texture: str = "none", style: str = "cartoon",
                   size: str = "standard") -> str:
    """Draw a stylized vector SCENE of an object as a layered SVG file.

    Each shape is a separate SVG element, so the UI can reveal/build the
    drawing element-by-element (live build animation), and every shape is
    filled with a texture instead of flat paint.

    Args:
        subject: apple, house, tree, cat, star, heart, car, rocket, flower,
                 mountain (also Uzbek: olma, uy, daraxt, mushuk, yulduz,
                 yurak, mashina, raketa, gul, tog)
        output: output SVG filename (relative path, e.g. "scene.svg")
        color: body color - red, green, blue, yellow, orange, purple, pink,
               cyan, brown, black, white, gold (Uzbek: qizil, kok/ko'k=BLUE,
               yashil, sariq, binafsha, pushti, qora, oq). Default: red.
        texture: fill texture - none, hatch, dots, grid, noise, gradient
                 (flat bo'yash o'rniga shakl ichini tekstura bilan to'ldiradi)
        style: cartoon | flat | realistic (so'rov uslubiga mos kontur texnikasi)
        size: standard | icon | avatar | card | poster | banner yoki 'WxH'

    Returns:
        the absolute path of the saved file, or an error message.
    """
    from mcp_servers.art_svg import build_scene_svg, save_svg

    try:
        svg, count = build_scene_svg(subject, color, texture,
                                     style=style, size=size)
    except ValueError as exc:
        # Part L (CP-L5): ochiq domen — ro'yxatdan tashqari obyekt "NOT_SUPPORTED"
        # deb belgilanadi, agent buni ko'rib LLM-generatsiyaga o'tishi mumkin.
        return "NOT_SUPPORTED: " + str(exc)
    return save_svg(svg, output)


@mcp.tool()
def ui_build_spec(app: str, output: str = "ui.uibuild.json", theme: str = "dark") -> str:
    """Create an INTERACTIVE UI construction plan (build spec) for a real
    live-build preview.

    The spec describes the REAL construction order of a UI screen as stages:
    1) background, 2) layout sections, 3) navigation layer (sidebar with a
    working open/close toggle), 4) content filled in design order, 5) action
    buttons that actually OPEN a window, 6) the opening window - first its
    shape and color, then 7) its inner content placed as a sketch. The frontend
    builds these as real HTML step by step (not a fade animation) and the
    finished parts are immediately interactive.

    Args:
        app: dashboard, mobile_app, login, profile, chat, settings, TODO
             (todo = REAL interactive task list: add, complete, delete,
             filters, counter, localStorage - also Uzbek: vazifalar)
             Uzbek aliases: boshqaruv, mobil, kirish, profil, suhbat, sozlamalar
        output: output spec filename (relative path, e.g. "todo.uibuild.json")
        theme: dark or light

    Returns:
        the absolute path of the saved spec file, or an error message.
    """
    from mcp_servers.ui_builder import build_spec, save_spec

    # Model ko'pincha noto'g'ri kengaytma beradi ("todo-app.html" kabi).
    # Frontend faqat *.uibuild.json fayllarni REAL live-build qiladi — kengaytmani
    # majburan to'g'rilaymiz (kontent JSON, kengaytma shartnoma). Papka saqlanadi
    # (output workspace'ga resolve qilingan absolyut yo'l bo'lishi mumkin).
    import os as _os
    _out = str(output)
    if not _os.path.basename(_out).lower().endswith(".uibuild.json"):
        _out = _os.path.splitext(_out)[0] + ".uibuild.json"
        output = _out

    try:
        spec = build_spec(app, theme)
    except ValueError as exc:
        return "NOT_SUPPORTED: " + str(exc)
    return save_spec(spec, output)


@mcp.tool()
def draw_ui_svg(app: str, output: str = "ui.svg", theme: str = "dark",
                 texture: str = "none", style: str = "cartoon",
                 size: str = "standard") -> str:
    """Draw a UI/UX mockup screen as a layered SVG (each UI element is a
    separate SVG element, revealed one-by-one by the live build).

    Args:
        app: dashboard, mobile_app, login, profile, chat, settings
             (also Uzbek: boshqaruv, mobil, kirish, profil, suhbat, sozlamalar)
        output: output SVG filename (relative path, e.g. "ui.svg")
        theme: dark or light
        texture: fill texture - none, hatch, dots, grid, noise, gradient
        style: cartoon | flat | realistic
        size: standard | icon | avatar | card | poster | banner yoki 'WxH'

    Returns:
        the absolute path of the saved file, or an error message.
    """
    from mcp_servers.art_svg import build_ui_svg, save_svg

    try:
        svg, count = build_ui_svg(app, theme, texture, style=style, size=size)
    except ValueError as exc:
        return "NOT_SUPPORTED: " + str(exc)
    return save_svg(svg, output)


if __name__ == "__main__":
    mcp.run()
