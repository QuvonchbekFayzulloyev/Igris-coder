"""
IGRIS BRAIN — SVG scene generator (element-by-element + texture fills)
======================================================================
Layered SVG chizmalar: har bir shakl alohida element bo'ladi (LiveBuildView
ularni birma-bir ko'rsatadi), shakllar ichi tekstura pattern'lari bilan
to'ldiriladi (hatch, dots, grid, noise, gradient). Ob'ekt scenalari va
UI/UX mockup scenalari mavjud.
"""

from __future__ import annotations

import math
import os
import re as _re

from mcp_servers.art_server import COLOR_MAP, DEFAULT_COLOR, _darken, _lighten


def _hex(rgb):
    """RGB tuple -> CSS hex."""
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c))) for c in rgb)


def _e(tag, attrs):
    """One self-closing SVG element."""
    a = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    return f"<{tag} {a}/>"


def _texture_defs(texture, color):
    """(defs_html, fill_ref) — texture yoki oddiy rang."""
    base = _hex(color)
    dark = _hex(_darken(color, 0.3))
    light = _hex(_lighten(color, 0.3))
    t = str(texture or "none").strip().lower()
    if t in ("hatch", "shtrix", "chiziqli"):
        return (
            f'<pattern id="tex" width="14" height="14" patternUnits="userSpaceOnUse" '
            f'patternTransform="rotate(45)"><rect width="14" height="14" fill="{base}"/>'
            f'<line x1="0" y1="0" x2="0" y2="14" stroke="{dark}" stroke-width="3"/></pattern>',
            "url(#tex)",
        )
    if t in ("dots", "nuqta"):
        return (
            f'<pattern id="tex" width="16" height="16" patternUnits="userSpaceOnUse">'
            f'<rect width="16" height="16" fill="{base}"/>'
            f'<circle cx="8" cy="8" r="3.4" fill="{dark}"/></pattern>',
            "url(#tex)",
        )
    if t in ("grid", "katak"):
        return (
            f'<pattern id="tex" width="24" height="24" patternUnits="userSpaceOnUse">'
            f'<rect width="24" height="24" fill="{base}"/>'
            f'<path d="M24 0H0V24" fill="none" stroke="{dark}" stroke-width="1.6" opacity="0.8"/></pattern>',
            "url(#tex)",
        )
    if t in ("noise", "shovqin", "govak", "texture"):
        return (
            f'<pattern id="tex" width="96" height="96" patternUnits="userSpaceOnUse">'
            f'<rect width="96" height="96" fill="{base}"/>'
            f'<filter id="texF"><feTurbulence type="fractalNoise" baseFrequency="0.8" '
            f'numOctaves="3" result="n"/><feColorMatrix in="n" type="matrix" values='
            f'"0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.55 0"/>'
            f'<feComposite operator="in" in2="SourceGraphic"/></filter>'
            f'<rect width="96" height="96" filter="url(#texF)"/></pattern>',
            "url(#tex)",
        )
    if t in ("gradient", "gradiyent"):
        return (
            f'<linearGradient id="tex" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{light}"/><stop offset="1" stop-color="{dark}"/>'
            f'</linearGradient>',
            "url(#tex)",
        )
    return "", base


def _svg_doc(elements, tex_defs=""):
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">']
    if tex_defs:
        parts.append(f"<defs>{tex_defs}</defs>")
    parts.extend(elements)
    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------------- #
# Talabdan kelib chiqib: uslub (style) va o'lcham (size) renderingni
# o'zgartiradi — namuna/shablon emas, so'rovga mos real natija.
# ---------------------------------------------------------------------- #

# O'lcham -> (kenglik, balandlik). Kontent 512x512 maydonida quriladi va
# proporsional markazlab shkalalanadi — noto'g'ri nisbat (distorsion) bo'lmaydi.
SIZE_TARGETS = {
    "standard": (512, 512),
    "icon": (256, 256),
    "avatar": (320, 320),
    "card": (640, 400),
    "poster": (768, 1024),
    "banner": (1024, 512),
}

# Uslub/janr -> kontur/qatlam/filter texnikasi (so'rov aytgan uslub haqiqatan
# qo'llanadi). `svg{filter:...}` — butun rasmga ruh beruvchi vizual effekt.
STYLE_CSS = {
    "child": (
        "path,rect,ellipse,circle,polygon,line{stroke-width:7;stroke:#00000055;"
        "stroke-linejoin:round;paint-order:stroke;}"
        "svg{filter:saturate(1.5) contrast(1.08);}"
    ),
    "bw": (
        "path,rect,ellipse,circle,polygon,line{stroke-width:2.6;stroke:#000;"
        "paint-order:stroke;}"
        "svg{filter:grayscale(1) contrast(1.2);}"
    ),
    "flat": "path,rect,ellipse,circle,polygon,line{paint-order:stroke;stroke-width:1.5;stroke:#0000001f;}",
    "cartoon": "path,rect,ellipse,circle,polygon,line{stroke-width:5;stroke:#0000002e;stroke-linejoin:round;}",
    "realistic": (
        "path,rect,ellipse,circle,polygon,line{stroke-width:1;stroke:#00000017;"
        "stroke-linejoin:round;}svg{filter:saturate(1.04) contrast(1.02);}"
    ),
    "fantasy": (
        "path,rect,ellipse,circle,polygon,line{stroke-width:3;stroke:#5b2a86;"
        "stroke-linejoin:round;}"
        "svg{filter:saturate(1.7) contrast(1.12) brightness(1.04) "
        "drop-shadow(0 0 5px #ffd76a66);}"
    ),
    "anime": (
        "path,rect,ellipse,circle,polygon,line{stroke-width:3.4;stroke:#111;"
        "stroke-linejoin:round;}"
        "svg{filter:saturate(1.4) contrast(1.1) brightness(1.03);}"
    ),
}


def _parse_size_wh(size) -> Optional[tuple[int, int]]:
    """'standard'|'icon'|... yoki '800x600' -> (w, h); aniqlanmasa None."""
    if not size:
        return None
    s = str(size).strip().lower()
    if s in SIZE_TARGETS:
        return SIZE_TARGETS[s]
    m = _re.search(r"(\d{2,4})\s*[xх*×]\s*(\d{2,4})", s)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if 32 <= w <= 4096 and 32 <= h <= 4096:
            return w, h
    return None


def _svg_doc_requirement(elements, tex_defs="", style="cartoon", size="standard") -> str:
    """So'rov uslubi/o'lchamini qo'llagan SVG hujjat.

    - style: kontur texnikasi (flat/cartoon/realistic) CSS orqali.
    - size: kontent markazlab, proporsional shkalalanadi (viewBox o'zgaradi).
    """
    css = STYLE_CSS.get(str(style or "cartoon").strip().lower(), STYLE_CSS["cartoon"])
    wh = _parse_size_wh(size)
    inner = ""
    if css:
        inner += f"<style>{css}</style>"
    if tex_defs:
        inner += f"<defs>{tex_defs}</defs>"
    inner += "".join(elements)
    if wh is None or wh == (512, 512):
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">{inner}</svg>'
    w, h = wh
    s = min(w / 512.0, h / 512.0)
    dx = (w - 512.0 * s) / 2.0
    dy = (h - 512.0 * s) / 2.0
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}">'
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>'
        f'<g transform="translate({dx:.1f} {dy:.1f}) scale({s:.4f})">{inner}</g>'
        f"</svg>"
    )


# ---------------------------------------------------------------------- #
# Object scenes (each shape = separate element)
# ---------------------------------------------------------------------- #

