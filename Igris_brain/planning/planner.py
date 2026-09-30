"""
IGRIS BRAIN — TaskPlanner (smart planning)
==========================================
Taskni bosqichlarga bo'ladi.

- LLM rejimida: Ollama'dan JSON reja so'raladi (qadamlar, har biriga tool tavsiyasi)
- Fallback rejimida: qoida asosidagi odatiy bosqichlar
  (o'qish -> reja -> yozish -> test) — LLM bo'lmasa ham ishlaydi

Output formati:
    {"goal": str, "reasoning": str, "confidence": float,
     "steps": [{"id": 1, "title": str, "tools": [str], "detail": str}]}
"""

from __future__ import annotations

import json
import re
from typing import Optional


DEFAULT_PLAN_SYSTEM = (
    "You are the planner of a coding agent. Break the user's task into 3-6 "
    "concrete, ordered steps. For each step suggest which tools to use from: "
    "{tool_list}. "
    "Use an MCP tool's full name exactly as listed (e.g. "
    "web_ai_bridge__browser_navigate) when the step needs browser automation. "
    "Respond with ONLY valid JSON: "
    '{"goal": "...", "reasoning": "1-2 sentences why this plan", '
    '"confidence": 0.0-1.0, '
    '"steps": [{"id": 1, "title": "...", "tools": ["..."], "detail": "..."}]}'
)


# Browser-ga oid vazifalarni aniqlash (fallback planner uchun)
BROWSER_TASK_WORDS = ("browser", "navigate", "web page")
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _req_block(req) -> str:
    """Requirement modelidan plan uchun ixcham blok (mavjud bo'lmasa bo'sh)."""
    if req is None:
        return ""
    lines = ["USER REQUIREMENTS:", f"- intent: {req.intent}",
             f"- output format: {req.output_format}", f"- verbosity: {req.verbosity}"]
    if getattr(req, "language", ""):
        lines.append(f"- language: {req.language}")
    if getattr(req, "deliverable_name", None):
        lines.append(f"- deliverable file: {req.deliverable_name}")
    if getattr(req, "constraints", None):
        lines.append("- constraints: " + "; ".join(req.constraints))
    return "\n".join(lines)


def _guess_file(task: str) -> str:
    """Task matnidagi fayl nomini topadi (yo'q bo'lsa '')."""
    m = re.search(r"[\w\-]+\.(py|ts|js|tsx|jsx|md|txt|html|css|json|go|rs|cpp|c|java|sql)", task or "")
    return m.group(0) if m else ""


