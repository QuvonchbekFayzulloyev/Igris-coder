"""
Roadmap v4 Phase A2 — CONTEXT FILTER (§6 qoldig'i)
===================================================
v1 §6: irrelevant context filter + cross-layer ranking + dedup.

Kontekst qatlamlari (system/user/memory/history) bir joyga yig'iladi:
  1. RELEVANCE SCORING — task matni bilan keyword overlap + layer og'irligi
  2. CROSS-LAYER RANKING — barcha qatlamlar orasida umumiy score bilan tartib
  3. DEDUP — bir xil ma'lumot 2 qatlamda bo'lmasligi (normalizatsiya + hash)

Falsifa: deterministik (LLM yo'q); score kanonik — layer nomi alohida.
"""
from __future__ import annotations

import hashlib
import re

__all__ = ["score_context", "rank_context_layers", "dedup_layers",
           "build_context"]

# Qatlam og'irliklari (ranking'da kichik bonus — score'ni buzmagan holda)
_LAYER_WEIGHT = {"system": 0.20, "user": 0.15, "memory": 0.10, "history": 0.05}

_STOP = {"the", "a", "an", "va", "bilan", "uchun", "bu", "shu", "and", "or",
         "of", "in", "on", "to", "is", "are", "was", "that", "this", "with"}


def _keywords(text: str) -> set:
    low = re.sub(r"[^\w\s]", " ", str(text or "").lower())
    return {w for w in low.split() if len(w) >= 3 and w not in _STOP}


def _norm(text: str) -> str:
    """Dedup uchun kanonik shakl: kichik harf + faqat so'zlar tartiblangan."""
    return " ".join(sorted(str(text or "").lower().split()))


def _fingerprint(text: str) -> str:
    return hashlib.sha256(_norm(text).encode("utf-8")).hexdigest()[:16]


def score_context(task: str, layer: str, content: str) -> float:
    """Task bilan kontent orasidagi relevance score (0..1+).

    score = |task_kw ∩ content_kw| / |task_kw| + layer_weight * 0.1
    Layer kichik bonus beradi (system konteksti doim foydali — lekin
    overlap'siz kontent baland score ololmaydi).
    """
    task_kw = _keywords(task)
    if not task_kw:
        return round(_LAYER_WEIGHT.get(layer, 0.0) * 0.1, 4)
    c_kw = _keywords(content)
    overlap = len(task_kw & c_kw) / len(task_kw)
    return round(overlap + _LAYER_WEIGHT.get(layer, 0.0) * 0.1, 4)


def rank_context_layers(layers: dict, task: str,
                        min_score: float = 0.12) -> list[dict]:
    """Barcha qatlamlar bir ro'yxatga chiqariladi + umumiy score bilan tartib.

    layers: {"system": str, "user": str, "memory": [str, ...],
             "history": [str, ...]}  — har qatlam bitta yoki ro'yxat.
    Qaytadi: [{layer, content, score}, ...] score bo'yicha kamayishda,
    min_score'dan past — chiqariladi (irrelevant filter).
    """
    items: list[dict] = []

    def _add(layer: str, val):
        if val is None:
            return
        if isinstance(val, (list, tuple)):
            for v in val:
                _add(layer, v)
            return
        content = str(val)
        if not content.strip():
            return
        items.append({"layer": layer, "content": content,
                      "score": score_context(task, layer, content)})

    for layer in ("system", "user", "memory", "history"):
        _add(layer, layers.get(layer))

    items.sort(key=lambda x: x["score"], reverse=True)
    return [it for it in items if it["score"] >= min_score]


def dedup_layers(ranked: list[dict]) -> list[dict]:
    """Bir xil ma'lumot bir necha qatlamda bo'lsa — ENG BALAND score'li saqlanadi.

    Fingerprint (normalizatsiya + sha256) asosida; natijada dup_content=False
    qatorlar qoladi; dublikatlar `dup_of` maydoni bilan belgilanadi.
    """
    seen: dict = {}
    out = []
    for it in (ranked or []):
        fp = _fingerprint(it.get("content", ""))
        if fp in seen:
            dup = dict(it)
            dup["dup_of"] = seen[fp]
            out.append(dup)
            continue
        seen[fp] = it.get("layer", "?")
        out.append(dict(it))
    return out


def build_context(layers: dict, task: str, min_score: float = 0.12,
                  max_items: int = 12) -> tuple:
    """To'liq pipeline: rank → dedup → limit.

    Qaytadi: (kept_items, stats{ranked, dropped_irrelevant, duplicates,
    dropped_limit}) — stats observability uchun.
    """
    ranked = rank_context_layers(layers, task, min_score=min_score)
    deduped = dedup_layers(ranked)
    dups = sum(1 for it in deduped if "dup_of" in it)
    clean = [it for it in deduped if "dup_of" not in it]
    kept = clean[:max_items]
    stats = {
        "ranked": len(ranked),
        "dropped_irrelevant": 0,  # rank ichida filtrlandi — taxminiy hisob
        "duplicates": dups,
        "dropped_limit": max(0, len(clean) - max_items),
    }
    # dropped_irrelevant aniq bo'lishi uchun qayta hisoblaymiz
    all_items = 0
    for layer in ("system", "user", "memory", "history"):
        val = layers.get(layer)
        if isinstance(val, (list, tuple)):
            all_items += len(val)
        elif val:
            all_items += 1
    stats["dropped_irrelevant"] = max(0, all_items - stats["ranked"] - dups)
    return kept, stats
