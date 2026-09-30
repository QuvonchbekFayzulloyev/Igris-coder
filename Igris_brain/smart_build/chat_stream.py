"""Chat Stream Aggregator — micro-actions → semantic actions.

Core principle: Chat stream — agentning ichki faoliyatining logi emas;
agent faoliyatining foydalanuvchi uchun semantic representation'i.

4 Detail Levels:
  L0 — Chat summary (doim ko'rinadi)
  L1 — Action detail (default collapsed)
  L2 — Execution trace (user expand qilganda)
  L3 — Raw evidence (eng chuqur)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class StreamGroup(str, Enum):
    """7 ta asosiy stream group."""
    UNDERSTAND = "understand"
    INVESTIGATE = "investigate"
    PLAN = "plan"
    EXECUTE = "execute"
    TEST = "test"
    VERIFY = "verify"
    RECOVER = "recover"


class StreamStatus(str, Enum):
    """Stream holati."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DetailLevel(str, Enum):
    """Detail darajalari."""
    L0_SUMMARY = "L0"       # Chat summary — doim ko'rinadi
    L1_ACTION = "L1"        # Action detail — default collapsed
    L2_TRACE = "L2"         # Execution trace — user expand
    L3_EVIDENCE = "L3"      # Raw evidence — eng chuqur


@dataclass
class MicroAction:
    """Bitta mikro-amal."""
    action_type: str
    description: str
    target: str = ""
    result: str = ""
    duration_ms: float = 0.0
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "type": self.action_type,
            "description": self.description,
            "target": self.target,
            "result": self.result,
            "duration_ms": round(self.duration_ms, 1),
        }


@dataclass
class SemanticAction:
    """Birlashtirilgan semantic action."""
    action_id: str
    group: StreamGroup
    label: str
    status: StreamStatus = StreamStatus.PENDING
    detail_level: DetailLevel = DetailLevel.L0_SUMMARY
    # L0 — Summary
    summary: str = ""
    progress: str = ""
    # L1 — Action detail
    files_changed: list[dict] = field(default_factory=list)
    reason: str = ""
    # L2 — Execution trace
    micro_actions: list[MicroAction] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    # L3 — Raw evidence
    raw_output: str = ""
    commands: list[dict] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    # Timing
    started_at: float = 0.0
    completed_at: float = 0.0
    duration_seconds: float = 0.0
    # Verification
    verification_result: str = ""
    evidence: list[dict] = field(default_factory=list)

    def start(self):
        """Action boshlandi."""
        self.status = StreamStatus.RUNNING
        self.started_at = time.time()

    def complete(self, success: bool = True):
        """Action tugadi."""
        self.status = StreamStatus.COMPLETED if success else StreamStatus.FAILED
        self.completed_at = time.time()
        if self.started_at:
            self.duration_seconds = self.completed_at - self.started_at

    def add_micro(self, action: MicroAction):
        """Mikro-action qo'shish."""
        self.micro_actions.append(action)

    def to_compact(self) -> dict:
        """L0 — Chat summary formatida."""
        icon = self._status_icon()
        duration = f" · {self.duration_seconds:.1f}s" if self.duration_seconds else ""
        progress = f" · {self.progress}" if self.progress else ""
        return {
            "type": "action",
            "group": self.group.value,
            "label": f"{icon} {self.label}{progress}{duration}",
            "status": self.status.value,
            "duration": self.duration_seconds,
            "detail_level": "L0",
        }

    def to_expanded(self) -> dict:
        """L1 — Action detail formatida."""
        result = {
            "type": "action_detail",
            "group": self.group.value,
            "label": self.label,
            "status": self.status.value,
            "summary": self.summary,
            "duration": self.duration_seconds,
            "detail_level": "L1",
        }
        if self.files_changed:
            result["files"] = self.files_changed
        if self.reason:
            result["reason"] = self.reason
        if self.symbols:
            result["symbols"] = self.symbols
        return result

    def to_trace(self) -> dict:
        """L2 — Execution trace formatida."""
        result = self.to_expanded()
        result["detail_level"] = "L2"
        result["micro_actions"] = [m.to_dict() for m in self.micro_actions]
        result["dependencies"] = self.dependencies
        return result

    def to_evidence(self) -> dict:
        """L3 — Raw evidence formatida."""
        result = self.to_trace()
        result["detail_level"] = "L3"
        result["raw_output"] = self.raw_output
        result["commands"] = self.commands
        result["screenshots"] = self.screenshots
        result["evidence"] = self.evidence
        return result

    def _status_icon(self) -> str:
        """Status belgisi."""
        icons = {
            StreamStatus.PENDING: "○",
            StreamStatus.RUNNING: "◉",
            StreamStatus.COMPLETED: "✓",
            StreamStatus.FAILED: "✗",
            StreamStatus.SKIPPED: "–",
        }
        return icons.get(self.status, "○")


