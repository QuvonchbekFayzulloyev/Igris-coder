"""
IGRIS BRAIN - UI build-spec generator (REAL construction, not animation)
========================================================================
UI/UX chizmasini "qurilish bosqichlari" sifatida tasvirlaydi:
  1. Fon (background)
  2. Section'larga ajratish (layout)
  3. Navigatsiya qatlami (sidebar + ochish/yopish tugmasi - ishlaydi)
  4. Kontent - dizayn tartibi bo'yicha to'ldirish
  5. Amallar (tugma) - bosilganda oyna ochiladi
  6. Ochiladigan oyna - avval SHAKLI va RANGI
  7. Oyna ichi - skech ko'rinishida joylashtirish, tekshirish

Frontend bu spec'ni real HTML qilib BOSQICHMA-BOSQICH quradi (animatsiya
emas - haqiqiy DOM qurilishi), har bosqichdan keyin interaktivlik ishlaydi
(sidebar ochiladi/yopiladi, tugma oynani ochadi).
"""

from __future__ import annotations

import json

from mcp_servers.art_svg import THEMES

SPEC_VERSION = 2


# ---------------------------------------------------------------------- #
# Element yordamchilari (hammasi inline-style bilan quriladi -> foreignObject
# orqali video capture ham bir xil ko'rinadi)
# ---------------------------------------------------------------------- #

def _el(type_, x, y, w, h, **style):
    el = {"type": type_, "x": x, "y": y, "w": w, "h": h}
    el.update({k: v for k, v in style.items() if v is not None})
    return el


def rect(x, y, w, h, fill, stroke=None, strokeW=None, radius=None, opacity=None, shadow=None, **kw):
    return _el("rect", x, y, w, h, fill=fill, stroke=stroke, strokeW=strokeW,
               radius=radius, opacity=opacity, shadow=shadow, **kw)


def text(x, y, w, h, txt, color=None, size=None, weight=None, align=None, **kw):
    return _el("text", x, y, w, h, text=txt, color=color, size=size, weight=weight, align=align, **kw)


def icon(x, y, w, h, glyph, color=None, size=None, **kw):
    return _el("icon", x, y, w, h, glyph=glyph, color=color, size=size, **kw)


def button(x, y, w, h, txt, bg, color="#ffffff", radius=8, size=14, action=None, **kw):
    return _el("button", x, y, w, h, text=txt, bg=bg, color=color, radius=radius, size=size,
               action=action, **kw)


def toggle(x, y, w, h, glyph, target, collapsedW=56, color=None, **kw):
    return _el("toggle", x, y, w, h, glyph=glyph, target=target, collapsedW=collapsedW, color=color, **kw)


def input_(x, y, w, h, placeholder, bg=None, border=None, radius=8, **kw):
    return _el("input", x, y, w, h, placeholder=placeholder, bg=bg, border=border, radius=radius, **kw)


def avatar(x, y, r, fill, glyph=None, **kw):
    return _el("avatar", x, y, r * 2, r * 2, fill=fill, glyph=glyph, **kw)


def bar(x, y, w, h, fill, radius=4, **kw):
    return _el("bar", x, y, w, h, fill=fill, radius=radius, **kw)


def chip(x, y, w, h, txt, bg, color=None, radius=20, size=11, **kw):
    return _el("chip", x, y, w, h, text=txt, bg=bg, color=color, radius=radius, size=size, **kw)


def modal(id_, x, y, w, h, fill, stroke, radius=16, title=None, **kw):
    return _el("modal", x, y, w, h, id=id_, fill=fill, stroke=stroke, radius=radius, title=title, **kw)


# ---------------------------------------------------------------------- #
# Umumiy qurilish bosqichlari (har bir app uchun bir xil tuzilma)
# ---------------------------------------------------------------------- #

def _assign_ids(cfg):
    """Action'li tugmalarga avtomatik id beradi (interaction trigger uchun)."""
    def walk(elements):
        for el in elements:
            action = el.get("action")
            if action and not el.get("id") and action.get("target"):
                el["id"] = "btn-" + action["target"]
    for key in ("bg", "sections", "nav"):
        walk(cfg.get(key) or [])
    for block in (cfg.get("content_blocks") or [cfg.get("content") or []]):
        walk(block)
    walk(cfg.get("actions") or [])
    if cfg.get("modal"):
        walk(cfg["modal"].get("frame") or [])
        walk(cfg["modal"].get("content") or [])


def _reparent_sidebar(cfg):
    """Sidebar ichidagi nav elementlarini sidebar'ga ichki qiladi (collapse
da yashirinishi uchun) va main section'ni qayd qiladi."""
    sb = None
    for el in cfg.get("sections") or []:
        if el.get("id") == "sidebar":
            sb = el
            break
    if not sb:
        return
    sx, sy = sb["x"], sb["y"]
    for el in cfg.get("nav") or []:
        if el.get("type") == "toggle" and el.get("target") == "sidebar":
            continue  # ochish/yopish tugmasi sidebar ichida emas
        if el.get("x", 0) >= sx and el.get("y", 0) >= sy:
            el["parent"] = "sidebar"
            el["x"] = el["x"] - sx
            el["y"] = el["y"] - sy
    # main section'ga id beramiz (toggle uni siljitishi uchun)
    for el in cfg.get("sections") or []:
        if el.get("x", 0) > sx and el.get("fill") == cfg.get("bg", [{}])[0].get("fill"):
            el.setdefault("id", "main")
            break


