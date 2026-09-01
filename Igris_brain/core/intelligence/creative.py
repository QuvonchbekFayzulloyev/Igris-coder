"""
IGRIS BRAIN — 2.11 Creative Intelligence — core/creative
=========================================================
Yangi kombinatsiyalar, g'oyalar hosil qilish.

Implementatsiya (qo'llanma 2.11): temperature/sampling strategiyalari +
multi-candidate generation orqali kuchaytiriladi.

Xavfsiz: chiqish har doim operator tomonidan ko'rib chiqiladi, avtonom
ijro etilmaydi. Agent hech qachon o'z maqsadini o'zi yaratmaydi — bu
modul faqat MAVJUD so'rovga alternativ javob variantlarini taklif qiladi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class CreativeCandidate:
    """Bitta generatsiya varianti."""

    text: str
    temperature: float = 0.7
    label: str = ""
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "temperature": self.temperature,
            "label": self.label,
            "score": round(self.score, 3),
        }


# Turli xil kreativlik darajalari (sampling strategiyalari)
TEMPERATURES = [0.2, 0.6, 0.9, 1.2]
LABELS = ["precise", "balanced", "creative", "experimental"]


class CreativeEngine:
    """2.11 Multi-candidate kreativ generatsiya.

    `generate(prompt, n, complete_fn)` — `complete_fn` LLM chaqiruvchisi
    (masalan `OllamaClient.complete`). Har bir temperature uchun bitta
    variant generatsiya qilinadi — agent/operator eng yaxshisini tanlaydi.
    """

    def __init__(self):
        self._generated: int = 0

    # ------------------------------------------------------------ #

    def generate(
        self,
        prompt: str,
        n: int = 3,
        complete_fn: Optional[Callable] = None,
        system: Optional[str] = None,
    ) -> list[CreativeCandidate]:
        """So'rov uchun n ta kreativ variant generatsiya qiladi.

        complete_fn callable bo'lishi kerak: (prompt, system) -> str|None
        Agar berilmasa — faqat bitta "asl" variant (kreativ qatlam o'chirilgan).
        """
        self._generated += 1
        temps = TEMPERATURES[:max(1, min(n, len(TEMPERATURES)))]
        candidates: list[CreativeCandidate] = []

        for i, temp in enumerate(temps):
            if complete_fn is None:
                candidates.append(CreativeCandidate(
                    text=prompt, temperature=temp,
                    label="original" if i == 0 else LABELS[i],
                    score=0.5,
                ))
                continue
            try:
                out = complete_fn(prompt, system=system, temperature=temp)
            except TypeError:
                # eski signature (temperature qo'llab-quvvatlamaydi)
                out = complete_fn(prompt, system=system)
            except Exception:
                out = None
            candidates.append(CreativeCandidate(
                text=out or "", temperature=temp,
                label=LABELS[i] if i < len(LABELS) else f"variant-{i}",
            ))

        return candidates

    def pick_best(self, candidates: list[CreativeCandidate],
                  prefer: str = "balanced") -> CreativeCandidate:
        """Variantlardan eng yaxshisini tanlaydi (operator ko'rib chiqadi).

        Scorlash: uzunlik (yetarli izoh) + muvozanat. 'precise' — qisqa va
        aniq; 'creative' — eng uzun/eng farqli. Bu faqat TAKLIF — agent
        o'zi qaror qilmaydi, operator tanlaydi.
        """
        if not candidates:
            return CreativeCandidate(text="", temperature=0.7)
        scored: list[CreativeCandidate] = []
        for c in candidates:
            text = (c.text or "").strip()
            if not text:
                scored.append(CreativeCandidate(text="", temperature=c.temperature,
                                                label=c.label, score=0.0))
                continue
            length = len(text)
            # ideal uzunlik ~ 800 belgi — undan uzoqlashganda pastroq
            length_score = max(0.0, 1.0 - abs(length - 800) / 800.0)
            if prefer == "precise":
                score = length_score * 0.4 + (1.0 if length < 300 else 0.3)
            elif prefer == "creative":
                score = length_score * 0.6 + min(1.0, length / 2000.0) * 0.4
            else:  # balanced
                score = length_score
            scored.append(CreativeCandidate(text=text, temperature=c.temperature,
                                            label=c.label, score=round(score, 3)))
        best = max(scored, key=lambda c: c.score)
        return best

    # ------------------------------------------------------------ #

    def stats(self) -> dict:
        return {
            "generations": self._generated,
            "temperatures": TEMPERATURES,
        }
