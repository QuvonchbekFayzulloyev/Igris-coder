# -*- coding: utf-8 -*-
"""Roadmap v2 — Phase C2: birlashgan timeline[] testlari.

Yopiladigan bo'shliq (§16 Observability): SM + tools + errors + recovery +
verifications birlashtirilgan chronological timeline — "nima bo'ldi?" savoliga
bitta strukturali javob.
"""
import os
import sys
import tempfile
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

try:  # Roadmap v2 C3: e2e marker — CI'da alohida job (pytest.ini'da ro'yxatda)
    import pytest  # noqa: F401
    pytestmark = pytest.mark.e2e
except ImportError:
    pytestmark = None

from executor.executor import AgentExecutor  # noqa: E402

CHECKS = []


def check(name, cond):
    CHECKS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL") + f"  {name}")


# ---------------------------------------------------------------- test LLMy

class _PlanLLM:
    """Planned loop uchun oddiy stub: reja + tool-args."""

    def __init__(self, ws_root):
        self.ws_root = ws_root
        self.calls = 0

    def chat(self, messages, **kw):
        self.calls += 1
        last = str(messages[-1].get("content", "")) if messages else ""
        if "plan" in last.lower() or "steps" in last.lower():
            return ('{"decision": "plan", "steps": ['
                    '{"id": "s1", "title": "Write file", '
                    '"tools": ["write_file"], "detail": "write note"}]}')
        if "args" in last.lower() or "arguments" in last.lower():
            return '{"path": "c2_note.md", "content": "c2 timeline note"}'
        return "Bajarildi"

    def complete(self, system=None, prompt="", **kw):
        return self.chat([{"content": system or ""}, {"content": prompt}])


class _NativeLLM:
    """Native loop stub: 1 tool-call iteratsiya, so'ng final content."""

    def __init__(self):
        self.calls = 0

    def chat_with_tools(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            return {
                "reasoning": "Fayl yozish uchun write_file kerak",
                "tool_calls": [{"name": "write_file",
                                "arguments": {"path": "c2_native.md",
                                              "content": "native c2"}}],
            }
        return {"content": "Ish tugadi: c2_native.md yozildi"}

    def complete(self, prompt, system=None):
        return None

    def chat(self, messages, system=None):
        return "barcha ishlar bajarildi"


# ---------------------------------------------------------------- testlar

class TestTimelinePlanned(unittest.TestCase):
    """Planned loop: timeline qatlamlari va tartibi."""

    def test_timeline_layers_and_monotonic(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = AgentExecutor(workspace_root=tmp, llm=_PlanLLM(tmp),
                               memory=None, mcp=None, human_provider=None,
                               max_iter=4)
            res = ex.run("create note file c2")
            tl = res.get("timeline") or []

            check("timeline bo'sh emas", len(tl) >= 3)
            layers = {e.get("layer") for e in tl}
            check("sm qatlami bor", "sm" in layers)
            check("tool qatlami bor", "tool" in layers)
            check("verify qatlami bor", "verify" in layers)

            # ts monotonic (None tugatiladi)
            ts_list = [e.get("ts") for e in tl]
            numeric = [t for t in ts_list if t is not None]
            check("ts qiymatlari bor", len(numeric) >= 2)
            check("ts monotonic",
                  all(numeric[i] <= numeric[i + 1]
                      for i in range(len(numeric) - 1)))

            # maydonlar kontrakti
            ev0 = tl[0]
            for k in ("ts", "layer", "kind", "detail"):
                check(f"event maydoni: {k}", k in ev0)

            # sm event struktura
            sm = [e for e in tl if e["layer"] == "sm"]
            check("sm event from/to maydonlari",
                  all("to" in e for e in sm))

            # tool event struktura
            tl_tools = [e for e in tl if e["layer"] == "tool"]
            check("tool event tool/action_id maydonlari",
                  all("tool" in e and "action_id" in e for e in tl_tools))


class _BadArgsLLM(_PlanLLM):
    """Plan to'g'ri, lekin tool-args invalid path — write_file xato beradi."""

    def complete(self, system=None, prompt="", **kw):
        text = str(prompt or "")
        if "plan" in text.lower() or "steps" in text.lower():
            return ('{"decision": "plan", "steps": ['
                    '{"id": "s1", "title": "Write file", '
                    '"tools": ["write_file"], "detail": "write note"}]}')
        # tool-args so'rovi → invalid path (mavjud bo'lmagan katalog)
        return '{"path": "Z:/__no_such_dir__/c2_err.txt", "content": "x"}'


class TestTimelineErrorRecovery(unittest.TestCase):
    """Xato va recovery voqealari timeline'da ko'rinadi."""

    def test_error_layer_in_timeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = AgentExecutor(workspace_root=tmp, llm=_BadArgsLLM(tmp),
                               memory=None, mcp=None, human_provider=None,
                               max_iter=4)
            # invalid path — write_file xato beradi → error qatlami
            res = ex.run("create note file c2_err")
            tl = res.get("timeline") or []
            layers = {e.get("layer") for e in tl}
            check("timeline to'liq (sm+tool)", {"sm", "tool"} <= layers)
            check("error qatlami bor", "error" in layers)
            err = [e for e in tl if e["layer"] == "error"]
            check("error event turi va xabari bor",
                  all(e.get("type") and e.get("detail") for e in err))
            # xato voqeasi tool voqeasidan keyin yoki bir xil ts — tartib saqlangan
            check("error event maydonlari to'liq",
                  all("ts" in e and "kind" in e for e in err))
            # result errors[] bilan timeline error qatlami mos
            n_errors = len(res.get("errors") or [])
            check("errors[] soni = timeline error soni",
                  n_errors == len(err),)


class TestTimelineNative(unittest.TestCase):
    """Native loop: decision_trace bilan birga timeline ham bo'ladi."""

    def test_native_timeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = AgentExecutor(workspace_root=tmp, llm=_NativeLLM(),
                               memory=None, mcp=None, human_provider=None,
                               max_iter=4)
            res = ex.run_native("write c2_native.md file")
            tl = res.get("timeline") or []
            check("native timeline bo'sh emas", len(tl) >= 3)
            layers = {e.get("layer") for e in tl}
            check("native tool qatlami bor", "tool" in layers)
            check("native sm qatlami bor", "sm" in layers)
            check("decision_trace ham bor",
                  len(res.get("decision_trace") or []) >= 1)


if __name__ == "__main__":
    unittest.main(exit=False)
    ok = sum(1 for _, c in CHECKS if c)
    print(f"\n=== C2 TIMELINE: {ok}/{len(CHECKS)} CHECKS "
          f"{'PASS' if ok == len(CHECKS) else 'FAIL'} ===")
    sys.exit(0 if ok == len(CHECKS) else 1)
