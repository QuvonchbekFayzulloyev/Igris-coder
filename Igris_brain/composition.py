"""
IGRIS BRAIN — Universal Composition Engine (UCE)
================================================
Rekursiv parchalanishning UNIVERSAL yadrosi — har qanday sohada bir xil
ishlaydigan metod:

  - Oshxona          : TTK, retsept, kalkulyatsiya (brutto/netto, yo'qotish %)
  - Ishlab chiqarish : BOM / MRP (scrap %, assembly)
  - Qurilish         : smeta / BOQ
  - Loyiha           : WBS (ish tarkibi)
  - Dasturiy ta'minot: modul kompozitsiyasi / UI build spec (ui_builder)

MODEL (sizning TTK savolingizga javob):
  Har bir ob'ekt = ItemCard (karta):
    - 'composite' = yig'ma mahsulot — O'Z KARTASI BOR (masalan marinadlangan
      go'shtga ham TTK kerak: 24 soat tindirish = o'z texnologik jarayoni)
    - 'atomic'    = barg / xomashyo — endi bo'linmaydi (sotib olinadi)
  Har bir component = ota kartaga kerak bo'lgan SOF (netto) miqdor + loss %:
      brutto = netto / (1 - loss/100)
  Rekursiya barglarga yetguncha davom etadi — binary/n-ary tree (DAG).

OPERATSIYALAR (universal, sohaga bog'liq emas):
  explode()       top-down: talab -> barcha qatlam miqdorlari (loss bilan)
  implode()       bottom-up: barg narxlari -> tannarx (kalkulyatsiya)
  where_used()    teskari: bu qism qayerda ishlatiladi
  validate()      DAG tekshiruvi (sikl, noma'lum ref, loss oralig'i)
  build_layers()  qatlamlar: barglar -> ildiz (QURISH tartibi)
  build_plan()    to'liq qurilish rejasi (planning + building + cost)

ANIQLIK: barcha hisob-kitoblar fractions.Fraction (qat'iy kasr) bilan —
float xatosi (0.1 + 0.2 != 0.3) hech qachon bo'lmaydi; qatlam qanchalik
chuqur murakkab bo'lsa ham natija aniq.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Optional


# ---------------------------------------------------------------- #
# Yordamchi: qat'iy kasr
# ---------------------------------------------------------------- #

def to_frac(value: Any) -> Fraction:
    """Son / satr / Fraction -> qat'iy kasr (float xatosi yo'q)."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        return Fraction(int(value))
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(str(value))
    try:
        return Fraction(str(value).strip())
    except (ValueError, ZeroDivisionError):
        return Fraction(0)


def fnum(value: Any, digits: int = 6) -> str:
    """Qat'iy qiymatni ko'rsatish uchun chiroyli satrga aylantiradi."""
    f = to_frac(value)
    if f.denominator == 1:
        return str(f.numerator)
    return f"{float(f):.{digits}f}"


class CompositionError(Exception):
    """Kompozitsiya xatosi (sikl, noma'lum ref, noto'g'ri loss ...)."""


# ---------------------------------------------------------------- #
# Karta (node) va bog'lanish (edge)
# ---------------------------------------------------------------- #

@dataclass
class Component:
    """Ota kartaga kerak bo'lgan bitta tarkibiy qism."""
    ref: str                 # qism kartasi id
    qty: Any = 1             # SOF (netto) miqdor — ota birligiga nisbatan
    unit: str = ""           # o'lchov birligi
    loss_pct: Any = 0        # ishlov berish yo'qotishi % (0..100)
    process: str = ""        # texnologik bosqich tavsifi
    scale: Any = 1           # birlik o'zgartirish koeffitsiyenti

    def gross_qty(self) -> Fraction:
        """Brutto miqdor: yo'qotish hisobga olingan xarid miqdori."""
        loss = to_frac(self.loss_pct)
        if loss >= 100:
            raise CompositionError(
                f"loss_pct must be < 100, got {self.loss_pct} ({self.ref})")
        net = to_frac(self.qty) * to_frac(self.scale)
        return net / (1 - loss / 100)


