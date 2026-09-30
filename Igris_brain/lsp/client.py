"""LSP Client — Language Server Protocol communication.

Har bir til uchun alohida language server bilan muloqot.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LSPDiagnostic:
    """LSP xabar diagnostikasi."""
    file: str
    line: int
    column: int
    message: str
    severity: str  # "error", "warning", "info", "hint"
    source: str = ""
    code: str = ""

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "severity": self.severity,
            "source": self.source,
            "code": self.code,
        }


@dataclass
class LSPDefinition:
    """Definition natijasi."""
    file: str
    line: int
    column: int
    text: str = ""

    def to_dict(self) -> dict:
        return {"file": self.file, "line": self.line, "column": self.column, "text": self.text}


@dataclass
class LSPReference:
    """Reference natijasi."""
    file: str
    line: int
    column: int
    text: str = ""
    context: str = ""

    def to_dict(self) -> dict:
        return {
            "file": self.file, "line": self.line, "column": self.column,
            "text": self.text, "context": self.context,
        }


@dataclass
class LSPHover:
    """Hover natijasi."""
    content: str
    file: str = ""
    line: int = 0
    column: int = 0

    def to_dict(self) -> dict:
        return {"content": self.content, "file": self.file, "line": self.line, "column": self.column}


@dataclass
class LSPCompletion:
    """Completion natijasi."""
    label: str
    kind: str = ""
    detail: str = ""
    documentation: str = ""
    insert_text: str = ""

    def to_dict(self) -> dict:
        return {
            "label": self.label, "kind": self.kind,
            "detail": self.detail, "documentation": self.documentation,
            "insert_text": self.insert_text,
        }


class LSPClient:
    """Bir til uchun LSP client."""

    def __init__(self, language: str, server_command: list[str], workspace_root: str = ""):
        self.language = language
        self.server_command = server_command
        self.workspace_root = workspace_root or os.getcwd()
        self._process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._responses: dict[int, dict] = {}
        self._initialized = False
        self._diagnostics: list[LSPDiagnostic] = []

    def start(self) -> bool:
        """Language server'ni ishga tushirish."""
        try:
            self._process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.workspace_root,
            )
            # Initialize
            self._send_request("initialize", {
                "processId": os.getpid(),
                "rootUri": f"file:///{self.workspace_root.replace(os.sep, '/')}",
                "capabilities": {
                    "textDocument": {
                        "completion": {"completionItem": {"snippetSupport": True}},
                        "hover": {"contentFormat": ["plaintext", "markdown"]},
                        "definition": {"dynamicRegistration": False},
                        "references": {"dynamicRegistration": False},
                        "publishDiagnostics": {"relatedInformation": True},
                    },
                },
            })
            self._send_notification("initialized", {})
            self._initialized = True
            return True
        except Exception:
            return False

    def stop(self) -> None:
        """Server'ni to'xtatish."""
        if self._process:
            try:
                self._send_request("shutdown", {})
                self._send_notification("exit", {})
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                if self._process:
                    self._process.kill()
            self._process = None
            self._initialized = False

    def is_running(self) -> bool:
        """Server ishlayaptimi?"""
        return self._process is not None and self._process.poll() is None

    def goto_definition(self, file_path: str, line: int, column: int) -> list[LSPDefinition]:
        """Definition ga o'tish."""
        if not self._initialized:
            return []
        uri = self._path_to_uri(file_path)
        result = self._send_request("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": column},
        })
        return self._parse_locations(result)

    def find_references(self, file_path: str, line: int, column: int) -> list[LSPReference]:
        """Referencelarni topish."""
        if not self._initialized:
            return []
        uri = self._path_to_uri(file_path)
        result = self._send_request("textDocument/references", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": column},
            "context": {"includeDeclaration": True},
        })
        return self._parse_references(result)

    def hover(self, file_path: str, line: int, column: int) -> Optional[LSPHover]:
        """Hover ma'lumotini olish."""
        if not self._initialized:
            return None
        uri = self._path_to_uri(file_path)
        result = self._send_request("textDocument/hover", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": column},
        })
        if result and "contents" in result:
            contents = result["contents"]
            if isinstance(contents, dict):
                text = contents.get("value", "")
            elif isinstance(contents, list):
                text = "\n".join(c.get("value", str(c)) if isinstance(c, dict) else str(c) for c in contents)
            else:
                text = str(contents)
            return LSPHover(content=text, file=file_path, line=line, column=column)
        return None

    def completion(self, file_path: str, line: int, column: int) -> list[LSPCompletion]:
        """Completion takliflarini olish."""
        if not self._initialized:
            return []
        uri = self._path_to_uri(file_path)
        result = self._send_request("textDocument/completion", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": column},
        })
        return self._parse_completions(result)

    def document_diagnostics(self, file_path: str) -> list[LSPDiagnostic]:
        """Fayl diagnostikasini olish."""
        if not self._initialized:
            return []
        uri = self._path_to_uri(file_path)
        result = self._send_request("textDocument/diagnostic", {
            "textDocument": {"uri": uri},
        })
        return self._parse_diagnostics(result)

    def did_open(self, file_path: str, content: str, language_id: str = "") -> None:
        """Fayl ochilganini bildirish."""
        if not self._initialized:
            return
        uri = self._path_to_uri(file_path)
        self._send_notification("textDocument/didOpen", {
            "textDocument": {
                "uri": uri,
                "languageId": language_id or self.language,
                "version": 1,
                "text": content,
            },
        })

    def did_change(self, file_path: str, content: str) -> None:
        """Fayl o'zgarganini bildirish."""
        if not self._initialized:
            return
        uri = self._path_to_uri(file_path)
        self._send_notification("textDocument/didChange", {
            "textDocument": {"uri": uri, "version": int(time.time())},
            "contentChanges": [{"text": content}],
        })

    def did_save(self, file_path: str) -> None:
        """Fayl saqlanganini bildirish."""
        if not self._initialized:
            return
        uri = self._path_to_uri(file_path)
        self._send_notification("textDocument/didSave", {
            "textDocument": {"uri": uri},
        })

    def get_diagnostics(self) -> list[LSPDiagnostic]:
        """Joriy diagnostikalarni olish."""
        return list(self._diagnostics)

    # --- Private ---

    def _send_request(self, method: str, params: dict) -> Optional[dict]:
        """JSON-RPC request yuborish."""
        if not self._process or not self._process.stdin or not self._process.stdout:
            return None
        self._request_id += 1
        req_id = self._request_id
        message = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        try:
            body = json.dumps(message)
            header = f"Content-Length: {len(body)}\r\n\r\n"
            self._process.stdin.write(header.encode() + body.encode())
            self._process.stdin.flush()
            # Response o'qish
            return self._read_response()
        except Exception:
            return None

    def _send_notification(self, method: str, params: dict) -> None:
        """JSON-RPC notification yuborish."""
        if not self._process or not self._process.stdin:
            return
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        try:
            body = json.dumps(message)
            header = f"Content-Length: {len(body)}\r\n\r\n"
            self._process.stdin.write(header.encode() + body.encode())
            self._process.stdin.flush()
        except Exception:
            pass

    def _read_response(self) -> Optional[dict]:
        """JSON-RPC response o'qish."""
        if not self._process or not self._process.stdout:
            return None
        try:
            # Header o'qish
            content_length = 0
            while True:
                line = self._process.stdout.readline().decode()
                if not line or line == "\r\n":
                    break
                if line.startswith("Content-Length:"):
                    content_length = int(line.split(":")[1].strip())
            if content_length == 0:
                return None
            # Body o'qish
            body = self._process.stdout.read(content_length).decode()
            return json.loads(body)
        except Exception:
            return None

    def _path_to_uri(self, path: str) -> str:
        """Fayl path'ni URI ga aylantirish."""
        if os.path.isabs(path):
            return f"file:///{path.replace(os.sep, '/')}"
        abs_path = os.path.join(self.workspace_root, path)
        return f"file:///{abs_path.replace(os.sep, '/')}"

    def _parse_locations(self, result: Any) -> list[LSPDefinition]:
        """Location natijasini parse qilish."""
        if not result:
            return []
        if isinstance(result, dict):
            result = [result]
        definitions = []
        for loc in result:
            uri = loc.get("uri", "")
            range_ = loc.get("range", {})
            start = range_.get("start", {})
            file_path = self._uri_to_path(uri)
            definitions.append(LSPDefinition(
                file=file_path,
                line=start.get("line", 0),
                column=start.get("character", 0),
            ))
        return definitions

    def _parse_references(self, result: Any) -> list[LSPReference]:
        """Reference natijasini parse qilish."""
        if not result:
            return []
        references = []
        for loc in result:
            uri = loc.get("uri", "")
            range_ = loc.get("range", {})
            start = range_.get("start", {})
            file_path = self._uri_to_path(uri)
            references.append(LSPReference(
                file=file_path,
                line=start.get("line", 0),
                column=start.get("character", 0),
            ))
        return references

    def _parse_completions(self, result: Any) -> list[LSPCompletion]:
        """Completion natijasini parse qilish."""
        if not result:
            return []
        items = result if isinstance(result, list) else result.get("items", [])
        completions = []
        for item in items:
            completions.append(LSPCompletion(
                label=item.get("label", ""),
                kind=str(item.get("kind", "")),
                detail=item.get("detail", ""),
                documentation=str(item.get("documentation", "")),
                insert_text=item.get("insertText", ""),
            ))
        return completions

    def _parse_diagnostics(self, result: Any) -> list[LSPDiagnostic]:
        """Diagnostics natijasini parse qilish."""
        if not result:
            return []
        diagnostics = []
        for diag in result:
            range_ = diag.get("range", {})
            start = range_.get("start", {})
            severity_map = {1: "error", 2: "warning", 3: "info", 4: "hint"}
            diagnostics.append(LSPDiagnostic(
                file="",
                line=start.get("line", 0),
                column=start.get("character", 0),
                message=diag.get("message", ""),
                severity=severity_map.get(diag.get("severity", 3), "info"),
                source=diag.get("source", ""),
                code=str(diag.get("code", "")),
            ))
        self._diagnostics = diagnostics
        return diagnostics

    def _uri_to_path(self, uri: str) -> str:
        """URI'ni fayl path'ga aylantirish."""
        path = uri.replace("file:///", "").replace("file://", "")
        return path.replace("/", os.sep)
