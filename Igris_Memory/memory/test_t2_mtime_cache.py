"""
IGRIS MEMORY — T2 mtime cache tests
====================================
problems_to_fix.md :: T2 — load_documents butun katalogni qayta o'qiydi.

Qamrov:
- Birinchi yuklama: barcha fayllar indekslanadi
- Ikkinchi yuklama (o'zgarishsiz): fayllar QAYTA O'QILMAYDI (open sanagich)
- Fayl o'zgarsa: eski versiya o'chirilib, yangisi qo'shiladi (search yangi)
- Fayl o'chirilsa: index'dan ham o'chiriladi
- force=True: hammasi qayta o'qiladi
- BM25Index.remove_source / FTS5Index.remove_source unit testlari

Izolyatsiya: RetrievalPipeline'ning hybrid index'lari vaqtinchalik DB'ga
yo'naltiriladi (haqiqiy brain_data/fts_index.db ifloslanmaydi).
"""

import os
import sys
import tempfile
import time
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from retrieval import BM25Index, RetrievalPipeline, VectorIndex  # noqa: E402
from fts5_index import FTS5Index  # noqa: E402


class _TempIndexPipeline(RetrievalPipeline):
    """load_documents vaqtinchalik FTS5 DB bilan ishlaydigan pipeline."""

    def __init__(self, db_path: str):
        super().__init__()
        self.hybrid.bm25 = FTS5Index(db_path=db_path)
        self.hybrid.vector = VectorIndex()


class TestBM25RemoveSource(unittest.TestCase):
    def test_remove_only_matching_source(self):
        idx = BM25Index()
        idx.add_document("alpha beta gamma", {"source": "a.md"})
        idx.add_document("delta epsilon zeta", {"source": "b.md"})
        idx.add_document("alpha zeta eta", {"source": "c.md"})
        idx.build()
        removed = idx.remove_source("b.md")
        self.assertEqual(removed, 1)
        self.assertEqual(idx.total_docs, 2)
        # qolgan hujjatlar hali ham topiladi (ikki hujjatda ham 'alpha' bor)
        hits = idx.search("alpha", top_k=5)
        self.assertEqual(len(hits), 2)
        self.assertTrue(all(h["metadata"]["source"] != "b.md" for h in hits))
        # o'chirilgan hujjat endi topilmaydi
        hits = idx.search("delta", top_k=5)
        self.assertEqual(len(hits), 0)

    def test_remove_nonexistent_noop(self):
        idx = BM25Index()
        idx.add_document("alpha beta", {"source": "a.md"})
        idx.build()
        self.assertEqual(idx.remove_source("nope.md"), 0)
        self.assertEqual(idx.total_docs, 1)

    def test_stats_consistent_after_removal(self):
        idx = BM25Index()
        for i in range(5):
            idx.add_document(f"doc {i} common token", {"source": f"f{i}.md"})
        idx.build()
        idx.remove_source("f0.md")
        self.assertEqual(idx.total_docs, 4)
        self.assertGreater(idx.avg_dl, 0)
        # search hali ishlaydi (rebuild yo'q, _built=True)
        self.assertTrue(idx.search("common"))


