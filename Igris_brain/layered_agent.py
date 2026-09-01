"""
IGRIS BRAIN — Layered Agentic Loop
====================================
User prompt kelishi bilan:
  1. RE-PROMPT: Promptni qayta tahlil qiladi (rol, vazifa, maqsad)
  2. LAYER CONSTRUCTION: Maqsadli qatlamlar tuziladi
  3. LAYER EXECUTION: Har bir qatlam layer-by-layer bajariladi
  4. STREAMING: Har bir tool/MCP/skill/layer chaqiruvida token streaming
  5. SYNTHESIS: Barcha natijalar yig'iladi, final result taqdim etiladi

Agentic Loop:
  user_prompt -> reprompt_engine -> layer_plan -> [layer1 -> layer2 -> ... -> layerN] -> final_result
     |              |                    |              |                                    |
  (raw)     (role/task/purpose)    (structured)   (streamed tokens)              (accumulated)
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from typing import Any, Callable, Generator, Optional

from layered_prompts import (
    RE_PROMPT_SYSTEM,
    RE_PROMPT_EXAMPLES,
    LAYER_CONSTRUCTION_SYSTEM,
    LAYER_EXECUTION_PROMPTS,
    TOOL_STREAMING_PROMPTS,
    FINAL_SYNTHESIS_SYSTEM,
    RepromptAnalysis,
    ExecutionLayer,
    LayerPlan,
    LayerStep,
    tools_for_capabilities,
)


# ================================================================= #
# SSE Event helpers
# ================================================================= #

def sse_event(event_type: str, **kwargs) -> dict:
    """Create an SSE event dict with type and extra fields."""
    ev = {"type": event_type}
    ev.update(kwargs)
    return ev


def layer_start(layer_name: str) -> dict:
    return sse_event("layer_start", layer=layer_name)


def layer_done(layer_name: str, status: str = "complete", **kwargs) -> dict:
    ev = sse_event("layer_done", layer=layer_name, status=status)
    ev.update(kwargs)
    return ev


def tool_start(tool_name: str, layer: str, description: str = "") -> dict:
    return sse_event("tool_start", tool=tool_name, layer=layer, description=description)


def tool_done(tool_name: str, layer: str, result_preview: str = "", **kwargs) -> dict:
    ev = sse_event("tool_done", tool=tool_name, layer=layer, result=result_preview)
    ev.update(kwargs)
    return ev


def mcp_start(mcp_tool: str, layer: str, description: str = "") -> dict:
    return sse_event("mcp_start", mcp=mcp_tool, layer=layer, description=description)


def mcp_done(mcp_tool: str, layer: str, result_preview: str = "", **kwargs) -> dict:
    ev = sse_event("mcp_done", mcp=mcp_tool, layer=layer, result=result_preview)
    ev.update(kwargs)
    return ev


def skill_start(skill_name: str, layer: str, description: str = "") -> dict:
    return sse_event("skill_start", skill=skill_name, layer=layer, description=description)


def skill_done(skill_name: str, layer: str, result_preview: str = "", **kwargs) -> dict:
    ev = sse_event("skill_done", skill=skill_name, layer=layer, result=result_preview)
    ev.update(kwargs)
    return ev


def token_event(content: str, source: str = "agent") -> dict:
    return sse_event("token", content=content, source=source)


def stage_event(stage: str, detail: str, layer: str = "planning") -> dict:
    return sse_event("stage", stage=stage, detail=str(detail)[:200], layer=layer)


def final_result(content: str, **kwargs) -> dict:
    ev = sse_event("final_result", content=content)
    ev.update(kwargs)
    return ev


# ================================================================= #
# ClarificationManager: Pause/resume for user clarification
# ================================================================= #

class ClarificationManager:
    """Clarification layer uchun multi-turn pause/resume mexanizmi.

    Multi-turn oqim:
      1. Agent aniqlaydi: clarification kerak (1+ savol)
      2. clarify event frontend'ga yuboriladi (birinchi savol)
      3. Generator TO'XTATILADI — user javobini kutadi
      4. Frontend POST /api/chat/clarify -> javob queue'ga tushadi
      5. Agent javobni tahlil qiladi — yetarli ma'lumot bormi?
      6. Agar YETARLI -> clarification tugadi, execution boshlanadi
      7. Agar YETARLI EMAS -> yangi savol so'raydi (qayta 2-5 bosqichlari)
      8. Max 5 ta savol (cheksiz loop oldini oladi)

    Xavfsizlik:
      - Max kutish vaqti: 5 daqiqa (har bir savol uchun)
      - Max savollar soni: 5 (cheksiz loop oldini oladi)
      - Session ID orqali bog'lanadi
      - Thread-safe (queue + Lock)
    """

    MAX_QUESTIONS = 5  # Cheksiz loop oldini oladi

    def __init__(self, timeout_seconds: int = 300):
        self.timeout = timeout_seconds
        self._sessions: dict[str, dict] = {}  # session_id -> state
        self._lock = threading.Lock()

    def create_session(self, session_id: str) -> str:
        """Yangi clarification sessiyasi yaratadi. Qaytaradi: clarification_id."""
        clar_id = f"clar-{uuid.uuid4().hex[:8]}"
        with self._lock:
            self._sessions[session_id] = {
                "id": clar_id,
                "session_id": session_id,
                "question": None,
                "answer_queue": queue.Queue(),
                "answer": None,
                "status": "waiting",
                "created_at": time.time(),
                # Multi-turn tracking
                "question_number": 0,
                "history": [],  # [{"question": str, "answer": str}, ...]
                "max_questions": self.MAX_QUESTIONS,
            }
        return clar_id

    def ask(self, session_id: str, question: str) -> str:
        """Savol beradi va user javobini kutadi (blocking).

        Multi-turn: har bir ask() chaqiruvida question_number oshadi.
        Qaytaradi: user javobi yoki timeout xabari.
        """
        with self._lock:
            state = self._sessions.get(session_id)
        if state is None:
            return "(no clarification session)"

        # Max savollar soniga yetilganini tekshirish
        if state["question_number"] >= state["max_questions"]:
            state["status"] = "max_questions_reached"
            return "(max clarification questions reached)"

        state["question"] = question
        state["status"] = "awaiting_human"
        state["question_number"] += 1

        try:
            answer = state["answer_queue"].get(timeout=self.timeout)
        except queue.Empty:
            state["question"] = None
            state["status"] = "timeout"
            return "(timeout: no clarification answer received)"

        # Javobni tarixga qo'shish
        state["history"].append({
            "question": question,
            "answer": str(answer),
            "question_number": state["question_number"],
        })
        state["answer"] = str(answer)
        state["question"] = None
        state["status"] = "answered"
        return str(answer)

    def respond(self, session_id: str, answer: str) -> bool:
        """Frontend'dan kelgan javobni queue'ga tushiradi.

        Qaytaradi: True = javob qabul qilindi, False = session topilmadi.
        """
        with self._lock:
            state = self._sessions.get(session_id)
        if state is None:
            return False
        try:
            state["answer_queue"].put_nowait(answer)
            return True
        except queue.Full:
            return False

    def get_status(self, session_id: str) -> Optional[dict]:
        """Sessiya holatini qaytaradi (frontend polling uchun)."""
        with self._lock:
            state = self._sessions.get(session_id)
        if state is None:
            return None
        return {
            "id": state["id"],
            "status": state["status"],
            "question": state["question"],
            "answer": state["answer"],
            "question_number": state["question_number"],
            "history": list(state["history"]),  # copy
            "max_questions": state["max_questions"],
        }

    def get_history(self, session_id: str) -> list[dict]:
        """Sessiya tarixini qaytaradi — barcha savol/javob juftliklari."""
        with self._lock:
            state = self._sessions.get(session_id)
        if state is None:
            return []
        return list(state["history"])

    def cleanup(self, session_id: str):
        """Sessiyani tozalaydi (clarification tugagandan keyin)."""
        with self._lock:
            self._sessions.pop(session_id, None)

    def is_pending(self, session_id: str) -> bool:
        """Sessiyada javob kutilayotganini tekshiradi."""
        with self._lock:
            state = self._sessions.get(session_id)
        return state is not None and state["status"] == "awaiting_human"


# Global clarification manager (bir marta yaratiladi)
CLARIFICATION_MANAGER = ClarificationManager()


# ================================================================= #
# RepromptEngine: User prompt -> Role/Task/Purpose
# ================================================================= #

class RepromptEngine:
    """User prompt'ini qayta tahlil qiladi — rol, vazifa, maqsad aniqlanadi.

    LLM bo'lmasa deterministik fallback ishlaydi (regex asosida).
    """

    def __init__(self, llm=None):
        self.llm = llm

    def analyze(
        self,
        message: str,
        history: Optional[list] = None,
        clarification_history: Optional[list[dict]] = None,
    ) -> RepromptAnalysis:
        """User prompt'ini tahlil qiladi — RepromptAnalysis qaytaradi.

        `clarification_history` — oldingi clarification exchange'lari (memory'dan).
        Agar shu yoki o'xshash so'rov oldin kelgan va clarification berilgan bo'lsa,
        agent qayta so'rash o'rniga oldingi javobni referens qiladi.
        """
        if self.llm is not None and self.llm_available():
            return self._llm_analyze(message, history, clarification_history)
        return self._fallback_analyze(message, clarification_history)

    def _llm_analyze(
        self,
        message: str,
        history: Optional[list] = None,
        clarification_history: Optional[list[dict]] = None,
    ) -> RepromptAnalysis:
        """LLM orqali chuqur tahlil."""
        system = RE_PROMPT_SYSTEM + "\n\n" + RE_PROMPT_EXAMPLES
        prompt = f"User message: {message}"
        if history:
            recent = history[-3:]
            if recent:
                prompt += "\n\nRecent conversation context:\n"
                for h in recent:
                    prompt += f"  {h.get('role', 'user')}: {h.get('content', '')[:100]}\n"
        # Clarification history — oldingi tajribadan foydalanish
        if clarification_history:
            prompt += "\n\nPrevious clarification history (use if relevant, do NOT re-ask):\n"
            for ch in clarification_history[:3]:
                prompt += f"  Q: {ch.get('original_query', '')[:100]}\n"
                prompt += f"  Asked: {ch.get('question', '')[:100]}\n"
                prompt += f"  Answered: {ch.get('answer', '')[:100]}\n"

        try:
            text = self.llm.complete(system=system, prompt=prompt)
            if not text:
                return self._fallback_analyze(message)
            parsed = self._extract_json(text)
            if not parsed:
                return self._fallback_analyze(message)
            return RepromptAnalysis(
                role=parsed.get("role", "assistant"),
                task=parsed.get("task", ""),
                purpose=parsed.get("purpose", ""),
                capabilities_needed=parsed.get("capabilities_needed", []),
                complexity=parsed.get("complexity", "simple"),
                clarification_needed=parsed.get("clarification_needed"),
                language=parsed.get("language", "uz"),
                subject=parsed.get("subject", ""),
            )
        except Exception as exc:
            print(f"[layered][reprompt] LLM analyze failed: {exc}")
            return self._fallback_analyze(message)

    def _fallback_analyze(self, message: str, clarification_history: Optional[list[dict]] = None) -> RepromptAnalysis:
        """Deterministik fallback — regex asosida tez tahlil.

        `clarification_history` — fallback rejimida ishlatilmaydi, lekin
        LLM rejimida oldingi clarification exchange'laridan foydalaniladi.
        """
        msg = message.lower()
        lang = "uz"
        if any(w in msg for w in ("what", "how", "why", "where", "when", "which")):
            lang = "en"
        elif any(w in msg for w in ("что", "как", "почему", "где")):
            lang = "ru"

        # Capability detection
        caps = []
        complexity = "simple"

        if any(w in msg for w in ("dastur", "kod", "code", "yoz", "create", "build", "qur", "app", "ilova", "dashboard", "react", "vue", "angular", "flask", "fastapi", "django")):
            caps.append("code_write")
            complexity = "moderate"
        if any(w in msg for w in ("o'qish", "read", "ko'rish", "look")):
            caps.append("code_read")
        if any(w in msg for w in ("rasm", "chiz", "draw", "svg", "image", "picture")):
            caps.append("draw")
            complexity = "moderate"
        if any(w in msg for w in ("web", "internet", "browse", "search", "qidir", "google")):
            caps.append("web_research")
            if any(w in msg for w in ("batafsil", "deep", "tadqiqot", "research")):
                caps.append("web_browse")
        if any(w in msg for w in ("fayl", "file", "directory", "papka", "list", "sqlite", "mysql", "postgres", "redis", "mongo", "baza", "database")):
            caps.append("file_management")
        if any(w in msg for w in ("hisobla", "calculate", "analiz", "data", "stat")):
            caps.append("data_analysis")
        if any(w in msg for w in ("organib", "o'rgat", "teach", "learn", "tushuntir")):
            caps.append("web_research")

        if not caps:
            caps = ["code_read"]

        # Role detection
        role = "assistant"
        if "code_write" in caps or "file_management" in caps:
            role = "coder"
        if "draw" in caps:
            role = "artist"
        if "web_research" in caps:
            role = "researcher"
        if "data_analysis" in caps:
            role = "analyst"
        if len(caps) >= 3:
            role = "full_stack_agent"

        # Complexity bump for multi-capability
        if len(caps) >= 3:
            complexity = "complex"
        elif len(caps) >= 2 and complexity == "simple":
            complexity = "moderate"

        return RepromptAnalysis(
            role=role,
            task=message[:200],
            purpose=f"Fulfill the user's request: {message[:200]}",
            capabilities_needed=caps,
            complexity=complexity,
            clarification_needed=None,
            language=lang,
            subject="",
        )

    @staticmethod
    def llm_available(self) -> bool:
        if self.llm is None:
            return False
        try:
            return self.llm.is_available()
        except Exception:
            return False

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        """LLM chiqishidan JSON obyektini ajratib oladi."""
        text = text.strip()
        # Try direct parse
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass
        # Try finding JSON block
        import re
        m = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except (json.JSONDecodeError, TypeError):
                pass
        # Try extracting from code fence
        m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except (json.JSONDecodeError, TypeError):
                pass
        return None


# ================================================================= #
# LayerConstructor: RepromptAnalysis -> LayerPlan
# ================================================================= #

class LayerConstructor:
    """Tahlil natijasidan qatlamli rejani tuzadi."""

    def __init__(self, llm=None):
        self.llm = llm

    def construct(self, analysis: RepromptAnalysis) -> LayerPlan:
        """RepromptAnalysis -> LayerPlan."""
        if self.llm is not None and self._llm_available():
            return self._llm_construct(analysis)
        return self._fallback_construct(analysis)

    def _llm_construct(self, analysis: RepromptAnalysis) -> LayerPlan:
        """LLM orqali qatlamli reja tuzish."""
        system = LAYER_CONSTRUCTION_SYSTEM
        prompt = (
            f"Reprompt Analysis:\n"
            f"  role: {analysis.role}\n"
            f"  task: {analysis.task}\n"
            f"  purpose: {analysis.purpose}\n"
            f"  capabilities: {analysis.capabilities_needed}\n"
            f"  complexity: {analysis.complexity}\n"
            f"  language: {analysis.language}\n"
            f"  subject: {analysis.subject}\n\n"
            f"Construct the execution layers."
        )

        try:
            text = self.llm.complete(system=system, prompt=prompt)
            if not text:
                return self._fallback_construct(analysis)
            parsed = RepromptEngine._extract_json(None, text)
            if not parsed or "layers" not in parsed:
                return self._fallback_construct(analysis)

            layers = []
            for ld in parsed["layers"]:
                sub_steps = []
                for ss in ld.get("sub_steps", []):
                    sub_steps.append(LayerStep(
                        tool=ss.get("tool", ""),
                        description=ss.get("description", ""),
                        args_hint=ss.get("args_hint", ""),
                    ))
                layers.append(ExecutionLayer(
                    name=ld.get("name", ""),
                    role=ld.get("role", ""),
                    task=ld.get("task", ""),
                    tools=ld.get("tools", []),
                    depends_on=ld.get("depends_on", []),
                    streaming=ld.get("streaming", True),
                    sub_steps=sub_steps,
                ))
            return LayerPlan(
                layers=layers,
                final_accumulation=parsed.get("final_accumulation", ""),
                reprompt=analysis,
            )
        except Exception as exc:
            print(f"[layered][constructor] LLM construct failed: {exc}")
            return self._fallback_construct(analysis)

    def _fallback_construct(self, analysis: RepromptAnalysis) -> LayerPlan:
        """Deterministik fallback — qoida asosidagi qatlamli reja."""
        layers = []
        complexity = analysis.complexity
        caps = analysis.capabilities_needed

        # Layer 1: Planning (har doim)
        layers.append(ExecutionLayer(
            name="planning",
            role="planner",
            task=f"Plan the execution for: {analysis.task[:150]}",
            tools=["read_file", "list_files"],
            depends_on=[],
            streaming=True,
            sub_steps=[
                LayerStep(tool="list_files", description="Explore project structure"),
                LayerStep(tool="read_file", description="Read relevant existing files"),
            ],
        ))

        # Layer 2: Execution (asosiy ish)
        exec_tools = tools_for_capabilities(caps)
        sub_steps = []
        for tool in exec_tools[:6]:  # max 6 tools per layer
            sub_steps.append(LayerStep(
                tool=tool,
                description=TOOL_STREAMING_PROMPTS.get(
                    caps[0] if caps else "file_management",
                    "Executing {tool}..."
                ).replace("{tool}", tool),
            ))
        layers.append(ExecutionLayer(
            name="execution",
            role=analysis.role,
            task=f"Execute: {analysis.task[:150]}",
            tools=exec_tools,
            depends_on=["planning"],
            streaming=True,
            sub_steps=sub_steps,
        ))

        # Layer 3: Validation (agar complex bo'lsa)
        if complexity in ("moderate", "complex"):
            layers.append(ExecutionLayer(
                name="validation",
                role="reviewer",
                task="Verify execution results meet requirements",
                tools=["read_file", "run_command"],
                depends_on=["execution"],
                streaming=True,
                sub_steps=[
                    LayerStep(tool="read_file", description="Verify created files"),
                ],
            ))

        # Layer 4: Synthesis (har doim)
        layers.append(ExecutionLayer(
            name="synthesis",
            role="synthesizer",
            task="Accumulate all results and present final output",
            tools=[],
            depends_on=[layers[-1].name],
            streaming=True,
            sub_steps=[],
        ))

        return LayerPlan(
            layers=layers,
            final_accumulation="Combine all layer results into a coherent final answer",
            reprompt=analysis,
        )

    def _llm_available(self) -> bool:
        if self.llm is None:
            return False
        try:
            return self.llm.is_available()
        except Exception:
            return False


# ================================================================= #
# LayeredAgent: The main orchestrator
# ================================================================= #

class LayeredAgent:
    """Qatlamli agentic loop — re-prompt -> layers -> streaming -> synthesis.

    Mavjud IgrisAgent ga bog'lanadi — uni wrapper sifatida ishlatadi:
      - RepromptEngine: prompt tahlili
      - LayerConstructor: qatlamli reja
      - IgrisAgent.chat_stream(): asosiy bajaruvchi (tool'lar, LLM)
      - Har bir qatlam SSE eventlari orqali streaming
    """

    def __init__(self, agent=None, llm=None):
        """
        Args:
            agent: IgrisAgent instance (asosiy bajaruvchi)
            llm: OllamaClient (reprompt + layer construction uchun)
        """
        self.agent = agent
        self.llm = llm or (getattr(agent, "llm", None) if agent else None)
        self.reprompt_engine = RepromptEngine(llm=self.llm)
        self.layer_constructor = LayerConstructor(llm=self.llm)

    def run_layered(
        self,
        message: str,
        history: Optional[list[dict]] = None,
        use_memory: bool = True,
        progress_cb: Optional[Callable] = None,
        session_id: str = "",
    ) -> Generator[dict, None, None]:
        """To'liq qatlamli agentic loop — generator orqali SSE eventlari.

        Har bir qatlam:
          1. layer_start event
          2. Tool/MCP/skill boshlanishi/tugashi streaming
          3. Token streaming (intermediate results)
          4. layer_done event

        Yakunda:
          5. final_result event (barcha natijalar yig'ildi)

        Clarification flow:
          - Agar clarification kerak bo'lsa, clarify event yuboriladi
          - Generator bloklanadi (threading.Event) — user javobini kutadi
          - Frontend POST /api/chat/clarify -> javob qabul qilinadi
          - Generator davom etadi (clarified context bilan)
        """
        t0 = time.perf_counter()
        all_layer_results: dict[str, Any] = {}
        sid = session_id or f"layered-{uuid.uuid4().hex[:8]}"

        # ── STEP 1: RE-PROMPT ──
        yield stage_event("analyze", "Prompt tahlil qilinmoqda...", layer="meta")
        # Oldingi clarification exchange'larini xotiradan topish (kelajakda referens)
        clarification_history = []
        if self.agent is not None and hasattr(self.agent, 'memory') and self.agent.memory:
            try:
                clarification_history = self.agent.memory.get_clarification_history(message)
            except Exception:
                clarification_history = []
        analysis = self.reprompt_engine.analyze(message, history, clarification_history)

        # Clarification check — MULTI-TURN PAUSE/RESUME flow
        clarified_message = message
        clarification_exchanges = []  # [{"question": str, "answer": str}, ...]
        if analysis.clarification_needed:
            yield layer_start("clarification")
            CLARIFICATION_MANAGER.create_session(sid)

            # Multi-turn loop: agent savol beradi, user javob beradi,
            # agent yetarli ma'lumot borligini tekshiradi
            max_turns = ClarificationManager.MAX_QUESTIONS
            current_question = analysis.clarification_needed

            for turn in range(max_turns):
                if not current_question:
                    break

                # Stream: savol
                yield stage_event(
                    "clarify",
                    f"[Turn {turn + 1}/{max_turns}] {current_question}",
                    layer="clarification",
                )
                yield sse_event(
                    "clarify",
                    question=current_question,
                    session_id=sid,
                    turn=turn + 1,
                    max_turns=max_turns,
                )

                # User javobini kutish (blocking)
                user_answer = CLARIFICATION_MANAGER.ask(sid, current_question)

                if not user_answer or user_answer.startswith("("):
                    # Timeout yoki xato — loopdan chiqish
                    yield token_event(
                        f"Clarification timeout/no answer — proceeding with gathered info",
                        source="system",
                    )
                    break

                # Javobni saqlash
                clarification_exchanges.append({
                    "question": current_question,
                    "answer": user_answer,
                    "turn": turn + 1,
                })
                yield token_event(f"User: {user_answer}", source="user")

                # Clarification history ni xotiraga saqlash (kelajakda referens uchun)
                if self.agent is not None and hasattr(self.agent, 'memory') and self.agent.memory:
                    try:
                        self.agent.memory.remember_clarification(
                            original_query=message,
                            question=current_question,
                            answer=user_answer,
                            session_id=sid,
                        )
                    except Exception as mem_exc:
                        print(f"[layered][clarification] memory save failed: {mem_exc}")

                # Yig'ilgan javoblar bilan qayta tahlil
                clarification_text = "\n".join(
                    f"  Q: {e['question']}\n  A: {e['answer']}"
                    for e in clarification_exchanges
                )
                clarified_message = f"{message}\n\nClarification exchanges:\n{clarification_text}"
                analysis = self.reprompt_engine.analyze(clarified_message, history)

                # Keyingi savol kerakligini tekshirish
                if not analysis.clarification_needed:
                    # Yetarli ma'lumot to'plandi
                    yield token_event(
                        f"Clarification complete — gathered {len(clarification_exchanges)} pieces of info",
                        source="system",
                    )
                    break

                # Keyingi savolga tayyorlanish
                current_question = analysis.clarification_needed

            # Clarification layer yakuni
            total = len(clarification_exchanges)
            yield layer_done(
                "clarification",
                status="complete" if total > 0 else "timeout",
                questions_asked=total,
                exchanges=clarification_exchanges,
            )

            CLARIFICATION_MANAGER.cleanup(sid)

        # ── STEP 2: LAYER CONSTRUCTION ──
        yield stage_event("plan", f"Building {analysis.complexity} execution plan...", layer="planning")
        plan = self.layer_constructor.construct(analysis)
        yield layer_start("planning")
        yield stage_event("plan", f"Qatlamli reja tuzildi: {len(plan.layers)} qatlam", layer="planning")
        yield layer_done("planning", status="complete",
                         plan={"layers": [l.name for l in plan.layers],
                               "reprompt": {"role": analysis.role,
                                            "task": analysis.task[:100],
                                            "purpose": analysis.purpose[:100],
                                            "complexity": analysis.complexity}})

        # ── STEP 3: LAYER-BY-LAYER EXECUTION ──
        for layer in plan.layers:
            yield layer_start(layer.name)
            yield stage_event(
                "execute",
                f"[{layer.name}] {layer.task[:100]}",
                layer=layer.name,
            )

            layer_result = yield from self._execute_layer(
                layer, message, analysis, all_layer_results,
                history=history, use_memory=use_memory,
            )
            all_layer_results[layer.name] = layer_result

            yield layer_done(
                layer.name,
                status="complete",
                summary=str(layer_result)[:300] if layer_result else "done",
            )

        # ── STEP 4: SYNTHESIS ──
        yield layer_start("synthesis")
        yield stage_event("synthesize", "Barcha natijalar yig'ilmoqda...", layer="synthesis")

        final_text = yield from self._synthesize(
            plan, analysis, all_layer_results,
            message=message, history=history,
        )

        yield layer_done("synthesis", status="complete")

        # ── STEP 5: FINAL RESULT ──
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        yield final_result(
            final_text,
            duration_ms=duration_ms,
            layers_executed=[l.name for l in plan.layers],
            reprompt={"role": analysis.role, "complexity": analysis.complexity},
            tool_calls=self._collect_tool_calls(all_layer_results),
        )

    def _execute_layer(
        self,
        layer: ExecutionLayer,
        original_message: str,
        analysis: RepromptAnalysis,
        previous_results: dict[str, Any],
        history: Optional[list] = None,
        use_memory: bool = True,
    ) -> Generator[dict, None, Any]:
        """Bir qatlamni bajaradi — har bir sub_step uchun streaming.

        Natijani qaytaradi (keyingi layer uchun context).
        """
        if layer.name == "synthesis":
            # Synthesis layer is handled separately in _synthesize
            return None

        layer_result_parts = []
        tools_used = []

        for sub_step in layer.sub_steps:
            tool_name = sub_step.tool
            if not tool_name:
                continue

            # ── Stream: tool boshlandi ──
            is_mcp = "__" in tool_name and not tool_name.startswith("art__")
            is_skill = tool_name == "use_skill"

            if is_mcp:
                yield mcp_start(tool_name, layer.name, sub_step.description)
            elif is_skill:
                yield skill_start(tool_name, layer.name, sub_step.description)
            else:
                yield tool_start(tool_name, layer.name, sub_step.description)

            # Stream: description token
            desc = sub_step.description or f"Using {tool_name}"
            yield token_event(f"\n🔧 [{layer.name}] {desc}...", source=tool_name)

            # ── Execute the tool via agent ──
            tool_result = self._invoke_tool(
                tool_name, sub_step, original_message, analysis,
                previous_results, layer.name,
            )

            tools_used.append(tool_name)

            # ── Stream: tool natijasi ──
            result_preview = ""
            if isinstance(tool_result, dict):
                result_preview = str(tool_result.get("output", tool_result.get("content", "")))[:200]
            elif isinstance(tool_result, str):
                result_preview = tool_result[:200]
            else:
                result_preview = str(tool_result)[:200] if tool_result else ""

            if result_preview:
                yield token_event(f"  ✅ {result_preview}", source=tool_name)

            if is_mcp:
                yield mcp_done(tool_name, layer.name, result_preview)
            elif is_skill:
                yield skill_done(tool_name, layer.name, result_preview)
            else:
                yield tool_done(tool_name, layer.name, result_preview)

            layer_result_parts.append({
                "tool": tool_name,
                "description": sub_step.description,
                "result": tool_result,
            })

        # Layer summary token
        summary = f"\n✅ [{layer.name}] Bajarildi — {len(layer_result_parts)} amal"
        yield token_event(summary, source=layer.name)

        return {
            "layer": layer.name,
            "role": layer.role,
            "tools_used": tools_used,
            "parts": layer_result_parts,
            "summary": summary,
        }

    def _invoke_tool(
        self,
        tool_name: str,
        sub_step: LayerStep,
        original_message: str,
        analysis: RepromptAnalysis,
        previous_results: dict[str, Any],
        layer_name: str,
    ) -> Any:
        """Bitta tool'ni chaqiradi — agent orqali yoki to'g'ridan-to'g'ri.

        Bu yerda ACTUAL tool execution sodir bo'ladi.
        Agent mavjud bo'lmasa, mock result qaytariladi.
        """
        # Agar agent mavjud bo'lsa — uning orqali bajariladi
        if self.agent is not None:
            try:
                return self._invoke_via_agent(
                    tool_name, sub_step, original_message,
                    analysis, previous_results, layer_name,
                )
            except Exception as exc:
                print(f"[layered][tool] {tool_name} failed: {exc}")
                return {"error": str(exc), "tool": tool_name}

        # Agent yo'q — mock result
        return {
            "tool": tool_name,
            "status": "simulated",
            "message": f"Tool {tool_name} would be invoked here",
            "layer": layer_name,
        }

    def _invoke_via_agent(
        self,
        tool_name: str,
        sub_step: LayerStep,
        original_message: str,
        analysis: RepromptAnalysis,
        previous_results: dict[str, Any],
        layer_name: str,
    ) -> Any:
        """Agent orqali tool'ni chaqiradi.

        Turkum:
          1. Tool schema'sini topadi
          2. Argumentlarni LLM yordamida generatsiya qiladi
          3. Tool'ni chaqiradi
          4. Natijani qaytaradi
        """
        # Tool registry'dan tool'ni topish
        registry = getattr(self.agent, "_registry", None)
        if registry is None:
            registry = getattr(self.agent, "registry", None)

        # MCP tool
        mcp = getattr(self.agent, "_mcp", None)
        if mcp is not None and callable(mcp):
            mcp = mcp()
        if mcp is not None and hasattr(mcp, "tool_index") and tool_name in mcp.tool_index:
            return self._invoke_mcp_tool(mcp, tool_name, sub_step, original_message, analysis)

        # Native tool (registry)
        if registry is not None and hasattr(registry, "get"):
            tool_obj = registry.get(tool_name)
            if tool_obj is not None:
                return self._invoke_native_tool(
                    tool_obj, tool_name, sub_step, original_message, analysis, previous_results
                )

        # art__ MCP tools
        if mcp is not None and hasattr(mcp, "tool_index"):
            for key in mcp.tool_index:
                if key == tool_name or key.endswith("__" + tool_name):
                    return self._invoke_mcp_tool(mcp, key, sub_step, original_message, analysis)

        return {"tool": tool_name, "status": "not_found", "message": f"Tool {tool_name} not available"}

    def _invoke_mcp_tool(
        self, mcp, tool_name: str, sub_step: LayerStep,
        original_message: str, analysis: RepromptAnalysis,
    ) -> Any:
        """MCP tool'ni chaqiradi — LLM yordamida argument generatsiya qiladi."""
        tool_info = mcp.tool_index.get(tool_name, {})
        schema = tool_info.get("schema", {})

        # LLM yordamida args generatsiya
        args = {}
        if self.llm is not None:
            try:
                args = self._generate_tool_args(
                    tool_name, schema, original_message, analysis
                )
            except Exception:
                pass

        # MCP call
        try:
            if hasattr(mcp, "call"):
                return mcp.call(tool_name, args)
            elif hasattr(mcp, "call_tool"):
                return mcp.call_tool(tool_name, args)
        except Exception as exc:
            return {"error": str(exc), "tool": tool_name, "args": args}

        return {"tool": tool_name, "args": args, "status": "mcp_call_not_implemented"}

    def _invoke_native_tool(
        self, tool_obj, tool_name: str, sub_step: LayerStep,
        original_message: str, analysis: RepromptAnalysis,
        previous_results: dict[str, Any],
    ) -> Any:
        """Native tool'ni chaqiradi — LLM yordamida argument generatsiya qiladi."""
        schema = {}
        if hasattr(tool_obj, "schema"):
            schema = tool_obj.schema
        elif hasattr(tool_obj, "to_schema"):
            try:
                schema = tool_obj.to_schema()
            except Exception:
                pass

        # LLM yordamida args generatsiya
        args = {}
        if self.llm is not None:
            try:
                args = self._generate_tool_args(
                    tool_name, schema, original_message, analysis
                )
            except Exception:
                pass

        # Tool call
        try:
            if hasattr(tool_obj, "run"):
                return tool_obj.run(**args)
            elif hasattr(tool_obj, "__call__"):
                return tool_obj(**args)
        except Exception as exc:
            return {"error": str(exc), "tool": tool_name, "args": args}

        return {"tool": tool_name, "args": args, "status": "native_call_not_implemented"}

    def _generate_tool_args(
        self, tool_name: str, schema: dict,
        original_message: str, analysis: RepromptAnalysis,
    ) -> dict:
        """LLM yordamida tool argumentlarini generatsiya qiladi."""
        if self.llm is None:
            return {}

        system = (
            f"You are generating arguments for the tool '{tool_name}'.\n"
            f"Original user request: {original_message[:300]}\n"
            f"Agent role: {analysis.role}\n"
            f"Tool purpose: {analysis.task[:200]}\n\n"
            f"Tool schema: {json.dumps(schema, ensure_ascii=False)[:1000]}\n\n"
            "Generate the exact JSON arguments for this tool call. "
            "Use real paths relative to the workspace. "
            "Reply with ONLY valid JSON object of arguments."
        )

        try:
            text = self.llm.complete(system=system, prompt="Generate tool arguments:")
            if text:
                parsed = RepromptEngine._extract_json(None, text)
                if isinstance(parsed, dict):
                    return parsed
        except Exception:
            pass
        return {}

    def _synthesize(
        self,
        plan: LayerPlan,
        analysis: RepromptAnalysis,
        all_results: dict[str, Any],
        message: str = "",
        history: Optional[list] = None,
    ) -> Generator[dict, None, str]:
        """Barcha qatlam natijalarini yig'adi va final javob generatsiya qiladi.

        LLM bo'lsa — u orqali formatlangan javob.
        Bo'lmasa — to'plangan natijalardan tuzilgan xulosa.
        """
        # Accumulate all results
        accumulated = []
        for layer_name, result in all_results.items():
            if result is None:
                continue
            accumulated.append(f"### {layer_name.upper()} LAYER RESULT:")
            if isinstance(result, dict):
                for part in result.get("parts", []):
                    accumulated.append(f"  - Tool: {part.get('tool', 'unknown')}")
                    accumulated.append(f"    Result: {str(part.get('result', ''))[:300]}")
                accumulated.append(f"  Summary: {result.get('summary', '')}")
            else:
                accumulated.append(f"  {str(result)[:500]}")

        context = "\n".join(accumulated)

        if self.llm is not None:
            try:
                system = FINAL_SYNTHESIS_SYSTEM
                prompt = (
                    f"User request: {message[:500]}\n"
                    f"Agent role: {analysis.role}\n"
                    f"Task: {analysis.task[:200]}\n"
                    f"Purpose: {analysis.purpose[:200]}\n"
                    f"Language: {analysis.language}\n\n"
                    f"Layer results:\n{context[:3000]}\n\n"
                    f"Synthesize the final answer."
                )

                # Stream the synthesis
                full_text = ""
                think_stream = getattr(self.llm, "think", False)
                for ev in self.llm.chat_stream_rich(
                    [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                    think=think_stream,
                ):
                    delta = ev.get("content") or ""
                    if not delta:
                        continue
                    if ev.get("type") == "think":
                        yield token_event(delta, source="synthesis-thinking")
                    else:
                        full_text += delta
                        yield token_event(delta, source="synthesis")

                if full_text.strip():
                    return full_text.strip()
            except Exception as exc:
                print(f"[layered][synthesis] LLM synthesis failed: {exc}")

        # Fallback: construct from accumulated results
        lines = [f"✅ **{analysis.role.replace('_', ' ').title()}** — {analysis.purpose}\n"]
        for layer_name, result in all_results.items():
            if result is None:
                continue
            lines.append(f"**{layer_name.title()} layer:**")
            if isinstance(result, dict):
                tools = result.get("tools_used", [])
                if tools:
                    lines.append(f"  Tools used: {', '.join(tools)}")
                parts = result.get("parts", [])
                for part in parts:
                    r = str(part.get("result", ""))[:150]
                    if r and r != "None":
                        lines.append(f"  - {part.get('tool', '')}: {r}")
                summary = result.get("summary", "")
                if summary:
                    lines.append(f"  {summary}")
            lines.append("")

        fallback_text = "\n".join(lines)
        # Stream fallback text
        for i in range(0, len(fallback_text), 50):
            chunk = fallback_text[i:i+50]
            yield token_event(chunk, source="synthesis")
        return fallback_text

    def _collect_tool_calls(self, all_results: dict[str, Any]) -> list[dict]:
        """Barcha qatlam natijalaridan tool call ro'yxatini yig'adi."""
        calls = []
        for layer_name, result in all_results.items():
            if result is None:
                continue
            if isinstance(result, dict):
                for part in result.get("parts", []):
                    calls.append({
                        "tool": part.get("tool", ""),
                        "layer": layer_name,
                        "description": part.get("description", ""),
                    })
        return calls


# ================================================================= #
# Convenience: create layered agent from IgrisAgent
# ================================================================= #

def create_layered_agent(agent) -> LayeredAgent:
    """IgrisAgent dan LayeredAgent yaratadi."""
    return LayeredAgent(
        agent=agent,
        llm=getattr(agent, "llm", None),
    )
