"""
Roadmap v2 — Phase B1 testlari: VERIFIED-ONLY SPEECH
=====================================================

Qamrov:
  - _verify_summary_claims: haqiqiy da'vo o'tadi, yolg'on fayl da'vosi ushlanadi,
    bajarilmagan tool da'vosi ushlanadi, bo'sh xulosa xavfsiz
  - _apply_claim_check: result maydonlari (final_claims_checked,
    unverified_claims), correction xulosaga qo'shiladi, recovery log
  - run() E2E: planned loop yakunida claim check ishlaydi (fail-safe)
  - Regressiya: oddiy run oqimi buzilmaydi

Run: python test_phase_b1_verified_speech.py
"""

import json
import os
import sys
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from executor.executor import AgentExecutor  # noqa: E402

_RESULTS = []


def check(name, cond):
    _RESULTS.append((name, bool(cond)))
    return bool(cond)


WS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")


def _mk_executor(llm=None):
    return AgentExecutor(
        workspace_root=WS, llm=llm, memory=None, mcp=None, human_provider=None,
    )


class _QuietLLM:
    """Hech narsa qaytarmaydigan stub (faqat _verify_* ni sinash uchun)."""

    def complete(self, prompt, system=None):
        return None

    def chat(self, messages, system=None):
        return "ok"


class TestVerifySummaryClaims(unittest.TestCase):

    def setUp(self):
        self.ex = _mk_executor(_QuietLLM())

    def test_true_claim_with_tool_evidence(self):
        tc = [{"tool": "write_file", "args": {"path": "hello.txt", "content": "x"},
               "result": {"ok": True}}]
        ok, note, un = self.ex._verify_summary_claims(
            "hello.txt fayli yaratildi va to'ldirildi.", "task", tc)
        self.assertTrue(ok)
        self.assertEqual(un, [])
        check("haqiqiy da'vo (tool dalil) o'tadi", ok)

    def test_false_file_claim_caught(self):
        ok, note, un = self.ex._verify_summary_claims(
            "config.json fayli yaratildi.", "task", [])
        self.assertFalse(ok)
        self.assertTrue(any(u["type"] == "file" and "config.json" in u["claim"] for u in un))
        self.assertIn("claim-check", note)
        check("yolg'on fayl da'vosi ushlanadi", not ok)

    def test_file_claim_verified_via_workspace(self):
        # workspace'da haqiqatan mavjud fayl — dalil tool_calls'da yo'q lekin diskda bor
        existing = None
        for root, _, files in os.walk(WS):
            for f in files:
                if f.endswith((".txt", ".py", ".md", ".json")):
                    existing = f
                    break
            if existing:
                break
        if not existing:
            self.skipTest("workspace'da test fayli yo'q")
        ok, _, un = self.ex._verify_summary_claims(
            f"{existing} tayyor.", "task", [])
        self.assertTrue(ok)
        check(f"workspace'da mavjud fayl da'vosi o'tadi ({existing})", ok)

    def test_unexecuted_tool_claim_caught(self):
        # 'write_file' xulosada tilga olingan, lekin tool_calls bo'sh
        ok, note, un = self.ex._verify_summary_claims(
            "Men write_file bilan fayl yozdim va taskni tugatdim.", "task", [])
        # fayl patterni yo'q; lekin 'write_file' nomi bajarilmagan — flag
        self.assertFalse(ok)
        self.assertTrue(any(u["type"] == "tool_not_executed" for u in un))
        check("bajarilmagan tool da'vosi ushlanadi", not ok)

    def test_empty_summary_safe(self):
        ok, note, un = self.ex._verify_summary_claims("", "task", [])
        self.assertTrue(ok)
        self.assertEqual(un, [])
        ok2, _, _ = self.ex._verify_summary_claims("   ", "task", [])
        self.assertTrue(ok2)
        check("bo'sh xulosa xavfsiz", True)

    def test_no_file_pattern_no_false_positive(self):
        # fayl ko'rinishida bo'lmagan oddiy matn — hech qachon flaglanmaydi
        ok, _, un = self.ex._verify_summary_claims(
            "Barcha ishlar muvaffaqiyatli yakunlandi. Rahmat!", "task", [])
        self.assertTrue(ok)
        self.assertEqual(un, [])
        check("oddiy matn false-positive yo'q", ok)


