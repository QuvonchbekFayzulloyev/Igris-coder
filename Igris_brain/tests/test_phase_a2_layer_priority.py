"""
Roadmap v2 — Phase A2 testlari: LAYER PRIORITY + CONFLICT BELGISI
==================================================================

Qamrov:
  - L1/L2 yozuvlari sintetik base + layer bonus bilan vault'dan yuqorida
  - L1 > L2 tartibi (ikkalasi ham score'siz bo'lsa)
  - Vault (retrieval-format) yozuvlari o'z score'i bilan qoladi
  - Conflict-signal'li yozuv kontekstda "[CONFLICT]" prefiksi bilan
  - Normal yozuvda prefiks yo'q
  - Phase 3 weighted recall (confidence boost) buzilmagan

Run: python test_phase_a2_layer_priority.py
"""

import os
import sys
import threading
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from agent.memory_bridge import MemoryBridge  # noqa: E402

_RESULTS = []


def check(name, cond):
    _RESULTS.append((name, bool(cond)))
    return bool(cond)


class _FakeManager:
    def __init__(self, results):
        self._results = results

    def search(self, query, top_k=5):
        return {"results": list(self._results)[:top_k]}


class _FakeBridge:
    """MemoryBridge metodlarini __init__'siz yaratilgan nusxa ustida ishga tushiradi."""

    def __init__(self, results):
        self.b = MemoryBridge.__new__(MemoryBridge)
        self.b.enabled = True
        self.b.manager = _FakeManager(results)
        self.b._error = ""
        self.b._latency = {}
        self.b._load_done = threading.Event()
        self.b._load_done.set()

    def recall(self, query, top_k=3, max_chars=1600):
        return MemoryBridge.recall(self.b, query, top_k=top_k, max_chars=max_chars)


class TestLayerPriority(unittest.TestCase):

    def test_l2_beats_vault_despite_no_score(self):
        # L2 yozuvda score YO'Q (recall-format); vault'da yuqori BM25 score bor.
        # A2: L2 sintetik base(1.0) + bonus(0.25) = 1.25+ > vault 0.9
        l2 = {"layer": "l2", "type": "solution-memory", "entry": {"content": "AAA l2 eslatma"}}
        vault = {"source": "notes/aaa.md", "score": 0.9}
        fb = _FakeBridge([vault, l2])
        ctx, hits = fb.recall("query", top_k=2)
        self.assertEqual(hits, 2)
        self.assertLess(ctx.index("AAA"), ctx.index("notes/aaa.md"))
        check("L2 (score'siz) vault'dan yuqorida", ctx.index("AAA") < ctx.index("notes/aaa.md"))

    def test_l1_beats_l2(self):
        # Ikkalasi ham score'siz: L1 bonus(0.5) > L2 bonus(0.25)
        l2 = {"layer": "l2", "type": "solution-memory", "entry": {"content": "BBB l2"}}
        l1 = {"layer": "l1", "type": "short-turn", "entry": {"content": "CCC l1"}}
        fb = _FakeBridge([l2, l1])
        ctx, hits = fb.recall("q", top_k=2)
        self.assertLess(ctx.index("CCC"), ctx.index("BBB"))
        check("L1 > L2 tartibi", ctx.index("CCC") < ctx.index("BBB"))

    def test_vault_high_score_still_competitive(self):
        # Vault juda yuqori score bilan L2'ni ortlab ketoladi (base 2.0*(0.75)=1.5+)
        l2 = {"layer": "l2", "type": "solution-memory", "entry": {"content": "DDD l2"}}
        vault = {"source": "docs/big.md", "score": 3.0}
        fb = _FakeBridge([vault, l2])
        ctx, hits = fb.recall("q", top_k=2)
        self.assertLess(ctx.index("docs/big.md"), ctx.index("DDD"))
        check("yuqori score'li vault L2'dan yuqorida", ctx.index("docs/big.md") < ctx.index("DDD"))

    def test_recall_format_with_explicit_score_unchanged(self):
        # Agar recall-formatda score BERILGAN bo'lsa — sintetik base qo'llanmaydi
        l2 = {"layer": "l2", "type": "x", "score": 0.1, "entry": {"content": "EEE low"}}
        vault = {"source": "f.md", "score": 0.8}
        fb = _FakeBridge([vault, l2])
        ctx, _ = fb.recall("q", top_k=2)
        self.assertLess(ctx.index("f.md"), ctx.index("EEE"))
        check("explicit score hurmat qilinadi", ctx.index("f.md") < ctx.index("EEE"))


