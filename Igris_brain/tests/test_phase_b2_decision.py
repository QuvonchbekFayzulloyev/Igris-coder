"""
Roadmap v2 — Phase B2 testlari: RASMIY DECISION MODELI + VALIDATION LAYER
==========================================================================

Qamrov:
  - PlanStep: from_dict xavfsizligi (invalid id/types), validate
  - Decision: from_plan round-trip, invalid qiymatlar rad etilishi,
    exception irmaslik, confidence clamp, engine/intent guard
  - validate_llm_output: parse → schema → tools zanjiri (3 bosqich)
  - planner.decide(): fasad, fallback intent
  - Backward compatibility: to_dict() plan dict shaklini saqlaydi

Run: python test_phase_b2_decision.py
"""

import json
import os
import sys
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from planning.decision import Decision, PlanStep  # noqa: E402
from planning.validation import validate_llm_output, validate_plan_json  # noqa: E402
from planning.planner import TaskPlanner  # noqa: E402

_RESULTS = []


def check(name, cond):
    _RESULTS.append((name, bool(cond)))
    return bool(cond)


class TestPlanStep(unittest.TestCase):

    def test_from_dict_valid(self):
        s = PlanStep.from_dict({"id": 2, "title": "yoz", "tools": ["write_file"], "detail": "d"})
        self.assertEqual(s.id, 2)
        self.assertEqual(s.tools, ["write_file"])
        check("PlanStep.from_dict valid", s.id == 2 and s.tools == ["write_file"])

    def test_from_dict_invalid_id_falls_back(self):
        s = PlanStep.from_dict({"id": "abc", "title": "t"}, fallback_id=3)
        self.assertEqual(s.id, 3)
        check("invalid id -> fallback", s.id == 3)

    def test_from_dict_non_dict(self):
        s = PlanStep.from_dict("just text", fallback_id=1)
        self.assertEqual(s.id, 1)
        self.assertIn("just text", s.title)
        check("non-dict xavfsiz", s.id == 1)

    def test_validate_tool_name_format(self):
        s = PlanStep(id=1, title="t", tools=["good_tool", "bad tool!"], detail="")
        errs = s.validate()
        self.assertTrue(any("bad tool" in e for e in errs))
        check("tool nom formati tekshiriladi", len(errs) == 1)


class TestDecision(unittest.TestCase):

    def test_round_trip_from_plan_to_dict(self):
        plan = {
            "goal": "x",
            "reasoning": "chunki",
            "confidence": 0.8,
            "intent": "code",
            "steps": [{"id": 1, "title": "a", "tools": ["read_file"], "detail": ""}],
            "engine": "llm",
        }
        d = Decision.from_plan(plan, task="x")
        back = d.to_dict()
        self.assertEqual(back["goal"], "x")
        self.assertEqual(back["reasoning"], "chunki")
        self.assertEqual(back["confidence"], 0.8)
        self.assertEqual(back["intent"], "code")
        self.assertEqual(back["steps"][0]["tools"], ["read_file"])
        check("round-trip: plan -> Decision -> plan", back["goal"] == "x" and back["intent"] == "code")

    def test_invalid_values_never_raise(self):
        # har qanday axlat kirish — exception YO'Q
        d = Decision.from_plan({
            "confidence": "yuqori", "steps": "steps emas", "engine": 123,
            "reasoning": 456, "intent": "noma'lum-intent",
        }, task=None)
        self.assertIsInstance(d, Decision)
        self.assertEqual(d.confidence, 0.5)  # default
        self.assertEqual(d.engine, "llm")    # default
        self.assertEqual(d.reasoning, "456") # str() ga aylantirildi
        self.assertEqual(d.intent, "")       # noma'lum -> bo'sh
        check("axlat kirish -> exception yo'q, defaultlar", d.confidence == 0.5)

    def test_confidence_clamped(self):
        d = Decision.from_plan({"confidence": 5.0, "steps": []})
        self.assertEqual(d.confidence, 1.0)
        d2 = Decision.from_plan({"confidence": -2, "steps": []})
        self.assertEqual(d2.confidence, 0.0)
        check("confidence 0..1 clamp", d.confidence == 1.0 and d2.confidence == 0.0)

    def test_validate_llm_engine_empty_steps(self):
        d = Decision.from_plan({"goal": "x", "engine": "llm", "steps": []})
        errs = d.validate()
        self.assertTrue(any("steps" in e for e in errs))
        check("llm + bo'sh steps -> xato", len(errs) >= 1)

    def test_validate_duplicate_step_ids(self):
        d = Decision(steps=[
            PlanStep(id=1, title="a"), PlanStep(id=1, title="b"),
        ], decision="x")
        errs = d.validate()
        self.assertTrue(any("takrorlangan" in e for e in errs))
        check("duplicate step.id ushlanadi", len(errs) >= 1)

    def test_is_confident_and_tool_names(self):
        d = Decision(decision="x", confidence=0.7, steps=[
            PlanStep(id=1, title="a", tools=["read_file", "list_files"]),
            PlanStep(id=2, title="b", tools=["read_file"]),
        ])
        self.assertTrue(d.is_confident)
        self.assertEqual(d.tool_names(), ["read_file", "list_files"])
        check("is_confident + tool_names unique", d.tool_names() == ["read_file", "list_files"])


