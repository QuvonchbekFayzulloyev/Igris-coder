"""SVG validator — yaratilgan chizma fayllarini ochib, baholaydi.

Ishlatish:
    python svg_validator.py                    # agent_workspace/*.svg skaneri
    python svg_validator.py duck.svg poster.svg
    python svg_validator.py --json report.json # mashina-format hisobot

Har bir fayl uchun:
  - viewBox, <!-- size: WxH --> va <!-- style: X --> izohlarini o'qiydi
  - strukturani tekshiradi (fon rect, elementlar soni, canvas chegarasi)
  - kompozitsiyani baholaydi (markazlash, to'ldirish, marginlar)
  - uslubga moslikni tekshiradi (realistic = gradient+soya, flat = hech biri)
  - palitra uyg'unligini baholaydi (ranglar soni, fon, xilma-xillik)

Natija: 0-100 ball (structure 25 | composition 25 | style 30 | palette 20).
Mezonlar svg-artist skill qoidalariga asoslangan.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Optional

DEFAULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")

STYLE_NAMES = ("cartoon", "realistic", "flat")
DEFAULT_STYLE = "cartoon"

# Son tokeni (path 'd' komandalari uchun) — `256-102.8` kabi birikkan sonlarni
# alohida ajratadi: har bir son o'z ishorasi bilan (minis keyingi sonning ishorasi).
_NUM_RE = r"[+-]?(?:\d+\.?\d*|\.\d+)"

# ---------------------------------------------------------------------- #
# O'qish: viewBox / izohlar / shakllar
# ---------------------------------------------------------------------- #

def read_svg_metadata(text: str) -> dict:
    """SVG boshidan viewBox, width/height va <!-- size --> / <!-- style -->
    izohlarini o'qiydi. Izohlar yo'q bo'lsa None qaytadi."""
    meta: dict = {"viewBox": None, "width": None, "height": None,
                  "size_comment": None, "style_comment": None}
    m = re.search(r"<svg\b[^>]*>", text, re.IGNORECASE)
    if m:
        tag = m.group(0)
        vb = re.search(
            r"viewBox\s*=\s*[\"']\s*([\d.+-]+)\s+([\d.+-]+)\s+([\d.+-]+)\s+([\d.+-]+)\s*[\"']",
            tag, re.IGNORECASE)
        if vb:
            meta["viewBox"] = tuple(float(vb.group(i)) for i in range(1, 5))
        for attr in ("width", "height"):
            am = re.search(attr + r"\s*=\s*[\"']([^\"']+)[\"']", tag, re.IGNORECASE)
            if am:
                meta[attr] = am.group(1)
    sm = re.search(r"<!--\s*size\s*:\s*([0-9xX×*\s]+?)\s*-->", text)
    if sm:
        meta["size_comment"] = sm.group(1).strip()
    st = re.search(r"<!--\s*style\s*:\s*([a-z]+)\s*-->", text, re.IGNORECASE)
    if st:
        style = st.group(1).strip().lower()
        meta["style_comment"] = style if style in STYLE_NAMES else None
    return meta


_SHAPE_RE = re.compile(r"<(rect|circle|ellipse|path|polygon|polyline|line)\b([^>]*)>",
                       re.IGNORECASE)


def _attr_num(attrs: str, name: str) -> Optional[float]:
    # (?<![\w-]) — cx'dagi 'x', stroke-width'dagi 'width' kabi soxta moslikni
    # oldini oladi: atribut nomi to'liq bo'lishi kerak (prefiks/suffiks emas).
    m = re.search(r"(?<![\w-])" + name + r"\s*=\s*[\"']\s*([\d.+-]+)\s*[\"']",
                  attrs, re.IGNORECASE)
    return float(m.group(1)) if m else None


def _attr_nums(attrs: str, name: str) -> list[float]:
    m = re.search(r"(?<![\w-])" + name + r"\s*=\s*[\"']([^\"']+)[\"']",
                  attrs, re.IGNORECASE)
    if not m:
        return []
    return [float(v) for v in re.findall(_NUM_RE, m.group(1))]


