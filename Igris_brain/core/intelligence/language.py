"""
IGRIS BRAIN — 2.1 Linguistic Intelligence — core/language
==========================================================
Aniq, ma'noli til ishlatish. LLM negizida allaqachon bor; bu qatlam
kuchaytiradi: domenga xos terminologiya (kod, arxitektura) uchun
lug'at (glossary) qatlami + tilni aniqlash.

Modul faqat YO'NALTIRISH beradi — mustaqil qaror qabul qilmaydi.
"""

from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------- #
# Domenga xos terminologiya lug'ati (uz <-> en) — kod/arxitektura
# ---------------------------------------------------------------- #

# uz -> en (qo'llanma: "domenga xos terminologiya uchun lug'at qatlami")
GLOSSARY: dict[str, str] = {
    "massiv": "array",
    "ro'yxat": "list",
    "lug'at": "dictionary",
    "to'plam": "set",
    "satr": "string",
    "matn": "text",
    "funksiya": "function",
    "o'zgaruvchi": "variable",
    "doimiy": "constant",
    "argument": "argument/parameter",
    "qaytarish": "return",
    "shart": "condition",
    "siklik": "loop",
    "iteratsiya": "iteration",
    "rekursiya": "recursion",
    "xato": "error",
    "istisno": "exception",
    "sinf": "class",
    "obyekt": "object",
    "usul": "method",
    "meros": "inheritance",
    "interfeys": "interface",
    "modul": "module",
    "kutubxona": "library",
    "paket": "package",
    "bog'liqlik": "dependency",
    "so'rov": "query",
    "indeks": "index",
    "kalit": "key",
    "qiymat": "value",
    "obyekt": "object",
    "grafik": "graph",
    "daraxt": "tree",
    "tugun": "node",
    "chekka": "edge",
    "xotira": "memory",
    "bufer": "buffer",
    "oqim": "stream",
    "fayl": "file",
    "papka": "folder/directory",
    "yo'l": "path",
    "kengaytma": "extension",
    "jarayon": "process",
    "ip": "thread",
    "sinxronlash": "synchronize",
    "shifrlash": "encryption",
    "kalit": "key",
    "xavfsizlik": "security",
    "arxitektura": "architecture",
    "qatlam": "layer",
    "interfeys": "interface",
    "protokol": "protocol",
    "so'rov": "request",
    "javob": "response",
    "ulanish": "connection",
    "port": "port",
    "server": "server",
    "mijoz": "client",
    "ma'lumotlar bazasi": "database",
    "jadval": "table",
    "ustun": "column",
    "qator": "row",
    "yozuv": "record",
    "so'rov tili": "query language",
    "transaksiya": "transaction",
    "zaxira nusxa": "backup",
    "tiklash": "restore",
    "sinov": "test",
    "xatolikni tuzatish": "debugging",
    "qayta ishlash": "refactoring",
    "optimallashtirish": "optimization",
    "yuklash": "loading",
    "saqlash": "saving",
    "o'chirish": "deleting",
    "yaratish": "creating",
}

# en -> uz (teskari indeks — inglizcha so'zni o'zbekcha izohlab berish)
EN_TO_UZ: dict[str, str] = {v: k for k, v in GLOSSARY.items()}


def detect_language(text: str) -> str:
    """Matn tilini aniqlaydi: 'uz' | 'en' | 'unknown'.

    Oddiy so'z chastotasi asosida (o'zbekcha xizmatchi so'zlar va
    apostrof belgisi o'zbekcha matn uchun kuchli signal).
    """
    if not text:
        return "unknown"
    low = text.lower()

    # O'zbekcha xizmatchi so'zlar — juda kuchli signal
    uz_markers = [
        "ning", "bilan", "uchun", "qanday", "nima", "kerak", "bo'ladi",
        "qil", "ber", "ayt", "yoz", "chiz", "hamma", "buni", "shuni",
        "hozir", "keyin", "lekin", "yoki", "emas", "mana", "shu",
        "o'zbek", "uzbek", "ilova", "dastur", "fayl", "papka",
    ]
    # Inglizcha xizmatchi so'zlar
    en_markers = [
        "the", "and", "for", "with", "please", "write", "create", "draw",
        "show", "tell", "what", "how", "this", "that", "file", "folder",
        "code", "function", "app", "website", "hello", "hi",
    ]

    uz_score = sum(low.count(m) for m in uz_markers)
    en_score = sum(low.count(m) for m in en_markers)
    # O'zbekcha apostrof (' o' g' ...) — o'zbekcha matn belgisi
    if "'" in low and re.search(r"[a-z]'[a-z]", low):
        uz_score += 2

    if uz_score > en_score and uz_score >= 2:
        return "uz"
    if en_score > uz_score and en_score >= 2:
        return "en"
    return "unknown"


def glossary_term(word: str) -> Optional[str]:
    """Bir so'z uchun lug'at izohi: uz->en yoki en->uz (agar bor bo'lsa)."""
    w = (word or "").strip().lower()
    if w in GLOSSARY:
        return GLOSSARY[w]
    if w in EN_TO_UZ:
        return EN_TO_UZ[w]
    return None


class LanguageLayer:
    """2.1 Lingvistik intellekt — terminologiya + til qatlami.

    `enrich_system` — asosiy system prompt'ga domenga xos lug'atni
    qo'shadi (faqat kerak bo'lsa, ixcham shaklda).
    """

    def __init__(self):
        self._last_lang: str = "unknown"

    # ------------------------------------------------------------ #

    def detect(self, text: str) -> str:
        self._last_lang = detect_language(text)
        return self._last_lang

    def glossary_block(self, max_terms: int = 24, lang: str = "uz") -> str:
        """System prompt uchun ixcham lug'at bloki (eng ko'p ishlatiladiganlar).

        lang='uz'  -> "massiv (array), ro'yxat (list), ..."
        lang='en'  -> "array (massiv), list (ro'yxat), ..."
        """
        items = list(GLOSSARY.items())
        if lang == "en":
            lines = [f"- {en} ({uz})" for uz, en in items[:max_terms]]
        else:
            lines = [f"- {uz} ({en})" for uz, en in items[:max_terms]]
        return "Domain glossary (Uzbek<->English coding terms):\n" + "\n".join(lines)

    def enrich_system(self, system: str, text: str, max_terms: int = 24) -> str:
        """System prompt'ga lug'at qo'shadi — lekin faqat agar matnda
        o'zbekcha/texnik termin bo'lsa va blok hali qo'shilmagan bo'lsa.

        Xavfsiz: prompt o'lchamini nazorat qiladi (max_terms).
        """
        if not text or "Domain glossary" in (system or ""):
            return system
        lang = self.detect(text)
        if lang == "unknown":
            # texnik so'z borligini tekshiramiz — matn qisqa va lug'atga
            # tegishli so'z bo'lsa ham boyitamiz
            low = text.lower()
            if not any(w in low for w in list(GLOSSARY)[:20]):
                return system
        block = self.glossary_block(max_terms=max_terms, lang=lang)
        return (system or "") + "\n\n" + block

    def stats(self) -> dict:
        return {
            "terms": len(GLOSSARY),
            "last_lang": self._last_lang,
        }