class TestApplyClaimCheck(unittest.TestCase):

    def setUp(self):
        self.ex = _mk_executor(_QuietLLM())

    def test_result_fields_on_clean_summary(self):
        result = {}
        out = self.ex._apply_claim_check("Ish tugadi.", "task", [], result, "ok")
        self.assertEqual(result.get("final_claims_checked"), True)
        self.assertEqual(result.get("unverified_claims"), [])
        self.assertEqual(out, "Ish tugadi.")
        check("toza xulosa: result maydonlari", result.get("final_claims_checked") is True)

    def test_correction_appended_and_logged(self):
        result = {}
        out = self.ex._apply_claim_check(
            "config.json yaratildi va deploy qilindi.", "task", [], result, "ok")
        self.assertEqual(result.get("final_claims_checked"), True)
        self.assertTrue(result.get("unverified_claims"))
        self.assertIn("[claim-check]", out)
        self.assertIn("config.json", out)
        # recovery log'ga yozilgan
        self.assertTrue(any(ev.get("action") == "claim_check" for ev in self.ex._recovery_log))
        check("correction qo'shildi + recovery log", "[claim-check]" in out)

    def test_empty_final_no_false_correction(self):
        # Bo'sh finalda da'vo HAM yo'q — claim-check o'tadi (hech narsa qo'shilmaydi).
        # (Correction faqat DALILSIZ DA'VO bo'lganda yoziladi.)
        result = {}
        out = self.ex._apply_claim_check("", "task", [], result, "partial")
        self.assertEqual(result.get("final_claims_checked"), True)
        self.assertEqual(out, "")
        check("bo'sh final: da'vo yo'q -> correction yo'q", out == "")


class _PlanLLM:
    """run() E2E uchun stub — kontentga qarab javob beradi (holat emas).

    Executor complete() ni turli maqsadlarda chaqiradi (reja, tool args,
    corrective...). Prompt tahlili orqali to'g'ri javob qaytaramiz:
      - promptda 'write_file' tool nomi + schema -> args JSON
      - promptda 'steps' so'rovi -> reja JSON
    chat() — final xulosa.
    """

    ARGS = json.dumps({"path": "b1_note.txt", "content": "salom"})
    PLAN = json.dumps({
        "goal": "create note",
        "steps": [{"id": 1, "title": "write note", "tools": ["write_file"],
                   "detail": "create b1_note.txt"}],
    })
    SUMMARY = "b1_note.txt fayli yaratildi va deploy ham qilindi."

    def complete(self, prompt, system=None):
        p = (prompt or "") + (system or "")
        if "write_file" in p and "path" in p:
            return self.ARGS
        if "steps" in p or "goal" in p:
            return self.PLAN
        return self.SUMMARY

    def chat(self, messages, system=None):
        return self.SUMMARY


class TestRunE2EClaimCheck(unittest.TestCase):

    def test_run_result_contains_claim_check(self):
        ex = AgentExecutor(workspace_root=WS, llm=_PlanLLM(), memory=None,
                           mcp=None, human_provider=None, max_iter=4)
        # Task 'create' so'zini o'z ichiga oladi → quality gate ham ishlaydi;
        # b1_note.txt haqiqatan yozilganligi uchun gate o'tadi.
        res = ex.run("create note file b1_note")
        self.assertIn(res["status"], ("ok", "partial"))
        # B1: result'da final_claims_checked bo'lishi SHART (fail-safe ham True/False)
        self.assertIn("final_claims_checked", res)
        self.assertTrue(res.get("final_claims_checked"))
        # xulosa (yoki quality gate note) mavjud; claim-check natijasi result'da
        final = res.get("final", "")
        self.assertTrue(final)
        # haqiqiy fayl diskda mavjud (write_file bajarilgan)
        self.assertTrue(os.path.isfile(os.path.join(WS, "b1_note.txt")))
        check("E2E: final_claims_checked=True", res.get("final_claims_checked") is True)
        check("E2E: haqiqiy fayl yaratilgan", os.path.isfile(os.path.join(WS, "b1_note.txt")))


if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    ok = sum(1 for _, s in _RESULTS if s)
    print(f"\nCHECKS: {ok}/{len(_RESULTS)} " + ("PASS" if ok == len(_RESULTS) else "FAIL"))
    sys.exit(0 if ok == len(_RESULTS) else 1)
