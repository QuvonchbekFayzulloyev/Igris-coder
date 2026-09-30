"""
CODER AGENT MEMORY — L4 Retrieval Pipeline
BM25 keyword search + FAISS vector search + RRF hybrid fusion.

1.5B optimization:
- BM25 as primary (zero model overhead)
- FAISS optional (MiniLM-L6-v2 80MB)
- LRU session cache
- Query rewriter (rule-based, no LLM)
"""

import json
import math
import os
import re
import time
from collections import OrderedDict
from typing import Any, Optional


# ============================================================
# BM25 KEYWORD INDEX
# ============================================================

# Roadmap v2 A3 (§5): O'zbekcha morfologiya yordamchisi.
# BM25/FTS5 tokenizatsiyasi morfologiyasiz — "kitoblarni" "kitob"ga mos
# kelmaydi. Yechim: index VA query tomonda bir xil yengil stemmer.

# O'zbek tilidagi eng ko'p uchraydigan qo'shimchalar (uzunligi bo'yicha
# kamayish tartibida — iterativ kesish uchun). Affiks almashinuvi (k→g,
# q→', p→b) bilan birga.
_UZ_SUFFIXES = (
    "laridagilardan", "laridagi", "dagilardan", "liklaridan", "imizdan",
    "lardan", "lariga", "larini", "larida", "larda", "dagi", "ganlar",
    "larin", "larin", "im_ga", "imiz", "ingiz", "lari", "larni", "lar",
    "ning", "nik", "lik", "gan", "magan", "ayotgan", "yotgan", "ilgan",
    "uvchi", "vchi", "ish", "dan", "dun", "kan", "gan", "ga", "qa",
    "da", "ta", "ni", "ning", "im", "iz", "ing", "i", "u", "a",
)
# yakka takror: to'plam — tez tekshiruv uchun (protsessda tartib muhim,
# tuple'dan foydalanamiz)

_UZ_CONSONANT_FRONT = {"k": "g", "q": "'", "p": "b", "t": "d"}


def uz_stem(word: str) -> str:
    """Yengil o'zbekcha stemmer — qo'shimchalarni kesadi (affiks almashinuvi bilan).

    Qoidalar:
      - so'z (2+ bo'g'in) qisqarmasdan keyin kamida 3 belgi qolishi kerak
      - uzun suffiks birinchi tekshiriladi (iterativ, max 2 bosqich)
      - k/q/p/t tugashida affiks almashinuvi (kitoblarni→kitob, kitobk→xato)

    Bu to'liq morfologik tahlil EMAS — recall uchun maqsad "kitoblarni" va
    "kitob" bir index kalitiga tushishi. Deterministik, stdlib faqat.
    """
    w = (word or "").strip().lower()
    if len(w) < 5:  # qisqa so'zlar allaqachon ildizga yaqin
        return w
    # max 3 bosqich kesish: "kitoblarimdagi" (dagi→im→lar) kabi zanjirlar uchun
    for _ in range(3):
        changed = False
        for suf in _UZ_SUFFIXES:
            if len(w) - len(suf) >= 3 and w.endswith(suf):
                w = w[: len(w) - len(suf)]
                changed = True
                break
        if not changed:
            break
    # affiks almashinuvi: kesilgandan keyingi oxirgi undosh
    if w[-1:] in _UZ_CONSONANT_FRONT:
        w = w[:-1] + _UZ_CONSONANT_FRONT[w[-1]]
        # ba'zan almashinuvdan keyin ham suffix qoldig'i bo'ladi (kitob+ni → kitob)
        for suf in ("ni", "i", "ga", "da"):
            if len(w) - len(suf) >= 3 and w.endswith(suf):
                w = w[: len(w) - len(suf)]
                break
    return w


