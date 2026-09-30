"""
IGRIS BRAIN — IgrisQuick — quick_paths compat fasadi (S5)
=========================================================
S5 modullashtirishda tez yo'llar `quick_paths.py`ga ko'chirildi. Bu fayl
ESKI import nomlarini saqlaydi (tashqi foydalanuvchilar/testlar uchun):
`from igris_quick import is_math_expr, weather_lookup, ...` ishlashda davom
etadi. Yangi kod to'g'ridan-to'g'ri `quick_paths`dan foydalanadi.

Fasadlar aniq va to'g'ri:
  is_math_expr(msg)         -> Optional[str]   (quick_paths.is_math_request)
  is_math_request(msg)      -> Optional[str]   (alias)
  resolve_math(expr, res)   -> str             (quick_paths.format_math_result)
  math_prefix(msg)          -> Optional[re.Match]  (quick_paths.MATH_PREFIX_RE.match)
  weather_lookup(msg)       -> Optional[str]   (quick_paths.quick_weather)
  weather_lookup_or_none(m) -> Optional[str]   (alias)
  resolve_weather(cond)     -> str             (quick_paths.wttr_cond)
"""

from __future__ import annotations

import re
from typing import Any, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agent.quick_paths as _qp

__all__ = [
    "is_math_expr",
    "is_math_request",
    "math_prefix",
    "weather_lookup",
    "weather_lookup_or_none",
    "resolve_math",
    "resolve_weather",
]


def is_math_expr(message: str) -> Optional[str]:
    """Sof arifmetik ifoda so'rovi — hisoblanadigan ifoda yoki None."""
    return _qp.is_math_request(message)


# Eski nom bilan bir xil semantika — alias.
is_math_request = is_math_expr


def math_prefix(message: str) -> Optional[re.Match]:
    """'hisobla: 2+2' kabi prefiksni aniqlaydi (quick_paths.MATH_PREFIX_RE)."""
    return _qp.MATH_PREFIX_RE.match(message or "")


def weather_lookup(message: str) -> Optional[str]:
    """Ob-havo tez javob (wttr.in + Open-Meteo) yoki None."""
    return _qp.quick_weather(message)


# Eski nom bilan bir xil semantika — alias.
weather_lookup_or_none = weather_lookup


def resolve_math(expr: str, result: Any) -> str:
    """Hisoblangan natijani chiroyli ko'rinishga keltiradi."""
    return _qp.format_math_result(expr, result)


def resolve_weather(cond: str) -> str:
    """wttr.in condition/emoji -> o'zbekcha tavsif."""
    return _qp.wttr_cond(cond)
