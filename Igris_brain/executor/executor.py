"""
IGRIS BRAIN — AgentExecutor (ReAct loop + self-correction)
==========================================================
Taskni bajaradi:
  1. PLAN   — TaskPlanner orqali bosqichlarga bo'ladi
  2. ACT    — har bosqich uchun tool'lar chaqiradi (read/write/run/python)
  3. OBSERVE— tool natijalarini yig'adi
  4. CORRECT— xatoliklarda LLM yordamida tuzatish (max 2 qayta urinish)

Iteratsiya cheklovi (max_iter), tool chaqiruv cheklovi (max_tool_calls).
Natijalar memory'ga yoziladi (decision-log, task-memory) — RAG uchun.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import shutil
import threading
import time
from collections import Counter
from typing import Any, Callable, Optional

_brain = sys.path[0] if sys.path else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _brain not in sys.path:
    sys.path.insert(0, _brain)
if os.path.join(os.path.dirname(_brain), "Igris_Memory") not in sys.path:
    sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))
from tools import Workspace, ToolRegistry, DEFAULT_REGISTRY
from planning.planner import TaskPlanner, URL_RE, _req_block
from agent.memory_bridge import MemoryBridge
from skills import SkillManager

# Phase 1: formal state machine + goal preservation (audit §1/§2/§12/§17).
# Import fail-safe: modul yo'q bo'lsa executor baribir ishlaydi (eski oqim).
try:
    from state.state_machine import StateMachine, AgentState, StateTransitionError, validate_plan_tools
    from state.goal_model import Goal, GoalContext, Objective
    _PHASE1_OK = True
except Exception:  # pragma: no cover
    _PHASE1_OK = False

# Phase 4 (§11): ErrorType enum — xato tasniflash (fail-safe import).
try:
    from tools.base import ErrorType as _ErrorType
except Exception:  # pragma: no cover
    _ErrorType = None

# Phase 2: Observation→State + VerificationRecord + loop detection (§4/§9/§10).
try:
    from state.world_state import (AgentWorldState, VerificationLog, VerificationRecord,
                             detect_loop, detect_stuck)
    import uuid as _uuid

    def _action_id() -> str:
        return f"act-{_uuid.uuid4().hex[:10]}"

    _PHASE2_OK = True
except Exception:  # pragma: no cover
    _PHASE2_OK = False

# Roadmap v3 R1 (§2/§17/§28): requirement matrix — deterministic completion
# contract. Import xato bo'lsa eski xatti-harakat (matrix yo'q) saqlanadi.
try:
    from planning import requirement_matrix as _rmx
    _RMX_OK = True
except Exception:  # pragma: no cover
    _rmx = None
    _RMX_OK = False


def _python_syntax_check(code: str) -> tuple[bool, str]:
    """A1 1-qadam: Python kodi sintaksis daraxtga to'g'ri keladimi.

    Deterministik (LLM yo'q, 0 xarajat, ~ms). Qaytadi: (ok, qisqa xato izohi).
    SyntaxError/IndentationError bo'lsa (ok=False, 'line N: msg') qaytadi.
    """
    import ast
    src = str(code or "")
    if not src.strip():
        return True, ""  # bo'shni boshqa qatlam tekshiradi
    try:
        ast.parse(src)
        return True, ""
    except SyntaxError as exc:
        line = f"line {exc.lineno}: " if getattr(exc, "lineno", None) else ""
        msg = str(getattr(exc, "msg", None) or exc)
        return False, f"{line}{msg}"
    except (ValueError, RecursionError):
        # noma'lum bayroqlar/rekursiya — sekur pas (false positive oldini olish)
        return True, ""


# A1 2-qadam (run-verification): bu xatolar fayl ISHGA TUSHMASLIGI haqida —
# gate'dan o'tmasligi kerak. Import xatolari NEYTRAL (uchinchi paket muhiti
# bog'liq) — pastda ro'yxat.
_RUN_FATAL_RE = re.compile(
    r"(NameError|TypeError|AttributeError|UnboundLocalError|"
    r"ZeroDivisionError|IndexError|KeyError|RecursionError)")
_RUN_NEUTRAL_RE = re.compile(
    r"(ModuleNotFoundError|ImportError|KeyboardInterrupt|"
    r"FileNotFoundError|PermissionError)")


def _python_run_check(code: str) -> tuple[Optional[bool], str]:
    """A1 2-qadam: Python fayli haqiqatan ishga tushadimi (izolyatsiyada).

    Qaytadi: (True, 'run ok') — exit 0; (False, 'NameError: ...') — ishga
    tushmaydigan kod; (None, sabab) — NEYTRAL (tekshirib bo'lmadi:
    deny-listdagi xavfli chaqiruvlar, import/deps xatosi, timeout).

    Xavfsizlik: subprocess (agent'dan alohida) + 6s timeout + python_tools
    deny-listi (xavfli kod umuman ishga tushirilmaydi) + `-I` (izolyatsiya:
    user site-packages'siz).
    """
    src = str(code or "")
    if len(src.strip()) < 120:  # sintaksis gate bilan bir xil chegara
        return None, "too short"
    try:
        from tools.python_tools import _blocked_by_sandbox
        blocked = _blocked_by_sandbox(src)
        if blocked:
            return None, "skipped (deny-list)"
    except Exception:
        pass  # deny-list mavjud emas — baribir ishga tushiramiz (alohida subprocess)
    import ast as _ast
    try:
        _ast.parse(src)  # sintaksis buzuk bo'lsa subprocess beker — darhol neytral
    except Exception:
        return None, "syntax"
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", src],
            capture_output=True, text=True, timeout=6,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                 "PYTHONIOENCODING": "utf-8"},
        )
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except OSError:
        return None, "os error"
    stderr = (proc.stderr or "")
    if proc.returncode == 0:
        return True, "run ok"
    # Import/muhit xatolari — NEYTRAL (uchinchi paket bu muhitda bo'lmasligi mumkin)
    if _RUN_NEUTRAL_RE.search(stderr):
        return None, "import/deps"
    m = _RUN_FATAL_RE.search(stderr)
    if m:
        lines = [ln for ln in stderr.strip().splitlines() if ln.strip()]
        return False, (lines[-1] if lines else m.group(0)).strip()[:160]
    return None, f"exit {proc.returncode}"


def _default_hooks():
    """Lazy DEFAULT_BUS import (hook tizimi ixtiyoriy)."""
    try:
        from monitor.hooks import DEFAULT_BUS
        return DEFAULT_BUS
    except Exception:
        return None


# Reja-birinchi qoida — har bir native run'da majburiy system qo'shimchasi.
# Agent muammoni aniqlab, reja tuzib, shundan keyin tool'lar bilan ishlaydi;
# xatolikda rejaga qaytadi (plan-first-fix skilliga mos).
PLAN_FIRST_SYSTEM = (
    "\n\nMANDATORY AGENTIC WORK RULE:\n"
    "PIPELINE: UNDERSTAND → PLAN → EXECUTE → VERIFY → RESPOND\n"
    "  1. UNDERSTAND: Restate the problem in one sentence.\n"
    "  2. PLAN: 1-3 concrete steps (which files, which tools, what args).\n"
    "  3. EXECUTE: Call tools step by step. No filler text between steps.\n"
    "  4. VERIFY: Check results. If error, fix the failing step — not ad-hoc.\n"
    "  5. RESPOND: One sentence summary. File path if created.\n"
    "NEVER say 'I cannot'. You have tools. Use them.\n"
    "TOKEN EFFICIENCY: Do work FIRST, explain after. No 'Let me...' preamble."
)


# Qobiliyat yetishmasligi belgilari — model "qila olmayman" desa
CAPABILITY_GAP_PATTERNS = re.compile(
    r"(i (don'?t|do not|can'?t|cannot|am not|'?m not) (have|do|draw|create|generate|produce)|"
    r"(no|not) (image|picture|drawing|vision|multimodal|capabilit|tool|ability)|"
    r"(don'?t|cannot|can'?t) (support|provide|access|use|see|read the image)|"
    r"lacking|unable to|out of scope|not possible|i have no|i do not have)",
    re.IGNORECASE,
)

# Planner whitelist — re-plan natijasidagi tool'larni ham shu ro'yxat bilan
# normalizatsiya qilamiz (Part L, CP-L4).
_PLANNER_ALLOWED_TOOLS = {
    "read_file", "write_file", "apply_patch", "list_files",
    "run_command", "python_exec",
}

# Muvaffaqiyatsiz qadamdan so'ng LLM'dan tuzatilgan qadamlar so'rash (Part L).
REPLAN_SYSTEM = (
    "You are the re-planner of a coding agent. One of the planned steps failed. "
    "Look at the error and propose REVISED next steps that fix the approach. "
    "Respond with ONLY valid JSON (an array of step objects)."
)


EXEC_ARGS_SYSTEM = (
    "You are the tool-caller of a coding agent. Given a step and a tool schema, "
    "produce the exact JSON arguments for the tool call. Use real paths relative "
    "to the workspace root. Reply with ONLY the JSON object of arguments."
)


def json_dumps_sorted(obj) -> str:
    import json
    try:
        return json.dumps(obj, sort_keys=True, ensure_ascii=False)
    except TypeError:
        return str(obj)


CORRECTION_SYSTEM = (
    "You are the error-fixer of a coding agent. A tool call failed. Given the "
    "tool name, the arguments, and the error, reply with ONLY the corrected "
    'JSON arguments for the same tool: {"tool": "...", "args": {...}}. '
    "If the plan itself was wrong, reply with a corrected plan step "
    '{"plan": "..."} instead.'
)

# Sifat eshigi: vazifa yozma natija talab qilganda, bo'sh/yo'q fayl
# topilsa - tuzatuvchi pass ishga tushadi (agent "bajardim" desa ham).
DELIVERABLE_WORDS = (
    "yoz", "yarat", "create", "write", "summar", "xulosa", "tahlil",
    "analyz", "report", "hisobot", "qayd", "natija", "result", "deliverable",
    "fix", "tuzat", "qur", "build", "och", "open", "draw", "chiz",
)

CORRECTIVE_SYSTEM = (
    "You are the finishing step of a coding agent. The task was mostly executed "
    "but the required written deliverable is missing, empty or does not fulfill "
    "the task. Produce the ACTUAL deliverable content from the tool outputs "
    "below: if the task asked for a summary/report/analysis, write that "
    "summary/report directly - the content itself, not instructions on how to "
    "do it, no placeholders, no empty text. Reply with ONLY valid JSON: "
    '{"path": "...", "content": "..."}'
)

# Sifat eshigi: yozma natija qisqa/bo'sh bo'lsa LLM bilan tekshiriladi
# ("Natijalar tahlil qilindi." kabi shablon - bajarilmagan hisoblanadi).
VERIFY_SYSTEM = (
    "You verify whether a coding agent actually fulfilled the user's task. "
    "Given the task, the deliverable file content, and the tool outputs, decide "
    "if the deliverable ACTUALLY completes the task - e.g. a real summary or "
    "report of the retrieved content. Short placeholder text like 'done', "
    "'ok', 'Natijalar tahlil qilindi' is NOT completion. "
    "Reply with ONLY: COMPLETE or INCOMPLETE"
)


# Tool nomi -> pipeline bosqichi (UI PipelineStepper'da REAL progress ko'rsatish
# uchun). 'plan' -> 'read' -> 'edit' -> 'test' -> 'review' oqimi.
_READ_TOOLS = (
    "read_file", "list_files", "list_directory", "glob", "search", "grep",
    "workspace_list", "get_file_info", "browser_get_text", "browser_info",
    "web_fetch",
)
# Fayl YARATUVCHI vositalar — rasm yuklash/qidiruv ham 'edit' (fayl hosil qiladi)
_EDIT_TOOLS = ("write_file", "apply_patch", "use_skill", "mcp_call", "web_search_image")
_TEST_TOOLS = ("python_exec", "run_command", "run_script", "browser_click",
               "browser_type", "browser_press_key")
_REVIEW_TOOLS = ("browser_screenshot", "verify", "check")


def stage_for_tool(tool: str) -> str:
    """Tool nomidan pipeline bosqichini aniqlaydi ('plan'|'read'|'edit'|'test'|'review')."""
    name = str(tool or "")
    low = name.lower()
    if low == "request_human":
        # Inson savoli — bajarish to'xtatilgan (pause), plan bosqichida ko'rinadi.
        return "plan"
    if low in _READ_TOOLS:
        return "read"
    if low in _EDIT_TOOLS:
        return "edit"
    if low in _TEST_TOOLS:
        return "test"
    if low in _REVIEW_TOOLS:
        return "review"
    if low.startswith("art__draw") or low.startswith("art__ui"):
        return "edit"
    if low.startswith("browser") or low.startswith("web_ai_bridge__browser"):
        return "read"
    return "read"


def _tool_preview(tool: str, args: dict) -> str:
    """Progress detal'i uchun qisqa tavsif (fayl/URL/komanda/skill nomi)."""
    args = args or {}
    for key in ("path", "file", "url", "command", "code", "output", "app", "subject", "name", "tool", "query"):
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().split("\n")[0][:48]
    return ""


class AgentExecutor:
    def __init__(
        self,
        workspace_root: str,
        llm=None,
        registry: Optional[ToolRegistry] = None,
        planner: Optional[TaskPlanner] = None,
        memory: Optional[MemoryBridge] = None,
        skills=None,
        mcp=None,
        human_provider=None,
        max_iter: int = 8,
        max_tool_calls: int = 30,
        max_retries: int = 2,
        hooks=None,
        plan_first: bool = True,
        progress_cb: Optional[Callable[[str, str], None]] = None,
        checkpoint_dir: str = "",
        cancel_event: Optional[threading.Event] = None,
    ):
        self.workspace = Workspace(workspace_root)
        self.registry = registry or DEFAULT_REGISTRY
        self.llm = llm
        self.planner = planner or TaskPlanner(
            llm=llm,
            mcp_names=(mcp.names() if mcp is not None else ()),
        )
        self.memory = memory
        self.skills = skills
        self.mcp = mcp
        self.human_provider = human_provider
        self.max_iter = max_iter
        self.max_tool_calls = max_tool_calls
        self.max_retries = max_retries
        self.hooks = hooks if hooks is not None else _default_hooks()
        self.plan_first = plan_first
        # Jonli progress: (stage, detail) — RunManager/UI real bosqichni ko'rsatadi.
        self.progress_cb = progress_cb
        # Phase 4 (§15): CANCELLATION — tashqaridan to'xtatish signali.
        # Har step/iteration boshida tekshiriladi; set() qilingach run
        # "cancelled" holatda Graceful yakunlanadi (checkpoint SAQLANADI).
        self.cancel_event = cancel_event or threading.Event()
        # Phase 4 (§11): same-error detection — bir xil xato matni N marta
        # takrorlansa — request_human (HITL escalation) taklif qilinadi.
        self.escalate_after_same_errors = 3
        # Phase 4 (§16): STRUCTURED error/recovery log — natija record'ida
        # {type, message, tool, recovery_action} ro'yxati (debug uchun).
        self._error_log: list[dict] = []
        self._recovery_log: list[dict] = []
        # SEMANTIK TALAB QATLAMI (Part L): user talab modeli — reja va sifat
        # eshigi shunga moslashadi. Lazy init (offline'da ham ishlaydi).
        self.req_extractor = None
        # Phase 1: goal preservation + formal state machine (har run uchun yangi).
        self.goal_context: Optional["GoalContext"] = None
        self.sm: Optional["StateMachine"] = None
        # Phase 2: observation→state + verification evidence (§4/§10).
        self.world: Optional["AgentWorldState"] = None
        self.vlog: Optional["VerificationLog"] = None
        # Phase 3 (§8/§12): checkpoint/resume — goal + qolgan qadamlar disk'da.
        # checkpoint_dir bo'sh bo'lsa — checkpoint YO'Q (eski xulq o'zgarmaydi).
        self.checkpoint_dir = checkpoint_dir
        if checkpoint_dir:
            try:
                os.makedirs(checkpoint_dir, exist_ok=True)
            except Exception:
                self.checkpoint_dir = ""
        # Roadmap v3 R1 (§2/§17/§28): requirement matrix — har run uchun yangi
        # snapshot (run boshida quriladi, immutable). False = eski xatti-harakat.
        self.enable_requirement_matrix = True

    def _extract_req(self, task: str):
        """Task uchun Requirement modeli (LLM/CAG) — xatolikda None."""
        if self.req_extractor is None:
            try:
                from core.requirements import RequirementExtractor
                self.req_extractor = RequirementExtractor(llm=self.llm, cache=None)
            except Exception:
                self.req_extractor = False
        if not self.req_extractor:
            return None
        try:
            return self.req_extractor.extract(task, None)
        except Exception:
            return None

    def _req_asks_output(self, task: str, req) -> bool:
        """Vazifa yozma natija (fayl) talab qiladimi — Requirement asosida.

        `_task_asks_output` (kalit-so'z) o'rniga/qo'shimchasiga: output_format
        fayl-shaklida bo'lsa yoki deliverable_name aniq bo'lsa — sifat eshigi
        ishlaydi (Part L, CP-L4/L8).
        """
        if req is None:
            return False
        if getattr(req, "deliverable_name", None):
            return True
        fmt = getattr(req, "output_format", "text")
        return fmt in ("file", "code", "image", "html")

    def _replan(self, task: str, failed_step: dict, step_result: dict,
                remaining: list[dict], req) -> Optional[list[dict]]:
        """Muvaffaqiyatsiz qadamdan so'ng — LLM'dan tuzatilgan keyingi qadamlar.

        Qotib qolgan "abort + canned summary" o'rniga: model xatoni ko'rib,
        qolgan ish uchun YANGI qadamlar taklif qiladi (Part L, CP-L4/L7).
        Maksimal re-plan 2 — cheksiz loop yo'q.
        """
        if self.llm is None:
            return None
        err = ""
        for o in (step_result.get("result") or {}).get("outcomes") or []:
            if isinstance(o, dict) and not o.get("ok"):
                err += " " + str(o.get("error") or "")
        allowed = "read_file, write_file, apply_patch, list_files, run_command, python_exec"
        if self.mcp is not None:
            allowed += ", " + ", ".join(self.mcp.names())
        prompt = (
            f"An agent step failed while working on the task.\n"
            f"Failed step: {failed_step.get('title', '')} — {failed_step.get('detail', '')}\n"
            f"Error: {(err or step_result.get('result', {}).get('note', '')).strip()[:500]}\n"
            f"Remaining planned steps: {remaining or 'none'}\n\n"
            + (_req_block(req) if req is not None else "")
            + "\nPropose REVISED NEXT STEPS (valid JSON array of "
            '{"id": int, "title": str, "tools": [str], "detail": str}) using tools from: '
            + allowed + ". Respond with ONLY valid JSON."
        )
        text = self.llm.complete(system=REPLAN_SYSTEM, prompt=prompt)
        if not text:
            return None
        parsed = self.planner._extract_json(text)
        if not parsed:
            return None
        if isinstance(parsed, dict):
            parsed = parsed.get("steps") or []
        if not isinstance(parsed, list) or not parsed:
            return None
        out: list[dict] = []
        for s in parsed[: self.max_iter]:
            try:
                sid = int(s.get("id", len(out) + 1))
            except (TypeError, ValueError):
                sid = len(out) + 1  # C2 fix: 's1' kabi non-numeric id — position bilan
            out.append({
                "id": sid,
                "title": str(s.get("title", "Step")).strip(),
                "tools": [t for t in (s.get("tools") or []) if t in _PLANNER_ALLOWED_TOOLS or (self.mcp is not None and t in self.mcp.names())][:4],
                "detail": str(s.get("detail", "")).strip(),
            })
        return out or None

    # ------------------------------------------------------------ #
    # Roadmap v2 C2 (§16): BIRLASHGAN TIMELINE — SM transitions + tool_calls
    # + errors + recovery_events + verifications bir chronological ro'yxatda.
    # ------------------------------------------------------------ #

    def _build_timeline(self, tool_calls: list[dict]) -> list[dict]:
        """Har qatlam voqeasini birlashtirib, ts bo'yicha saralaydi.

        Event shakli: {ts, layer, kind, detail, ...qatlam-maydonlari}
        - sm:      SM state transitions (kind=transition, from/to/note)
        - tool:    tool calls (kind=tool_call, tool/action_id/duration)
        - error:   structured errors (kind=error, type/tool/message)
        - recovery: recovery events (kind=recovery, action/detail)
        - verify:  verifications (kind=verification, method/status)

        ts YO'Q bo'lgan voqealar (eski rekordlar) — oxiriga qo'shiladi
        (ts=None → sortingda tugatiladi, hech qachon yiqilmaydi).
        """
        events: list[dict] = []

        # 1) SM transitions (history: {ts, from, to, ok, note, ...})
        if self.sm is not None:
            try:
                for rec in self.sm.history():
                    events.append({
                        "ts": rec.get("ts"),
                        "layer": "sm",
                        "kind": "transition",
                        "from": rec.get("from"),
                        "to": rec.get("to"),
                        "ok": rec.get("ok"),
                        "detail": str(rec.get("note") or "")[:200],
                    })
            except Exception:
                pass

        # 2) Tool calls (record: {action_id, tool, args, result, ...})
        for tc in tool_calls or []:
            ts = tc.get("ts")
            events.append({
                "ts": ts,
                "layer": "tool",
                "kind": "tool_call",
                "tool": str(tc.get("tool", "")),
                "action_id": str(tc.get("action_id", "")),
                "ok": bool((tc.get("result") or {}).get("ok", True)),
                "detail": str(tc.get("output_preview") or "")[:200],
            })

        # 3) Errors
        for e in self._error_log or []:
            events.append({
                "ts": e.get("ts"),
                "layer": "error",
                "kind": "error",
                "type": e.get("type"),
                "tool": e.get("tool", ""),
                "detail": str(e.get("message") or "")[:200],
            })

        # 4) Recovery events
        for r in self._recovery_log or []:
            events.append({
                "ts": r.get("ts"),
                "layer": "recovery",
                "kind": "recovery",
                "action": r.get("action"),
                "detail": str(r.get("detail") or "")[:200],
            })

        # 5) Verifications
        if self.vlog is not None:
            try:
                for v in self.vlog.to_list():
                    events.append({
                        "ts": v.get("timestamp"),
                        "layer": "verify",
                        "kind": "verification",
                        "method": v.get("method"),
                        "status": v.get("status"),
                        "detail": str(v.get("note") or "")[:200],
                    })
            except Exception:
                pass

        # ts bo'yicha saralash (None — oxirida, fail-safe)
        events.sort(key=lambda ev: (
            1 if ev.get("ts") is None else 0,
            ev.get("ts") or 0.0,
        ))
        return events

    # ------------------------------------------------------------ #
    # Roadmap v2 B1 (§13): VERIFIED-ONLY SPEECH — final xulosadagi da'volar
    # real tool_calls/workspace dalillari bilan deterministik solishtiriladi.
    # ------------------------------------------------------------ #

    # Da'vo patternlari: matndan fayl yo'llari va tool nomlarini ajratadi
    _CLAIM_PATH_RE = re.compile(
        r"(?:[\w./\\-]+\/)*[\w\-]+\.[A-Za-z0-9]{1,6}"  # path/file.ext
    )
    _CLAIM_TOOL_RE = None  # lazy: registry asosida quriladi

    @staticmethod
    def _known_file_from_tool_calls(tool_calls: list[dict]) -> set[str]:
        """tool_calls ichida haqiqatan yozilgan/o'zgartirilgan fayl yo'llari."""
        known: set[str] = set()
        for tc in tool_calls or []:
            name = str(tc.get("tool", ""))
            args = tc.get("args", {}) or {}
            if name in ("write_file", "apply_patch", "read_file", "delete_file", "rename_file"):
                p = str(args.get("path") or args.get("source") or "").strip()
                if p:
                    known.add(os.path.basename(p))
                    known.add(p.replace("\\", "/").lstrip("./"))
            if name == "use_skill":
                pass  # skill nomi fayl da'vo emas
        return {k for k in known if k}

    def _verify_summary_claims(
        self,
        summary: str,
        task: str,
        tool_calls: list[dict],
    ) -> tuple[bool, str, list[dict]]:
        """Final xulosadagi da'volarni dalillar bilan solishtiradi (B1).

        Qaytaradi: (all_ok, correction_note, unverified_claims)
        - Fayl da'vosi: xulosada tilga olingan fayl tool_calls'da yoki
          workspace'da mavjud bo'lishi kerak.
        - Tool da'vosi: xulosada tilga olingan tool nomi bajarilganlar
          ro'yxatida bo'lishi kerak ("deploy qildim" — lekin run_command
          bajarilmagan bo'lsa — yolg'on da'vo).
        Deterministik, LLM'siz. Notion: "success" ga ishonch emas — faqat
        dalil (§13 "Done claim only after verification").
        """
        if not summary or not summary.strip():
            return True, "", []
        if not tool_calls:
            # hech qanday tool bajarilmagan — fayl/tool da'vosi bo'lsa ham dalil yo'q;
            # faqat fayl patternlarini tekshiramiz (workspace bo'sh bo'lsa unverified)
            pass
        low = (summary or "").lower()
        executed_tools = {str(tc.get("tool", "")) for tc in (tool_calls or [])}
        known_files = self._known_file_from_tool_calls(tool_calls or [])

        unverified: list[dict] = []

        # 1) Fayl da'volari — path/file.ext patterni
        for m in self._CLAIM_PATH_RE.finditer(summary):
            claim = m.group(0).replace("\\", "/").lstrip("./").lower()
            base = os.path.basename(claim)
            if not base or "." not in base:
                continue
            # kod/paket nomlari (main.py, package.json) — da'vo sifatida
            if base in {k.lower() for k in known_files}:
                continue
            # workspace'da mavjudmi?
            exists = False
            try:
                exists = self.workspace.exists(claim) or self.workspace.exists(base)
            except Exception:
                exists = False
            if exists or base in {k.lower() for k in known_files}:
                continue
            unverified.append({"type": "file", "claim": claim})

        # 2) Tool da'volari — xulosada tool nomi aytilib, bajarilmagan bo'lsa
        #    (faqat registry nomlari bilan; "git" kabi umumiy so'zlar ushlanmaydi)
        for tool_name in self.registry.names():
            if len(tool_name) < 5:  # qisqa nomlar so'z ichida yalg'on mos bo'ladi
                continue
            if tool_name in low and tool_name not in executed_tools:
                # "run_command"ni bajarish kerak edi, lekin bo'lmagan
                # — lekin bu MUVOFFAQIYAT da'vosi ekanini aniqlash qiyin;
                # xavfsiz tomonda: bajarilmagan tool tilga olingan bo'lsa flag.
                unverified.append({"type": "tool_not_executed", "claim": tool_name})

        if not unverified:
            return True, "", []

        note_parts = [f"{u['type']}: {u['claim']}" for u in unverified[:8]]
        correction = (
            "[claim-check] Xulosada dalilsiz da'volar topildi va aniqlandi: "
            + "; ".join(note_parts)
            + ". Bu elementlar HAQIQATAN bajarilmagan yoki yaratilmagan."
        )
        return False, correction, unverified

    def _apply_claim_check(
        self,
        final_content: str,
        task: str,
        tool_calls: list[dict],
        result: dict,
        status: str,
    ) -> str:
        """run()/run_native() yakunida da'vo tekshiruvi + correction qo'llash.

        result'ga: final_claims_checked, unverified_claims maydonlari yoziladi.
        Yolg'on da'vo topilsa: xulosa Correction bilan to'ldiriladi + status
        hech qachon yuqorilamasdi (ok -> ok emas; faqat haqiqiy dalil bo'lsa ok).
        Recovery log'ga yoziladi (§16).
        """
        ok, correction, unverified = self._verify_summary_claims(
            final_content, task, tool_calls)
        result["final_claims_checked"] = True
        if ok:
            result["unverified_claims"] = []
            return final_content
        result["unverified_claims"] = unverified
        self._log_recovery("claim_check", correction[:200])
        # Xulosa: asl matn + aniq tuzatish izohi (fayl yo'q — demak da'vo yolg'on)
        if status == "ok" and any(u["type"] == "file" for u in unverified):
            # "bajarildi" da'vosi fayl dalilsiz — status ok qoladi (tool'lar ok),
            # lekin xulosaga ANIQ tuzatish yoziladi (§13: failure yashirmaslik).
            return f"{final_content.rstrip()}\n\n{correction}"
        return f"{final_content.rstrip()}\n\n{correction}" if final_content.strip() else correction

    def _progress(self, stage: str, detail: str, record: Optional[dict] = None):
        """Progress callback'ni chaqiradi (xavfsiz — hech qachon yiqilmaydi).

        record: bajarilgan tool haqida to'liq yozuv (tool, args, result, output_preview)
        — RunManager uni `tool_calls_partial`ga qo'shadi, frontend RUN DAVOMIDA
        chizma kartalarini jonli ko'rsatadi (run tugashini kutmaydi).
        """
        if self.progress_cb is None:
            return
        try:
            self.progress_cb(stage, detail, record)
        except Exception:
            self.progress_cb = None

    # ------------------------------------------------------------ #
    # Phase 4 (§11/§15/§16): cancellation + error/recovery log
    # ------------------------------------------------------------ #

    def _check_cancelled(self) -> bool:
        """Cancellation signali tekshiruvi (§15).

        cancel_event set() bo'lsa True — chaqiruvchi to'xtashi kerak.
        Deterministik, thread-safe (Event atomik).
        """
        return self.cancel_event is not None and self.cancel_event.is_set()

    def _log_error(self, etype: str, message: str, tool: str = "") -> None:
        """Structured error log (§16): {type, message, tool, ts} — natijada qaytadi."""
        self._error_log.append({
            "type": etype or "internal",
            "message": str(message or "")[:300],
            "tool": tool,
            "ts": round(time.time(), 3),
        })

    def _log_recovery(self, action: str, detail: str = "") -> None:
        """Recovery log (§16): {action, detail, ts} — retry/fix/replan/resume/HITL."""
        self._recovery_log.append({
            "action": action,
            "detail": str(detail or "")[:200],
            "ts": round(time.time(), 3),
        })

    def _record_tool_error(self, tool_name: str, out: dict) -> bool:
        """Tool xatosini tasniflaydi va loglaydi (§11 + §16).

        Qaytadi: escalate_kerakmi? — bir xil xato matni
        `escalate_after_same_errors` marta takrorlansa True (§11 qadam 5).
        """
        etype = "internal"
        if _ErrorType is not None:
            try:
                etype = _ErrorType.from_result(out)
            except Exception:
                etype = "internal"
        msg = str(out.get("error") or "")
        self._log_error(etype, msg, tool=tool_name)
        # §11 same-error counter: oxirgi N xatoning hammasi bir xil matn bo'lsa —
        # agent qotib qolgan — HITL escalation kerak.
        recent = [e["message"] for e in self._error_log[-self.escalate_after_same_errors:]]
        return (len(recent) >= self.escalate_after_same_errors
                and len(set(recent)) == 1 and bool(msg.strip()))

    # ------------------------------------------------------------ #
    # Checkpoint / resume (Phase 3: §8 pipeline resume + §12 goal restore)
    # ------------------------------------------------------------ #

    def _checkpoint_path(self, task_id: str) -> str:
        return os.path.join(self.checkpoint_dir, f"exec_{task_id}.json")

    # Roadmap v3 R2 (§10): checkpoint schema versioni — bo'lajak evolution
    # uchun kafolat: eski versiya o'qiladi (best-effort), YANGIROQ versiya
    # rad etiladi (kelajakdagi format — xavfsiz fallback).
    CHECKPOINT_VERSION = 2

    def _save_checkpoint(self, task: str, completed_step_ids: list[int],
                         status: str, plan_steps: Optional[list[dict]] = None) -> None:
        """Run holatini disk'ga yozadi: goal + progress (§8 checkpoint).

        §12 goal restore: immutable Goal to'liq (id+text) saqlanadi — resume
        bir xil goal_id bilan davom etadi (goal yangi yaratilmaydi).
        Fail-safe: checkpoint xatosi run'ni BUZMAYDI.

        R2 (§10): version + plan steps + requirements snapshot + verification
        log + action_id registry. Avvalgi valid checkpoint `.bak` nusxa
        sifatida saqlanadi (corruption fallback) — atomik yozish bilan birga.
        """
        if not self.checkpoint_dir or self.goal_context is None:
            return
        try:
            import json as _json
            data = {
                "version": self.CHECKPOINT_VERSION,              # R2: schema evolution
                "task": task,
                "goal": self.goal_context.goal.to_dict(),        # §12: immutable goal
                "objective": self.goal_context.objective.to_dict() if self.goal_context.objective else None,
                "completed_step_ids": completed_step_ids[:50],
                "status": status,
                "tool_calls_count": len(self._cp_tool_calls),
                "ts": time.time(),
                # R2 (§22): step tafsilotlari (fayl nomlari) — resume'da
                # reconciliation fs bilan solishtirish uchun.
                "plan_steps": [
                    {"id": s.get("id"), "title": s.get("title", ""),
                     "tools": s.get("tools", [])}
                    for s in (plan_steps or [])[:50]
                ],
                # R2 (§10): immutable requirement snapshot — resume'da BIR XIL
                # requirement'lar bilan tekshirish kafolati.
                "requirements": (self._req_snapshot.to_json()
                                 if getattr(self, "_req_snapshot", None) is not None else None),
                # R2 (§10/§27): verification evidence tarixi (kesilgan).
                "verifications": (self.vlog.to_list()[-20:]
                                  if getattr(self, "vlog", None) is not None else []),
                # R2 (§11): bajarilgan action id'lar — resume'da duplicate himoya.
                "action_ids": [tc.get("action_id") for tc in (self._cp_tool_calls or [])
                               if tc.get("action_id")][-100:],
            }
            path = self._checkpoint_path(self.goal_context.goal.id)
            # R2 (§10): mavjud valid checkpoint'ni .bak ga ko'chirish —
            # yangi yozish buzilsa eski holat tiklanadi.
            if os.path.exists(path):
                try:
                    shutil.copyfile(path, path + ".bak")
                except Exception:
                    pass
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                _json.dump(data, fh, ensure_ascii=False)
            os.replace(tmp, path)   # atomik yozish (crash-safe)
        except Exception:
            pass  # checkpoint muhim emas run to'g'ri yakunlanishiga

    def load_checkpoint(self, task_id: str) -> Optional[dict]:
        """Checkpoint'ni o'qiydi (resume uchun). Mavjud bo'lmasa None.

        R2 (§10) corruption detection:
          - JSON parse xato -> `.bak` nusxadan tiklash harakati
          - `.bak` ham buzuk -> None (resume yo'q, xavfsiz yangi run)
          - version YANGIROQ checkpoint rad etiladi (kelajakdagi format)
        """
        if not self.checkpoint_dir or not task_id:
            return None
        try:
            import json as _json
            path = self._checkpoint_path(task_id)
            raw = self._read_cp_json(path)
            if raw is None and os.path.exists(path + ".bak"):
                # Buzuk asosiy fayl — .bak fallback (R2 kafolati)
                raw = self._read_cp_json(path + ".bak")
            if raw is None:
                return None
            try:
                ver = int(raw.get("version") or 1)
            except Exception:
                ver = 1
            if ver > self.CHECKPOINT_VERSION:
                return None  # kelajakdagi format — qayta ishlash xavfsiz emas
            return raw
        except Exception:
            return None

    @staticmethod
    def _read_cp_json(path: str) -> Optional[dict]:
        """JSON faylni o'qiydi; parse xatosida None (corruption-safe)."""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return None

    def clear_checkpoint(self, task_id: str) -> None:
        """Muvaffaqiyatli yakunlangandan keyin checkpoint o'chiriladi.

        R2: .bak zaxira nusxasi ham o'chiriladi — aks holda workspace'da
        checkpoint qoldiqlari qoladi (stress run izolyatsiyasi buziladi).
        """
        if not self.checkpoint_dir or not task_id:
            return
        try:
            path = self._checkpoint_path(task_id)
            for p in (path, path + ".bak"):
                if os.path.exists(p):
                    os.remove(p)
        except Exception:
            pass

    def _restore_checkpoint_for_task(self, task: str) -> bool:
        """§8/§12: shu task uchun saqlangan checkpoint bo'lsa — goal + progress tiklanadi.

        Goal ID STABIL bo'ladi: bir xil task qayta run qilinsa (crash'dan keyin
        yoki yangi executor nusxada) — disk'dagi BIR XIL goal tiklanadi, yangi
        UUID yaratilmaydi (goal continuity). Topilmasa — False.
        """
        if not self.checkpoint_dir:
            return False
        try:
            import json as _json
            for fname in os.listdir(self.checkpoint_dir):
                if not fname.startswith("exec_") or not fname.endswith(".json"):
                    continue
                path = os.path.join(self.checkpoint_dir, fname)
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        data = _json.load(fh)
                except Exception:
                    continue
                if str(data.get("task") or "") != task or not data.get("goal"):
                    continue
                goal = Goal.from_dict(data["goal"])
                objective = (Objective.from_dict(data["objective"])
                             if data.get("objective") else None)
                self.goal_context = GoalContext(goal, objective)
                self._cp_skip_steps = set(
                    int(i) for i in (data.get("completed_step_ids") or []))
                return True
        except Exception:
            pass
        return False

    def resume_from_checkpoint(self, task_id: str) -> Optional[dict]:
        """Checkpoint'dan goal restore qilib run'ni davom ettiradi (§12).

        - Goal disk'dan tiklanadi (BIR XIL goal_id — yangi yaratilmaydi)
        - run() chaqiriladi; reja planner'dan qayta olinadi (deterministik)
          va allaqachon bajarilgan step'lar completed_step_ids bo'yicha
          o'tkazib yuboriladi
        Qaytadi: run() natijasi yoki checkpoint topilmasa None.
        """
        cp = self.load_checkpoint(task_id)
        if cp is None:
            return None
        try:
            if _PHASE1_OK:
                goal = Goal.from_dict(cp["goal"])
                objective = Objective.from_dict(cp["objective"]) if cp.get("objective") else None
                self.goal_context = GoalContext(goal, objective)
            cp_task = str(cp.get("task") or "")
            cp_skip = set(int(i) for i in (cp.get("completed_step_ids") or []))
            # R2 (§22/§23): RECONCILIATION — checkpoint'dagi completed step'lar
            # fs holati bilan solishtiriladi. Fayl HAZIR -> skip (duplicate'siz);
            # fayl YO'QOLGAN (tashqi o'zgarish) -> step REDO (qayta bajariladi).
            # Fail-safe: reconciliation xatosida checkpoint skip o'zgarmaydi.
            recon_report: dict = {"reconciled": False}
            if cp.get("status") != "ok":  # ok'da checkpoint allaqachon cleared
                try:
                    from executor.checkpoint_integrity import is_stale, reconcile_steps
                    self._cp_stale = is_stale(cp, self.workspace.root)
                    raw_steps = cp.get("plan_steps") or []
                    if raw_steps:
                        recon = reconcile_steps(raw_steps, cp_skip,
                                                self.workspace.root, cp_task)
                    else:
                        # Eski checkpoint'da plan_steps yo'q — resume jarayonida
                        # reja kelgach reconcile qilinadi (_apply_reconciliation).
                        recon = None
                    if recon is not None:
                        from executor.checkpoint_integrity import merge_skip_with_reconciliation
                        cp_skip, recon_report = merge_skip_with_reconciliation(cp_skip, recon)
                except Exception:
                    recon_report = {"reconciled": False}
            self._cp_recon_report = recon_report
            # R1 (§2/§17): checkpoint'da saqlangan requirement snapshot TIKLANADI —
            # resume bir xil requirement'lar bilan tekshiriladi (immutable kafolat).
            req_json = cp.get("requirements")
            if _RMX_OK and req_json:
                try:
                    self._req_snapshot = _rmx.RequirementSnapshot.from_json(req_json)
                except Exception:
                    pass
            self._cp_skip_steps = cp_skip
            res = self.run(cp_task)
            self._cp_skip_steps = set()
            if isinstance(res, dict):
                res["reconciliation"] = getattr(self, "_cp_recon_report",
                                                 {"reconciled": False})
                if getattr(self, "_cp_stale", False):
                    res["checkpoint_stale"] = True
            return res
        except Exception:
            self._cp_skip_steps = set()
            return None

    # ------------------------------------------------------------ #
    # State machine helper (Phase 1) — fail-safe SM o'tishlari
    # ------------------------------------------------------------ #

    def _sm_transition(self, to_state, ctx: Optional[dict] = None,
                       trigger: str = "", critical: bool = False) -> None:
        """SM o'tish — fail-safe: SM yo'q bo'lsa executor oqimi BUZILMAYDI.

        critical=True (masalan PLAN -> EXECUTE guard'i) — guard rad etsa
        StateTransitionError qayta ko'tariladi: noto'g'ri reja bajarilmaydi.
        Qolgan hollarda rad etilgan o'tish logga yoziladi va davom etiladi
        (keng qamrovli integratsiya Phase 2'da tugallanadi).
        """
        if self.sm is None:
            return
        try:
            self.sm.transition(to_state, ctx or {}, trigger=trigger)
        except StateTransitionError as exc:
            if critical:
                raise
            try:
                self._progress("state", f"SM: {exc}")
            except Exception:
                pass

    # ------------------------------------------------------------ #
    # Main entry
    # ------------------------------------------------------------ #

    def run(self, task: str, requirements=None, goal_context=None) -> dict:
        t0 = time.perf_counter()

        # §17 Resource Control — monitoring boshlash
        _rc = None
        try:
            from monitor.resource_monitor import ResourceControl, ResourceLimits, get_resources
            _rc = ResourceControl(ResourceLimits(max_ram_mb=512, max_cpu_s=30, max_disk_mb=100))
            _rc._snap = get_resources()
        except Exception:
            _rc = None

        # Phase 1 (§2/§12): GOAL PRESERVATION — goal_context berilmagan bo'lsa
        # task matnidan yaratiladi (immutable Goal). Re-plan paytida goal
        # hech qachon o'zgarmaydi; natijaga goal_id qo'shiladi (tracing).
        if goal_context is not None:
            self.goal_context = goal_context
        elif self.goal_context is None or self.goal_context.goal.text != task:
            if _PHASE1_OK:
                try:
                    # §12 goal restore: checkpoint'da shu task bo'lsa — disk'dagi
                    # goal tiklanadi (goal_id stabil). Yo'q bo'lsa — yangi.
                    if not self._restore_checkpoint_for_task(task):
                        self.goal_context = GoalContext(Goal.create(task))
                except Exception:
                    self.goal_context = None
        # Phase 1 (§1): formal state machine — har run uchun yangi nusxa.
        if _PHASE1_OK:
            try:
                self.sm = StateMachine(task_id=(self.goal_context.goal.id if self.goal_context else ""),
                                       max_iter=max(self.max_iter, 50),
                                       max_retries=max(self.max_retries, 2))
            except Exception:
                self.sm = None
        else:
            self.sm = None
        # Phase 2 (§4/§10): world state + verification log — har run uchun yangi.
        if _PHASE2_OK:
            self.world = AgentWorldState()
            self.vlog = VerificationLog()
        else:
            self.world = None
            self.vlog = None
        # Roadmap v3 R1 (§2): requirement snapshot — run BOSHIDA, immutable.
        self._req_snapshot = None
        if _RMX_OK and self.enable_requirement_matrix:
            try:
                self._req_snapshot = _rmx.RequirementSnapshot(
                    task, _rmx.extract_requirements(task))
            except Exception:
                self._req_snapshot = None

        # SM: INPUT -> UNDERSTAND (input executor'ga keldi va task bo'sh emas)
        self._sm_transition(AgentState.UNDERSTAND if _PHASE1_OK else AgentState.PLAN,
                            {"input_validated": bool(task and task.strip())})
        # Part L: Requirement modeli — reja va sifat eshigi shunga moslashadi.
        if requirements is None:
            requirements = self._extract_req(task)
        # SM: UNDERSTAND -> PLAN (requirement modeli tayyor — offline'da None ham OK)
        self._sm_transition(AgentState.PLAN, {"requirements_ready": True})
        plan = self.planner.plan(task, requirements)
        self._progress("plan", "reja tuzildi — bajarish boshlandi")

        steps: list[dict] = []
        tool_calls: list[dict] = []
        corrections = 0
        total_tools = 0
        status = "ok"
        replans = 0
        # Phase 3 (§8): checkpoint tracking (init bo'lsa ham xavfsiz)
        self._cp_tool_calls = tool_calls
        self._cp_skip_steps = getattr(self, "_cp_skip_steps", set())
        _cp_done: list[int] = list(self._cp_skip_steps)

        if self.hooks is not None:
            self.hooks.fire("on_plan", {"task": task, "plan": plan})
        # SM: PLAN -> EXECUTE — plan tool nomlari registry/MCP'da mavjudligi
        # DETERMINISTIK tekshiriladi (guard: g_plan_valid). Noma'lum tool bo'lsa
        # — StateTransitionError: noto'g'ri reja bajarilishga urinmaydi.
        allowed = set(self.registry.names())
        if self.mcp is not None:
            try:
                allowed |= set(self.mcp.names() or [])
            except Exception:
                pass
        plan_steps = plan.get("steps", [])[: self.max_iter]
        ok_plan, plan_msg = validate_plan_tools(plan_steps, sorted(allowed))
        self._sm_transition(AgentState.EXECUTE, {"plan_steps": plan_steps,
                                                 "allowed_tools": sorted(allowed)},
                            trigger=plan_msg or "plan validated")
        i = 0
        while i < len(plan_steps):
            step = plan_steps[i]
            i += 1
            # Phase 3 (§8): resume — allaqachon bajarilgan step'ni O'TKAZIB YUBOR
            # (checkpoint'dan qaytishda qayta bajarish yo'q).
            if int(step.get("id", i)) in self._cp_skip_steps:
                continue
            # Phase 4 (§15): cancellation — signal kelgan bo'lsa to'xtash.
            # Checkpoint SAQLANADI (status != ok) — keyinroq resume mumkin.
            if self._check_cancelled():
                status = "cancelled"
                self._log_recovery("cancelled", "cancel signal received (planned loop)")
                self._progress("review", "run bekor qilindi (cancel)")
                break
            if self.hooks is not None:
                self.hooks.fire("on_step_start", {"task": task, "step": step, "plan": plan})
            # Phase 5 (§13): "step N of M" progress formati — UI real o'rinni ko'rsatadi.
            self._progress("execute", f"step {i}/{len(plan_steps)}: {step.get('title', '')}")
            step_result = self._execute_step(step, tool_calls, task)
            total_tools += step_result["tool_count"]
            corrections += step_result["corrections"]
            steps.append({
                "id": step["id"],
                "title": step["title"],
                "tools": step.get("tools", []),
                "status": step_result["status"],
                "result": step_result["result"],
            })
            if self.hooks is not None:
                self.hooks.fire("on_step_done", {"task": task, "step": step,
                                                  "result": step_result})
            # Phase 4 (§15): step ichida cancel bo'lsa — darhol to'xtash.
            if step_result["status"] == "cancelled":
                status = "cancelled"
                self._log_recovery("cancelled", "cancel signal received (mid-step)")
                break
            # Phase 3 (§8/§12): har step'dan keyin checkpoint (atomik) —
            # crash/resume'da goal + progress tiklanadi.
            if step_result["status"] == "done":
                _cp_done.append(int(step.get("id", i)))
            # R2 (§22): plan_steps ham saqlanadi — resume reconciliation fs
            # solishtiruvi uchun (fayl nomlari step title/tools'dan chiqariladi).
            self._save_checkpoint(task, _cp_done, step_result["status"],
                                  plan_steps=plan_steps)
            # Phase 2 (§4): tool natijalari AgentWorldState'ga o'tadi
            # (confirmed/assumed flag bilan — real Observation→State konversiyasi).
            if self.world is not None:
                for tc in tool_calls[-step_result["tool_count"]:]:
                    self.world.add_from_record(tc)
            # SM: EXECUTE -> OBSERVE (tool natijalari yig'ildi)
            self._sm_transition(AgentState.OBSERVE,
                                {"tool_result": {"tool_count": step_result["tool_count"]}})
            # SM: OBSERVE -> VERIFY — flag endi WORLD STATE'DAN keladi
            # (real confirmed/assumed; §4 konversiya natijasi).
            obs_flags = self.world.observation_flags() if self.world is not None else (
                ["confirmed"] if step_result["status"] != "error" else ["assumed"])
            self._sm_transition(AgentState.VERIFY,
                                {"observation_flags": obs_flags or ["assumed"]})
            # SM: VERIFY -> UPDATE_STATE (quality gate'dan oldingi holat)
            self._sm_transition(AgentState.UPDATE_STATE,
                                {"verify_status": "VERIFIED" if step_result["status"] != "error" else "UNKNOWN"})
            # SM: UPDATE_STATE -> CONTINUE (yana qadam bor) -> PLAN -> EXECUTE
            # (keyingi iteratsiya; oxirgi qadamda CONTINUE guard rad etadi —
            #  fail-safe, yakuniy holat pastda alohida belgilanadi).
            if i < len(plan_steps) and total_tools < self.max_tool_calls:
                self._sm_transition(AgentState.CONTINUE,
                                    {"remaining_steps": len(plan_steps) - i + 1})
                self._sm_transition(AgentState.PLAN, {"requirements_ready": True})
                self._sm_transition(AgentState.EXECUTE,
                                    {"plan_steps": [plan_steps[i]] if i < len(plan_steps) else [],
                                     "allowed_tools": sorted(allowed)},
                                    trigger="next step")
            if step_result["status"] == "error":
                status = "partial"
                # Part L (L7): qotib qolgan "abort + canned summary" o'rniga —
                # LLM'dan tuzatilgan KEYINGI qadamlar (maks 2 re-plan).
                if replans < 2 and self.llm is not None:
                    revised = self._replan(task, step, step_result,
                                           plan_steps[i:], requirements)
                    if revised:
                        replans += 1
                        self._log_recovery("replan", f"step {step.get('id')} → {len(revised)} yangi qadam")
                        plan_steps = plan_steps[:i] + revised
                elif replans >= 2:
                    break  # re-plan limiti — qolgan qadamlar bajarilmaydi
            if total_tools >= self.max_tool_calls:
                status = "stopped"
                break

        # ---------- Sifat eshigi (quality gate) ----------
        # "Bajardim" degani yetarli emas: vazifa yozma natija talab qilsa, fayl
        # haqiqatan vazifani bajaryaptimi tekshiramiz (bo'sh, shablon yoki yo'q
        # bo'lsa — tuzatuvchi pass). Brauzer xulosalari (browser_get_text) uchun
        # fayl shart emas — yakuniy javobning o'zi natija.
        quality_note = ""
        # SM: UPDATE_STATE -> COMPLETE/FAIL — YAKUNIY holat DETERMINISTIK guard'dan
        # o'tadi: COMPLETE faqat VERIFIED bilan (LLM da'vosiga ishonch yo'q — §17).
        # Phase 4 (§15): cancelled — user to'xtatdi (FAILED emas, checkpoint saqlanadi).
        # R1.2: matrix formal statusi ham guard ctx'ida beriladi (bir manba kafolati).
        final_verify = ("VERIFIED" if status == "ok"
                        else ("UNKNOWN" if status in ("partial", "cancelled") else "FAILED"))
        _rm_early = self._build_requirement_matrix(status)
        _completion_ctx = (_rm_early or {}).get("completion") if _RMX_OK else None
        if final_verify == "VERIFIED" and quality_note == "" and (
                self._task_asks_output(task) or self._req_asks_output(task, requirements)):
            # yozma natija talab qilinadi — COMPLETE guard'i delivery tekshiruvisiz
            # o'tmaydi: avval quality gate, keyin holat.
            pass
        self._sm_transition(
            AgentState.COMPLETE if final_verify == "VERIFIED" else (
                AgentState.FAIL if final_verify == "FAILED" else AgentState.UPDATE_STATE),
            {"verify_status": final_verify,
             "remaining_steps": 0,
             "completion": _completion_ctx,
             "retry_limit_reached": status == "stopped",
             "fatal_error": False},
            trigger=f"executor status={status}")
        if status != "stopped" and (self._task_asks_output(task)
                                    or self._req_asks_output(task, requirements)) \
                and not self._browser_summary_done(task, tool_calls):
            ok_del, note = self._verify_deliverable(task, tool_calls)
            # Phase 2 (§10): verification EVIDENCE — expected vs actual yoziladi.
            if self.vlog is not None:
                requested = self._requested_files(task)
                written = sorted((self.world.files_touched or {}).keys()) \
                    if self.world is not None else []
                self.vlog.add(VerificationRecord.make(
                    action_id=self.goal_context.goal.id if self.goal_context else task[:40],
                    method="deliverable",
                    ok=ok_del if ok_del else None if (note and "talab" in note) else ok_del,
                    expected={"files": requested},
                    actual={"files_written": written[:8]},
                    note=note or "deliverable verified"))
            if not ok_del:
                status = "partial"
                quality_note = note or (
                    "task yozma natija talab qilardi, lekin fayl bo'sh/yo'q/shablon — "
                    "agent talab darajasida bajarmadi"
                )

        # Roadmap v3 R4 (§13–§16): DOMAIN VERIFIERS — yozilgan artefaktlar
        # domayn tekshiruvchilaridan o'tadi (kod run+stdout, hujjat tuzilishi,
        # manba evidence, manifest). Fail-safe: xato run'ni buzmaydi.
        # ok=False bo'lsa executor statusi "ok"→"partial" pasayadi (§29 golden
        # rule: tool ok=true'ga ishonib bo'lmaydi — artefakt o'zi tekshiriladi).
        if self.vlog is not None and status not in ("cancelled",):
            try:
                from verification.domain_verifiers import run_domain_verifiers
                written_for_dv = sorted(set(
                    [(tc.get("args") or {}).get("path") for tc in tool_calls
                     if tc.get("tool") in ("write_file", "apply_patch")
                     and isinstance((tc.get("args") or {}).get("path"), str)]))
                if written_for_dv:
                    dv_results = run_domain_verifiers(
                        self.workspace.root, task, written_for_dv)
                    for dvr in dv_results:
                        self.vlog.add(VerificationRecord.make(
                            action_id=self.goal_context.goal.id
                            if self.goal_context else task[:40],
                            method=f"domain:{dvr.get('domain', '?')}",
                            ok=dvr.get("ok"),
                            expected={"target": dvr.get("target"),
                                      "method": dvr.get("method")},
                            actual={"target": dvr.get("target")},
                            note=dvr.get("note", "")))
                    result_dv = {"checked": len(dv_results),
                                 "failed": sum(1 for r in dv_results
                                               if r.get("ok") is False)}
                    if result_dv["failed"] and status == "ok":
                        status = "partial"
                        quality_note = quality_note or (
                            "domain verifier failed: "
                            + "; ".join(r.get("note", "")[:60]
                                        for r in dv_results if r.get("ok") is False)[:200])
            except Exception:
                pass  # fail-safe

        result = {
            "task": task,
            "status": status,
            "engine": "planned",
            "plan": plan,
            "steps": steps,
            "tool_calls": tool_calls,
            "final": quality_note or "",
            "quality_note": quality_note,
            "stats": {
                "steps": len(steps),
                "tool_calls": total_tools,
                "corrections": corrections,
                "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            },
            "workspace_root": self.workspace.root,
        }
        # Roadmap v3 R1 (§17/§28): requirement matrix — evidence bilan formal status.
        _rm_report = self._build_requirement_matrix(status)
        if _rm_report is not None:
            result["requirement_matrix"] = _rm_report["matrix"]
            result["completion"] = _rm_report["completion"]
            if _rm_report["executor_status"] != status:
                result["status"] = status = _rm_report["executor_status"]

        # Roadmap v4 B3 (§10): EXPECTED vs ACTUAL comparison — task'dan
        # deterministik expected mapping + real fs/stdout bilan solishtirish.
        try:
            from verification.verification_comparison import (map_expected_from_task,
                                                 compare_all)
            _exp_list = map_expected_from_task(task)
            if _exp_list:
                _files_actual: dict = {}
                for _tc in tool_calls:
                    if _tc.get("tool") in ("write_file", "apply_patch"):
                        _p = (_tc.get("args") or {}).get("path")
                        if isinstance(_p, str) and _p:
                            try:
                                _r = self.workspace.read(_p)
                                _files_actual[_p] = str(_r.get("content") or "")
                            except Exception:
                                _files_actual[_p] = ""
                _stdout_actual = " ".join(
                    str(tc.get("output_preview") or tc.get("detail") or "")
                    for tc in tool_calls
                    if tc.get("tool") == "python_exec")
                _ran_python = any(tc.get("tool") == "python_exec"
                                  for tc in tool_calls)
                if not _ran_python:
                    # stdout expected'lar hali tekshirilmaydi (skript
                    # ishga tushirilmagan) — faqat fayl expected'lari.
                    _exp_list = [e for e in _exp_list
                                 if not e.kind.startswith("stdout_")]
                _cmp = compare_all(_exp_list or [], {
                    "root": self.workspace.root,
                    "files": _files_actual,
                    "stdout": _stdout_actual,
                })
                if not _exp_list:
                    result["expected_comparison"] = {
                        "all_match": True, "score": 1.0,
                        "comparisons": [], "note": "stdout not applicable"}
                else:
                    result["expected_comparison"] = _cmp
                    if not _cmp["all_match"] and status == "ok":
                        status = "partial"
                        result["status"] = "partial"
                        quality_note = quality_note or (
                            "expected comparison failed: "
                            + "; ".join(c["diff"] for c in _cmp["comparisons"]
                                        if not c["match"])[:200])
        except Exception:
            pass  # fail-safe: comparison xatosi run'ni buzmaydi

        # Phase 1 tracing: goal_id + SM history (§16 observability)
        if self.goal_context is not None:
            result["goal_id"] = self.goal_context.goal.id
            result["goal_text"] = self.goal_context.goal.text
        if self.sm is not None:
            result["sm_final_state"] = self.sm.state.value
            result["sm_history_len"] = len(self.sm.history())
        # Phase 2 tracing (§4/§10): world state stats + verification evidence
        if self.world is not None:
            result["world_stats"] = self.world.stats()
            result["confirmed_facts"] = self.world.confirmed_facts(limit=10)
        if self.vlog is not None:
            result["verifications"] = self.vlog.to_list()
        # Phase 4 (§16): structured error/recovery loglar — ikkala loop uchun ham.
        if self._error_log:
            result["errors"] = self._error_log
        if self._recovery_log:
            result["recovery_events"] = self._recovery_log
        # Roadmap v2 B3 (§16): planned loop decision bloki — LLM qarorining
        # rasmiy ko'rinishi (reasoning/confidence/intent) + reja guard natijasi.
        result["decision"] = {
            "engine": plan.get("engine", ""),
            "reasoning": plan.get("reasoning", ""),
            "confidence": plan.get("confidence"),
            "intent": plan.get("intent", ""),
            "plan_validated": bool(plan_msg == "" or plan_msg),
            "steps_total": len(plan_steps),
        }
        if status == "cancelled":
            result["cancelled"] = True
        # Phase 3 (§8/§12): muvaffaqiyatli yakun — checkpoint O'CHIRILADI;
        # partial/stopped/cancelled — checkpoint SAQLANADI (resume mumkin).
        if self.goal_context is not None:
            if status == "ok":
                self.clear_checkpoint(self.goal_context.goal.id)
                result["checkpoint"] = "cleared"
            elif self.checkpoint_dir:
                result["checkpoint"] = "kept"
        # Phase 4 (§16): structured error/recovery loglar — natija record'ida.
        if self._error_log:
            result["errors"] = self._error_log
        if self._recovery_log:
            result["recovery_events"] = self._recovery_log
        if status == "cancelled":
            result["cancelled"] = True
            if getattr(self, "_cp_skip_steps", None):
                result["resumed_from_checkpoint"] = True
                result["skipped_steps"] = sorted(self._cp_skip_steps)

        # Roadmap v2 B1 (§13): verified-only speech — final xulosa da'volari
        # dalillar bilan solishtiriladi (tool_calls + workspace).
        try:
            result["final"] = self._apply_claim_check(
                result.get("final", ""), task, tool_calls, result, status)
        except Exception:
            result["final_claims_checked"] = False  # fail-safe: hech qachon yiqilmaydi

        # Roadmap v2 C2 (§16): birlashgan chronological timeline.
        try:
            result["timeline"] = self._build_timeline(tool_calls)
        except Exception:
            pass  # timeline observability — run'ni buzmaydi

        if self.hooks is not None:
            self.hooks.fire("on_task_done", {"task": task, "result": result})
        self._remember(task, result)

        # §17 Resource Control — resurs ishlatilishini qo'shish
        if _rc is not None:
            try:
                from monitor.resource_monitor import get_resources
                final_snap = get_resources()
                result["resource_usage"] = final_snap.to_dict()
                violations = _rc.check(final_snap)
                if violations:
                    result["resource_violations"] = [v.message for v in violations]
            except Exception:
                pass

        return result

    # ------------------------------------------------------------ #
    # Native tool-calling loop (LLM picks tools itself — schema-based)
    # ------------------------------------------------------------ #

    def run_native(self, task: str, system: Optional[str] = None) -> dict:
        """Model tool'larni o'zi tanlaydi (Ollama tools API).

        Loop:
          1. messages: system + task (va RAG konteksti)
          2. model javob: tool_calls -> bajariladi -> natija tool-message sifatida
          3. model javob: content (final) -> tugaydi

        Agent kengaytmalari:
          - `use_skill(name)`  — qobiliyat yetishmasa skill ko'rsatmasini yuklaydi
          - `mcp_call(tool, args)` — MCP server vositalarini chaqiradi
          - `request_human(question)` — HITL: insondan yordam/ma'lumot so'raydi

        Capability-gap detection: model "qila olmayman" desa (masalan "rasm
        chiza olmayman") — avtomatik re-prompt: skills va MCP vositalari
        eslatiladi; shunda ham iloj bo'lmasa `request_human` taklif qilinadi.

        Model `tools` qobiliyatiga ega bo'lmasa yoki transport xato bo'lsa
        — odatiy `run()` ga qaytadi (fallback).
        """
        # Part L: talab modeli — system + xulosa + sifat eshigi shunga moslashadi.
        requirements = self._extract_req(task)
        if self.llm is None:
            return self.run(task)
        t0 = time.perf_counter()
        # Phase 1 (§1/§2): SM + goal preservation — native yo'lda ham.
        if _PHASE1_OK:
            try:
                self.goal_context = GoalContext(Goal.create(task))
                self.sm = StateMachine(task_id=self.goal_context.goal.id,
                                       max_iter=max(self.max_iter, 50),
                                       max_retries=max(self.max_retries, 2))
                self._sm_transition(AgentState.UNDERSTAND, {"input_validated": True})
                self._sm_transition(AgentState.PLAN, {"requirements_ready": True})
                self._sm_transition(AgentState.EXECUTE,
                                    {"plan_steps": [{"id": 1, "tools": []}],
                                     "allowed_tools": sorted(self.registry.names())},
                                    trigger="native loop (model tool tanlaydi)")
            except Exception:
                self.goal_context = None
                self.sm = None
        # GOAL PIN (§12): original goal har prompt'da saqlanadi — context
        # o'sib ketganda yoki summarization bo'lganda ham goal yo'qolmaydi.
        goal_pin = self.goal_context.prompt_pin() if self.goal_context else ""
        # Phase 2 (§4/§10): world state + verification log — native yo'lda ham.
        if _PHASE2_OK:
            self.world = AgentWorldState()
            self.vlog = VerificationLog()
        else:
            self.world = None
            self.vlog = None
        # Roadmap v3 R1 (§2): requirement snapshot — run BOSHIDA, immutable.
        self._req_snapshot = None
        if _RMX_OK and self.enable_requirement_matrix:
            try:
                self._req_snapshot = _rmx.RequirementSnapshot(
                    task, _rmx.extract_requirements(task))
            except Exception:
                self._req_snapshot = None
        self._progress("plan", "task tahlil qilinmoqda…")
        tool_calls: list[dict] = []
        failed_tools = 0
        plan_text = ""
        _tool_sigs: list[str] = []      # §9: aylanma aniqlash uchun signature'lar
        _write_count = 0                # §9: stuck detection (yozma ish hisobi)
        sys_text = system or (
            "You are Igris, a coding agent working in a sandboxed workspace. "
            "Use the available tools to inspect, create, edit and run files. "
            "Think step by step. When the task is complete, answer with a short "
            "summary of what you did. Paths are relative to the workspace root."
            "\n\nIMPORTANT: You have extra capabilities beyond plain file tools:"
            "\n- `use_skill(name)` — loads a skill (step-by-step instructions) that"
            " lets you do things you cannot do with raw tools, e.g. drawing images"
            " with Pillow, SVG generation, etc. When a request needs a capability"
            " you lack (like creating an image/picture), DO NOT give up — call"
            " use_skill to load the relevant skill instructions first."
            "\n- `mcp_call(tool, args)` — calls tools on connected MCP servers"
            " (server__tool name, e.g. art__draw_object_png)."
            "\n- `request_human(question)` — if you are truly stuck after trying"
            " skills and MCP tools, ask the human operator for input."
        )
        if self.plan_first:
            sys_text += PLAN_FIRST_SYSTEM
        sys_text += (
            "\n\nBROWSER TASKS (URLs / web pages / 'browser' / 'open the page'):\n"
            "The web_ai_bridge MCP tools drive a REAL Chrome browser through the "
            "user's own authorized profile — you browse exactly like the user. "
            "When a task involves a website, use them like a human would:\n"
            "1) web_ai_bridge__browser_navigate {\"url\": \"<full URL>\"} to open the page.\n"
            "2) web_ai_bridge__browser_get_text {} to read the page's visible text.\n"
            "3) Interact further only if the task needs it: browser_click, "
            "browser_type, browser_wait_for, browser_screenshot, etc.\n"
            "4) The final answer summarizing/analyzing the page IS the deliverable "
            "— no file needs to be created for a browse-and-summarize task.\n"
            "Call the tools directly by name (e.g. web_ai_bridge__browser_navigate) "
            "or through mcp_call(\"web_ai_bridge__browser_navigate\", {...})."
        )
        if self.skills is not None:
            sys_text += (
                "\n\nAvailable skills (call use_skill to load one):\n"
                + self.skills.describe_all()
            )
        messages: list[dict] = [
            {"role": "system", "content": sys_text},
            {"role": "user", "content": task},
        ]

        # RAG kontekst (xotiradan)
        if self.memory is not None and self.memory.enabled:
            ctx, hits = self.memory.recall(task, top_k=3, max_chars=1200)
            if ctx:
                messages[0]["content"] += (
                    "\n\nRelevant recalled knowledge (use only if useful):\n" + ctx
                )
        # SEMANTIK TALAB (Part L): model javobni talabga mos shakllantiradi.
        if requirements is not None:
            messages[0]["content"] += "\n\n" + _req_block(requirements)
        # GOAL PIN (§12): ORIGINAL GOAL — context o'ssa ham yo'qolmaydi.
        if goal_pin:
            messages[0]["content"] += "\n\n" + goal_pin

        schemas = self.registry.ollama_schemas() + self._agent_schemas()
        status = "ok"
        final_content = ""
        iterations = 0
        any_tool_executed = False
        any_failure = False
        gap_reprompted = 0
        human_asked = False
        seen_calls: set[tuple] = set()
        # Roadmap v2 B3 (§16): LLM decision trace — har iteratsiyada model
        # qarorining izchil yozuvi (reasoning/thinking + tanlangan tool'lar).
        decision_trace: list[dict] = []
        # B2 (§9): per-iteration timeout — bir iteratsiya (LLM chaqiruvi +
        # tool'lar) SHU vaqtdan ko'p bo'lsa 'stopped' (default 120s).
        _iter_timeout = float(getattr(self, "per_iteration_timeout_s", 120.0))
        _iter_timeout_hit = False   # B2: timeout native'da sodir bo'ldimi

        while iterations < self.max_iter:
            iterations += 1
            _iter_t0 = time.perf_counter()
            _tools_done = False   # shu iteratsiyada kamida 1 tool bajarildimi (B2)
            # Phase 4 (§15): cancellation — signal bo'lsa native loop ham to'xtaydi.
            if self._check_cancelled():
                status = "cancelled"
                self._log_recovery("cancelled", "cancel signal received (native loop)")
                self._progress("review", "run bekor qilindi (cancel)")
                break
            if len(tool_calls) >= self.max_tool_calls:
                status = "stopped"
                break

            # Phase 2 (§9): aylanma/stuck detection — deterministik (LLM yo'q).
            # Phase 4 tuzatish: gap-reprompt iteratsiyalari (model bo'sh javob
            # qaytargani uchun qayta so'ralganlar) stuck hisobiga KIRMAYDI —
            # ular aylanma emas, model javobsizligi. Aks holda bo'sh javob
            # oqimi 6-iteratsiyada guardni erta ishga tushiradi.
            if _PHASE2_OK:
                _loop, _why = detect_loop(_tool_sigs)
                _stuck, _why2 = detect_stuck(_write_count, iterations - gap_reprompted)
                if _loop or _stuck:
                    status = "partial"
                    final_content = _why or _why2
                    self._progress("review", f"loop-guard: {final_content}")
                    break

            resp = self.llm.chat_with_tools(messages, tools=schemas)
            if not resp or not isinstance(resp, dict):
                # transport error → fallback to planned execution
                return self.run(task, requirements)

            # B3: har iteratsiya qarori trace'ga yoziladi (§16 LLM decision log).
            # B2 (§9): iteration_id (UUID, takrorlanmas) + action_reason
            # (qaror sababi — reasoning'dan; tool'siz final'da content'dan).
            _reason = str(resp.get("reasoning") or resp.get("thinking") or "")
            if not _reason:
                _reason = ("tool call: " + ", ".join(
                    str(c.get("name", "")) for c in (resp.get("tool_calls") or [])
                    if isinstance(c, dict))) if resp.get("tool_calls") else \
                    str(resp.get("content") or "")
            decision_trace.append({
                "iteration": iterations,
                "iteration_id": f"iter-{_uuid.uuid4().hex[:12]}",
                "action_reason": _reason.strip()[:200] or "no reasoning returned",
                "reasoning": str(resp.get("reasoning") or resp.get("thinking") or "")[:500],
                "tool_calls": [str(c.get("name", "")) for c in (resp.get("tool_calls") or [])
                               if isinstance(c, dict)][:8],
                "content_preview": str(resp.get("content") or "")[:200],
            })

            if resp.get("tool_calls"):
                progressed = False
                for call in resp["tool_calls"]:
                    name = call.get("name", "")
                    if not name:
                        continue  # bo'sh nom — model artefakti, o'tkazib yuboramiz
                    args = self._normalize_native_args(name, call.get("arguments", {}) or {})

                    # takroriy bir xil chaqiruvni bloklash (loop oldini olish)
                    key = (name, json_dumps_sorted(args))
                    if key in seen_calls:
                        messages.append({
                            "role": "tool",
                            "name": name,
                            "content": "That exact tool call was already made. Do something different.",
                        })
                        continue
                    seen_calls.add(key)
                    progressed = True
                    _tools_done = True

                    if name == "request_human" and human_asked:
                        # model allaqachon insondan so'ragan — javobni ishlatib
                        # davom etishi kerak, qayta so'rashi shart emas.
                        messages.append({
                            "role": "tool",
                            "name": name,
                            "content": (
                                "You already asked the human and the answer is in the "
                                "conversation above. Use that answer now and CONTINUE the "
                                "task — pick up your existing plan and keep executing "
                                "tools until it is complete."
                            ),
                        })
                        continue

                    out = self._execute_agent_tool(name, args)
                    record = {
                        "action_id": _action_id() if _PHASE2_OK else "",  # §3: unique action ID
                        "ts": round(time.time(), 3),  # C2: timeline uchun vaqt
                        "tool": name,
                        "args": args,
                        "result": {k: v for k, v in out.items() if k != "output"},
                        "output_preview": str(out.get("output") or out.get("content") or "")[:300],
                    }
                    # Phase 4 (§11): same-error detection — bir xil xato N marta
                    # bo'lsa modelga HITL escalation buyruqlari yuboriladi.
                    if not out.get("ok") and name != "request_human":
                        escalate = self._record_tool_error(name, out)
                        if escalate:
                            messages.append({
                                "role": "user",
                                "content": (
                                    f"The tool '{name}' failed with the SAME error "
                                    f"{self.escalate_after_same_errors} times: "
                                    f"{str(out.get('error') or '')[:200]}. Repeating it will not "
                                    "help. Either use a DIFFERENT tool/approach, or call "
                                    "request_human with a clear question for the operator."
                                ),
                            })
                            self._log_recovery("escalate_hitl", f"{name}: same error {self.escalate_after_same_errors}x")
                    # Phase 2 (§4): observation → world state (confirmed/assumed)
                    if self.world is not None:
                        self.world.add_from_record(record)
                    # Phase 2 (§9): signature yig'ish (aylanma aniqlash)
                    if _PHASE2_OK:
                        try:
                            _tool_sigs.append(f"{name}:{json_dumps_sorted(args)[:120]}")
                        except Exception:
                            _tool_sigs.append(name)
                    if name in ("write_file", "apply_patch"):
                        _write_count += 1
                    # Jonli progress — record ham yuboriladi (run tugamasdan UI'da ko'rsatiladi)
                    self._progress(stage_for_tool(name),
                                   f"{name} → {_tool_preview(name, args)}", record)
                    any_tool_executed = True
                    if name == "request_human":
                        human_asked = True
                    if self.hooks is not None:
                        self.hooks.fire("on_tool_call", {
                            "task": task, "tool": name, "args": args, "result": out,
                        })
                        if not out.get("ok"):
                            self.hooks.fire("on_error", {
                                "task": task, "tool": name, "error": out.get("error", ""),
                            })
                    tool_calls.append(record)
                    # tool natijasi modelga qaytariladi (tool message)
                    result_text = str(out.get("output") or out.get("content") or out.get("error") or "ok")
                    if name == "request_human" and out.get("ok"):
                        # Inson javobini user-message sifatida qaytaramiz — model
                        # buni ko'proq e'tiborga oladi va davom etadi.
                        messages.append({
                            "role": "user",
                            "content": f"Human operator answered your question: {result_text[:1500]}. Continue the task using that information.",
                        })
                    else:
                        messages.append({
                            "role": "tool",
                            "name": name,
                            "content": result_text[:4000],
                        })
                    if not out.get("ok"):
                        any_failure = True
                        failed_tools += 1
                if not progressed:
                    # hammasi takroriy edi — model tutilib qolgan. Soxta
                    # muvaffaqiyat yozish YO'Q: faqat read/keraksiz tool'lar
                    # bo'lsa (write/apply_patch/MCP natija tool'i yo'q) — partial.
                    # Ammo haqiqiy ish bajarilgan bo'lsa (write_file yoki
                    # muvaffaqiyatli MCP tool) — model shunchaki final xulosa
                    # bermayapti, buni "stopped" emas balki ok deb baholaymiz.
                    real_work = any(
                        c.get("tool") in ("write_file", "apply_patch", "python_exec", "run_command", "mcp_call", "use_skill")
                        for c in tool_calls
                    )
                    if any_failure or not real_work:
                        status = "partial"
                    # Shablon xulosa o'rniga — modeldan REAL xulosa so'raymiz.
                    # (reasoning: "Task appears complete" shabloni emas, haqiqiy
                    #  nima qilinganini izohlovchi matn qaytariladi.)
                    summary = self._ask_final_summary(messages, requirements)
                    final_content = (
                        summary
                        or "Task appears complete: the model repeated its last tool call "
                        "and was stopped."
                    )
                    break
                continue

            final_content = resp.get("content", "") or ""
            # Bo'sh javob + allaqachon tool'lar bo'lsa — model to'xtab qolgan;
            # re-prompt bilan davom ettirishga undaymiz (max 4 qayta urinish).
            if not final_content.strip() and any_tool_executed:
                if gap_reprompted < 4:
                    gap_reprompted += 1
                    messages.append({
                        "role": "user",
                        "content": (
                            "Your previous message was empty. Continue the task now — "
                            "use the available tools and finish the job. Reply with your "
                            "final summary when done."
                        ),
                    })
                    continue
                # 4 marta re-prompt'dan keyin ham model bo'sh javob qaytarmoqda —
                # lekin tool'lar muvaffaqiyatli bajarilgan bo'lsa, vazifa
                # yakunlangan deb hisoblaymiz (noto'g'ri "stopped" oldini olish).
                if not any_failure:
                    status = "ok"
                    final_content = (
                        f"Task complete: {len(tool_calls)} tool call(s) executed "
                        f"successfully. The model stopped without a final summary "
                        f"(after {gap_reprompted + 1} empty responses)."
                    )
                else:
                    status = "partial"
                    final_content = (
                        "Task partial: some tool calls failed and the model stopped "
                        "without a final summary."
                    )
                break
            # B2 (§9): per-iteration timeout — iteratsiya belgilangan vaqtdan
            # oshsa (sekin LLM yoki murakkab tool'lar) toza to'xtaymiz.
            _iter_dt = time.perf_counter() - _iter_t0
            if _iter_timeout and _iter_dt > _iter_timeout and not _tools_done:
                status = "stopped"
                _iter_timeout_hit = True
                final_content = (
                    f"Stopped: iteration {iterations} exceeded "
                    f"{_iter_timeout}s limit (per-iteration timeout).")
                self._log_recovery(
                    "iteration_timeout",
                    f"iteration {iterations} took {_iter_dt:.1f}s "
                    f"> {_iter_timeout}s limit")
                self._progress("review", f"iteration timeout ({_iter_dt:.1f}s)")
                break
            # Capability-gap: model "qila olmayman" desa — skills/MCP eslatamiz
            if not any_tool_executed and gap_reprompted == 0 \
                    and CAPABILITY_GAP_PATTERNS.search(final_content):
                gap_reprompted = 1
                messages.append({
                    "role": "user",
                    "content": (
                        "You said you cannot do this. Do NOT give up — you have extra "
                        "capabilities:\n"
                        + (self.skills.describe_all() if self.skills else "(no skills)")
                        + "\n"
                        + (self.mcp.describe_all() if self.mcp else "(no MCP tools)")
                        + "\n\nLoad a relevant skill with use_skill, or call an MCP tool "
                        "with mcp_call to accomplish the task. If you genuinely need the "
                        "human's help, call request_human with a clear question."
                    ),
                })
                continue
            # Reja-uskash: hali hech qanday tool bajarilmagan paytdagi birinchi
            # matn — model rejasi. Uni saqlaymiz va modelni rejani bajarishga
            # undaymiz (loop'ni TUGATMAYMIZ — reja yakuniy javob emas!).
            if not any_tool_executed and not plan_text and final_content.strip():
                plan_text = final_content.strip()[:300]
                self._progress("plan", f"reja: {plan_text[:70]}")
                messages.append({
                    "role": "user",
                    "content": (
                        "Plan noted. Now EXECUTE the plan using the available tools — "
                        "make the tool calls you planned, then finish with a short summary."
                    ),
                })
                continue
            break

        # Model hech qanday tool chaqirmadi (native tool-calling'ni qo'llamaydi)
        # — planned execution (run) ga o'tamiz: `_ask_tool_args` prompt-asosida ishlaydi.
        if not any_tool_executed and not _iter_timeout_hit:
            return self.run(task, requirements)

        if not final_content:
            # max_iter tugadi yoki per-iteration timeout — model hali ham
            # ishlayotgan edi. Timeout'da 'stopped' saqlanadi (§9 semantikasi).
            status = "stopped" if status == "ok" else status
            # Bajarilgan ish bo'lsa — shablon emas, REAL xulosa bilan yopamiz
            summary = self._ask_final_summary(messages, requirements) if tool_calls else ""
            final_content = summary or "Stopped: iteration limit reached."

        # ---------- Sifat eshigi (quality gate) ----------
        # Brauzer xulosasi (browser_get_text natijasi) fayl talab qilmaydi.
        if (self._task_asks_output(task) or self._req_asks_output(task, requirements)) \
            and not self._browser_summary_done(task, tool_calls):
            ok_del, note = self._verify_deliverable(task, tool_calls)
            if not ok_del:
                status = "partial"
                final_content = (
                    (final_content or "").strip()
                    or (note or "task yozma natija talab qilardi, lekin fayl "
                        "bo'sh/yo'q/shablon - agent talab darajasida bajarmadi")
                )

        # SM: yakuniy holat — deterministik guard orqali (§17: COMPLETE faqat
        # VERIFIED bilan; LLM final matniga ishonch emas, real natijaga tayanadi).
        # Phase 4 (§15): cancelled — UNKNOWN (user to'xtatdi, FAILED emas).
        # R1.2: matrix formal statusi ham guard ctx'ida beriladi (bir manba kafolati).
        final_verify = ("VERIFIED" if status == "ok"
                        else ("UNKNOWN" if status in ("partial", "cancelled") else "FAILED"))
        _rm_early = self._build_requirement_matrix(status)
        _completion_ctx = (_rm_early or {}).get("completion") if _RMX_OK else None
        self._sm_transition(
            AgentState.COMPLETE if final_verify == "VERIFIED" else (
                AgentState.FAIL if final_verify == "FAILED" else AgentState.UPDATE_STATE),
            {"verify_status": final_verify,
             "remaining_steps": 0,
             "completion": _completion_ctx,
             "retry_limit_reached": status == "stopped",
             "fatal_error": False},
            trigger=f"native status={status}")

        result = {
            "task": task,
            "status": status,
            "engine": "tool-calling",
            "steps": [],
            "plan": {
                "goal": task,
                "steps": [{"id": 1, "title": plan_text, "tools": [], "detail": ""}] if plan_text else [],
                "engine": "tool-calling",
            },
            "tool_calls": tool_calls,
            "final": final_content,
            "human_asked": human_asked,
            "stats": {
                "steps": iterations,
                "tool_calls": len(tool_calls),
                "corrections": 0,
                "failures": failed_tools,
                "gap_reprompted": gap_reprompted,
                "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            },
            "workspace_root": self.workspace.root,
        }
        # Roadmap v3 R1 (§17/§28): requirement matrix — evidence bilan formal status.
        _rm_report = self._build_requirement_matrix(status)
        if _rm_report is not None:
            result["requirement_matrix"] = _rm_report["matrix"]
            result["completion"] = _rm_report["completion"]
            if _rm_report["executor_status"] != status:
                result["status"] = status = _rm_report["executor_status"]

        # Roadmap v4 B3 (§10): EXPECTED vs ACTUAL comparison — task'dan
        # deterministik expected mapping + real fs/stdout bilan solishtirish.
        try:
            from verification.verification_comparison import (map_expected_from_task,
                                                 compare_all)
            _exp_list = map_expected_from_task(task)
            if _exp_list:
                _files_actual: dict = {}
                for _tc in tool_calls:
                    if _tc.get("tool") in ("write_file", "apply_patch"):
                        _p = (_tc.get("args") or {}).get("path")
                        if isinstance(_p, str) and _p:
                            try:
                                _r = self.workspace.read(_p)
                                _files_actual[_p] = str(_r.get("content") or "")
                            except Exception:
                                _files_actual[_p] = ""
                _stdout_actual = " ".join(
                    str(tc.get("output_preview") or tc.get("detail") or "")
                    for tc in tool_calls
                    if tc.get("tool") == "python_exec")
                _ran_python = any(tc.get("tool") == "python_exec"
                                  for tc in tool_calls)
                if not _ran_python:
                    # stdout expected'lar hali tekshirilmaydi (skript
                    # ishga tushirilmagan) — faqat fayl expected'lari.
                    _exp_list = [e for e in _exp_list
                                 if not e.kind.startswith("stdout_")]
                _cmp = compare_all(_exp_list or [], {
                    "root": self.workspace.root,
                    "files": _files_actual,
                    "stdout": _stdout_actual,
                })
                if not _exp_list:
                    result["expected_comparison"] = {
                        "all_match": True, "score": 1.0,
                        "comparisons": [], "note": "stdout not applicable"}
                else:
                    result["expected_comparison"] = _cmp
                    if not _cmp["all_match"] and status == "ok":
                        status = "partial"
                        result["status"] = "partial"
                        quality_note = quality_note or (
                            "expected comparison failed: "
                            + "; ".join(c["diff"] for c in _cmp["comparisons"]
                                        if not c["match"])[:200])
        except Exception:
            pass  # fail-safe: comparison xatosi run'ni buzmaydi
        # Phase 1 tracing: goal_id + SM history (§16 observability)
        if self.goal_context is not None:
            result["goal_id"] = self.goal_context.goal.id
            result["goal_text"] = self.goal_context.goal.text
        if self.sm is not None:
            result["sm_final_state"] = self.sm.state.value
            result["sm_history_len"] = len(self.sm.history())
        # Phase 2 tracing (§4/§10): world stats + verification evidence
        if self.world is not None:
            result["world_stats"] = self.world.stats()
            result["confirmed_facts"] = self.world.confirmed_facts(limit=10)
        if self.vlog is not None:
            result["verifications"] = self.vlog.to_list()
        # Phase 4 (§16): structured error/recovery loglar — native loop.
        if self._error_log:
            result["errors"] = self._error_log
        if self._recovery_log:
            result["recovery_events"] = self._recovery_log
        # Roadmap v2 B3 (§16): LLM decision trace — native loop.
        if decision_trace:
            result["decision_trace"] = decision_trace

        # Roadmap v2 B1 (§13): verified-only speech — native loop xulosasi uchun.
        try:
            result["final"] = self._apply_claim_check(
                result.get("final", ""), task, tool_calls, result, status)
        except Exception:
            result["final_claims_checked"] = False  # fail-safe

        # Roadmap v2 C2 (§16): birlashgan chronological timeline — native loop.
        try:
            result["timeline"] = self._build_timeline(tool_calls)
        except Exception:
            pass  # observability — run'ni buzmaydi

        if self.hooks is not None:
            self.hooks.fire("on_task_done", {"task": task, "result": result})
        self._remember(task, result)
        return result

    # ------------------------------------------------------------ #
    # Universal composition execution (bottom-up qatlamlab qurish)
    # ------------------------------------------------------------ #

    def run_composition(self, goal: str, demand: Any = 1,
                        registry=None, max_layer_errors: int = 0) -> dict:
        """Universal qatlamli qurish: reja (top-down) -> bajarish (bottom-up).

        CompositionEngine.build_plan() reja quradi (explosion + layers),
        so'ng qatlamlar BARGLARDAN Ildizga bajariladi. Har bir qatlam
        o'zidan oldingisiga tayanadi — qatlamdagi biron node xato bersa,
        yuqori qatlamlar ishga tushmaydi (noto'g'ri qismga qurilish yo'q).

        Atomic node bajarilishi:
          - attrs['tool'] bor bo'lsa -> registry/MCP tool chaqiriladi
          - LLM bo'lsa -> process matni asosida qadam bajariladi
          - aks holda -> "planned" (rejalashtirilgan) belgilanadi

        Return: {task, status, engine, demand, plan, layers, nodes,
                 errors, stats, workspace_root}
        """
        from task.composition import CardRegistry, CompositionEngine

        t0 = time.perf_counter()
        registry = registry if registry is not None else CardRegistry()
        engine = CompositionEngine(registry)
        errors = engine.validate()
        if errors:
            return self._composition_result(goal, demand, plan=None,
                                            status="error", errors=errors[:6], t0=t0)
        if engine.registry.get(goal) is None:
            return self._composition_result(goal, demand, plan=None,
                                            status="error",
                                            errors=[f"unknown goal: {goal}"], t0=t0)

        plan = engine.build_plan(goal, demand)
        if plan.get("errors"):
            return self._composition_result(goal, demand, plan=plan,
                                            status="error",
                                            errors=plan["errors"][:6], t0=t0)
        layers: list[dict] = []
        nodes: dict[str, dict] = {}
        failures = 0
        status = "ok"

        for li, layer in enumerate(plan["layers"]):
            layer_report = {"layer": li, "nodes": [], "status": "ok"}
            for nid in layer:
                card = engine.registry.require(nid)
                need = plan["explosion"].get(nid, "?")
                child_status = None
                if card.is_composite:
                    child_status = {
                        c.ref: nodes.get(c.ref, {}).get("status", "error")
                        for c in card.components
                    }
                res = self._execute_composition_node(card, need, child_status)
                nodes[nid] = res
                layer_report["nodes"].append({nid: res.get("status")})
                if res.get("status") == "error":
                    failures += 1
                    layer_report["status"] = "error"
            layers.append(layer_report)
            if layer_report["status"] == "error":
                status = "partial"
                if failures > max_layer_errors:
                    break  # pastki qatlam buzildi — yuqori qatlamlar ishlamaydi

        return self._composition_result(goal, demand, plan=plan, status=status,
                                        layers=layers, nodes=nodes,
                                        errors=errors, t0=t0)

    def _execute_composition_node(self, card, need: Any,
                                  child_status: Optional[dict] = None) -> dict:
        """Bitta karta node'ini bajaradi (atomic -> tool, composite -> yig'ish).

        child_status: composite node uchun bolalar holati ({ref: status}).
        Composite faqat barcha bolalari 'ok' bo'lsa muvaffaqiyatli hisoblanadi.
        """
        base = {"item": card.id, "kind": card.kind,
                "name": card.name or card.id, "need": str(need)}
        if card.is_composite:
            status = "ok" if child_status is not None and all(
                s == "ok" for s in child_status.values()) else "error"
            return {**base, "status": status,
                    "detail": (card.attrs.get("process")
                               or "assembled from children")}
        tool = card.attrs.get("tool")
        if tool:
            args = dict(card.attrs.get("args") or {})
            out = self._execute_agent_tool(tool, args)
            ok = bool(out.get("ok"))
            return {**base, "status": "ok" if ok else "error", "tool": tool,
                    "output": str(out.get("output") or out.get("error") or "")[:300]}
        if self.llm is not None:
            detail = card.attrs.get("process") or card.name or card.id
            text = self.llm.complete(
                system=("You are executing one step of a composition plan. "
                        "Describe concisely how you would complete this step."),
                prompt=f"Step: {detail}\nRequired qty: {need} {card.unit}")
            return {**base, "status": "ok", "detail": (text or "").strip()[:300]}
        return {**base, "status": "ok",
                "detail": card.attrs.get("process") or "planned"}

    def _composition_result(self, goal: str, demand: Any, plan=None,
                            status: str = "ok", layers=None, nodes=None,
                            errors=None, t0: Optional[float] = None) -> dict:
        """Composition natijasini yig'adi (yagona format)."""
        t0 = t0 if t0 is not None else time.perf_counter()
        return {
            "task": goal,
            "status": status,
            "engine": "composition",
            "demand": str(demand),
            "plan": plan,
            "layers": layers or [],
            "nodes": nodes or {},
            "errors": errors or [],
            "stats": {
                "layers": len(layers or []),
                "nodes": len(nodes or {}),
                "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            },
            "workspace_root": self.workspace.root,
        }

    # ------------------------------------------------------------ #
    # Agent extension tools (skills / MCP / human-in-the-loop)
    # ------------------------------------------------------------ #

    def _agent_schemas(self) -> list[dict]:
        """Qo'shimcha agent tool'larning Ollama schema'lari."""
        schemas = []
        if self.skills is not None:
            schemas.append({
                "type": "function",
                "function": {
                    "name": "use_skill",
                    "description": "Load a skill's step-by-step instructions to do something "
                                    "you cannot do with raw tools (e.g. drawing an image). "
                                    "Skills available: " + ", ".join(self.skills.names() or []),
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string", "description": "skill name"}},
                        "required": ["name"],
                    },
                },
            })
        if self.mcp is not None:
            schemas.append({
                "type": "function",
                "function": {
                    "name": "mcp_call",
                    "description": "Call a tool on a connected MCP server. Use name "
                                    "'server__tool'. Available tools: "
                                    + ", ".join(self.mcp.names() or ["(none)"]),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tool": {"type": "string", "description": "server__tool name"},
                            "args": {"type": "object", "description": "tool arguments"},
                        },
                        "required": ["tool"],
                    },
                },
            })
        if self.human_provider is not None:
            schemas.append({
                "type": "function",
                "function": {
                    "name": "request_human",
                    "description": "Ask the human operator for input, confirmation or help. "
                                    "Use only after you have genuinely tried skills and MCP tools.",
                    "parameters": {
                        "type": "object",
                        "properties": {"question": {"type": "string", "description": "clear question for the human"}},
                        "required": ["question"],
                    },
                },
            })
        return schemas

    def _execute_agent_tool(self, name: str, args: dict) -> dict:
        """Registry tool'larini yoki agent kengaytma tool'larini bajaradi."""
        if name == "use_skill":
            if self.skills is None:
                return {"ok": False, "error": "no skills available"}
            skill = self.skills.get(str(args.get("name", "")))
            if skill is None:
                return {"ok": False, "error": f"unknown skill: {args.get('name')}. Available: {self.skills.names()}"}
            return {"ok": True, "output": skill.full_text(), "content": skill.full_text()}
        if name == "mcp_call":
            if self.mcp is None:
                return {"ok": False, "error": "no MCP bridge available"}
            tool = str(args.get("tool", ""))
            norm = self._normalize_mcp_args(tool, args.get("args") or {})
            if norm.get("ok") is False:
                return norm
            return self.mcp.call_tool(tool, norm)
        # To'g'ridan-to'g'ri MCP tool nomi (web_ai_bridge__browser_navigate kabi)
        # — model ularni nomlari bo'yicha chaqiradi, generic mcp_call emas.
        if self.mcp is not None and name in self.mcp.names():
            norm = self._normalize_mcp_args(name, args)
            if norm.get("ok") is False:
                return norm
            return self.mcp.call_tool(name, norm)
        if name == "request_human":
            if self.human_provider is None:
                return {"ok": False, "error": "no human available — finish autonomously"}
            try:
                answer = self.human_provider(str(args.get("question", "")))
            except Exception as exc:
                return {"ok": False, "error": f"human provider failed: {exc}"}
            if not answer:
                return {"ok": False, "error": "human gave no answer"}
            return {"ok": True, "output": f"Human answered: {answer}", "content": f"Human answered: {answer}"}
        # Rasm fayllarini (rastr) write_file/apply_patch bilan yozish/bo'shatish
        # bloklanadi — chizmalar faqat art__draw_object_png kabi MCP tool'lar orqali
        # yaratiladi. Model bo'sh content bilan rasmni buzishi oldini oladi.
        if name in ("write_file", "apply_patch"):
            p = str(args.get("path") or "")
            if p.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico")):
                return {"ok": False, "error": (
                    "refusing to write a raster image file with write_file - use "
                    "art__draw_object_png instead"
                )}
        # oddiy registry tool'i
        return self.registry.execute(self.workspace, name, args)

    # ------------------------------------------------------------ #
    # Native args normalization
    # ------------------------------------------------------------ #

    def _normalize_mcp_args(self, tool: str, raw_args: dict) -> dict:
        """MCP tool arg'larini schema'ga moslashtiradi.

        - Alias normalize: model `object` yozsa -> `subject` (schema prop nomi)
        - Path'li arg'lar workspace'ga resolve qilinadi (sandbox ichida qoladi)
        """
        SYNONYMS = {"object": "subject", "output_path": "output",
                    "filepath": "path", "filename": "output"}
        args = dict(raw_args or {})
        props: dict = {}
        if self.mcp is not None:
            info = self.mcp.tool_index.get(tool)
            if info:
                params = info.get("schema", {}).get("parameters") or {}
                props = params.get("properties") or {}
        prop_names = set(props.keys())
        for key in list(args.keys()):
            if key in prop_names:
                continue
            alias = SYNONYMS.get(key)
            if alias and alias in prop_names and alias not in args:
                args[alias] = args.pop(key)
        # SMART DEFAULT OUTPUT: model `output` bermagan bo'lsa (art__* tool'larida)
        # subject/app dan nom yaratamiz VA workspace'ga resolve qilamiz. Aks holda
        # fayl MCP server cwd'siga yozilib, workspace/preview ko'ra olmay qoladi.
        if "output" in prop_names and not args.get("output"):
            import re as _re
            base = str(args.get("subject") or args.get("app") or args.get("name") or "art")
            slug = _re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_") or "art"
            if "ui_build_spec" in tool:
                slug = (slug or "ui") + ".uibuild.json"
            elif "svg" in tool:
                slug = (slug or "scene") + ".svg"
            else:
                slug = (slug or "art") + ".png"
            try:
                args["output"] = self.workspace.resolve(slug)
            except ValueError:
                args["output"] = slug
        # path'li arg'lar — doim workspace root ichiga resolve qilinadi.
        # Mutlaq (absolyut) yo'llar (masalan browser_upload_file uchun tashqi
        # fayl) o'zgarmasdan o'tkaziladi — faqat nisbiy yo'llar resolve qilinadi.
        import os as _os
        for key in list(args.keys()):
            if key not in prop_names:
                continue
            val = args[key]
            if not isinstance(val, str) or not val or _os.path.isabs(val):
                continue
            kind = props.get(key, {}).get("type", "")
            if key in ("output", "path", "file", "filename") or kind == "string" \
                    and ("path" in key or "file" in key or "output" in key):
                try:
                    args[key] = self.workspace.resolve(val)
                except ValueError:
                    return {"ok": False, "error": f"path escapes workspace: {val}"}
        return args

    def _normalize_native_args(self, tool_name: str, args: dict) -> dict:
        """Native model argumentlarini tool'ga moslashtiradi.

        - Windows: `python3` -> `python`
        - bo'sh yoki `/workspace` cwd -> workspace root
        - python_exec `timeout` 60 ga cheklanadi
        - MCP tool'lar: schema'ga mos normalize (path'lar workspace'ga resolve)
        """
        args = dict(args or {})
        if tool_name == "run_command":
            cmd = str(args.get("command", ""))
            if cmd.strip().startswith("python3 "):
                args["command"] = cmd.replace("python3 ", "python ", 1)
            cwd = str(args.get("cwd") or "").strip()
            if not cwd:
                args["cwd"] = ""
            elif cwd in ("/workspace", "\\workspace", "workspace", "ws"):
                args["cwd"] = self.workspace.root
            else:
                try:
                    args["cwd"] = self.workspace.resolve(cwd)
                except ValueError:
                    args["cwd"] = self.workspace.root
        if tool_name == "python_exec":
            t = args.get("timeout")
            if isinstance(t, (int, float)) and t > 60:
                args["timeout"] = 60
        return args

    # ------------------------------------------------------------ #
    # Step execution
    # ------------------------------------------------------------ #

    def _execute_step(self, step: dict, tool_calls: list[dict], task: str = "") -> dict:
        """Bir bosqichni bajaradi: tavsiya qilingan tool'lar orqali."""
        tools = step.get("tools") or []
        outcomes: list[dict] = []
        status = "done"
        corrections = 0

        if not tools:
            return {"status": status, "result": {"note": "no tools for this step"},
                    "tool_count": 0, "corrections": 0}

        for tool_name in tools:
            # Phase 4 (§15): cancellation — signal bo'lsa step darhol to'xtaydi.
            if self._check_cancelled():
                return {"status": "cancelled", "result": {"note": "cancel signal"},
                        "tool_count": len(outcomes), "corrections": corrections}
            if len(tool_calls) >= self.max_tool_calls:
                return {"status": "stopped", "result": {"note": "tool limit reached"},
                        "tool_count": len(outcomes), "corrections": corrections}
            args = self._default_args(tool_name, step, task)
            out, corr = self._call_with_retry(tool_name, args)
            corrections += corr
            record = {
                "action_id": _action_id() if _PHASE2_OK else "",  # §3: har action unique ID
                "ts": round(time.time(), 3),  # C2: timeline uchun vaqt
                "step": step.get("id"),
                "step_title": step.get("title"),
                "tool": tool_name,
                "args": args,
                "result": {k: v for k, v in out.items() if k != "output"} ,
                "output_preview": str(out.get("output") or out.get("content") or "")[:200],
            }
            if corr:
                # Phase 4 (§16): LLM-arg tuzatish recovery event sifatida.
                self._log_recovery("arg_fix", f"{tool_name}: {corr}x retry-corrected")
            # Jonli progress — run davomida UI'da ko'rinadi
            self._progress(stage_for_tool(tool_name),
                           f"{tool_name} → {_tool_preview(tool_name, args)}", record)
            tool_calls.append(record)
            outcomes.append(out)
            if not out.get("ok"):
                # Phase 4 (§11/§16): xato tasnif + log + same-error escalation.
                self._record_tool_error(tool_name, out)
                status = "error"
                break

        return {
            "status": status,
            "result": {"outcomes": outcomes, "note": step.get("detail", "")},
            "tool_count": len(outcomes),
            "corrections": corrections,
        }

    # ------------------------------------------------------------ #
    # Tool call + retry
    # ------------------------------------------------------------ #

    def _call_with_retry(self, tool_name: str, args: dict) -> tuple[dict, int]:
        """Tool'ni chaqiradi; xatolikda LLM tuzatishi bilan qayta (max retries).

        `_execute_agent_tool` MCP tool'larini (server__tool) ham, registry
        tool'larini ham o'zi to'g'ri yo'lga yo'naltiradi.
        """
        retries = 0
        out = self._execute_agent_tool(tool_name, args)
        while not out.get("ok") and retries < self.max_retries and self.llm is not None:
            retries += 1
            fixed = self._ask_fix(tool_name, args, out)
            if not fixed:
                break
            tool_name, args = fixed
            out = self._execute_agent_tool(tool_name, args)
        return out, retries

    def _ask_fix(self, tool_name: str, args: dict, out: dict) -> Optional[tuple[str, dict]]:
        """LLM'dan tuzatilgan tool chaqiruvini so'raydi."""
        prompt = (
            f"Tool: {tool_name}\nArgs: {args}\nError: {out.get('error', '')}\n\n"
            "Provide corrected JSON."
        )
        text = self.llm.complete(system=CORRECTION_SYSTEM, prompt=prompt)
        if not text:
            return None
        parsed = self.planner._extract_json(text)
        if not parsed:
            return None
        if "tool" in parsed and isinstance(parsed["tool"], str):
            return parsed["tool"], parsed.get("args", {}) or {}
        return None

    def _ask_final_summary(self, messages: list[dict], requirements=None) -> str:
        """Tool'lar bajarilgach — modeldan ODDIY matnli xulosa so'raydi.

        qwen2.5-coder tool-call JSON'ini content sifatida takrorlaydi; shu
        sabab toolsiz chat so'rovini yuboramiz — haqiqiy xulosa olamiz.
        (igris_agent._chat_with_tools'dagi xulosa naqshi bilan bir xil.)
        Part L: requirements berilsa — xulosa uzunligi/tili shunga moslanadi
        (qotib qolgan "2-3 short sentences" o'rniga).
        """
        self._progress("review", "xulosa yozilmoqda…")
        if self.llm is None:
            return ""
        if requirements is not None:
            lang = getattr(requirements, "language", "") or "the user's language"
            verb = {
                "concise": "1-2 short sentences",
                "detailed": "a detailed summary (5-8 sentences)",
                "balanced": "2-4 short sentences",
            }.get(getattr(requirements, "verbosity", "balanced"), "2-4 short sentences")
            content = (
                f"Summarize what you just did for the user in {verb}, in {lang}: "
                "what was the task, what tools you used, what was created/fixed and "
                "the final result. Plain text only — no JSON, no tool-call format, "
                "no code fences."
            )
        else:
            content = (
                "Summarize what you just did for the user in 2-3 short sentences, "
                "in the user's language: what was the task, what tools you used, "
                "what was created/fixed and the final result. Plain text only — "
                "no JSON, no tool-call format, no code fences."
            )
        base = [m for m in messages if m.get("role") in ("system", "user", "assistant")]
        base.append({
            "role": "user",
            "content": content,
        })
        try:
            resp = self.llm.chat(base)
        except Exception:
            return ""
        return (resp or "").strip()

    # ------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------ #

    def _default_args(self, tool_name: str, step: dict, task: str = "") -> dict:
        """Tool uchun boshlang'ich argumentlar (planner detail'idan).

        LLM mavjud bo'lsa — modeldan argumentlar so'raladi (smart execution).
        Part L (CP-C3): LLM bor bo'lsa placeholder CONTENT yaratilmaydi —
        yolg'on fayl/kod ("# generated by Igris", "print('ok')") emas; LLM
        args bera olmasa `{}` qaytadi va tool halol xato bilan tugaydi
        (`_ask_fix` uni tuzatishi mumkin). LLM bo'lmasa (offline) — qoida
        asosida, lekin faqat real task-detail'dan (placeholder shablonlar yo'q).
        """
        if self.llm is not None:
            generated = self._ask_tool_args(tool_name, step)
            if generated is not None:
                return generated
            # Faqat read-only tool'lar uchun xavfsiz path-guess qoladi
            title = step.get("title", "").lower()
            detail = step.get("detail", "")
            path = _guess_path(task) or _guess_path(title) or _guess_path(detail) or ""
            if tool_name == "read_file" and path:
                return {"path": path}
            if tool_name == "list_files":
                return {"path": "", "depth": 2}
            return {}

        title = step.get("title", "").lower()
        detail = step.get("detail", "")
        path = (_guess_path(task) or _guess_path(title) or _guess_path(detail) or "")
        if tool_name == "read_file":
            return {"path": path}
        if tool_name == "write_file":
            return {"path": path, "content": detail}
        if tool_name == "apply_patch":
            return {"path": path, "patch": detail[:400]}
        if tool_name == "list_files":
            return {"path": "", "depth": 2}
        if tool_name == "run_command":
            return {"command": detail}
        if tool_name == "python_exec":
            return {"code": detail}
        # MCP tool'lari uchun fallback: rejadan URL (browser_navigate) yoki
        # selector (click/type) olinadi — LLM bo'lmasa ham ishlashi uchun.
        if self.mcp is not None and tool_name in self.mcp.names():
            if tool_name.endswith("__browser_navigate"):
                m = re.search(r"https?://\S+", (detail or "") + " " + task)
                if m:
                    return {"url": m.group(0).rstrip(".,)]}")}
            return {}
        return {}

    def _ask_tool_args(self, tool_name: str, step: dict) -> Optional[dict]:
        """LLM'dan berilgan tool uchun to'g'ri argumentlar so'raydi.

        Promptda bosqich maqsadi + tool schema beriladi; javob JSON args.
        """
        tool = self.registry.get(tool_name)
        schema = tool.schema() if tool else None
        if schema is None and self.mcp is not None:
            info = self.mcp.tool_index.get(tool_name)
            if info:
                schema = info["schema"]
        schema = schema or {}
        prompt = (
            f"You are executing this step of an agent task:\n"
            f"Step: {step.get('title', '')}\n"
            f"Detail: {step.get('detail', '')}\n\n"
            f"Call the tool '{tool_name}' with the arguments needed to make progress.\n"
            f"Tool schema: {schema}\n\n"
            "Reply with ONLY valid JSON object of arguments, e.g. "
            '{"path": "src/main.py", "content": "print(1)"}. '
            "Use real file paths relative to workspace root.\n"
            "If you need to inspect first, use list_files."
        )
        text = self.llm.complete(system=EXEC_ARGS_SYSTEM, prompt=prompt)
        if not text:
            return None
        parsed = self.planner._extract_json(text)
        if not parsed:
            return None
        return {k: v for k, v in parsed.items() if not k.startswith("_")}

    # ------------------------------------------------------------ #
    # Sifat eshigi: yetkazib berilgan natijani tekshirish
    # ------------------------------------------------------------ #

    @staticmethod
    def _task_asks_output(task: str) -> bool:
        """Vazifa yozma natija (fayl) talab qiladimi?"""
        low = (task or "").lower()
        return any(w in low for w in DELIVERABLE_WORDS)

    @staticmethod
    def _browser_summary_done(task: str, tool_calls: list[dict]) -> bool:
        """Brauzer xulosa vazifasi bajarilganmi?

        Vazifada URL / brauzer so'zlari bo'lsa va web_ai_bridge browser
        tool'laridan kamida bittasi MUVaffaqiyatli chaqirilgan bo'lsa —
        yakuniy javob (xulosa) natija hisoblanadi, fayl shart emas.
        """
        low = (task or "").lower()
        is_browser = bool(URL_RE.search(task or "")) or any(
            w in low for w in ("browser", "web page", "webpage", "open the page", "sayt", "sahifa")
        )
        if not is_browser:
            return False
        ok_tools = {
            str(tc.get("tool") or "")
            for tc in (tool_calls or [])
            if (tc.get("result") or {}).get("ok")
        }
        # Sahifa TARKIBI haqiqatan o'qilgan bo'lsa — xulosa natija hisoblanadi.
        # Faqat browser_info/screenshot kabi yordamchi chaqiriq yetarli emas.
        if "web_ai_bridge__browser_get_text" in ok_tools \
                or "web_ai_bridge__ask_web_ai" in ok_tools:
            return True
        if "web_ai_bridge__browser_navigate" in ok_tools \
                and "web_ai_bridge__browser_screenshot" in ok_tools:
            return True
        return False

    @staticmethod
    def _requested_files(task: str) -> list[str]:
        """Taskda aytilgan fayl nomlarini topadi (save to X, fayl nomi bilan)."""
        found: list[str] = []
        for m in re.finditer(r"[\w./\\-]+\.(?:py|txt|md|json|png|jpg|jpeg|svg|html|css|js|csv|log|webm)\b", (task or ""), re.IGNORECASE):
            name = m.group(0).strip(".,;:()'\"`")
            if name and name not in found:
                found.append(name)
        return found[:8]

    # ------------------------------------------------------------------ #
    # Roadmap v3 R1 (§17/§28): REQUIREMENT MATRIX — deterministik completion
    # contract. COMPLETE faqat barcha mandatory requirement'lar PASS bo'lganda.
    # ------------------------------------------------------------------ #

    def _build_requirement_matrix(self, status: str) -> Optional[dict]:
        """Run oxirida requirement matrix'ni yuritadi + formal status qaytaradi.

        Snapshot run boshida immutable yaratilgan; tekshiruv REAL fs holatidan
        (workspace) o'tadi — LLM javobiga va tool ok=true'ga ishonmaydi.
        Fail-safe: matrix xatosi run'ni buzmaydi (None qaytadi).
        """
        snap = getattr(self, "_req_snapshot", None)
        if snap is None:
            return None
        try:
            report = _rmx.run_matrix(snap, self.workspace.root)
            matrix = report["matrix"]
            c_status = _rmx.completion_status(matrix)
            # B1 claim-check bilan bir xil falsafa: status sm bilan mos emasa —
            # executor statusini pasaytiramiz (COMPLETE faqat evidence bilan).
            if c_status == _rmx.CONTRACT_FAILED and status == "ok":
                status = "partial"
            elif c_status == _rmx.CONTRACT_PARTIAL and status == "ok":
                status = "partial"
            return {
                "completion": c_status,
                "executor_status": status,
                "matrix": matrix,
            }
        except Exception:
            return None

    def _verify_deliverable(self, task: str, tool_calls: list[dict]) -> tuple[bool, str]:
        """Sifat eshigi: yozilgan natija vazifani haqiqatan bajaryaptimi?

        Qaytadi: (ok, note)
          - taskda nomlangan fayl( lar ) yozilmagan / bo'sh / shablon -> tuzatish
          - fayl shubhali qisqa      -> LLM tekshiruvi, kerak bo'lsa tuzatish
          - fayl yetarli darajada    -> (True, "")
        """
        requested = self._requested_files(task)
        paths: list[str] = []
        for tc in tool_calls:
            if tc.get("tool") in ("write_file", "apply_patch"):
                p = (tc.get("args") or {}).get("path")
                if isinstance(p, str) and p:
                    paths.append(p)

        # 1) Taskda AYTIQGANDek fayl borligini tekshiramiz (masalan blue_apple.png)
        if requested:
            missing = []
            for name in requested:
                base = os.path.basename(str(name).replace("\\", "/"))
                exists = any(
                    os.path.basename(str(p).replace("\\", "/")) == base
                    for p in paths
                ) or os.path.isfile(os.path.join(self.workspace.root, base))
                if not exists:
                    missing.append(name)
            if missing:
                fix = self._try_finish_deliverable(task, tool_calls)
                if fix is not None:
                    self._record_deliverable_fix(tool_calls, fix)
                return (fix is not None), (
                    "talab qilingan fayl topilmadi: " + ", ".join(missing[:3])
                    if fix is None else ""
                )

        if not paths:
            fix = self._try_finish_deliverable(task, tool_calls)
            if fix is not None:
                self._record_deliverable_fix(tool_calls, fix)
            return (fix is not None), ("hech qanday fayl yozilmadi" if fix is None else "")

        path = paths[-1]
        try:
            r = self.workspace.read(path)
        except Exception:
            r = {}
        content = str(r.get("content") or "") if r.get("ok") else ""

        if not content.strip():
            fix = self._try_finish_deliverable(task, tool_calls)
            if fix is not None:
                self._record_deliverable_fix(tool_calls, fix)
            return (fix is not None), ("fayl bo'sh qoldi" if fix is None else "")

        # Qisqa/shablon bo'lishi mumkin bo'lgan natijalar LLM bilan tekshiriladi
        if len(content.strip()) >= 120:
            # A1 1-qadam (deterministik verifikator): Python fayllari uchun
            # sintaksis darhol tekshiriladi — 120+ belgili lekin BUZUQ kod
            # ilgari quality gate'dan erkin o'tib ketardi.
            if path.lower().endswith(".py"):
                ok_syn, syn_note = _python_syntax_check(content)
                if not ok_syn:
                    fix = self._try_finish_deliverable(task, tool_calls)
                    if fix is not None:
                        self._record_deliverable_fix(tool_calls, fix)
                    return (fix is not None), (
                        f"python sintaksis xatosi: {syn_note}" if fix is None else ""
                    )
                # A1 2-qadam (run-verification): fayl haqiqatan ishga tushadimi?
                # Faqat QAT'IY ishga tushmaslik gate'dan o'tkazmaydi (False);
                # neytral holatlar (import/deps, deny-list, timeout) — o'tkazadi.
                run_ok, run_note = _python_run_check(content)
                if run_ok is False:
                    fix = self._try_finish_deliverable(task, tool_calls)
                    if fix is not None:
                        self._record_deliverable_fix(tool_calls, fix)
                    return (fix is not None), (
                        f"python fayli ishga tushmaydi: {run_note}" if fix is None else ""
                    )
            return True, ""
        verdict = self._llm_verify_deliverable(task, path, content, tool_calls)
        if verdict == "complete":
            return True, ""
        fix = self._try_finish_deliverable(task, tool_calls)
        if fix is not None:
            self._record_deliverable_fix(tool_calls, fix)
        return (fix is not None), (
            "natija vazifani bajarmadi" if fix is None else ""
        )

    def _record_deliverable_fix(self, tool_calls: list[dict], fix: dict):
        """Sifat eshigi tuzatuvchi yozuvini tool_calls'ga qo'shadi + jonli stream.

        UI'da chizma karta ko'rinishi va RUN DAVOMIDA (progress_cb orqali)
        ham yetib borishi uchun. `fix` — write_file dict (path, content...).
        """
        tool_calls.append(fix)
        p = ""
        try:
            args = fix.get("args") or {}
            if isinstance(args, dict):
                p = str(args.get("path") or "")
        except Exception:
            p = ""
        self._progress("edit", f"write_file → {p}", fix)

    def _llm_verify_deliverable(self, task: str, path: str, content: str,
                                tool_calls: list[dict]) -> str:
        """LLM natijani vazifaga mos deb baholaydi: 'complete' | 'incomplete'."""
        if self.llm is None:
            return "complete" if len(content.strip()) >= 120 else "incomplete"
        ctx_parts: list[str] = []
        for tc in tool_calls[-6:]:
            prev = str(tc.get("output_preview") or "")[:300]
            if prev.strip():
                ctx_parts.append(f"[{tc.get('tool')}] {prev}")
        ctx = "\n".join(ctx_parts)[:1800]
        prompt = (
            f"TASK:\n{task[:400]}\n\n"
            f"DELIVERABLE FILE '{path}':\n{content[:1500]}\n\n"
            f"TOOL OUTPUTS:\n{ctx or '(none)'}\n\n"
            "Reply with ONLY: COMPLETE or INCOMPLETE"
        )
        try:
            text = self.llm.complete(system=VERIFY_SYSTEM, prompt=prompt)
        except Exception:
            return "complete" if len(content.strip()) >= 120 else "incomplete"
        t = (text or "").strip().upper()
        if "COMPLETE" in t and "INCOMPLETE" not in t:
            return "complete"
        return "incomplete"

    def _try_finish_deliverable(self, task: str, tool_calls: list[dict]) -> Optional[dict]:
        """Tuzatuvchi pass: yig'ilgan tool natijalari asosida LLM yetkazib
        beriladigan natijani yozadi. Muvaffaqiyat bo'lsa toolcall dict qaytadi.

        Agent bo'sh fayl yozib 'bajardim' deganida ham ishlaydi — kontekstdan
        (browser_get_text kabi) haqiqiy tarkib yaratiladi.
        """
        if self.llm is None:
            return None
        ctx_parts: list[str] = []
        for tc in tool_calls[-6:]:
            preview = str(tc.get("output_preview") or "")[:600]
            if preview.strip():
                ctx_parts.append(f"[{tc.get('tool')}] {preview}")
        ctx = "\n".join(ctx_parts)[:2500]
        # Maqsad fayl: agent allaqachon yozgan yo'l ustuvor; agar taskda nomlangan
        # fayl bo'lsa (masalan "buggy.py") — shuni tuzatamiz, result.txt emas.
        named = self._requested_files(task)
        attempted = [
            str((tc.get("args") or {}).get("path"))
            for tc in tool_calls
            if tc.get("tool") in ("write_file", "apply_patch")
            and (tc.get("args") or {}).get("path")
        ]
        path = "result.txt"
        if attempted and (not named or any(
                os.path.basename(str(p).replace("\\", "/")) == os.path.basename(str(n).replace("\\", "/"))
                for p in attempted for n in named)):
            path = attempted[-1]
        elif named:
            path = named[0]
        # fix/tuzat vazifalari: joriy fayl tarkibini prompt'ga qo'shamiz — LLM
        # bo'sh/prose emas, HAQIQIY tuzatilgan kontent yozishi uchun.
        current = ""
        try:
            r = self.workspace.read(path)
            if r.get("ok"):
                current = str(r.get("content") or "")[:1500]
        except Exception:
            current = ""
        current_block = (
            f"\n\nCURRENT FILE '{path}' CONTENT (fix this):\n{current}\n"
            if current.strip() else ""
        )
        # fix/tuzat belgilari — "error" so'zi keng, uni olib tashladik ("handles
        # errors" kabi zararsiz vazifalarni fix-prompt'iga aylantirmaslik uchun).
        is_fix = bool(re.search(r"(fix|tuzat|bug|xato|repair|noto'g'ri)", task or "", re.IGNORECASE))
        if not is_fix and current.strip():
            is_fix = True  # joriy fayl mavjud bo'lsa — tuzatish senariysi
        prompt = (
            "TASK:\n" + (task or "")[:500]
            + current_block
            + "\n\nTOOL OUTPUTS (context):\n" + (ctx or "(no tool outputs)")
            + "\n\n"
            + (("The task is to FIX an existing file. Produce the CORRECTED FULL "
                f"FILE CONTENT (the complete fixed version of '{path}', not a "
                "summary, not a comment, not instructions).\n") if is_fix else "")
            + "Write the missing deliverable to file '" + path + "'. "
            "Reply with ONLY JSON: {\"path\": \"...\", \"content\": \"...\"} — "
            "content must be the real deliverable text, non-empty."
        )
        try:
            text = self.llm.complete(system=CORRECTIVE_SYSTEM, prompt=prompt)
        except Exception:
            return None
        parsed = self.planner._extract_json(text) if text else None
        if not parsed or not parsed.get("content"):
            return None
        p = str(parsed.get("path") or path)
        content = str(parsed["content"])
        if not content.strip():
            return None
        try:
            out = self.workspace.write(p, content)
        except Exception:
            return None
        if not out.get("ok"):
            return None
        return {
            "tool": "write_file",
            "args": {"path": p, "content": content},
            "result": {"ok": True},
            "output_preview": content[:200],
        }

    def _remember(self, task: str, result: dict):
        if self.memory is None or not self.memory.enabled:
            return
        try:
            summary = f"{result['status']} | {result['stats']['tool_calls']} tools | {result['stats']['corrections']} fixes"
            self.memory.remember(
                f"TASK: {task}\nSTATUS: {result['status']}\nSTEPS: {len(result['steps'])} "
                f"TOOLS: {result['stats']['tool_calls']} FIXES: {result['stats']['corrections']}",
                memory_type="experience",
                tags=["agent-task", result["status"]],
                summary=summary,
            )
        except Exception:
            pass


def _guess_path(title: str) -> str:
    """Bosqich sarlavhasidan fayl nomini topishga urinish."""
    import re
    m = re.search(r"[\w./-]+\.\w+", title)
    return m.group(0) if m else ""



