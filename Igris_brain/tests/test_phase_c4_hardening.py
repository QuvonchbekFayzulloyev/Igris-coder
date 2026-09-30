# -*- coding: utf-8 -*-
"""
Roadmap v2 — Phase C4 testlari: HARDENING (§15 right-sizing qoldiqlari)
========================================================================

Qamrov:
  - FIFO task queue: sig'im 1 — ortiqchasi "queued", FIFO tartibida ishga tushadi
  - Queue'dagi run'ni cancel: navbatdan olib tashlanadi, hech ishga tushmaydi
  - queue_info(): monitoring kontrakti (max_concurrent/active/queued)
  - /api/health/metrics "runs" bo'limi: RunManager DI orqali
  - System metrics: psutil bo'lmasa lightweight fallback (crash yo'q)

Roadmap v2 C3: pytest markeri `e2e` emas — bu unit darajadagi testlar.

Run: python test_phase_c4_hardening.py  |  pytest test_phase_c4_hardening.py
"""

import os
import sys
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

CHECKS = []


def check(name, cond):
    CHECKS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL") + f"  {name}")


def _make_launch(record, rid):
    """launch_fn stub: ishga tushganda record'ga yozadi (tartib kuzatuvi)."""
    def _launch():
        record.append(rid)
    return _launch


# ------------------------------------------------------------------ #
# FIFO QUEUE
# ------------------------------------------------------------------ #

class TestFifoQueue(unittest.TestCase):

    def _rm(self, max_concurrent=1):
        try:
            from server.server import RunManager
        except Exception as exc:
            self.skipTest(f"server import bo'lmadi: {exc}")
        return RunManager(max_concurrent=max_concurrent)

    def test_first_runs_others_queued(self):
        rm = self._rm(1)
        rec = []
        s1, s2, s3 = ({"id": f"r{i}", "status": "init"} for i in (1, 2, 3))
        rm._enqueue("r1", s1, _make_launch(rec, "r1"))
        rm._enqueue("r2", s2, _make_launch(rec, "r2"))
        rm._enqueue("r3", s3, _make_launch(rec, "r3"))
        check("birinchi run darhol ishlaydi", s1["status"] == "running")
        check("ortiqchalar queued", s2["status"] == "queued" and s3["status"] == "queued")
        check("faqat r1 launch bo'ldi", rec == ["r1"])
        qi = rm.queue_info()
        check("queue_info: active=1 queued=2",
              qi["active"] == 1 and qi["queued"] == 2)
        check("queued_ids FIFO tartibda", qi["queued_ids"] == ["r2", "r3"])

    def test_fifo_order_on_finish(self):
        rm = self._rm(1)
        rec = []
        s1, s2, s3 = ({"id": f"r{i}", "status": "init"} for i in (1, 2, 3))
        rm._enqueue("r1", s1, _make_launch(rec, "r1"))
        rm._enqueue("r2", s2, _make_launch(rec, "r2"))
        rm._enqueue("r3", s3, _make_launch(rec, "r3"))
        rm._on_run_finished("r1")
        check("r1 tugadi -> r2 ishga tushdi (FIFO)",
              s2["status"] == "running" and rec == ["r1", "r2"])
        rm._on_run_finished("r2")
        check("r2 tugadi -> r3 ishga tushdi (FIFO)",
              s3["status"] == "running" and rec == ["r1", "r2", "r3"])
        rm._on_run_finished("r3")
        check("hammasi tugadi -> queue bo'sh",
              rm.queue_info()["active"] == 0 and rm.queue_info()["queued"] == 0)

    def test_max_concurrent_2(self):
        rm = self._rm(2)
        rec = []
        s1, s2, s3 = ({"id": f"r{i}", "status": "init"} for i in (1, 2, 3))
        rm._enqueue("r1", s1, _make_launch(rec, "r1"))
        rm._enqueue("r2", s2, _make_launch(rec, "r2"))
        rm._enqueue("r3", s3, _make_launch(rec, "r3"))
        check("sig'im 2: r1 va r2 darhol ishlaydi",
              s1["status"] == "running" and s2["status"] == "running")
        check("faqat r3 navbatda", s3["status"] == "queued")
        rm._on_run_finished("r1")
        check("r1 tugadi -> r3 chiqdi",
              s3["status"] == "running" and rec == ["r1", "r2", "r3"])

    def test_cancel_queued_run(self):
        rm = self._rm(1)
        rec = []
        s1, s2 = {"id": "r1", "status": "init"}, {"id": "r2", "status": "init"}
        rm._enqueue("r1", s1, _make_launch(rec, "r1"))
        rm._enqueue("r2", s2, _make_launch(rec, "r2"))
        # r2 navbatda — cancel qilinadi
        ok = rm.cancel("r2")
        check("navbatdagi run cancel -> True", ok is True)
        check("navbatdagi run status -> cancelled", s2["status"] == "cancelled")
        check("navbatdan olib tashlandi", rm.queue_info()["queued"] == 0)
        # r1 tugadi — r2 HECH QACHON ishga tushmasligi kerak
        rm._on_run_finished("r1")
        check("bekor qilingan run ishga tushmadi", rec == ["r1"])
        qi = rm.queue_info()
        check("yakunda active=0 queued=0",
              qi["active"] == 0 and qi["queued"] == 0)

    def test_cancel_running_and_unknown(self):
        rm = self._rm(1)
        rec = []
        s1 = {"id": "r1", "status": "init"}
        rm._enqueue("r1", s1, _make_launch(rec, "r1"))
        check("running run cancel -> True (eski kontrakt)", rm.cancel("r1") is True)
        check("unknown run cancel -> False", rm.cancel("nope") is False)