def _svg_apple(color, tex):
    dark = _hex(_darken(color))
    return [
        _e("ellipse", {"cx": 256, "cy": 252, "rx": 148, "ry": 146, "fill": tex, "stroke": dark, "stroke-width": 6}),
        _e("ellipse", {"cx": 256, "cy": 142, "rx": 60, "ry": 44, "fill": tex}),
        _e("rect", {"x": 247, "y": 56, "width": 18, "height": 78, "rx": 6, "fill": "#7a4f1e"}),
        _e("path", {"d": "M 266 88 Q 344 56 358 122 Q 324 126 268 98 Z", "fill": "#2f9e4f"}),
        _e("ellipse", {"cx": 178, "cy": 180, "rx": 46, "ry": 34, "fill": _hex(_lighten(color, 0.55)), "opacity": 0.75}),
    ]


def _svg_house(color, tex):
    dark = _hex(_darken(color))
    return [
        _e("rect", {"x": 110, "y": 200, "width": 292, "height": 220, "fill": tex, "stroke": dark, "stroke-width": 5}),
        _e("polygon", {"points": "90,204 256,80 422,204", "fill": "#b03030", "stroke": "#6e1616", "stroke-width": 4}),
        _e("rect", {"x": 226, "y": 300, "width": 60, "height": 120, "rx": 4, "fill": "#7a4a1e", "stroke": "#4c2b10", "stroke-width": 3}),
        _e("rect", {"x": 140, "y": 256, "width": 52, "height": 52, "rx": 6, "fill": "#8ec9e8", "stroke": "#4a7d9e", "stroke-width": 3}),
        _e("rect", {"x": 320, "y": 256, "width": 52, "height": 52, "rx": 6, "fill": "#8ec9e8", "stroke": "#4a7d9e", "stroke-width": 3}),
        _e("rect", {"x": 330, "y": 120, "width": 26, "height": 92, "rx": 5, "fill": "#8b5a2b"}),
    ]


def _svg_tree(color, tex):
    return [
        _e("rect", {"x": 234, "y": 260, "width": 44, "height": 170, "rx": 8, "fill": "#7a4f1e"}),
        _e("ellipse", {"cx": 256, "cy": 200, "rx": 130, "ry": 120, "fill": tex, "stroke": _hex(_darken(color)), "stroke-width": 4}),
        _e("ellipse", {"cx": 300, "cy": 130, "rx": 80, "ry": 62, "fill": _hex(_lighten(color, 0.25))}),
        _e("ellipse", {"cx": 196, "cy": 150, "rx": 60, "ry": 48, "fill": _hex(_lighten(color, 0.15))}),
    ]


def _svg_cat(color, tex):
    return [
        _e("polygon", {"points": "150,220 178,110 226,190", "fill": tex}),
        _e("polygon", {"points": "362,220 334,110 286,190", "fill": tex}),
        _e("ellipse", {"cx": 256, "cy": 280, "rx": 130, "ry": 118, "fill": tex, "stroke": _hex(_darken(color)), "stroke-width": 5}),
        _e("ellipse", {"cx": 208, "cy": 262, "rx": 18, "ry": 22, "fill": "#202020"}),
        _e("ellipse", {"cx": 304, "cy": 262, "rx": 18, "ry": 22, "fill": "#202020"}),
        _e("ellipse", {"cx": 213, "cy": 268, "rx": 7, "ry": 9, "fill": "#e8f4ff"}),
        _e("ellipse", {"cx": 299, "cy": 268, "rx": 7, "ry": 9, "fill": "#e8f4ff"}),
        _e("polygon", {"points": "244,318 256,306 268,318 256,334", "fill": "#f0789a"}),
        _e("path", {"d": "M 224 348 Q 256 372 288 348", "fill": "none", "stroke": "#202020", "stroke-width": 5, "stroke-linecap": "round"}),
        _e("path", {"d": "M 176 320 Q 140 326 122 312", "fill": "none", "stroke": "#202020", "stroke-width": 4, "stroke-linecap": "round"}),
        _e("path", {"d": "M 336 320 Q 372 326 390 312", "fill": "none", "stroke": "#202020", "stroke-width": 4, "stroke-linecap": "round"}),
    ]


def _svg_star(color, tex):
    pts = []
    for i in range(10):
        r = 190 if i % 2 == 0 else 88
        ang = -1.5708 + i * 0.6283
        pts.append((256 + r * math.cos(ang), 256 + r * math.sin(ang)))
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return [
        _e("polygon", {"points": points, "fill": tex, "stroke": _hex(_darken(color)), "stroke-width": 5, "stroke-linejoin": "round"}),
        _e("circle", {"cx": 256, "cy": 256, "r": 40, "fill": _hex(_lighten(color, 0.6)), "opacity": 0.9}),
    ]


def _svg_heart(color, tex):
    return [
        _e("path", {
            "d": "M 256 432 C 118 330 118 172 200 172 C 240 172 256 202 256 232 "
                 "C 256 202 272 172 312 172 C 394 172 394 330 256 432 Z",
            "fill": tex, "stroke": _hex(_darken(color)), "stroke-width": 5, "stroke-linejoin": "round",
        }),
        _e("ellipse", {"cx": 200, "cy": 240, "rx": 34, "ry": 26, "fill": _hex(_lighten(color, 0.55)), "opacity": 0.8}),
    ]


def _svg_car(color, tex):
    dark = _hex(_darken(color))
    return [
        _e("rect", {"x": 70, "y": 250, "width": 372, "height": 120, "rx": 26, "fill": tex, "stroke": dark, "stroke-width": 6}),
        _e("path", {"d": "M 150 250 L 190 160 Q 210 132 260 132 L 330 132 Q 376 132 386 182 L 398 250 Z", "fill": tex, "stroke": dark, "stroke-width": 6}),
        _e("rect", {"x": 208, "y": 156, "width": 96, "height": 70, "rx": 10, "fill": "#bfe3f5", "stroke": "#3f6f8f", "stroke-width": 4}),
        _e("rect", {"x": 316, "y": 156, "width": 52, "height": 70, "rx": 10, "fill": "#bfe3f5", "stroke": "#3f6f8f", "stroke-width": 4}),
        _e("circle", {"cx": 160, "cy": 370, "r": 52, "fill": "#202020", "stroke": dark, "stroke-width": 6}),
        _e("circle", {"cx": 160, "cy": 370, "r": 22, "fill": "#c8c8c8"}),
        _e("circle", {"cx": 352, "cy": 370, "r": 52, "fill": "#202020", "stroke": dark, "stroke-width": 6}),
        _e("circle", {"cx": 352, "cy": 370, "r": 22, "fill": "#c8c8c8"}),
        _e("rect", {"x": 84, "y": 266, "width": 26, "height": 20, "rx": 6, "fill": "#ffe9a8"}),
        _e("rect", {"x": 402, "y": 266, "width": 26, "height": 20, "rx": 6, "fill": "#ff8a8a"}),
    ]