class BM25Index:
    """
    BM25 keyword search index.
    Zero model overhead, works with any LLM.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: list[list[str]] = []
        self.metadata: list[dict] = []
        self.doc_freqs: dict[str, int] = {}
        self.avg_dl: float = 0.0
        self.total_docs: int = 0
        self._built = False

    def tokenize(self, text: str) -> list[str]:
        """Tokenization + A3: o'zbekcha yengil stemming + apostrof normalizatsiya.

        Har token: asl shakli + stem (ikkalasi ham kalit bo'ladi) — leksik
        moslik yo'qolmaydi, morfologik moslik QO'SHILADI. Document va query
        tomonda bir xil qo'llaniladi.

        Apostrof (o'qish/g'oya, to'g'ri yozuvda ʻ/ʼ/'): bo'shliq EMAS,
        O'CHIRILADI — 'o'qish' va 'oqish' bir token ('oqish') bo'ladi.
        """
        text = text.lower()
        # A3: apostrof turlari (', ', ʻ, ʼ, `) — so'z ichida bo'lsa ham olib tashlanadi
        text = re.sub(r"[\u0027\u2018\u2019\u02bc\u02ee\u0060]", "", text)
        text = re.sub(r"[^\w\s]", " ", text)
        raw = [t for t in text.split() if len(t) > 1]
        out: list[str] = []
        seen: set[str] = set()
        for t in raw:
            if t not in seen:
                seen.add(t)
                out.append(t)
            s = uz_stem(t)
            if s != t and len(s) > 1 and s not in seen:
                seen.add(s)
                out.append(s)
        return out

    def add_document(self, content: str, metadata: Optional[dict] = None):
        """Add a document to the index."""
        tokens = self.tokenize(content)
        if len(tokens) < 2:
            return

        self.documents.append(tokens)
        self.metadata.append(metadata or {"source": "unknown"})

        # Update document frequencies
        unique_tokens = set(tokens)
        for token in unique_tokens:
            self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1

        self.total_docs += 1
        self._built = False

    def build(self):
        """Pre-compute average document length."""
        if not self.documents:
            return
        total_len = sum(len(doc) for doc in self.documents)
        self.avg_dl = total_len / len(self.documents)
        self._built = True

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Search the index using BM25 scoring.
        
        Returns:
            List of {"score": float, "metadata": dict, "index": int}
        """
        if not self.documents:
            return []

        if not self._built:
            self.build()

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        scores = []
        for i, doc in enumerate(self.documents):
            score = self._score_document(query_tokens, doc, i)
            if score > 0:
                scores.append((score, i))

        scores.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, idx in scores[:top_k]:
            results.append({
                "score": score,
                "metadata": self.metadata[idx],
                "index": idx,
            })
        return results

    def _score_document(self, query_tokens: list[str], doc: list[str], doc_idx: int) -> float:
        """Calculate BM25 score for a document."""
        doc_len = len(doc)
        score = 0.0

        for qt in query_tokens:
            if qt not in self.doc_freqs:
                continue

            # IDF
            df = self.doc_freqs[qt]
            idf = math.log((self.total_docs - df + 0.5) / (df + 0.5) + 1)

            # TF in document
            tf = doc.count(qt)

            # BM25 formula
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self.avg_dl, 1))
            score += idf * numerator / denominator

        return score

    def get_stats(self) -> dict:
        return {
            "total_documents": self.total_docs,
            "unique_terms": len(self.doc_freqs),
            "avg_doc_length": self.avg_dl,
        }

    def remove_source(self, source: str) -> int:
        """Berilgan `source` metadata'ga ega hujjatlarni index'dan o'chiradi.

        T2 (mtime cache): fayl o'zgarganda eski versiyasi o'chirilib, yangisi
        qo'shiladi — to'liq rebuild Yo'Q. `doc_freqs` va `avg_dl` qayta
        hisoblanadi (O(N) faqat o'chirilganda; add_document'dagi kabi).

        Qaytaradi: o'chirilgan hujjatlar soni.
        """
        keep_docs: list[list[str]] = []
        keep_meta: list[dict] = []
        removed = 0
        for doc, meta in zip(self.documents, self.metadata):
            if isinstance(meta, dict) and meta.get("source") == source:
                removed += 1
                continue
            keep_docs.append(doc)
            keep_meta.append(meta)
        if not removed:
            return 0
        self.documents = keep_docs
        self.metadata = keep_meta
        # doc_freqs qayta hisoblash
        self.doc_freqs = {}
        for doc in self.documents:
            for term in set(doc):
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1
        self.total_docs = len(self.documents)
        self.avg_dl = (
            sum(len(doc) for doc in self.documents) / self.total_docs
            if self.total_docs else 0.0
        )
        self._built = True  # statistikalar yangi — rebuild shart emas
        return removed


