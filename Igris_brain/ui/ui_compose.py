"""
IGRIS BRAIN — Universal UI Composition (UCC)
============================================
UI build spec'larini universal kompozitsiya yadrosi (composition.py) bilan
bog'laydi. "Detal-ma-detal qurish" texnologiyasi:

  1. PLAN (avval reja)     — spec'dagi BARCHA elementlar qatlamlarga bo'linadi
     (composition engine build_layers: barglar -> ildiz)
  2. UX JOYLASHTIRISH      — har bir element canvas chegarasida ekani,
     qavatlar va bosh menyu (sidebar/nav) bir-biriga XALAQIT QILMASLIGI
     tekshiriladi (overlap detektori)
  3. PUZZLE YIG'ISH        — exec_order: har element o'z o'rniga navbatma-navbat
     teriladi; id/koordinata mosligi tekshiriladi
  4. G'ISHT QAYTA ISHLATISH — bir xil (type+style) elementlar 'brick' sifatida
     aniqlanadi — avval qurilgan g'isht mavjud bo'lsa tanlanadi (reuse)
  5. STANDARTLAR           — o'lcham/chegara/spacing qoidalari bo'yicha tekshiruv

Bu modul faqat UI'ga emas — har qanday 'spec' (TTK, BOM, WBS, UI) uchun bir xil
ishlaydi: asosiy yadro composition.CompositionEngine.
"""

from __future__ import annotations

from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from task.composition import CardRegistry, CompositionEngine, Component, ItemCard

# ---------------------------------------------------------------------- #
# UI standartlari (sodda, kengaytiriladigan)
# ---------------------------------------------------------------------- #

UI_STANDARDS = {
    # elementlar o'lcham chegaralari
    "min_el_w": 8,
    "min_el_h": 8,
    "overlap_tolerance": 1,  # piksel xatolik toleransi
}

# Interaktiv (klik qilinadigan) element turlari
INTERACTIVE_TYPES = ("button", "toggle", "input")


# ---------------------------------------------------------------------- #
# UI karta reestri: spec -> composition cards
# ---------------------------------------------------------------------- #

def spec_to_cards(spec: dict) -> CardRegistry:
    """UI spec'dagi har qavatni composite card, har elementni atomic card qiladi.

    UCC asosiy g'oyasi: spec'ning har 'stage'i = bitta composite (qavat),
    har element = atomic (g'isht). Shunda composition engine:
      - qatlamlarni topadi (barg->ildiz)
      - exec_order (puzzle tartibi) beradi
      - overlap/chegara tekshiruvlarini o'tkazadi
    """
    reg = CardRegistry()
    stages = spec.get("stages") or []
    # Ildiz karta: butun app
    root_comps = [Component(ref=f"stage:{st.get('id', i)}", qty=1)
                  for i, st in enumerate(stages)]
    reg.add(ItemCard(
        id="app",
        kind="composite",
        name=spec.get("app", "app"),
        attrs={"canvas": spec.get("canvas", {}), "theme": spec.get("theme", "dark")},
        components=root_comps,
    ))
    for i, st in enumerate(stages):
        sid = f"stage:{st.get('id', i)}"
        els = st.get("elements") or []
        reg.add(ItemCard(
            id=sid,
            kind="composite",
            name=st.get("title", sid),
            attrs={"title": st.get("title", ""), "stage_idx": i},
            components=[Component(ref=f"el:{sid}:{j}", qty=1)
                        for j in range(len(els))],
        ))
        for j, el in enumerate(els):
            reg.add(ItemCard(
                id=f"el:{sid}:{j}",
                kind="atomic",
                name=el.get("type", "el"),
                attrs={
                    "type": el.get("type", "rect"),
                    "x": el.get("x", 0),
                    "y": el.get("y", 0),
                    "w": el.get("w", 0),
                    "h": el.get("h", 0),
                    "id": el.get("id", ""),
                    "parent": el.get("parent", ""),
                    "fill": el.get("fill", ""),
                    "interactive": el.get("type", "") in INTERACTIVE_TYPES,
                },
            ))
    return reg


# ---------------------------------------------------------------------- #
# Overlap detektori — qavatlar va bosh menyu xalaqit qilmasligi
# ---------------------------------------------------------------------- #