# ------------------------------------------------------------------ #
# HEALTH METRICS: runs + system fallback
# ------------------------------------------------------------------ #

class TestHealthMetricsRuns(unittest.TestCase):

    def test_runs_section(self):
        try:
            from server.server_health import collect_health_metrics
        except Exception as exc:
            self.skipTest(f"server_health import bo'lmadi: {exc}")
        try:
            from server.server import RunManager
        except Exception:
            RunManager = None
        if RunManager is None:
            check("runs bo'limi: RunManager mavjud", False)
            return
        rm = RunManager(max_concurrent=1)
        rm._enqueue("r1", {"id": "r1", "status": "running"}, lambda: None)
        rm._enqueue("r2", {"id": "r2", "status": "init"}, lambda: None)

        class _StubAgent:  # agent=None bo'lsa funksiya erta return qiladi
            @staticmethod
            def status():
                return {"bricks": {"total": 0}, "knowledge": {"rules": 0},
                        "chains": {}}

        m = collect_health_metrics(agent=_StubAgent(), run_manager=rm)
        runs = m.get("runs") or {}
        check("runs bo'limi bor", "error" not in runs)
        check("runs: max_concurrent=1", runs.get("max_concurrent") == 1)
        check("runs: active=1 queued=1",
              runs.get("active") == 1 and runs.get("queued") == 1)
        check("runs: runs_total=2", runs.get("runs_total") == 2)

    def test_runs_section_without_manager(self):
        try:
            from server.server_health import collect_health_metrics
        except Exception as exc:
            self.skipTest(f"server_health import bo'lmadi: {exc}")

        class _StubAgent:
            @staticmethod
            def status():
                return {"bricks": {"total": 0}, "knowledge": {"rules": 0},
                        "chains": {}}

        m = collect_health_metrics(agent=_StubAgent(), run_manager=None)
        runs = m.get("runs") or {}
        check("run_manager yo'q -> error shakli saqlanadi", "error" in runs)

    def test_system_section_no_crash(self):
        """psutil yo'q bo'lsa lightweight fallback — section baribir to'ladi."""
        try:
            from server.server_health import collect_health_metrics
        except Exception as exc:
            self.skipTest(f"server_health import bo'lmadi: {exc}")

        class _StubAgent:
            @staticmethod
            def status():
                return {"bricks": {"total": 0}, "knowledge": {"rules": 0},
                        "chains": {}}

        m = collect_health_metrics(agent=_StubAgent(), run_manager=None)
        system = m.get("system") or {}
        check("system bo'limi crash qilmadi", "error" not in system)
        # psutil bo'l-bo'lmas — pid baribir bo'ladi (ikki yo'lda ham)
        check("system: pid bor", bool(system.get("pid")))


if __name__ == "__main__":
    unittest.main(exit=False)
    ok = sum(1 for _, c in CHECKS if c)
    print(f"\n=== C4 HARDENING: {ok}/{len(CHECKS)} CHECKS "
          f"{'PASS' if ok == len(CHECKS) else 'FAIL'} ===")
    sys.exit(0 if ok == len(CHECKS) else 1)