def _path_points_abs(d: str) -> list[tuple[float, float]]:
    """Path 'd' atributini ABSOLUT nuqtalarga o'tkazadi.

    Relative komandalar (m/l/c/s/q/t/h/v/a — kichik harflar) ham to'g'ri
    hisoblanadi: joriy nuqta kuzatiladi va delta'lar qo'shiladi. Bu validator
    bbox'ining path'li chizmalarda aniq bo'lishi uchun kerak (duck.svg kabi
    relative-komandali fayllar markazlashgan bo'lsa ham xato bbox bermasin).
    """
    tokens = re.findall(r"[a-zA-Z]|" + _NUM_RE, str(d))
    pts: list[tuple[float, float]] = []
    cx = cy = 0.0
    sx = sy = 0.0
    cmd = "M"
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if not re.fullmatch(_NUM_RE, t):
            cmd = t
            i += 1
            continue
        c = cmd.upper()
        rel = cmd.islower()
        if c == "Z":
            cx, cy = sx, sy
            cmd = "Z"
            continue
        try:
            if c in "ML":
                x, y = float(tokens[i]), float(tokens[i + 1])
                if rel:
                    x, y = x + cx, y + cy
                cx, cy = x, y
                pts.append((cx, cy))
                if c == "M":
                    sx, sy = cx, cy
                i += 2
            elif c == "H":
                x = float(tokens[i])
                cx = x + cx if rel else x
                pts.append((cx, cy))
                i += 1
            elif c == "V":
                y = float(tokens[i])
                cy = y + cy if rel else y
                pts.append((cx, cy))
                i += 1
            elif c == "C":
                x1, y1, x2, y2, x, y = (float(tokens[i + k]) for k in range(6))
                if rel:
                    x1, y1 = x1 + cx, y1 + cy
                    x2, y2 = x2 + cx, y2 + cy
                    x, y = x + cx, y + cy
                cx, cy = x, y
                pts.append((cx, cy))
                i += 6
            elif c == "S":
                x2, y2, x, y = (float(tokens[i + k]) for k in range(4))
                if rel:
                    x2, y2 = x2 + cx, y2 + cy
                    x, y = x + cx, y + cy
                cx, cy = x, y
                pts.append((cx, cy))
                i += 4
            elif c == "Q":
                x1, y1, x, y = (float(tokens[i + k]) for k in range(4))
                if rel:
                    x1, y1 = x1 + cx, y1 + cy
                    x, y = x + cx, y + cy
                cx, cy = x, y
                pts.append((cx, cy))
                i += 4
            elif c == "T":
                x, y = float(tokens[i]), float(tokens[i + 1])
                if rel:
                    x, y = x + cx, y + cy
                cx, cy = x, y
                pts.append((cx, cy))
                i += 2
            elif c == "A":
                x, y = float(tokens[i + 5]), float(tokens[i + 6])
                if rel:
                    x, y = x + cx, y + cy
                cx, cy = x, y
                pts.append((cx, cy))
                i += 7
            else:
                i += 1
        except (IndexError, ValueError):
            break  # buzilgan path — shu nuqtagacha bo'lganlar yetarli
    return pts


def _shape_bbox(attrs: str) -> Optional[tuple[float, float, float, float]]:
    """Bitta shaklning taxminiy bbox'i: (x0, y0, x1, y1)."""
    x, y = _attr_num(attrs, "x"), _attr_num(attrs, "y")
    w, h = _attr_num(attrs, "width"), _attr_num(attrs, "height")
    if w is not None:
        # x/y berilmagan bo'lsa (fon rect kabi) — 0 deb olamiz
        x0 = x if x is not None else 0.0
        y0 = y if y is not None else 0.0
        h0 = h if h is not None else w
        return (x0, y0, x0 + w, y0 + h0)
    cx, cy = _attr_num(attrs, "cx"), _attr_num(attrs, "cy")
    r = _attr_num(attrs, "r")
    if cx is not None and r is not None:
        cy0 = cy if cy is not None else r
        return (cx - r, cy0 - r, cx + r, cy0 + r)
    rx = _attr_num(attrs, "rx")
    if cx is not None and rx is not None:
        ry = _attr_num(attrs, "ry") or rx
        cy0 = cy if cy is not None else ry
        return (cx - rx, cy0 - ry, cx + rx, cy0 + ry)
    dm = re.search(r"(?<![\w-])d\s*=\s*[\"']([^\"']+)[\"']", attrs, re.IGNORECASE)
    if dm:
        pts = _path_points_abs(dm.group(1))
        if len(pts) >= 2:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return (min(xs), min(ys), max(xs), max(ys))
    vals = _attr_nums(attrs, "points")
    if len(vals) >= 4:
        xs, ys = vals[0::2], vals[1::2]
        return (min(xs), min(ys), max(xs), max(ys))
    return None


