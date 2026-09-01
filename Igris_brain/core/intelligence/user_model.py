"""
IGRIS BRAIN — 2.6 Interpersonal Intelligence — core/user-model
===============================================================
Foydalanuvchi niyati, ohangi, kontekstini o'qish.

Ruxsat etilgan doira: javobni foydalanuvchiga MOSLASHTIRISH (ton,
tafsilot darajasi, til). Qat'iy cheklov (qo'llanma 3-bo'lim):
    - "persuasion strategy" degan concept umuman YO'Q
    - foydalanuvchini boshqarish/ishontirish maqsadida emas
    - faqat javob sifatini o'zgartiradi, maqsadli natijani emas
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from core.intelligence.language import detect_language


# ---------------------------------------------------------------- #
# Foydalanuvchi profili
# ---------------------------------------------------------------- #

@dataclass
class UserProfile:
    """Foydalanuvchi haqida moslashtirish uchun xavfsiz kontekst."""

    language: str = "unknown"            # uz | en | unknown
    detail_level: str = "balanced"       # concise | balanced | detailed
    tone: str = "neutral"                # neutral | formal | casual
    expertise: str = "unknown"           # beginner | intermediate | expert | unknown
    preferences: dict = field(default_factory=dict)   # operator tomonidan qo'lda o'rnatiladigan
    _message_count: int = 0

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "detail_level": self.detail_level,
            "tone": self.tone,
            "expertise": self.expertise,
            "preferences": dict(self.preferences),
            "message_count": self._message_count,
        }


# Naqshlar — foydalanuvchi xabarlaridan signal yig'ish uchun
_DETAIL_CONCISE = re.compile(
    r"\b(qisqa|qisqacha|lo'nda|ixcham|bitta\s+gap)\b|"
    r"\b(short|brief|concise|tl;dr|quickly)\b", re.IGNORECASE)
_DETAIL_DETAILED = re.compile(
    r"\b(batafsil|to'liq|chuqur|har\s+bir\s+qadam|izohlab)\b|"
    r"\b(detailed|thorough|in\s+depth|step\s+by\s+step|explain)\b", re.IGNORECASE)
_EXPERT_BEGINNER = re.compile(
    r"\b(boshlang'ich|yangi\s+o'rgan|oddiy\s+tilda|sodda)\b|"
    r"\b(beginner|newbie|simple\s+terms|basic)\b", re.IGNORECASE)
_EXPERT_EXPERT = re.compile(
    r"\b(professional|ekspert|ilg'or|murakkab)\b|"
    r"\b(expert|advanced|senior|professional|complex)\b", re.IGNORECASE)
_TONE_FORMAL = re.compile(
    r"\b(rasmiy|adabiy|formal)\b|"
    r"\b(formal|professional\s+tone)\b", re.IGNORECASE)
_TONE_CASUAL = re.compile(
    r"\b(do'stona|erkin|norasmiy)\b|"
    r"\b(casual|friendly|informal|relaxed)\b", re.IGNORECASE)


class UserModel:
    """2.6 Foydalanuvchi modeli — faqat preferences/kontekst saqlaydi.

    Xavfsizlik chegaralari:
      - Faqat javob sifatini moslashtiradi (til, tafsilot, ohang).
      - Hech qachon "foydalanuvchini X qilishga ko'ndirish" maqsadini
        o'z ichiga olmaydi.
      - Profil operator tomonidan ko'rib chiqilishi mumkin (inspeksiya).
    """

    def __init__(self, profile_path: Optional[str] = None):
        self.profile = UserProfile()
        self.profile_path = profile_path
        self._lock = threading.RLock()
        self._load() if profile_path else None

    # ------------------------------------------------------------ #
    # Signallarni yig'ish (passiv — foydalanuvchi xabaridan o'rganish)
    # ------------------------------------------------------------ #

    def observe(self, message: str) -> dict:
        """Foydalanuvchi xabaridan profil signalini yig'adi.

        Bu faqat moslashtirish uchun — hech qanday maqsadli natijani
        optimallashtirmaydi.
        """
        if not message:
            return {}
        with self._lock:
            self.profile._message_count += 1
            updates: dict[str, str] = {}

            lang = detect_language(message)
            if lang != "unknown":
                # oldingi "unknown" bo'lsa yoki uz/en aniq bo'lsa yangilaymiz
                if self.profile.language == "unknown" or lang != self.profile.language:
                    self.profile.language = lang
                    updates["language"] = lang

            if _DETAIL_CONCISE.search(message):
                self.profile.detail_level = "concise"
                updates["detail_level"] = "concise"
            elif _DETAIL_DETAILED.search(message):
                self.profile.detail_level = "detailed"
                updates["detail_level"] = "detailed"

            if _EXPERT_BEGINNER.search(message):
                self.profile.expertise = "beginner"
                updates["expertise"] = "beginner"
            elif _EXPERT_EXPERT.search(message):
                self.profile.expertise = "expert"
                updates["expertise"] = "expert"

            if _TONE_FORMAL.search(message):
                self.profile.tone = "formal"
                updates["tone"] = "formal"
            elif _TONE_CASUAL.search(message):
                self.profile.tone = "casual"
                updates["tone"] = "casual"

            self._save()
            return updates

    def set_preference(self, key: str, value: str) -> None:
        """Operator tomonidan qo'lda o'rnatiladigan preference."""
        with self._lock:
            self.profile.preferences[str(key)] = str(value)
            self._save()

    # ------------------------------------------------------------ #
    # Promptni moslashtirish (faqat javob sifatiga ta'sir)
    # ------------------------------------------------------------ #

    def adaptation_directives(self) -> list[str]:
        """System prompt uchun moslashtirish direktivalari (inglizcha).

        Faqat NEUTRAL bo'lmagan/aniq bo'lgan xususiyatlar chiqariladi.
        Hech qachon maqsadli natijani o'zgartirish direktivasi YO'Q.
        """
        p = self.profile
        directives: list[str] = []

        if p.language == "uz":
            directives.append(
                "Respond in Uzbek (o'zbek tilida) unless the user writes in English."
            )
        elif p.language == "en":
            directives.append("Respond in English.")

        detail = p.preferences.get("detail", p.detail_level)
        if detail == "concise":
            directives.append(
                "Keep answers concise: short, direct, no filler."
            )
        elif detail == "detailed":
            directives.append(
                "Give thorough, detailed answers with explanations and examples."
            )

        if p.expertise == "beginner":
            directives.append(
                "User is a beginner: avoid heavy jargon, explain terms simply."
            )
        elif p.expertise == "expert":
            directives.append(
                "User is experienced: use precise technical language, skip basics."
            )

        tone = p.preferences.get("tone", p.tone)
        if tone == "formal":
            directives.append("Use a formal, professional tone.")
        elif tone == "casual":
            directives.append("Use a friendly, casual tone.")

        # Operator tomonidan qo'lda o'rnatilgan qo'shimcha preference'lar
        for k, v in p.preferences.items():
            if k in ("detail", "tone"):
                continue
            directives.append(f"User preference ({k}): {v}")

        return directives

    # ------------------------------------------------------------ #
    # Persist / load
    # ------------------------------------------------------------ #

    def _save(self):
        if not self.profile_path:
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.profile_path)),
                        exist_ok=True)
            with open(self.profile_path, "w", encoding="utf-8") as fh:
                json.dump(self.profile.to_dict(), fh, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _load(self):
        if not self.profile_path or not os.path.isfile(self.profile_path):
            return
        try:
            with open(self.profile_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self.profile.language = data.get("language", "unknown")
                self.profile.detail_level = data.get("detail_level", "balanced")
                self.profile.tone = data.get("tone", "neutral")
                self.profile.expertise = data.get("expertise", "unknown")
                self.profile.preferences = dict(data.get("preferences", {}))
                self.profile._message_count = int(data.get("message_count", 0))
        except (OSError, json.JSONDecodeError, ValueError):
            pass

    def reset(self) -> None:
        with self._lock:
            self.profile = UserProfile()
            self._save()

    # ------------------------------------------------------------ #

    def stats(self) -> dict:
        return self.profile.to_dict()