def _reparent_modal(cfg):
    """Modal ichidagi elementlarni modal'ga ichki qiladi; ✕ tugmasiga close beradi."""
    modal_cfg = cfg.get("modal")
    if not modal_cfg:
        return
    frame = modal_cfg.get("frame") or []
    if not frame:
        return
    m = frame[0]
    mid = m.get("id")
    if not mid:
        return
    mx, my = m["x"], m["y"]
    for lst in (frame[1:], modal_cfg.get("content") or []):
        for el in lst:
            el["parent"] = mid
            el["x"] = el["x"] - mx
            el["y"] = el["y"] - my
            if el.get("type") == "icon" and el.get("glyph") == "✕" and not el.get("action"):
                el["action"] = {"kind": "close-modal", "target": mid}


def _stages_from(cfg):
    """cfg: {bg, sections, nav, nav_interactions, content_blocks, actions,
    action_interactions, modal} -> bosqichlar ro'yxati."""
    _assign_ids(cfg)

    def keep(elements):
        """Bo'sh bosqichlarni tashlab yuboradi — kompozitsiya plani bo'sh
        qavatni ko'tarmaydi (build_plan: 'composite has no components')."""
        return bool(elements)

    stages = [
        {"id": "bg", "title": "1 · Fon — sahifa asosi", "elements": cfg["bg"], "interactions": []},
        {"id": "layout", "title": "2 · Section'larga ajratish", "elements": cfg["sections"], "interactions": []},
        {"id": "nav", "title": "3 · Navigatsiya qatlami", "elements": cfg["nav"],
         "interactions": cfg.get("nav_interactions", [])},
    ]
    blocks = cfg.get("content_blocks") or [cfg["content"]]
    for i, block in enumerate(blocks):
        if not keep(block):
            continue
        stages.append({
            "id": f"content{i + 1}",
            "title": f"{4 + i} · Kontent — qism {i + 1}",
            "elements": block,
            "interactions": [],
        })
    action_idx = 3 + len(cfg.get("content_blocks") or [cfg["content"]])
    if keep(cfg["actions"]):
        stages.append({
            "id": "actions",
            "title": f"{action_idx + 1} · Amallar — tugmalar",
            "elements": cfg["actions"],
            "interactions": cfg.get("action_interactions", []),
        })
    modal_cfg = cfg.get("modal")
    if modal_cfg:
        if keep(modal_cfg["frame"]):
            stages.append({
                "id": "modal-frame",
                "title": f"{action_idx + 2} · Ochiladigan oyna — shakl va rang",
                "elements": modal_cfg["frame"],
                "interactions": [],
            })
        if keep(modal_cfg.get("content") or []):
            stages.append({
                "id": "modal-content",
                "title": f"{action_idx + 3} · Oyna ichi — skech va joylashuv",
                "elements": modal_cfg["content"],
                "interactions": [],
            })
    return stages


def build_spec(app: str, theme: str = "dark") -> dict:
    """App nomi va tema -> to'liq qurilish spec'i.

    Spec'ga universal kompozitsiya rejasi (plan) ham qo'shiladi — qavatlar
    (layers), yig'ish tartibi (exec_order) va overlap tekshiruvi. Bu 'detal
    ma detal' qurish texnologiyasining PLANNING bosqichi: hamma narsa avval
    rejada aniqlanadi, keyin frontend shu reja bo'yicha puzzle yig'adi.
    """
    key = str(app).strip().lower()
    cfg_fn = APPS.get(key)
    if cfg_fn is None:
        raise ValueError(f"unknown app '{app}'. Known: {', '.join(sorted(APPS))}")
    th = THEMES.get(str(theme).strip().lower(), THEMES["dark"])
    cfg = cfg_fn(th)
    _reparent_sidebar(cfg)
    _reparent_modal(cfg)
    spec = {
        "version": SPEC_VERSION,
        "app": key,
        "theme": "dark" if th is THEMES["dark"] else "light",
        "canvas": cfg.get("canvas", {"w": 960, "h": 640}),
        "vars": th,
        "stages": _stages_from(cfg),
    }
    # Universal kompozitsiya rejasi (ixtiyoriy — frontend uchun puzzle tartibi).
    # Eslatma: bu yerda LAZY import qilinadi — `ui_compose.compose_app()` ham
    # `build_spec`ni lazy import qiladi, aks holda modul yuklanish sikli bo'ladi.
    try:
        from ui_compose import compose_ui
        plan = compose_ui(spec)
        if plan.get("ok"):
            spec["plan"] = {
                "layers": plan["layers"],
                "exec_order": plan["exec_order"],
                "stage_plan": plan["stage_plan"],
                "overlaps": plan["overlaps"],
                "bounds": plan["bounds"],
                "bricks": plan["bricks"],
                "issues_total": plan["issues_total"],
            }
    except Exception as exc:  # pragma: no cover - faqat xatolikda
        import sys
        print(f"[ui_builder] plan skip (ixtiyoriy): {exc}", file=sys.stderr)
    return spec


def save_spec(spec: dict, output: str) -> str:
    """Spec'ni faylga yozadi, absolyut yo'lni qaytaradi."""
    import os
    out = os.path.abspath(output)
    os.makedirs(os.path.dirname(out), exist_ok=True) if os.path.dirname(out) else None
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, ensure_ascii=False, indent=1)
    return f"image saved to {out}"


# ---------------------------------------------------------------------- #
# Dashboard
# ---------------------------------------------------------------------- #

