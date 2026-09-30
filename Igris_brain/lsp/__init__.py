"""IGRIS LSP — Language Server Protocol integration.

Code intelligence: definitions, references, hover, diagnostics, completion.
"""
from lsp.client import LSPClient
from lsp.manager import LSPManager

__all__ = ["LSPClient", "LSPManager"]