def _svg_rocket(color, tex):
    return [
        _e("path", {"d": "M 256 60 Q 330 170 330 260 L 330 300 L 182 300 L 182 260 Q 182 170 256 60 Z", "fill": tex, "stroke": _hex(_darken(color)), "stroke-width": 5}),
        _e("circle", {"cx": 256, "cy": 230, "r": 38, "fill": "#bfe3f5", "stroke": "#3f6f8f", "stroke-width": 5}),
        _e("polygon", {"points": "182,300 150,410 210,330", "fill": "#c0392b"}),
        _e("polygon", {"points": "330,300 362,410 302,330", "fill": "#c0392b"}),
        _e("path", {"d": "M 214 380 Q 256 440 298 380 Q 256 420 214 380 Z", "fill": "#f5a623", "stroke": "#c47b08", "stroke-width": 3}),
        _e("circle", {"cx": 240, "cy": 96, "r": 10, "fill": "#ffffff", "opacity": 0.9}),
    ]


def _svg_flower(color, tex):
    els = []
    for i in range(6):
        ang = i * 1.0472
        cx = 256 + 74 * math.cos(ang)
        cy = 170 + 74 * math.sin(ang)
        els.append(_e("ellipse", {"cx": f"{cx:.0f}", "cy": f"{cy:.0f}", "rx": 52, "ry": 34, "fill": tex, "stroke": _hex(_darken(color)), "stroke-width": 3}))
    els.append(_e("circle", {"cx": 256, "cy": 170, "r": 42, "fill": _hex(_lighten(color, 0.6))}))
    els.append(_e("rect", {"x": 250, "y": 220, "width": 12, "height": 150, "rx": 5, "fill": "#3f9e4f"}))
    els.append(_e("ellipse", {"cx": 214, "cy": 300, "rx": 44, "ry": 18, "fill": "#3f9e4f", "transform": "rotate(-24 214 300)"}))
    els.append(_e("ellipse", {"cx": 298, "cy": 330, "rx": 44, "ry": 18, "fill": "#3f9e4f", "transform": "rotate(24 298 330)"}))
    return els


def _svg_mountain(color, tex):
    return [
        _e("rect", {"x": 0, "y": 400, "width": 512, "height": 112, "fill": "#cfe8c8"}),
        _e("polygon", {"points": "70,410 240,150 420,410", "fill": "#8f9aa8", "stroke": "#5f6a78", "stroke-width": 4}),
        _e("polygon", {"points": "120,410 280,90 470,410", "fill": tex, "stroke": _hex(_darken(color)), "stroke-width": 5}),
        _e("polygon", {"points": "258,132 236,196 300,196 276,158", "fill": "#ffffff", "opacity": 0.95}),
        _e("circle", {"cx": 90, "cy": 90, "r": 44, "fill": "#f5d76e", "stroke": "#d9b23c", "stroke-width": 4}),
        _e("ellipse", {"cx": 360, "cy": 90, "rx": 60, "ry": 22, "fill": "#ffffff", "opacity": 0.85}),
        _e("ellipse", {"cx": 300, "cy": 60, "rx": 44, "ry": 16, "fill": "#ffffff", "opacity": 0.85}),
    ]


def _svg_sun(color, tex):
    els = []
    # nurlar — 12 ta atrofida
    for i in range(12):
        ang = i * 0.5236
        x1 = 256 + 122 * math.cos(ang)
        y1 = 256 + 122 * math.sin(ang)
        x2 = 256 + 168 * math.cos(ang)
        y2 = 256 + 168 * math.sin(ang)
        els.append(_e("line", {"x1": f"{x1:.0f}", "y1": f"{y1:.0f}", "x2": f"{x2:.0f}", "y2": f"{y2:.0f}",
                               "stroke": tex, "stroke-width": 13, "stroke-linecap": "round"}))
    els.append(_e("circle", {"cx": 256, "cy": 256, "r": 96, "fill": tex,
                              "stroke": _hex(_darken(color)), "stroke-width": 5}))
    els.append(_e("circle", {"cx": 256, "cy": 256, "r": 40, "fill": _hex(_lighten(color, 0.5)), "opacity": 0.9}))
    return els


def _svg_moon(color, tex):
    return [
        _e("circle", {"cx": 246, "cy": 256, "r": 128, "fill": tex, "stroke": _hex(_darken(color)), "stroke-width": 5}),
        # yarim oy kesmasi
        _e("circle", {"cx": 304, "cy": 220, "r": 104, "fill": "#17171b"}),
        _e("circle", {"cx": 196, "cy": 214, "r": 11, "fill": _hex(_lighten(color, 0.4)), "opacity": 0.75}),
        _e("circle", {"cx": 232, "cy": 304, "r": 8, "fill": _hex(_lighten(color, 0.3)), "opacity": 0.6}),
    ]


def _svg_bird(color, tex):
    dark = _hex(_darken(color))
    return [
        _e("ellipse", {"cx": 250, "cy": 282, "rx": 62, "ry": 50, "fill": tex, "stroke": dark, "stroke-width": 4}),
        _e("circle", {"cx": 296, "cy": 256, "r": 24, "fill": tex, "stroke": dark, "stroke-width": 4}),
        _e("polygon", {"points": "312,250 344,242 314,262", "fill": "#f5a623"}),
        _e("circle", {"cx": 302, "cy": 252, "r": 4, "fill": "#202020"}),
        _e("path", {"d": "M 236 300 Q 150 322 118 280", "fill": "none", "stroke": tex, "stroke-width": 9, "stroke-linecap": "round"}),
        _e("path", {"d": "M 276 320 Q 262 362 284 380", "fill": "none", "stroke": dark, "stroke-width": 5, "stroke-linecap": "round"}),
        _e("path", {"d": "M 234 320 Q 222 362 244 380", "fill": "none", "stroke": dark, "stroke-width": 5, "stroke-linecap": "round"}),
    ]


def _svg_fish(color, tex):
    dark = _hex(_darken(color))
    return [
        _e("path", {"d": "M 104 256 Q 176 148 344 256 Q 176 364 104 256 Z", "fill": tex, "stroke": dark, "stroke-width": 5}),
        _e("polygon", {"points": "326 256 384 196 384 316", "fill": tex, "stroke": dark, "stroke-width": 4}),
        _e("circle", {"cx": 300, "cy": 238, "r": 9, "fill": "#202020"}),
        _e("path", {"d": "M 322 262 Q 338 270 348 258", "fill": "none", "stroke": "#202020", "stroke-width": 4, "stroke-linecap": "round"}),
        _e("path", {"d": "M 176 208 Q 216 188 258 214", "fill": "none", "stroke": _hex(_lighten(color, 0.5)), "stroke-width": 5, "stroke-linecap": "round", "opacity": 0.8}),
    ]


def _svg_butterfly(color, tex):
    dark = _hex(_darken(color))
    return [
        _e("ellipse", {"cx": 194, "cy": 208, "rx": 68, "ry": 88, "fill": tex, "stroke": dark, "stroke-width": 4, "transform": "rotate(-20 194 208)"}),
        _e("ellipse", {"cx": 318, "cy": 208, "rx": 68, "ry": 88, "fill": tex, "stroke": dark, "stroke-width": 4, "transform": "rotate(20 318 208)"}),
        _e("ellipse", {"cx": 216, "cy": 336, "rx": 50, "ry": 62, "fill": tex, "stroke": dark, "stroke-width": 4, "transform": "rotate(24 216 336)"}),
        _e("ellipse", {"cx": 296, "cy": 336, "rx": 50, "ry": 62, "fill": tex, "stroke": dark, "stroke-width": 4, "transform": "rotate(-24 296 336)"}),
        _e("rect", {"x": 250, "y": 148, "width": 12, "height": 220, "rx": 6, "fill": "#5a4630"}),
        _e("circle", {"cx": 256, "cy": 146, "r": 18, "fill": "#202020"}),
        _e("path", {"d": "M 244 144 Q 218 122 232 112", "fill": "none", "stroke": "#202020", "stroke-width": 3, "stroke-linecap": "round"}),
        _e("path", {"d": "M 268 144 Q 294 122 280 112", "fill": "none", "stroke": "#202020", "stroke-width": 3, "stroke-linecap": "round"}),
    ]