def _apply_wrapper_transform(bbox: tuple[float, float, float, float],
                             text: str) -> tuple[float, float, float, float]:
    """draw_custom_svg size-rescale `<g transform=translate+scale>` ni qo'llaydi.

    Model 512x512 shablon chizib, tool yangi o'lchamga moslagan bo'lsa —
    kontent bbox'i canvas koordinatalariga o'tkaziladi (kompozitsiya
    bahosi to'g'ri chiqishi uchun).
    """
    # FAQAT wrapper guruhini hisobga olamiz: <svg> tegidan keyingi dastlabki
    # 400 belgi ichidagi birinchi <g transform=...> (draw_custom_svg rescale
    # wrapper'i). Chuqurroq joylashgan kichik guruh transformlari kompozitsiya
    # bbox'ini buzmasligi uchun chetlab o'tiladi.
    sm = re.search(r"<svg\b[^>]*>", text, re.IGNORECASE)
    if not sm:
        return bbox
    head = text[sm.end():sm.end() + 400]
    m = re.search(r"<g\b[^>]*transform\s*=\s*[\"']([^\"']+)[\"']", head, re.IGNORECASE)
    if not m:
        return bbox
    t = m.group(1)
    sm = re.search(r"scale\(\s*([\d.+-]+)", t)
    if not sm:
        return bbox
    s = float(sm.group(1))
    tm = re.search(r"translate\(\s*([\d.+-]+)[,\s]+([\d.+-]+)\s*\)", t)
    tx = float(tm.group(1)) if tm else 0.0
    ty = float(tm.group(2)) if tm else 0.0
    x0, y0, x1, y1 = bbox
    return (x0 * s + tx, y0 * s + ty, x1 * s + tx, y1 * s + ty)


def _collect_colors(text: str) -> list[str]:
    """fill/stroke/stop-color qiymatlarini yig'adi (#abc -> #aabbcc normalizatsiya)."""
    colors: list[str] = []
    for m in re.finditer(r"(?:fill|stroke|stop-color)\s*=\s*[\"']([^\"']+)[\"']",
                         text, re.IGNORECASE):
        c = m.group(1).strip().lower()
        if not c or c == "none":
            continue
        if re.fullmatch(r"#[0-9a-f]{3}", c):
            c = "#" + "".join(ch * 2 for ch in c[1:])
        if re.fullmatch(r"#[0-9a-f]{6}", c):
            colors.append(c)
        else:
            colors.append(c)  # rgb(...) / rgba(...) / nom / url(#...)
    return colors


