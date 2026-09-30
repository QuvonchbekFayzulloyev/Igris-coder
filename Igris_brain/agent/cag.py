"""
IGRIS BRAIN — CAG (Cache-Augmented Generation)
==============================================
LLM javoblarini keshlash: bir xil (system, prompt) so'rov qayta kelsa,
LLM'ni qayta ishga tushirmasdan keshlangan javobni qaytaradi.

- Kalit: (system_prompt, user_prompt) sha256-hash
- LRU eviction (max_entries)
- TTL muddati (ttl_seconds)
- Invalidate: prefix / to'liq kalit bo'yicha
- Deterministik javoblarga mo'ljallangan (kreativ muhokama keshlamaydi)

Chat loop'iga ulanish:
    hit = cache.get(system, prompt)
    if hit is not None: return hit
    text = llm.complete(system=..., prompt=...)
    cache.put(system, prompt, text)
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from typing import Optional


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


class CagCache:
    def __init__(self, max_entries: int = 256, ttl_seconds: int = 1800):
        self.max_entries = max_entries
        self.ttl = ttl_seconds
        self._store: OrderedDict[str, dict] = OrderedDict()  # key -> {text, ts}
        self.stats = {"hits": 0, "misses": 0, "puts": 0, "invalidates": 0, "evictions": 0}

    # ------------------------------------------------------------ #
    # Core
    # ------------------------------------------------------------ #

    def _key(self, system: str, prompt: str) -> str:
        return _hash(system) + ":" + _hash(prompt)

    def get(self, system: str, prompt: str) -> Optional[str]:
        """Keshdan javob oladi (TTL o'tgan bo'lsa o'chiradi)."""
        key = self._key(system, prompt)
        entry = self._store.get(key)
        if entry is None:
            self.stats["misses"] += 1
            return None
        if time.time() - entry["ts"] > self.ttl:
            self._store.pop(key, None)
            self.stats["misses"] += 1
            return None
        self._store.move_to_end(key)  # LRU
        self.stats["hits"] += 1
        return entry["text"]

    def put(self, system: str, prompt: str, text: str) -> None:
        if not text or not text.strip():
            return
        key = self._key(system, prompt)
        self._store[key] = {"text": text, "ts": time.time()}
        self._store.move_to_end(key)
        self.stats["puts"] += 1
        self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)
            self.stats["evictions"] += 1

    # ------------------------------------------------------------ #
    # Invalidate
    # ------------------------------------------------------------ #

    def invalidate(self, key_prefix: str = "") -> int:
        """Kalit prefiksi bo'yicha o'chiradi; bo'sh bo'lsa hammasini."""
        before = len(self._store)
        if not key_prefix:
            self._store.clear()
        else:
            keys = [k for k in self._store if k.startswith(key_prefix)]
            for k in keys:
                self._store.pop(k, None)
        removed = before - len(self._store)
        self.stats["invalidates"] += removed
        return removed

    # ------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------ #

    def size(self) -> int:
        return len(self._store)

    def status(self) -> dict:
        total = self.stats["hits"] + self.stats["misses"]
        return {
            "size": self.size(),
            "max_entries": self.max_entries,
            "ttl_seconds": self.ttl,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": round(self.stats["hits"] / total, 3) if total else 0.0,
            "puts": self.stats["puts"],
            "invalidates": self.stats["invalidates"],
            "evictions": self.stats["evictions"],
        }

    def clear(self) -> None:
        self._store.clear()


DEFAULT_CAG = CagCache()
__all__ = ["CagCache", "DEFAULT_CAG"]