def _svg_mushroom(color, tex):
    dark = _hex(_darken(color))
    return [
        _e("path", {"d": "M 118 262 Q 256 118 394 262 Z", "fill": tex, "stroke": dark, "stroke-width": 5}),
        _e("rect", {"x": 226, "y": 258, "width": 60, "height": 142, "rx": 14, "fill": "#e8dcc8", "stroke": "#b8a890", "stroke-width": 4}),
        _e("ellipse", {"cx": 182, "cy": 240, "r": 16, "fill": "#ffffff", "opacity": 0.85}),
        _e("ellipse", {"cx": 256, "cy": 216, "r": 20, "fill": "#ffffff", "opacity": 0.85}),
        _e("ellipse", {"cx": 330, "cy": 244, "r": 14, "fill": "#ffffff", "opacity": 0.85}),
    ]


def _svg_ball(color, tex):
    return [
        _e("circle", {"cx": 256, "cy": 256, "r": 150, "fill": tex, "stroke": _hex(_darken(color)), "stroke-width": 6}),
        _e("path", {"d": "M 256 106 A 150 150 0 0 0 256 406", "fill": "none", "stroke": _hex(_lighten(color, 0.4)), "stroke-width": 9, "opacity": 0.8}),
        _e("path", {"d": "M 128 202 Q 256 262 384 202", "fill": "none", "stroke": _hex(_darken(color)), "stroke-width": 6}),
        _e("ellipse", {"cx": 204, "cy": 190, "rx": 26, "ry": 20, "fill": _hex(_lighten(color, 0.6)), "opacity": 0.8}),
    ]


def _svg_camel(color, tex):
    """Tuya (bactrian — ikki kamarli, oson va taniqli ko'rinish)."""
    dark = _hex(_darken(color))
    fur = _hex(_lighten(color, 0.35))
    return [
        # fon uzra yurish: oldingi oyog'lar
        _e("path", {"d": "M 176 350 L 168 448 L 186 448 L 194 352", "fill": fur, "stroke": dark, "stroke-width": 4}),
        _e("path", {"d": "M 330 350 L 338 448 L 356 448 L 350 352", "fill": fur, "stroke": dark, "stroke-width": 4}),
        # tana
        _e("ellipse", {"cx": 262, "cy": 330, "rx": 120, "ry": 62, "fill": tex, "stroke": dark, "stroke-width": 5}),
        # ikki kamar
        _e("path", {"d": "M 190 300 Q 216 216 252 296 Q 262 306 270 296 Q 300 214 332 298", "fill": tex, "stroke": dark, "stroke-width": 5, "stroke-linejoin": "round"}),
        _e("ellipse", {"cx": 222, "cy": 258, "rx": 34, "ry": 30, "fill": fur, "opacity": 0.55}),
        _e("ellipse", {"cx": 316, "cy": 260, "rx": 34, "ry": 30, "fill": fur, "opacity": 0.55}),
        # bo'yin + bosh
        _e("path", {"d": "M 352 320 Q 392 260 386 186 Q 384 158 364 158 Q 346 158 350 190 Q 356 250 322 302 Z", "fill": tex, "stroke": dark, "stroke-width": 5, "stroke-linejoin": "round"}),
        _e("ellipse", {"cx": 358, "cy": 150, "rx": 40, "ry": 26, "fill": tex, "stroke": dark, "stroke-width": 5}),
        _e("circle", {"cx": 344, "cy": 144, "r": 6, "fill": "#202020"}),
        # quloq + dumi
        _e("ellipse", {"cx": 348, "cy": 128, "rx": 8, "ry": 14, "fill": fur, "stroke": dark, "stroke-width": 3, "transform": "rotate(-18 348 128)"}),
        _e("path", {"d": "M 142 316 Q 106 296 100 258", "fill": "none", "stroke": dark, "stroke-width": 9, "stroke-linecap": "round"}),
        # orqa oyog'lar
        _e("path", {"d": "M 216 380 L 212 448 L 230 448 L 236 380", "fill": tex, "stroke": dark, "stroke-width": 4}),
        _e("path", {"d": "M 296 380 L 300 448 L 318 448 L 314 380", "fill": tex, "stroke": dark, "stroke-width": 4}),
        # yelka sohasi: sahna yer chizig'i
        _e("line", {"x1": 60, "y1": 452, "x2": 452, "y2": 452, "stroke": "#c8b78e", "stroke-width": 5, "stroke-linecap": "round", "opacity": 0.6}),
    ]


def _svg_dog(color, tex):
    dark = _hex(_darken(color))
    snout = _hex(_lighten(color, 0.55))
    return [
        # dumi
        _e("path", {"d": "M 380 300 Q 432 264 436 212", "fill": "none", "stroke": tex, "stroke-width": 16, "stroke-linecap": "round"}),
        # tana
        _e("ellipse", {"cx": 268, "cy": 322, "rx": 118, "ry": 72, "fill": tex, "stroke": dark, "stroke-width": 5}),
        # oyog'lar
        _e("rect", {"x": 186, "y": 366, "width": 34, "height": 86, "rx": 12, "fill": tex, "stroke": dark, "stroke-width": 4}),
        _e("rect", {"x": 240, "y": 378, "width": 34, "height": 78, "rx": 12, "fill": tex, "stroke": dark, "stroke-width": 4}),
        _e("rect", {"x": 306, "y": 378, "width": 34, "height": 78, "rx": 12, "fill": tex, "stroke": dark, "stroke-width": 4}),
        _e("rect", {"x": 356, "y": 366, "width": 34, "height": 86, "rx": 12, "fill": tex, "stroke": dark, "stroke-width": 4}),
        # bosh
        _e("circle", {"cx": 152, "cy": 226, "r": 62, "fill": tex, "stroke": dark, "stroke-width": 5}),
        # quloqlar (osilgan)
        _e("ellipse", {"cx": 104, "cy": 218, "rx": 20, "ry": 42, "fill": _hex(_darken(color, 0.18)), "stroke": dark, "stroke-width": 4, "transform": "rotate(14 104 218)"}),
        _e("ellipse", {"cx": 200, "cy": 218, "rx": 20, "ry": 42, "fill": _hex(_darken(color, 0.18)), "stroke": dark, "stroke-width": 4, "transform": "rotate(-14 200 218)"}),
        # tumsa + ko'z + burun
        _e("ellipse", {"cx": 122, "cy": 252, "rx": 34, "ry": 26, "fill": snout, "stroke": dark, "stroke-width": 4}),
        _e("ellipse", {"cx": 104, "cy": 244, "rx": 9, "ry": 7, "fill": "#202020"}),
        _e("path", {"d": "M 104 258 Q 116 268 128 260", "fill": "none", "stroke": "#202020", "stroke-width": 4, "stroke-linecap": "round"}),
        _e("circle", {"cx": 142, "cy": 212, "r": 8, "fill": "#202020"}),
        _e("circle", {"cx": 178, "cy": 212, "r": 8, "fill": "#202020"}),
        # dog bone
        _e("ellipse", {"cx": 176, "cy": 300, "rx": 26, "ry": 18, "fill": snout, "opacity": 0.7}),
        _e("line", {"x1": 70, "y1": 456, "x2": 450, "y2": 456, "stroke": "#c8b78e", "stroke-width": 5, "stroke-linecap": "round", "opacity": 0.6}),
    ]


