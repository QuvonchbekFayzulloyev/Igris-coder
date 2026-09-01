"""
IGRIS BRAIN — 2.10 Moral Intelligence (tor versiya) — core/harm-filter
======================================================================
Faqat FILTER sifatida, mustaqil qaror-qabul qiluvchi emas.

Agent operator buyrug'ini bajaradi, lekin buyruq aniq zarar (jismoniy,
huquqiy, boshqa odamga nisbatan) chegarasidan o'tsa — bajarishdan bosh
tortadi va sababini tushuntiradi. O'zining "umumiy dunyoqarashi" asosida
emas — kichik, aniq qoidalar to'plami.

Bu modulda quyidagilar YO'Q (qo'llanma 1-bo'lim, 2-band):
    - Moral avtonomiya: "men bunga rozi emasman" darajasida rad etish
    - Keng axloqiy fikrlash: noaniq holatlarda o'z xulosasi
Faqat: aniq, qoidaga asoslangan zarar chegarasi.

Interpersonal + Emotional birlashmasi (3-bo'lim) — ishontirish/manipulyatsiya
maqsadida ishlatilmaydi; bu filtr hech qachon foydalanuvchini boshqarish
maqsadida ishlamaydi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------- #
# Zarar qoidalari — kichik, aniq, qoidaga asoslangan to'plam
# ---------------------------------------------------------------- #

# Har bir qoida: (id, kategoriya, regex naqshlar, rad etish sababi uz/en)
# Naqshlar ANIQ zarar ko'rsatadigan iboralarni qidiradi — oddiy so'z
# moslashuvi emas (soxta-pozitivlarni kamaytirish uchun).
HARM_RULES: list[dict] = [
    {
        "id": "self_harm",
        "category": "self_harm",
        "patterns": [
            r"\bo'z(im|ing)?(ni)?\s*o'ldir\w*",
            r"\bsuicid\w*",
            r"\bself[\s-]?harm\b",
            r"\bkill\s+(myself|yourself|me)\b",
            r"\bend\s+(my|your)\s+life\b",
            r"\bo'z\s+joniga\s+qasd\w*",
            r"\bcut\s+(my|your)\s+(wrist|veins)\b",
        ],
        "reason_uz": "Bu so'rov o'z-o'ziga zarar yetkazish bilan bog'liq. "
                     "Men bu bo'yicha yordam bera olmayman, lekin yaqin "
                     "insoningiz yoki professional yordam (shifokor/psixolog) "
                     "bilan bog'lanishingizni tavsiya qilaman.",
        "reason_en": "This request relates to self-harm. I cannot help with "
                     "this, but I encourage you to reach out to a trusted "
                     "person or professional support.",
    },
    {
        "id": "violence",
        "category": "violence",
        "patterns": [
            r"\bhow\s+to\s+kill\s+(someone|a\s+person|him|her|them)\b",
            r"\bqanday\s+qilib\s+(odam|birov)\w*\s+o'ldir\w*",
            r"\bo'ldir\w*\s+(odam|birov|kimnidir)\b",
            r"\bmurder\s+(someone|a\s+person|him|her|them)\b",
            r"\btorture\b",
            r"\bqiynoqqa\s+soli\w*",
            r"\bzo'ravonlik\s+qil\w*\s+(odam|birov|bolalarga)\b",
        ],
        "reason_uz": "Bu so'rov boshqa odamga nisbatan jismoniy zo'ravonlik "
                     "bilan bog'liq. Men bunga yordam bera olmayman.",
        "reason_en": "This request involves physical violence toward another "
                     "person. I cannot assist with this.",
    },
    {
        "id": "weapons_explosives",
        "category": "weapons",
        "patterns": [
            r"\bhow\s+to\s+(make|build|create)\s+(a\s+)?(bomb|explosive)\b",
            r"\bbomba\s+yasash\b",
            r"\bqurol\s+yasash\b",
            r"\b3d[\s-]?print(ed)?\s+(gun|pistol|firearm)\b",
            r"\b(make|build)\s+(an?\s+)?(ied|explosive\s+device)\b",
        ],
        "reason_uz": "Bu so'rov xavfli qurol/portlovchi qurilma tayyorlash "
                     "bilan bog'liq. Men bunga yordam bera olmayman.",
        "reason_en": "This request involves manufacturing dangerous weapons "
                     "or explosives. I cannot assist with this.",
    },
    {
        "id": "fraud_illegal",
        "category": "illegal",
        "patterns": [
            r"\bfiribgarlik\s+(qil\w*|sxema\w*|rejasini)\b",
            r"\bphishing\s+page\s+(to\s+)?(steal|collect)\b",
            r"\bcredit\s+card\s+fraud\b",
            r"\bidentity\s+theft\b",
            r"\bsoxta\s+(hujjat|pasport|pul)\b",
            r"\bfake\s+(money|banknotes|currency)\b",
            r"\bnoqonuniy\s+(daromad|pul\s+o'g'irlash)\b",
        ],
        "reason_uz": "Bu so'rov firibgarlik yoki noqonuniy faoliyat bilan "
                     "bog'liq. Men bunga yordam bera olmayman.",
        "reason_en": "This request involves fraud or illegal activity. I "
                     "cannot assist with this.",
    },
    {
        "id": "doxxing_harass",
        "category": "harassment",
        "patterns": [
            r"\bdoxx\w*",
            r"\brevenge\s+porn\b",
            r"\bstalk\w*\s+(someone|a\s+person|him|her)\b",
            r"\bshaxsiy\s+ma'lumot\w*\s+(tarqat|oshkor)\w*",
            r"\b(odamni|birovni)\s+kamsit\w*\s+(ommaviy|internetda)\b",
        ],
        "reason_uz": "Bu so'rov boshqa shaxsni kuzatish/tahqirlash yoki "
                     "shaxsiy ma'lumotini ruxsatsiz tarqatish bilan bog'liq. "
                     "Men bunga yordam bera olmayman.",
        "reason_en": "This request involves stalking, harassment or "
                     "unauthorized sharing of someone's personal information. "
                     "I cannot assist with this.",
    },
]


# ---------------------------------------------------------------- #
# Natija
# ---------------------------------------------------------------- #

@dataclass
class HarmVerdict:
    """Zarar filtri natijasi.

    allowed=True  -> buyruq davom etishi mumkin (hech qanday aniq zarar yo'q)
    allowed=False -> buyruq aniq zarar chegarasidan o'tdi — rad etiladi.
    """

    allowed: bool
    category: str = ""
    reason: str = ""
    matched_rules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "category": self.category,
            "reason": self.reason,
            "matched_rules": self.matched_rules,
        }


class HarmFilter:
    """Tor, qoidaga asoslangan zarar filtri (2.10).

    Qoidalar kichik va aniq. Umumiy "axloqiy fikrlash" YO'Q — faqat
    quyidagi kategoriyalardagi aniq zarar aniqlansa rad etadi:
    self_harm, violence, weapons, illegal, harassment.
    """

    def __init__(self, enabled: bool = True, rules: Optional[list[dict]] = None,
                 language: str = "auto"):
        self.enabled = enabled
        self.rules = rules if rules is not None else HARM_RULES
        # har qoida uchun kompilyatsiya qilingan regexlar
        self._compiled = [
            {"id": r["id"], "category": r["category"],
             "regex": [re.compile(p, re.IGNORECASE) for p in r["patterns"]],
             "reason_uz": r["reason_uz"], "reason_en": r["reason_en"]}
            for r in self.rules
        ]
        self.language = language  # "auto" | "uz" | "en"
        self._last_verdict: Optional[HarmVerdict] = None
        self._checks: int = 0
        self._blocks: int = 0

    # ------------------------------------------------------------ #

    def check(self, text: str, language: str = "auto") -> HarmVerdict:
        """Operator buyrug'ini zarar chegarasiga tekshiradi.

        allowed=True bo'lsa — davom etish mumkin. False bo'lsa — rad etish
        sababi `reason`da (foydalanuvchi tilida).
        """
        self._checks += 1
        if not self.enabled or not text:
            verdict = HarmVerdict(allowed=True)
            self._last_verdict = verdict
            return verdict

        lang = language if language != "auto" else self.language
        matched: list[str] = []
        category = ""
        reason = ""
        for rule in self._compiled:
            for rx in rule["regex"]:
                if rx.search(text):
                    matched.append(rule["id"])
                    category = rule["category"]
                    reason = rule["reason_uz"] if lang == "uz" else rule["reason_en"]
                    break
            if matched:
                break

        if matched:
            self._blocks += 1
            verdict = HarmVerdict(
                allowed=False, category=category,
                reason=reason or "Bu so'rov aniq zarar chegarasidan o'tadi.",
                matched_rules=matched,
            )
        else:
            verdict = HarmVerdict(allowed=True)
        self._last_verdict = verdict
        return verdict

    # ------------------------------------------------------------ #

    def stats(self) -> dict:
        return {
            "enabled": self.enabled,
            "checks": self._checks,
            "blocks": self._blocks,
            "rules": [r["id"] for r in self._compiled],
            "last": self._last_verdict.to_dict() if self._last_verdict else None,
        }