class TestConflictFlag(unittest.TestCase):

    def test_conflicting_entry_gets_prefix(self):
        l2 = {"layer": "l2", "type": "solution-memory",
              "entry": {"content": "deploy no longer uses ftp, use sftp instead"}}
        fb = _FakeBridge([l2])
        ctx, hits = fb.recall("deploy", top_k=1)
        self.assertEqual(hits, 1)
        self.assertIn("[CONFLICT]", ctx)
        check("[CONFLICT] prefiksi bor", "[CONFLICT]" in ctx)

    def test_normal_entry_no_prefix(self):
        l2 = {"layer": "l2", "type": "solution-memory",
              "entry": {"content": "deploy uses docker compose up"}}
        fb = _FakeBridge([l2])
        ctx, hits = fb.recall("deploy", top_k=1)
        self.assertEqual(hits, 1)
        self.assertNotIn("[CONFLICT]", ctx)
        check("normal yozuvda prefiks yo'q", "[CONFLICT]" not in ctx)

    def test_vault_conflict_flagged(self):
        vault = {"source": "notes/old.md", "score": 1.2}
        # _read_source_snippet fayldan o'qiydi — fayl yo'q bo'lsa metadata JSON;
        # metadata orqali conflict signal yaratib bo'lmaydi, shuning uchun
        # retrieval-formatda hech bo'lmaganda crash yo'q va flag faqat matnga chiqadi.
        fb = _FakeBridge([vault])
        ctx, hits = fb.recall("q", top_k=1)
        self.assertEqual(hits, 1)
        check("vault yozuvi o'zgarmagan oqim", "notes/old.md" in ctx)


class TestWeightedRecallRegression(unittest.TestCase):
    """Phase 3 confidence boost A2 o'zgarishlaridan keyin ham ishlaydi."""

    def test_confidence_boost_still_applies(self):
        hi = {"entry": {"content": "AAA hi", "confidence_score": 1.0}, "score": 1.0}
        lo = {"entry": {"content": "BBB lo", "confidence_score": 0.0}, "score": 1.4}
        fb = _FakeBridge([lo, hi])
        ctx, _ = fb.recall("q", top_k=2)
        # layer yo'q — bonus 0; faqat confidence formula: A=1.0, B=0.7
        self.assertLess(ctx.index("AAA"), ctx.index("BBB"))
        check("confidence boost saqlangan", ctx.index("AAA") < ctx.index("BBB"))

    def test_layer_bonus_applies_on_top_of_confidence(self):
        hi_vault = {"source": "h.md", "score": 1.0}  # 1.0*(0.5+0.5)=1.0
        lo_l2 = {"layer": "l2", "type": "x", "entry": {"content": "MMM lo-conf", "confidence_score": 0.0}}
        # lo_l2: 1.0*0.5 + 0.25 = 0.75 < 1.0 — vault yuqorida qoladi
        fb = _FakeBridge([hi_vault, lo_l2])
        ctx, _ = fb.recall("q", top_k=2)
        self.assertLess(ctx.index("h.md"), ctx.index("MMM"))
        check("bonus confidence ustiga qo'shiladi (vault yutadi)", ctx.index("h.md") < ctx.index("MMM"))


if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    ok = sum(1 for _, s in _RESULTS if s)
    print(f"\nCHECKS: {ok}/{len(_RESULTS)} " + ("PASS" if ok == len(_RESULTS) else "FAIL"))
    sys.exit(0 if ok == len(_RESULTS) else 1)
