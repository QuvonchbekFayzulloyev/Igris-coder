"""LSP Manager — bir nechta language serverni boshqarish.

Til aniqlash, server start/stop, fallback chain.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from lsp.client import (
    LSPClient, LSPCompletion, LSPDefinition, LSPDiagnostic,
    LSPHover, LSPReference,
)


@dataclass
class LSPServerConfig:
    """Language server konfiguratsiyasi."""
    language: str
    command: list[str]
    file_patterns: list[str]  # e.g., ["*.py", "*.pyi"]
    priority: int = 0  # qancha past bo'lsa, shuncha afzal


# Default server konfiguratsiyalari
DEFAULT_SERVERS: list[LSPServerConfig] = [
    LSPServerConfig(
        language="python",
        command=["pylsp"],
        file_patterns=["*.py", "*.pyi"],
        priority=0,
    ),
    LSPServerConfig(
        language="typescript",
        command=["typescript-language-server", "--stdio"],
        file_patterns=["*.ts", "*.tsx", "*.js", "*.jsx"],
        priority=0,
    ),
    LSPServerConfig(
        language="rust",
        command=["rust-analyzer"],
        file_patterns=["*.rs"],
        priority=0,
    ),
    LSPServerConfig(
        language="go",
        command=["gopls"],
        file_patterns=["*.go"],
        priority=0,
    ),
    LSPServerConfig(
        language="java",
        command=["jdtls"],
        file_patterns=["*.java"],
        priority=0,
    ),
    LSPServerConfig(
        language="csharp",
        command=["omnisharp", "--languageserver", "--hostPID", "0"],
        file_patterns=["*.cs"],
        priority=0,
    ),
    LSPServerConfig(
        language="cpp",
        command=["clangd"],
        file_patterns=["*.cpp", "*.c", "*.h", "*.hpp"],
        priority=0,
    ),
    LSPServerConfig(
        language="ruby",
        command=["solargraph", "stdio"],
        file_patterns=["*.rb"],
        priority=0,
    ),
    LSPServerConfig(
        language="php",
        command=["phpactor", "language-server"],
        file_patterns=["*.php"],
        priority=0,
    ),
    LSPServerConfig(
        language="swift",
        command=["sourcekit-lsp"],
        file_patterns=["*.swift"],
        priority=0,
    ),
]


class LSPManager:
    """Language serverlarni boshqarish."""

    def __init__(self, workspace_root: str = ""):
        self.workspace_root = workspace_root or os.getcwd()
        self._servers: dict[str, LSPClient] = {}
        self._configs: dict[str, LSPServerConfig] = {}
        self._file_map: dict[str, str] = {}  # ext -> language
        self._init_configs()

    def _init_configs(self) -> None:
        """Default konfiguratsiyalarni yuklash."""
        for config in DEFAULT_SERVERS:
            self._configs[config.language] = config
            for pattern in config.file_patterns:
                ext = pattern.replace("*", "")
                self._file_map[ext] = config.language

    def get_language_for_file(self, file_path: str) -> str:
        """Fayl uchun tilni aniqlash."""
        _, ext = os.path.splitext(file_path)
        return self._file_map.get(ext, "")

    def get_client(self, language: str) -> Optional[LSPClient]:
        """Til uchun LSP client olish."""
        if language in self._servers:
            client = self._servers[language]
            if client.is_running():
                return client
        return None

    def start_server(self, language: str) -> Optional[LSPClient]:
        """Language server'ni ishga tushirish."""
        if language in self._servers:
            existing = self._servers[language]
            if existing.is_running():
                return existing

        config = self._configs.get(language)
        if config is None:
            return None

        client = LSPClient(
            language=language,
            server_command=config.command,
            workspace_root=self.workspace_root,
        )
        if client.start():
            self._servers[language] = client
            return client
        return None

    def stop_server(self, language: str) -> None:
        """Language server'ni to'xtatish."""
        if language in self._servers:
            self._servers[language].stop()
            del self._servers[language]

    def stop_all(self) -> None:
        """Barcha serverlarni to'xtatish."""
        for language in list(self._servers.keys()):
            self.stop_server(language)

    def auto_start(self, file_path: str) -> Optional[LSPClient]:
        """Fayl uchun avtomatik server start qilish."""
        language = self.get_language_for_file(file_path)
        if not language:
            return None
        client = self.get_client(language)
        if client:
            return client
        return self.start_server(language)

    # --- High-level API ---

    def goto_definition(self, file_path: str, line: int, column: int) -> list[LSPDefinition]:
        """Definition ga o'tish."""
        client = self.auto_start(file_path)
        if client:
            return client.goto_definition(file_path, line, column)
        return []

    def find_references(self, file_path: str, line: int, column: int) -> list[LSPReference]:
        """Referencelarni topish."""
        client = self.auto_start(file_path)
        if client:
            return client.find_references(file_path, line, column)
        return []

    def hover(self, file_path: str, line: int, column: int) -> Optional[LSPHover]:
        """Hover ma'lumotini olish."""
        client = self.auto_start(file_path)
        if client:
            return client.hover(file_path, line, column)
        return None

    def completion(self, file_path: str, line: int, column: int) -> list[LSPCompletion]:
        """Completion takliflarini olish."""
        client = self.auto_start(file_path)
        if client:
            return client.completion(file_path, line, column)
        return []

    def diagnostics(self, file_path: str) -> list[LSPDiagnostic]:
        """Fayl diagnostikasini olish."""
        client = self.auto_start(file_path)
        if client:
            return client.document_diagnostics(file_path)
        return []

    def did_open(self, file_path: str, content: str) -> None:
        """Fayl ochilganini bildirish."""
        client = self.auto_start(file_path)
        if client:
            language = self.get_language_for_file(file_path)
            client.did_open(file_path, content, language)

    def did_change(self, file_path: str, content: str) -> None:
        """Fayl o'zgarganini bildirish."""
        client = self.auto_start(file_path)
        if client:
            client.did_change(file_path, content)

    def did_save(self, file_path: str) -> None:
        """Fayl saqlanganini bildirish."""
        client = self.auto_start(file_path)
        if client:
            client.did_save(file_path)

    def get_all_diagnostics(self) -> dict[str, list[dict]]:
        """Barcha fayllar diagnostikasini olish."""
        all_diag = {}
        for language, client in self._servers.items():
            if client.is_running():
                diags = client.get_diagnostics()
                for d in diags:
                    if d.file:
                        if d.file not in all_diag:
                            all_diag[d.file] = []
                        all_diag[d.file].append(d.to_dict())
        return all_diag

    def get_status(self) -> dict:
        """Serverlar holatini olish."""
        status = {}
        for language, client in self._servers.items():
            status[language] = {
                "running": client.is_running(),
                "initialized": client._initialized,
            }
        return status

    def get_available_languages(self) -> list[str]:
        """Mavjud tillarni olish."""
        return list(self._configs.keys())
