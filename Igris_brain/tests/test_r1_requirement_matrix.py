# -*- coding: utf-8 -*-
"""
Roadmap v3 R1 testlari: REQUIREMENT MATRIX + COMPLETION CONTRACT
================================================================

Qamrov (TODO §2/§17/§28/§19):
  - Extraction: mandatory/optional, fayl nomi + fe'l konteksti
  - Snapshot immutablligi (§2)
  - Matrix runner: deterministik fs checks + REAL evidence (§17)
  - Completion contract: formal statuslar (§28)
  - Executor integratsiya: result.requirement_matrix + completion
  - FALSE COMPLETION senariylari (§19): tool ok=true lekin fayl yo'q →
    executor endi "ok" deyolmaydi (matrix pasaytiradi)

Run: python test_r1_requirement_matrix.py  |  pytest test_r1_requirement_matrix.py
"""

import json
import os
import sys
import tempfile
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from planning.requirement_matrix import (  # noqa: E402
    ReqItem, RequirementSnapshot, extract_requirements, run_matrix,
    completion_status, check_item,
    STATUS_PASS, STATUS_FAIL, STATUS_UNKNOWN,
    CONTRACT_COMPLETE, CONTRACT_PARTIAL, CONTRACT_FAILED, CONTRACT_BLOCKED,
    CHECK_FILE_EXISTS, CHECK_FILE_CONTAINS, CHECK_FILE_ABSENT,
)

CHECKS = []


def check(name, cond):
    CHECKS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL") + f"  {name}")


# ------------------------------------------------------------------ #
# EXTRACTION (§2)
# ------------------------------------------------------------------ #

class TestExtraction(unittest.TestCase):

    def test_file_with_action_verb_mandatory(self):
        reqs = extract_requirements("report.txt faylini yarat va yoz")
        check("fayl req topildi", len(reqs) == 1)
        check("mandatory", reqs[0].kind == "mandatory")
        check("target report.txt", reqs[0].target == "report.txt")
        check("check=file_exists", reqs[0].check == CHECK_FILE_EXISTS)

    def test_optional_hint(self):
        reqs = extract_requirements(
            "report.txt yarat, agar kerak bo'lsa log.txt ham yoz")
        kinds = {r.target: r.kind for r in reqs}
        check("report.txt mandatory", kinds.get("report.txt") == "mandatory")
        check("log.txt optional", kinds.get("log.txt") == "optional")

    def test_action_verb_without_file(self):
        reqs = extract_requirements("hisob-kitob qilib natijani saqla")
        check("umumiy deliverable req", len(reqs) == 1
              and reqs[0].check == "file_not_empty")

    def test_no_requirements_for_question(self):
        reqs = extract_requirements("python nima? menga tushuntir")
        check("savolga req yo'q", len(reqs) == 0)

    def test_duplicate_filenames_dedup(self):
        reqs = extract_requirements("report.txt yarat va report.txt ni tekshir")
        check("dup olib tashlandi", len(reqs) == 1)


# ------------------------------------------------------------------ #
# SNAPSHOT IMMUTABILITY (§2)
# ------------------------------------------------------------------ #

class TestSnapshot(unittest.TestCase):

    def test_snapshot_roundtrip_and_freeze(self):
        items = extract_requirements("notes.md yarat")
        snap = RequirementSnapshot("notes.md yarat", items)
        js = snap.to_json()
        snap2 = RequirementSnapshot.from_json(js)
        check("roundtrip: item soni", len(snap2.items) == len(snap.items))
        check("roundtrip: target", snap2.items[0].target == "notes.md")
        # items tuple — o'zgartirib bo'lmaydi
        try:
            snap.items.append(ReqItem(id="RX", text="x"))  # type: ignore
            immutable = False
        except AttributeError:
            immutable = True
        check("items o'zgarmas (tuple)", immutable)
        check("mandatory() faqat mandatory", len(snap2.mandatory()) == 1)


# ------------------------------------------------------------------ #
# MATRIX RUNNER (§17)
# ------------------------------------------------------------------ #

class TestMatrixRunner(unittest.TestCase):

    def test_file_exists_fail_then_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = RequirementSnapshot("t", extract_requirements("report.txt yarat"))
            m = run_matrix(snap, tmp)
            check("fayl yo'q -> FAIL", m["matrix"][0]["status"] == STATUS_FAIL)
            check("evidence: exists=False",
                  m["matrix"][0]["evidence"].get("exists") is False)
            with open(os.path.join(tmp, "report.txt"), "w", encoding="utf-8") as fh:
                fh.write("IGRIS TEST CONTENT" * 5)
            m2 = run_matrix(snap, tmp)
            check("fayl bor -> PASS", m2["matrix"][0]["status"] == STATUS_PASS)
            check("evidence: size > 0",
                  m2["matrix"][0]["evidence"].get("size", 0) > 0)

    def test_file_contains_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.txt"), "w", encoding="utf-8") as fh:
                fh.write("IGRIS REAL TASK TEST")
            it = ReqItem(id="R1", text="a.txt contains TEST", kind="mandatory",
                         check=CHECK_FILE_CONTAINS, target="a.txt")
            it.text = "TEST"  # contains pattern sifatida ishlatiladi
            status, ev = check_item(tmp, it)
            check("contains -> PASS", status == STATUS_PASS and ev.get("pattern_found") is True)
            it2 = ReqItem(id="R2", text="YO'Q", kind="mandatory",
                          check=CHECK_FILE_CONTAINS, target="a.txt")
            status2, _ = check_item(tmp, it2)
            check("contains yo'q -> FAIL", status2 == STATUS_FAIL)

    def test_file_absent_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            it = ReqItem(id="R1", text="old.txt o'chirilgan", kind="mandatory",
                         check=CHECK_FILE_ABSENT, target="old.txt")
            status, _ = check_item(tmp, it)
            check("absent -> PASS", status == STATUS_PASS)
            with open(os.path.join(tmp, "old.txt"), "w") as fh:
                fh.write("x")
            status2, _ = check_item(tmp, it)
            check("absent buzildi -> FAIL", status2 == STATUS_FAIL)