class TestFTS5RemoveSource(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db = os.path.join(self.tmpdir, "test_fts.db")

    def test_remove_and_search_after(self):
        idx = FTS5Index(db_path=self.db)
        try:
            idx.add_document("unique alpha content here", {"source": "a.md"})
            idx.add_document("other beta content here", {"source": "b.md"})
            self.assertEqual(idx.remove_source("a.md"), 1)
            self.assertEqual(idx.total_docs, 1)
            # o'chirilgan hujjat endi topilmaydi
            hits = idx.search("unique alpha", top_k=5)
            srcs = {h["metadata"].get("source") for h in hits}
            self.assertNotIn("a.md", srcs)
            # qolgan hujjat topiladi
            hits = idx.search("beta", top_k=5)
            self.assertTrue(any(h["metadata"].get("source") == "b.md" for h in hits))
        finally:
            idx.close()

    def test_remove_nonexistent_noop(self):
        idx = FTS5Index(db_path=self.db)
        try:
            idx.add_document("some content here", {"source": "a.md"})
            self.assertEqual(idx.remove_source("nope.md"), 0)
        finally:
            idx.close()

    def test_fallback_delegates(self):
        idx = FTS5Index(db_path=self.db)
        try:
            if idx._memo is None:
                self.skipTest("FTS5 mavjud — fallback yo'q")
            idx.add_document("fallback content here", {"source": "a.md"})
            self.assertEqual(idx.remove_source("a.md"), 1)
        finally:
            idx.close()


class TestLoadDocumentsMtimeCache(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db = os.path.join(self.tmpdir, "cache_test.db")
        self.pipe = _TempIndexPipeline(self.db)
        self.calls = {"opens": 0}
        self._orig_open = open

    def tearDown(self):
        try:
            self.pipe.hybrid.bm25.close()
        except Exception:
            pass

    def _counting_open(self, fpath, *a, **kw):
        # faqat korpus fayllarini sanaymiz (db/log fayllarini emas)
        if str(fpath).endswith((".md", ".json", ".jsonl")):
            self.calls["opens"] += 1
        return self._orig_open(fpath, *a, **kw)

    def test_unchanged_files_not_reread(self):
        p1 = os.path.join(self.tmpdir, "a.md")
        p2 = os.path.join(self.tmpdir, "b.md")
        with open(p1, "w", encoding="utf-8") as f:
            f.write("python dasturlash tili haqida izohlar")
        with open(p2, "w", encoding="utf-8") as f:
            f.write("ob-havo ma'lumotlari va tahlillar")

        with unittest.mock.patch("builtins.open", side_effect=self._counting_open):
            self.pipe.load_documents(self.tmpdir)
            first = self.calls["opens"]
            self.assertEqual(first, 2)
            # ikkinchi yuklama — o'zgarmagan: 0 yangi o'qish
            self.pipe.load_documents(self.tmpdir)
            self.assertEqual(self.calls["opens"], first)

    def test_changed_file_reindexed(self):
        p1 = os.path.join(self.tmpdir, "a.md")
        with open(p1, "w", encoding="utf-8") as f:
            f.write("eski mazmun olma nok anor")

        self.pipe.load_documents(self.tmpdir)
        self.assertTrue(self.pipe.hybrid.search("olma", top_k=3))

        # content o'zgarishi + mtime/size yangilanishi
        time.sleep(0.02)
        with open(p1, "w", encoding="utf-8") as f:
            f.write("yangi mazmun tarvuz qovun uzum")
        os.utime(p1, (time.time() + 1, time.time() + 1))

        self.pipe.load_documents(self.tmpdir)
        # yangi mazmun topiladi
        hits = self.pipe.hybrid.search("tarvuz", top_k=5)
        self.assertTrue(hits)
        self.assertEqual(
            hits[0]["metadata"].get("source"), os.path.normpath(p1))
        # eski mazmun boshqa hujjat sifatida QOLMAGAN (remove_source ishladi)
        old_hits = self.pipe.hybrid.search("anor", top_k=5)
        self.assertEqual(len(old_hits), 0)

    def test_deleted_file_removed_from_state(self):
        p1 = os.path.join(self.tmpdir, "a.md")
        with open(p1, "w", encoding="utf-8") as f:
            f.write("ochiriladigan hujjat mazmuni kirish")
        self.pipe.load_documents(self.tmpdir)
        self.assertIn(os.path.normpath(p1), self.pipe._file_state)
        os.remove(p1)
        self.pipe.load_documents(self.tmpdir)
        # fayl_state tozalangan
        self.assertNotIn(os.path.normpath(p1), self.pipe._file_state)

    def test_force_rereads_everything(self):
        p1 = os.path.join(self.tmpdir, "a.md")
        with open(p1, "w", encoding="utf-8") as f:
            f.write("mazmun bir marta yozildi")
        with unittest.mock.patch("builtins.open", side_effect=self._counting_open):
            self.pipe.load_documents(self.tmpdir)
            first = self.calls["opens"]
            self.pipe.load_documents(self.tmpdir, force=True)
            self.assertGreater(self.calls["opens"], first)

    def test_search_no_duplicates_after_reload(self):
        p1 = os.path.join(self.tmpdir, "a.md")
        with open(p1, "w", encoding="utf-8") as f:
            f.write("qizil olma daraxtda turgan")
        self.pipe.load_documents(self.tmpdir)
        self.pipe.load_documents(self.tmpdir)  # noop reload
        hits = self.pipe.hybrid.search("olma", top_k=5)
        srcs = [h["metadata"].get("source") for h in hits]
        self.assertEqual(len(srcs), len(set(srcs)))  # dublikat yo'q


if __name__ == "__main__":
    unittest.main()