class TestValidationChain(unittest.TestCase):

    def test_clean_plan_passes_all_stages(self):
        r = validate_llm_output(
            json.dumps({"goal": "x", "steps": [{"id": 1, "title": "a", "tools": ["read_file"], "detail": ""}]}),
            task="x", allowed_tools=["read_file", "list_files"])
        self.assertTrue(r.ok)
        self.assertEqual(r.source, "ok")
        self.assertIsNotNone(r.decision)
        check("toza plan: 3 bosqich o'tadi", r.ok and r.source == "ok")

    def test_parse_failure_reported(self):
        r = validate_llm_output("bu umuman JSON emas", task="x")
        self.assertFalse(r.ok)
        self.assertEqual(r.source, "parse")
        check("parse bosqichi xatosi", r.source == "parse")

    def test_schema_failure_reported(self):
        # engine=llm + bo'sh steps -> schema xato
        r = validate_llm_output(json.dumps({"goal": "x", "engine": "llm", "steps": []}), task="x")
        self.assertFalse(r.ok)
        self.assertEqual(r.source, "schema")
        check("schema bosqichi xatosi", r.source == "schema")

    def test_hallucinated_tool_reported(self):
        r = validate_llm_output(
            json.dumps({"goal": "x", "steps": [{"id": 1, "title": "a", "tools": ["deploy_prod"], "detail": ""}]}),
            task="x", allowed_tools=["read_file"])
        self.assertFalse(r.ok)
        self.assertEqual(r.source, "tools")
        self.assertIn("deploy_prod", r.errors[0])
        check("hallucinated tool tools bosqichida ushlanadi", r.source == "tools")

    def test_validate_plan_json_direct(self):
        r = validate_plan_json({"goal": "x", "confidence": 1.0,
                                "steps": [{"id": 1, "title": "a", "tools": [], "detail": ""}]},
                               allowed_tools=None)
        self.assertTrue(r.ok)
        check("validate_plan_json to'g'ridan-to'g'ri", r.ok)


class TestPlannerDecide(unittest.TestCase):

    def test_decide_fallback_intent_and_confidence(self):
        p = TaskPlanner(llm=None)
        d = p.decide("create notes.txt with hello")
        self.assertEqual(d.engine, "fallback")
        self.assertEqual(d.confidence, 1.0)
        self.assertGreater(len(d.steps), 0)
        check("decide(): fallback + conf 1.0 + steps", d.confidence == 1.0)

    def test_decide_with_requirements_intent(self):
        # requirements — haqiqiy Requirement modeli (core/requirements.py)
        from core.requirements import Requirement
        req = Requirement(intent="code")
        p = TaskPlanner(llm=None)
        d = p.decide("create app.py", requirements=req)
        self.assertEqual(d.intent, "code")
        check("decide(): requirements.intent olinadi", d.intent == "code")

    def test_decide_with_allowed_tools_guard(self):
        p = TaskPlanner(llm=None)
        d = p.decide("create notes.txt", allowed_tools=["read_file"])
        # fallback reja write_file'ni o'z ichiga olishi mumkin — guard source belgilaydi
        if any("write_file" in s.tools for s in d.steps):
            self.assertEqual(d.source, "tools_rejected")
            check("allowed_tools guard: rad etilgan belgilandi", d.source == "tools_rejected")
        else:
            self.assertEqual(d.source, "planner")
            check("allowed_tools guard: reja toza", d.source == "planner")

    def test_backward_compatible_plan_shape(self):
        p = TaskPlanner(llm=None)
        plan = p.plan("create notes.txt with hello")
        # eski kod kutgan maydonlar: goal, steps, engine — HECH QANDAY o'zgarish yo'q
        self.assertIn("goal", plan)
        self.assertIn("steps", plan)
        self.assertIn("engine", plan)
        d = Decision.from_plan(plan, task="create notes.txt")
        back = d.to_dict()
        self.assertIn("goal", back)
        self.assertIn("steps", back)
        self.assertIn("engine", back)
        check("backward-compatible plan shakli", all(k in back for k in ("goal", "steps", "engine")))


if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    ok = sum(1 for _, s in _RESULTS if s)
    print(f"\nCHECKS: {ok}/{len(_RESULTS)} " + ("PASS" if ok == len(_RESULTS) else "FAIL"))
    sys.exit(0 if ok == len(_RESULTS) else 1)