# ============================================================
# VECTOR INDEX (FAISS - optional)
# ============================================================

# Roadmap v2 A1: hash-based DETERMINISTIC embedding fallback.
# MiniLM/FAISS o'rnatilmagan holatda ham vector search ishlashi kerak
# (avval: model yo'q bo'lsa search() JIM bo'sh qaytarardi — T3 "ishlamaydi").
# Yondashuv: char 3-4-gram hash signaturasi → normallashtirilgan vektor
# (sketch/n-gram hashing). Kosinus o'xshashlik sharh bilan taqqoslanadi.

def _hash_embedding(text: str, dim: int = 384) -> list[float]:
    """Deterministik, model-siz embedding: char n-gram hashing sketch.

    - 3 va 4-gram'lar (pastki registr, faqat [a-z0-9' ] qoladi)
    - Har gram stabil FNV-1a hash → bucket indeksi, ±1 sign (hash mod 2)
    - Bucketlarga qo'shish → L2 normallashtirish → kosinusga tayyor
    Xususiyatlari: tez (~100KB/s dan yuqori), izchil (ayni matn → ayni
    vektor), modul-tashqisiz (faqat stdlib). Semantik chuqurlik MiniLM'dan
    past, lekin leksik parafrazalar/morfologik o'zgarishlarni tutadi.
    """
    vec = [0.0] * dim
    low = re.sub(r"[^\w\s]", " ", (text or "").lower())
    low = re.sub(r"\s+", " ", low).strip()
    if not low:
        return vec
    grams: list[str] = []
    for n in (3, 4):
        padded = f" {low} "
        for i in range(len(padded) - n + 1):
            grams.append(padded[i:i + n])
    for g in grams:
        h = 2166136261  # FNV-1a offset basis
        for ch in g:
            h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
        idx = h % dim
        sign = 1.0 if (h >> 31) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def _cosine(a: list[float], b: list[float]) -> float:
    """Pure-python kosinus (numpy shart emas; dim=384 uchun tez yetarli)."""
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / math.sqrt(na * nb)