def _svg_owl(color, tex):
    dark = _hex(_darken(color))
    belly = _hex(_lighten(color, 0.5))
    return [
        # quloq cho'qqilari
        _e("polygon", {"points": "150,140 178,84 204,132", "fill": tex, "stroke": dark, "stroke-width": 4}),
        _e("polygon", {"points": "362,140 334,84 308,132", "fill": tex, "stroke": dark, "stroke-width": 4}),
        # tana
        _e("ellipse", {"cx": 256, "cy": 280, "rx": 132, "ry": 152, "fill": tex, "stroke": dark, "stroke-width": 5}),
        # qorin
        _e("ellipse", {"cx": 256, "cy": 330, "rx": 82, "ry": 88, "fill": belly}),
        # qorin paternlari
        _e("path", {"d": "M 220 310 q 12 10 24 0 q 12 10 24 0 q 12 10 24 0", "fill": "none", "stroke": _hex(_darken(color, 0.25)), "stroke-width": 4, "stroke-linecap": "round"}),
        _e("path", {"d": "M 226 344 q 12 10 24 0 q 12 10 24 0 q 12 10 24 0", "fill": "none", "stroke": _hex(_darken(color, 0.25)), "stroke-width": 4, "stroke-linecap": "round"}),
        # katta ko'zalar (oq disk)
        _e("circle", {"cx": 206, "cy": 222, "r": 44, "fill": "#f8f4e8", "stroke": dark, "stroke-width": 4}),
        _e("circle", {"cx": 306, "cy": 222, "r": 44, "fill": "#f8f4e8", "stroke": dark, "stroke-width": 4}),
        _e("circle", {"cx": 206, "cy": 222, "r": 20, "fill": "#202020"}),
        _e("circle", {"cx": 306, "cy": 222, "r": 20, "fill": "#202020"}),
        _e("circle", {"cx": 212, "cy": 216, "r": 6, "fill": "#ffffff"}),
        _e("circle", {"cx": 312, "cy": 216, "r": 6, "fill": "#ffffff"}),
        # tumshuq
        _e("polygon", {"points": "240,248 272,248 256,278", "fill": "#f5a623", "stroke": "#c47b08", "stroke-width": 3}),
        # qanotlar
        _e("path", {"d": "M 130 262 Q 108 330 148 396", "fill": "none", "stroke": _hex(_darken(color, 0.3)), "stroke-width": 8, "stroke-linecap": "round"}),
        _e("path", {"d": "M 382 262 Q 404 330 364 396", "fill": "none", "stroke": _hex(_darken(color, 0.3)), "stroke-width": 8, "stroke-linecap": "round"}),
        # panjalar
        _e("line", {"x1": 216, "y1": 430, "x2": 216, "y2": 456, "stroke": "#c47b08", "stroke-width": 7, "stroke-linecap": "round"}),
        _e("line", {"x1": 296, "y1": 430, "x2": 296, "y2": 456, "stroke": "#c47b08", "stroke-width": 7, "stroke-linecap": "round"}),
        _e("line", {"x1": 196, "y1": 458, "x2": 236, "y2": 458, "stroke": "#c47b08", "stroke-width": 7, "stroke-linecap": "round"}),
        _e("line", {"x1": 276, "y1": 458, "x2": 316, "y2": 458, "stroke": "#c47b08", "stroke-width": 7, "stroke-linecap": "round"}),
    ]


def _svg_duck(color, tex):
    dark = _hex(_darken(color))
    wing = _hex(_lighten(color, 0.3))
    return [
        # suv chizig'i
        _e("path", {"d": "M 40 440 Q 90 428 140 440 Q 190 452 240 440 Q 290 428 340 440 Q 390 452 440 440 L 470 440", "fill": "none", "stroke": "#6db3d8", "stroke-width": 8, "stroke-linecap": "round", "opacity": 0.7}),
        # tana
        _e("path", {"d": "M 140 340 Q 130 258 220 250 Q 340 242 380 320 Q 396 372 340 398 Q 240 428 168 392 Q 142 374 140 340 Z", "fill": tex, "stroke": dark, "stroke-width": 5}),
        # dum
        _e("path", {"d": "M 146 306 Q 108 292 96 258 Q 128 264 150 280 Z", "fill": wing, "stroke": dark, "stroke-width": 4, "stroke-linejoin": "round"}),
        # qanot
        _e("path", {"d": "M 210 320 Q 258 296 306 318 Q 300 366 252 374 Q 216 372 210 320 Z", "fill": wing, "stroke": dark, "stroke-width": 4}),
        # bosh
        _e("circle", {"cx": 342, "cy": 208, "r": 52, "fill": tex, "stroke": dark, "stroke-width": 5}),
        # bo'yin
        _e("path", {"d": "M 322 250 Q 330 290 346 310 L 386 300 Q 366 270 366 240 Z", "fill": tex, "stroke": dark, "stroke-width": 5}),
        # tumshuq (o'rdak — keng)
        _e("ellipse", {"cx": 414, "cy": 212, "rx": 36, "ry": 18, "fill": "#f5a623", "stroke": "#c47b08", "stroke-width": 3}),
        _e("circle", {"cx": 346, "cy": 196, "r": 7, "fill": "#202020"}),
    ]


def _svg_robot(color, tex):
    dark = _hex(_darken(color))
    light = _hex(_lighten(color, 0.5))
    return [
        # antenna
        _e("line", {"x1": 256, "y1": 58, "x2": 256, "y2": 96, "stroke": dark, "stroke-width": 6}),
        _e("circle", {"cx": 256, "cy": 48, "r": 12, "fill": "#e0435f", "stroke": dark, "stroke-width": 4}),
        # bosh
        _e("rect", {"x": 168, "y": 96, "width": 176, "height": 120, "rx": 22, "fill": tex, "stroke": dark, "stroke-width": 5}),
        # ko'z oynalari
        _e("rect", {"x": 192, "y": 128, "width": 56, "height": 44, "rx": 12, "fill": "#17171b", "stroke": dark, "stroke-width": 4}),
        _e("rect", {"x": 264, "y": 128, "width": 56, "height": 44, "rx": 12, "fill": "#17171b", "stroke": dark, "stroke-width": 4}),
        _e("circle", {"cx": 210, "cy": 144, "r": 7, "fill": "#7ef29a"}),
        _e("circle", {"cx": 282, "cy": 144, "r": 7, "fill": "#7ef29a"}),
        # og'iz (panjara)
        _e("rect", {"x": 216, "y": 184, "width": 80, "height": 16, "rx": 6, "fill": "#17171b"}),
        _e("line", {"x1": 236, "y1": 184, "x2": 236, "y2": 200, "stroke": light, "stroke-width": 3}),
        _e("line", {"x1": 256, "y1": 184, "x2": 256, "y2": 200, "stroke": light, "stroke-width": 3}),
        _e("line", {"x1": 276, "y1": 184, "x2": 276, "y2": 200, "stroke": light, "stroke-width": 3}),
        # tana
        _e("rect", {"x": 158, "y": 232, "width": 196, "height": 150, "rx": 20, "fill": tex, "stroke": dark, "stroke-width": 5}),
        # ko'krak paneli
        _e("rect", {"x": 190, "y": 258, "width": 76, "height": 54, "rx": 10, "fill": light, "stroke": dark, "stroke-width": 4}),
        _e("circle", {"cx": 306, "cy": 270, "r": 14, "fill": "#e0435f", "stroke": dark, "stroke-width": 4}),
        _e("circle", {"cx": 306, "cy": 308, "r": 14, "fill": "#f5d76e", "stroke": dark, "stroke-width": 4}),
        _e("rect", {"x": 190, "y": 328, "width": 132, "height": 12, "rx": 6, "fill": "#17171b", "opacity": 0.8}),
        # qo'llar
        _e("rect", {"x": 96, "y": 246, "width": 44, "height": 118, "rx": 18, "fill": tex, "stroke": dark, "stroke-width": 5}),
        _e("rect", {"x": 372, "y": 246, "width": 44, "height": 118, "rx": 18, "fill": tex, "stroke": dark, "stroke-width": 5}),
        _e("circle", {"cx": 118, "cy": 382, "r": 18, "fill": dark}),
        _e("circle", {"cx": 394, "cy": 382, "r": 18, "fill": dark}),
        # oyoqlar
        _e("rect", {"x": 186, "y": 382, "width": 52, "height": 72, "rx": 14, "fill": tex, "stroke": dark, "stroke-width": 5}),
        _e("rect", {"x": 274, "y": 382, "width": 52, "height": 72, "rx": 14, "fill": tex, "stroke": dark, "stroke-width": 5}),
        _e("rect", {"x": 170, "y": 448, "width": 84, "height": 20, "rx": 9, "fill": dark}),
        _e("rect", {"x": 258, "y": 448, "width": 84, "height": 20, "rx": 9, "fill": dark}),
    ]