def _app_dashboard(th):
    bg, panel, text_c, muted, accent, stroke = th["bg"], th["panel"], th["text"], th["muted"], th["accent"], th["stroke"]
    return {
        "bg": [rect(0, 0, 960, 640, fill=bg)],
        "sections": [
            rect(0, 0, 960, 64, fill=panel, stroke=stroke, strokeW=1),
            rect(0, 64, 220, 576, fill=panel, stroke=stroke, strokeW=1, id="sidebar"),
            rect(220, 64, 740, 576, fill=bg),
        ],
        "nav": [
            toggle(12, 76, 36, 36, glyph="☰", target="sidebar", collapsedW=56, color=text_c),
            icon(30, 18, 32, 32, glyph="◆", color=accent, size=20),
            text(74, 22, 180, 24, "IGRIS CRM", color=text_c, size=17, weight=700),
            rect(18, 130, 184, 40, fill=accent, radius=8, opacity=0.16),
            text(32, 140, 150, 20, "Bosh sahifa", color=accent, size=13, weight=600),
            text(32, 188, 150, 20, "Analitika", color=muted, size=13),
            text(32, 236, 150, 20, "Loyihalar", color=muted, size=13),
            text(32, 284, 150, 20, "Xodimlar", color=muted, size=13),
            text(32, 332, 150, 20, "Sozlamalar", color=muted, size=13),
        ],
        "nav_interactions": [{"kind": "toggle-sidebar", "trigger": "sidebar", "collapsedW": 56}],
        "content_blocks": [
            [
                rect(244, 90, 220, 92, fill=panel, stroke=stroke, strokeW=1, radius=12),
                text(264, 106, 120, 14, "Jami daromad", color=muted, size=11),
                text(264, 126, 120, 26, "$128,400", color=text_c, size=22, weight=700),
                bar(264, 160, 120, 6, fill=accent, radius=3),
                rect(484, 90, 220, 92, fill=panel, stroke=stroke, strokeW=1, radius=12),
                text(504, 106, 120, 14, "Faol loyihalar", color=muted, size=11),
                text(504, 126, 120, 26, "24", color=text_c, size=22, weight=700),
                bar(504, 160, 90, 6, fill="#2f9e4f", radius=3),
                rect(724, 90, 220, 92, fill=panel, stroke=stroke, strokeW=1, radius=12),
                text(744, 106, 120, 14, "Yangi xodimlar", color=muted, size=11),
                text(744, 126, 120, 26, "7", color=text_c, size=22, weight=700),
                bar(744, 160, 60, 6, fill="#3b82f6", radius=3),
            ],
            [
                rect(244, 206, 460, 240, fill=panel, stroke=stroke, strokeW=1, radius=12),
                text(264, 222, 200, 16, "Oylik statistikasi", color=text_c, size=14, weight=600),
                bar(284, 360, 26, 64, fill=accent, radius=4),
                bar(336, 320, 26, 104, fill=accent, radius=4),
                bar(388, 340, 26, 84, fill=accent, radius=4),
                bar(440, 280, 26, 144, fill=accent, radius=4),
                bar(492, 300, 26, 124, fill=accent, radius=4),
                bar(544, 264, 26, 160, fill=accent, radius=4),
                bar(596, 330, 26, 94, fill=accent, radius=4),
                bar(648, 290, 26, 134, fill=accent, radius=4),
                rect(724, 206, 220, 240, fill=panel, stroke=stroke, strokeW=1, radius=12),
                text(744, 222, 160, 16, "Tezkor vazifalar", color=text_c, size=14, weight=600),
                rect(744, 252, 180, 26, fill=muted, radius=6, opacity=0.5),
                rect(744, 288, 180, 26, fill=muted, radius=6, opacity=0.35),
                rect(744, 324, 180, 26, fill=muted, radius=6, opacity=0.5),
                rect(744, 360, 180, 26, fill=muted, radius=6, opacity=0.35),
            ],
            [
                rect(244, 470, 700, 150, fill=panel, stroke=stroke, strokeW=1, radius=12),
                text(264, 486, 200, 16, "Oxirgi faollik", color=text_c, size=14, weight=600),
                avatar(284, 526, 14, fill=accent, glyph="A"),
                avatar(340, 526, 14, fill="#2f9e4f", glyph="B"),
                avatar(396, 526, 14, fill="#3b82f6", glyph="C"),
                text(452, 522, 300, 16, "3 ta yangi a'zo qo'shildi", color=text_c, size=13),
                text(452, 542, 300, 14, "12 daqiqa oldin", color=muted, size=11),
                text(760, 540, 160, 20, "Barchasini ko'rish", color=accent, size=12, weight=600, align="right"),
            ],
        ],
        "actions": [
            button(824, 16, 118, 34, "+ Yangi loyiha", bg=accent, radius=8, size=13, action={"kind": "open-modal", "target": "modal-new"}),
        ],
        "action_interactions": [{"kind": "open-modal", "trigger": "btn-modal-new", "target": "modal-new"}],
        "modal": {
            "frame": [
                rect(270, 130, 420, 380, fill=panel, stroke=accent, strokeW=2, radius=16, shadow=True, id="modal-new"),
                icon(650, 144, 26, 26, glyph="✕", color=muted, size=16),
                text(300, 154, 240, 24, "Yangi loyiha yaratish", color=text_c, size=17, weight=700),
                rect(300, 190, 360, 1, fill=stroke),
            ],
            "content": [
                text(300, 212, 200, 16, "Loyiha nomi", color=muted, size=12),
                input_(300, 232, 360, 44, "Misol: Mobil ilova", bg=bg, border=stroke, radius=8),
                text(300, 296, 200, 16, "Tavsif", color=muted, size=12),
                input_(300, 316, 360, 80, "Loyiha haqida qisqacha...", bg=bg, border=stroke, radius=8),
                button(300, 420, 170, 44, "Bekor qilish", bg=bg, color=text_c, radius=8, size=13, action=None),
                button(490, 420, 170, 44, "Yaratish", bg=accent, radius=8, size=13),
            ],
        },
    }


