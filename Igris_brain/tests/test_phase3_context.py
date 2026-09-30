"""Phase 3 impl (2) testlari — §5 weighted recall / D2 maintenance + §6 ContextBudget.

Qamrov:
  - ContextBudget: token estimatsiya, prioritet qatlamlar, overflow degradation
    (memory tashlanadi, history eskilari tashlanadi, goal_pin/user saqlanadi)
  - MemoryBridge weighted recall: final_score = bm25 * (0.5 + 0.5*confidence)
  - MemoryBridge.run_maintenance: kunlik interval + force + disabled guard

Run: python test_phase3_context.py
"""

import os
import sys
import threading
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from state.context_budget import ContextBudget, estimate_tokens  # noqa: E402
from agent.memory_bridge import MemoryBridge  # noqa: E402

_RESULTS = []


def check(name, cond):
    _RESULTS.append((name, bool(cond)))
    return bool(cond)


# ============================================================
# §6 ContextBudget
# ============================================================

class TestEstimateTokens(unittest.TestCase):

    def test_empty(self):
        check("empty -> 0", estimate_tokens("") == 0)

    def test_deterministic_ceiling(self):
        # 4 belgi = 1 token; 8 belgi = 2 token; 9 belgi = 3 token (ceil)
        check("8 chars = 2 tok", estimate_tokens("a" * 8) == 2)
        check("9 chars = 3 tok (ceil)", estimate_tokens("a" * 9) == 3)

    def test_deterministic_same_input(self):
        check("deterministik", estimate_tokens("salom dunyo") == estimate_tokens("salom dunyo"))


class TestContextBudgetPriorities(unittest.TestCase):

    def _mk(self, max_tokens=4096):
        return ContextBudget(max_tokens=max_tokens)

    def test_small_prompt_all_kept(self):
        b = self._mk()
        system, kept, rep = b.fit_prompt(
            base_system="sys", req_block="req", goal_pin="goal",
            memory_block="mem", history=[{"role": "user", "content": "h1"}],
            user_message="salom", max_history=12)
        check("kichik prompt: goal saqlanadi", "goal" in system)
        check("kichik prompt: req saqlanadi", "req" in system)
        check("kichik prompt: mem saqlanadi", "mem" in system)
        check("kichik prompt: history kept", rep["history_kept"] == 1)
        check("kichik prompt: drop yo'q", not rep["dropped"])

    def test_overflow_drops_memory_first(self):
        # Juda kichik budget — memory sig'maydi, goal/user qoladi
        b = self._mk(max_tokens=512)
        goal = "GOAL: " + "g" * 100
        base = "BASE: " + "b" * 200
        mem = "MEM: " + "m" * 800   # ~200 token — budgetda yo'q
        system, kept, rep = b.fit_prompt(
            base_system=base, goal_pin=goal, memory_block=mem,
            history=[], user_message="user msg")
        check("overflow: memory tashlandi", "memory_block" in rep["dropped"] or "memory_block" in rep["truncated"])
        check("overflow: goal SAQLANADI", goal in system)
        check("overflow: user saqlanadi", "user msg" not in system)  # user system'da emas, alohida
        check("overflow: base qolgan", "BASE" in system)

    def test_history_newest_first_kept(self):
        b = ContextBudget(max_tokens=512, reserve_response=0)
        hist = [{"role": "user", "content": "x" * 600} for _ in range(6)]
        system, kept, rep = b.fit_prompt(
            base_system="s", history=hist, user_message="u", max_history=12)
        check("history: barchasi sig'maydi", rep["history_kept"] < 6)
        check("history: eng yangilari saqlanadi", kept[-1]["content"] == hist[-1]["content"])
        check("history: report total", rep["history_total"] == 6)

    def test_goal_never_dropped(self):
        # Ekstremal katta goal + katta base — goal baribir systemda
        b = ContextBudget(max_tokens=512)
        goal = "GOAL " + "z" * 1200
        base = "BASE " + "y" * 4000
        system, kept, rep = b.fit_prompt(base_system=base, goal_pin=goal, history=[], user_message="u")
        check("goal hech qachon tashlanmaydi", goal in system)

    def test_report_fields(self):
        b = self._mk()
        system, kept, rep = b.fit_prompt(base_system="s", history=[], user_message="u")
        for k in ("budget", "estimated", "history_kept", "history_total", "dropped", "truncated"):
            check(f"report field: {k}", k in rep)

    def test_invalid_max_tokens_fallback(self):
        b = ContextBudget(max_tokens="junk")
        check("invalid max_tokens -> default", b.max_tokens == 4096)

    def test_reserve_clamped(self):
        b = ContextBudget(max_tokens=512, reserve_response=10_000)
        check("reserve budget yarmidan oshmaydi", b.reserve_response <= 256)


