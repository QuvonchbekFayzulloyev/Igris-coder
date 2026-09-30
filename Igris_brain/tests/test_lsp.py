"""LSP Module — unit tests."""
from __future__ import annotations

import sys
import os

# Add parent directory for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


class TestLSPManager:
    """LSP Manager testlari."""

    def test_manager_creation(self):
        from lsp.manager import LSPManager
        manager = LSPManager()
        assert manager is not None

    def test_get_language_for_file(self):
        from lsp.manager import LSPManager
        manager = LSPManager()
        assert manager.get_language_for_file("test.py") == "python"
        assert manager.get_language_for_file("test.ts") == "typescript"
        assert manager.get_language_for_file("test.rs") == "rust"
        assert manager.get_language_for_file("test.go") == "go"
        assert manager.get_language_for_file("test.java") == "java"
        assert manager.get_language_for_file("test.unknown") == ""

    def test_get_available_languages(self):
        from lsp.manager import LSPManager
        manager = LSPManager()
        languages = manager.get_available_languages()
        assert "python" in languages
        assert "typescript" in languages
        assert "rust" in languages

    def test_get_status(self):
        from lsp.manager import LSPManager
        manager = LSPManager()
        status = manager.get_status()
        assert isinstance(status, dict)

    def test_auto_start_unknown(self):
        from lsp.manager import LSPManager
        manager = LSPManager()
        # Unknown file type should return None
        result = manager.auto_start("test.unknown")
        assert result is None


class TestLSPClient:
    """LSP Client testlari."""

    def test_client_creation(self):
        from lsp.client import LSPClient
        client = LSPClient("python", ["pylsp"], "/tmp")
        assert client.language == "python"
        assert not client.is_running()

    def test_definition_creation(self):
        from lsp.client import LSPDefinition
        defn = LSPDefinition(file="test.py", line=10, column=5)
        d = defn.to_dict()
        assert d["file"] == "test.py"
        assert d["line"] == 10

    def test_reference_creation(self):
        from lsp.client import LSPReference
        ref = LSPReference(file="test.py", line=10, column=5, text="foo")
        d = ref.to_dict()
        assert d["file"] == "test.py"
        assert d["text"] == "foo"

    def test_hover_creation(self):
        from lsp.client import LSPHover
        hover = LSPHover(content="int", file="test.py", line=10, column=5)
        d = hover.to_dict()
        assert d["content"] == "int"

    def test_completion_creation(self):
        from lsp.client import LSPCompletion
        comp = LSPCompletion(label="append", kind="Method", detail="list.append()")
        d = comp.to_dict()
        assert d["label"] == "append"
        assert d["kind"] == "Method"

    def test_diagnostic_creation(self):
        from lsp.client import LSPDiagnostic
        diag = LSPDiagnostic(file="test.py", line=10, column=5,
                            message="undefined variable", severity="error")
        d = diag.to_dict()
        assert d["message"] == "undefined variable"
        assert d["severity"] == "error"


class TestLSPTools:
    """LSP Tools testlari."""

    def test_lsp_status_tool(self):
        from tools.lsp_tools import LSP_STATUS
        assert LSP_STATUS.name == "lsp_status"

    def test_lsp_definition_tool(self):
        from tools.lsp_tools import LSP_DEFINITION
        assert LSP_DEFINITION.name == "lsp_definition"

    def test_lsp_references_tool(self):
        from tools.lsp_tools import LSP_REFERENCES
        assert LSP_REFERENCES.name == "lsp_references"

    def test_lsp_hover_tool(self):
        from tools.lsp_tools import LSP_HOVER
        assert LSP_HOVER.name == "lsp_hover"

    def test_lsp_completion_tool(self):
        from tools.lsp_tools import LSP_COMPLETION
        assert LSP_COMPLETION.name == "lsp_completion"

    def test_lsp_diagnostics_tool(self):
        from tools.lsp_tools import LSP_DIAGNOSTICS
        assert LSP_DIAGNOSTICS.name == "lsp_diagnostics"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