# ---------------------------------------------------------------------- #
# Login
# ---------------------------------------------------------------------- #

def _app_login(th):
    bg, panel, text_c, muted, accent, stroke = th["bg"], th["panel"], th["text"], th["muted"], th["accent"], th["stroke"]
    return {
        "bg": [rect(0, 0, 960, 640, fill=bg)],
        "sections": [
            rect(270, 90, 420, 460, fill=panel, stroke=stroke, strokeW=1, radius=20, id="card"),
            rect(270, 90, 420, 8, fill=accent, radius=4),
        ],
        "nav": [
            avatar(460, 144, 30, fill=accent, glyph="I"),
            text(414, 216, 132, 22, "IGRIS", color=text_c, size=19, weight=700, align="center"),
            text(414, 244, 132, 16, "Tizimga kirish", color=muted, size=12, align="center"),
        ],
        "content": [
            text(330, 290, 240, 16, "Email yoki login", color=muted, size=12),
            input_(330, 312, 300, 46, "email@misol.uz", bg=bg, border=stroke, radius=10),
            text(330, 378, 240, 16, "Parol", color=muted, size=12),
            input_(330, 400, 300, 46, "••••••••", bg=bg, border=stroke, radius=10),
        ],
        "actions": [
            button(330, 468, 300, 48, "Kirish", bg=accent, radius=10, size=15, weight=600,
                   action={"kind": "open-modal", "target": "modal-welcome"}),
        ],
        "action_interactions": [{"kind": "open-modal", "trigger": "btn-modal-welcome", "target": "modal-welcome"}],
        "modal": {
            "frame": [
                rect(330, 210, 300, 240, fill=panel, stroke=accent, strokeW=2, radius=16, shadow=True, id="modal-welcome"),
                icon(596, 224, 24, 24, glyph="✕", color=muted, size=14),
                avatar(470, 246, 26, fill="#2f9e4f", glyph="✓"),
                text(390, 306, 180, 22, "Xush kelibsiz!", color=text_c, size=18, weight=700, align="center"),
            ],
            "content": [
                text(380, 340, 200, 34, "Hisobingizga muvaffaqiyatli kirdingiz. Bosh sahifaga yo'naltirilmoqdasiz...",
                     color=muted, size=12, align="center"),
                button(410, 398, 140, 40, "Davom etish", bg=accent, radius=8, size=13),
                bar(430, 456, 100, 4, fill=accent, radius=2),
            ],
        },
    }


# ---------------------------------------------------------------------- #
# Chat
# ---------------------------------------------------------------------- #

def _app_chat(th):
    bg, panel, text_c, muted, accent, stroke = th["bg"], th["panel"], th["text"], th["muted"], th["accent"], th["stroke"]
    return {
        "bg": [rect(0, 0, 960, 640, fill=bg)],
        "sections": [
            rect(0, 0, 960, 64, fill=panel, stroke=stroke, strokeW=1),
            rect(0, 64, 960, 512, fill=bg),
            rect(0, 576, 960, 64, fill=panel, stroke=stroke, strokeW=1, id="composer"),
        ],
        "nav": [
            icon(20, 18, 32, 32, glyph="←", color=text_c, size=20),
            avatar(70, 14, 20, fill=accent, glyph="M"),
            text(110, 20, 200, 20, "Malika Karimova", color=text_c, size=15, weight=600),
            text(110, 40, 200, 14, "onlayn", color="#2f9e4f", size=11),
            icon(900, 18, 32, 32, glyph="⋮", color=muted, size=20),
        ],
        "content": [
            rect(70, 96, 280, 66, fill=panel, stroke=stroke, strokeW=1, radius=14),
            text(90, 112, 240, 16, "Salom! Loyiha holati qanday?", color=text_c, size=13),
            text(90, 132, 240, 14, "10:24", color=muted, size=10),
            rect(610, 186, 280, 66, fill=accent, radius=14, opacity=0.9),
            text(630, 202, 240, 16, "Hammasi joyida, ertaga demo beramiz", color="#1c1205", size=13),
            text(630, 222, 240, 14, "10:25", color="#1c1205", size=10, opacity=0.7),
            rect(70, 276, 300, 66, fill=panel, stroke=stroke, strokeW=1, radius=14),
            text(90, 292, 260, 16, "Yaxshi, maketlarni ham ko'rsatib qo'y", color=text_c, size=13),
            text(90, 312, 260, 14, "10:26", color=muted, size=10),
            rect(560, 366, 330, 66, fill=accent, radius=14, opacity=0.9),
            text(580, 382, 290, 16, "Albatta, 5 daqiqada tayyor bo'ladi 👍", color="#1c1205", size=13),
            text(580, 402, 290, 14, "10:26", color="#1c1205", size=10, opacity=0.7),
            rect(70, 470, 220, 40, fill=panel, stroke=stroke, strokeW=1, radius=20),
            text(90, 482, 180, 14, "Yaxshi, kutyapman", color=text_c, size=12),
        ],
        "actions": [
            button(20, 586, 120, 42, "+ Yangi chat", bg=accent, radius=10, size=13,
                   action={"kind": "open-modal", "target": "modal-newchat"}),
            input_(160, 586, 700, 42, "Xabar yozing...", bg=bg, border=stroke, radius=21),
            button(880, 586, 60, 42, "➤", bg=accent, radius=21, size=16),
        ],
        "action_interactions": [{"kind": "open-modal", "trigger": "btn-modal-newchat", "target": "modal-newchat"}],
        "modal": {
            "frame": [
                rect(290, 180, 380, 300, fill=panel, stroke=accent, strokeW=2, radius=16, shadow=True, id="modal-newchat"),
                icon(630, 194, 24, 24, glyph="✕", color=muted, size=14),
                text(320, 200, 240, 22, "Yangi chat boshlash", color=text_c, size=16, weight=700),
            ],
            "content": [
                input_(320, 240, 320, 44, "Ism yoki login qidiring...", bg=bg, border=stroke, radius=10),
                avatar(340, 312, 20, fill="#3b82f6", glyph="D"),
                text(380, 316, 220, 18, "Dilshod Bekov", color=text_c, size=13),
                avatar(340, 356, 20, fill="#9b59b6", glyph="S"),
                text(380, 360, 220, 18, "Sardor Aliyev", color=text_c, size=13),
                avatar(340, 400, 20, fill="#2f9e4f", glyph="N"),
                text(380, 404, 220, 18, "Nigora Rahimova", color=text_c, size=13),
                button(480, 436, 160, 40, "Tanlangan bilan suhbat", bg=accent, radius=8, size=12),
            ],
        },
    }