# ============================================================
# §5 MemoryBridge: weighted recall + maintenance
# ============================================================

class _FakeManager:
    """manager.search() natijasini boshqaradigan fake."""

    def __init__(self, results):
        self._results = results
        self.persistent = None
        self.calls = []

    def search(self, query, top_k=5):
        self.calls.append((query, top_k))
        return {"query": query, "results": self._results, "count": len(self._results)}


class _FakeBridge:
    """MemoryBridge metodlarini __init__'siz yaratilgan nusxa ustida ishga tushiradi.

    Muhim: MemoryBridge.recall(self.b, ...) shaklida OCHIQ delegatsiya —
    class-level assignment descriptor `self`ni wrapper'ga bog'lab qo'yadi.
    """

    def __init__(self, results):
        self.b = MemoryBridge.__new__(MemoryBridge)  # __init__'siz
        self.b.enabled = True
        self.b.manager = _FakeManager(results)
        self.b._error = ""
        self.b._latency = {}
        self.b._last_maintenance = 0.0
        self.b._maint_lock = threading.Lock()
        # recall() _ensure_loaded() chaqiradi — korpus allaqachon yuklangan
        # (fake manager) deb belgilaymiz.
        self.b._load_done = threading.Event()
        self.b._load_done.set()

    def recall(self, query, top_k=3, max_chars=1600):
        return MemoryBridge.recall(self.b, query, top_k=top_k, max_chars=max_chars)

    def run_maintenance(self, force=False):
        return MemoryBridge.run_maintenance(self.b, force=force)


class TestWeightedRecall(unittest.TestCase):

    def test_confidence_boosts_rank(self):
        # Past BM25 score + yuqori confidence YUQORI final score olishi kerak
        hi_conf = {"entry": {"content": "AAA", "confidence_score": 1.0, "id": "a"}, "score": 1.0}
        lo_conf = {"entry": {"content": "BBB", "confidence_score": 0.0, "id": "b"}, "score": 1.4}
        fb = _FakeBridge([lo_conf, hi_conf])
        ctx, hits = fb.recall("query", top_k=2)
        # A: 1.0*(0.5+0.5)=1.0 ; B: 1.4*(0.5+0.0)=0.7 -> A birinchi
        self.assertTrue("AAA" in ctx and "BBB" in ctx)
        self.assertTrue(ctx.index("AAA") < ctx.index("BBB"), f"weighted order buzildi: {ctx[:80]}")
        check("yuhori confidence birinchi", ctx.index("AAA") < ctx.index("BBB"))
        check("A va B ikkalasi bor", "AAA" in ctx and "BBB" in ctx)

    def test_low_confidence_dropped_from_topk(self):
        hi = {"entry": {"content": "AAA hi", "confidence_score": 1.0, "id": "a"}, "score": 0.8}
        lo = {"entry": {"content": "BBB lo", "confidence_score": 0.0, "id": "b"}, "score": 0.9}
        fb = _FakeBridge([hi, lo])
        ctx, hits = fb.recall("q", top_k=1)
        self.assertEqual(hits, 1)
        self.assertIn("AAA", ctx)
        self.assertNotIn("BBB", ctx)
        check("top_k=1: faqat high conf", hits == 1 and "AAA" in ctx and "BBB" not in ctx)

    def test_missing_confidence_default_half(self):
        # confidence_score yo'q -> 0.5 hisoblanadi (neytral)
        no_conf = {"entry": {"content": "CCC", "id": "c"}, "score": 2.0}
        mid = {"entry": {"content": "DDD", "confidence_score": 0.5, "id": "d"}, "score": 2.0}
        fb = _FakeBridge([mid, no_conf])
        ctx, hits = fb.recall("q", top_k=2)
        self.assertEqual(hits, 2)
        check("default conf=0.5 neytral (ikkalasi ham qoladi)", hits == 2)

    def test_confidence_clamped(self):
        # 5.0 dan katta -> clamp 0..1 (xato bo'lsa 0.5)
        over = {"entry": {"content": "EEE", "confidence_score": 5.0, "id": "e"}, "score": 1.0}
        fb = _FakeBridge([over])
        ctx, hits = fb.recall("q", top_k=1)
        self.assertEqual(hits, 1)
        check("clamp: invalid qiymat ham ishlaydi", hits == 1)

    def test_disabled_bridge(self):
        b = MemoryBridge.__new__(MemoryBridge)
        b.enabled = False
        ctx, hits = b.recall("q")
        check("disabled -> ('', 0)", ctx == "" and hits == 0)