# ------------------------------------------------------------------ #
# COMPLETION CONTRACT (§28)
# ------------------------------------------------------------------ #

class TestCompletionContract(unittest.TestCase):

    def _row(self, kind="mandatory", status=STATUS_PASS):
        return {"id": "R1", "kind": kind, "status": status}

    def test_all_pass_complete(self):
        check("all PASS -> complete",
              completion_status([self._row(), self._row()]) == CONTRACT_COMPLETE)

    def test_one_fail_partial(self):
        m = [self._row(status=STATUS_PASS), self._row(status=STATUS_FAIL)]
        check("PASS+FAIL -> partial", completion_status(m) == CONTRACT_PARTIAL)

    def test_all_fail_failed(self):
        m = [self._row(status=STATUS_FAIL), self._row(status=STATUS_FAIL)]
        check("all FAIL -> failed", completion_status(m) == CONTRACT_FAILED)

    def test_unknown_blocked(self):
        m = [self._row(status=STATUS_PASS), self._row(status=STATUS_UNKNOWN)]
        check("PASS+UNKNOWN -> blocked", completion_status(m) == CONTRACT_BLOCKED)

    def test_optional_ignored(self):
        m = [self._row(kind="optional", status=STATUS_FAIL)]
        check("faqat optional FAIL -> complete", completion_status(m) == CONTRACT_COMPLETE)

    def test_no_requirements_complete(self):
        check("req yo'q -> complete", completion_status([]) == CONTRACT_COMPLETE)


# ------------------------------------------------------------------ #
# EXECUTOR INTEGRATSIYA + FALSE COMPLETION (§19)
# ------------------------------------------------------------------ #

class _PlanLLMFile:
    """Planned loop stub: report.txt yozadi (content to'liq)."""

    def complete(self, prompt, system=None):
        p = (prompt or "") + (system or "")
        if "write_file" in p and "path" in p:
            return json.dumps({"path": "report.txt",
                               "content": "IGRIS REAL TASK TEST " * 10})
        if "steps" in p or "goal" in p:
            return json.dumps({"goal": "create report", "steps": [
                {"id": 1, "title": "write report", "tools": ["write_file"],
                 "detail": "create report.txt"}]})
        return "report.txt yaratildi"


class _PlanLLMEmpty:
    """Planned loop stub: FAYL YOZMAYDI (false completion senariy)."""

    def complete(self, prompt, system=None):
        p = (prompt or "") + (system or "")
        if "steps" in p or "goal" in p:
            return json.dumps({"goal": "create report", "steps": [
                {"id": 1, "title": "noop", "tools": [], "detail": "nothing"}]})
        return "Bajarildi deb hisoblayman."


class TestExecutorIntegration(unittest.TestCase):

    def test_matrix_pass_with_real_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            from executor.executor import AgentExecutor
            ex = AgentExecutor(workspace_root=tmp, llm=_PlanLLMFile(),
                               memory=None, mcp=None, human_provider=None,
                               max_iter=4)
            res = ex.run("report.txt yarat va ichiga IGRIS REAL TASK TEST yoz")
            check("fayl real yaratildi",
                  os.path.isfile(os.path.join(tmp, "report.txt")))
            check("completion=complete", res.get("completion") == CONTRACT_COMPLETE)
            rm = res.get("requirement_matrix") or []
            check("matrix'da 1 mandatory PASS",
                  len(rm) == 1 and rm[0]["status"] == STATUS_PASS)
            check("evidence mavjud", bool(rm[0].get("evidence")))

    def test_false_completion_blocked(self):
        """§19: tool ok=true / LLM 'bajarildi' — fayl YO'Q → COMPLETE YO'Q."""
        with tempfile.TemporaryDirectory() as tmp:
            from executor.executor import AgentExecutor
            ex = AgentExecutor(workspace_root=tmp, llm=_PlanLLMEmpty(),
                               memory=None, mcp=None, human_provider=None,
                               max_iter=4)
            res = ex.run("report.txt yarat va ichiga IGRIS yoz")
            check("fayl yaratilmadi",
                  not os.path.isfile(os.path.join(tmp, "report.txt")))
            check("completion=failed", res.get("completion") == CONTRACT_FAILED)
            check("executor status pasaytirildi (partial)",
                  res.get("status") == "partial")
            rm = res.get("requirement_matrix") or []
            check("matrix'da FAIL evidence bilan",
                  rm and rm[0]["status"] == STATUS_FAIL
                  and rm[0]["evidence"].get("exists") is False)


if __name__ == "__main__":
    unittest.main(exit=False)
    ok = sum(1 for _, c in CHECKS if c)
    print(f"\n=== R1 REQUIREMENT MATRIX: {ok}/{len(CHECKS)} CHECKS "
          f"{'PASS' if ok == len(CHECKS) else 'FAIL'} ===")
    sys.exit(0 if ok == len(CHECKS) else 1)
