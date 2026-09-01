"""
IGRIS BRAIN — 2.3 Musical Intelligence — core/music
===================================================
Ovoz/musiqa naqshlarini tushunish.

Qo'llanma 2.3-band: ixtiyoriy plugin, faqat kerak bo'lsa. Sof matn agenti
uchun real foydali versiya: foydalanuvchi musiqa nazariyasi (akkordlar,
notalar, intervallar, gamma, ritm) haqida so'rasa — agentga ixcham musiqa
lug'ati + yo'naltirish beradi (LLM musiqiy terminlarni aniq ishlatadi).

Bu modul faqat ANIQLASH + YO'NALTIRISH beradi — ovoz bilan ishlamaydi,
avtonom ijro etmaydi. Ovozli interfeys (audio I/O) qo'shilsa, shu qatlam
prosody tahlili uchun kengaytirilishi mumkin.
"""

from __future__ import annotations

import re
from typing import Optional


# Musiqa/ovoz bilan bog'liq so'rov markerlari (uz + en)
_MUSIC_WORDS = (
    "akkord", "akkordlar", "akord", "chord", "chords",
    "nota", "notalar", "note", "notes", "melodiya", "melody",
    "ritm", "rhythm", "qo'shiq", "qoshiq", "song", "musiqa", "music",
    "gamma", "gammas", "scale", "interval", "intervals", "tonal",
    "ovoz", "audio", "sound", "treble", "bass", "tempo", "prosody",
    "sozlama", "tune", "tuning", "kuy", "kuylash", "sing", "songwriting",
)

# Nota nomlari — o'zbek/ingliz (xorijiy transliteratsiyalar bilan)
NOTE_GLOSSARY = (
    "Notes: do=C, re=D, mi=E, fa=F, sol=G, lya=A, si=B. "
    "Sharps (#) raise a note by a half-step, flats (b) lower it."
)

# Musiqa nazariyasi bo'yicha QISQA yo'naltirish — system prompt uchun.
# Faqat javob SIFATINI oshiradi; agent mustaqil qaror qabul qilmaydi.
MUSIC_DIRECTIVE = (
    "The user is asking about music/audio. Use precise music-theory terms: "
    "a major chord = root + major 3rd + perfect 5th; minor chord = root + "
    "minor 3rd + perfect 5th. Roman numerals: I IV V (major key), i iv v "
    "(minor key). Intervals count letter names inclusively (C to G = 5th). "
    "If relevant, name notes in both Uzbek (do-re-mi) and English (C-D-E)."
)


class MusicLayer:
    """2.3 Musiqa/ovoz so'rovlarini aniqlaydi va yo'naltiradi.

    Usullar:
      - detect(text)          -> musiqiy so'rovmi (bool + markerlar)
      - directive(text)       -> system prompt uchun musiqa direktivasi ("" bo'lsa — kerak emas)
    """

    def __init__(self):
        self._scans: int = 0
        self._last_musical: bool = False

    # ------------------------------------------------------------ #

    def detect(self, text: str) -> bool:
        self._scans += 1
        low = (text or "").lower()
        self._last_musical = any(w in low for w in _MUSIC_WORDS)
        return self._last_musical

    def directive(self, text: str) -> str:
        """Musiqa so'rovi bo'lsa — glossary + yo'naltirish bloki, aks holda ''."""
        if not self.detect(text):
            return ""
        return "Music reference:\n- " + NOTE_GLOSSARY + "\n\n" + MUSIC_DIRECTIVE

    # ------------------------------------------------------------ #

    def stats(self) -> dict:
        return {
            "scans": self._scans,
            "last_musical": self._last_musical,
            "markers": len(_MUSIC_WORDS),
        }
