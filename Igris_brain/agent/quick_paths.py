"""
IGRIS BRAIN — QuickPaths (math + weather) — S5 modullashtirish
===============================================================
problems_to_fix.md :: S5 (qism) — igris_agent god-file'dan ajratilgan.
Protokol P12: math/weather tez deterministik yo'llar (LLM/brauzer keraksiz).

**MATH**: `is_math_request` — faqat raqamlar va + - * / ( ) bo'lgan qisqa
so'rovni topadi; `format_math_result` — natijani chiroyli ko'rinishga keltiradi
(hisoblash `IntelligenceCore.quick_math` → `LogicLayer.safe_math` da — agent
uzatadi, bu modul FAQT aniqlash/format qiladi).

**WEATHER**: `is_weather` — ob-havo so'rovini aniqlaydi; `quick_weather` —
wttr.in (joy nomini biladi, ~1-2s) asosiy, Open-Meteo (geocoding+forecast)
fallback. Qaytadi: tayyor o'zbekcha matn yoki None (so'rov ob-havo emas /
joy topilmadi — agent LLM yo'liga o'tadi).

Fail-safe: hech qachon exception tashlab chatni buzmaydi (tarmoq xatlari
None/continue bilan yutiladi).
"""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from typing import Optional

# ---------------------------------------------------------------------- #
# MATH — deterministik arifmetika aniqlash
# ---------------------------------------------------------------------- #

# Raqamlar va + - * / ( ) dan tashqari hech narsa bo'lmagan arifmetik zanjir.
# "2+2*3", "(15-3)/4" kabi ifodalarni topadi; "Python dasturi yoz" kabi
# so'rovlar ushlanmaydi (raqam zanjiri yo'q).
MATH_EXPR_RE = re.compile(r"(?<![\w.])(?:[-+]?\d+(?:\.\d+)?)(?:\s*[-+*/]\s*[-+]?\d+(?:\.\d+)?)+")
MATH_PREFIX_RE = re.compile(
    r"^\s*(hisobla|hisoblang|hisoblab\s+ber|calculate|compute|evaluate|nechchi|qancha|what\s+is|how\s+much\s+is)\s*[:=]?\s*(.+)$",
    re.IGNORECASE,
)


def is_math_request(message: str) -> Optional[str]:
    """Sof arifmetik ifoda so'rovi — tez deterministik javob uchun.

    Qaytaradi: xavfsiz hisoblanadigan ifoda yoki None. Faqat raqamlar va
    + - * / ( ) bo'lgan, juda qisqa (<= 60 belgi) so'rovlar qabul qilinadi.
    """
    msg = (message or "").strip()
    if not msg or len(msg) > 60:
        return None
    m = MATH_PREFIX_RE.match(msg)
    expr = m.group(2).strip() if m else msg
    if not re.fullmatch(r"[\d\s+\-*/().]+", expr):
        return None
    if not MATH_EXPR_RE.search(expr):
        return None
    return expr


def format_math_result(expr: str, result) -> str:
    """Hisoblangan natijani foydalanuvchiga chiroyli ko'rinishda qaytaradi."""
    result_f = float(result)
    pretty = str(int(result_f)) if result_f.is_integer() else f"{result_f:.6f}".rstrip("0").rstrip(".")
    return f"{expr} = {pretty}"


# ---------------------------------------------------------------------- #
# WEATHER — aniqlash + so'zlug'lar
# ---------------------------------------------------------------------- #

# "bugun ... ob-havosi qanday?" kabi so'rovlar — LLM/brauzer KERAKSIZ:
# geocoding + forecast API orqali 2-4 soniyada aniq javob.
WEATHER_RE = re.compile(
    r"\b(?:ob[\s-]?havo|obhavo|weather|temperatur|harorat)\w*|"
    r"\bhavo\w*(?=\s+(?:qanday|qanaqa|nech|necha|bugun|bugungi|hozir|holat|daraja))",
    re.IGNORECASE,
)

