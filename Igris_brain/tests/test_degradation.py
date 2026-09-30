"""S3 — Silent-degradation registry testlari.

Kontrakt:
- mark() hech qachon exception tashlamaydi
- bir xil component+fallback → count+1 (ro'yxat shishmaydi)
- report() eng so'nggi birinchi
- FTS5 import buzilsa → memory.keyword-index mark bo'ladi
- MCP connect xatosi → mcp.<name> mark bo'ladi

Run: python -m pytest test_degradation.py -q
"""
import os
import sys
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from monitor import degradation  # noqa: E402


class TestDegradationRegistry(unittest.TestCase):

    def setUp(self):
        degradation.clear()

    def tearDown(self):
        degradation.clear()

    def test_mark_and_report(self):
        degradation.mark("test.comp", "boom", fallback="fb")
        rep = degradation.report()
        self.assertEqual(len(rep), 1)
        self.assertEqual(rep[0]["component"], "test.comp")
        self.assertEqual(rep[0]["fallback"], "fb")
        self.assertIn("boom", rep[0]["reason"])
        self.assertGreater(rep[0]["ts"], 0)

    def test_dedup_increments_count(self):
        degradation.mark("test.comp", "boom1", fallback="fb")
        degradation.mark("test.comp", "boom2", fallback="fb")
        rep = degradation.report()
        self.assertEqual(len(rep), 1, "bir xil component+fallback dedup qilinmadi")
        self.assertEqual(rep[0]["count"], 2)
        self.assertIn("boom2", rep[0]["reason"], "eng so'nggi reason saqlanmadi")

    def test_different_fallback_separate_entries(self):
        degradation.mark("test.comp", "x", fallback="a")
        degradation.mark("test.comp", "y", fallback="b")
        self.assertEqual(len(degradation.report()), 2)

    def test_report_newest_first(self):
        degradation.mark("old.one", "x", fallback="f")
        degradation.mark("new.one", "y", fallback="f")
        rep = degradation.report()
        self.assertEqual(rep[0]["component"], "new.one")

    def test_active_older_than(self):
        degradation.mark("fresh.comp", "x", fallback="f")
        active = degradation.active_older_than(600.0)
        self.assertEqual(len(active), 1)
        # Juda qisqa oyna — hamma eskirgan bo'ladi
        self.assertEqual(len(degradation.active_older_than(0.0001)), 0)

    def test_never_raises(self):
        # noto'g'ri argumentlar bilan ham crash yo'q
        degradation.mark(None, None, fallback=None)
        degradation.mark("", "", fallback="")
        rep = degradation.report()
        self.assertTrue(all(isinstance(e, dict) for e in rep))

    def test_persistence_to_disk(self):
        degradation.mark("disk.test", "persist", fallback="fb")
        # Yangi jarayon simulatsiyasi: modul holatini tozalab qayta o'qish
        degradation._ENTRIES.clear()
        degradation._LOADED = False
        rep = degradation.report()
        self.assertEqual(len(rep), 1)
        self.assertEqual(rep[0]["component"], "disk.test")


class TestMCPBridgeMarks(unittest.TestCase):

    def test_connect_failure_marks(self):
        """MCP ulanmagan server mark bo'ladi (registryda ko'rinadi)."""
        from tools.mcp_bridge import McpBridge
        import monitor.degradation as degradation
        degradation.clear()
        bridge = McpBridge.__new__(McpBridge)  # __init__siz (async loop yo'q)
        # MCPBridge._connect async — to'g'ridan-to'g'ri chaqiramiz asyncio orqali
        import asyncio
        try:
            asyncio.run(bridge._connect("_bad_server_", {
                "command": sys.executable,
                "args": ["-c", "import sys; sys.exit(7)"],  # darhol o'lgan jarayon
                "cwd": os.path.dirname(os.path.abspath(__file__)),
            }))
        except Exception:
            pass  # transport xatosi ham mark bo'lishi kerak
        comps = [e["component"] for e in degradation.report()]
        self.assertIn("mcp._bad_server_", comps,
                      "MCP connect xatosi registryga yozilmadi")


class TestFTS5FallbackMarks(unittest.TestCase):

    def test_fts5_missing_marks(self):
        """fts5_index import buzilsa → BM25 fallback + mark (memory.keyword-index)."""
        import builtins
        import monitor.degradation as degradation
        degradation.clear()
        # memory paketi + memory/ papkasi (retrieval.py yashaydigan joy) path'ga
        real_import = builtins.__import__
        here = os.path.dirname(os.path.abspath(__file__))
        mem_root = os.path.normpath(os.path.join(here, "..", "..", "Igris_Memory"))
        mem_pkg = os.path.join(mem_root, "memory")
        for p in (mem_root, mem_pkg):
            if p not in sys.path:
                sys.path.insert(0, p)

        def fake(name, *a, **k):
            if name == "fts5_index" or name == "memory.fts5_index":
                raise ImportError("simulated fts5 missing")
            return real_import(name, *a, **k)

        builtins.__import__ = fake
        try:
            import memory.retrieval as R
            hs = R.HybridSearch()
            self.assertEqual(type(hs.bm25).__name__, "BM25Index")
        finally:
            builtins.__import__ = real_import
        comps = [e["component"] for e in degradation.report()]
        self.assertIn("memory.keyword-index", comps,
                      "FTS5 fallback registryga yozilmadi")


class TestServicesEndpointShape(unittest.TestCase):
    """/api/system/services javobi degradations maydonlarini o'z ichiga oladi
    (endpoint funksiyasini to'g'ridan-to'g'ri chaqirish — server ishga tushirmasdan)."""

    def test_endpoint_includes_degradations(self):
        import server.server as server
        result = server.api_system_services()
        self.assertIn("degradations", result)
        self.assertIn("degradations_active", result)
        self.assertIsInstance(result["degradations"], list)
        self.assertIsInstance(result["degradations_active"], int)


if __name__ == "__main__":
    unittest.main()