# ---------------------------------------------------------------------- #
# Settings
# ---------------------------------------------------------------------- #

def _app_settings(th):
    bg, panel, text_c, muted, accent, stroke = th["bg"], th["panel"], th["text"], th["muted"], th["accent"], th["stroke"]
    return {
        "bg": [rect(0, 0, 960, 640, fill=bg)],
        "sections": [
            rect(0, 0, 960, 64, fill=panel, stroke=stroke, strokeW=1),
            rect(0, 64, 220, 576, fill=panel, stroke=stroke, strokeW=1, id="sidebar"),
            rect(220, 64, 740, 576, fill=bg),
        ],
        "nav": [
            toggle(12, 76, 36, 36, glyph="☰", target="sidebar", collapsedW=56, color=text_c),
            icon(30, 18, 32, 32, glyph="⚙", color=accent, size=20),
            text(74, 22, 180, 24, "Sozlamalar", color=text_c, size=17, weight=700),
            text(32, 140, 150, 20, "Umumiy", color=accent, size=13, weight=600),
            text(32, 188, 150, 20, "Hisob", color=muted, size=13),
            text(32, 236, 150, 20, "Xavfsizlik", color=muted, size=13),
            text(32, 284, 150, 20, "Bildirishnomalar", color=muted, size=13),
            text(32, 332, 150, 20, "Til", color=muted, size=13),
        ],
        "nav_interactions": [{"kind": "toggle-sidebar", "trigger": "sidebar", "collapsedW": 56}],
        "content": [
            rect(260, 100, 660, 72, fill=panel, stroke=stroke, strokeW=1, radius=12),
            text(284, 116, 300, 16, "Tungi rejim", color=text_c, size=14, weight=600),
            text(284, 138, 400, 14, "Interfeysni qorong'i ko'rinishda ko'rsatish", color=muted, size=11),
            chip(840, 116, 56, 30, "", bg=accent, radius=15),
            rect(260, 192, 660, 72, fill=panel, stroke=stroke, strokeW=1, radius=12),
            text(284, 208, 300, 16, "Xabar tovushlari", color=text_c, size=14, weight=600),
            text(284, 230, 400, 14, "Yangiliklarda ovozli xabar berish", color=muted, size=11),
            chip(840, 208, 56, 30, "", bg=muted, radius=15),
            rect(260, 284, 660, 72, fill=panel, stroke=stroke, strokeW=1, radius=12),
            text(284, 300, 300, 16, "Ma'lumotlarni saqlash", color=text_c, size=14, weight=600),
            text(284, 322, 400, 14, "Faqat Wi-Fi orqali yuklab olish", color=muted, size=11),
            chip(840, 300, 56, 30, "", bg=accent, radius=15),
            rect(260, 376, 660, 72, fill=panel, stroke=stroke, strokeW=1, radius=12),
            text(284, 392, 300, 16, "Profilni tahrirlash", color=text_c, size=14, weight=600),
            text(284, 414, 400, 14, "Ism, avatar va bio ma'lumotlari", color=muted, size=11),
        ],
        "actions": [
            button(760, 386, 140, 40, "Ochish", bg=bg, color=text_c, radius=8, size=13,
                   action={"kind": "open-modal", "target": "modal-profile"}),
        ],
        "action_interactions": [{"kind": "open-modal", "trigger": "btn-modal-profile", "target": "modal-profile"}],
        "modal": {
            "frame": [
                rect(290, 150, 380, 360, fill=panel, stroke=accent, strokeW=2, radius=16, shadow=True, id="modal-profile"),
                icon(630, 164, 24, 24, glyph="✕", color=muted, size=14),
                avatar(470, 180, 28, fill=accent, glyph="U"),
                text(410, 244, 140, 20, "Profilni tahrirlash", color=text_c, size=16, weight=700, align="center"),
            ],
            "content": [
                text(330, 284, 160, 14, "Ism", color=muted, size=12),
                input_(330, 302, 300, 42, "Umid Karimov", bg=bg, border=stroke, radius=8),
                text(330, 358, 160, 14, "Bio", color=muted, size=12),
                input_(330, 376, 300, 70, "Igris agent bilan ishlayman...", bg=bg, border=stroke, radius=8),
                button(330, 462, 140, 42, "Bekor qilish", bg=bg, color=text_c, radius=8, size=13),
                button(490, 462, 140, 42, "Saqlash", bg=accent, radius=8, size=13),
            ],
        },
    }