WEATHER_STOP = frozenset((
    "bugun", "bugungi", "hozir", "hozirgi", "kecha", "ertaga", "kunlik",
    "ob", "havo", "obhavo", "ob-havo", "havosini", "havosi", "havoni", "havoda",
    "havosiga", "havosida", "obhavosini", "obhavosi", "ob-havosini",
    "qanday", "qanaqa", "nech", "necha", "daraja", "grader",
    "temperatur", "temperatura", "harorat", "weather",
    "tuman", "viloyat", "shahar", "shahri", "shahrida", "shahridagi",
    "viloyatida", "viloyatidagi", "tumanida", "tumanidagi", "tumanda",
    "today", "now", "tonight", "tomorrow", "yesterday", "right", "current",
    "bugungi", "kun", "kuni", "kecha", "ertaga", "hozirgi",
    "in", "at", "for", "of", "the", "and", "de", "du", "a", "an",
    "so'ra", "sora", "soray", "so'ray", "so'rayman", "sorayman",
    "ayt", "ayting", "ber", "bering", "qil", "qiling", "uchun",
    "bilan", "iltimos", "menga", "men", "da", "de", "ni", "ning",
    "ga", "dagisi", "dagi", "holat", "holatini", "axvol", "ahvol",
))

# Open-Meteo weather_code -> o'zbekcha tavsif
WMO_CODE_TEXT = {
    0: "ochiq osmon", 1: "asosan ochiq", 2: "ozgina bulutli", 3: "bulutli",
    45: "tumanli", 48: "qirovli tuman",
    51: "mayda yomg'ir", 53: "mayda yomg'ir", 55: "intensiv mayda yomg'ir",
    56: "muzli mayda yomg'ir", 57: "muzli yomg'ir",
    61: "yomg'ir", 63: "yomg'ir", 65: "kuchli yomg'ir",
    66: "muzli yomg'ir", 67: "kuchli muzli yomg'ir",
    71: "qor", 73: "qor", 75: "kuchli qor", 77: "qor zarralari",
    80: "quyulma yomg'ir", 81: "quyulma yomg'ir", 82: "kuchli quyulma yomg'ir",
    85: "quyulma qor", 86: "kuchli quyulma qor",
    95: "momaqaldiroq", 96: "momaqaldiroq va do'l", 99: "kuchli momaqaldiroq va do'l",
}

# wttr.in condition/emoji -> o'zbekcha
WTTR_COND_MAP = {
    "sunny": "quyoshli", "clear": "ochiq", "partly cloudy": "ozgina bulutli",
    "cloudy": "bulutli", "overcast": "bulutli", "mist": "tumanli",
    "fog": "tumanli", "haze": "xira", "light rain": "mayda yomg'ir",
    "light drizzle": "mayda yomg'ir", "patchy rain": "ba'zi yomg'ir",
    "rain": "yomg'ir", "moderate rain": "yomg'ir", "heavy rain": "kuchli yomg'ir",
    "light snow": "mayda qor", "snow": "qor", "heavy snow": "kuchli qor",
    "thunderstorm": "momaqaldiroq", "freezing": "muzli",
    # wttr.in format=3 emoji belgilar
    "☀️": "quyoshli", "☀": "quyoshli", "⛅": "ozgina bulutli",
    "☁️": "bulutli", "🌦️": "o'zgaruvchan", "🌧️": "yomg'ir",
    "🌨️": "qor", "⛈️": "momaqaldiroq", "🌫️": "tumanli",
    "❄️": "qor", "🌬️": "shamolli",
    "quyoshli": "quyoshli", "ochiq": "ochiq", "bulutli": "bulutli",
    "yomg'ir": "yomg'ir", "tumanli": "tumanli",
}


