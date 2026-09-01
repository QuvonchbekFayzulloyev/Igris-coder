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
        """Simple whitespace + lowercase tokenization."""
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        return [t for t in text.split() if len(t) > 1]

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


# ============================================================
# VECTOR INDEX (FAISS - optional)
# ============================================================

class VectorIndex:
    """
    Vector similarity search using FAISS.
    Optional: falls back to cosine similarity if FAISS not available.
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.vectors: list[list[float]] = []
        self.metadata: list[dict] = []
        self._model = None
        self._use_faiss = False
        self._faiss_index = None

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
        """Build FAISS index from stored vectors."""
        model = self._get_model()
        if model is None or not self.vectors:
            return

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

        except Exception:
            pass

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search using vector similarity."""
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

    def get_stats(self) -> dict:
        return {
            "total_documents": len(self.metadata),
            "dimension": self.dimension,
            "faiss_available": self._faiss_available,
            "faiss_index_built": self._use_faiss,
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
        self.bm25 = BM25Index()
        self.vector = VectorIndex()

    def add_document(self, content: str, metadata: Optional[dict] = None):
        """Add a document to both indexes."""
        self.bm25.add_document(content, metadata)
        self.vector.add_document(content, metadata)

    def build(self):
        """Build both indexes."""
        self.bm25.build()
        self.vector.build()

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

    def load_documents(self, memory_dir: str):
        """
        Load all .md and .json files from memory directory.
        
        Args:
            memory_dir: Path to memory directory (e.g., "memory/")
        """
        if not os.path.exists(memory_dir):
            return

        for root, dirs, files in os.walk(memory_dir):
            for fname in files:
                if fname.endswith((".md", ".json", ".jsonl")):
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            content = f.read()
                        if len(content.strip()) > 10:
                            self.hybrid.add_document(
                                content,
                                {"source": fpath, "type": fname.split(".")[-1]},
                            )
                    except Exception:
                        pass

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