# ---------------------------------------------------------------------- #
# Profile
# ---------------------------------------------------------------------- #

def _app_profile(th):
    bg, panel, text_c, muted, accent, stroke = th["bg"], th["panel"], th["text"], th["muted"], th["accent"], th["stroke"]
    return {
        "bg": [rect(0, 0, 960, 640, fill=bg)],
        "sections": [
            rect(0, 0, 960, 190, fill=accent, opacity=0.85),
            rect(0, 190, 960, 450, fill=bg),
        ],
        "nav": [
            icon(20, 18, 32, 32, glyph="←", color="#1c1205", size=20),
            text(420, 22, 120, 22, "Profil", color="#1c1205", size=16, weight=700, align="center"),
        ],
        "content": [
            avatar(428, 120, 46, fill=panel, glyph="UK"),
            text(380, 226, 200, 24, "Umid Karimov", color=text_c, size=18, weight=700, align="center"),
            text(380, 254, 200, 16, "umid@misol.uz", color=muted, size=12, align="center"),
            rect(180, 272, 180, 84, fill=panel, stroke=stroke, strokeW=1, radius=12),
            text(200, 288, 140, 20, "Loyihalar", color=muted, size=11, align="center"),
            text(200, 312, 140, 26, "24", color=text_c, size=22, weight=700, align="center"),
            rect(390, 272, 180, 84, fill=panel, stroke=stroke, strokeW=1, radius=12),
            text(410, 288, 140, 20, "Xodimlar", color=muted, size=11, align="center"),
            text(410, 312, 140, 26, "7", color=text_c, size=22, weight=700, align="center"),
            rect(600, 272, 180, 84, fill=panel, stroke=stroke, strokeW=1, radius=12),
            text(620, 288, 140, 20, "Yulduzlar", color=muted, size=11, align="center"),
            text(620, 312, 140, 26, "★ 4.8", color=accent, size=20, weight=700, align="center"),
            rect(180, 388, 600, 64, fill=panel, stroke=stroke, strokeW=1, radius=12),
            text(204, 408, 300, 16, "Faoliyat tarixi", color=text_c, size=14, weight=600),
            text(204, 430, 400, 14, "24 loyiha, 12 ta jamoa, 3 ta mukofot", color=muted, size=11),
            rect(180, 472, 600, 64, fill=panel, stroke=stroke, strokeW=1, radius=12),
            text(204, 492, 300, 16, "Ko'nikmalar", color=text_c, size=14, weight=600),
            chip(204, 508, 90, 26, "UX Design", bg=accent, radius=13, size=10, opacity=0.15),
            chip(306, 508, 110, 26, "Prototyping", bg="#3b82f6", radius=13, size=10, opacity=0.15),
            chip(428, 508, 90, 26, "Figma", bg="#9b59b6", radius=13, size=10, opacity=0.15),
        ],
        "actions": [
            button(760, 560, 170, 46, "Profilni tahrirlash", bg=accent, radius=10, size=13,
                   action={"kind": "open-modal", "target": "modal-edit"}),
        ],
        "action_interactions": [{"kind": "open-modal", "trigger": "btn-modal-edit", "target": "modal-edit"}],
        "modal": {
            "frame": [
                rect(290, 160, 380, 340, fill=panel, stroke=accent, strokeW=2, radius=16, shadow=True, id="modal-edit"),
                icon(630, 174, 24, 24, glyph="✕", color=muted, size=14),
                text(320, 182, 240, 22, "Profilni tahrirlash", color=text_c, size=16, weight=700),
            ],
            "content": [
                text(330, 222, 160, 14, "Ism", color=muted, size=12),
                input_(330, 240, 300, 42, "Umid Karimov", bg=bg, border=stroke, radius=8),
                text(330, 300, 160, 14, "Lavozim", color=muted, size=12),
                input_(330, 318, 300, 42, "UX Designer", bg=bg, border=stroke, radius=8),
                text(330, 378, 160, 14, "Shahar", color=muted, size=12),
                input_(330, 396, 300, 42, "Toshkent", bg=bg, border=stroke, radius=8),
                button(330, 452, 140, 42, "Bekor qilish", bg=bg, color=text_c, radius=8, size=13),
                button(490, 452, 140, 42, "Saqlash", bg=accent, radius=8, size=13),
            ],
        },
    }


# ---------------------------------------------------------------------- #
# Mobile app (portret 480x840)
# ---------------------------------------------------------------------- #