def is_weather(message: str) -> bool:
    """So'rov ob-havo ehtiyojini bildiradimi (WEATHER_RE)."""
    return bool(WEATHER_RE.search((message or "").strip()))


def wmo_text(code: int) -> str:
    """Open-Meteo weather_code -> o'zbekcha tavsif."""
    return WMO_CODE_TEXT.get(code, "o'zgaruvchan bulutli")


def wttr_cond(cond: str) -> str:
    """wttr.in condition/emoji -> o'zbekcha (noma'lumi o'zicha qoladi)."""
    low = (cond or "").lower().strip()
    return WTTR_COND_MAP.get(low, low or "o'zgaruvchan")


def fmt_temp(t) -> str:
    """Temperatura ni "+12°C" / "-3°C" ko'rinishga keltiradi."""
    try:
        v = float(t)
    except (TypeError, ValueError):
        return "?"
    return ("+" if v >= 0 else "") + str(int(round(v))) + "°C"


# ---------------------------------------------------------------------- #
# WEATHER — joy nomini ajratish + manbalardan olish
# ---------------------------------------------------------------------- #

def _stem(tok: str) -> list[str]:
    """Qo'shimchalarni olib tashlaydi: Toshkentda -> Toshkent."""
    low = tok.lower()
    suffixes = ("dagi", "dagisi", "dan", "da", "de", "ga", "ning", "ni")
    s = tok
    for suf in suffixes:
        if low.endswith(suf):
            s = tok[: -len(suf)]
            break
    out = [s] if s else []
    if "'" in s:
        out.append(s.replace("'", ""))
    return out


def _location_candidates(msg: str) -> list[str]:
    """Joy nomi nomzodlarini ajratadi (birinchi navbatda sinab ko'riladigan)."""
    tokens = [t.strip(".,;:!?'\"()[]") for t in re.split(r"\s+", msg)]
    loc_words = [
        t for t in tokens
        if t and not any(ch.isdigit() for ch in t)
        and t.lower() not in WEATHER_STOP
        and re.search(r"[A-Za-z]", t)
    ]
    candidates: list[str] = []
    # Birikma birinchi ("new york" kabi ikki so'zli joylar), keyin alohida
    # tokenlar eng aniqdan (oxirgidan) boshlab.
    joined = " ".join(loc_words[-2:]).strip()
    for s in _stem(joined):
        if s and s not in candidates:
            candidates.append(s)
    for t in reversed(loc_words[-4:]):
        for s in _stem(t):
            if s and s not in candidates:
                candidates.append(s)
    if not candidates:
        candidates = ["toshkent"]
    return candidates


def _fetch_wttr(cand: str) -> Optional[str]:
    """wttr.in — joy + ob-havo bitta tez so'rovda (tuman darajasigacha)."""
    # wttr.in oddiy Python-urllib User-Agent'ni rad qiladi (HTTP 500) —
    # o'z UA'mizni yuboramiz.
    _wua = {"User-Agent": "IgrisAgent/2.0 (local; contact localhost)"}
    try:
        url = ("https://wttr.in/" + urllib.parse.quote(cand) + "?format=3")
        with urllib.request.urlopen(urllib.request.Request(url, headers=_wua), timeout=5) as resp:
            text = resp.read().decode("utf-8", "replace")
        if "unknown location" in text.lower() or "no results" in text.lower():
            return None
        m = re.match(r"^\s*(.*?):\s*(.*?)\s*([+-]?\d+°C)\s*$", text, re.DOTALL)
        if not m:
            return None
        name = (m.group(1) or cand).strip()
        cond = m.group(2).strip()
        temp = m.group(3)
        # Namlik va shamol — qo'shimcha mayda so'rov (bitta: %h+%w)
        extra: list[str] = []
        try:
            url2 = ("https://wttr.in/" + urllib.parse.quote(cand) + "?format=%h+%w")
            with urllib.request.urlopen(urllib.request.Request(url2, headers=_wua), timeout=5) as resp2:
                parts2 = resp2.read().decode("utf-8", "replace").split()
            hum = next((p for p in parts2 if p.endswith("%")), "")
            wind = next((p for p in parts2 if "km/h" in p), "")
            if hum:
                extra.append("namlik " + hum)
            if wind:
                # yo'nalish o'qlarini tozalab, raqamni olamiz (→5km/h -> 5 km/h)
                wm = re.search(r"(\d+)\s*km/h", wind)
                if wm:
                    extra.append("shamol " + wm.group(1) + " km/soat")
        except Exception:
            pass
        answer = "Hozir " + name + "da: " + temp + " — " + wttr_cond(cond) + "."
        if extra:
            answer += " " + ", ".join(extra) + "."
        answer += " Manba: wttr.in (jonli)."
        return answer
    except Exception:
        return None


