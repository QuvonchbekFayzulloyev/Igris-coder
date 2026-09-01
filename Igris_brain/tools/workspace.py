"""
IGRIS BRAIN — Workspace (xavfsiz fayl sandbox)
==============================================
Barcha fayl operatsiyalari shu klass orqali bajariladi.

Xavfsizlik:
  - `root` dan tashqariga chiqish bloklanadi (path traversal himoyasi)
  - `root` avtomatik yaratiladi
  - `resolve()` barcha `..` va mutlaq yo'llarni tekshiradi
"""

from __future__ import annotations

import os


class Workspace:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    # ------------------------------------------------------------ #
    # Path safety
    # ------------------------------------------------------------ #

    def resolve(self, rel_path: str) -> str:
        """rel_path -> xavfsiz absolyut yo'l. Traversal bo'lsa ValueError."""
        rel_path = str(rel_path or "").strip()
        # MCP modellar `/workspace/apple.png` kabi yozishi mumkin — bu
        # workspace rootiga nisbatan. Leading slash va `/workspace/` prefiksini
        # tozalaymiz (workspace root ichida qolishi uchun).
        if rel_path.startswith(("/", "\\")):
            rel_path = rel_path.lstrip("/\\")
            for prefix in ("workspace/", "ws/", "workdir/"):
                if rel_path.lower().startswith(prefix):
                    rel_path = rel_path[len(prefix):]
                    break
        candidate = os.path.abspath(os.path.join(self.root, rel_path))
        if not self._is_inside(candidate):
            raise ValueError(f"Path escapes workspace root: {rel_path}")
        return candidate

    def _is_inside(self, candidate: str) -> bool:
        """Symlink hujumiga qarshi: REAL (yechilgan) yo'llar solishtiriladi.

        `os.path.abspath` symlink'ni yechmaydi — workspace ichidagi symlink
        tashqariga ishora qilsa, normpath asosidagi tekshiruv uni "ichkarida"
        deb o'tkazardi. `realpath` barcha symlink'ni oxirigacha yechadi, shu
        sabab root'dan tashqariga ishora qiluvchi yo'l aniqlanadi va bloklanadi.
        """
        root = os.path.realpath(self.root)
        cand = os.path.realpath(candidate)
        return cand == root or cand.startswith(root + os.sep)

    # ------------------------------------------------------------ #
    # Files
    # ------------------------------------------------------------ #

    def read(self, rel_path: str) -> dict:
        path = self.resolve(rel_path)
        if not os.path.isfile(path):
            return {"ok": False, "error": f"File not found: {rel_path}"}
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return {"ok": True, "path": rel_path, "content": f.read()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def write(self, rel_path: str, content: str) -> dict:
        path = self.resolve(rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"ok": True, "path": rel_path, "bytes": len(content.encode("utf-8"))}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def list(self, rel_path: str = "", depth: int = 2) -> dict:
        base = self.resolve(rel_path)
        if not os.path.isdir(base):
            return {"ok": False, "error": f"Not a directory: {rel_path or '.'}"}
        tree: list[dict] = []

        def walk(d: str, level: int) -> None:
            if level > depth:
                return
            try:
                entries = sorted(os.listdir(d))
            except OSError:
                return
            for name in entries:
                full = os.path.join(d, name)
                if name.startswith((".git", "node_modules", "__pycache__", ".venv")):
                    continue
                rel = os.path.relpath(full, self.root)
                is_dir = os.path.isdir(full)
                node = {"path": rel.replace(os.sep, "/"), "type": "dir" if is_dir else "file"}
                tree.append(node)
                if is_dir:
                    walk(full, level + 1)

        walk(base, 0)
        return {"ok": True, "root": self.root, "entries": tree}

    def exists(self, rel_path: str) -> bool:
        try:
            return os.path.exists(self.resolve(rel_path))
        except ValueError:
            return False

    def info(self) -> dict:
        return {
            "root": self.root,
            "exists": os.path.isdir(self.root),
        }