@dataclass
class ChatStream:
    """To'liq chat stream — bitta task uchun."""
    task: str
    actions: list[SemanticAction] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    total_duration: float = 0.0
    final_status: str = "running"
    final_result: str = ""

    def add_action(self, group: StreamGroup, label: str) -> SemanticAction:
        """Yangi action qo'shish."""
        action = SemanticAction(
            action_id=f"action_{len(self.actions)}",
            group=group,
            label=label,
        )
        self.actions.append(action)
        return action

    def get_current(self) -> Optional[SemanticAction]:
        """Joriy active action."""
        for a in reversed(self.actions):
            if a.status == StreamStatus.RUNNING:
                return a
        return None

    def complete(self, success: bool = True):
        """Stream tugadi."""
        self.completed_at = time.time()
        self.total_duration = self.completed_at - self.started_at
        self.final_status = "completed" if success else "failed"

    def to_compact_stream(self) -> list[dict]:
        """L0 — Barcha actionlarni compact formatda."""
        return [a.to_compact() for a in self.actions]

    def to_summary(self) -> dict:
        """Stream xulosasi."""
        completed = sum(1 for a in self.actions if a.status == StreamStatus.COMPLETED)
        failed = sum(1 for a in self.actions if a.status == StreamStatus.FAILED)
        return {
            "task": self.task,
            "status": self.final_status,
            "total_actions": len(self.actions),
            "completed": completed,
            "failed": failed,
            "duration": round(self.total_duration, 1),
            "actions": self.to_compact_stream(),
        }