def _fetch_open_meteo(candidates: list[str]) -> Optional[str]:
    """Fallback: Open-Meteo geocoding + forecast (kalit talab qilmaydi)."""
    import json as _json
    lat = lon = None
    found_name = ""
    for cand in candidates:
        try:
            q = urllib.parse.quote(cand)
            url = ("https://geocoding-api.open-meteo.com/v1/search?name="
                   + q + "&count=1&language=uz&format=json")
            with urllib.request.urlopen(url, timeout=6) as resp:
                data = _json.loads(resp.read().decode("utf-8", "replace"))
            results = data.get("results") or []
            if results:
                r = results[0]
                lat = r.get("latitude")
                lon = r.get("longitude")
                found_name = r.get("name") or cand
                break
        except Exception:
            continue
    if lat is None or lon is None:
        return None
    try:
        furl = ("https://api.open-meteo.com/v1/forecast?latitude="
                + str(lat) + "&longitude=" + str(lon)
                + "&current=temperature_2m,relative_humidity_2m,"
                  "apparent_temperature,weather_code,wind_speed_10m&timezone=auto")
        with urllib.request.urlopen(furl, timeout=6) as resp:
            fdata = _json.loads(resp.read().decode("utf-8", "replace"))
        cur = fdata.get("current") or {}
    except Exception:
        return None
    temp = cur.get("temperature_2m")
    if temp is None:
        return None

    code = int(cur.get("weather_code") or 0)
    hum = cur.get("relative_humidity_2m")
    feels = cur.get("apparent_temperature")
    wind = cur.get("wind_speed_10m")

    line = fmt_temp(temp) + " — " + wmo_text(code)
    if feels is not None:
        line += ", haqiqiy " + fmt_temp(feels)
    extra: list[str] = []
    if hum is not None:
        extra.append("namlik " + str(int(hum)) + "%")
    if wind is not None:
        extra.append("shamol " + str(int(round(float(wind)))) + " km/soat")
    answer = "Hozir " + found_name + "da: " + line + "."
    if extra:
        answer += " " + ", ".join(extra) + "."
    answer += " Manba: Open-Meteo (jonli)."
    return answer


def quick_weather(message: str) -> Optional[str]:
    """Ob-havo so'roviga deterministik tez javob.

    Asosiy manba: wttr.in (joy nomini ham biladi — G'ijduvon kabi tuman
    darajasidagi joylarni topadi, bitta so'rov ~1-2 soniya). Fallback:
    Open-Meteo (geocoding + forecast). Qaytadi: tayyor matn yoki None
    (so'rov ob-havo emas / joy topilmadi — u holda LLM yo'li ishlaydi).
    """
    msg = (message or "").strip()
    if not msg or not is_weather(msg):
        return None
    candidates = _location_candidates(msg)
    # 1) wttr.in — eng tez (joy + ob-havo bitta so'rovda)
    for cand in candidates:
        answer = _fetch_wttr(cand)
        if answer:
            return answer
    # 2) Fallback: Open-Meteo
    return _fetch_open_meteo(candidates)
