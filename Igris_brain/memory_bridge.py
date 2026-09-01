"""
IGRIS BRAIN — Memory Bridge
===========================
Connects the brain (deterministic bricks + Ollama LLM) to Igris_Memory
(L1 runtime, L2 persistent, L4 retrieval) for RAG-style recall and
automatic remembering of every resolution.

Features
--------
- recall(query)   -> RAG context string assembled from memory + vault notes
- remember(...)   -> persist query/result pairs (bounded, duplicate-safe)
- on_resolve()    -> post-resolution hook: remember + trigger memory hooks
- session start/end + status
- graceful degradation: if Igris_Memory is unavailable the bridge stays
  disabled and every call is a no-op (the brain still works).

Layout
------
Igris_Memory/
    brain_data/          <- data created by this bridge (runtime/persistent/...)
    memory/              <- the memory package itself (imported, not written)
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from typing import Optional

from safety import has_suspicious, sanitize  # noqa: E402  (N2: RAG kontekst tozalash)

HERE = os.path.dirname(os.path.abspath(__file__))
MEMORY_ROOT = os.path.normpath(os.path.join(HERE, "..", "Igris_Memory"))
DEFAULT_BASE_DIR = os.path.join(MEMORY_ROOT, "brain_data")


class MemoryBridge:
    """RAG + persistence bridge into Igris_Memory."""

    def __init__(self, enabled: bool = True, session_id: str = "", base_dir: str = ""):
        self.enabled = False
        self.manager = None
        self._error = ""
        self.base_dir = base_dir or DEFAULT_BASE_DIR
        self._latency: dict[str, float] = {}   # op -> avg ms (benchmark)
        # Part N: korpus yuklanishi BACKGROUND thread'da — agent init / birinchi
        # /api/status bloklanmaydi (noto'g'ri "offline" ko'rinmaydi). `recall`
        # yuklanish tugashini kutadi (max 3s).
        self._load_done = threading.Event()

        if not enabled:
            return
        try:
            if MEMORY_ROOT not in sys.path:
                sys.path.insert(0, MEMORY_ROOT)
            from memory import MemoryManager  # Igris_Memory/memory/__init__.py

            self.manager = MemoryManager(base_dir=self.base_dir)
            self.enabled = True
            if session_id:
                self.start_session(session_id)
            # RAG corpus (memory data + Obsidian vault notes) — background'da
            # bo'laklab yuklanadi; dastlabki so'rovlar tez javob beradi.
            dirs = (self.base_dir, MEMORY_ROOT)
            bg = threading.Thread(target=self._bg_load_corpus, args=(dirs,),
                                  daemon=True, name="memory-corpus-load")
            bg.start()
        except Exception as exc:  # pragma: no cover - defensive
            self._error = str(exc)
            self.enabled = False

    def _bg_load_corpus(self, dirs: tuple) -> None:
        """Korpusni bo'laklab yuklaydi (har papka alohida try bilan)."""
        try:
            for d in dirs:
                try:
                    if self.manager is not None:
                        self.manager.retrieval.load_documents(d)
                except Exception:
                    pass
        finally:
            self._load_done.set()

    def _ensure_loaded(self) -> None:
        """RAG korpus yuklanishini kutadi (max 5s) — recall to'liq natija beradi."""
        if not self._load_done.is_set():
            self._load_done.wait(timeout=5.0)

    # ------------------------------------------------------------ #
    # Sessions
    # ------------------------------------------------------------ #

    def start_session(self, session_id: str = "") -> dict:
        if not self.enabled:
            return {"status": "disabled"}
        return self.manager.start_session(session_id)

    def end_session(self, summary: str = "") -> dict:
        if not self.enabled:
            return {"status": "disabled"}
        return self.manager.end_session(summary)

    # ------------------------------------------------------------ #
    # RAG recall
    # ------------------------------------------------------------ #

    def recall(self, query: str, top_k: int = 3, max_chars: int = 1600) -> tuple[str, int]:
        """Return (context_string, hit_count) from memory retrieval.

        N1/N2 xavfsizlik: har bir eslatma PoisoningProtection'da tekshiriladi;
        shubhali (injection) yozuvlar tashlab ketiladi, qolgani tozalanadi.
        """
        if not self.enabled:
            return "", 0
        t0 = time.perf_counter()
        try:
            # Part N: korpus yuklanishi tugashini kutamiz (max 3s) — search
            # bo'sh index'da ishlamasligi uchun.
            self._ensure_loaded()
            results = self.manager.search(query, top_k=top_k)
            entries = results.get("results", []) or []
            parts: list[str] = []
            for e in entries[:top_k]:
                if "entry" in e:                       # recall-format hit
                    entry = e.get("entry", {})
                    text = entry.get("content") or entry.get("summary") or json.dumps(entry, ensure_ascii=False)
                    src = f"{e.get('layer', '')}:{e.get('type', 'memory')}"
                    # N1: PoisoningProtection check_entry — suspicious bo'lsa bloklash
                    if not self._entry_safe(entry, src):
                        continue
                else:                                   # retrieval-format hit
                    src = str(e.get("source", "memory"))
                    text = self._read_source_snippet(src, 300)
                    if not text:                        # fallback: metadata only
                        text = json.dumps(e.get("metadata", {}), ensure_ascii=False)
                snippet = text if isinstance(text, str) else str(text)
                # N2: injection naqshlari bo'lsa — yozuvni kontekstga qo'shmaslik
                if has_suspicious(snippet):
                    continue
                parts.append(f"[{src}] {snippet[:300]}")
            joined = "\n".join(parts)
            self._latency["recall_ms"] = (time.perf_counter() - t0) * 1000
            return joined[:max_chars], len(parts)
        except Exception as exc:  # pragma: no cover - defensive
            self._error = str(exc)
            return "", 0

    def _entry_safe(self, entry: dict, src: str) -> bool:
        """N1: PoisoningProtection orqali yozuvni tekshiradi (suspicious -> False)."""
        try:
            if self.manager is not None and hasattr(self.manager, "check_security"):
                res = self.manager.check_security(entry)
                if isinstance(res, dict) and res.get("verdict") == "suspicious":
                    return False
        except Exception:
            pass
        return True

    @staticmethod
    def _read_source_snippet(src: str, limit: int = 300) -> str:
        """Read the first non-empty text lines of a memory/vault source file."""
        if not src or src.startswith("memory:"):
            return ""
        path = src
        try:
            if not os.path.isabs(path):
                path = os.path.join(MEMORY_ROOT, path)
            if not os.path.exists(path):
                return ""
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read(4000)
            lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            # skip YAML front-matter-ish lines (---, title:, tags:)
            body = [ln for ln in lines if not ln.startswith(("---", "title:", "tags:", "created:", "author:"))]
            return " ".join(body)[:limit]
        except Exception:
            return ""

    # ------------------------------------------------------------ #
    # Remember
    # ------------------------------------------------------------ #

    def remember(
        self,
        content: str,
        memory_type: str = "solution-memory",
        tags: Optional[list[str]] = None,
        summary: str = "",
    ) -> dict:
        """N1: yozishdan oldin PoisoningProtection tekshiruvi."""
        if not self.enabled:
            return {"status": "disabled"}
        # N1: shubhali kontentni xotiraga YOZMAYMIZ — zaharlanish oldini oladi.
        if has_suspicious(content or "") or has_suspicious(summary or ""):
            return {"status": "blocked", "reason": "suspicious content rejected by poisoning protection"}
        t0 = time.perf_counter()
        try:
            res = self.manager.api.remember(
                content[:2000],
                memory_type=memory_type,
                layer="l2",
                tags=tags or [],
                summary=(summary or content)[:200],
            )
            # make the new memory immediately retrievable (in-session RAG)
            try:
                self.manager.retrieval.hybrid.add_document(
                    content[:2000],
                    {"source": f"memory:{memory_type}", "type": memory_type},
                )
                # mark the BM25 index dirty so the next search rebuilds
                self.manager.retrieval.hybrid.bm25._built = False
            except Exception:
                pass
            self._latency["remember_ms"] = (time.perf_counter() - t0) * 1000
            return res
        except Exception as exc:  # pragma: no cover - defensive
            self._error = str(exc)
            return {"status": "error", "message": str(exc)}

    def on_resolve(self, query: str, result: dict) -> None:
        """Post-resolution hook: persist the exchange + fire memory hooks."""
        if not self.enabled:
            return
        out = result.get("output") or ""
        if not out:
            return
        try:
            engine = result.get("engine", "?")
            conf = result.get("confidence", 0.0)
            # L2: durable solution memory (duplicate-safe)
            self.remember(
                f"Q: {query}\nA: {out}",
                memory_type="solution-memory",
                tags=["brain", str(engine), "resolution"],
                summary=query[:120],
            )
            # L1: short-turn session continuity (N1: shubhali kontent yozilmaydi)
            if not has_suspicious(out or "") and not has_suspicious(query or ""):
                self.manager.api.remember(
                    out[:500],
                    memory_type="short-turn",
                    layer="l1",
                    tags=["turn"],
                    summary=query[:100],
                )
            # memory-level hooks (custom trigger 'on_resolve')
            self.manager.hooks.trigger("on_resolve", {
                "query": query,
                "engine": engine,
                "confidence": conf,
            })
        except Exception:  # pragma: no cover - never break the agent
            pass

    def remember_clarification(
        self,
        original_query: str,
        question: str,
        answer: str,
        session_id: str = "",
    ) -> None:
        """Clarification history ni xotiraga saqlaydi — kelajakda referens uchun.

        Har bir clarification exchange L2 xotiraga yoziladi:
          - Q: original query
          - Clarification question: agent so'ragan savol
          - Clarification answer: user javobi

        Keyingi marta shu yoki o'xshash so'rov kelganda, memory recall
        oldingi clarification tajribasini kontekstga qo'shadi — agent qayta
        so'rash o'rniga allaqachon javob olinganini biladi.
        """
        if not self.enabled or not (original_query and question and answer):
            return
        try:
            content = (
                f"Clarification exchange:\n"
                f"  Original query: {original_query}\n"
                f"  Question asked: {question}\n"
                f"  User answer: {answer}"
            )
            self.remember(
                content,
                memory_type="solution-memory",
                tags=["brain", "clarification", session_id or "anon"],
                summary=f"Clarification for '{original_query[:80]}': {answer[:80]}",
            )
            # L1 short-turn ga ham yozamiz — sessiya ichida tezkor
            try:
                self.manager.api.remember(
                    content[:500],
                    memory_type="short-turn",
                    layer="l1",
                    tags=["clarification", session_id or "anon"],
                    summary=f"Clarification: {question[:80]} -> {answer[:80]}",
                )
            except Exception:
                pass
            # memory-level hooks
            self.manager.hooks.trigger("on_clarification", {
                "original_query": original_query,
                "question": question,
                "answer": answer,
                "session_id": session_id,
            })
        except Exception:  # pragma: no cover - never break the agent
            pass

    def get_clarification_history(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[dict]:
        """Shu so'rovga oid oldingi clarification exchange'larni qidiradi.

        Qaytaradi: [{'original_query': str, 'question': str, 'answer': str}, ...]
        """
        if not self.enabled or not query:
            return []
        try:
            results = self.search(f"clarification {query}", top_k=top_k)
            items = results.get("results") or results.get("items") or []
            clarifications = []
            for item in items:
                content = item.get("content") or item.get("text") or ""
                if "Clarification exchange:" not in content:
                    continue
                # Parse clarification from stored content
                lines = content.split("\n")
                entry = {}
                for line in lines:
                    line = line.strip()
                    if line.startswith("Original query:"):
                        entry["original_query"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Question asked:"):
                        entry["question"] = line.split(":", 1)[1].strip()
                    elif line.startswith("User answer:"):
                        entry["answer"] = line.split(":", 1)[1].strip()
                if entry.get("question") and entry.get("answer"):
                    clarifications.append(entry)
            return clarifications[:top_k]
        except Exception:  # pragma: no cover
            return []

    def get_clarification_analytics(self) -> dict:
        """Clarification tahlilini qaytaradi — chastota, naqshlar, samaradorlik.

        Qaytaradi: {
          total_clarifications: int,
          total_questions: int,
          avg_questions_per_session: float,
          common_questions: [{'question': str, 'count': int}, ...],
          common_answers: [{'answer': str, 'count': int}, ...],
          clarification_rate: float,  # clarifications / total queries
          success_rate: float,        # sessions with clarification > 0
        }
        """
        if not self.enabled:
            return {
                "total_clarifications": 0,
                "total_questions": 0,
                "avg_questions_per_session": 0,
                "common_questions": [],
                "common_answers": [],
                "clarification_rate": 0,
                "success_rate": 0,
            }
        try:
            # Search for all clarification exchanges
            results = self.search("clarification", top_k=100)
            items = results.get("results") or results.get("items") or []

            total_clarifications = 0
            total_questions = 0
            questions_count: dict[str, int] = {}
            answers_count: dict[str, int] = {}

            for item in items:
                content = item.get("content") or item.get("text") or ""
                if "Clarification exchange:" not in content:
                    continue

                total_clarifications += 1
                total_questions += 1

                # Parse question and answer
                lines = content.split("\n")
                for line in lines:
                    line = line.strip()
                    if line.startswith("Question asked:"):
                        q = line.split(":", 1)[1].strip()
                        if q:
                            # Normalize question for counting
                            q_normalized = q.lower().rstrip("?").strip()
                            questions_count[q_normalized] = questions_count.get(q_normalized, 0) + 1
                    elif line.startswith("User answer:"):
                        a = line.split(":", 1)[1].strip()
                        if a:
                            # Normalize answer for counting (first 50 chars)
                            a_normalized = a[:50].lower().strip()
                            answers_count[a_normalized] = answers_count.get(a_normalized, 0) + 1

            # Sort by frequency
            common_questions = sorted(
                [{"question": q, "count": c} for q, c in questions_count.items()],
                key=lambda x: x["count"],
                reverse=True,
            )[:10]

            common_answers = sorted(
                [{"answer": a, "count": c} for a, c in answers_count.items()],
                key=lambda x: x["count"],
                reverse=True,
            )[:10]

            # Calculate rates (approximate — we don't have total queries here)
            avg_questions = (
                total_questions / total_clarifications
                if total_clarifications > 0
                else 0
            )

            return {
                "total_clarifications": total_clarifications,
                "total_questions": total_questions,
                "avg_questions_per_session": round(avg_questions, 2),
                "common_questions": common_questions,
                "common_answers": common_answers,
                "clarification_rate": 0,  # requires total queries context
                "success_rate": 0,  # requires outcome context
            }
        except Exception:  # pragma: no cover
            return {
                "total_clarifications": 0,
                "total_questions": 0,
                "avg_questions_per_session": 0,
                "common_questions": [],
                "common_answers": [],
                "clarification_rate": 0,
                "success_rate": 0,
            }

    # ------------------------------------------------------------ #
    # Status / helpers
    # ------------------------------------------------------------ #

    def status(self) -> dict:
        if not self.enabled:
            return {"enabled": False, "error": self._error}
        try:
            return {
                "enabled": True,
                "manager": self.manager.status(),
                "latency_ms": {k: round(v, 2) for k, v in self._latency.items()},
                "error": self._error or None,
            }
        except Exception as exc:  # pragma: no cover
            return {"enabled": True, "error": str(exc)}

    def search(self, query: str, top_k: int = 5) -> dict:
        if not self.enabled:
            return {"status": "disabled"}
        return self.manager.search(query, top_k=top_k)