def _intersects(a: dict, b: dict, tol: int = 1) -> bool:
    ax1, ay1 = a["x"], a["y"]
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx1, by1 = b["x"], b["y"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    return not (ax2 <= bx1 + tol or bx2 <= ax1 + tol or
                ay2 <= by1 + tol or by2 <= ay1 + tol)


def _contains(a: dict, b: dict, tol: int = 1) -> bool:
    """a butunlay b ni ichiga oladimi? (ichma-ich joylashuv — normal kompozitsiya)."""
    return (a["x"] <= b["x"] + tol and a["y"] <= b["y"] + tol and
            a["x"] + a["w"] >= b["x"] + b["w"] - tol and
            a["y"] + a["h"] >= b["y"] + b["h"] - tol)


def _genuine_overlap(a: dict, b: dict, tol: int = 1) -> bool:
    """Haqiqiy xalaqit: qoplanish bor, lekin ichma-ich EMAS.

    Karta ichidagi matn (containment) — normal dizayn, xalaqit emas.
    Ikkala yo'nalishda ham to'liq ichma-ich bo'lmasa va qoplanish bo'lsa —
    elementlar bir-biriga xalaqit qilmoqda.
    """
    if not _intersects(a, b, tol):
        return False
    if _contains(a, b, tol) or _contains(b, a, tol):
        return False
    return True


def _absolute_positions(spec: dict) -> tuple[dict[str, dict], dict[str, str]]:
    """Har elementning MUTLAQ koordinatasini hisoblaydi (parent zanjiri bo'ylab).

    ui_builder reparent qilgan elementlar ota-ga nisbatan koordinatada
    (masalan sidebar ichidagi nav — sidebar (0,64) ga nisbatan). Overlap
    tekshiruvi to'g'ri bo'lishi uchun barcha elementlarni absolute joyiga
    ko'chiramiz.

    Return: ({id_or_index: {x,y,w,h,type,stage}}, {id: parent_id})
    """
    by_id: dict[str, dict] = {}
    parents: dict[str, str] = {}
    for st in spec.get("stages") or []:
        sid = st.get("id", "")
        for i, el in enumerate(st.get("elements") or []):
            key = el.get("id") or f"{sid}:{i}"
            pid = el.get("parent") or ""
            by_id[key] = {
                "x": el.get("x", 0), "y": el.get("y", 0),
                "w": el.get("w", 0), "h": el.get("h", 0),
                "type": el.get("type"), "stage": sid,
            }
            if pid:
                parents[key] = pid

    def resolve(key: str, seen: Optional[set] = None) -> dict:
        seen = seen or set()
        if key in seen:
            return dict(by_id.get(key, {}))
        seen = seen | {key}
        el = dict(by_id.get(key, {}))
        pid = parents.get(key)
        if pid and pid in by_id:
            p = resolve(pid, seen)
            el["x"] = el.get("x", 0) + p.get("x", 0)
            el["y"] = el.get("y", 0) + p.get("y", 0)
        return el

    resolved: dict[str, dict] = {}
    for key in by_id:
        resolved[key] = resolve(key)
    return resolved, parents


def check_overlaps(spec: dict) -> list[dict]:
    """Elementlar orasidagi haqiqiy xalaqitlarni topadi (absolute koordinatada).

    Qoidalar:
      - ichma-ich joylashuv (containment) — normal kompozitsiya, xalaqit EMAS
      - bitta qavat ichidagi elementlar o'zaro qoplanishsa — WARNING
      - navigatsiya (bosh menyu) bilan kontent qavati qoplanishsa — ERROR

    Return: [{"stage_a", "stage_b", "el_a", "el_b", "severity", "msg"}]
    """
    issues: list[dict] = []
    resolved, _ = _absolute_positions(spec)
    keys = list(resolved.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            ka, kb = keys[i], keys[j]
            a, b = resolved[ka], resolved[kb]
            if a["stage"] != b["stage"]:
                # turli qavatlar orasidagi qoplanish — qavatlararo xalaqit
                if a["stage"].startswith("content") and "nav" in b["stage"] \
                        or b["stage"].startswith("content") and "nav" in a["stage"]:
                    if _genuine_overlap(a, b, UI_STANDARDS["overlap_tolerance"]):
                        issues.append({
                            "stage_a": a["stage"], "stage_b": b["stage"],
                            "el_a": {"type": a.get("type"), "x": a.get("x"),
                                     "y": a.get("y"), "w": a.get("w"), "h": a.get("h")},
                            "el_b": {"type": b.get("type"), "x": b.get("x"),
                                     "y": b.get("y"), "w": b.get("w"), "h": b.get("h")},
                            "severity": "error",
                            "msg": f"bosh menyu kontentga xalaqit qilmoqda: "
                                   f"{b.get('type')}@{b.get('x')},{b.get('y')} "
                                   f"vs {a.get('type')}@{a.get('x')},{a.get('y')}",
                        })
                continue
            if not _genuine_overlap(a, b, UI_STANDARDS["overlap_tolerance"]):
                continue
            severity = "error" if "nav" in a["stage"] or "menu" in a["stage"] \
                else "warning"
            issues.append({
                "stage_a": a["stage"],
                "stage_b": b["stage"],
                "el_a": {"type": a.get("type"), "x": a.get("x"),
                         "y": a.get("y"), "w": a.get("w"), "h": a.get("h")},
                "el_b": {"type": b.get("type"), "x": b.get("x"),
                         "y": b.get("y"), "w": b.get("w"), "h": b.get("h")},
                "severity": severity,
                "msg": f"[{a['stage']}] {a.get('type')} va {b.get('type')} qoplanishi "
                       f"({a.get('x')},{a.get('y')}) <-> ({b.get('x')},{b.get('y')})",
            })
    return issues


# ---------------------------------------------------------------------- #
# Chegara / o'lcham tekshiruvi (standartlar)
# ---------------------------------------------------------------------- #

def check_bounds(spec: dict) -> list[str]:
    """Har element canvas ichida ekanini va minimal o'lchamga yetishini tekshiradi.

    Parent ichidagi (reparent qilingan) elementlar MUTLAQ koordinatada
    tekshiriladi — check_overlaps bilan bir xil asos (nomuvofiqlik yo'q).
    """
    warnings: list[str] = []
    canvas = spec.get("canvas") or {"w": 960, "h": 640}
    cw, ch = canvas.get("w", 960), canvas.get("h", 640)
    resolved, _ = _absolute_positions(spec)
    for key, el in resolved.items():
        x, y, w, h = el.get("x", 0), el.get("y", 0), el.get("w", 0), el.get("h", 0)
        if x < 0 or y < 0 or x + w > cw or y + h > ch:
            warnings.append(
                f"[{el.get('stage')}] {el.get('type')} canvas chegarasidan chiqdi "
                f"({x},{y},{w},{h}) canvas={cw}x{ch}")
            continue
        # Turli turlar uchun minimal o'lchamlar (nozik chiziq/diagramma
        # barlari, modal tutqichlari alohida ruxsat oladi)
        t = el.get("type")
        min_h = {"bar": 4, "text": 6, "rect": 6}.get(t, UI_STANDARDS["min_el_h"])
        min_w = UI_STANDARDS["min_el_w"] if t != "bar" else 4
        # qisqa nozik chiziqlar / tutqichlar (h<=6 yoki w<=6) — ruxsat
        if w <= 6 or h <= 6:
            continue
        if 0 < w < min_w or 0 < h < min_h:
            warnings.append(
                f"[{el.get('stage')}] {el.get('type')} juda kichik ({w}x{h})")
    return warnings


# ---------------------------------------------------------------------- #
# Brick (g'isht) tahlili — bir xil elementlar qayta ishlatilishi
# ---------------------------------------------------------------------- #

def brick_stats(spec: dict) -> dict:
    """Bir xil (type + o'lcham + to'ldiruvchi) elementlarni guruhlaydi.

    'Agar g'isht mavjud bo'lsa tanlanadi' — bir xil ko'rinishdagi elementlar
    bitta brick turi sifatida qayta ishlatiladi.
    """
    from collections import Counter
    counter: Counter = Counter()
    for st in spec.get("stages") or []:
        for el in (st.get("elements") or []):
            key = (el.get("type"), round(el.get("w", 0) / 10),
                   round(el.get("h", 0) / 10), el.get("fill", ""))
            counter[key] += 1
    total = sum(counter.values())
    reused = sum(1 for k, v in counter.items() if v > 1)
    top = counter.most_common(6)
    return {
        "total_elements": total,
        "unique_bricks": len(counter),
        "reusable_bricks": reused,
        "reuse_ratio": round(reused / total, 3) if total else 0,
        "top_bricks": [
            {"type": k[0], "w": k[1] * 10, "h": k[2] * 10, "fill": k[3], "count": v}
            for k, v in top
        ],
    }


# ---------------------------------------------------------------------- #
# Universal kompozitsiya rejasi (PLAN -> JOYLASHTIRISH -> YIG'ISH)
# ---------------------------------------------------------------------- #

def compose_ui(spec: dict) -> dict:
    """UI spec -> universal qurilish rejasi (plan + layers + exec_order).

    Qadamlari:
      1. spec -> cards (qavat = composite, element = atomic)
      2. composition engine: validate, layers (barg->ildiz), exec_order
      3. overlap + bounds + brick tahlillari
      4. Yagona natija: frontend LIVE BUILD puzzle tartibi uchun tayyor

    Return: {ok, errors, layers, exec_order, explosion, overlaps, bounds,
             bricks, stage_plan}
    """
    reg = spec_to_cards(spec)
    engine = CompositionEngine(reg)
    goal = "app"
    # Dedup: qatlamlar / exec_order / explosion BIR joyda hisoblanadi —
    # CompositionEngine.build_plan() (bu yerda qayta hisoblanmaydi).
    plan = engine.build_plan(goal, 1)
    if plan.get("errors"):
        return {"ok": False, "errors": plan["errors"][:8], "engine": "uic-compose"}
    layers = plan["layers"]
    exec_order = plan["exec_order"]

    # Qavat rejasi: har stage uchun elementlar tartibi
    stages = spec.get("stages") or []
    stage_plan: list[dict] = []
    for i, st in enumerate(stages):
        sid = f"stage:{st.get('id', i)}"
        els = st.get("elements") or []
        stage_plan.append({
            "stage": st.get("id"),
            "title": st.get("title"),
            "element_count": len(els),
            "start_exec": exec_order.index(f"el:{sid}:0") if els else -1,
            "end_exec": exec_order.index(f"el:{sid}:{len(els)-1}") if els else -1,
        })

    overlaps = check_overlaps(spec)
    bounds = check_bounds(spec)
    bricks = brick_stats(spec)

    return {
        "ok": True,
        "engine": "uic-compose",
        "errors": [],
        "canvas": spec.get("canvas", {}),
        "layers": layers,                 # barglar -> ildiz (puzzle qatlamlari)
        "exec_order": exec_order,         # to'liq yig'ish tartibi
        "stage_plan": stage_plan,         # har qavat elementlari soni + tartibi
        "explosion": plan["explosion"],
        "overlaps": overlaps,             # xalaqit tekshiruvi
        "bounds": bounds,                 # chegara standartlari
        "bricks": bricks,                 # g'isht qayta ishlatish
        "issues_total": len(overlaps) + len(bounds),
    }


def compose_app(app: str, theme: str = "dark") -> dict:
    """App nomi -> build_spec + compose_ui (bitta chaqiruvda)."""
    from mcp_servers.ui_builder import build_spec
    spec = build_spec(app, theme)
    plan = compose_ui(spec)
    plan["spec"] = spec
    return plan


# ---------------------------------------------------------------------- #
# CLI tekshiruvi: python ui_compose.py
# ---------------------------------------------------------------------- #

def main() -> int:
    plan = compose_app("dashboard")
    print(f"ok={plan['ok']}  layers={len(plan['layers'])}  "
          f"exec_order={len(plan['exec_order'])}  issues={plan['issues_total']}")
    print("overlaps:", [o["msg"] for o in plan["overlaps"]][:4])
    print("bounds:", plan["bounds"][:4])
    print("bricks:", plan["bricks"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