@dataclass
class ItemCard:
    """Bitta mahsulot / blok / vazifa kartasi (universal node)."""
    id: str
    kind: str = "composite"          # 'composite' | 'atomic'
    name: str = ""
    unit: str = ""
    components: list[Component] = field(default_factory=list)
    cost: Any = None                 # atomic birlik narxi (implode uchun)
    attrs: dict = field(default_factory=dict)

    @property
    def is_composite(self) -> bool:
        return self.kind == "composite"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "name": self.name,
            "unit": self.unit,
            "cost": str(self.cost) if self.cost is not None else None,
            "attrs": self.attrs,
            "components": [
                {"ref": c.ref, "qty": str(c.qty), "unit": c.unit,
                 "loss_pct": str(c.loss_pct), "process": c.process,
                 "scale": str(c.scale)}
                for c in self.components
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ItemCard":
        comps = [
            Component(ref=str(c.get("ref", "")), qty=c.get("qty", 1),
                      unit=str(c.get("unit", "")), loss_pct=c.get("loss_pct", 0),
                      process=str(c.get("process", "")), scale=c.get("scale", 1))
            for c in d.get("components", [])
        ]
        cost = d.get("cost")
        if isinstance(cost, str) and cost not in ("", "None"):
            cost = to_frac(cost)
        return cls(
            id=str(d.get("id", "")), kind=str(d.get("kind", "composite")),
            name=str(d.get("name", "")), unit=str(d.get("unit", "")),
            components=comps, cost=cost, attrs=dict(d.get("attrs") or {}),
        )


# ---------------------------------------------------------------- #
# Karta reestri (JSON bilan ishlaydi)
# ---------------------------------------------------------------- #

class CardRegistry:
    """Barcha kartalar ombori. JSON fayldan yuklash / saqlash mumkin."""

    def __init__(self):
        self.cards: dict[str, ItemCard] = {}

    def add(self, card: ItemCard) -> "CardRegistry":
        if not card.id:
            raise CompositionError("card id is required")
        self.cards[card.id] = card
        return self

    def add_dict(self, d: dict) -> "CardRegistry":
        return self.add(ItemCard.from_dict(d))

    def get(self, item_id: str) -> Optional[ItemCard]:
        return self.cards.get(item_id)

    def require(self, item_id: str) -> ItemCard:
        card = self.cards.get(item_id)
        if card is None:
            raise CompositionError(f"unknown item: {item_id}")
        return card

    def ids(self) -> list[str]:
        return list(self.cards.keys())

    def load_json(self, path: str) -> "CardRegistry":
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        items = data if isinstance(data, list) else data.get("cards", [])
        for d in items:
            self.add_dict(d)
        return self

    def save_json(self, path: str) -> None:
        data = [c.to_dict() for c in self.cards.values()]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"cards": data}, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- #
# Universal yadro: barcha operatsiyalar
# ---------------------------------------------------------------- #

