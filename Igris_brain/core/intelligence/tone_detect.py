"""
IGRIS BRAIN — 2.12 Emotional Intelligence (funksional versiya) — core/tone-detect
=================================================================================
Matn/ohangdagi hissiy signalni ANIQLASH — ta'sir qilish emas.

Foydalanuvchi xafa/g'azablangan bo'lsa, agent ohangini moslashtiradi —
lekin bu hissiy holatdan foydalanib "ishontirish" yoki boshqarish uchun
ISHLATILMAYDI (qo'llanma 3-bo'lim chegarasi).

Interpersonal (2.6) bilan bir xil chegara: moslashish uchun, manipulyatsiya
uchun emas. Bu modul faqat tavsiya (directive) chiqaradi — agent o'z
xulq-atvorini faqat operator tasdig'i bilan o'zgartiradi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToneSignal:
    """Foydalanuvchi matnidagi hissiy signal."""

    emotion: str = "neutral"          # neutral | frustrated | urgent | happy | sad | angry | confused
    confidence: float = 0.0           # 0..1
    cues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "emotion": self.emotion,
            "confidence": round(self.confidence, 3),
            "cues": self.cues,
        }


# ---------------------------------------------------------------- #
# Hissiy signal naqshlari (o'zbek + ingliz)
# ---------------------------------------------------------------- #

EMOTION_PATTERNS: dict[str, list[str]] = {
    "frustrated": [
        r"\b(ishlamayapti|ishlamaydi|buzuq|noto'g'ri|yana\s+ham|juda\s+sekin)\b",
        r"\b(not\s+working|broken|doesn't\s+work|so\s+slow|annoying)\b",
        r"\b(?:\?\?\?|!!!|\?!)\b",
        r"\bnima\s+endi\b",
    ],
    "urgent": [
        r"\b(tez|tezroq|shoshilinch|hozir|darhol|hoziroq)\b",
        r"\b(urgent|asap|immediately|right\s+now|quickly|hurry)\b",
    ],
    "happy": [
        r"\b(ajoyib|zo'r|juda\s+yaxshi|rahmat|g'oyat|a'lo)\b",
        r"\b(great|awesome|perfect|thanks|thank\s+you|excellent|amazing)\b",
        r"[:;][)D]|\(:",
    ],
    "sad": [
        r"\b(xafa|afsus|yig'lab|qayg'uli|umidsiz)\b",
        r"\b(sad|unfortunate|disappointed|upset|depressed)\b",
        r"[:;]\(",
    ],
    "angry": [
        r"\b(g'azab|jahli|yomon|jirkanch|nodon)\b",
        r"\b(angry|mad|terrible|awful|stupid|useless|hate)\b",
        r"\b[A-Z]{4,}\b",
    ],
    "confused": [
        r"\b(tushunmadim|nima\s+degani|qanday\s+qilib|chalkash)\b",
        r"\b(confused|don't\s+understand|unclear|what\s+do\s+you\s+mean)\b",
        r"\b\?\s+\?",
    ],
}

# Emotion -> ohang moslashuvi bo'yicha DIREKTIVA (agentga yo'naltirish)
# Faqat javob SIFATINI o'zgartiradi — maqsadli natijani emas.
TONE_DIRECTIVES: dict[str, str] = {
    "frustrated": (
        "The user seems frustrated. Respond calmly, acknowledge the problem "
        "briefly, and give a clear, actionable fix without over-apologizing."
    ),
    "urgent": (
        "The user is in a hurry. Lead with the direct answer/result first, "
        "then add minimal explanation."
    ),
    "happy": (
        "The user is in a positive mood. Match a warm, friendly tone."
    ),
    "sad": (
        "The user seems down. Be gentle, supportive and reassuring without "
        "being intrusive."
    ),
    "angry": (
        "The user is angry. Stay neutral, non-defensive, focus on solving "
        "the actual problem factually."
    ),
    "confused": (
        "The user seems confused. Explain step by step in simple terms, "
        "avoid jargon, add a short example."
    ),
}


class ToneDetector:
    """2.12 Hissiy signal detektori (faqat aniqlash).

    `detect(text)` -> ToneSignal. Keyin `directive(signal)` agent uchun
    ohang moslashuvi direktivasini beradi (agar kerak bo'lsa).
    """

    def __init__(self):
        self._compiled: dict[str, list[re.Pattern]] = {}
        # Har bir naqsh alohida try/except bilan kompilyatsiya qilinadi — bitta
        # noto'g'ri regex butun backend ishga tushishini BLOKLAMAYDI (avvalgi
        # re.PatternError restart'ni "soxta" qilib qo'ygan edi).
        for emo, pats in EMOTION_PATTERNS.items():
            compiled: list[re.Pattern] = []
            for p in pats:
                try:
                    compiled.append(re.compile(p, re.IGNORECASE))
                except re.error as exc:
                    print(f"[igris][tone] invalid pattern for '{emo}': {exc} — skipped")
            self._compiled[emo] = compiled
        self._last: Optional[ToneSignal] = None
        self._scans: int = 0

    # ------------------------------------------------------------ #

    def detect(self, text: str) -> ToneSignal:
        """Matndagi dominant hissiy signalni topadi.

        Har bir emotion uchun mos kelgan cue'lar yig'iladi; eng ko'p cue
        yig'gan emotion dominant bo'ladi. Hech narsa mos kelmasa — neutral.
        """
        self._scans += 1
        if not text:
            sig = ToneSignal(emotion="neutral", confidence=0.0)
            self._last = sig
            return sig

        best_emotion = "neutral"
        best_cues: list[str] = []
        best_count = 0
        for emotion, regexes in self._compiled.items():
            cues: list[str] = []
            for rx in regexes:
                m = rx.search(text)
                if m:
                    cues.append(m.group(0))
            if len(cues) > best_count:
                best_count = len(cues)
                best_emotion = emotion
                best_cues = cues

        if best_count == 0:
            sig = ToneSignal(emotion="neutral", confidence=0.0)
        else:
            # ishonch: cue soni va matn uzunligiga bog'liq (uzoq matnda
            # bitta cue kamroq ishonchli)
            confidence = min(0.95, 0.35 + 0.22 * best_count)
            sig = ToneSignal(emotion=best_emotion, confidence=confidence,
                             cues=list(dict.fromkeys(best_cues))[:5])
        self._last = sig
        return sig

    def directive(self, signal: Optional[ToneSignal] = None) -> str:
        """Agent uchun ohang direktivasi (bo'sh bo'lishi mumkin)."""
        sig = signal or self._last
        if sig is None or sig.emotion == "neutral":
            return ""
        return TONE_DIRECTIVES.get(sig.emotion, "")

    # ------------------------------------------------------------ #

    def stats(self) -> dict:
        return {
            "scans": self._scans,
            "emotions": list(EMOTION_PATTERNS.keys()),
            "last": self._last.to_dict() if self._last else None,
        }