def _hex_hue(c: str) -> Optional[float]:
    """#rrggbb rangning hue burchagi (0-360), boshqa formatda None."""
    m = re.fullmatch(r"#([0-9a-f]{6})", c)
    if not m:
        return None
    r, g, b = (int(m.group(1)[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        return None
    if mx == r:
        h = 60 * (((g - b) / d) % 6)
    elif mx == g:
        h = 60 * (((b - r) / d) + 2)
    else:
        h = 60 * (((r - g) / d) + 4)
    return h % 360


# ---------------------------------------------------------------------- #
# Baholash
# ---------------------------------------------------------------------- #

def _score_structure(text: str, meta: dict, bg_ok: bool, bg_first: bool,
                     elem_count: int, content: Optional[tuple], vb: tuple,
                     checks: list) -> tuple[int, int]:
    """Struktura (25 ball): viewBox, fon, elementlar, canvas chegarasi."""
    vb_x0, vb_y0, vb_w, vb_h = vb
    score = 0
    if meta["viewBox"]:
        score += 5
        checks.append({"name": "viewBox", "ok": True, "detail": f"{vb_w:.0f}x{vb_h:.0f}"})
    else:
        checks.append({"name": "viewBox", "ok": False, "detail": "yo'q"})
    if bg_ok:
        score += 5
        checks.append({"name": "fon", "ok": True, "detail": "to'liq-canvas rect"})
    else:
        checks.append({"name": "fon", "ok": False, "detail": "topilmadi"})
    if bg_first:
        score += 5
        checks.append({"name": "fon tartibi", "ok": True, "detail": "birinchi element"})
    else:
        checks.append({"name": "fon tartibi", "ok": False, "detail": "birinchi emas"})
    if elem_count >= 8:
        score += 5
    elif elem_count >= 4:
        score += 3
    elif elem_count >= 2:
        score += 1
    checks.append({"name": "elementlar", "ok": elem_count >= 4,
                   "detail": f"{elem_count} ta"})
    # o'lcham atribute'lari viewBox bilan mosmi?
    size_ok = True
    if meta["width"] is not None:
        try:
            if abs(float(meta["width"]) - vb_w) > 1:
                size_ok = False
        except ValueError:
            size_ok = False
    if meta["height"] is not None:
        try:
            if abs(float(meta["height"]) - vb_h) > 1:
                size_ok = False
        except ValueError:
            size_ok = False
    # o'lcham atribute'lari — informatsion tekshiruv (ballga ta'sir qilmaydi)
    checks.append({"name": "o'lcham", "ok": size_ok,
                   "detail": "width/height viewBox bilan " + ("mos" if size_ok else "MOS EMAS")})
    # kontent canvas chegarasida qolganmi?
    if content is not None:
        x0, y0, x1, y1 = content
        if x0 < vb_x0 - 1 or y0 < vb_y0 - 1 or x1 > vb_x0 + vb_w + 1 or y1 > vb_y0 + vb_h + 1:
            checks.append({"name": "chegara", "ok": False, "detail": "kontent canvas'dan chiqib ketgan"})
        else:
            score += 5
            checks.append({"name": "chegara", "ok": True, "detail": "kontent canvas ichida"})
    else:
        checks.append({"name": "chegara", "ok": False, "detail": "kontent aniqlanmadi"})
    return score, 25


def _score_composition(content: Optional[tuple], vb: tuple,
                       checks: list) -> tuple[int, int]:
    """Kompozitsiya (25 ball): markazlash, to'ldirish, marginlar."""
    if content is None:
        checks.append({"name": "kompozitsiya", "ok": False, "detail": "kontent yo'q"})
        return 0, 25
    vb_x0, vb_y0, vb_w, vb_h = vb
    x0, y0, x1, y1 = content
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    ccx, ccy = vb_x0 + vb_w / 2.0, vb_y0 + vb_h / 2.0
    dx, dy = abs(cx - ccx) / vb_w, abs(cy - ccy) / vb_h

    score = 0
    if dx <= 0.12:
        score += 5
    elif dx <= 0.25:
        score += 3
    else:
        score += 1
    if dy <= 0.12:
        score += 5
    elif dy <= 0.25:
        score += 3
    else:
        score += 1
    checks.append({"name": "markazlash", "ok": dx <= 0.25 and dy <= 0.25,
                   "detail": f"siljish: H {dx * 100:.0f}% / V {dy * 100:.0f}%"})

    area = (x1 - x0) * (y1 - y0)
    fill = area / (vb_w * vb_h) if (vb_w * vb_h) > 0 else 0.0
    if 0.30 <= fill <= 0.95:
        score += 10
    elif 0.15 <= fill < 0.30:
        score += 6
    else:
        score += 3
    checks.append({"name": "to'ldirish", "ok": 0.30 <= fill <= 0.95,
                   "detail": f"canvasning {fill * 100:.0f}%"})

    # margin: kontent chekkaga tegib ketmasin (~2% ichida tegish = yomon)
    margin = min(x0 - vb_x0, vb_x0 + vb_w - x1, y0 - vb_y0, vb_y0 + vb_h - y1)
    if margin >= max(1.0, vb_w * 0.02):
        score += 5
        checks.append({"name": "margin", "ok": True, "detail": f"chekkadan {margin:.0f}px"})
    else:
        checks.append({"name": "margin", "ok": False, "detail": "kontent chekkaga tegib ketgan"})
    return score, 25


def _score_style(text: str, meta: dict, checks: list) -> tuple[int, int]:
    """Uslub (30 ball): gradient, soya, silliq chiziqlar, defs, uslubga moslik."""
    has_grad = ("linearGradient" in text) or ("radialGradient" in text)
    has_shadow = ("feDropShadow" in text) or ("feGaussianBlur" in text) or bool(
        re.search(r"rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\.", text))
    has_outline = bool(re.search(r"stroke\s*=\s*[\"'](?!none)", text, re.IGNORECASE)) \
        or bool(re.search(r"stroke-width\s*=", text, re.IGNORECASE))
    has_smooth = ("stroke-linejoin" in text) or ("stroke-linecap" in text)
    has_defs = bool(re.search(r"<defs>", text, re.IGNORECASE))

    score = 0
    if has_grad:
        score += 8
        checks.append({"name": "gradient", "ok": True, "detail": "linear/radial"})
    else:
        checks.append({"name": "gradient", "ok": False, "detail": "yo'q — tekis ranglar"})
    if has_shadow:
        score += 8
        checks.append({"name": "soya", "ok": True, "detail": "feDropShadow/Blur yoki yumshoq ellipse"})
    else:
        checks.append({"name": "soya", "ok": False, "detail": "yo'q"})
    if has_smooth:
        score += 4
        checks.append({"name": "silliq chiziqlar", "ok": True, "detail": "round join/cap"})
    else:
        checks.append({"name": "silliq chiziqlar", "ok": False, "detail": "yo'q"})
    if has_defs:
        score += 4
        checks.append({"name": "defs", "ok": True, "detail": "tartibli markup"})
    else:
        checks.append({"name": "defs", "ok": False, "detail": "yo'q"})

    # Uslub izohiga moslik (6 ball)
    style = meta["style_comment"] or DEFAULT_STYLE
    compliance = 0.0
    if style == "realistic":
        compliance = 1.0 if (has_grad and has_shadow) else (0.5 if (has_grad or has_shadow) else 0.0)
    elif style == "flat":
        compliance = 1.0 if (not has_grad and not has_shadow) else 0.3
    else:  # cartoon
        compliance = 1.0 if has_outline else 0.5
    score += int(round(compliance * 6))
    checks.append({"name": "uslub mosligi", "ok": compliance >= 0.8,
                   "detail": f"{style}: {compliance * 100:.0f}%"})
    return score, 30


def _score_palette(text: str, bg_fill: Optional[str], checks: list) -> tuple[int, int]:
    """Palitra (20 ball): ranglar soni, fon yumshoqligi, xilma-xillik.

    `bg_fill` — validate_svg_text tomonidan to'liq-canvas fon rect'dan
    aniqlangan rang (qayta skanerlanmaydi — birinchi rect har doim fon emas).
    """
    colors = _collect_colors(text)
    uniq = sorted(set(colors))
    n = len(uniq)
    score = 0
    if 2 <= n <= 8:
        score += 10
        checks.append({"name": "ranglar", "ok": True, "detail": f"{n} ta — uyg'un"})
    elif 9 <= n <= 14:
        score += 7
        checks.append({"name": "ranglar", "ok": True, "detail": f"{n} ta — biroz ko'p"})
    else:
        checks.append({"name": "ranglar", "ok": False, "detail": f"{n} ta — juda kam/yoki ko'p"})

    # Fon yumshoqligi: validate_svg_text aniqlagan to'liq-canvas fon rect rangi
    hard_bg = bg_fill in ("#fff", "#ffffff", "white", "#000", "#000000", "black")
    if bg_fill and not hard_bg:
        score += 5
        checks.append({"name": "fon rangi", "ok": True, "detail": f"{bg_fill} — yumshoq"})
    else:
        checks.append({"name": "fon rangi", "ok": False,
                       "detail": (bg_fill or "yo'q") + " — qattiq oq/qora"})

    # Xilma-xillik: turli hue'lar soni
    hues = {h for c in uniq for h in [_hex_hue(c)] if h is not None}
    if len(hues) >= 3:
        score += 5
        checks.append({"name": "xilma-xillik", "ok": True, "detail": f"{len(hues)} xil rang ohangi"})
    elif len(hues) == 2:
        score += 3
        checks.append({"name": "xilma-xillik", "ok": True, "detail": "2 xil rang ohangi"})
    else:
        checks.append({"name": "xilma-xillik", "ok": False, "detail": "monoxrom/aniqlanmadi"})
    return score, 20


def validate_svg_text(text: str) -> dict:
    """SVG matnini ochib, sifatni 0-100 ball bilan baholaydi."""
    text = str(text or "")
    report: dict = {
        "meta": read_svg_metadata(text),
        "checks": [],
        "scores": {},
        "total": 0,
        "verdict": "",
        "size_consistency": None,
    }
    meta = report["meta"]
    if "<svg" not in text.lower() or "</svg>" not in text.lower():
        report["checks"].append({"name": "hujjat", "ok": False, "detail": "<svg>...</svg> yo'q"})
        report["verdict"] = "noto'g'ri fayl"
        return report
    vb = meta["viewBox"]
    if vb is None:
        report["checks"].append({"name": "viewBox", "ok": False, "detail": "topilmadi"})
        report["verdict"] = "viewBox yo'q"
        return report

    # size izohi viewBox bilan mosmi?
    if meta["size_comment"]:
        mm = re.search(r"(\d+)\s*[xX×*]\s*(\d+)", meta["size_comment"])
        if mm:
            sw, sh = int(mm.group(1)), int(mm.group(2))
            report["size_consistency"] = (abs(sw - vb[2]) <= 1 and abs(sh - vb[3]) <= 1)
        else:
            report["size_consistency"] = None

    # Shakllarni skanerlaymiz
    shapes = list(_SHAPE_RE.finditer(text))
    elem_count = len(shapes)
    bg_ok = bg_first = False
    full_w, full_h = vb[2] * 0.98, vb[3] * 0.98
    bg_fill: Optional[str] = None
    content: Optional[tuple[float, float, float, float]] = None
    for idx, m in enumerate(shapes):
        attrs = m.group(2)
        bb = _shape_bbox(attrs)
        if bb is None:
            continue
        x0, y0, x1, y1 = bb
        is_bg = (m.group(1).lower() == "rect"
                 and (x1 - x0) >= full_w and (y1 - y0) >= full_h)
        if is_bg:
            bg_ok = True
            if idx == 0:
                bg_first = True
            if bg_fill is None:
                fm = re.search(r"fill\s*=\s*[\"']([^\"']+)[\"']", attrs, re.IGNORECASE)
                if fm:
                    bg_fill = fm.group(1).strip().lower()
            continue
        if content is None:
            content = (x0, y0, x1, y1)
        else:
            content = (min(content[0], x0), min(content[1], y0),
                       max(content[2], x1), max(content[3], y1))
    if content is not None:
        content = _apply_wrapper_transform(content, text)

    s_struct, _ = _score_structure(text, meta, bg_ok, bg_first, elem_count, content, vb,
                                   report["checks"])
    s_comp, _ = _score_composition(content, vb, report["checks"])
    s_style, _ = _score_style(text, meta, report["checks"])
    s_pal, _ = _score_palette(text, bg_fill, report["checks"])

    report["scores"] = {
        "structure": s_struct, "composition": s_comp,
        "style": s_style, "palette": s_pal,
    }
    report["total"] = s_struct + s_comp + s_style + s_pal
    total = report["total"]
    if total >= 80:
        report["verdict"] = "a'lo"
    elif total >= 65:
        report["verdict"] = "yaxshi"
    elif total >= 50:
        report["verdict"] = "o'rta"
    else:
        report["verdict"] = "past"
    return report


def validate_svg_file(path: str) -> dict:
    """Faylni ochib baholaydi; xatoda {'error': ...} qaytaradi.

    Bitta buzilgan fayl butun skanerni qulatmasligi uchun keng xato ushlash
    qo'llanadi — xato fayl o'z 'error' maydoni bilan hisobotda ko'rinadi.
    """
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError as exc:
        return {"error": str(exc), "path": path}
    try:
        report = validate_svg_text(text)
    except Exception as exc:
        return {"error": f"parse xatosi: {exc}", "path": path}
    report["path"] = path
    return report


# ---------------------------------------------------------------------- #
# CLI
# ---------------------------------------------------------------------- #

def _format_report(r: dict) -> str:
    if r.get("error"):
        return f"  ERROR: {r['error']}"
    meta = r["meta"]
    if r.get("verdict") in ("noto'g'ri fayl", "viewBox yo'q"):
        return "  viewBox : -- (yo'q)\n" + f"  BAHO: {r['total']}/100 ({r['verdict']})"
    lines = [f"  viewBox : {meta['viewBox'][2]:.0f}x{meta['viewBox'][3]:.0f}"
             f" (offset {meta['viewBox'][0]:.0f},{meta['viewBox'][1]:.0f})"]
    lines.append("  size    : " + (meta["size_comment"] or "-- izoh yo'q"))
    lines.append("  style   : " + (meta["style_comment"] or "-- izoh yo'q"))
    if r.get("size_consistency") is not None:
        lines.append("  o'lcham mosligi: "
                     + ("ha (viewBox = size izohi)" if r["size_consistency"] else "YO'Q (viewBox != size izohi!)"))
    bad = [c["name"] for c in r["checks"] if not c["ok"]]
    s = r["scores"]
    el = next((c["detail"] for c in r["checks"] if c["name"] == "elementlar"), "?")
    lines.append(f"  elementlar : {el} | zaif jihatlar: {', '.join(bad) if bad else '—'}")
    lines.append(f"  BAHO: {r['total']}/100 ({r['verdict']})")
    lines.append(f"    structure {s['structure']:>2}/25 | composition {s['composition']:>2}/25 | "
                 f"style {s['style']:>2}/30 | palette {s['palette']:>2}/20")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="SVG chizma sifatini baholaydi (0-100).")
    ap.add_argument("files", nargs="*", help="SVG fayllar (berilmasa agent_workspace skaneri)")
    ap.add_argument("--dir", default=DEFAULT_DIR, help="skanerlanadigan papka (default: agent_workspace)")
    ap.add_argument("--json", metavar="OUT", help="JSON hisobot fayliga yozish")
    args = ap.parse_args(argv)

    files = list(args.files)
    if not files:
        files = sorted(
            os.path.join(args.dir, f)
            for f in os.listdir(args.dir)
            if f.lower().endswith(".svg")
        ) if os.path.isdir(args.dir) else []
    if not files:
        print("SVG fayllar topilmadi (--dir yoki fayl yo'li bering).")
        return 1

    reports = [validate_svg_file(f) for f in files]
    for i, (path, r) in enumerate(zip(files, reports)):
        name = os.path.basename(path)
        print(f"[{i + 1}/{len(files)}] {name}")
        print(_format_report(r))
        if i < len(files) - 1:
            print()

    ok = [r for r in reports if not r.get("error") and r.get("total", 0) > 0]
    if ok:
        avg = sum(r["total"] for r in ok) / len(ok)
        best = max(ok, key=lambda r: r["total"])
        worst = min(ok, key=lambda r: r["total"])
        print(f"\n=== Umumiy: o'rtacha {avg:.0f}/100 | eng yaxshi: "
              f"{os.path.basename(best['path'])} ({best['total']}) | "
              f"eng past: {os.path.basename(worst['path'])} ({worst['total']})")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(reports, fh, ensure_ascii=False, indent=2)
        print(f"JSON hisobot: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
