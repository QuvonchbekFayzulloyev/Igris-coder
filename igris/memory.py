"""
igris.memory
------------
Two persistence layers, matching the "Memory MCP" concept from the
architecture plan, implemented here directly rather than as a separate
process since it's pure local state:

- session log (.igris/memory/session.jsonl): append-only turn history,
  used to reconstruct short-term conversational context.
- checkpoints (.igris/memory/checkpoints.json): small key/value store for
  durable facts learned across sessions (preferences, project conventions,
  recurring corrections) -- the "learned pattern" layer.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class Memory:
    def __init__(self, config):
        self.dir = config.path_for("memory.dir")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.session_path = self.dir / config.get("memory.session_log", "session.jsonl")
        self.checkpoints_path = self.dir / config.get("memory.checkpoints_file", "checkpoints.json")

    # ---- session log ----------------------------------------------------

    def log_turn(self, role: str, content: str, meta: dict | None = None) -> None:
        entry = {"ts": time.time(), "role": role, "content": content, "meta": meta or {}}
        with open(self.session_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def recent_turns(self, limit: int = 12) -> list[dict]:
        if not self.session_path.exists():
            return []
        lines = self.session_path.read_text(encoding="utf-8").strip().splitlines()
        out = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    # ---- checkpoints (learned patterns / preferences) --------------------

    def _load_checkpoints(self) -> dict:
        if not self.checkpoints_path.exists():
            return {}
        try:
            return json.loads(self.checkpoints_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def get_checkpoint(self, key: str, default: Any = None) -> Any:
        return self._load_checkpoints().get(key, default)

    def set_checkpoint(self, key: str, value: Any) -> None:
        data = self._load_checkpoints()
        data[key] = value
        self.checkpoints_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def all_checkpoints(self) -> dict:
        return self._load_checkpoints()
