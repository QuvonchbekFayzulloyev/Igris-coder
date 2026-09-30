"""T1 — FTS5Index testlari.

Interfeys BM25Index bilan bir xil bo'lishi SHART (drop-in replacement):
add_document / build / search / tokenize / get_stats / total_docs / _built.

Run: python -m pytest test_fts5_index.py -q
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fts5_index import FTS5Index, _FTS5_AVAILABLE  # noqa: E402
from retrieval import BM25Index  # noqa: E402


class TestFTS5IndexInterfaceParity(unittest.TestCase):

    def _mk(self):
        tmp = tempfile.mkdtemp(prefix="igris_fts_")
        return FTS5Index(db_path=os.path.join(tmp, "idx.db"))

    def test_fts5_available(self):
        # Sinov muhitida FTS5 bor (yo'q bo'lsa fallback testlari baribir o'tadi)
        self.assertTrue(_FTS5_AVAILABLE, "FTS5 mavjud emas — fallback rejim tekshirildi")

    def test_add_and_search(self):
        idx = self._mk()
        idx.add_document("python is a programming language", {"source": "a.md"})
        idx.add_document("weather forecast tomorrow sunny", {"source": "b.md"})
        res = idx.search("python programming", top_k=2)
        self.assertTrue(len(res) >= 1)
        self.assertEqual(res[0]["metadata"]["source"], "a.md")

    def test_incremental_no_rebuild(self):
        """T1 asosiy talab: add_document'dan KEYIN search darhol ishlaydi
        (rebuild kutish yo'q) va har qo'shilish searchni BUZMAYDI."""
        idx = self._mk()
        idx.add_document("first doc about red apples", {"source": "1.md"})
        r1 = idx.search("red apples", top_k=1)
        self.assertEqual(len(r1), 1)
        # 100 taga qo'sh — har biridan keyin search ishlashi kerak
        for i in range(100):
            idx.add_document(f"doc {i} about topic {i}", {"source": f"{i}.md"})
            if i % 25 == 0:
                r = idx.search("red apples", top_k=1)
                self.assertEqual(len(r), 1, f"add #{i} searchni buzdi")
                self.assertEqual(r[0]["metadata"]["source"], "1.md")
        self.assertEqual(idx.total_docs, 101)

    def test_dedup_same_content(self):
        idx = self._mk()
        idx.add_document("duplicate content here", {"source": "x.md"})
        idx.add_document("duplicate content here", {"source": "x.md"})
        self.assertEqual(idx.total_docs, 1)

    def test_different_content_both_stored(self):
        idx = self._mk()
        idx.add_document("content alpha", {"source": "x.md"})
        idx.add_document("content beta", {"source": "y.md"})
        self.assertEqual(idx.total_docs, 2)

    def test_built_property_always_true(self):
        idx = self._mk()
        self.assertTrue(idx._built)
        idx.add_document("some text here", {"source": "s.md"})
        self.assertTrue(idx._built, "incremental indexda _built hech qachon False bo'lmasligi kerak")

    def test_search_empty_index(self):
        idx = self._mk()
        self.assertEqual(idx.search("anything", top_k=3), [])

    def test_stats_shape(self):
        idx = self._mk()
        idx.add_document("stats test document", {"source": "s.md"})
        st = idx.get_stats()
        self.assertEqual(st["total_documents"], 1)
        self.assertEqual(st.get("engine"), "fts5")

    def test_persistence_across_reopen(self):
        """Diskda saqlanadi — yangi instance bir xil db'dan topadi."""
        tmp = tempfile.mkdtemp(prefix="igris_fts_")
        db = os.path.join(tmp, "idx.db")
        idx1 = FTS5Index(db_path=db)
        idx1.add_document("persistent memory test unique words", {"source": "p.md"})
        idx1.close()
        idx2 = FTS5Index(db_path=db)
        res = idx2.search("persistent memory", top_k=1)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["metadata"]["source"], "p.md")
        self.assertEqual(idx2.total_docs, 1)

    def test_bm25_ranking_reasonable(self):
        idx = self._mk()
        idx.add_document("the cat sat on the mat", {"source": "cat.md"})
        idx.add_document("database performance tuning", {"source": "db.md"})
        res = idx.search("database performance", top_k=2)
        self.assertEqual(res[0]["metadata"]["source"], "db.md")

    def test_parity_with_bm25index(self):
        """Tokenizatsiya/interfeys mosligi: BM25Index bilan bir xil tokenize natijasi."""
        text = "Hello, IGRIS-test! UX 42"
        a = BM25Index().tokenize(text)
        b = FTS5Index().tokenize(text) if hasattr(FTS5Index, "tokenize") else None
        # FTS5Index'ta tokenize modul darajasida — bir xil oila
        from fts5_index import tokenize as fts_tokenize
        b = fts_tokenize(text)
        self.assertEqual(a, b, "tokenizatsiya BM25Index bilan mos emas")


class TestFTS5Fallback(unittest.TestCase):
    """FTS5 yo'q muhitda ham ishlashi kerak (BM25Index fallback)."""

    def test_module_has_fallback_path(self):
        import fts5_index
        import inspect
        src = inspect.getsource(fts5_index)
        self.assertIn("BM25Index", src, "fallback yo'q — FTS5 bo'lmasa crash bo'ladi")
        self.assertIn("_memo", src)


if __name__ == "__main__":
    unittest.main()
