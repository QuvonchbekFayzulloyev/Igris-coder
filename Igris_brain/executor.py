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

import os
import re
import time
from typing import Any, Callable, Optional

from tools import Workspace, ToolRegistry, DEFAULT_REGISTRY
from planner import TaskPlanner, URL_RE, _req_block
from memory_bridge import MemoryBridge
from skills import SkillManager


def _default_hooks():
    """Lazy DEFAULT_BUS import (hook tizimi ixtiyoriy)."""
    try:
        from hooks import DEFAULT_BUS
        return DEFAULT_BUS
    except Exception:
        return None


# Reja-birinchi qoida — har bir native run'da majburiy system qo'shimchasi.
# Agent muammoni aniqlab, reja tuzib, shundan keyin tool'lar bilan ishlaydi;
# xatolikda rejaga qaytadi (plan-first-fix skilliga mos).
PLAN_FIRST_SYSTEM = (
    "\n\nMANDATORY WORK RULE (plan-first):\n"
    "1. Before touching any tool, restate the problem in one sentence.\n"
    "2. Write a short visible plan (1-3 steps: what to read/create/fix, "
    "which files, which tools).\n"
    "3. Execute the plan step by step with the available tools.\n"
    "4. Verify the result against the plan. If a tool fails, first say which "
    "plan step went wrong, then fix THAT step — never patch ad-hoc outside the plan.\n"
    "5. When done, summarize what the plan achieved."
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
        # SEMANTIK TALAB QATLAMI (Part L): user talab modeli — reja va sifat
        # eshigi shunga moslashadi. Lazy init (offline'da ham ishlaydi).
        self.req_extractor = None

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
        for s in parsed[: self.max_steps]:
            out.append({
                "id": int(s.get("id", len(out) + 1)),
                "title": str(s.get("title", "Step")).strip(),
                "tools": [t for t in (s.get("tools") or []) if t in _PLANNER_ALLOWED_TOOLS or (self.mcp is not None and t in self.mcp.names())][:4],
                "detail": str(s.get("detail", "")).strip(),
            })
        return out or None

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
    # Main entry
    # ------------------------------------------------------------ #

    def run(self, task: str, requirements=None) -> dict:
        t0 = time.perf_counter()
        # Part L: Requirement modeli — reja va sifat eshigi shunga moslashadi.
        if requirements is None:
            requirements = self._extract_req(task)
        plan = self.planner.plan(task, requirements)
        self._progress("plan", "reja tuzildi — bajarish boshlandi")

        steps: list[dict] = []
        tool_calls: list[dict] = []
        corrections = 0
        total_tools = 0
        status = "ok"
        replans = 0

        if self.hooks is not None:
            self.hooks.fire("on_plan", {"task": task, "plan": plan})
        plan_steps = plan.get("steps", [])[: self.max_iter]
        i = 0
        while i < len(plan_steps):
            step = plan_steps[i]
            i += 1
            if self.hooks is not None:
                self.hooks.fire("on_step_start", {"task": task, "step": step, "plan": plan})
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
            if step_result["status"] == "error":
                status = "partial"
                # Part L (L7): qotib qolgan "abort + canned summary" o'rniga —
                # LLM'dan tuzatilgan KEYINGI qadamlar (maks 2 re-plan).
                if replans < 2 and self.llm is not None:
                    revised = self._replan(task, step, step_result,
                                           plan_steps[i:], requirements)
                    if revised:
                        replans += 1
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
        if status != "stopped" and (self._task_asks_output(task)
                                    or self._req_asks_output(task, requirements)) \
                and not self._browser_summary_done(task, tool_calls):
            ok_del, note = self._verify_deliverable(task, tool_calls)
            if not ok_del:
                status = "partial"
                quality_note = note or (
                    "task yozma natija talab qilardi, lekin fayl bo'sh/yo'q/shablon — "
                    "agent talab darajasida bajarmadi"
                )

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

        if self.hooks is not None:
            self.hooks.fire("on_task_done", {"task": task, "result": result})
        self._remember(task, result)
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
        self._progress("plan", "task tahlil qilinmoqda…")
        tool_calls: list[dict] = []
        failed_tools = 0
        plan_text = ""
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

        schemas = self.registry.ollama_schemas() + self._agent_schemas()
        status = "ok"
        final_content = ""
        iterations = 0
        any_tool_executed = False
        any_failure = False
        gap_reprompted = 0
        human_asked = False
        seen_calls: set[tuple] = set()

        while iterations < self.max_iter:
            iterations += 1
            if len(tool_calls) >= self.max_tool_calls:
                status = "stopped"
                break

            resp = self.llm.chat_with_tools(messages, tools=schemas)
            if not resp or not isinstance(resp, dict):
                # transport error → fallback to planned execution
                return self.run(task, requirements)

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
                        "tool": name,
                        "args": args,
                        "result": {k: v for k, v in out.items() if k != "output"},
                        "output_preview": str(out.get("output") or out.get("content") or "")[:300],
                    }
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
        if not any_tool_executed:
            return self.run(task, requirements)

        if not final_content:
            # max_iter tugadi, model hali ham tool chaqirayotgan edi
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
        from composition import CardRegistry, CompositionEngine

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
            if len(tool_calls) >= self.max_tool_calls:
                return {"status": "stopped", "result": {"note": "tool limit reached"},
                        "tool_count": len(outcomes), "corrections": corrections}
            args = self._default_args(tool_name, step, task)
            out, corr = self._call_with_retry(tool_name, args)
            corrections += corr
            record = {
                "step": step.get("id"),
                "step_title": step.get("title"),
                "tool": tool_name,
                "args": args,
                "result": {k: v for k, v in out.items() if k != "output"} ,
                "output_preview": str(out.get("output") or out.get("content") or "")[:200],
            }
            # Jonli progress — run davomida UI'da ko'rinadi
            self._progress(stage_for_tool(tool_name),
                           f"{tool_name} → {_tool_preview(tool_name, args)}", record)
            tool_calls.append(record)
            outcomes.append(out)
            if not out.get("ok"):
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