def _svg_plane(color, tex):
    dark = _hex(_darken(color))
    wingc = _hex(_lighten(color, 0.3))
    return [
        # fon bulutlari
        _e("ellipse", {"cx": 110, "cy": 120, "rx": 54, "ry": 20, "fill": "#ffffff", "opacity": 0.8}),
        _e("ellipse", {"cx": 410, "cy": 180, "rx": 60, "ry": 22, "fill": "#ffffff", "opacity": 0.7}),
        _e("ellipse", {"cx": 340, "cy": 80, "rx": 44, "ry": 16, "fill": "#ffffff", "opacity": 0.6}),
        # fyuzelyaj
        _e("path", {"d": "M 70 280 Q 200 232 350 240 Q 420 244 452 270 Q 420 296 350 300 Q 200 308 70 288 Z", "fill": tex, "stroke": dark, "stroke-width": 5}),
        # kokpit
        _e("path", {"d": "M 396 252 Q 428 258 446 270 Q 424 280 396 282 Z", "fill": "#bfe3f5", "stroke": dark, "stroke-width": 4}),
        # qanot
        _e("path", {"d": "M 240 292 L 196 402 Q 192 414 204 412 L 316 372 Q 330 366 326 350 L 310 300 Z", "fill": wingc, "stroke": dark, "stroke-width": 5, "stroke-linejoin": "round"}),
        # ikkinchi qanot (orqada)
        _e("path", {"d": "M 230 240 L 200 150 Q 196 138 208 142 L 306 186 Q 318 192 314 208 L 304 240 Z", "fill": wingc, "stroke": dark, "stroke-width": 5, "stroke-linejoin": "round"}),
        # quyruq
        _e("path", {"d": "M 84 282 L 46 214 Q 40 202 54 206 L 116 246 Z", "fill": wingc, "stroke": dark, "stroke-width": 5, "stroke-linejoin": "round"}),
        _e("path", {"d": "M 88 288 L 52 346 Q 46 358 60 354 L 120 300 Z", "fill": wingc, "stroke": dark, "stroke-width": 5, "stroke-linejoin": "round"}),
        # oynalar
        _e("circle", {"cx": 150, "cy": 262, "r": 9, "fill": "#bfe3f5", "stroke": dark, "stroke-width": 3}),
        _e("circle", {"cx": 190, "cy": 258, "r": 9, "fill": "#bfe3f5", "stroke": dark, "stroke-width": 3}),
        _e("circle", {"cx": 230, "cy": 254, "r": 9, "fill": "#bfe3f5", "stroke": dark, "stroke-width": 3}),
        _e("circle", {"cx": 270, "cy": 252, "r": 9, "fill": "#bfe3f5", "stroke": dark, "stroke-width": 3}),
        # harakat chiziqlari
        _e("line", {"x1": 70, "y1": 330, "x2": 160, "y2": 330, "stroke": dark, "stroke-width": 5, "stroke-linecap": "round", "opacity": 0.35}),
        _e("line", {"x1": 46, "y1": 356, "x2": 136, "y2": 356, "stroke": dark, "stroke-width": 5, "stroke-linecap": "round", "opacity": 0.25}),
    ]


SCENE_OBJECTS = {
    "apple": _svg_apple, "olma": _svg_apple,
    "house": _svg_house, "uy": _svg_house,
    "tree": _svg_tree, "daraxt": _svg_tree,
    "cat": _svg_cat, "mushuk": _svg_cat,
    "star": _svg_star, "yulduz": _svg_star,
    "heart": _svg_heart, "yurak": _svg_heart,
    "car": _svg_car, "mashina": _svg_car,
    "rocket": _svg_rocket, "raketa": _svg_rocket,
    "flower": _svg_flower, "gul": _svg_flower,
    "mountain": _svg_mountain, "tog": _svg_mountain, "tog'": _svg_mountain,
    "sun": _svg_sun, "quyosh": _svg_sun,
    "moon": _svg_moon, "oy": _svg_moon,
    "bird": _svg_bird, "qush": _svg_bird,
    "fish": _svg_fish, "baliq": _svg_fish,
    "butterfly": _svg_butterfly, "kapalak": _svg_butterfly,
    "mushroom": _svg_mushroom, "qo'ziqorin": _svg_mushroom,
    "ball": _svg_ball, "to'p": _svg_ball,
    "camel": _svg_camel, "tuya": _svg_camel,
    "dog": _svg_dog, "it": _svg_dog, "kuchuk": _svg_dog,
    "owl": _svg_owl, "mifqush": _svg_owl, "oqqush": _svg_owl,
    "duck": _svg_duck, "o'rdak": _svg_duck, "ordak": _svg_duck,
    "robot": _svg_robot,
    "plane": _svg_plane, "samolyot": _svg_plane, "airplane": _svg_plane,
}


# ---------------------------------------------------------------------- #
# UI/UX mockup scenes (each UI part = separate element)
# ---------------------------------------------------------------------- #

THEMES = {
    "dark": {"bg": "#17171b", "panel": "#26262c", "text": "#e4e4e7",
             "muted": "#5a5a63", "accent": "#f59e0b", "stroke": "#3a3a42"},
    "light": {"bg": "#f4f4f5", "panel": "#ffffff", "text": "#18181b",
              "muted": "#a3a3ad", "accent": "#3b82f6", "stroke": "#d9d9e0"},
}


