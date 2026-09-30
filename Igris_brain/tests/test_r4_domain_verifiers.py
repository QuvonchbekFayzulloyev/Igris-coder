"""
Roadmap v3 R4 — DOMAIN VERIFIERS testlari (§13 + §14 + §15 + §16)
==================================================================
Qamrov:
  - verify_code_output: expected, pattern, crash, deny-list neutral, wrong output
  - verify_source_evidence: hash evidence, summary link, missing, empty
  - verify_document: md sections/required, csv, json, html, docx, unknown ext
  - verify_file_manifest: ok, missing, empty, non-UTF8, unexpected leak
  - run_domain_verifiers: task-based routing + fail-safe
  - Executor integratsiya: yozuv → vlog'da domain:... record + status pasayishi

Run: python test_r4_domain_verifiers.py | pytest test_r4_domain_verifiers.py
"""
from __future__ import annotations

import os
import sys
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from verification.domain_verifiers import (  # noqa: E402
    verify_code_output, verify_source_evidence, verify_document,
    verify_file_manifest, run_domain_verifiers,
)
from workspace_harness import WorkspaceHarness  # noqa: E402


class TestCodeOutput(unittest.TestCase):
    """§14 — expected output comparison."""

    def test_correct_output_passes(self):
        ok, note = verify_code_output("print(2 + 3)", expected="5")
        self.assertTrue(ok, note)

    def test_wrong_output_fails_with_evidence(self):
        ok, note = verify_code_output("print(2 + 2)", expected="5")
        self.assertFalse(ok)
        self.assertIn("not in stdout", note)

    def test_pattern_search(self):
        ok, _ = verify_code_output("print('total: 42')",
                                   pattern=r"total:\s*\d+")
        self.assertTrue(ok)

    def test_pattern_miss_fails(self):
        ok, note = verify_code_output("print('nothing here')",
                                      pattern=r"total:\s*\d+")
        self.assertFalse(ok)
        self.assertIn("pattern", note)

    def test_crashing_script_fails(self):
        ok, note = verify_code_output("raise ZeroDivisionError('boom')",
                                      expected="5")
        self.assertFalse(ok)
        self.assertIn("crashed", note)

    def test_deny_list_is_neutral(self):
        ok, note = verify_code_output(
            'import os\nos.system("echo hi")', expected="hi")
        self.assertIsNone(ok)
        self.assertIn("neutral", note)

    def test_no_expectation_is_neutral(self):
        ok, _ = verify_code_output("print('x')")
        self.assertIsNone(ok)


class TestSourceEvidence(unittest.TestCase):
    """§15 — source path + content hash."""

    def test_evidence_collected_with_hash(self):
        with WorkspaceHarness() as h:
            h.seed({"source.md": "IGRIS uses checkpoint + reconciliation."})
            ok, note = verify_source_evidence(h.root, "source.md")
            self.assertTrue(ok, note)
            self.assertIn("sha256", note)

    def test_summary_must_reference_source(self):
        with WorkspaceHarness() as h:
            h.seed({"source.md": "data data data data data data data data"})
            h.seed({"summary.md": "xulosa manba source.md dan olindi — uzun matn " * 2})
            ok, note = verify_source_evidence(h.root, "source.md",
                                              summary_path="summary.md")
            self.assertTrue(ok, note)

    def test_summary_without_reference_fails(self):
        with WorkspaceHarness() as h:
            h.seed({"source.md": "data data data data data data data data"})
            h.seed({"summary.md": "hech qanday havola yo'q, uzun matn " * 3})
            ok, note = verify_source_evidence(h.root, "source.md",
                                              summary_path="summary.md")
            self.assertFalse(ok)
            self.assertIn("does not reference", note)

    def test_missing_source_fails(self):
        with WorkspaceHarness() as h:
            ok, note = verify_source_evidence(h.root, "ghost.md")
            self.assertFalse(ok)
            self.assertIn("missing", note)

    def test_empty_source_fails(self):
        with WorkspaceHarness() as h:
            h.seed({"empty.md": ""})
            ok, note = verify_source_evidence(h.root, "empty.md")
            self.assertFalse(ok)
            self.assertIn("empty", note)