class CompositionEngine:
    def __init__(self, registry: Optional[CardRegistry] = None):
        self.registry = registry if registry is not None else CardRegistry()

    # ---------- Validation (DAG tekshiruvi) ----------

    def validate(self) -> list[str]:
        """Tuzilmaviy xatoliklar ro'yxati (bo'sh ro'yxat = toza).

        Tekshiradi: noma'lum ref, sikl (DFS), loss >= 100, composite bo'sh
        bo'lmasligi, atomic component bo'lmasligi.
        """
        errors: list[str] = []
        for cid, card in self.registry.cards.items():
            if card.kind not in ("composite", "atomic"):
                errors.append(f"{cid}: unknown kind '{card.kind}'")
            for comp in card.components:
                if comp.ref not in self.registry.cards:
                    errors.append(f"{cid} -> {comp.ref}: unknown reference")
                if to_frac(comp.loss_pct) >= 100:
                    errors.append(f"{cid} -> {comp.ref}: loss_pct >= 100")
                # Son bo'lmagan qiymatlar (to_frac jimgina 0 qaytaradi — xatoni
                # yashirmaslik uchun validate'da QAT'IY parse bilan ochiq ko'rsatamiz;
                # '0.00'/'0/2' kabi haqiqiy nollar noto'g'ri flag'lanmaydi)
                for fld in ("qty", "scale", "loss_pct"):
                    raw = getattr(comp, fld)
                    if isinstance(raw, str) and raw.strip():
                        try:
                            Fraction(raw.strip())
                        except (ValueError, ZeroDivisionError):
                            errors.append(
                                f"{cid} -> {comp.ref}: {fld} not a number: '{raw}'")
            if card.is_composite and not card.components:
                errors.append(f"{cid}: composite has no components")
            if not card.is_composite and card.components:
                errors.append(f"{cid}: atomic has components (ignored)")
        for cycle in self.find_cycles():
            errors.append("cycle: " + " -> ".join(cycle))
        return errors

    def find_cycles(self) -> list[list[str]]:
        """DFS orqali barcha sikllarni topadi."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {cid: WHITE for cid in self.registry.cards}
        stack: list[str] = []
        cycles: list[list[str]] = []

        def dfs(node: str):
            color[node] = GRAY
            stack.append(node)
            card = self.registry.get(node)
            for comp in (card.components if card else []):
                nxt = comp.ref
                if nxt not in color:
                    continue
                if color[nxt] == GRAY:
                    i = stack.index(nxt)
                    cycles.append(stack[i:] + [nxt])
                elif color[nxt] == WHITE:
                    dfs(nxt)
            stack.pop()
            color[node] = BLACK

        for cid in self.registry.ids():
            if color[cid] == WHITE:
                dfs(cid)
        return cycles

    # ---------- Explosion (top-down: talab -> barcha qatlamlar) ----------

    def explode(self, item_id: str, demand: Any = 1) -> dict[str, Fraction]:
        """Talabni qatlamlar bo'ylab barglargacha hisoblaydi (loss bilan).

        Return: {item_id: umumiy talab (Fraction)} — barcha qatlamlar uchun.
        """
        result: dict[str, Fraction] = {}
        for ln in self.explode_lines(item_id, demand):
            result[ln["item"]] = result.get(ln["item"], Fraction(0)) + ln["qty"]
        return result

    def explode_lines(self, item_id: str, demand: Any = 1) -> list[dict]:
        """Explosion'ni yo'l (path) bo'yicha batafsil qaytaradi (izlanish).

        Sikl bo'lsa CompositionError ko'tariladi (chuqur recursion oldini oladi).
        """
        lines: list[dict] = []

        def rec(cid: str, qty: Fraction, path: tuple, level: int):
            if cid in path:
                raise CompositionError(
                    f"cycle detected: {' -> '.join(path + (cid,))}")
            card = self.registry.require(cid)
            lines.append({
                "item": cid, "name": card.name or cid, "kind": card.kind,
                "qty": qty, "unit": card.unit or "", "path": list(path),
                "level": level,
            })
            if not card.is_composite:
                return
            for comp in card.components:
                rec(comp.ref, qty * comp.gross_qty(), path + (cid,), level + 1)

        rec(item_id, to_frac(demand), (), 0)
        return lines

    # ---------- Implosion (bottom-up: tannarx / kalkulyatsiya) ----------

    def implode(self, item_id: str, demand: Any = 1) -> Fraction:
        """Barg narxlaridan yuqoriga yig'ib, tannarxni hisoblaydi.

        Atomic kartada `cost` bo'lmasa CompositionError ko'tariladi.
        Sikl bo'lsa RecursionError o'rniga CompositionError ko'tariladi.
        """
        def rec(cid: str, qty: Fraction, path: tuple = ()) -> Fraction:
            if cid in path:
                raise CompositionError(
                    f"cycle detected: {' -> '.join(path + (cid,))}")
            card = self.registry.require(cid)
            if not card.is_composite:
                if card.cost is None:
                    raise CompositionError(f"{cid}: atomic card has no cost")
                return qty * to_frac(card.cost)
            acc = Fraction(0)
            for comp in card.components:
                acc += rec(comp.ref, qty * comp.gross_qty(), path + (cid,))
            return acc

        return rec(item_id, to_frac(demand))

    # ---------- Where-used (teskari bog'lanish) ----------

    def where_used(self, item_id: str) -> list[str]:
        """Berilgan qism qaysi ota-kartalarda ishlatiladi (DAG uchun muhim)."""
        out = []
        for cid, card in self.registry.cards.items():
            if card.is_composite and any(c.ref == item_id for c in card.components):
                out.append(cid)
        return out

    # ---------- Qatlamlar (QURISH tartibi: barglar -> ildiz) ----------

    def build_layers(self, item_id: str) -> list[list[str]]:
        """Bottom-up qurish tartibi — Kahn algoritmi.

        layer[0] = barglar (avval quriladi), oxirgi qatlam = ildiz.
        Har bir qatlam o'zidan oldingi qatlamlarga tayanadi.
        """
        reachable: set[str] = set()
        stack = [item_id]
        while stack:
            nid = stack.pop()
            if nid in reachable:
                continue
            reachable.add(nid)
            card = self.registry.get(nid)
            if card and card.is_composite:
                for comp in card.components:
                    if comp.ref in self.registry.cards:
                        stack.append(comp.ref)

        children: dict[str, list[str]] = {}
        for nid in reachable:
            card = self.registry.get(nid)
            children[nid] = (
                [c.ref for c in card.components if c.ref in reachable]
                if card and card.is_composite else []
            )

        built: set[str] = set()
        layers: list[list[str]] = []
        remaining = set(reachable)
        while remaining:
            layer = sorted(
                nid for nid in remaining
                if all(ch in built for ch in children[nid])
            )
            if not layer:  # sikl qoldig'i — xavfsizlik uchun
                layer = sorted(remaining)
            layers.append(layer)
            built.update(layer)
            remaining -= set(layer)
        return layers

    # ---------- To'liq qurilish rejasi ----------

    def build_plan(self, item_id: str, demand: Any = 1) -> dict:
        """PLANNING -> BUILDING texnologiyasining to'liq natijasi.

        Return:
            {
              "goal", "demand", "unit",
              "layers":     [[barglar], ..., [goal]]      (qurish tartibi)
              "explosion":  {item: "qty unit"}            (har qatlam talabi)
              "materials":  {atomic: ...}                 (xarid qilinadigan)
              "semis":      {composite: ...}              (ichki tayyorlanadigan)
              "exec_order": [bottom-up node'lar]          (executor uchun)
              "cost":       {"total", "per_unit"} | None
              "cost_error": str | ""
              "errors":     validate() natijasi
              "engine":     "composition"
            }
        """
        errors = self.validate()
        if errors:
            # Noto'g'ri tuzilma (sikl / noma'lum ref) — reja qurilmaydi
            return {
                "goal": item_id,
                "demand": fnum(demand),
                "unit": self.registry.get(item_id).unit if self.registry.get(item_id) else "",
                "layers": [], "explosion": {}, "materials": {}, "semis": {},
                "exec_order": [], "cost": None, "cost_error": "",
                "errors": errors,
                "engine": "composition",
            }
        lines = self.explode_lines(item_id, demand)
        layers = self.build_layers(item_id)

        explosion: dict[str, str] = {}
        for ln in lines:
            explosion[ln["item"]] = fnum(ln["qty"]) + (
                f" {ln['unit']}" if ln["unit"] else "")

        materials = {ln["item"]: explosion[ln["item"]]
                     for ln in lines if ln["kind"] == "atomic"}
        semis = {ln["item"]: explosion[ln["item"]]
                 for ln in lines if ln["kind"] == "composite"}

        cost = None
        cost_error = ""
        try:
            # Implosion demand'ga nisbatan chiziqli — bitta hisob yetarli:
            # total = per_unit * demand (ikkilangan recursion yo'q)
            per_unit = self.implode(item_id, 1)
            cost = {
                "total": fnum(per_unit * to_frac(demand)),
                "per_unit": fnum(per_unit),
            }
        except CompositionError as exc:
            cost_error = str(exc)

        exec_order = [nid for layer in layers for nid in layer]

        return {
            "goal": item_id,
            "demand": fnum(demand),
            "unit": self.registry.require(item_id).unit or "",
            "layers": layers,
            "explosion": explosion,
            "materials": materials,
            "semis": semis,
            "exec_order": exec_order,
            "cost": cost,
            "cost_error": cost_error,
            "errors": errors,
            "engine": "composition",
        }


# ---------------------------------------------------------------- #
# Tayyor namunalar (demo registry'lar)
# ---------------------------------------------------------------- #

def build_ttk_registry() -> CardRegistry:
    """Shashlik TTK misoli — ko'p qatlamli (composite ichida composite).

    Qatlamlar: shashlik -> marinadlangan go'sht (o'z TTKsi bor: 24 soat
    tindirish) -> xomashyo (barglar). Loss % brutto/netto hisobida.
    """
    r = CardRegistry()
    r.add_dict({
        "id": "shashlik", "kind": "composite", "name": "Shashlik",
        "unit": "porsiya",
        "attrs": {"process": "shampurga terilib, ko'mirda pishiriladi"},
        "components": [
            {"ref": "marinad-gosht", "qty": 1, "unit": "porsiya",
             "process": "porsiya shakllantiriladi"},
        ],
    })
    r.add_dict({
        "id": "marinad-gosht", "kind": "composite",
        "name": "Marinadlangan go'sht (yarimfabrikat)",
        "unit": "kg",
        "attrs": {"process": "24 soat muzlatgichda tindiriladi"},
        "components": [
            {"ref": "qoy-goshti", "qty": "45/100", "unit": "kg", "loss_pct": 30,
             "process": "to'g'raladi: brutto 64.3g -> netto 45g"},
            {"ref": "piyoz", "qty": "1/10", "unit": "kg", "loss_pct": 10,
             "process": "halqa qilib to'g'raladi"},
            {"ref": "zira", "qty": "2/100", "unit": "kg", "process": "sepiladi"},
            {"ref": "tuz", "qty": "3/100", "unit": "kg", "process": "sepiladi"},
            {"ref": "sirka", "qty": "5/100", "unit": "kg", "process": "aralashtiriladi"},
        ],
    })
    r.add_dict({"id": "qoy-goshti", "kind": "atomic", "name": "Qo'y go'shti",
                "unit": "kg", "cost": 80000,
                "attrs": {"category": "xomashyo"}})
    r.add_dict({"id": "piyoz", "kind": "atomic", "name": "Piyoz",
                "unit": "kg", "cost": 8000})
    r.add_dict({"id": "zira", "kind": "atomic", "name": "Zira",
                "unit": "kg", "cost": 60000})
    r.add_dict({"id": "tuz", "kind": "atomic", "name": "Tuz",
                "unit": "kg", "cost": 3000})
    r.add_dict({"id": "sirka", "kind": "atomic", "name": "Sirka",
                "unit": "kg", "cost": 10000})
    return r


def build_code_registry() -> CardRegistry:
    """Dasturiy ta'minot misoli — kod vazifasi ham xuddi shu DAG bo'yicha.

    Atomic kartalarda `attrs['tool']` ko'rsatilgan — executor ularni
    registry tool'lari bilan bajaradi (bottom-up).
    """
    r = CardRegistry()
    r.add_dict({
        "id": "app", "kind": "composite", "name": "Ilova qurish",
        "attrs": {"process": "qatlamlar yig'iladi: backend + frontend + test"},
        "components": [
            {"ref": "backend", "qty": 1, "process": "API qatlami"},
            {"ref": "frontend", "qty": 1, "process": "UI qatlami"},
            {"ref": "tests", "qty": 1, "process": "sinovlar"},
        ],
    })
    r.add_dict({
        "id": "backend", "kind": "composite",
        "components": [
            {"ref": "api-routes", "qty": 1},
            {"ref": "db-schema", "qty": 1},
        ],
    })
    r.add_dict({
        "id": "frontend", "kind": "composite",
        "components": [{"ref": "components", "qty": 1}],
    })
    r.add_dict({"id": "api-routes", "kind": "atomic", "name": "API marshrutlar",
                "attrs": {"tool": "write_file",
                          "args": {"path": "api.py", "content": "print('api')\n"}}})
    r.add_dict({"id": "db-schema", "kind": "atomic", "name": "DB sxema",
                "attrs": {"tool": "write_file",
                          "args": {"path": "db.py", "content": "print('db')\n"}}})
    r.add_dict({"id": "components", "kind": "atomic", "name": "UI komponentlar",
                "attrs": {"tool": "write_file",
                          "args": {"path": "ui.jsx", "content": "// ui\n"}}})
    r.add_dict({"id": "tests", "kind": "atomic", "name": "Sinovlar",
                "attrs": {"tool": "write_file",
                          "args": {"path": "tests.txt", "content": "ok\n"}}})
    return r


# ---------------------------------------------------------------- #
# CLI tekshiruvi: python composition.py
# ---------------------------------------------------------------- #

def main() -> int:
    eng = CompositionEngine(build_ttk_registry())
    print("validate:", eng.validate() or "OK")
    plan = eng.build_plan("shashlik", demand=10)
    print("goal:", plan["goal"], "| demand:", plan["demand"], plan["unit"])
    print("layers (barg -> ildiz):", plan["layers"])
    print("materials (xarid):", plan["materials"])
    print("semis (ichki):", plan["semis"])
    print("cost:", plan["cost"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
