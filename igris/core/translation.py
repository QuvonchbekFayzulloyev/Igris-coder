"""
igris.core.translation
-----------------------
Unified Translation Module — translates any language to canonical (English)
before the Understanding Module processes the text, then translates response
back to the user's original language if needed.

Preserves meaning, context, technical terms, and user intent.
Not word-for-word translation — semantic preservation is the goal.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

LANGUAGE_PATTERNS: dict[str, list[str]] = {
    "uz": [
        r"\b(salom|rahmat|iltimos|marhamat|kechir)\b",
        r"\b(men|sen|u|biz|siz|ular)\b",
        r"\b(va|bilan|uchun|bilan|kerak|bor|yo'q|hozi|endi)\b",
        r"\b(faqat|faqatgina|ham|hamma|har|hech)\b",
        r"\b(bu|shu|mana|ana|qanaqa)\b",
        r"\b(qanday|qanaqa|nima|kim|nega|qachon|qayerda|qayerga)\b",
        r"\b(ishla|yoz|o'qi|kel|ket|bor|ber|ol|qil|yarat|tuzat|ko'rsat)\b",
        r"\b(-man|-san|-di|-miz|-siz|-dilar|-ing|-gan|-yot|-moqda)\b",
        r"\b(rasm|surat|tasvir|foto|video)\b",
        r"\b(olma|kitob|daftar|stol|eshik|deraza|qalam|ruchka|kompyuter)\b",
    ],
    "ru": [
        r"\b(я|ты|он|она|оно|мы|вы|они)\b",
        r"\b(и|в|на|с|по|для|от|из|о|об|при|за|через|до)\b",
        r"\b(это|что|как|где|когда|почему|зачем|кто|котор)\b",
        r"\b(работа|код|программа|файл|система|функци)\b",
        r"\b(создай|напиши|исправ|удали|покажи|найди)\b",
        r"\b(изображение|картинк|рисун|фото)\b",
    ],
    "kk": [
        r"\b(мен|сен|ол|біз|сіз|олар)\b",
        r"\b(және|менен|үшін|керек|бар|жоқ)\b",
        r"\b(қандай|қалай|не|кім|неге|қашан|қайда)\b",
        r"\b(сурет|фото|бейне)\b",
    ],
    "tr": [
        r"\b(ben|sen|o|biz|siz|onlar)\b",
        r"\b(ve|ile|için|gerek|var|yok)\b",
        r"\b(nasıl|ne|kim|neden|ne zaman|nerede|hangi)\b",
        r"\b(resim|fotoğraf|görsel|şekil)\b",
    ],
}

CANONICAL_LANG = "en"

_TRANSLATION_CACHE: dict[str, str] = {}

_LLM_CONFIG_CACHE: dict | None = None


def _load_llm_config() -> dict:
    global _LLM_CONFIG_CACHE
    if _LLM_CONFIG_CACHE:
        return _LLM_CONFIG_CACHE
    try:
        cfg_path = Path(__file__).resolve().parents[2] / ".igris" / "config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        _LLM_CONFIG_CACHE = {
            "base_url": cfg.get("model", {}).get("base_url", cfg.get("ollama", {}).get("base_url", "http://127.0.0.1:11434")),
            "model": cfg.get("model", {}).get("name", cfg.get("ollama", {}).get("model", "qwen3:4b")),
        }
    except Exception:
        _LLM_CONFIG_CACHE = {"base_url": "http://127.0.0.1:11434", "model": "qwen3:4b"}
    return _LLM_CONFIG_CACHE


def detect_language(text: str) -> str:
    """Detect language by matching known patterns.

    Returns language code ('uz', 'ru', 'kk', 'tr', or 'en' for default).
    Uses heuristic pattern matching — fast, no network call.
    """
    lowered = text.lower().strip()
    if not lowered:
        return CANONICAL_LANG

    # Count pattern matches per language
    scores: dict[str, int] = {}
    for lang, patterns in LANGUAGE_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, lowered))
        if score > 0:
            scores[lang] = score

    if not scores:
        return CANONICAL_LANG

    best = max(scores, key=scores.get)
    return best


def needs_translation(text: str) -> tuple[bool, str]:
    """Check if text needs translation to canonical English.

    Returns (needs_translation, detected_language).
    """
    lang = detect_language(text)
    return lang != CANONICAL_LANG, lang


async def translate_to_canonical(text: str, source_lang: str | None = None) -> str:
    """Translate text from detected language to canonical English.

    Uses local LLM for translation when available. Falls back to
    removing diacritics and returning as-is if LLM is down.
    Preserves meaning, context, technical terms, and user intent.

    Results are cached to avoid repeated translation of the same text.
    """
    if not text.strip():
        return text

    if source_lang is None:
        _, detected = needs_translation(text)
        source_lang = detected

    if source_lang == CANONICAL_LANG:
        return text

    cache_key = f"{source_lang}:{text.lower().strip()}"
    if cache_key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[cache_key]

    config = _load_llm_config()
    if not config.get("base_url"):
        _TRANSLATION_CACHE[cache_key] = text
        return text

    try:
        import httpx
        prompt = (
            f"Translate the following text from {source_lang} to English. "
            "Preserve all technical terms, code identifiers, file paths, and proper nouns exactly as-is. "
            "Keep the original meaning, tone, and intent. Do NOT add explanations.\n\n"
            f"Text: {text}"
        )
        resp = httpx.post(
            f"{config['base_url']}/api/chat",
            json={
                "model": config["model"],
                "messages": [
                    {"role": "system", "content": "You are a precise translation engine. Output ONLY the translation, no explanations, no notes."},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.1},
            },
            timeout=30,
        )
        result = resp.json().get("message", {}).get("content", "").strip()
        result = re.sub(r"^(Here'?s? |Sure!? |Translation:?)\s*", "", result, flags=re.IGNORECASE).strip()
        if result:
            _TRANSLATION_CACHE[cache_key] = result
            return result
    except Exception:
        pass

    _TRANSLATION_CACHE[cache_key] = text
    return text


async def translate_from_canonical(text: str, target_lang: str) -> str:
    """Translate text from canonical English back to target language.

    Used when the user wrote in a non-English language — the response
    should be in their language too.
    """
    if target_lang == CANONICAL_LANG or not text.strip():
        return text

    cache_key = f"rev:{target_lang}:{text.lower().strip()[:100]}"
    if cache_key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[cache_key]

    config = _load_llm_config()
    if not config.get("base_url"):
        return text

    try:
        import httpx
        prompt = (
            f"Translate the following text from English to {target_lang}. "
            "Preserve all technical terms, code identifiers, file paths, and proper nouns exactly as-is. "
            "Keep the original meaning, tone, and formatting. Do NOT add explanations.\n\n"
            f"Text: {text[:3000]}"
        )
        resp = httpx.post(
            f"{config['base_url']}/api/chat",
            json={
                "model": config["model"],
                "messages": [
                    {"role": "system", "content": f"You are a precise translation engine. Output ONLY the {target_lang} translation, no explanations, no notes."},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.1},
            },
            timeout=60,
        )
        result = resp.json().get("message", {}).get("content", "").strip()
        result = re.sub(r"^(Here'?s? |Sure!? |Translation:?)\s*", "", result, flags=re.IGNORECASE).strip()
        if result:
            suffix = text[3000:] if len(text) > 3000 else ""
            full = result + suffix
            _TRANSLATION_CACHE[cache_key] = full
            return full
    except Exception:
        pass

    return text