def _app_mobile(th):
    bg, panel, text_c, muted, accent, stroke = th["bg"], th["panel"], th["text"], th["muted"], th["accent"], th["stroke"]
    return {
        "canvas": {"w": 480, "h": 840},
        "bg": [rect(0, 0, 480, 840, fill=bg)],
        "sections": [
            rect(0, 0, 480, 40, fill=panel),
            rect(0, 40, 480, 62, fill=panel, stroke=stroke, strokeW=1),
            rect(0, 102, 480, 668, fill=bg),
            rect(0, 770, 480, 70, fill=panel, stroke=stroke, strokeW=1, id="tabbar"),
        ],
        "nav": [
            text(20, 12, 120, 16, "9:41", color=text_c, size=12, weight=600),
            icon(440, 12, 24, 18, glyph="▮▮", color=text_c, size=10),
            text(20, 52, 200, 24, "Bosh sahifa", color=text_c, size=18, weight=700),
            icon(430, 54, 32, 32, glyph="🔔", color=muted, size=16),
            rect(20, 118, 440, 58, fill=panel, stroke=stroke, strokeW=1, radius=14),
            icon(38, 134, 24, 24, glyph="⌕", color=muted, size=14),
            text(74, 138, 300, 16, "Qidirish...", color=muted, size=13),
        ],
        "content": [
            rect(20, 196, 440, 150, fill=accent, radius=16),
            text(40, 218, 300, 20, "Sayyor aksiya", color="#1c1205", size=16, weight=700),
            text(40, 246, 380, 34, "Yozgi to'plamda 30% chegirma. Faqat shu hafta!",
                 color="#1c1205", size=12, opacity=0.85),
            button(40, 292, 130, 38, "Batafsil", bg="#1c1205", color="#f5a623", radius=10, size=12),
            text(20, 366, 200, 20, "Mashhur tovarlar", color=text_c, size=16, weight=700),
            rect(20, 398, 212, 230, fill=panel, stroke=stroke, strokeW=1, radius=14),
            rect(40, 418, 172, 120, fill=muted, radius=10, opacity=0.3),
            text(40, 556, 170, 18, "Kurtka", color=text_c, size=14, weight=600),
            text(40, 580, 170, 16, "$89", color=accent, size=15, weight=700),
            rect(248, 398, 212, 230, fill=panel, stroke=stroke, strokeW=1, radius=14),
            rect(268, 418, 172, 120, fill=muted, radius=10, opacity=0.3),
            text(268, 556, 170, 18, "Krossovka", color=text_c, size=14, weight=600),
            text(268, 580, 170, 16, "$129", color=accent, size=15, weight=700),
            rect(20, 650, 212, 90, fill=panel, stroke=stroke, strokeW=1, radius=14),
            text(40, 668, 170, 16, "Savatcha", color=text_c, size=13, weight=600),
            text(40, 692, 170, 14, "3 ta mahsulot", color=muted, size=11),
            rect(248, 650, 212, 90, fill=panel, stroke=stroke, strokeW=1, radius=14),
            text(268, 668, 170, 16, "Sevimlilar", color=text_c, size=13, weight=600),
            text(268, 692, 170, 14, "5 ta mahsulot", color=muted, size=11),
        ],
        "actions": [
            button(190, 700, 100, 48, "+ Savatga", bg=accent, radius=24, size=13,
                   action={"kind": "open-modal", "target": "modal-sheet"}),
            icon(60, 788, 24, 24, glyph="⌂", color=accent, size=18),
            icon(228, 788, 24, 24, glyph="☰", color=muted, size=18),
            icon(396, 788, 24, 24, glyph="◈", color=muted, size=18),
        ],
        "action_interactions": [{"kind": "open-modal", "trigger": "btn-modal-sheet", "target": "modal-sheet"}],
        "modal": {
            "frame": [
                rect(20, 470, 440, 350, fill=panel, stroke=accent, strokeW=2, radius=22, shadow=True, id="modal-sheet"),
                rect(204, 484, 72, 4, fill=muted, radius=2),
                text(40, 506, 240, 22, "Buyurtma berish", color=text_c, size=17, weight=700),
            ],
            "content": [
                text(40, 546, 200, 16, "Yetkazish manzili", color=muted, size=12),
                input_(40, 566, 400, 46, "Manzilni kiriting...", bg=bg, border=stroke, radius=10),
                text(40, 632, 200, 16, "To'lov usuli", color=muted, size=12),
                rect(40, 652, 400, 52, fill=bg, border=stroke, radius=10),
                text(60, 670, 300, 16, "Karta orqali ···· 4242", color=text_c, size=13),
                button(40, 736, 400, 56, "Tasdiqlash va to'lash", bg=accent, radius=14, size=15, weight=600),
            ],
        },
    }


# ---------------------------------------------------------------------- #
# Todo — REAL interaktiv vazifalar ro'yxati (TodoMVC'dan kuchliroq)
# ---------------------------------------------------------------------- #
# Frontend (LiveBuildHTML) `spec.app == 'todo'` bo'lsa to'liq interaktivlikni
# yoqadi: qo'shish, bajarilganini belgilash, o'chirish, filtrlar, hisoblagich,
# localStorage'da saqlash, ustuvorlik (prio). Id'lar shartnomaviy:
#   todo-input / todo-input-modal  — matn kiritish
#   todo-add                        — qo'shish tugmasi
#   todo-list                       — vazifalar ro'yxati (dinamik qatorlar)
#   todo-count                      — "N ta qoldi" hisoblagichi
#   todo-empty                      — bo'sh holat xabari
#   todo-clear                      — bajarilganlarni tozalash
#   filter-all / filter-active / filter-done — filtr tugmalari
#   prio-low / prio-med / prio-high — ustuvorlik tanlash