def _ui_dashboard(th, tex):
    bg, panel, text, muted, accent, stroke = th["bg"], th["panel"], th["text"], th["muted"], th["accent"], th["stroke"]
    return [
        _e("rect", {"x": 0, "y": 0, "width": 512, "height": 512, "fill": bg}),
        _e("rect", {"x": 0, "y": 0, "width": 512, "height": 58, "fill": panel}),
        _e("circle", {"cx": 30, "cy": 29, "r": 15, "fill": accent}),
        _e("rect", {"x": 60, "y": 17, "width": 170, "height": 24, "rx": 5, "fill": text}),
        _e("rect", {"x": 402, "y": 14, "width": 92, "height": 30, "rx": 7, "fill": accent}),
        _e("rect", {"x": 0, "y": 58, "width": 140, "height": 454, "fill": panel}),
        _e("rect", {"x": 14, "y": 86, "width": 112, "height": 22, "rx": 4, "fill": accent}),
        _e("rect", {"x": 14, "y": 124, "width": 112, "height": 22, "rx": 4, "fill": muted}),
        _e("rect", {"x": 14, "y": 162, "width": 112, "height": 22, "rx": 4, "fill": muted}),
        _e("rect", {"x": 14, "y": 200, "width": 112, "height": 22, "rx": 4, "fill": muted}),
        _e("rect", {"x": 160, "y": 82, "width": 160, "height": 92, "rx": 10, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 176, "y": 98, "width": 96, "height": 14, "rx": 4, "fill": muted}),
        _e("rect", {"x": 176, "y": 122, "width": 62, "height": 28, "rx": 4, "fill": accent}),
        _e("rect", {"x": 336, "y": 82, "width": 160, "height": 92, "rx": 10, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 352, "y": 98, "width": 96, "height": 14, "rx": 4, "fill": muted}),
        _e("rect", {"x": 352, "y": 122, "width": 62, "height": 28, "rx": 4, "fill": accent}),
        _e("rect", {"x": 160, "y": 196, "width": 336, "height": 196, "rx": 10, "fill": tex, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 192, "y": 320, "width": 30, "height": 52, "rx": 4, "fill": accent}),
        _e("rect", {"x": 244, "y": 276, "width": 30, "height": 96, "rx": 4, "fill": accent}),
        _e("rect", {"x": 296, "y": 300, "width": 30, "height": 72, "rx": 4, "fill": accent}),
        _e("rect", {"x": 348, "y": 236, "width": 30, "height": 136, "rx": 4, "fill": accent}),
        _e("rect", {"x": 400, "y": 258, "width": 30, "height": 114, "rx": 4, "fill": accent}),
        _e("rect", {"x": 160, "y": 414, "width": 336, "height": 22, "rx": 4, "fill": muted}),
        _e("rect", {"x": 160, "y": 446, "width": 336, "height": 22, "rx": 4, "fill": muted}),
        _e("rect", {"x": 160, "y": 478, "width": 336, "height": 22, "rx": 4, "fill": muted}),
    ]


