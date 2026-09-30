"""A1 1-qadam — Python sintaksis verifikatori testlari.

Executor sifat darvozasida 120+ belgili .py fayl BUZUQ sintaksis bilan
o'tib ketmasligi kerak (ilgari faqat uzunlik tekshirilardi).

Run: python -m pytest test_deliverable_syntax.py -q
"""
import os
import sys
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from executor.executor import _python_syntax_check  # noqa: E402


class TestPythonSyntaxCheck(unittest.TestCase):

    def test_valid_code_passes(self):
        ok, note = _python_syntax_check("def add(a, b):\n    return a + b\n")
        self.assertTrue(ok)
        self.assertEqual(note, "")

    def test_long_valid_code_passes(self):
        code = "import os\n\n" + "\n".join(
            f"def fn_{i}(x):\n    return x * {i} + 1" for i in range(12))
        ok, _ = _python_syntax_check(code)
        self.assertTrue(ok)

    def test_broken_code_fails(self):
        ok, note = _python_syntax_check("def broken(:\n    pass")
        self.assertFalse(ok)
        self.assertIn("line", note)

    def test_missing_colon_fails(self):
        ok, note = _python_syntax_check("def f()\n    return 1\n")
        self.assertFalse(ok)

    def test_indentation_error_fails(self):
        ok, note = _python_syntax_check("def f():\nreturn 1\n")
        self.assertFalse(ok)
        self.assertTrue("line" in note or "indent" in note.lower())

    def test_unbalanced_parens_fails(self):
        ok, _ = _python_syntax_check("x = (1 + 2\nprint(x)")
        self.assertFalse(ok)

    def test_empty_is_neutral(self):
        ok, _ = _python_syntax_check("")
        self.assertTrue(ok)
        ok, _ = _python_syntax_check("   \n  ")
        self.assertTrue(ok)

    def test_note_takes_non_string(self):
        ok, _ = _python_syntax_check(None)
        self.assertTrue(ok)


class TestVerifyDeliverablePythonGate(unittest.TestCase):
    """Butun gate yo'li: buzuk .py fayl gate'dan O'TMASLIGI kerak."""

    def _exec(self, tmp):
        from executor.executor import AgentExecutor
        ex = AgentExecutor(workspace_root=tmp, llm=None)
        return ex

    def test_broken_py_rejected_by_gate(self):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="igris_syn_")
        ex = self._exec(tmp)
        broken = ("# model yozgan buzuk modul\n" + "import os\n\n" +
                  "def run(data):\n    if data is None\n        return []\n" +
                  "    result = [x for x in data if x\n")
        # gate workspace.read orqali DISKDAN o'qiydi — avval yozamiz
        ex.workspace.write("run.py", broken)
        ok, note = ex._verify_deliverable(
            "run.py faylini yoz", [
                {"tool": "write_file", "args": {"path": "run.py", "content": broken}},
            ])
        self.assertFalse(ok, "buzuk python fayl gate'dan o'tdi!")
        self.assertIn("sintaksis", note.lower())

    def test_valid_py_accepted_by_gate(self):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="igris_syn_")
        ex = self._exec(tmp)
        valid = ("import os\n\n" + "\n".join(
            f"def util_{i}(a, b):\n    return a + b * {i}" for i in range(10)))
        ex.workspace.write("good.py", valid)
        ok, note = ex._verify_deliverable(
            "good.py faylini yoz", [
                {"tool": "write_file", "args": {"path": "good.py", "content": valid}},
            ])
        self.assertTrue(ok, f"to'g'ri fayl rad etildi: {note}")

    def test_non_python_file_unaffected(self):
        """Boshqa kengaytmalar (.md/.txt/.json) sintaksis tekshiruvida yo'q — odatiy oqim."""
        import tempfile
        tmp = tempfile.mkdtemp(prefix="igris_syn_")
        ex = self._exec(tmp)
        md = "# Sarlavha\n\n" + "paragraf matn. " * 30
        ex.workspace.write("doc.md", md)
        ok, note = ex._verify_deliverable(
            "doc.md yoz", [
                {"tool": "write_file", "args": {"path": "doc.md", "content": md}},
            ])
        self.assertTrue(ok, f"markdown fayl rad etildi: {note}")


if __name__ == "__main__":
    unittest.main()