class ChatStreamAggregator:
    """Micro-actions → semantic actions aggregation.

    6 micro-action → 1 semantic action:
      search("token") →
      read(auth/token.py) →
      read(auth/session.py) →
      find("refresh_token") →
      find("save_session") →
      ═══════════════════════════
      ◉ Investigating authentication · 6 files
    """

    # Micro-action → Semantic group mapping
    ACTION_GROUPS = {
        # Investigate
        "search": StreamGroup.INVESTIGATE,
        "search_code": StreamGroup.INVESTIGATE,
        "grep": StreamGroup.INVESTIGATE,
        "glob": StreamGroup.INVESTIGATE,
        "read_file": StreamGroup.INVESTIGATE,
        "list_files": StreamGroup.INVESTIGATE,
        "lsp_definition": StreamGroup.INVESTIGATE,
        "lsp_references": StreamGroup.INVESTIGATE,
        "lsp_hover": StreamGroup.INVESTIGATE,
        "lsp_completion": StreamGroup.INVESTIGATE,
        "lsp_diagnostics": StreamGroup.INVESTIGATE,
        "vision_observe": StreamGroup.INVESTIGATE,
        "vision_find": StreamGroup.INVESTIGATE,
        # Plan
        "smart_build_analyze": StreamGroup.PLAN,
        "todowrite": StreamGroup.PLAN,
        # Execute
        "write_file": StreamGroup.EXECUTE,
        "apply_patch": StreamGroup.EXECUTE,
        "edit_file": StreamGroup.EXECUTE,
        "smart_edit": StreamGroup.EXECUTE,
        "create_directory": StreamGroup.EXECUTE,
        "rename_file": StreamGroup.EXECUTE,
        "delete_file": StreamGroup.EXECUTE,
        "run_command": StreamGroup.EXECUTE,
        "python_exec": StreamGroup.EXECUTE,
        "git_command": StreamGroup.EXECUTE,
        "vision_click": StreamGroup.EXECUTE,
        "vision_type": StreamGroup.EXECUTE,
        # Test
        "smart_build_check": StreamGroup.TEST,
        "test": StreamGroup.TEST,
        # Verify
        "smart_build_error": StreamGroup.VERIFY,
        "vision_verify": StreamGroup.VERIFY,
    }

    # Semantic labels
    GROUP_LABELS = {
        StreamGroup.UNDERSTAND: "Understanding",
        StreamGroup.INVESTIGATE: "Investigating",
        StreamGroup.PLAN: "Planning",
        StreamGroup.EXECUTE: "Editing",
        StreamGroup.TEST: "Testing",
        StreamGroup.VERIFY: "Verifying",
        StreamGroup.RECOVER: "Recovering",
    }

    def __init__(self):
        self._streams: dict[str, ChatStream] = {}
        self._current_stream: Optional[ChatStream] = None
        self._pending_micros: list[MicroAction] = []
        self._last_group: Optional[StreamGroup] = None

    def start_stream(self, task: str) -> ChatStream:
        """Yangi stream boshlash."""
        stream = ChatStream(task=task)
        self._streams[task] = stream
        self._current_stream = stream
        return stream

    def add_tool_call(self, tool_name: str, args: dict, result: dict = None) -> Optional[dict]:
        """Tool call qo'shish — micro-action sifatida.

        Returns: Semantic action update (compact format) yoki None.
        """
        group = self.ACTION_GROUPS.get(tool_name, StreamGroup.EXECUTE)
        label = self.GROUP_LABELS.get(group, "Working")

        micro = MicroAction(
            action_type=tool_name,
            description=self._describe_tool(tool_name, args),
            target=self._extract_target(tool_name, args),
            result=self._extract_result(tool_name, result),
            metadata={"args": args, "result": result},
        )

        # Aggregation — bir xil group ketma-ket bo'lsa
        if self._last_group == group and self._current_stream:
            current = self._current_stream.get_current()
            if current and current.group == group:
                current.add_micro(micro)
                current.progress = self._aggregate_progress(current)
                return current.to_compact()

        # Yangi semantic action
        if self._current_stream:
            action = self._current_stream.add_action(group, label)
            action.start()
            action.add_micro(micro)
            action.progress = self._aggregate_progress(action)
            self._last_group = group
            return action.to_compact()

        return None

    def complete_action(self, success: bool = True, details: dict = None):
        """Joriy action'ni tugatish."""
        if self._current_stream:
            current = self._current_stream.get_current()
            if current:
                current.complete(success)
                if details:
                    current.files_changed = details.get("files", [])
                    current.reason = details.get("reason", "")
                    current.symbols = details.get("symbols", [])
                    current.dependencies = details.get("dependencies", [])
                    current.raw_output = details.get("raw_output", "")
                    current.commands = details.get("commands", [])
                    current.evidence = details.get("evidence", [])
                return current.to_compact()
        return None

    def complete_stream(self, success: bool = True, result: str = ""):
        """Stream'ni tugatish."""
        if self._current_stream:
            # Active actionlarni tugatish
            for action in self._current_stream.actions:
                if action.status == StreamStatus.RUNNING:
                    action.complete(success)

            self._current_stream.complete(success)
            self._current_stream.final_result = result
            self._current_stream = None
            self._last_group = None

    def get_stream(self, task: str = None) -> Optional[ChatStream]:
        """Stream olish."""
        if task:
            return self._streams.get(task)
        return self._current_stream

    def get_all_streams(self) -> list[dict]:
        """Barcha streamlarni olish."""
        return [s.to_summary() for s in self._streams.values()]

    # ── PRIVATE ────────────────────────────────────────────────

    def _describe_tool(self, tool_name: str, args: dict) -> str:
        """Tool uchun qisqa tavsif."""
        descriptions = {
            "read_file": f"read {args.get('path', '')}",
            "write_file": f"write {args.get('path', '')}",
            "edit_file": f"edit {args.get('path', '')}",
            "smart_edit": f"edit {args.get('path', '')}",
            "search_code": f"search '{args.get('query', '')}'",
            "grep": f"grep '{args.get('pattern', '')}'",
            "glob": f"find {args.get('pattern', '')}",
            "run_command": f"run {args.get('command', '')[:50]}",
            "python_exec": "run python",
            "git_command": f"git {args.get('command', '')}",
            "list_files": f"list {args.get('path', '.')}",
            "create_directory": f"mkdir {args.get('path', '')}",
            "rename_file": f"rename {args.get('old_path', '')}",
            "delete_file": f"delete {args.get('path', '')}",
            "vision_observe": "observe screen",
            "vision_find": f"find '{args.get('description', '')}'",
            "vision_click": f"click '{args.get('description', '')}'",
            "vision_type": f"type in '{args.get('target', '')}'",
            "vision_verify": f"verify '{args.get('action', '')}'",
            "smart_build_analyze": f"analyze: {args.get('task', '')[:50]}",
            "smart_build_check": f"check {len(args.get('files', []))} files",
            "smart_build_error": "parse error",
            "todowrite": "update tasks",
        }
        return descriptions.get(tool_name, tool_name)

    def _extract_target(self, tool_name: str, args: dict) -> str:
        """Tool target'ini ajratib olish."""
        return args.get("path") or args.get("query") or args.get("pattern") or args.get("description") or ""

    def _extract_result(self, tool_name: str, result: dict = None) -> str:
        """Tool natijasini ajratib olish."""
        if not result:
            return ""
        if result.get("ok") is False:
            return f"error: {result.get('error', 'unknown')}"
        if result.get("content"):
            return f"{len(result['content'])} chars"
        if result.get("output"):
            return result["output"][:100]
        return "ok"

    def _aggregate_progress(self, action: SemanticAction) -> str:
        """Progress matnini yaratish."""
        count = len(action.micro_actions)
        if count <= 1:
            return ""
        return f"{count} operations"