def _ui_mobile(th, tex):
    bg, panel, text, muted, accent, stroke = th["bg"], th["panel"], th["text"], th["muted"], th["accent"], th["stroke"]
    return [
        _e("rect", {"x": 0, "y": 0, "width": 512, "height": 512, "rx": 0, "fill": bg}),
        _e("rect", {"x": 0, "y": 0, "width": 512, "height": 34, "fill": panel}),
        _e("circle", {"cx": 396, "cy": 17, "r": 9, "fill": muted}),
        _e("rect", {"x": 24, "y": 60, "width": 240, "height": 30, "rx": 6, "fill": text}),
        _e("rect", {"x": 380, "y": 54, "width": 108, "height": 40, "rx": 20, "fill": accent}),
        _e("rect", {"x": 24, "y": 116, "width": 464, "height": 54, "rx": 14, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("circle", {"cx": 56, "cy": 143, "r": 12, "fill": muted}),
        _e("rect", {"x": 150, "y": 228, "width": 212, "height": 190, "rx": 16, "fill": tex, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 150, "y": 156, "width": 212, "height": 52, "rx": 16, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 170, "y": 176, "width": 120, "height": 14, "rx": 4, "fill": muted}),
        _e("rect", {"x": 382, "y": 228, "width": 106, "height": 190, "rx": 16, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 382, "y": 156, "width": 106, "height": 52, "rx": 16, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 398, "y": 176, "width": 74, "height": 14, "rx": 4, "fill": muted}),
        _e("rect", {"x": 24, "y": 452, "width": 464, "height": 44, "rx": 12, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("circle", {"cx": 60, "cy": 474, "r": 10, "fill": accent}),
        _e("circle", {"cx": 256, "cy": 474, "r": 10, "fill": muted}),
        _e("circle", {"cx": 452, "cy": 474, "r": 10, "fill": muted}),
    ]


def _ui_login(th, tex):
    bg, panel, text, muted, accent, stroke = th["bg"], th["panel"], th["text"], th["muted"], th["accent"], th["stroke"]
    return [
        _e("rect", {"x": 0, "y": 0, "width": 512, "height": 512, "fill": bg}),
        _e("circle", {"cx": 256, "cy": 130, "r": 44, "fill": accent}),
        _e("rect", {"x": 196, "y": 206, "width": 120, "height": 20, "rx": 5, "fill": text}),
        _e("rect", {"x": 116, "y": 262, "width": 280, "height": 58, "rx": 12, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 116, "y": 336, "width": 280, "height": 58, "rx": 12, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 116, "y": 420, "width": 280, "height": 62, "rx": 14, "fill": accent}),
        _e("rect", {"x": 196, "y": 498, "width": 120, "height": 12, "rx": 4, "fill": muted}),
    ]


def _ui_profile(th, tex):
    bg, panel, text, muted, accent, stroke = th["bg"], th["panel"], th["text"], th["muted"], th["accent"], th["stroke"]
    return [
        _e("rect", {"x": 0, "y": 0, "width": 512, "height": 512, "fill": bg}),
        _e("rect", {"x": 0, "y": 0, "width": 512, "height": 150, "fill": tex}),
        _e("circle", {"cx": 256, "cy": 120, "r": 56, "fill": accent, "stroke": th["bg"], "stroke-width": 8}),
        _e("rect", {"x": 196, "y": 180, "width": 120, "height": 24, "rx": 6, "fill": text}),
        _e("rect", {"x": 216, "y": 214, "width": 80, "height": 14, "rx": 4, "fill": muted}),
        _e("rect", {"x": 96, "y": 262, "width": 104, "height": 64, "rx": 10, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 204, "y": 262, "width": 104, "height": 64, "rx": 10, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 312, "y": 262, "width": 104, "height": 64, "rx": 10, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 96, "y": 352, "width": 320, "height": 30, "rx": 8, "fill": text, "opacity": 0.85}),
        _e("rect", {"x": 96, "y": 398, "width": 320, "height": 30, "rx": 8, "fill": muted}),
        _e("rect", {"x": 96, "y": 444, "width": 320, "height": 30, "rx": 8, "fill": muted}),
    ]


def _ui_chat(th, tex):
    bg, panel, text, muted, accent, stroke = th["bg"], th["panel"], th["text"], th["muted"], th["accent"], th["stroke"]
    return [
        _e("rect", {"x": 0, "y": 0, "width": 512, "height": 512, "fill": bg}),
        _e("rect", {"x": 0, "y": 0, "width": 512, "height": 60, "fill": panel}),
        _e("circle", {"cx": 30, "cy": 30, "r": 16, "fill": accent}),
        _e("rect", {"x": 60, "y": 19, "width": 140, "height": 22, "rx": 5, "fill": text}),
        _e("rect", {"x": 44, "y": 96, "width": 260, "height": 66, "rx": 16, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 208, "y": 184, "width": 260, "height": 66, "rx": 16, "fill": tex, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 44, "y": 272, "width": 300, "height": 66, "rx": 16, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 160, "y": 360, "width": 300, "height": 66, "rx": 16, "fill": tex, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 24, "y": 452, "width": 400, "height": 46, "rx": 23, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("circle", {"cx": 468, "cy": 475, "r": 20, "fill": accent}),
    ]


def _ui_settings(th, tex):
    bg, panel, text, muted, accent, stroke = th["bg"], th["panel"], th["text"], th["muted"], th["accent"], th["stroke"]
    return [
        _e("rect", {"x": 0, "y": 0, "width": 512, "height": 512, "fill": bg}),
        _e("rect", {"x": 0, "y": 0, "width": 512, "height": 60, "fill": panel}),
        _e("rect", {"x": 24, "y": 20, "width": 120, "height": 22, "rx": 5, "fill": text}),
        _e("rect", {"x": 24, "y": 92, "width": 464, "height": 66, "rx": 12, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 44, "y": 106, "width": 180, "height": 16, "rx": 4, "fill": muted}),
        _e("circle", {"cx": 452, "cy": 125, "r": 16, "fill": accent}),
        _e("rect", {"x": 24, "y": 172, "width": 464, "height": 66, "rx": 12, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 44, "y": 186, "width": 180, "height": 16, "rx": 4, "fill": muted}),
        _e("circle", {"cx": 452, "cy": 205, "r": 16, "fill": muted}),
        _e("rect", {"x": 24, "y": 252, "width": 464, "height": 66, "rx": 12, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 44, "y": 266, "width": 180, "height": 16, "rx": 4, "fill": muted}),
        _e("circle", {"cx": 452, "cy": 285, "r": 16, "fill": muted}),
        _e("rect", {"x": 24, "y": 340, "width": 464, "height": 66, "rx": 12, "fill": panel, "stroke": stroke, "stroke-width": 2}),
        _e("rect", {"x": 44, "y": 354, "width": 180, "height": 16, "rx": 4, "fill": muted}),
        _e("circle", {"cx": 452, "cy": 373, "r": 16, "fill": accent}),
    ]


UI_SCENES = {
    "dashboard": _ui_dashboard,
    "mobile_app": _ui_mobile, "mobile": _ui_mobile, "app": _ui_mobile,
    "login": _ui_login,
    "profile": _ui_profile,
    "chat": _ui_chat,
    "settings": _ui_settings,
}


# ---------------------------------------------------------------------- #
# Subject + color parser — model ko'pincha birlashgan ibora yuboradi:
#   subject="red apple" / "qizil olma" / "green apple fruit"
# Bu yerda deterministik tarzda ob'ekt va rangni ajratib olamiz — LLM'ning
# qaysi so'z ob'ekt, qaysi so'z rang ekanini aniqlashi shart emas (aniqlik).
# ---------------------------------------------------------------------- #

_COLOR_KEYS = frozenset(COLOR_MAP.keys())
_OBJECT_KEYS = frozenset(SCENE_OBJECTS.keys())


def parse_scene_phrase(subject, color=None):
    """Birlashgan iboradan (object_key, color_name) ajratib oladi.

    Misollar:
      parse_scene_phrase("red apple")            -> ("apple", "red")
      parse_scene_phrase("qizil olma")           -> ("olma", "qizil")
      parse_scene_phrase("green apple fruit")    -> ("apple", "green")
      parse_scene_phrase("uy")                   -> ("uy", None)
      parse_scene_phrase("apple", "blue")        -> ("apple", "blue")

    Qaytadi: (object_key, color_name|None). Topilmasa ValueError.
    """
    subj = str(subject or "").strip().lower()

    def _clean(s):
        return s.strip().replace("'", "").replace("’", "")

    # 1) To'g'ridan-to'g'ri mos — eng ishonchli
    if subj in _OBJECT_KEYS:
        return subj, _valid_color(color)

    # 2) Iboradan ob'ektni topamiz (alohida so'z yoki qo'shma so'z)
    words = [w for w in _re.split(r"[\s_,;\-]+", subj) if w]
    obj_key = None
    for w in words:
        cw = _clean(w)
        if cw in _OBJECT_KEYS:
            obj_key = cw
            break
    if obj_key is None:
        # "to'p" kabi apostroffi so'zlar — so'z ichida izlaymiz
        for w in words:
            for k in _OBJECT_KEYS:
                if k and (w.startswith(k) or k.startswith(w)) and len(w) >= 3:
                    obj_key = k
                    break
            if obj_key:
                break
    if obj_key is None:
        raise ValueError(
            f"unknown subject '{subject}'. Known: {', '.join(sorted(_OBJECT_KEYS))}"
        )

    # 3) Rangni aniqlaymiz: explicit color -> iboradagi rang -> default
    color_name = _valid_color(color)
    if color_name is None:
        for w in words:
            cw = _clean(w)
            if cw in _COLOR_KEYS:
                color_name = cw
                break
    return obj_key, color_name


def _valid_color(color):
    """Berilgan rang nomini tasdiqlaydi (noto'g'ri bo'lsa None)."""
    if color is None:
        return None
    c = str(color).strip().lower().replace("'", "").replace("’", "")
    if c in _COLOR_KEYS:
        return c
    # "light blue" kabi — birinchi so'zni tekshiramiz
    first = _re.split(r"[\s_,;\-]+", c)[0] if c else ""
    return first if first in _COLOR_KEYS else None


# ---------------------------------------------------------------------- #
# Public builders
# ---------------------------------------------------------------------- #

def build_scene_svg(subject, color, texture, style="cartoon", size="standard"):
    """Layered SVG for an object scene -> (svg_text, elements_count).

    `style` (flat/cartoon/realistic) va `size` (standard/icon/avatar/card/
    poster/banner yoki 'WxH') — so'rov talabidan kelib chiqib qo'llanadi:
    bir xil narsa turli uslub/o'lchamda HAQIQIY har xil ko'rinadi (namuna emas).
    """
    obj_key, color_name = parse_scene_phrase(subject, color)
    fn = SCENE_OBJECTS[obj_key]
    # Rang: iboradagi rang -> ob'ektning standart rangi -> qizil
    if color_name is not None:
        body = COLOR_MAP[color_name]
    else:
        body = DEFAULT_COLOR.get(obj_key) or COLOR_MAP["red"]
    defs, tex = _texture_defs(texture, body)
    elements = fn(body, tex)
    doc = _svg_doc_requirement(elements, defs, style=style, size=size)
    return doc, len(elements)


def _hex_to_rgb(h):
    """'#rrggbb' -> (r, g, b)."""
    h = str(h).lstrip("#")
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (200, 30, 40)


def build_ui_svg(app, theme, texture, style="cartoon", size="standard"):
    """Layered SVG for a UI mockup -> (svg_text, elements_count)."""
    key = str(app).strip().lower()
    fn = UI_SCENES.get(key)
    if fn is None:
        raise ValueError(
            f"unknown app '{app}'. Known: {', '.join(sorted(UI_SCENES))}"
        )
    th = THEMES.get(str(theme).strip().lower(), THEMES["dark"])
    # Tekstura bazasi — theme accent rangi (hex -> rgb)
    body = _hex_to_rgb(th["accent"])
    defs, tex = _texture_defs(texture, body)
    elements = fn(th, tex)
    doc = _svg_doc_requirement(elements, defs, style=style, size=size)
    return doc, len(elements)


def save_svg(svg_text: str, output: str) -> str:
    """SVG'ni faylga yozadi, absolyut yo'lni qaytaradi."""
    out = os.path.abspath(output)
    os.makedirs(os.path.dirname(out), exist_ok=True) if os.path.dirname(out) else None
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg_text)
    return f"image saved to {out}"
