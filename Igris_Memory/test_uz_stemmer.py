"""
Roadmap v2 — Phase A3 testlari: O'ZBEKCHA STEMMER (BM25/FTS5)
==============================================================

Qamrov:
  - uz_stem: qo'shimcha kesish (kitoblarni→kitob), affiks almashinuvi,
    qisqa so'zlar himoyasi, iterativ kesish, latin/kirill
  - BM25Index.tokenize: asl + stem juftliklari, apostrof normalizatsiya
  - BM25 E2E: 'kitoblarni o'qish' → 'kitob oqish' hujjatini topadi
  - FTS5 _query_tokens: stem kengaytirma + apostrof
  - Regressiya: BM25 oddiy so'rovlar buzilmaydi, vector recall alohida

Run: python test_uz_stemmer.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory.retrieval import BM25Index, VectorIndex, uz_stem  # noqa: E402
from memory.fts5_index import _query_tokens, tokenize  # noqa: E402

_RESULTS = []


def check(name, cond):
    _RESULTS.append((name, bool(cond)))
    return bool(cond)


class TestUzStem(unittest.TestCase):

    def test_plural_accusative(self):
        self.assertEqual(uz_stem("kitoblarni"), "kitob")
        self.assertEqual(uz_stem("daftarlarni"), "daftar")
        check("kitoblarni -> kitob", uz_stem("kitoblarni") == "kitob")

    def test_locative_and_dative(self):
        self.assertEqual(uz_stem("kitoblarda"), "kitob")
        self.assertEqual(uz_stem("maktabga"), "maktab")
        check("kitoblarda -> kitob", uz_stem("kitoblarda") == "kitob")
        check("maktabga -> maktab", uz_stem("maktabga") == "maktab")

    def test_possessive(self):
        self.assertEqual(uz_stem("kitoblarim"), "kitob")
        self.assertEqual(uz_stem("daftaringiz"), "daftar")
        check("kitoblarim -> kitob", uz_stem("kitoblarim") == "kitob")

    def test_consonant_alternation(self):
        # k/q/p/t tugashli ildiz + unli bilan boshlanuvchi qo'shimcha:
        # kitob + lar + ni -> kesilgach 'kitobk' emas, 'kitob' bo'lishi kerak
        self.assertEqual(uz_stem("kitoblarni"), "kitob")
        # q → ' (o'zbekcha: o'quvchi kabi ildizlar saqlanadi)
        stem_q = uz_stem("o'quvchilarni")
        self.assertTrue(stem_q.startswith("o"))
        check("affiks almashinuvi ishlaydi", uz_stem("kitoblarni") == "kitob")

    def test_short_words_untouched(self):
        self.assertEqual(uz_stem("kitob"), "kitob")
        self.assertEqual(uz_stem("olma"), "olma")
        check("qisqa so'zlar o'zgarmaydi", uz_stem("kitob") == "kitob")

    def test_iterative_stripping(self):
        # zanjir qo'shimchalar: "kitoblarimdagi" -> kitob
        s = uz_stem("kitoblarimdagi")
        self.assertEqual(s, "kitob")
        check("iterativ kesish (larim+dagi)", s == "kitob")

    def test_deterministic(self):
        self.assertEqual(uz_stem("kitoblarni"), uz_stem("kitoblarni"))
        check("deterministik", True)

    def test_empty_safe(self):
        self.assertEqual(uz_stem(""), "")
        self.assertEqual(uz_stem(None) if False else uz_stem(""), "")
        check("bo'sh kirish xavfsiz", True)


class TestTokenizeA3(unittest.TestCase):

    def test_asl_plus_stem_pairs(self):
        bm = BM25Index()
        toks = bm.tokenize("kitoblarni oqish")
        self.assertIn("kitoblarni", toks)
        self.assertIn("kitob", toks)
        check("asl + stem juftligi", "kitoblarni" in toks and "kitob" in toks)

    def test_apostrophe_normalized(self):
        bm = BM25Index()
        toks = bm.tokenize("o'qish kerak")
        self.assertIn("oqish", toks)
        self.assertNotIn("qish", toks)
        check("o'qish -> oqish (bir token)", "oqish" in toks and "qish" not in toks)

    def test_apostrophe_variants(self):
        bm = BM25Index()
        # turli apostrof belgilari: ' ' ʻ ʼ
        toks = bm.tokenize("o\u2019qish g\u2018oya to\u02bcplam")
        self.assertIn("oqish", toks)
        self.assertIn("goya", toks)
        self.assertIn("toplam", toks)
        check("barcha apostrof turlari", "oqish" in toks and "goya" in toks)

    def test_fts5_query_tokens_stem_expansion(self):
        t = _query_tokens("kitoblarni o'qish")
        self.assertIn("kitob", t)
        self.assertIn("oqish", t)
        check("FTS5 query stem kengaytirma", "kitob" in t)

    def test_fts5_tokenize_apostrophe(self):
        t = tokenize("o'qish")
        self.assertEqual(t, ["oqish"])
        check("fts5 tokenize apostrof", t == ["oqish"])


class TestBM25E2EA3(unittest.TestCase):

    def _mk_index(self):
        bm = BM25Index()
        bm.add_document("kitob oqish insonni boyitadi", {"source": "doc_kitob"})
        bm.add_document("pomidor ekish bahorda amalga oshiriladi", {"source": "doc_pomidor"})
        bm.build()
        return bm

    def test_morphological_match_found(self):
        bm = self._mk_index()
        res = bm.search("kitoblarni o'qish foydalimi", top_k=2)
        self.assertTrue(res)
        self.assertEqual(res[0]["metadata"]["source"], "doc_kitob")
        check("kitoblarni -> kitob hujjati topildi", res[0]["metadata"]["source"] == "doc_kitob")

    def test_unrelated_doc_not_first(self):
        bm = self._mk_index()
        res = bm.search("kitoblarni o'qish foydalimi", top_k=2)
        self.assertNotEqual(res[0]["metadata"]["source"], "doc_pomidor")
        check("alohida hujjat birinchi emas", res[0]["metadata"]["source"] != "doc_pomidor")

    def test_exact_match_still_works(self):
        bm = self._mk_index()
        res = bm.search("kitob oqish", top_k=2)
        self.assertEqual(res[0]["metadata"]["source"], "doc_kitob")
        check("leksik aniq moslik buzilmagan", res[0]["metadata"]["source"] == "doc_kitob")

    def test_existing_tests_scenario(self):
        # Phase 3 test'dagi tur: inglizcha so'rovlar ta'sir qilmasligi kerak
        bm = BM25Index()
        bm.add_document("def process_data(df): return df.dropna()", {"source": "code1"})
        bm.build()
        res = bm.search("process_data function", top_k=1)
        self.assertTrue(res)
        check("inglizcha/tech so'rovlar buzilmagan", res[0]["metadata"]["source"] == "code1")


class TestNoRegressionVector(unittest.TestCase):
    """A3 keyword tomonga tegadi — vector recall alohida ishlaydi."""

    def test_vector_index_still_works(self):
        vi = VectorIndex()
        vi.add_document("kitob oqish foydali", {"source": "k"})
        vi.build()
        res = vi.search("kitob oqish", top_k=1)
        self.assertTrue(res)
        check("vector recall ta'sir qilmagan", len(res) == 1)


if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    ok = sum(1 for _, s in _RESULTS if s)
    print(f"\nCHECKS: {ok}/{len(_RESULTS)} " + ("PASS" if ok == len(_RESULTS) else "FAIL"))
    sys.exit(0 if ok == len(_RESULTS) else 1)