def _app_todo(th):
    bg, panel, text_c, muted, accent, stroke = th["bg"], th["panel"], th["text"], th["muted"], th["accent"], th["stroke"]
    return {
        "bg": [rect(0, 0, 960, 640, fill=bg)],
        "sections": [
            rect(0, 0, 960, 64, fill=panel, stroke=stroke, strokeW=1),
            rect(0, 62, 960, 2, fill=accent),
            rect(120, 96, 720, 448, fill=panel, stroke=stroke, strokeW=1, radius=20, shadow=True),
        ],
        "nav": [
            icon(28, 16, 32, 32, glyph="✓", color=accent, size=22),
            text(72, 20, 300, 24, "Vazifalarim", color=text_c, size=17, weight=700),
            text(72, 46, 420, 14, "Rejalaringizni boshqaring — barchasi bir joyda", color=muted, size=11),
            button(820, 16, 120, 32, "+ Yangi vazifa", bg=accent, radius=8, size=13, weight=600,
                   action={"kind": "open-modal", "target": "modal-add"}),
        ],
        "content_blocks": [
            [
                text(152, 118, 260, 20, "Bugungi reja", color=text_c, size=16, weight=600),
                text(700, 116, 108, 20, "3 ta qoldi", color=accent, size=13, weight=600, align="right", id="todo-count"),
                bar(152, 142, 656, 6, fill=accent, radius=3, opacity=0.35),
                input_(152, 168, 560, 42, "Yangi vazifa qo'shing…", bg=bg, border=stroke, radius=10, id="todo-input"),
                button(724, 168, 84, 42, "Qo'shish", bg=accent, radius=10, size=14, weight=600,
                       action={"kind": "todo-add"}),
            ],
            [
                button(152, 228, 84, 30, "Barchasi", bg=bg, color=muted, radius=15, size=12, id="filter-all",
                       action={"kind": "todo-filter", "target": "all"}),
                button(244, 228, 70, 30, "Faol", bg=bg, color=muted, radius=15, size=12, id="filter-active",
                       action={"kind": "todo-filter", "target": "active"}),
                button(322, 228, 96, 30, "Bajarilgan", bg=bg, color=muted, radius=15, size=12, id="filter-done",
                       action={"kind": "todo-filter", "target": "done"}),
                rect(152, 268, 656, 212, fill=bg, radius=10, stroke=stroke, strokeW=1, id="todo-list"),
                text(330, 370, 300, 20, "Vazifalar yo'q — yuqoriga yozib qo'shing ✨", color=muted, size=12,
                     align="center", id="todo-empty"),
            ],
            [
                rect(152, 492, 656, 1, fill=stroke),
                text(152, 508, 260, 18, "Bajarilganlar jamlanadi va saqlanadi", color=muted, size=11),
                button(632, 502, 176, 32, "Barchasini tozalash", bg=bg, color=muted, radius=8, size=12,
                       action={"kind": "todo-clear"}),
            ],
        ],
        "actions": [],
        "action_interactions": [{"kind": "open-modal", "trigger": "btn-modal-add", "target": "modal-add"}],
        "modal": {
            "frame": [
                rect(300, 150, 360, 320, fill=panel, stroke=accent, strokeW=2, radius=16, shadow=True, id="modal-add"),
                icon(622, 164, 24, 24, glyph="✕", color=muted, size=14),
                text(330, 168, 240, 22, "Yangi vazifa", color=text_c, size=16, weight=700),
            ],
            "content": [
                text(340, 208, 200, 16, "Vazifa matni", color=muted, size=12),
                input_(340, 228, 280, 42, "Masalan: hisobotni tayyorlash…", bg=bg, border=stroke, radius=8, id="todo-input-modal"),
                text(340, 292, 200, 16, "Muhimlik", color=muted, size=12),
                button(340, 312, 80, 32, "Past", bg=bg, color=muted, radius=16, size=12, id="prio-low",
                       action={"kind": "todo-prio", "target": "low"}),
                button(428, 312, 80, 32, "O'rta", bg=accent, color="#fff", radius=16, size=12, id="prio-med",
                       action={"kind": "todo-prio", "target": "med"}),
                button(516, 312, 80, 32, "Yuqori", bg=bg, color=muted, radius=16, size=12, id="prio-high",
                       action={"kind": "todo-prio", "target": "high"}),
                button(340, 388, 130, 42, "Bekor qilish", bg=bg, color=text_c, radius=8, size=13,
                       action={"kind": "close-modal", "target": "modal-add"}),
                button(490, 388, 130, 42, "Qo'shish", bg=accent, radius=8, size=14, weight=600,
                       action={"kind": "todo-add"}),
            ],
        },
    }


# ---------------------------------------------------------------------- #
# APPS ro'yxati
# ---------------------------------------------------------------------- #

APPS: dict = {
    "dashboard": _app_dashboard, "boshqaruv": _app_dashboard,
    "login": _app_login, "kirish": _app_login,
    "chat": _app_chat, "suhbat": _app_chat,
    "settings": _app_settings, "sozlamalar": _app_settings,
    "profile": _app_profile, "profil": _app_profile,
    "mobile_app": _app_mobile, "mobile": _app_mobile, "app": _app_mobile,
    "todo": _app_todo, "vazifalar": _app_todo, "vazifa": _app_todo,
    "tasks": _app_todo, "tasklist": _app_todo, "ro'yxat": _app_todo,
}