# Qatlamli (TTK/BOM/WBS) rejalashtirish uchun CompositionEngine.build_plan()
# ishlatiladi — `from composition import CompositionEngine` (CompositionPlanner
# sinfi dublikat edi, olib tashlandi). Executor: AgentExecutor.run_composition().
class TaskPlanner:
    def __init__(self, llm=None, max_steps: int = 6, mcp_names=()):
        self.llm = llm
        self.max_steps = max_steps
        self.mcp_names = tuple(mcp_names or ())

    # ------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------ #

    def plan(self, task: str, requirements=None) -> dict:
        """Task -> reja dict. LLM bo'lmasa fallback qoidalar.

        `requirements` — ixtiyoriy Requirement modeli (Part L): LLM plan
        prompt'iga ham, fallback qadamlariga ham talab shakli uzatiladi —
        reja task O'ZGARISHIGA mos shakllanadi (qotib qolgan skeleton emas).
        """
        if self.llm is not None:
            try:
                parsed = self._plan_via_llm(task, requirements)
                if parsed and parsed.get("steps"):
                    return self._normalize(task, parsed)
            except Exception:
                pass
        fallback = self._fallback(task, requirements)
        # B2: intent — requirements classifier oilasidan (agar bor bo'lsa)
        if requirements is not None:
            intent = getattr(requirements, "intent", "")
            if intent:
                fallback["intent"] = str(intent)[:30]
        return fallback

    def decide(self, task: str, requirements=None, allowed_tools=None):
        """B2 fasad: plan() + rasmiy Decision modeli.

        Qaytaradi: Decision (hech qachon exception irmaydi — from_plan xavfsiz).
        allowed_tools berilsa — reja tool'lari registry/MCP bilan tekshiriladi
        (§14 band 8, validate_plan_tools bilan bir xil funksiya).
        """
        plan = self.plan(task, requirements)
        from planning.decision import Decision
        d = Decision.from_plan(plan, task=task)
        if allowed_tools is not None:
            from state.state_machine import validate_plan_tools
            _, msg = validate_plan_tools([s.to_dict() for s in d.steps],
                                         sorted(set(allowed_tools)))
            if msg:
                d.source = "tools_rejected"  # observability: guard rad etdi
        return d

    # ------------------------------------------------------------ #
    # LLM path
    # ------------------------------------------------------------ #

    def _plan_via_llm(self, task: str, requirements=None) -> Optional[dict]:
        tool_list = "read_file, write_file, apply_patch, list_files, run_command, python_exec"
        if self.mcp_names:
            tool_list += ", plus the connected MCP tools: " + ", ".join(self.mcp_names)
        # `.replace`, `.format` emas — template ichidagi JSON jingalak qavslari
        # ({"goal": ...}) format placeholder'i deb xato talqin qilinadi.
        system = DEFAULT_PLAN_SYSTEM.replace("{tool_list}", tool_list)
        if requirements is not None:
            system += "\n\n" + _req_block(requirements)
        out = self.llm.complete(system=system, prompt=task)
        if not out:
            return None
        return self._extract_json(out)

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        # try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # try fenced block
        m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # try first { ... } balanced block
        start = text.find("{")
        if start >= 0:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start : i + 1])
                        except json.JSONDecodeError:
                            return None
        return None

    # ------------------------------------------------------------ #
    # Fallback (rule-based)
    # ------------------------------------------------------------ #

    def _fallback(self, task: str, requirements=None) -> dict:
        """Talab modeli asosidagi fallback reja (kalit-so'z skeleton emas).

        Part L: `requirements` bor bo'lsa — qadamlar shunga mos tuziladi
        (intent/output_format/deliverable_name/constraints). Kalit-so'z faqat
        requirement modeli bo'lmaganda (offline) ishlatiladi.
        """
        req = requirements
        low = task.lower()
        steps: list[dict] = []

        # Brauzer vazifasi — web_ai_bridge MCP tool'lari bilan (agar ulangan bo'lsa)
        nav = "web_ai_bridge__browser_navigate"
        txt = "web_ai_bridge__browser_get_text"
        m = URL_RE.search(task)
        is_browser = (req is not None and req.intent == "web") or bool(m) or any(
            w in low for w in BROWSER_TASK_WORDS)
        if is_browser and nav in self.mcp_names and txt in self.mcp_names:
            url = m.group(0).rstrip(".,)]}") if m else ""
            steps.append(self._step(1, "Open the page in the browser", [nav],
                                    f"Navigate to {url or 'the URL from the task'}."))
            steps.append(self._step(2, "Read the page text", [txt],
                                    "Read the visible text of the page."))
            # Requirement output_format/constraints'ga mos yakuniy bosqich
            if req is not None and req.output_format in ("list", "table", "steps"):
                steps.append(self._step(3, f"Present as {req.output_format}", [],
                                        f"Present the page content as a {req.output_format} "
                                        f"in {'Uzbek' if req.language == 'uz' else 'the user language'}."))
            else:
                steps.append(self._step(3, "Summarize the page", [],
                                        "Summarize what the page contains."))
            return {"goal": task, "steps": steps[: self.max_steps], "engine": "fallback"}

        deliverable = (getattr(req, "deliverable_name", None) if req is not None else None) \
            or _guess_file(task) or "result.txt"
        wants_file = (req is not None and req.output_format in ("file", "code", "image", "html")) \
            or bool(deliverable) or any(w in low for w in ("write", "create", "yoz", "yarat"))

        # 1) Tushunish: fayl-ish so'rovlarida workspace ko'rish kerak bo'ladi
        if wants_file:
            steps.append(self._step(1, "Understand requirements",
                                    ["list_files", "read_file"],
                                    f"Task: {task[:200]}"))

        # 2) Amalga oshirish — natija shakli talabga mos
        if req is not None and req.intent == "code":
            steps.append(self._step(len(steps) + 1, f"Write {deliverable}",
                                    ["write_file"],
                                    f"Create `{deliverable}` implementing the task."))
        elif wants_file:
            steps.append(self._step(len(steps) + 1, f"Create {deliverable}",
                                    ["write_file"],
                                    f"Create `{deliverable}` with the requested content "
                                    f"({req.output_format if req is not None else 'file'})."))
        elif any(w in low for w in ("read", "o'qi", "open", "ko'rish", "faylni o'qi")):
            steps.append(self._step(1, "Read the relevant files", ["read_file", "list_files"],
                                    "Inspect the workspace to understand the current code."))

        # 3) Tekshirish
        if any(w in low for w in ("test", "verify", "run", "tekshir", "bajar", "check")) \
                or (req is not None and req.needs_tools and wants_file):
            steps.append(self._step(len(steps) + 1, "Verify with tests / execution",
                                    ["run_command", "python_exec"],
                                    "Run tests or execute the code to confirm it works."))

        # 4) Yakuniy xulosa — til/chuqurlik talabga mos
        verb = "detailed" if (req is not None and req.verbosity == "detailed") else ""
        steps.append(self._step(len(steps) + 1,
                                "Summarize result" + (f" ({verb})" if verb else ""),
                                [],
                                "Report what was done and the outcome."))

        if not steps:
            steps.append(self._step(1, "Understand requirements",
                                    ["read_file"], f"Task: {task[:200]}"))
            steps.append(self._step(2, "Summarize result",
                                    [], "Report what was done and the outcome."))

        return {
            "goal": task,
            "steps": steps[: self.max_steps],
            "engine": "fallback",
            # Phase 5 (§14): fallback deterministik — to'liq ishonch.
            "confidence": 1.0,
        }

    @staticmethod
    def _step(i: int, title: str, tools: list[str], detail: str) -> dict:
        return {"id": i, "title": title, "tools": tools, "detail": detail}

    # ------------------------------------------------------------ #
    # Normalize
    # ------------------------------------------------------------ #

    def _normalize(self, task: str, parsed: dict) -> dict:
        steps = []
        allowed = {"read_file", "write_file", "apply_patch", "list_files",
                   "run_command", "python_exec"}
        if self.mcp_names:
            allowed = allowed | set(self.mcp_names)
        for s in parsed.get("steps", [])[: self.max_steps]:
            steps.append({
                "id": int(s.get("id", len(steps) + 1)),
                "title": str(s.get("title", "Step")).strip(),
                "tools": [t for t in (s.get("tools") or []) if t in allowed][:4],
                "detail": str(s.get("detail", "")).strip(),
            })
        plan = {"goal": task, "steps": steps, "engine": "llm"}
        # Phase 5 (§14): ixtiyoriy decision maydonlari — reason/status separation.
        # Model bermasa — maydon qo'shilmaydi (backward-compatible).
        if parsed.get("reasoning"):
            plan["reasoning"] = str(parsed["reasoning"])[:500]
        try:
            conf = float(parsed.get("confidence"))
            if 0.0 <= conf <= 1.0:
                plan["confidence"] = round(conf, 2)
        except (TypeError, ValueError):
            pass
        return plan
