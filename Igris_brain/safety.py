"""
IGRIS BRAIN — Safety / Sanitization
===================================
RAG kontekst va web matnini LLM'ga yuborishdan OLDIN tozalash uchun yagona
manba. Prompt-injection hujumlarini (\"ignore previous instructions\", \"system:\"
kabi) aniqlaydi va neytrallashtiradi.

Manba: Igris_Memory/memory/poisoning.py — PoisoningProtection.SUSPICIOUS_PATTERNS.
Bu yerdagi `scan()` bilan MemoryBridge (RAG recall) ham, web_tools (web_fetch
chiqishi) ham bir xil qoidadan foydalanadi — N2/N3 muammolariga yechim.
"""

from __future__ import annotations

import re

# PoisoningProtection naqshlari bilan bir xil — Igris_Memory'ni import qilish
# majburiy emas (boshqa joylarda qayta ishlatiladigan mustaqil ro'yxat).
SUSPICIOUS_PATTERNS = [
    r"ignore\s+(previous|all|above|prior)\s+(instructions?|rules?|prompts?)",
    r"ignore\s+all\s+previous\s+(instructions?|rules?|prompts?)",
    r"you\s+are\s+now\s+(a|an)\s+",
    r"forget\s+(everything|all|previous)",
    r"system\s*:\s*",
    r"<\s*(script|instruction)\s*>",
    r"override\s+(safety|rules?|instructions?)",
    r"jailbreak",
    r"DAN\s+mode",
    r"developer\s+mode",
    r"admin\s+access",
    r"bypass\s+(all|security|rules?)",
    r"disregard\s+(previous|all)\s+instructions?",
    r"pretend\s+(you\s+are|to\s+be)\s+",
    r"repeat\s+(after\s+me|the\s+above)",
    r"new\s+instructions?\s*:",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_PATTERNS]


def scan(text: str) -> list[str]:
    """Matndagi injection naqshlarini topadi. Bo'sh ro'yxat = xavfsiz."""
    if not text:
        return []
    return [m.group(0) for pat in _COMPILED for m in pat.finditer(text)]


def has_suspicious(text: str) -> bool:
    """Matnda shubhali injection naqsh bormi?"""
    return bool(scan(text))


def sanitize(text: str, replace: str = "[filtered: suspicious content]") -> str:
    """Matndagi injection naqshlarini olib tashlaydi (faqat mos kelgan qism).

    BUTUN satrni emas, faqat naqshga mos kelgan BO'LAK maskalanadi — matnning
    qolgan qismi saqlanadi. Bu web sahifalar uchun muhim: HTML bitta uzun
    satrga siqilgan bo'lishi mumkin, butun satrni maskalash butun sahifani
    o'chirib tashlardi. Yashirin ko'rsatma esa hali ham LLM'ga yetib bormaydi.
    """
    if not text:
        return text
    for pat in _COMPILED:
        text = pat.sub(replace, text)
    return text
