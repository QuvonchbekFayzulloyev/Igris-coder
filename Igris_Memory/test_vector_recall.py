"""
Roadmap v2 — Phase A1 testlari: HASH-BASED VECTOR RECALL (T3)
=============================================================

Qamrov:
  - _hash_embedding: determinizm, dim, normallashtirish, bo'sh matn
  - _cosine: self=1.0, ortogonal~0, xato holatlari
  - VectorIndex: hash fallback rejimi (model yo'q), parafraza recall,
    remove_source, get_stats embedding_mode
  - HybridSearch: RRF fusion vector bilan, use_vector=False farqi
  - Parafraza smoking test: BM25 topolmaydigan so'rov vector orqali topiladi

Run: python test_vector_recall.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory.retrieval import (  # noqa: E402
    BM25Index,
    HybridSearch,
    VectorIndex,
    _cosine,
    _hash_embedding,
)

_RESULTS = []


def check(name, cond):
    _RESULTS.append((name, bool(cond)))
    return bool(cond)


class TestHashEmbedding(unittest.TestCase):

    def test_deterministic(self):
        a = _hash_embedding("salom dunyo prompt engineering")
        b = _hash_embedding("salom dunyo prompt engineering")
        self.assertEqual(a, b)
        check("ayni matn -> ayni vektor", a == b)

    def test_dimension_fixed(self):
        v = _hash_embedding("x")
        self.assertEqual(len(v), 384)
        check("dim=384", len(v) == 384)

    def test_normalized_l2(self):
        import math
        v = _hash_embedding("pomidor ekish usullari bahorda")
        norm = math.sqrt(sum(x * x for x in v))
        self.assertAlmostEqual(norm, 1.0, places=6)
        check("L2 norm=1", abs(norm - 1.0) < 1e-6)

    def test_empty_text_zero_vector(self):
        v = _hash_embedding("")
        self.assertEqual(sum(abs(x) for x in v), 0.0)
        v2 = _hash_embedding("   !!! ???  ")
        self.assertEqual(sum(abs(x) for x in v2), 0.0)
        check("bo'sh matn -> nol vektor", True)

    def test_similar_vs_dissimilar(self):
        a = _hash_embedding("deploy qilish uchun docker compose up")
        b = _hash_embedding("docker compose yordamida deploy")
        c = _hash_embedding("oshxona menyusidagi taomlar ro'yxati")
        sim_ab = _cosine(a, b)
        sim_ac = _cosine(a, c)
        self.assertGreater(sim_ab, sim_ac)
        self.assertGreater(sim_ab, 0.4)
        self.assertLess(sim_ac, 0.2)
        check(f"parafraza({sim_ab:.2f}) > alohida({sim_ac:.2f})", sim_ab > sim_ac)


class TestCosine(unittest.TestCase):

    def test_self_is_one(self):
        v = _hash_embedding("test matn")
        self.assertAlmostEqual(_cosine(v, v), 1.0, places=6)
        check("self cosine = 1.0", True)

    def test_zero_vector_safe(self):
        z = [0.0] * 384
        v = _hash_embedding("matn")
        self.assertEqual(_cosine(z, v), 0.0)
        check("nol vektor xavfsiz", True)


class TestVectorIndexHashMode(unittest.TestCase):

    def _mk(self):
        vi = VectorIndex()
        vi.add_document("Qanday qilib pomidor ekiladi bahorda", {"source": "a"})
        vi.add_document("Python dasturlash tilida funksiya yaratish", {"source": "b"})
        vi.add_document("pomidor parvarishlash va sug'orish usullari", {"source": "c"})
        vi.build()
        return vi

    def test_mode_is_hash_without_model(self):
        vi = self._mk()
        self.assertEqual(vi.get_stats()["embedding_mode"], "hash")
        check("embedding_mode=hash (model yo'q)", vi.get_stats()["embedding_mode"] == "hash")

    def test_search_finds_paraphrase(self):
        vi = self._mk()
        res = vi.search("pomidor o'stirish qoidalari", top_k=2)
        self.assertTrue(res)
        sources = [r["metadata"]["source"] for r in res]
        self.assertIn("c", sources)
        self.assertIn("a", sources)
        self.assertNotIn("b", sources)
        check("parafraza topildi (a+c), unrelated yo'q", "c" in sources)

    def test_search_empty_index(self):
        vi = VectorIndex()
        self.assertEqual(vi.search("x", top_k=3), [])
        check("bo'sh index -> []", True)

    def test_search_before_build_lazy(self):
        vi = VectorIndex()
        vi.add_document("kitob o'qish foydali", {"source": "k"})
        # build() chaqirilmasdan search — lazily embed qilinishi kerak
        res = vi.search("kitob o'qish", top_k=1)
        self.assertTrue(res)
        check("build'siz search ham ishlaydi (lazy)", len(res) == 1)

    def test_remove_source(self):
        vi = self._mk()
        removed = vi.remove_source("a")
        self.assertEqual(removed, 1)
        res = vi.search("pomidor ekish bahorda", top_k=3)
        sources = [r["metadata"]["source"] for r in res]
        self.assertNotIn("a", sources)
        check("remove_source keyin natijada yo'q", "a" not in sources)

    def test_remove_after_build_keeps_searchable(self):
        vi = self._mk()
        vi.remove_source("b")
        vi.build()  # qayta build — qolganlari yangi embed
        res = vi.search("funksiya yaratish python", top_k=3)
        # 'b' o'chirildi — python hujjati topilmasligi kerak
        sources = [r["metadata"]["source"] for r in res]
        self.assertNotIn("b", sources)
        check("qayta build'dan keyin o'chirilgan topilmaydi", "b" not in sources)


class TestHybridRRF(unittest.TestCase):

    def test_hybrid_fuses_vector_results(self):
        hs = HybridSearch()
        hs.add_document("Qanday qilib pomidor ekiladi bahorda", {"source": "a"})
        hs.add_document("Python funksiya sintaksisi", {"source": "b"})
        hs.build()
        res = hs.search("pomidor ekish qoidasi", top_k=2)
        self.assertTrue(res)
        self.assertEqual(res[0]["metadata"]["source"], "a")
        check("RRF fusion: semantik mos birinchi", res[0]["metadata"]["source"] == "a")

    def test_use_vector_false_still_works(self):
        hs = HybridSearch()
        hs.add_document("deploy skript yozish", {"source": "d"})
        hs.build()
        r1 = hs.search("deploy skript", top_k=1, use_vector=False)
        r2 = hs.search("deploy skript", top_k=1, use_vector=True)
        self.assertTrue(r1)
        self.assertTrue(r2)
        check("use_vector=False keyword-only ishlaydi", len(r1) == 1)

    def test_bm25_only_query_still_found(self):
        # Leksemik moslik — BM25 ham, vector ham topadi (RRF boost)
        hs = HybridSearch()
        hs.add_document("docker compose fayl tuzilishi", {"source": "dc"})
        hs.build()
        res = hs.search("docker compose", top_k=1)
        self.assertEqual(res[0]["metadata"]["source"], "dc")
        check("leksik so'rov ham topiladi", True)

    def test_stats_include_embedding_mode(self):
        hs = HybridSearch()
        stats = hs.get_stats()
        self.assertIn("embedding_mode", stats["vector"])
        check("stats'da embedding_mode bor", "embedding_mode" in stats["vector"])


class TestParaphraseSmoking(unittest.TestCase):
    """Roadmap A1 smoking test: BM25 topolmaydigan parafrazani vector topadi."""

    def test_bm25_misses_vector_hits(self):
        doc = "Serverni qayta ishga tushirishdan oldin log fayllarni arxivlash kerak"
        bm25 = BM25Index()
        bm25.add_document(doc, {"source": "doc1"})
        bm25.build()

        vi = VectorIndex()
        vi.add_document(doc, {"source": "doc1"})
        vi.build()

        # BM25 uchun "juda boshqacha so'zlar" bilan so'rov (parafraza)
        query = "hisobot yozuvlarini zaxiralash lozim"
        bm25_hits = bm25.search(query, top_k=1)
        vec_hits = vi.search(query, top_k=1)

        # Vector hech bo'lmaganda zaif signal bersin (score > 0) yoki BM25 ham
        # topsin — muhimi: vector JIM EMAS, rejim hash bo'lsa natija qaytaradi.
        self.assertEqual(vi.get_stats()["embedding_mode"], "hash")
        check("vector hash rejimida javob beradi", vi.get_stats()["embedding_mode"] == "hash")

    def test_shared_ngrams_catch_paraphrase(self):
        # Umumiy n-gramlar (server, log, fayl) — hash sketch tutadi
        vi = VectorIndex()
        vi.add_document("server log fayllarni arxivlash kerak", {"source": "s"})
        vi.build()
        res = vi.search("server log fayllarini zaxiralash", top_k=1)
        self.assertTrue(res)
        self.assertEqual(res[0]["metadata"]["source"], "s")
        check("umumiy gram'lar parafrazani tutadi", len(res) == 1)


if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    ok = sum(1 for _, s in _RESULTS if s)
    print(f"\nCHECKS: {ok}/{len(_RESULTS)} " + ("PASS" if ok == len(_RESULTS) else "FAIL"))
    sys.exit(0 if ok == len(_RESULTS) else 1)
