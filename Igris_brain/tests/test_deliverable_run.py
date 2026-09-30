"""A1 2-qadam — Python run-verification testlari.

Executor sifat darvozasida 120+ belgili .py fayl sintaksis to'g'ri lekin
ISHGA TUSHMAYDIGAN holatlarda (NameError, TypeError...) gate'dan o'tmasligi
kerak. Import/deps xatolari NEYTRAL — muhitga bog'liq, gate rad etmaydi.

Run: python -m pytest test_deliverable_run.py -q
"""
import os
import sys
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from executor.executor import _python_run_check  # noqa: E402


_LONG_IMPORT = "import os\nimport sys\n\n"  # 120+ belgi uchun


class TestPythonRunCheck(unittest.TestCase):

    def test_working_code_runs(self):
        code = _LONG_IMPORT + "\n".join(
            f"def fn_{i}(x):\n    return x * {i} + 1\n" for i in range(8))
        ok, note = _python_run_check(code)
        self.assertIs(ok, True, note)
        self.assertEqual(note, "run ok")

    def test_name_error_fails(self):
        code = _LONG_IMPORT + "\n".join(
            f"def fn_{i}(a, b):\n    return a + b * {i}\n" for i in range(8))
        code += "\n\nresult = undefined_variable_xyz + 1\n"
        ok, note = _python_run_check(code)
        self.assertIs(ok, False)
        self.assertIn("NameError", note)

    def test_type_error_fails(self):
        code = _LONG_IMPORT + "\n".join(
            f"def gn_{i}(a):\n    return a + {i}\n" for i in range(8))
        code += "\n\nout = 5 + '5'\n"
        ok, note = _python_run_check(code)
        self.assertIs(ok, False)
        self.assertIn("TypeError", note)

    def test_zero_division_fails(self):
        code = _LONG_IMPORT + "\n".join(
            f"def hd_{i}(a):\n    return a * {i + 1}\n" for i in range(8))
        code += "\n\nbad = 10 / 0\n"
        ok, note = _python_run_check(code)
        self.assertIs(ok, False)

    def test_import_error_is_neutral(self):
        code = _LONG_IMPORT + "x = 1\n" * 20
        code += "import definitely_not_installed_pkg_12345\n"
        ok, note = _python_run_check(code)
        self.assertIsNone(ok)
        self.assertEqual(note, "import/deps")

    def test_deny_list_is_neutral(self):
        # sandbox deny-listga tushadigan kod — ishga tushirilmaydi, neytral
        code = _LONG_IMPORT + "\n".join(
            f"def dn_{i}(a):\n    return a - {i}\n" for i in range(8))
        code += "\n\nimport subprocess\nsubprocess.run(['echo', 'hi'])\n"
        ok, note = _python_run_check(code)
        self.assertIsNone(ok)
        self.assertIn("deny-list", note)

    def test_timeout_is_neutral(self):
        code = _LONG_IMPORT + "\n".join(
            f"def tn_{i}(a):\n    return a + {i}\n" for i in range(8))
        code += "\n\nwhile True:\n    pass\n"
        ok, note = _python_run_check(code)
        self.assertIsNone(ok)
        self.assertEqual(note, "timeout")

    def test_too_short_is_neutral(self):
        ok, note = _python_run_check("print('hi')")
        self.assertIsNone(ok)
        self.assertEqual(note, "too short")

    def test_broken_syntax_is_neutral_here(self):
        # sintaksis buzuk — sintaksis gate rad etadi; bu yerda neytral
        ok, note = _python_run_check("def broken(:\n    pass\n" + "# padding\n" * 20)
        self.assertIsNone(ok)
        self.assertEqual(note, "syntax")

    def test_print_output_does_not_fail(self):
        code = _LONG_IMPORT + "\n".join(
            f"def pn_{i}(a):\n    return a + {i}\n" for i in range(8))
        code += "\n\nprint('salom dunyo')\n"
        ok, _ = _python_run_check(code)
        self.assertIs(ok, True)


class TestVerifyDeliverableRunGate(unittest.TestCase):
    """Butun gate yo'li: ishga tushmaydigan .py gate'dan O'TMASLIGI kerak."""

    def _exec(self, tmp):
        from executor.executor import AgentExecutor
        return AgentExecutor(workspace_root=tmp, llm=None)

    def _write_and_verify(self, tmp, fname, code):
        ex = self._exec(tmp)
        ex.workspace.write(fname, code)
        return ex._verify_deliverable(f"{fname} faylini yoz", [
            {"tool": "write_file", "args": {"path": fname, "content": code}},
        ])

    def test_runtime_error_rejected_by_gate(self):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="igris_run_")
        code = (_LONG_IMPORT + "\n".join(
            f"def fn_{i}(a, b):\n    return a + b * {i}\n" for i in range(8)))
        code += "\n\nresult = missing_name_abc + 1\n"
        ok, note = self._write_and_verify(tmp, "runner.py", code)
        self.assertFalse(ok, "ishga tushmaydigan fayl gate'dan o'tdi!")
        self.assertIn("ishga tushmaydi", note)

    def test_working_file_accepted_by_gate(self):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="igris_run_")
        code = (_LONG_IMPORT + "\n".join(
            f"def wf_{i}(a, b):\n    return a + b * {i}\n" for i in range(10)))
        ok, note = self._write_and_verify(tmp, "worker.py", code)
        self.assertTrue(ok, f"to'g'ri fayl rad etildi: {note}")

    def test_deps_missing_still_accepted(self):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="igris_run_")
        code = (_LONG_IMPORT + "\n".join(
            f"def dp_{i}(a):\n    return a * {i}\n" for i in range(10)))
        code += "import no_such_module_qq\n"
        ok, note = self._write_and_verify(tmp, "deps.py", code)
        self.assertTrue(ok, f"deps-neutral fayl rad etildi: {note}")


if __name__ == "__main__":
    unittest.main()