class VectorIndex:
    """
    Vector similarity search using FAISS.
    Optional: falls back to cosine similarity if FAISS not available.

    Roadmap v2 A1: uchinchi qatlam — HASH-BASED deterministic embedding.
    Zanjir: MiniLM (semantic, eng sifatli) → hash sketch (deterministik,
    offline kafolat). Model yo'q bo'lsa ham search() endi JIM BO'SH
    QAYTARMAYDI — hash sketch natija beradi (T3 "ishlamaydi" muammosi
    yopildi). `_embedding_mode`: "minilm" | "hash".
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.vectors: list[list[float]] = []
        self.metadata: list[dict] = []
        self._model = None
        self._use_faiss = False
        self._faiss_index = None
        # A1: embedding rejimi — build() da aniqlanadi ("minilm" yoki "hash")
        self._embedding_mode = "none"

        # Try to load FAISS
        try:
            import faiss
            import numpy as np
            self._faiss_available = True
        except ImportError:
            self._faiss_available = False

    def _get_model(self):
        """Lazy-load sentence transformer model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                pass
        return self._model

    def add_document(self, content: str, metadata: Optional[dict] = None):
        """Add a document (will be embedded on search)."""
        self.vectors.append(content)  # Store raw text for now
        self.metadata.append(metadata or {"source": "unknown"})

    def build(self):
        """Build index from stored texts.

        A1: avval MiniLM sinanadi (semantic sifat); o'rnatilmagan bo'lsa —
        HASH-BASED sketch bilan barcha hujjatlar embedding qilinadi
        (deterministik, stdlib faqat). Endi hech qanday holatda jim
        ishdan chiqmaydi.
        """
        if not self.vectors:
            return

        model = self._get_model()
        if model is not None:
            try:
                import numpy as np

                # Encode all documents
                texts = [v if isinstance(v, str) else str(v) for v in self.vectors]
                embeddings = model.encode(texts, batch_size=64, show_progress_bar=False)
                embeddings = np.array(embeddings).astype("float32")

                if self._faiss_available:
                    import faiss
                    self._faiss_index = faiss.IndexFlatIP(self.dimension)
                    self._faiss_index.add(embeddings)
                    self._use_faiss = True
                else:
                    # Store embeddings for manual cosine similarity
                    self.vectors = embeddings.tolist()
                self._embedding_mode = "minilm"
                return
            except Exception:
                pass

        # A1 FALLBACK: hash-based deterministic sketch (model yo'q / xato).
        # remove_source() bilan mos bo'lishi uchun vektorlar `self.vectors`
        # ichida saqlanadi (docs o'rniga) — remove_source vektorlarni filtrlaydi.
        self._use_faiss = False
        self._faiss_index = None
        self.vectors = [_hash_embedding(v if isinstance(v, str) else str(v), self.dimension)
                        for v in self.vectors]
        self._embedding_mode = "hash"

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search using vector similarity.

        A1: uch rejim —
          1) FAISS + MiniLM embeddings (eng sifatli)
          2) MiniLM embeddings + pure/numpy cosine
          3) HASH sketch + pure-python cosine (offline kafolat — endi default)
        Model bo'lmasa JIM BO'SH QAYTARMAYDI — hash sketch ishlaydi.
        """
        if not self.metadata:
            return []

        # REJIM 3: hash sketch (model yo'q yoki build hash rejimida bo'ldi)
        if self._embedding_mode == "hash" or (self._model is None and not self._use_faiss):
            # build() chaqirilmagan bo'lsa ham ishlashi uchun lazily embed qilamiz
            if self.vectors and not isinstance(self.vectors[0], list):
                self.build()
            if not self.vectors or not isinstance(self.vectors[0], list):
                return []
            qvec = _hash_embedding(query, self.dimension)
            scored = []
            for i, dvec in enumerate(self.vectors):
                sim = _cosine(qvec, dvec)
                if sim > 0.05:  # hash sketch noise floor
                    scored.append((sim, i))
            scored.sort(key=lambda t: t[0], reverse=True)
            return [
                {"score": float(s), "metadata": self.metadata[i], "index": i}
                for s, i in scored[:top_k]
            ]

        model = self._get_model()
        if model is None:
            return []

        try:
            import numpy as np

            query_embedding = model.encode([query]).astype("float32")

            if self._use_faiss and self._faiss_index is not None:
                scores, indices = self._faiss_index.search(query_embedding, min(top_k, len(self.metadata)))
                results = []
                for score, idx in zip(scores[0], indices[0]):
                    if idx >= 0:
                        results.append({
                            "score": float(score),
                            "metadata": self.metadata[idx],
                            "index": int(idx),
                        })
                return results
            elif isinstance(self.vectors, list) and len(self.vectors) > 0:
                # Manual cosine similarity
                doc_vectors = np.array(self.vectors)
                query_vec = query_embedding.flatten()
                doc_norms = np.linalg.norm(doc_vectors, axis=1)
                query_norm = np.linalg.norm(query_vec)
                if query_norm > 0 and np.all(doc_norms > 0):
                    similarities = (doc_vectors @ query_vec) / (doc_norms * query_norm)
                    top_indices = np.argsort(similarities)[::-1][:top_k]
                    return [
                        {
                            "score": float(similarities[i]),
                            "metadata": self.metadata[i],
                            "index": int(i),
                        }
                        for i in top_indices
                        if similarities[i] > 0
                    ]
        except Exception:
            pass

        return []

    def remove_source(self, source: str) -> int:
        """Berilgan `source` metadata'ga ega hujjatlarni o'chiradi (T2).

        FAISS'dan ayrim rowid o'chirib bo'lmaydi (IndexFlat) — index tozalanadi
        (qayta qurish keyingi build() da). Recall vaqtinchalik kamayishi
        mumkin; keyword index (FTS5/BM25) asosiy qidiruv qatlami.

        Qaytaradi: o'chirilgan hujjatlar soni.
        """
        keep_vectors: list = []
        keep_meta: list[dict] = []
        removed = 0
        for vec, meta in zip(self.vectors, self.metadata):
            if isinstance(meta, dict) and meta.get("source") == source:
                removed += 1
                continue
            keep_vectors.append(vec)
            keep_meta.append(meta)
        if not removed:
            return 0
        self.vectors = keep_vectors
        self.metadata = keep_meta
        if self._faiss_index is not None:
            self._faiss_index = None
            self._use_faiss = False
        return removed

    def get_stats(self) -> dict:
        return {
            "total_documents": len(self.metadata),
            "dimension": self.dimension,
            "faiss_available": self._faiss_available,
            "faiss_index_built": self._use_faiss,
            # A1: qaysi embedding rejimi ishlayapti ("minilm" | "hash" | "none")
            "embedding_mode": self._embedding_mode,
        }


# ============================================================
# HYBRID SEARCH (RRF Fusion)
# ============================================================

class HybridSearch:
    """
    Hybrid search combining BM25 + Vector with Reciprocal Rank Fusion.
    
    RRF formula: score = 1 / (k + rank) for each ranking
    """

    def __init__(self, rrf_k: int = 60):
        self.rrf_k = rrf_k
        # T1 optimization (2026-09-12): BM25Index o'rniga FTS5Index —
        # incremental insert (har add_document'da rebuild YO'Q), diskda
        # saqlanadi (restart'da qayta yuklash kerak emas). Interfeys bir xil:
        # add_document/build/search/get_stats. FTS5 yo'q bo'lsa avtomatik
        # asl BM25Index ga qaytadi (fts5_index.py ichida).
        self.bm25 = self._make_keyword_index()
        self.vector = VectorIndex()

    def _make_keyword_index(self):
        """FTS5Index yaratadi; imkoni bo'lmasa asl BM25Index (hech qachon crash yo'q).

        Import izchilligi: fts5_index.py bu papkada (memory/) yashaydi, lekin
        MemoryBridge faqat Igris_Memory ildizini sys.path'ga qo'shadi — shu
        sababli yalang'ich `from fts5_index import ...` ishlab turgan serverda
        topilmasdi (jim BM25 fallback). Endi: 1) shu papkani sys.path'ga
        qo'shamiz, 2) paket-ichki nisbiy import ham sinab ko'ramiz.
        """
        try:
            try:
                from fts5_index import FTS5Index
            except ImportError:
                import os as _os, sys as _sys
                _here = _os.path.dirname(_os.path.abspath(__file__))
                if _here not in _sys.path:
                    _sys.path.insert(0, _here)
                from fts5_index import FTS5Index
            return FTS5Index()
        except Exception as exc:
            # S3: FTS5 yo'q bo'lsa BM25 ga qaytish ENDI JIM EMAS —
            # /api/system/services'da ko'rinadi (3-6x sekinlik = muhim signal).
            try:
                import sys as _sys2
                if ".." not in [p for p in _sys2.path]:
                    _brain = _os.path.normpath(_os.path.join(_here, "..", "..", "Igris_brain"))
                    if _os.path.isdir(_brain) and _brain not in _sys2.path:
                        _sys2.path.insert(0, _brain)
                from monitor.degradation import mark
                mark("memory.keyword-index", str(exc)[:300], fallback="BM25Index")
            except Exception:
                pass
            return BM25Index()

    def add_document(self, content: str, metadata: Optional[dict] = None):
        """Add a document to both indexes."""
        self.bm25.add_document(content, metadata)
        self.vector.add_document(content, metadata)

    def build(self):
        """Build both indexes."""
        self.bm25.build()
        self.vector.build()

    def remove_source(self, source: str) -> int:
        """Ikkala index'dan `source` hujjatlarni o'chiradi (T2 mtime cache).

        Qaytaradi: o'chirilgan hujjatlar soni (bm25 + vector, max ikkalasi).
        """
        removed = 0
        try:
            removed += self.bm25.remove_source(source)
        except Exception:
            pass
        try:
            removed += self.vector.remove_source(source)
        except Exception:
            pass
        return removed

    def search(self, query: str, top_k: int = 5, use_vector: bool = True) -> list[dict]:
        """
        Search using RRF fusion of BM25 + Vector results.
        
        Args:
            query: Search query
            top_k: Number of results to return
            use_vector: Whether to use vector search (can disable for speed)
        
        Returns:
            Fused results sorted by RRF score
        """
        # Get BM25 results (always available)
        bm25_results = self.bm25.search(query, top_k=top_k * 3)

        # Get vector results (optional)
        vector_results = []
        if use_vector:
            vector_results = self.vector.search(query, top_k=top_k * 3)

        # RRF fusion
        all_sources: dict[str, dict] = {}

        # Process BM25 results
        for rank, result in enumerate(bm25_results):
            key = result["metadata"].get("source", str(result["index"]))
            if key not in all_sources:
                all_sources[key] = {
                    "source": key,
                    "ranks": [],
                    "metadata": result["metadata"],
                }
            all_sources[key]["ranks"].append(rank + 1)

        # Process vector results
        for rank, result in enumerate(vector_results):
            key = result["metadata"].get("source", str(result["index"]))
            if key not in all_sources:
                all_sources[key] = {
                    "source": key,
                    "ranks": [],
                    "metadata": result["metadata"],
                }
            all_sources[key]["ranks"].append(len(bm25_results) + rank + 1)

        # Calculate RRF scores
        results = []
        for key, data in all_sources.items():
            rrf_score = sum(1.0 / (self.rrf_k + r) for r in data["ranks"])
            results.append({
                "score": rrf_score,
                "source": data["source"],
                "metadata": data["metadata"],
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_stats(self) -> dict:
        return {
            "bm25": self.bm25.get_stats(),
            "vector": self.vector.get_stats(),
            "rrf_k": self.rrf_k,
        }


# ============================================================
# QUERY REWRITER (Rule-based)
# ============================================================

class QueryRewriter:
    """
    Rule-based query rewriter for 1.5B models.
    No LLM needed - pure rule-based expansion.
    """

    def __init__(self):
        self.expansion_rules = {
            "auth": ["authentication", "login", "jwt", "token"],
            "error": ["error", "exception", "bug", "fail"],
            "test": ["test", "spec", "unit", "integration"],
            "db": ["database", "sql", "query", "model"],
            "perf": ["performance", "speed", "slow", "optimize"],
            "api": ["endpoint", "route", "request", "response"],
            "ui": ["interface", "frontend", "component", "style"],
            "deploy": ["deploy", "build", "release", "ci", "cd"],
            "security": ["auth", "encrypt", "hash", "token", "csrf"],
        }

        self.simplify_rules = [
            (r"could you please", ""),
            (r"how do I", "how to"),
            (r"can you", ""),
            (r"please", ""),
            (r"implement", "code"),
            (r"fix", "debug"),
        ]

    def rewrite(self, query: str) -> list[str]:
        """
        Rewrite query with expansions.
        
        Returns:
            List of query variations (original + expanded)
        """
        original = query.lower().strip()
        queries = [original]

        # Expand based on rules
        expanded = original
        for term, synonyms in self.expansion_rules.items():
            if term in original:
                expanded += " " + " ".join(synonyms)

        if expanded != original:
            queries.append(expanded)

        return queries

    def simplify(self, query: str) -> str:
        """Simplify query by removing polite phrases."""
        for pattern, replacement in self.simplify_rules:
            query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", query).strip()

    def extract_keywords(self, query: str, max_keywords: int = 10) -> list[str]:
        """Extract top keywords from query."""
        words = self.simplify(query).lower().split()
        # Remove stop words
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                       "have", "has", "had", "do", "does", "did", "will", "would", "could",
                       "should", "may", "might", "shall", "can", "need", "dare", "ought",
                       "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
                       "as", "into", "through", "during", "before", "after", "above", "below",
                       "between", "out", "off", "over", "under", "again", "further", "then",
                       "once", "here", "there", "when", "where", "why", "how", "all", "both",
                       "each", "few", "more", "most", "other", "some", "such", "no", "nor",
                       "not", "only", "own", "same", "so", "than", "too", "very", "just"}
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return keywords[:max_keywords]


# ============================================================
# LRU SESSION CACHE
# ============================================================

class SessionCache:
    """
    LRU cache for session-level query results.
    Max 50 entries, TTL-based expiration.
    """

    def __init__(self, max_size: int = 50, ttl_seconds: int = 1800):
        self.cache: OrderedDict[str, dict] = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl_seconds
        self.stats = {"hits": 0, "misses": 0}

    def get(self, key: str) -> Optional[list[dict]]:
        """Get cached results."""
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["time"] < self.ttl:
                self.cache.move_to_end(key)
                self.stats["hits"] += 1
                return entry["value"]
            else:
                del self.cache[key]
        self.stats["misses"] += 1
        return None

    def set(self, key: str, value: list[dict]):
        """Cache results."""
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = {"value": value, "time": time.time()}

    def invalidate(self, pattern: str):
        """Invalidate entries matching pattern."""
        keys_to_delete = [k for k in self.cache if pattern in k]
        for key in keys_to_delete:
            del self.cache[key]

    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()

    def get_stats(self) -> dict:
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total if total > 0 else 0
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": hit_rate,
        }


# ============================================================
# RETRIEVAL PIPELINE (orchestrator)
# ============================================================

class RetrievalPipeline:
    """
    Complete retrieval pipeline combining all search methods.
    
    Pipeline:
    1. Query rewrite (expand/simplify)
    2. Cache check
    3. BM25 search (primary)
    4. Vector search (optional)
    5. RRF fusion
    6. Cache store
    """

    def __init__(self):
        self.hybrid = HybridSearch()
        self.rewriter = QueryRewriter()
        self.cache = SessionCache()
        self._loaded = False
        # T2 (mtime cache): fayl yo'li -> (mtime, size) xaritasi.
        # load_documents qayta chaqirilganda FAQAT o'zgargan/yangi fayllar
        # o'qiladi va index'ga qo'shiladi; o'zgargan faylning eski versiyasi
        # index'dan o'chiriladi (remove_source). O'zgarmagan fayllar
        # o'chirib-qo'shilmaydi (dedup ham bor, lekin o'qish/skan tejaladi).
        self._file_state: dict[str, tuple[float, int]] = {}

    def load_documents(self, memory_dir: str, force: bool = False):
        """
        Load all .md and .json files from memory directory.

        T2: mtime cache — faqat o'zgargan fayllar qayta indekslanadi.
        `force=True` — barcha fayllarni qayta o'qish (cache bekor).

        Args:
            memory_dir: Path to memory directory (e.g., "memory/")
            force: Skip mtime cache and re-index everything
        """
        if not os.path.exists(memory_dir):
            return

        dir_prefix = os.path.normpath(memory_dir) + os.sep
        seen_paths: set[str] = set()

        for root, dirs, files in os.walk(memory_dir):
            for fname in files:
                if fname.endswith((".md", ".json", ".jsonl")):
                    fpath = os.path.join(root, fname)
                    fpath_norm = os.path.normpath(fpath)
                    seen_paths.add(fpath_norm)
                    try:
                        st = os.stat(fpath)
                        mtime, size = st.st_mtime, st.st_size
                    except OSError:
                        continue
                    prev = self._file_state.get(fpath_norm)
                    if not force and prev == (mtime, size):
                        continue  # o'zgarmagan — o'tkazib yuborish
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            content = f.read()
                        if len(content.strip()) > 10:
                            source_key = fpath_norm
                            # O'zgargan fayl: eski versiyani index'dan o'chirish
                            if prev is not None:
                                self.hybrid.remove_source(source_key)
                            self.hybrid.add_document(
                                content,
                                {"source": source_key, "type": fname.split(".")[-1]},
                            )
                            self._file_state[fpath_norm] = (mtime, size)
                    except Exception:
                        pass

        # O'chirilgan fayllarni index'dan ham o'chirish
        stale = [p for p in self._file_state
                 if p.startswith(dir_prefix) and p not in seen_paths]
        for p in stale:
            try:
                self.hybrid.remove_source(p)
            except Exception:
                pass
            self._file_state.pop(p, None)

        self.hybrid.build()
        self._loaded = True

    def search(self, query: str, top_k: int = 5, use_cache: bool = True) -> list[dict]:
        """
        Search memory with full pipeline.
        
        Args:
            query: Search query
            top_k: Number of results
            use_cache: Whether to use session cache
        
        Returns:
            List of search results
        """
        # 1. Check cache
        cache_key = f"{query}:{top_k}"
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # 2. Rewrite query
        queries = self.rewriter.rewrite(query)

        # 3. Search with all query variations
        all_results = {}
        for q in queries:
            results = self.hybrid.search(q, top_k=top_k * 2)
            for r in results:
                key = r.get("source", "")
                if key not in all_results or r["score"] > all_results[key]["score"]:
                    all_results[key] = r

        # 4. Sort and limit
        final_results = sorted(all_results.values(), key=lambda x: x["score"], reverse=True)[:top_k]

        # 5. Cache results
        if use_cache:
            self.cache.set(cache_key, final_results)

        return final_results

    def search_memory(
        self,
        query: str,
        l1_memory=None,
        l2_memory=None,
        top_k: int = 5,
    ) -> dict:
        """
        Search across all memory layers.
        
        Args:
            query: Search query
            l1_memory: RuntimeMemory instance (optional)
            l2_memory: PersistentMemory instance (optional)
            top_k: Number of results per layer
        
        Returns:
            Dict with results from each layer
        """
        results = {"l1": [], "l2": [], "retrieval": [], "query": query}

        # Search L1 (runtime)
        if l1_memory:
            for type_name in ["short-turn", "active-context", "task-memory", "observation-memory"]:
                entries = l1_memory.read(type_name, limit=2)
                for entry in entries:
                    if query.lower() in json.dumps(entry, ensure_ascii=False).lower():
                        results["l1"].append({"type": type_name, "entry": entry})

        # Search L2 (persistent)
        if l2_memory:
            l2_results = l2_memory.search(query, limit=top_k)
            results["l2"] = l2_results

        # Search retrieval pipeline
        if self._loaded:
            results["retrieval"] = self.search(query, top_k=top_k)

        return results

    def get_stats(self) -> dict:
        return {
            "hybrid": self.hybrid.get_stats(),
            "cache": self.cache.get_stats(),
            "loaded": self._loaded,
        }