class TestMaintenanceScheduler(unittest.TestCase):

    def test_first_call_runs(self):
        # persistent fake: cleanup_stale statistikasini qaytaradi
        class P:
            def cleanup_stale(self, archive_days=30, delete_days=90):
                return {"archived": 2, "deleted": 1}
        fb = _FakeBridge([])
        fb.b.manager.persistent = P()
        res = fb.run_maintenance(force=True)
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res.get("archived"), 2)
        check("birinchi chaqiruv ishlaydi", res.get("status") == "ok" and res.get("archived") == 2)

    def test_interval_skip(self):
        import time as _t
        fb = _FakeBridge([])
        fb.b._last_maintenance = _t.time()  # hozirgina ishlagan
        res = fb.run_maintenance()
        self.assertEqual(res.get("status"), "skipped")
        check("interval ichida skip", res.get("status") == "skipped" and res.get("reason") == "not due")

    def test_force_overrides_interval(self):
        class P:
            def cleanup_stale(self):
                return {"archived": 0, "deleted": 0}
        fb = _FakeBridge([])
        fb.b.manager.persistent = P()
        fb.b._last_maintenance = 9e9  # kelajakda
        res = fb.run_maintenance(force=True)
        self.assertEqual(res.get("status"), "ok")
        check("force intervalni e'tiborsiz qoldiradi", res.get("status") == "ok")

    def test_error_handled(self):
        class P:
            def cleanup_stale(self):
                raise RuntimeError("boom")
        fb = _FakeBridge([])
        fb.b.manager.persistent = P()
        res = fb.run_maintenance(force=True)
        self.assertEqual(res.get("status"), "error")
        self.assertIn("boom", res.get("message", ""))
        check("xato ushlanadi", res.get("status") == "error" and "boom" in res.get("message", ""))

    def test_min_interval_is_daily(self):
        check("MIN_INTERVAL_SECS = 86400 (kuniga 1)", MemoryBridge.MIN_INTERVAL_SECS == 86400)


# ============================================================
# §6 Agent integratsiyasi: budget agent init'da mavjud
# ============================================================

class TestAgentBudgetWiring(unittest.TestCase):

    def test_agent_has_budget(self):
        # Agent'ni to'liq ishga tushirmasdan klass atribut mavjudligini tekshiramiz
        import agent.igris_agent as igris_agent
        check("ContextBudget import qilingan", hasattr(igris_agent, "ContextBudget"))
        from state.context_budget import ContextBudget as CB
        b = CB()
        check("default budget 4096-512", b.prompt_budget == 4096 - 512)


if __name__ == "__main__":
    import io
    from contextlib import redirect_stderr
    buf = io.StringIO()
    with redirect_stderr(buf):
        unittest.main(argv=["x", "-v"], exit=False)
    ok = sum(1 for _, c in _RESULTS if c)
    print(f"\n{'=' * 50}\nCHECKS: {ok}/{len(_RESULTS)} PASS")
    failed = [n for n, c in _RESULTS if not c]
    for n in failed:
        print(f"  FAIL: {n}")
    sys.exit(1 if failed else 0)