class TestDocument(unittest.TestCase):
    """§16 — md/csv/json/html/docx structure."""

    def test_md_with_sections_passes(self):
        with WorkspaceHarness() as h:
            h.seed({"doc.md": "# Intro\n\ntext\n\n## Body\n\nmore\n\n## Extra\n"})
            ok, note = verify_document(h.root, "doc.md")
            self.assertTrue(ok, note)

    def test_md_missing_sections_fails(self):
        with WorkspaceHarness() as h:
            h.seed({"doc.md": "# Only one heading\n"})
            ok, note = verify_document(h.root, "doc.md", min_sections=2)
            self.assertFalse(ok)
            self.assertIn("section", note)

    def test_md_required_sections(self):
        with WorkspaceHarness() as h:
            h.seed({"doc.md": "# Intro\n\n## Usage\n\n## API\n"})
            ok, _ = verify_document(h.root, "doc.md",
                                    required_sections=["Usage", "API"])
            self.assertTrue(ok)
            ok2, note2 = verify_document(h.root, "doc.md",
                                         required_sections=["License"])
            self.assertFalse(ok2)
            self.assertIn("License", note2)

    def test_csv_structure(self):
        with WorkspaceHarness() as h:
            h.seed({"data.csv": "a,b\n1,2\n3,4\n"})
            ok, note = verify_document(h.root, "data.csv")
            self.assertTrue(ok, note)
            h.seed({"bad.csv": "a\n"})
            ok2, note2 = verify_document(h.root, "bad.csv")
            self.assertFalse(ok2)

    def test_json_and_html(self):
        with WorkspaceHarness() as h:
            h.seed({"good.json": '{"k": [1, 2]}', "bad.json": "{oops",
                    "page.html": "<html><body><p>x</p></body></html>"})
            self.assertTrue(verify_document(h.root, "good.json")[0])
            self.assertFalse(verify_document(h.root, "bad.json")[0])
            self.assertTrue(verify_document(h.root, "page.html")[0])

    def test_docx_container(self):
        import io
        import zipfile
        with WorkspaceHarness() as h:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("word/document.xml", "<doc/>")
            h.seed({"real.docx": buf.getvalue()})
            self.assertTrue(verify_document(h.root, "real.docx")[0])
            h.seed({"fake.docx": "not a zip"})
            self.assertFalse(verify_document(h.root, "fake.docx")[0])

    def test_unknown_extension_neutral(self):
        with WorkspaceHarness() as h:
            h.seed({"art.bin": b"\x00\x01"})
            ok, note = verify_document(h.root, "art.bin")
            self.assertIsNone(ok)


class TestFileManifest(unittest.TestCase):
    """§13 — exists/size/encoding/unexpected."""

    def test_manifest_ok_with_unexpected_report(self):
        with WorkspaceHarness() as h:
            h.seed({"a.txt": "x", "b.py": "print(1)", "_extra.bin": "y"})
            ok, note = verify_file_manifest(h.root, ["a.txt", "b.py"])
            self.assertTrue(ok, note)
            self.assertIn("1 unexpected", note)

    def test_missing_file_fails(self):
        with WorkspaceHarness() as h:
            h.seed({"a.txt": "x"})
            ok, note = verify_file_manifest(h.root, ["a.txt", "ghost.txt"])
            self.assertFalse(ok)
            self.assertIn("ghost.txt", note)

    def test_empty_file_fails(self):
        with WorkspaceHarness() as h:
            h.seed({"empty.txt": ""})
            ok, note = verify_file_manifest(h.root, ["empty.txt"])
            self.assertFalse(ok)
            self.assertIn("empty", note)

    def test_non_utf8_text_fails(self):
        with WorkspaceHarness() as h:
            h.seed({"broken.txt": b"\xff\xfe\xfa"})
            ok, note = verify_file_manifest(h.root, ["broken.txt"])
            self.assertFalse(ok)
            self.assertIn("non-UTF8", note)

    def test_unexpected_leak_fails(self):
        with WorkspaceHarness() as h:
            h.seed({"keep.txt": "x"})
            h.seed({f"leak_{i}.tmp": "y" for i in range(60)})
            ok, note = verify_file_manifest(h.root, ["keep.txt"],
                                            max_unexpected=50)
            self.assertFalse(ok)
            self.assertIn("unexpected", note)


