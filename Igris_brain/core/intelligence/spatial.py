"""
IGRIS BRAIN — 2.4 Spatial Intelligence — core/spatial
======================================================
Joylashuv, layout, 2D/3D munosabatlarni tushunish.

Bu `interface-designer` skill'idagi layer/region inventarizatsiyasining
umumlashtirilgan modeli — UI, fayl tuzilishi (va hatto abstrakt grafik
strukturalar) uchun bir xil abstraksiya.

Foydalanish: agent UI spec / fayl daraxti / layout ma'lumotini tahlil
qilganda spatial modul ishlatiladi. Faqat tahlil — ijro operator
nazoratida (qo'llanma 2.4-band).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Region:
    """Fazoviy hudud (region) — UI yoki strukturaning bir qismi."""

    id: str
    label: str = ""
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    layer: int = 0
    children: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label,
            "x": self.x, "y": self.y, "w": self.w, "h": self.h,
            "layer": self.layer, "children": list(self.children),
        }


def _overlap(a: Region, b: Region) -> bool:
    """Ikki region qoplashadimi (2D AABB)."""
    return not (
        a.x + a.w <= b.x or b.x + b.w <= a.x or
        a.y + a.h <= b.y or b.y + b.h <= a.y
    )


class SpatialReasoner:
    """2.4 Umumiy fazoviy-reasoning modeli.

    Usullar:
      - analyze_layout(regions)  -> qatlamlar, qoplashlar, hududlar
      - analyze_file_tree(paths) -> fayl struktura tahlili (qatlam/depth)
    """

    def __init__(self):
        self._analyses: int = 0

    # ------------------------------------------------------------ #
    # UI / layout tahlili
    # ------------------------------------------------------------ #

    def analyze_layout(self, regions: list[dict]) -> dict:
        """Regionlar ro'yxatini tahlil qiladi.

        Kirish: [{id, label?, x, y, w, h, layer?}]
        Chiqish: qatlamlar (by layer), qoplash juftlari, hudud indeksi.
        """
        self._analyses += 1
        objs: list[Region] = []
        for i, r in enumerate(regions or []):
            if not isinstance(r, dict):
                continue
            objs.append(Region(
                id=str(r.get("id") or f"r{i}"),
                label=str(r.get("label") or r.get("id") or f"r{i}"),
                x=float(r.get("x", 0)), y=float(r.get("y", 0)),
                w=float(r.get("w", 0)), h=float(r.get("h", 0)),
                layer=int(r.get("layer", 0)),
            ))

        # 1. Qatlamlar (z-index bo'yicha guruhlash)
        layers: dict[int, list[str]] = {}
        for o in objs:
            layers.setdefault(o.layer, []).append(o.id)

        # 2. Qoplash juftlari (overlap) — layout muammosini aniqlash
        overlaps: list[dict] = []
        for i in range(len(objs)):
            for j in range(i + 1, len(objs)):
                if _overlap(objs[i], objs[j]):
                    overlaps.append({
                        "a": objs[i].id, "b": objs[j].id,
                        "layer_a": objs[i].layer, "layer_b": objs[j].layer,
                    })

        # 3. Hudud indeksi — jadval ko'rinishida tez qidiruv
        index = {o.id: o.to_dict() for o in objs}

        return {
            "count": len(objs),
            "layers": {str(k): v for k, v in sorted(layers.items())},
            "overlaps": overlaps,
            "overlap_count": len(overlaps),
            "index": index,
        }

    # ------------------------------------------------------------ #
    # Fayl struktura tahlili (fazoviy: chuqurlik/hierarchiya)
    # ------------------------------------------------------------ #

    def analyze_file_tree(self, paths: list[str]) -> dict:
        """Fayl yo'llari ro'yxatidan daraxt tahlili.

        Chiqish: max_depth, har bir chuqurlikdagi elementlar soni,
        katalog/yo'l guruhlari.
        """
        self._analyses += 1
        depth_count: dict[int, int] = {}
        dirs: set[str] = set()
        files: list[str] = []
        max_depth = 0

        for p in (paths or []):
            p = str(p).replace("\\", "/")
            parts = [x for x in p.split("/") if x]
            depth = len(parts)
            max_depth = max(max_depth, depth)
            depth_count[depth] = depth_count.get(depth, 0) + 1
            if len(parts) > 1:
                dirs.add("/".join(parts[:-1]))
            if parts:
                files.append(parts[-1])

        return {
            "entries": len(paths or []),
            "max_depth": max_depth,
            "depth_distribution": {str(k): v for k, v in sorted(depth_count.items())},
            "directories": sorted(dirs),
            "dir_count": len(dirs),
            "leaf_files": files,
        }

    # ------------------------------------------------------------ #

    def stats(self) -> dict:
        return {"analyses": self._analyses}