class TestRouting(unittest.TestCase):
    """run_domain_verifiers — task matniga qarab routing + fail-safe."""

    def test_py_routes_to_code(self):
        with WorkspaceHarness() as h:
            h.seed({"calc.py": "print(2+3)\n"})
            res = run_domain_verifiers(h.root, "create calc.py", ["calc.py"])
            self.assertEqual(len(res), 1)
            self.assertEqual(res[0]["domain"], "code")
            self.assertTrue(res[0]["ok"], res[0]["note"])

    def test_md_routes_to_document(self):
        with WorkspaceHarness() as h:
            h.seed({"doc.md": "# A\n\n## B\n"})
            res = run_domain_verifiers(h.root, "create doc.md", ["doc.md"])
            self.assertEqual(res[0]["domain"], "document")
            self.assertTrue(res[0]["ok"])

    def test_broken_py_fails(self):
        with WorkspaceHarness() as h:
            h.seed({"bad.py": "def f(:\n"})
            res = run_domain_verifiers(h.root, "create bad.py", ["bad.py"])
            self.assertFalse(res[0]["ok"])

    def test_failsafe_never_raises(self):
        with WorkspaceHarness() as h:
            # mavjud bo'lmagan fayl — verifier None/False qaytaradi, yiqilmaydi
            res = run_domain_verifiers(h.root, "task", ["ghost.py", "ghost.md"])
            self.assertEqual(len(res), 2)
            self.assertIn(res[0]["ok"], (True, False, None))


class TestExecutorIntegration(unittest.TestCase):
    """Executor'ga ulash: buzuk .py → status partial + FAILED evidence."""

    PLAN = {"goal": "write script", "engine": "llm", "steps": [
        {"id": 1, "title": "write script", "tools": ["write_file"],
         "detail": "create `calc.py` that prints 5"}]}

    class _LLM:
        """Scripted LLM: har safar bitta write_file bilan skript yozadi."""

        def __init__(self, plan, content):
            self.plan = plan
            self.content = content

        def complete(self, prompt, system=None):
            import json as _json
            s = (system or "")
            p = (prompt or "")
            if "requirement extractor" in s:
                return _json.dumps({"intent": "code", "output_format": "code",
                                    "deliverable_name": "calc.py",
                                    "verbosity": "balanced", "confidence": 0.9})
            if "planner" in s and "tool-caller" not in s:
                return _json.dumps(self.plan)
            if "COMPLETE or INCOMPLETE" in p:
                return "COMPLETE"
            if "finishing step" in s:
                return _json.dumps({"path": "calc.py", "content": "final"})
            if "write_file" in p or '"path"' in p:
                return _json.dumps({"path": "calc.py", "content": self.content})
            return "bajarildi"

        def chat(self, messages, system=None):
            return "bajarildi"

    def _run(self, content: str) -> dict:
        from executor.executor import AgentExecutor
        with WorkspaceHarness() as h:
            ex = AgentExecutor(
                workspace_root=h.root, llm=self._LLM(self.PLAN, content),
                memory=None, mcp=None, human_provider=None,
                checkpoint_dir=h.checkpoint_dir, max_iter=8,
                max_tool_calls=10)
            res = ex.run("create calc.py that prints 5")
            res["_workspace"] = h
            return res

    def test_broken_script_downgrades_status(self):
        res = self._run("print(undefined_variable_xyz)\n")
        dom = [v for v in res.get("verifications", [])
               if v.get("method", "").startswith("domain:")]
        self.assertEqual(len(dom), 1)
        self.assertEqual(dom[0]["status"], "FAILED")
        self.assertIn("crashed", dom[0]["note"])
        self.assertEqual(res["status"], "partial",
                         "buzuk skript 'ok' bo'lmasligi kerak (§29)")

    def test_good_script_stays_ok_and_verified(self):
        res = self._run("print(2 + 3)\n")
        dom = [v for v in res.get("verifications", [])
               if v.get("method", "").startswith("domain:")]
        self.assertEqual(len(dom), 1)
        self.assertEqual(dom[0]["status"], "VERIFIED")
        self.assertEqual(res["status"], "ok")


if __name__ == "__main__":
    unittest.main()
