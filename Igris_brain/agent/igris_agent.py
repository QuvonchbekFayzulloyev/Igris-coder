"""
IGRIS CODER AGENT — Main Orchestrator
=====================================
Hybrid engine:
  1. Deterministic: bricks + knowledge + constraint resolver (<10ms)
  2. Healing:     reconstruct missing capability chains
  3. Hybrid LLM:  Ollama fallback for complex / low-confidence queries
  4. Memory/RAG:  Igris_Memory bridge — recall before, remember after

Reference (plan, igris_brick_knowledge):
    Query: 'matritsani teskari top' [uz -> code]
    Status: ✓  Confidence: 0.902  Chains: ['chain_math']
    Output: np.linalg.inv(matrix)
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.brick_system import BrickBank
from core.knowledge_system import KnowledgeBank, build_default_knowledge, build_default_bricks
from resolver.constraint_resolver import ConstraintResolver, Resolution
from chains.chain_system import (
    ChainRegistry,
    ChainHealer,
    build_default_chains,
)
from llm.ollama_client import OllamaClient
from setup.refactor_machine import RefactorMachine
from agent.memory_bridge import MemoryBridge
from state.context_budget import ContextBudget
from core.intelligence import IntelligenceCore
from core.intelligence.logic import extract_balanced_json
from core.requirements import Requirement, RequirementExtractor
from core.request_meaning import assist_fields, parse_request_meaning

# S5 modullashtirish: tez yo'llar (math/weather) va veb strategiya alohida
# modullarda — agent metodlari delegatsiya qiladi. Web prompt matnlari
# (GUIDE/HINTS) ham web_strategy.py'da — moslik uchun eksport qilinadi.
import agent.quick_paths as quick_paths_mod
import web.web_strategy as web_strategy_mod
from web.web_strategy import WEB_TOOLS_GUIDE, WEB_TOOL_HINTS  # noqa: F401

# S5: delegatsiya quick_paths_mod / web_strategy_mod modul-atributlari orqali
# (yuqoridagi importlar). igris_quick.py — quick_paths fasadi (compat qatlam).


# Chat uchun ish maydoni — UI workspace daraxti bilan bir xil (preview ishlashi uchun)
DEFAULT_WORKSPACE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")

# Chat ham REAL tool'lar bilan ishlaydi: model "rasm chiza olmayman" deyishi
# shart emas — chizmani O'ZI yaratadi (art__draw_custom_svg) yoki tayyor
# shablonlarni ishlatadi.
CHAT_TOOLS_SYSTEM = (
    "=== IGRIS CORE PROMPT v2 ===\n\n"
    "IDENTITY: You are Igris — a local agentic coding assistant. You have REAL "
    "tools that CREATE files, GENERATE images, RUN code, and ACCESS the web. "
    "NEVER say 'I cannot' or 'I don't have tools'. You DO. Act on every request.\n\n"
    "PIPELINE: For every request, follow this pattern:\n"
    "  1. UNDERSTAND — Parse the request. What exactly is needed? What language?\n"
    "  2. PLAN — Which tools will you use? (see TOOL MAP below)\n"
    "  3. EXECUTE — Call the tools. Do the work. Create files. Draw images.\n"
    "  4. VERIFY — Did it work? If error, fix it. If incomplete, finish it.\n"
    "  5. RESPOND — One short sentence about what you did. File path if created.\n\n"
    "TOKEN EFFICIENCY (CRITICAL):\n"
    "  - NEVER output long explanations before doing work — DO FIRST, explain after.\n"
    "  - NEVER repeat the user's request back to them.\n"
    "  - NEVER say 'I will now...' or 'Let me...' — just DO it.\n"
    "  - After creating a file, respond in ONE sentence: what was created + path.\n"
    "  - For code: show the RESULT, not the process. Working code > long explanation.\n"
    "  - For drawings: 'File created: duck.svg' — no code dump.\n"
    "  - For questions: answer directly. No preamble.\n\n"
    "TOOL MAP (use the RIGHT tool for the job):\n\n"
    "  DRAWING (user asks for image/picture/rasm/chiz):\n"
    "    ANY subject -> art__draw_custom_svg (svg, output, style, size)\n"
    "      style: cartoon | realistic | flat | child | bw | fantasy | anime\n"
    "      size: standard | icon | avatar | card | poster | banner | WxH\n"
    "      viewBox matches size (poster=1080x1920, icon=256x256, standard=512x512)\n"
    "    Canned subjects (apple/house/tree/cat/star/heart/car/rocket/flower/\n"
    "      mountain/sun/moon/bird/fish/butterfly/mushroom/ball/camel/dog/owl/\n"
    "      duck/robot/plane) ->\n"
    "      art__draw_scene_svg (subject, output, color, texture, style, size)\n"
    "    UI mockups -> art__draw_ui_svg (app, output, theme, texture)\n"
    "    Interactive apps (dashboard/todo/login/profile/calculator) ->\n"
    "      art__ui_build_spec (app, output, theme) — output must end .uibuild.json\n\n"
    "  CODE (user asks for script/program/app/dastur/kod):\n"
    "    Write code: write_file(path, content)\n"
    "    Edit existing: apply_patch(path, patch)\n"
    "    Run/verify: python_exec(code) or run_command(command)\n"
    "    List workspace: list_files(path)\n"
    "    Quality: write COMPLETE working code, then RUN it to verify. Fix errors.\n\n"
    "  FILE ARTIFACTS (user asks for an office, diagram, engineering, or audio file):\n"
    "    DOCX report -> artifact__create_document, PPTX slides -> artifact__create_presentation,\n"
    "    XLSX table -> artifact__create_spreadsheet, PDF -> artifact__create_pdf.\n"
    "    Flow diagram -> artifact__create_diagram; 3D -> artifact__create_3d_model or\n"
    "    artifact__create_openscad_model; electronics -> artifact__create_kicad_pcb or\n"
    "    artifact__create_kicad_schematic; audio cue -> artifact__create_audio_tone.\n"
    "    ALWAYS call artifact__validate_artifact after creating one. Never claim an\n"
    "    artifact exists unless the creation and validation tool both succeeded.\n\n"
    "  WEB (user asks to browse/research/fetch a page):\n"
    "    Read page text: web_fetch(url) — fast, no browser needed\n"
    "    Download image: web_search_image(query) — saves to workspace\n"
    "    Browse interactive pages: web_ai_bridge__browser_navigate(url)\n"
    "      then web_ai_bridge__browser_get_text() to read content\n"
    "    Delegate research: ask_web_ai or web_ai_start_research\n\n"
    "  CONVERSATION (ordinary questions, no file/image needed):\n"
    "    Answer directly. No tools. Be concise. Match the user's language.\n"
    "    (uz = Uzbek, en = English, ru = Russian — detect from their message)\n\n"
    "AGENTIC LOOP (when tools are involved):\n"
    "  - Call tool -> check result -> if error, fix and retry -> if done, respond\n"
    "  - MAX 6 rounds for code/drawing, MAX 8 for web browsing\n"
    "  - NEVER give up. If art__draw_scene_svg rejects subject -> use art__draw_custom_svg\n"
    "  - If write_file fails -> check path, fix, retry\n"
    "  - If model says 'I cannot' -> STOP TALKING. Call the tool."
)


# art__ tool'lariga ham schema-darajadagi QISQA ko'rsatma — model qaysi
# chizish vositasini QACHON tanlashni biladi (draw_custom_svg bosh, scene/UI
# tezkor varianti, ui_build_spec interaktiv ekranlar uchun).
ART_TOOL_HINTS: dict = {
    "art__draw_custom_svg": (
        "MAIN drawing tool - use for ANY image the user requests (objects, "
        "scenes, logos, posters, avatars): YOU are the artist, generate the "
        "full <svg> markup yourself and pass style='cartoon|realistic|flat' "
        "and size='standard|icon|avatar|card|poster|banner'. There is NO fixed "
        "subject list."),
    "art__draw_scene_svg": (
        "Quick layered SCENE for known simple objects (apple, house, tree, cat, "
        "star, heart, car, rocket, flower, mountain, sun, moon, bird, fish, "
        "butterfly, mushroom, ball, camel, dog, owl, duck, robot, plane). "
        "For anything else use draw_custom_svg."),
    "art__draw_object_png": (
        "Legacy canned PNG drawing of a simple object (raster, not SVG). Prefer "
        "draw_custom_svg or draw_scene_svg for vector quality; use this only "
        "when the user explicitly wants a PNG/raster picture."),
    "art__draw_ui_svg": (
        "STATIC UI/UX mockup screen as layered SVG (app, theme, texture). Use "
        "for a visual mockup/wireframe. For a REAL interactive screen use "
        "ui_build_spec instead."),
    "art__ui_build_spec": (
        "REAL INTERACTIVE UI screen (dashboard, todo app, settings, ...): "
        "produces a .uibuild.json that the frontend renders as a live-build "
        "preview with working widgets. Output must end in .uibuild.json. Use "
        "for apps/screens the user can actually interact with."),
    "art__list_subjects": "List the objects the canned scene/drawing tools can render.",
}

# Qisqa MCP schema-hintlar: Office/diagram/engineering tool'lari model
# tanlovida aniq ko'rinadi.  Bular faqat yordamchi tavsif; haqiqiy parametr
# shartnomasi MCP server schema'sidan olinadi.
ARTIFACT_TOOL_HINTS: dict = {
    "artifact__create_document": "Create a real, locally saved DOCX report or document.",
    "artifact__create_presentation": "Create a real PPTX presentation; use for slides, PowerPoint, taqdimot.",
    "artifact__create_spreadsheet": "Create a real XLSX workbook from structured table rows.",
    "artifact__create_pdf": "Create a real PDF report locally.",
    "artifact__create_diagram": "Create a real SVG flow diagram from nodes and A -> B edges.",
    "artifact__create_3d_model": "Create a real ASCII STL cube or pyramid mesh.",
    "artifact__create_openscad_model": "Save a real parametric OpenSCAD .scad model.",
    "artifact__create_kicad_pcb": "Create a KiCad .kicad_pcb starter board with footprints.",
    "artifact__create_kicad_schematic": "Create a KiCad .kicad_sch starter schematic.",
    "artifact__create_audio_tone": "Create a real WAV audio cue; it is a tone, not synthetic speech.",
    "artifact__validate_artifact": "Validate an artifact after creation. Required before claiming completion.",
}


# ---------------------------------------------------------------------- #
# STACK REJALARI — framework/til aniqlanganda tool rejasi + buyruq qo'llanmasi
# ---------------------------------------------------------------------- #
# Kod so'rovida framework/til topilsa (`_detect_code_stack`):
#   - `_planned_tools` shu stack'ga mos vositalarni rejalaydi
#     (React -> read/write/list/run_command — npm shu terminal orqali ishlaydi),
#   - `_stack_guide` modelga ANIQ buyruqlarni system prompt orqali yetkazadi
#     (npm install, npx webpack, manage.py runserver...).
# Alohida npm/webpack tool'i KERAK EMAS — run_command terminal vositasi yetarli,
# faqat modelga qanday buyruq kerakligi aytilishi shart.

# S5: STACK_PLANS/FRAMEWORK_STACK/ORM_STACK/LANG_STACK/DB_STACK/
# DB_DISPLAY_SUFFIX statik jadvallari agent_stack_data.py'da (yagona manba) —
# shu nomlar bilan qayta eksport qilinadi (testlar/klass attributlari mosligi).
from agent.agent_stack_data import (  # noqa: E402, F401
    STACK_PLANS, FRAMEWORK_STACK, ORM_STACK, LANG_STACK, DB_STACK, DB_DISPLAY_SUFFIX,
)
import agent.request_classifier as request_classifier  # S5: deterministik klassifikatsiya (yagona manba)
import agent.agent_stack_data as agent_stack_data  # noqa: F401  (S5: stack jadvallari — qayta eksport uchun)

# ---------------------------------------------------------------------- #
# INTELLEKT 2.2 — xavfsiz arifmetika so'rovi detektori (tez deterministik yo'l)
# ---------------------------------------------------------------------- #

# S5: quick_paths.py'ga ko'chirildi — moslik uchun alias (tashqi foydalanuvchilar).
MATH_EXPR_RE = quick_paths_mod.MATH_EXPR_RE
MATH_PREFIX_RE = quick_paths_mod.MATH_PREFIX_RE

# S5: markerlar request_classifier.py'da (yagona manba) — alias sifatida
# saqlanadi (tashqi importlar/eski havolalar buzilmasin).
STRUCTURE_REQUEST_WORDS = request_classifier.STRUCTURE_REQUEST_WORDS

# INTELLEKT 2.11 — kreativ so'rov markerlari (multi-candidate generatsiya)
CREATIVE_REQUEST_WORDS = request_classifier.CREATIVE_REQUEST_WORDS


# ---------------------------------------------------------------------- #
# AGENTIK PIPELINE REGISTRY — zarurat turi -> pipeline spetsifikatsiyasi
# ---------------------------------------------------------------------- #
# chat()/chat_stream() so'rovni klassifikatsiya qiladi va SHU jadval asosida
# agentik pipeline'ni tanlab QUradi: qaysi bosqichlar (PipelineStepper uchun),
# qaysi dvigatel ishlaydi. Bir nechta zarurat birlashgan bo'lsa (masalan
# "rasm chiz va kod yoz") `_build_pipeline` qo'shimcha (sub) pipeline'larni
# ham generatsiya qiladi — foydalanuvchi pipeline BIRINCHI quriladi.
#
# Oxirida bajarilgan ish `data["completion"]` sifatida konversatsiyaga
# to'ldiriladi (server chat_history.jsonl'ga ham yozadi).

# ------------------------------------------------------------------
# PIPELINE_SPECS — loop reestri (agentic architecture §3.1 + §3.2)
# ------------------------------------------------------------------
# Har bir kirish = bitta Loop. fieldlar:
#   stages      — pipeline bosqichlari (plan → ... → review)
#   engine      — LLM tipi (llm / llm+tools / math-quick / weather-quick)
#   loop_shape  — iteratsiya shakli (§3.2):
#       straight_through    — 1 marta ishlaydi, chiqish
#       react_iterative     — think → act → observe, max_iter marta
#       plan_then_execute   — bir marta rejalash, keyin ketma-ket bosqichlar
#       build_verify        — edit → review (deterministik) → repair, max_repair marta
#       reflexion_critique  — generate → self-critique → retry, max_repair marta
#   max_iter    — loop-shape iteratsiya cheklovi (react/build_verify uchun)
#   max_repair  — review bosqichi retry cheklovi (build_verify/reflexion uchun)
# ------------------------------------------------------------------
PIPELINE_SPECS: dict = {
    # -- chat-family (javob o'zi matn) ------------------------------------------
    "chat": {
        "label": "Suhbat (to'g'ridan-to'g'ri javob)",
        "stages": ["plan", "review"],
        "engine": "llm",
        "loop_shape": "react_iterative",
        "max_iter": 8,
        "max_repair": 0,
    },
    "math": {
        "label": "Hisob / mantiq",
        "stages": ["plan", "review"],
        "engine": "math-quick",
        "loop_shape": "straight_through",
        "max_iter": 1,
        "max_repair": 0,
    },
    "weather": {
        "label": "Ob-havo",
        "stages": ["plan", "review"],
        "engine": "weather-quick",
        "loop_shape": "straight_through",
        "max_iter": 1,
        "max_repair": 0,
    },
    "creative": {
        "label": "Kreativ variantlar",
        "stages": ["plan", "review"],
        "engine": "llm",
        "loop_shape": "reflexion_critique",
        "max_iter": 1,
        "max_repair": 3,
    },
    "structure": {
        "label": "Loyiha strukturasi",
        "stages": ["plan", "read", "review"],
        "engine": "llm",
        "loop_shape": "react_iterative",
        "max_iter": 8,
        "max_repair": 0,
    },
    # -- creator-family (artifact ishlab chiqaradi) ------------------------------
    "draw": {
        "label": "Chizma / SVG",
        "stages": ["plan", "edit", "review"],
        "engine": "llm+tools",
        "loop_shape": "build_verify",
        "max_iter": 8,
        "max_repair": 3,
    },
    "ui_build": {
        "label": "UI qurish (uibuild)",
        "stages": ["plan", "read", "edit", "test", "review"],
        "engine": "llm+tools",
        "loop_shape": "plan_then_execute",
        "max_iter": 1,
        "max_repair": 0,
    },
    "web": {
        "label": "Veb tadqiqot",
        "stages": ["plan", "read", "review"],
        "engine": "llm+tools",
        "loop_shape": "react_iterative",
        "max_iter": 8,
        "max_repair": 0,
    },
    "code": {
        "label": "Kod vazifasi",
        "stages": ["plan", "read", "edit", "test", "review"],
        "engine": "llm+tools",
        "loop_shape": "build_verify",
        "max_iter": 8,
        "max_repair": 3,
    },
    "file_task": {
        "label": "Fayl vazifasi (o'qish/tahrirlash)",
        "stages": ["plan", "read", "edit", "review"],
        "engine": "llm+tools",
        "loop_shape": "plan_then_execute",
        "max_iter": 1,
        "max_repair": 0,
    },
    "composition": {
        "label": "Kompozitsiya (qatlamli qurish)",
        "stages": ["plan", "read", "edit", "test", "review"],
        "engine": "llm+tools",
        "loop_shape": "plan_then_execute",
        "max_iter": 1,
        "max_repair": 0,
    },
}


def _tool_desc_with_hint(schema: dict, hint: Optional[str]) -> str:
    """Schema description'iga 'WHEN TO USE' hint'ini qo'shadi (web+art DRY).

    Base 350 belgigacha cheklanadi, hint esa TO'LIQ saqlanadi (hintlar ~300
    belgidan oshmasa umumiy cap 800 ichida hint o'rtasidan kesilmaydi).
    """
    desc = (schema.get("description") or "")[:350]
    if hint:
        desc = (desc + "\n\nWHEN TO USE: " + hint)[:800]
    return desc


def _drawing_quality_tip(report: dict) -> str:
    """Validator hisobotidan eng zaif jihatlar uchun amaliy takliflar tuzadi.

    Xotiradagi CHIZMA SIFATI yozuviga qo'shiladi — RAG recall'da model
    keyingi chizishda aynan nimani yaxshilashni ko'radi (svg-artist skill
    qoidalariga asoslangan).
    """
    weak = {c.get("name") for c in report.get("checks") or [] if not c.get("ok")}
    style = (report.get("meta") or {}).get("style_comment") or "cartoon"
    tips: list[str] = []
    # flat uslubda gradient/soya bo'lmasligi TO'G'RI — bu uslubda 'qo'shish'
    # taklifi berilmaydi (aks holda modelga zid ko'rsatma ketardi).
    if "gradient" in weak and style != "flat":
        tips.append("asosiy tanaga gradient (linear/radial) qo'shish")
    if "soya" in weak and style != "flat":
        tips.append("yumshoq soya (feDropShadow yoki pastki opacity-ellipse)")
    if "fon" in weak or "fon tartibi" in weak:
        tips.append("birinchi element: to'liq-canvas yumshoq fon rect")
    if "markazlash" in weak:
        tips.append("mavzuni canvas markaziga joylash")
    if "margin" in weak:
        tips.append("chekkadan ~12% margin qoldirish")
    if "chegara" in weak:
        tips.append("kontent viewBox chegarasida qolsin")
    if "ranglar" in weak:
        tips.append("2-6 rangli uyg'un palitra tanlash")
    if "xilma-xillik" in weak:
        tips.append("3+ rang ohangi ishlatish (monoxrom emas)")
    if "uslub mosligi" in weak:
        if style == "realistic":
            tips.append("realistic: gradient + soya majburiy")
        elif style == "flat":
            tips.append("flat: gradient/soya YO'Q bo'lishi kerak")
        else:
            tips.append("cartoon: qalin kontur (stroke-width 4-6)")
    if "silliq chiziqlar" in weak:
        tips.append("stroke-linejoin/linecap round")
    return "; ".join(tips[:4])


# S5 delegatsiya: veb va tez yo'llar alohida moduli orqali ulanadi (fallback bilan).
# `from igris_web` / `from igris_quick` yetib kelmasa default ikkala moduli ham
# `(getattr(sys.modules.get('igris_web') or web_strategy_mod, name) or
#   getattr(quick_paths_mod, name, None))` ko'rinishida uxlati (runtime fallback).

def _delegate_web(name: str) -> Any:
    """Web/quick funksiyasiga delegatsiya qiladi; topilmasa None qaytaradi."""
    for candidate in (getattr(sys.modules.get('igris_web'), name, None), getattr(web_strategy_mod, name, None)):
        if candidate is not None:
            return candidate
    return None

def _delegate_quick(name: str) -> Any:
    """Quick-path funksiyasiga delegatsiya qiladi; topilmasa None qaytaradi."""
    for candidate in (getattr(sys.modules.get('igris_quick'), name, None), getattr(quick_paths_mod, name, None)):
        if candidate is not None:
            return candidate
    return None

_WEB_SOURCE_TOOLS = frozenset({
    "web_fetch",                    # to'g'ridan-to'g'ri sahifa matni
    "web_ai_bridge__browser_get_text",
    "web_ai_bridge__web_ai_get_conversation",
    "web_ai_bridge__ask_web_ai",
    "web_ai_bridge__web_ai_check_research",
    "web_ai_bridge__web_ai_start_research",
})


def _is_web_source_tool(name: str) -> bool:
    """Tool web-manba qaytaradimi (prefiksli MCP web tool'lar ham)."""
    if name in _WEB_SOURCE_TOOLS:
        return True
    # web_ai_bridge__* kabi prefiksli chaqiruvlar (mcp prefiks sxemasi)
    return name.startswith("web_") or name.startswith("web_ai_bridge__")


class IgrisAgent:
    """Orchestrates bricks -> resolver -> chains -> RAG memory -> optional LLM."""

    def __init__(
        self,
        use_llm: bool = True,
        llm_model: str = "qwen3:8b",
        llm_base_url: str = "http://localhost:11434",
        min_confidence: float = 0.7,
        memory_enabled: bool = True,
        memory_session: str = "",
        memory_dir: str = "",
        workspace_root: str = "",
        # Ixtiyoriy OpenAI-mos logprob re-so'ruvi (self-eval ishonch signali;
        # 2x inference narxi). Server `--logprobs` / `IGRIS_LOGPROBS=1` bilan
        # yoqiladi. Default O'CHIQ — native /api/chat logprob qaytarmaydi.
        llm_logprobs: bool = False,
        # OmniRoute gateway (optional)
        omniroute_url: str = "",
        omniroute_api_key: str = "",
        omniroute_model: str = "",
        # So'rov semantikasini LLM bilan boyitish (ixtiyoriy assist:
        # problem/goal/definition/paradigms). Deterministik parse asosiy
        # yo'l; assist faqat LLM mavjudligida ishlaydi.
        # IGRIS_MEANING_ASSIST=0 bilan global o'chiriladi.
        meaning_llm_assist: bool = True,
    ):
        # Deterministic core
        self.bricks = BrickBank().add_many(build_default_bricks())
        self.knowledge = build_default_knowledge()
        self.resolver = ConstraintResolver(self.bricks, self.knowledge)
        self.chains = build_default_chains(self.knowledge)
        self.healer = ChainHealer(self.chains)

        # Hybrid LLM (optional, lazy)
        self.use_llm = use_llm
        self.min_confidence = min_confidence
        
        # LLM client — OmniRoute yoki Ollama
        self.llm = self._init_llm(
            llm_model, llm_base_url, llm_logprobs,
            omniroute_url, omniroute_api_key, omniroute_model,
        )
        
        self._llm_checked = False
        self._llm_available = False
        # Graceful degradation: LLM xatosidan keyin avtomatik tiklash
        self._llm_last_failure = 0.0     # oxirgi xato vaqti (epoch)
        self._llm_failure_count = 0      # ketma-ket xato soni
        self._llm_cooldown = 60.0        # xatodan keyin kutish vaqti (sekund)
        self._llm_max_cooldown = 600.0   # maksimal cooldown (10 daqiqa)
        # Degradation metrics tracking - time-series uchun
        self._degradation_history: list[dict] = []  # oxirgi N ta event
        self._degradation_max_history = 100         # max tarix uzunligi
        self._degradation_started_at = 0.0          # joriy degradation boshlangan vaqt
        self._total_degradation_time = 0.0          # jami degradation vaqti (sekund)
        self._total_degradation_count = 0           # jami degradation soni
        self._last_recovery_time = 0.0              # oxirgi tiklash vaqti (epoch)

        # Memory / RAG bridge (Igris_Memory)
        self.memory = MemoryBridge(enabled=memory_enabled, session_id=memory_session,
                                   base_dir=memory_dir)

        # Vision System — text-only LLMga "ko'z beradi"
        self.vision = self._init_vision()

        # Refactor Machine (meta-assessment layer)
        self.refactor = RefactorMachine(agent=self)

        # CAG (response cache) + MAG (memory-augmented context)
        self.cag_cache = None
        self.mag = None

        # SO'ROV SEMANTIKASI keshi (core/request_meaning) — takroriy so'rovda
        # qayta tahlil qilinmaydi (deterministik, LLM'siz)
        self._meaning_cache: dict = {}
        # Ixtiyoriy LLM assist (problem/goal/definition boyitish) — env kill-switch
        _assist_env = str(os.environ.get("IGRIS_MEANING_ASSIST", "1")).strip().lower()
        self._meaning_assist = (bool(meaning_llm_assist)
                                and _assist_env not in ("0", "off", "false", "no"))

        # §6 CONTEXT BUDGET (Phase 3): prompt qatlamlarini token budget bilan
        # sig'dirish — goal_pin/user HECH QACHON tashlanmaydi, overflow'da
        # memory → history(eskilari) → req tartibida graceful degradation.
        self.context_budget = ContextBudget()

        # A4 (web manba tekshiruvi): joriy chatning web-manba indeksi.
        # `_chat_with_tools` web tool natijalarini shu yerga yig'adi;
        # `_with_self_eval` yakuniy javobni shu manbalar bilan solishtiradi
        # (grounding signal). Chat boshida tozalanadi.
        self._web_sources = None

        # Intelligence core (BuildIntalaganceInstructionRequest.md)
        # 2.10 harm-filter -> 2.6 user-model + 2.12 tone-detect ->
        # [2.1 language / 2.2 logic / 2.4 spatial / 2.11 creative] ->
        # 2.7 self-eval. Avtonomiya NOL: bu qatlam hech qachon agentning
        # o'z maqsadini/system prompt'ini o'zi o'zgartirmaydi.
        self.intelligence = IntelligenceCore(
            enabled=True,
            language="auto",
        )

        # Chat tool'lar (MCP + workspace) — lazy init
        self.workspace_root = workspace_root or DEFAULT_WORKSPACE
        self._mcp_cache: Optional[object] = None
        self._chat_exec = None
        self._registry_cache = None
        self._chat_tools_cache: Optional[list[dict]] = None
        # svg-artist skill matni — chizish so'rovlarida system prompt'ga qo'shiladi
        self._draw_skill_cache: Optional[str] = None
        # SEMANTIK TALAB QATLAMI (Part L): user talabini struktur modelga o'tkazadi —
        # javob shakllanishi (til/chuqurlik/format/cheklovlar) shunga moslanadi.
        # LLM yo'q/offline bo'lsa deterministik fallback ishlaydi.
        # llm_provider: (a) agent.llm keyin almashtirilsa (test fake /
        # reconnect) ekstraktor ham ergashadi; (b) LLM qatlami mavjud emas /
        # cooldown'da bo'lsa None — deterministik fallback (hujjatlashtirilgan
        # shartnoma), real tarmoq chaqiruvi va kutish yo'q.
        self.requirements = RequirementExtractor(
            llm=self.llm, cache=None,
            llm_provider=lambda: self.llm if self.llm_available() else None)

        # Smart Build Engine v2 — Weak LLM + Strong Cognitive Infrastructure
        # Context Intelligence, Deterministic Executor, Error Parser, Verifier
        self.smart_build_engine = self._init_smart_build()

        # Chat Stream Aggregator — micro-actions → semantic actions
        self._chat_stream_agg = self._init_chat_stream()

    # ------------------------------------------------------------ #
    # LLM Initialization — OmniRoute yoki Ollama
    # ------------------------------------------------------------ #

    def _init_llm(
        self,
        llm_model: str,
        llm_base_url: str,
        llm_logprobs: bool,
        omniroute_url: str,
        omniroute_api_key: str,
        omniroute_model: str,
    ):
        """LLM client'ni ishga tushirish — OmniRoute afzallik bilan."""
        import os
        
        # 1. OmniRoute — agar URL berilgan yoki env'da mavjud bo'lsa
        omni_url = omniroute_url or os.environ.get("OMNIROUTE_URL", "")
        omni_key = omniroute_api_key or os.environ.get("OMNIROUTE_API_KEY", "")
        omni_model = omniroute_model or os.environ.get("OMNIROUTE_DEFAULT_MODEL", "")
        
        if omni_url:
            try:
                from llm.omniroute_client import OmniRouteClient
                client = OmniRouteClient(
                    base_url=omni_url,
                    api_key=omni_key,
                    default_model=omni_model or "openai/gpt-4o-mini",
                )
                # Health check — gateway ishlayaptimi?
                if client.health_check():
                    return client
            except Exception:
                pass  # OmniRoute mavjud emas — Ollama ga o'tamiz
        
        # 2. Ollama — default fallback
        from llm.ollama_client import OllamaClient
        return OllamaClient(
            model=llm_model,
            base_url=llm_base_url,
            logprobs=llm_logprobs,
        )

    # ------------------------------------------------------------ #
    # Vision System — LLM-independent Custom Vision
    # ------------------------------------------------------------ #

    def _init_vision(self):
        """Vision system'ni ishga tushirish."""
        try:
            from vision.perception import PerceptionEngine
            engine = PerceptionEngine(
                save_dir=str(self.workspace_root / ".igris" / "vision_captures")
                if hasattr(self.workspace_root, "__truediv__")
                else ".igris/vision_captures",
                confidence_threshold=0.6,
            )
            return engine
        except Exception:
            return None

    def vision_observe(self, source: str = "screen", **kwargs) -> dict:
        """Sahna kuzatuvi — agent'ning "ko'zi".

        Args:
            source: "screen", "window", "region", "file"
            **kwargs: capture parametrlari

        Returns:
            Scene dict + LLM context
        """
        if not self.vision:
            return {"error": "Vision system not available"}

        scene = self.vision.observe(source, **kwargs)
        context = self.vision.context_for_llm(scene)
        json_ctx = self.vision.json_context_for_llm(scene)

        return {
            "scene": scene.to_dict(),
            "context": context,
            "json_context": json_ctx,
            "objects_count": len(scene.objects),
            "interactive_count": len(scene.get_interactive_objects()),
        }

    def vision_find_target(self, description: str) -> dict:
        """Tavsif bo'yicha target topish."""
        if not self.vision:
            return {"error": "Vision system not available"}

        scene = self.vision.observe()
        target = self.vision.find_target(scene, description)

        if target is None:
            return {"found": False, "description": description}

        return {
            "found": True,
            "target": target.to_dict(),
            "scene": scene.to_dict(),
        }

    def vision_click(self, description: str) -> dict:
        """Tavsif bo'yicha obyektni bosish."""
        if not self.vision:
            return {"error": "Vision system not available"}

        from vision.action_bridge import ActionBridge
        bridge = ActionBridge(safety_enabled=True)

        # Avval sahnani kuzatamiz
        scene = self.vision.observe()
        target = self.vision.find_target(scene, description)

        if target is None:
            return {"success": False, "error": "Target not found"}

        # Xavfsizlik tekshiruvi
        if not target.is_safe:
            return {
                "success": False,
                "error": f"Unsafe: {target.safety_reason}",
            }

        # Bosamiz
        result = bridge.click(target)
        return result.to_dict()

    def vision_type_text(self, target_description: str, text: str) -> dict:
        """Tavsif bo'yicha obyektga matn kiritish."""
        if not self.vision:
            return {"error": "Vision system not available"}

        from vision.action_bridge import ActionBridge
        bridge = ActionBridge(safety_enabled=True)

        scene = self.vision.observe()
        target = self.vision.find_target(scene, target_description)

        if target is None:
            return {"success": False, "error": "Target not found"}

        result = bridge.type_text(target, text)
        return result.to_dict()

    def vision_verify(self, before: dict, action: str = "") -> dict:
        """Amal tasdig'i — oldingi va hozirgi sahnani solishtirish."""
        if not self.vision:
            return {"error": "Vision system not available"}

        after_scene = self.vision.observe()

        # Before scene'ni qayta yaratish
        from vision.contracts import BBox, DetectedObject, ObjectType, Scene, SceneType
        before_objects = []
        for od in before.get("objects", []):
            bbox_data = od.get("bbox", {})
            obj = DetectedObject(
                object_id=od.get("object_id", ""),
                object_type=ObjectType(od.get("object_type", "unknown")),
                bbox=BBox(bbox_data.get("x1", 0), bbox_data.get("y1", 0),
                          bbox_data.get("x2", 0), bbox_data.get("y2", 0)),
                confidence=od.get("confidence", 0.0),
                associated_text=od.get("associated_text", ""),
                is_interactive=od.get("is_interactive", False),
            )
            before_objects.append(obj)

        before_scene = Scene(
            scene_type=SceneType(before.get("scene_type", "unknown")),
            objects=before_objects,
            width=before.get("width", 0),
            height=before.get("height", 0),
            window_title=before.get("window_title", ""),
        )

        result = self.vision.verify_action(before_scene, after_scene, action)
        return result.to_dict()

    def vision_get_performance(self) -> dict:
        """Vision performansini olish."""
        if not self.vision:
            return {"error": "Vision system not available"}
        return self.vision.get_performance()

    # ------------------------------------------------------------ #
    # Vision Tools — LLM ga "ko'z berish"
    # ------------------------------------------------------------ #

    def _vision_tools(self) -> list[dict]:
        """Vision tool schema'lari — LLM ga ko'rsatiladi."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "vision_observe",
                    "description": "Observe the current screen. Returns detected objects, text, and UI elements with coordinates.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "Capture source: 'screen', 'window', 'region', 'file'",
                                "enum": ["screen", "window", "region", "file"],
                                "default": "screen",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "vision_find",
                    "description": "Find a UI element by description. Returns object_id, bounding box, and confidence.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Description of the element to find (e.g., 'Search button', 'Submit', 'input field')",
                            },
                        },
                        "required": ["description"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "vision_click",
                    "description": "Click on a UI element by description. Returns success/failure with coordinates.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Description of the element to click (e.g., 'Search button', 'OK', 'Submit')",
                            },
                        },
                        "required": ["description"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "vision_type",
                    "description": "Type text into a UI element by description.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "Description of the input field (e.g., 'search box', 'email input')",
                            },
                            "text": {
                                "type": "string",
                                "description": "Text to type",
                            },
                        },
                        "required": ["target", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "vision_verify",
                    "description": "Verify if an action succeeded by comparing before/after screen states.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": "Description of the action that was taken",
                            },
                        },
                        "required": ["action"],
                    },
                },
            },
        ]

    def _execute_vision_tool(self, name: str, args: dict) -> dict:
        """Vision tool'ni bajarish."""
        try:
            if name == "vision_observe":
                source = args.get("source", "screen")
                return self.vision_observe(source)
            elif name == "vision_find":
                desc = args.get("description", "")
                return self.vision_find_target(desc)
            elif name == "vision_click":
                desc = args.get("description", "")
                return self.vision_click(desc)
            elif name == "vision_type":
                target = args.get("target", "")
                text = args.get("text", "")
                return self.vision_type_text(target, text)
            elif name == "vision_verify":
                action = args.get("action", "")
                # Oldingi sahnani olish
                prev_scene = self.vision.get_memory().get_previous_scene()
                if prev_scene:
                    return self.vision_verify(prev_scene.to_dict(), action)
                return {"error": "No previous scene available for verification"}
            return {"error": f"Unknown vision tool: {name}"}
        except Exception as e:
            return {"error": f"Vision tool error: {str(e)}"}

    # ------------------------------------------------------------ #
    # Smart Build Engine — Weak LLM + Strong Cognitive Infrastructure
    # ------------------------------------------------------------ #

    def _init_smart_build(self):
        """Smart Build engine'ni ishga tushirish — Vision integratsiya bilan."""
        try:
            from smart_build.engine_v2 import SmartBuildEngineV2
            return SmartBuildEngineV2(
                project_root=self.workspace_root,
                vision_engine=self.vision,
            )
        except Exception:
            return None

    def smart_build(self, task: str, progress_cb=None) -> dict:
        """Smart Build — Weak LLM + Strong Cognitive Infrastructure.

        Pipeline: Intent → Context Intelligence → Small LLM → Deterministic → Verify
        """
        if not self.smart_build_engine:
            return {"error": "Smart Build engine not available"}

        t0 = time.perf_counter()

        # 1. Intent Engine — task complexity aniqlash
        if progress_cb:
            progress_cb("plan", "Smart Build: task tahlil qilinmoqda...")

        context = self.smart_build_engine._context_engine.process(task)

        # 2. Token budget complexity ga qarab
        complexity = context.complexity
        token_budget = self.smart_build_engine._get_token_budget(complexity)

        # 3. Context Intelligence — faqat relevant data
        if progress_cb:
            progress_cb("read", f"Context: {len(context.relevant_files)} relevant files, {context.tokens_used} tokens")

        enriched_context = self.smart_build_engine._context_engine.process(task, token_budget)

        # 4. Deterministic pre-checks
        if progress_cb:
            progress_cb("edit", "Deterministic checks...")

        pre_evidence = self.smart_build_engine._run_deterministic_checks(enriched_context)

        # 5. LLM decision (if needed)
        llm_decision = None
        if token_budget > 0 and self.llm_available():
            if progress_cb:
                progress_cb("edit", "LLM reasoning...")
            llm_prompt = enriched_context.to_llm_prompt()
            try:
                llm_decision = self.llm.complete(
                    system="You are a code analysis assistant. Analyze the context and provide a decision.",
                    prompt=llm_prompt
                )
            except Exception as e:
                llm_decision = f"LLM error: {e}"

        # 6. Execute
        if progress_cb:
            progress_cb("test", "Execution...")

        exec_evidence = self.smart_build_engine._execute_deterministic(enriched_context)

        # 7. Verify
        if progress_cb:
            progress_cb("review", "Verification...")

        all_evidence = pre_evidence + exec_evidence
        verification = self.smart_build_engine._verify_with_evidence(all_evidence, task)

        # 8. Result
        duration = time.time() - t0
        result = {
            "task": task,
            "status": verification.status.value,
            "complexity": complexity.value,
            "confidence": verification.confidence,
            "evidence_count": len(all_evidence),
            "evidence_passed": sum(1 for e in all_evidence if e.status.value == "success"),
            "tokens_used": enriched_context.tokens_used,
            "token_budget": token_budget,
            "llm_decision": llm_decision,
            "duration_seconds": round(duration, 2),
            "context": enriched_context.to_dict(),
            "verification": verification.to_dict(),
        }

        # Memory
        if self.memory.enabled:
            self.memory.on_resolve(task, {"output": str(result), "engine": "smart_build", "confidence": verification.confidence})

        return result

    def smart_build_tools(self) -> list[dict]:
        """Smart Build tool schema'lari — LLM ga ko'rsatiladi."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "smart_build_analyze",
                    "description": "Analyze a task using Smart Build pipeline. Returns context, complexity, and evidence.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "Task to analyze (e.g., 'add authentication', 'fix bug in auth.py')",
                            },
                        },
                        "required": ["task"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "smart_build_check",
                    "description": "Run deterministic checks on files (syntax, imports, build, tests).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of files to check",
                            },
                        },
                        "required": ["files"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "smart_build_error",
                    "description": "Parse an error message into structured evidence for LLM reasoning.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "error": {
                                "type": "string",
                                "description": "Raw error message (traceback, exception, etc.)",
                            },
                            "changed_files": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Recently changed files (optional)",
                            },
                        },
                        "required": ["error"],
                    },
                },
            },
        ]

    def _execute_smart_build_tool(self, name: str, args: dict) -> dict:
        """Smart Build tool'ni bajarish."""
        try:
            if name == "smart_build_analyze":
                task = args.get("task", "")
                return self.smart_build(task)
            elif name == "smart_build_check":
                files = args.get("files", [])
                if not self.smart_build_engine:
                    return {"error": "Smart Build engine not available"}
                evidence = []
                for f in files:
                    e = self.smart_build_engine._executor.check_syntax_valid(f)
                    evidence.append(e.to_dict())
                return {"evidence": evidence}
            elif name == "smart_build_error":
                error = args.get("error", "")
                changed = args.get("changed_files", [])
                if not self.smart_build_engine:
                    return {"error": "Smart Build engine not available"}
                parsed = self.smart_build_engine.handle_error(error, changed)
                return parsed.to_dict()
            return {"error": f"Unknown smart build tool: {name}"}
        except Exception as e:
            return {"error": f"Smart Build tool error: {str(e)}"}

    # ------------------------------------------------------------ #
    # Chat Stream Aggregator — micro-actions → semantic actions
    # ------------------------------------------------------------ #

    def _init_chat_stream(self):
        """Chat Stream aggregator'ni ishga tushirish."""
        try:
            from smart_build.chat_stream import ChatStreamAggregator
            return ChatStreamAggregator()
        except Exception:
            return None

    def stream_start(self, task: str) -> dict:
        """Yangi chat stream boshlash."""
        if not self._chat_stream_agg:
            return {"error": "Chat stream not available"}
        stream = self._chat_stream_agg.start_stream(task)
        return {"task": task, "status": "started"}

    def stream_tool_call(self, tool_name: str, args: dict, result: dict = None) -> dict:
        """Tool call'ni stream'ga qo'shish — semantic action yaratish."""
        if not self._chat_stream_agg:
            return {"error": "Chat stream not available"}
        update = self._chat_stream_agg.add_tool_call(tool_name, args, result)
        return update or {"status": "aggregated"}

    def stream_complete_action(self, success: bool = True, details: dict = None) -> dict:
        """Joriy action'ni tugatish."""
        if not self._chat_stream_agg:
            return {"error": "Chat stream not available"}
        return self._chat_stream_agg.complete_action(success, details) or {"status": "completed"}

    def stream_complete(self, success: bool = True, result: str = "") -> dict:
        """Stream'ni tugatish."""
        if not self._chat_stream_agg:
            return {"error": "Chat stream not available"}
        self._chat_stream_agg.complete_stream(success, result)
        return {"status": "stream_completed"}

    def stream_get_current(self) -> dict:
        """Joriy stream holatini olish."""
        if not self._chat_stream_agg:
            return {"error": "Chat stream not available"}
        stream = self._chat_stream_agg.get_stream()
        if not stream:
            return {"status": "no_active_stream"}
        return stream.to_summary()

    def stream_get_all(self) -> list[dict]:
        """Barcha streamlarni olish."""
        if not self._chat_stream_agg:
            return []
        return self._chat_stream_agg.get_all_streams()

    # ------------------------------------------------------------ #
    # Smart Edit — avtomatik read → edit chain
    # ------------------------------------------------------------ #

    def smart_edit(self, path: str, old_string: str, new_string: str,
                   replace_all: bool = False) -> dict:
        """Avtomatik read → edit chain.
        
        1. Faylni avtomatik o'qiydi
        2. Xatolik bo'lsa, fayl tarkibini ko'rsatadi
        3. Edit'ni bajaradi
        
        Returns: {ok, diff, error, hint}
        """
        ex = self._chat_executor()
        if ex is None:
            return {"ok": False, "error": "tools unavailable"}
        
        # 1. Avval o'qish
        read_result = ex._execute_agent_tool("read_file", {"path": path})
        if not read_result.get("ok"):
            return read_result
        
        content = read_result.get("content", "")
        lines = content.splitlines()
        
        # 2. Tekshirish — old_string mavjudmi?
        if old_string not in content:
            # Qidiruv — yaqin matnlarni topish
            suggestions = self._suggest_edit_target(content, old_string)
            return {
                "ok": False,
                "error": f"'{old_string[:50]}...' not found in {path}",
                "file_lines": len(lines),
                "first_20_lines": "\n".join(lines[:20]),
                "suggestions": suggestions,
            }
        
        # 3. Edit bajarish
        edit_result = ex._execute_agent_tool("edit_file", {
            "path": path,
            "old_string": old_string,
            "new_string": new_string,
            "replace_all": replace_all,
        })
        return edit_result

    def _suggest_edit_target(self, content: str, target: str) -> list[str]:
        """Edit uchun yaqin matnlarni topish."""
        import difflib
        lines = content.splitlines()
        suggestions = []
        
        # exact match yo'q — yaqin satrlarni qidiramiz
        target_lower = target.lower().strip()
        for i, line in enumerate(lines):
            line_stripped = line.strip().lower()
            # Partial match
            if any(word in line_stripped for word in target_lower.split() if len(word) > 2):
                suggestions.append(f"Line {i+1}: {line.strip()[:80]}")
        
        # fuzzy match
        if not suggestions:
            for i, line in enumerate(lines):
                ratio = difflib.SequenceMatcher(None, target_lower, line.strip().lower()).ratio()
                if ratio > 0.4:
                    suggestions.append(f"Line {i+1} (similarity {ratio:.0%}): {line.strip()[:80]}")
        
        return suggestions[:5]

    # ------------------------------------------------------------ #
    # LLM availability (lazy + cached)
    # ------------------------------------------------------------ #

    def llm_available(self) -> bool:
        """LLM mavjudligini tekshiradi. Graceful degradation bilan:

        - Birinchi marta: Ollama mavjudligini tekshiradi
        - Xatodan keyin: cooldown davomida False qaytaradi
        - Cooldown tugagach: qayta tekshiradi (avtomatik tiklash)
        - Maksimal cooldown: 10 daqiqa (cheksiz kutish yo'q)
        """
        if not self.use_llm:
            return False
        now = time.time()
        # Cooldown holatida: hali kutish kerak
        if self._llm_failure_count > 0 and self._llm_last_failure > 0:
            elapsed = now - self._llm_last_failure
            cooldown = min(
                self._llm_cooldown * (2 ** min(self._llm_failure_count - 1, 4)),
                self._llm_max_cooldown
            )
            if elapsed < cooldown:
                return False
            # Cooldown tugadi - qayta tekshiramiz
        if not self._llm_checked:
            self._llm_available = self.llm.is_available()
            self._llm_checked = True
        return self._llm_available

    def _mark_llm_failed(self, error: str = ""):
        """LLM xatosini qayd etadi - graceful degradation uchun.

        Birinchi xatoda: 60s cooldown
        Keyingilarda: 2x oshadi (120s, 240s, 480s, 600s max)
        Cooldown tugagach: avtomatik qayta tekshiriladi.

        Degradation event tarixi saqlanadi - monitoring dashboard uchun.
        """
        now = time.time()
        self._llm_last_failure = now
        self._llm_failure_count += 1
        self._llm_available = False
        self._llm_checked = True
        cooldown = min(
            self._llm_cooldown * (2 ** min(self._llm_failure_count - 1, 4)),
            self._llm_max_cooldown
        )
        # Degradation event tracking
        if self._degradation_started_at == 0:
            self._degradation_started_at = now
            self._total_degradation_count += 1
        event = {
            "type": "failure",
            "timestamp": now,
            "error": str(error)[:200],
            "failure_count": self._llm_failure_count,
            "cooldown_seconds": cooldown,
        }
        self._degradation_history.append(event)
        if len(self._degradation_history) > self._degradation_max_history:
            self._degradation_history.pop(0)
        print(f"[igris] LLM failed ({self._llm_failure_count}x): {error[:80]} - cooldown {cooldown:.0f}s")

    def _mark_llm_recovered(self):
        """LLM qayta ishga tushdi - cooldown'ni tozalaydi.

        Degradation event tarixiga recovery yozuvi qo'shiladi.
        """
        now = time.time()
        recovery_duration = 0.0
        if self._degradation_started_at > 0:
            recovery_duration = now - self._degradation_started_at
            self._total_degradation_time += recovery_duration
        if self._llm_failure_count > 0:
            print(f"[igris] LLM recovered after {self._llm_failure_count} failures ({recovery_duration:.0f}s degradation)")
        # Degradation recovery event
        event = {
            "type": "recovery",
            "timestamp": now,
            "failures_before_recovery": self._llm_failure_count,
            "degradation_duration_seconds": round(recovery_duration, 1),
            "total_degradation_count": self._total_degradation_count,
            "total_degradation_time_seconds": round(self._total_degradation_time, 1),
        }
        self._degradation_history.append(event)
        if len(self._degradation_history) > self._degradation_max_history:
            self._degradation_history.pop(0)
        # Reset state
        self._llm_failure_count = 0
        self._llm_last_failure = 0.0
        self._llm_available = True
        self._llm_checked = True
        self._degradation_started_at = 0.0
        self._last_recovery_time = now

    def degradation_status(self) -> dict:
        """Degradation metrics holati - monitoring dashboard uchun."""
        now = time.time()
        current_degradation_time = 0.0
        if self._degradation_started_at > 0:
            current_degradation_time = now - self._degradation_started_at
        return {
            "is_degraded": self._llm_failure_count > 0,
            "failure_count": self._llm_failure_count,
            "current_cooldown_seconds": min(
                self._llm_cooldown * (2 ** max(0, self._llm_failure_count - 1)),
                self._llm_max_cooldown
            ) if self._llm_failure_count > 0 else 0,
            "current_degradation_seconds": round(current_degradation_time, 1),
            "total_degradation_count": self._total_degradation_count,
            "total_degradation_time_seconds": round(self._total_degradation_time, 1),
            "last_recovery_time": self._last_recovery_time or None,
            "history": self._degradation_history[-20:],  # oxirgi 20 ta event
        }

    # ------------------------------------------------------------ #
    # Universal speed boost (TURBO) — har qanday LLM ga birdek qo'llanadi
    # ------------------------------------------------------------ #

    def set_speed(self, turbo: bool):
        """Universal tez rejim: BIR kalit — barcha modellarni tezlashtiradi.

        - Ollama so'rovlari: kichik kontekst/token, thinking o'chiq, qisqa timeout
        - oddiy chat savollari -> avtomatik tanlangan tez model (fast_model)
        - katta model faqat murakkab/tool vazifalarga qoladi
        """
        if not self.use_llm:
            return
        try:
            models = self.llm.list_models()
        except Exception:
            models = []
        # ModelInfo (OmniRoute) / str (Ollama) farqi — agent faqat NOMlarni oladi
        models = [m.id if hasattr(m, "id") else str(m) for m in (models or [])]
        self.llm.set_turbo(bool(turbo), available_models=models)
        print(f"[igris] speed: turbo={'on' if turbo else 'off'} fast_model={self.llm.fast_model}")

    def speed_status(self) -> dict:
        return {
            "turbo": bool(getattr(self.llm, "turbo", False)),
            "fast_model": getattr(self.llm, "fast_model", None),
            "model": self.llm.model,
        }

    # ------------------------------------------------------------ #
    # Semantic requirement layer (Part L — user talabiga mos javob)
    # ------------------------------------------------------------ #

    def _extract_requirements(self, message: str,
                              history: Optional[list] = None) -> Requirement:
        """User talabini struktur modelga o'tkazadi (LLM, CAG-keshlangan).

        Hech qachon exception bermaydi — xatolikda deterministik fallback.
        Chizish so'rovi — DETERMINISTIK tez talab (LLM keraksiz: sekin va
        kuchsiz model noto'g'ri chiqarishi mumkin).
        """
        try:
            if self._is_draw_request(message):
                return self.requirements.extract_fast(message)
        except Exception:
            pass
        try:
            self.requirements.cache = self._cag()
        except Exception:
            pass
        try:
            return self.requirements.extract(message, history)
        except Exception:
            return Requirement()

    def _summary_instruction(self, req: Requirement) -> str:
        """Final xulosa ko'rsatmasi — req (til/chuqurlik/format)ga mos.

        Qotib qolgan "1-2 short sentences" o'rniga foydalanuvchi talabiga
        mos uzunlik va shakl (Part L, CP-L3/B1).
        """
        lang = req.language or "the user's language"
        verb = {
            "concise": "1-2 short sentences",
            "detailed": "a detailed summary (5-8 sentences) covering the key steps",
            "balanced": "2-4 short sentences",
        }.get(req.verbosity, "2-4 short sentences")
        fmt = req.output_format
        text = (
            f"Summarize what you just did for the user in {verb}, in {lang}. "
            "Plain text only — no JSON, no tool-call format, no code fences. "
            "Mention the created file if relevant."
        )
        if fmt in ("list", "table", "steps"):
            text += f" Present the summary as a {fmt}."
        if req.constraints:
            text += " Constraints to respect: " + "; ".join(req.constraints) + "."
        return text

    def _compliance(self, content: str, req: Requirement, message: str) -> str:
        """Talab bilan solishtiradi; nomoslik bo'lsa BIR marta qayta generatsiya.

        Faqat aniq talab (til/format/cheklov/chuqurlik) bor bo'lganda ishlaydi —
        qimmat tekshiruv keraksiz chaqirilmaydi. CAG `chk:` kesh bilan bir xil
        tekshiruv takrorlanmaydi (Part L, CP-L3/B2).
        """
        if not content or not content.strip():
            return content
        if self.llm is None or not self.llm_available():
            return content
        if req.output_format in ("image",):
            return content  # rasm/visual — draw-pipeline orqali tekshirilgan
        if not (req.language or req.output_format != "text" or req.verbosity != "balanced"
                or req.constraints or req.deliverable_name):
            return content
        try:
            cache = self._cag()
            key = f"chk:{message}"
            if cache is not None:
                hit = cache.get("req", key)
                if hit == content:
                    return content
            system = (
                "You verify that an agent's answer satisfies the user's stated "
                "requirements. Respond with ONLY 'yes' or 'no'.\n"
                f"Requirements: intent={req.intent}; language={req.language or 'any'}; "
                f"format={req.output_format}; verbosity={req.verbosity}; "
                f"constraints={req.constraints or 'none'}; "
                f"deliverable={req.deliverable_name or 'none'}.\n"
                "Answer 'no' ONLY if the answer clearly violates a requirement "
                "(wrong language, wrong format, missing requested file, or too "
                "brief when detailed was requested)."
            )
            verdict = self.llm.complete(system=system, prompt=f"Answer: {content[:2000]}")
            if verdict and verdict.strip().lower().startswith("yes"):
                if cache is not None:
                    cache.put("req", key, content)
                return content
            # Nomoslik — talabga mos qilib 1 marta qayta generatsiya
            messages = [
                {"role": "system", "content": (
                    "Improve the previous answer so it strictly follows the user "
                    "requirements. Stay truthful — do not invent facts.\n"
                    + req.to_block()
                )},
                {"role": "user", "content": message},
                {"role": "assistant", "content": content},
            ]
            fixed = self.llm.chat(messages)
            if fixed and fixed.strip():
                return fixed.strip()
        except Exception:
            pass
        return content

    def _retry_generate(self, messages: list[dict], req: Requirement,
                        attempts: int = 2) -> str:
        """Bo'sh/`I could not...` javob o'rniga qayta generatsiya (req bilan).

        Turli temperature/hint bilan 2 urinish; hali ham bo'sh bo'lsa — halol,
        template bo'lmagan minimal javob (yolg'on "bajarildi" aytmaydi).
        """
        # Part O: chizish so'rovi — kuchsiz model qimmat/junk SVG beradi;
        # retry qilish o'rniga to'g'ridan-to'g'ri halol javob (tez, crashsiz).
        user_msg = " ".join(str(m.get("content") or "") for m in (messages or [])
                            if m.get("role") == "user")
        is_draw = bool(user_msg) and self._is_draw_request(user_msg)
        if is_draw:
            attempts = 0
        for i in range(attempts):
            try:
                m = list(messages)
                if i > 0:
                    m.append({"role": "user", "content":
                              "Please actually answer the user's request now. "
                              + req.to_block()})
                out = self.llm.chat(m) if i == 0 else self.llm.complete(
                    system=(m[0].get("content") if m and m[0].get("role") == "system" else ""),
                    prompt=m[-1].get("content", ""))
                if out and out.strip():
                    # Part O: soxta "Chizdim ... rasm tayyor" (model rasmini
                    # CHIZMAGAN) — muvaffaqiyat deb qabul qilinmaydi.
                    if self._fake_draw_claim(out):
                        continue
                    return out.strip()
            except Exception:
                continue

        # Part N: xabarni TILga mos va REAL SABAB bilan beramiz — "rephrase"
        # shabloni emas. Model yuklana olmasa (OOM) avtomatik kichik modelga
        # o'tilgan; baribir bo'sh bo'lsa — tushunarli izoh.
        lang = (req.language or self._detect_lang(messages) or "uz")
        # Part O: chizish so'rovi bajarilmadi — ma'lum narsalarni taklif qilamiz
        # (yolg'on "Chizdim" emas).
        if is_draw:
            if lang == "uz":
                return ("Bu narsani hozirgi model bilan aniq chizib bo'lmadi. "
                        "Ma'lum narsalardan birini so'rang (olma, uy, daraxt, "
                        "mushuk, mashina, gul, qush, baliq, kapalak...) yoki "
                        "Settings'dan kuchliroq modelni tanlang.")
            return ("The current model could not draw this accurately. Ask for a "
                    "known subject (apple, house, tree, cat, car, flower, bird, "
                    "fish, butterfly...) or pick a stronger model in Settings.")
        reason = (getattr(self.llm, "last_error", None) or "").lower()
        if any(k in reason for k in ("out of memory", "cudamalloc", "xotira",
                                     "yuklana olmadi", "failed to load",
                                     "unable to allocate", "cuda0 buffer")):
            if lang == "uz":
                return ("Model GPU xotirasi yetmagani uchun yuklana olmadi — "
                        "kichikroq modelga avtomatik o'tildi. Yana bir marta "
                        "yozib ko'ring yoki Settings'dan boshqa model tanlang.")
            return ("The model could not load (GPU memory) — a smaller model "
                    "was selected automatically. Try again or pick another "
                    "model in Settings.")
        if reason and "ollama" in reason:
            if lang == "uz":
                return (f"Model ishlay olmadi (Ollama xatosi). Qayta urinib "
                        f"ko'ring. Tafsilot: {reason[:120]}")
            return (f"The model failed (Ollama error). Please try again. "
                    f"Detail: {reason[:120]}")
        if lang == "uz":
            return ("Men javob bera olmadim — model bo'sh natija qaytardi. "
                    "So'rovingizni boshqacha shaklda yozib ko'ring yoki aniqroq "
                    "ayting (men nima qilishim kerakligini).")
        # AUDIT: "I could not generate" bilan boshlanishi SHART — bu matn
        # `_cacheable_out` junk-guardining kanonik markeri (test kontrakti:
        # test_chat_stream_turbo_junk_not_written_to_memory).
        return ("I could not generate a response — the model returned an empty "
                "answer. Please try again or rephrase your request.")

    def _detect_lang(self, messages: list[dict]) -> str:
        """Xabarlardan tilni aniqlaydi (uz/en) — fallback xabari to'g'ri tilda."""
        try:
            import re as _re
            text = " ".join(str(m.get("content") or "") for m in (messages or [])
                            if m.get("role") == "user").lower()
            if _re.search(
                    r"[ʻ'`‘]?[oO]ʻ|[gG]ʻ|ў|қ|ғ|ҳ|ё|o'z|qan|uchun|kerak|salom|"
                    r"rasm|chiz|qilib|so'rang|mushuk|gul|baliq|kapalak|mashina|"
                    r"daraxt|quyosh|yulduz|yurak|raketa|tog|havo|nech|qanday|"
                    r"qanaqa|ko'rsat|yozib|olma|uy|qush|rangda|o'lcham|uslub",
                    text):
                return "uz"
            return "en"
        except Exception:
            return "uz"

    # AUDIT: _draw_unsupported_message O'CHIRILDI — u hech qanday oqimdan
    # chaqirilmas edi (o'lik kod) va mazmuni last-chance retry + deterministik
    # kutubxona bilan eskirgan: rad javoblari endi _retry_generate'dan keladi.

    # ------------------------------------------------------------ #
    # Resolution pipeline
    # ------------------------------------------------------------ #

    def resolve(self, query: str, allow_llm: bool = True, use_memory: bool = True) -> dict:
        """Full pipeline: RAG recall -> deterministic -> (heal) -> LLM fallback.

        Returns a dict with status, confidence, engine, output, trace,
        duration_ms and (ok rezolyutsiyalarda) self_eval. Every resolution
        is remembered in Igris_Memory — istisno: repair qilib bo'lmaydigan
        buzilgan LLM chiqishi (verified='fail') RAG'ni ifloslantirmaslik
        uchun xotiraga YOZILMAYDI.
        """
        t0 = time.perf_counter()

        # 0. RAG recall (memory context, before any engine runs)
        memory_ctx, memory_hits = self.memory.recall(query) if (use_memory and self.memory.enabled) else ("", 0)

        # 1. Deterministic pass
        res: Resolution = self.resolver.resolve(query)

        # 2. Healing pass when deterministic output is weak
        if res.status == "failed":
            healed = self.resolver.heal(query, self.chains.availability(),
                                        self.chains.similarity_map())
            if healed.confidence > 0:
                res = healed

        # 3. Hybrid LLM fallback for low confidence / complex queries
        if allow_llm and self.llm_available() and res.confidence < self.min_confidence:
            # Part L (D2): LLM fallback endi faqat kod emas — user talabining
            # O'ZI asosida javob beradi (eski "har doim Python kodga aylantir"
            # fiksiri qotib qolgan pattern edi). `req.intent == code` bo'lsa
            # kod prompti, aks holda umumiy (req-format/til/chuqurlik bo'yicha).
            req = self._extract_requirements(query, None)
            if req.intent == "code":
                system = (
                    "You are Igris, a coding agent. Convert the user request "
                    "into executable code. Respond with only the code, "
                    "no explanation, in a code fenced block."
                )
            else:
                system = (
                    "You are Igris, a local assistant. Answer the user's request "
                    "directly and truthfully, following exactly the requirements.\n"
                    + req.to_block()
                )
            if memory_ctx:
                system += (
                    "\n\nRelevant recalled knowledge from memory (use only if useful):\n"
                    + memory_ctx
                )
            try:
                llm_out = self.llm.complete(system=system, prompt=query)
            except Exception as llm_exc:
                # LLM xatosi - graceful degradation: deterministic natijani qaytaramiz
                self._mark_llm_failed(str(llm_exc))
                print(f"[igris] LLM failed in resolve, falling back to deterministic: {llm_exc}")
                llm_out = None
            if llm_out:
                # Muvaffaqiyatli LLM chaqiruvi - cooldown'ni tozalaymiz
                self._mark_llm_recovered()
                # AUDIT: extract_code HAR DOIM chaqiriladi — u oddiy matn uchun
                # zararsiz passthrough (strip), lekin model javobni ```fence```
                # bilan o'raganda toza matn/code ajratadi. Ilgari faqat
                # intent=='code' bo'lsa chaqirilardi — fallback yo'lida fence
                # qoldiqlari structure_check'ga xom kirib ketardi.
                code = self.llm.extract_code(llm_out)
                # A2: LLM fallback yo'lida ham struktura tekshiruvi/ta'mirlash —
                # chat final yo'li bilan BIR XIL: code chiqishi repair'dan o'tadi,
                # muammo bo'lsa `structure_check` biriktiriladi va `verified`
                # signali self_eval'ga ulanadi (repaired −0.10 / fail −0.25).
                # Toza javoblar hisobotga tushmaydi (shovqin yo'q).
                code_final, struct_check = self._verify_and_repair(code or "")
                # A1: kod uchun semantik tekshiruv (syntax, mavzu mosligi)
                if struct_check is None:
                    code_final, domain_check = self._domain_verify(code_final or "", query, "code")
                    if domain_check is not None:
                        struct_check = domain_check
                data = {
                    "query": query,
                    "status": "ok",
                    "engine": "llm",
                    "model": self.llm.model,
                    "matched_bricks": res.matched_bricks,
                    "matched_rules": res.matched_rules,
                    "trace": res.trace + ["Engine: Ollama LLM fallback"],
                    "output": code_final or code,
                    "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
                    "duration_ms": (time.perf_counter() - t0) * 1000.0,
                }
                if struct_check is not None:
                    data["structure_check"] = struct_check
                # Ixtiyoriy logprob re-so'ruvi uchun system+query saqlanadi
                # (`_self_eval_for` o'qiydi va olib tashlaydi).
                data["_llm_messages"] = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": query},
                ]
                # A2: self_eval BIR MARTA hisoblanadi, confidence undan olinadi
                # (LLM fallback yo'lida ham javob kalibrlangan bo'ladi).
                # `confidence` DOIM mavjud bo'lishi kerak — intellekt xato
                # bersa ham neytral 0.5 qaytadi (eski _calibrated_confidence
                # fallback'i kabi).
                ev = self._self_eval_for(data)
                data["confidence"] = (ev or {}).get("confidence", 0.5)
                self.refactor.observe(query, data)
                # RAG ifloslanmasligi: repair qilib BO'LMAYDIGAN buzilgan
                # chiqish (structure_check ok=False, verified='fail') xotiraga
                # yozilmaydi — aks holda keyingi recall buzilgan code'ni
                # qaytaradi. Javob foydalanuvchiga baribir qaytadi (fail
                # signali + past confidence bilan); telemetry (refactor)
                # ham yoziladi — faqat RAG tozalanadi.
                if struct_check is None or struct_check.get("ok") is not False:
                    self.memory.on_resolve(query, data)
                return data

        # Return deterministic resolution
        data = res.to_dict()
        data["engine"] = "deterministic" if not data["healed"] else "healed"
        data["memory"] = {"recall_hits": memory_hits, "context_chars": len(memory_ctx)}
        # A2: resolverning heuristic confidence'i o'rniga — SelfEvaluator (2.7)
        # kalibratsiyasi (engine/status/output/memory_hits/healed signallari).
        # Resolverning O'Z bahosi (0.6*rule_score + 0.4*coverage) `resolver_score`
        # sifatida uzatiladi — kuchsiz rule mosligi deterministik OK'ni 1.0 ga
        # cheklab qo'ymaydi (SelfEvaluator engine signalini shu bilan scaley
        # qiladi). FAQAT muvaffaqiyatli (status="ok") rezolyutsiyalar
        # kalibrlanadi — failed/partial (0.0/<=0.5) resolver bahosi saqlanadi,
        # aks holda SelfEvaluator ularni 0.4/0.75 ga ko'tarib, RAG'ni
        # shishirilgan ishonch bilan ifloslantirishi mumkin edi ("low = yomon
        # javob" kontrakti buzilardi). self_eval ham shu yerda BIR MARTA
        # hisoblanadi va `data["self_eval"]`'ga biriktiriladi (resolve natijasi
        # chat natijalari kabi kalibrlangan bo'ladi).
        if data["status"] == "ok":
            data["resolver_score"] = float(res.confidence or 0.0)
            ev = self._self_eval_for(data)
            if ev:
                data["confidence"] = ev.get("confidence", 0.5)
        data["chains"] = self.active_chains(res)
        data["llm_available"] = self.llm_available()
        data["duration_ms"] = (time.perf_counter() - t0) * 1000.0

        # Continuous process analysis (telemetry)
        self.refactor.observe(query, data)
        self.memory.on_resolve(query, data)
        return data

    def chat(self, message: str, history: Optional[list[dict]] = None,
             use_memory: bool = True, progress_cb=None) -> dict:
        """Conversational completion (used by the interface bridge server).

        Chat ham REAL tool'lar bilan ishlaydi: foydalanuvchi rasm chizish, sahifa
        ochish yoki fayl yaratishni so'rasa, model mavjud MCP/registry tool'larini
        chaqiradi, ular bajariladi va javobga `tool_calls` + `image` maydonlari
        qo'shiladi (frontend karta ko'rsatadi). Oddiy savollarda esa to'g'ridan-
        to'g'ri javob beradi.

        CAG (cache-augmented): keshda javob bo'lsa — LLM chaqirilmaydi.
        MAG (memory-augmented): xotira konteksti L1+L2+RAG yig'ib beriladi.

        progress_cb: ixtiyoriy (stage, detail) callback — frontend pipeline
        stepperiga JONLI progress yuboradi (chat run davomida).

        history: [{role: 'user'|'assistant', content: str}, ...]
        """
        t0 = time.perf_counter()
        # A4: har chat yangi manba-to'plam bilan boshlanadi (oldingi chat
        # web-manbalari bu javobga ta'sir qilmasin)
        self._web_sources = None

        # --- TODO COMMAND CHECK ---
        # Todo buyruqlarini tekshiramiz (/todo ... yoki natural language)
        try:
            from task.todo_integration import get_todo_integration
            todo_int = get_todo_integration()
            todo_result = todo_int.process_message(message)
            if todo_result and todo_result.get("is_todo"):
                return self._finalize({
                    "message": message,
                    "content": todo_result["response"],
                    "engine": "todo",
                    "model": self.llm.model,
                    "tool_calls": [],
                    "image": None,
                    "memory": {"recall_hits": 0, "context_chars": 0},
                    "duration_ms": (time.perf_counter() - t0) * 1000.0,
                    "todo": todo_result.get("data"),
                }, None)
        except ImportError:
            pass  # Todo integration not available

        # JONLI PIPELINE: chat boshlanganda — real stage frontend stepperiga yuboriladi
        if progress_cb is not None:
            try:
                progress_cb("plan", "task tahlil qilinmoqda…")
            except Exception:
                pass

        # AGENTIK PIPELINE: zarurat turi aniqlanadi va mos pipeline tanlab
        # QURILADI (chat/math/weather/draw/ui_build/web/code/composition/...).
        # Detektorlar deterministik (LLM chaqirilmaydi) — progress'da pipeline
        # nomi ko'rinadi, oxirida ish yakuni `completion` record'ida
        # konversatsiyaga to'ldiriladi.
        pipeline = self._build_pipeline(message, history)
        # SEMANTIK TALAB (Part L): user talabini struktur modelga o'tkazamiz —
        # javob shakllanishi (til/chuqurlik/format/cheklovlar) shunga moslanadi.
        req = self._extract_requirements(message, history)
        # SO'ROV SEMANTIKASI (core/request_meaning): muammo/maqsad/definitsiya/
        # detaillar + paradigmaviy tahlil (ilmiy/mantiqiy/falsafiy/majoziy/...)
        # + kanal tartibi (LLM-in/LLM-out aralashmasin, noise bo'lmasin).
        # Deterministik (LLM'siz); natija LOKAL `interp` — faqat shu chat
        # record'iga kiradi, keyingi so'rga qolmaydi (anti-noise).
        interp = self._interpret_request(message, pipeline, req)
        # GOAL PIN (Phase 1, §2/§12): user maqsadi immutable Goal sifatida
        # qayd etiladi va system prompt'ga pin qilinadi (context compression'da
        # ham goal yo'qolmaydi). Fail-safe: modul yo'q/bo'sh matn — pin yo'q.
        goal_pin = ""
        try:
            from state.goal_model import Goal, GoalContext
            if message and message.strip():
                goal_pin = GoalContext(Goal.create(message)).prompt_pin()
        except Exception:
            goal_pin = ""
        if progress_cb is not None:
            try:
                progress_cb("plan", f"{pipeline['label']}: {pipeline['clarified']}")
            except Exception:
                pass

        # --- CLARIFICATION GATE (§3.3.c) ---
        # Pre-loop: so'rov yetarli darajada aniqlanganini tekshiramiz.
        # Agar kerakli maydonlar yetishmasa — clarify event yuboriladi va
        # agent SUHBATGA QAYTADI (loop boshlanmaydi). Foydalanuvchi javob
        # bergandan keyin pipeline QAYTA ishga tushadi.
        clar = self._clarification_gate(req)
        if clar is not None:
            return self._finalize({
                "message": message,
                "content": clar["question"],
                "engine": "clarification",
                "model": self.llm.model,
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "duration_ms": (time.perf_counter() - t0) * 1000.0,
                "clarification": {
                    "question": clar["question"],
                    "missing_fields": clar["missing_fields"],
                },
            }, pipeline, interp)

        # INTELLEKT 2.10 (harm-filter): operator buyrug'i aniq zarar
        # chegarasidan o'tsa — rad etiladi, sabab tushuntiriladi. Bu eng
        # birinchi qadam (qo'llanma 4-bo'lim oqimi). Rad etilgan so'rov
        # LLM'ga ham bormaydi, xotiraga ham yozilmaydi.
        verdict = self.intelligence.screen(message)
        if not verdict.allowed:
            if progress_cb is not None:
                try:
                    progress_cb("review", "so'rov rad etildi (zarar filtri)")
                except Exception:
                    pass
            refusal = verdict.reason or "Bu so'rov aniq zarar chegarasidan o'tadi."
            data = {
                "message": message,
                "content": refusal,
                "engine": "harm-filter",
                "model": self.llm.model,
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "duration_ms": (time.perf_counter() - t0) * 1000.0,
                "refused": True,
                "refusal_category": verdict.category,
                "self_eval": self.intelligence.evaluate(
                    engine="harm-filter", status="ok", output=refusal
                ).to_dict(),
            }
            return self._finalize(data, pipeline, interp)

        # INTELLEKT 2.6+2.12: foydalanuvchi xabarini kuzatamiz (profil signali)
        # va ohangni aniqlaymiz — faqat moslashtirish uchun, manipulyatsiya emas.
        try:
            self.intelligence.observe(message)
        except Exception:
            pass

        # TEZ DETERMINISTIK YO'L: ob-havo so'rovi — brauzer/LLM keraksiz,
        # Open-Meteo API orqali 2-4 soniyada aniq javob (qwen3:8b katta modelni
        # ishga tushirmaydi — tezlik va aniqlik kafolati).
        quick = self._quick_weather(message)
        if quick is not None:
            if progress_cb is not None:
                try:
                    progress_cb("review", "javob tayyor")
                except Exception:
                    pass
            data = {
                "message": message,
                "content": quick,
                "engine": "weather-quick",
                "model": self.llm.model,
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "duration_ms": (time.perf_counter() - t0) * 1000.0,
                "quick": True,
            }
            if self.memory.enabled:
                try:
                    self.memory.on_resolve(message, {"output": quick, "engine": "weather-quick", "confidence": self._confidence_for(data)})
                except Exception:
                    pass
            return self._finalize(data, pipeline, interp)

        # INTELLEKT 2.2 (logic): oddiy arifmetika — deterministik tez yo'l
        # (LLM/brauzer keraksiz; xavfsiz safe_math orqali hisoblanadi).
        quick_math = self._quick_math(message)
        if quick_math is not None:
            if progress_cb is not None:
                try:
                    progress_cb("review", "javob tayyor")
                except Exception:
                    pass
            data = {
                "message": message,
                "content": quick_math,
                "engine": "math-quick",
                "model": self.llm.model,
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "duration_ms": (time.perf_counter() - t0) * 1000.0,
                "quick": True,
            }
            if self.memory.enabled:
                try:
                    self.memory.on_resolve(message, {"output": quick_math, "engine": "math-quick", "confidence": self._confidence_for(data)})
                except Exception:
                    pass
            return self._finalize(data, pipeline, interp)

        # --- SUPERVISOR INTEGRATION (§9) ---
        # Complex so'rovlarda (1+ ta loop kerak) avtomatik DAG quradi.
        # Tartib: harm-filter VA tez yo'llardan KEYIN — rad etilishi kerak
        # so'rov LLM DAG rejasiga ketmaydi, ob-havo/arifmetika esa supervisor
        # checkpoint yukisiz darhol javob oladi.
        supervisor_result = self._run_supervisor(message, pipeline, progress_cb)
        if supervisor_result is not None:
            supervisor_tools = list(supervisor_result.get("tool_calls") or [])
            data = {
                "message": message,
                "content": supervisor_result.get("summary", ""),
                "engine": "supervisor",
                "model": self.llm.model if self.llm_available() else "offline",
                # Supervisor node'lari bajargan haqiqiy amallar yuqori
                # response'da ham saqlanadi. Aks holda UI va evidence guard
                # toolsiz deb o'ylab, soxta yakunlashni yashirardi.
                "tool_calls": supervisor_tools,
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "duration_ms": (time.perf_counter() - t0) * 1000.0,
                "supervisor": {
                    "status": supervisor_result.get("status"),
                    "iterations_used": supervisor_result.get("iterations_used", 0),
                    "nodes": supervisor_result.get("nodes", {}),
                },
            }
            if supervisor_result.get("files_changed"):
                data["files_changed"] = supervisor_result["files_changed"]
            # Non-atomic yo'lda ham "bajardim" faqat dalil bilan chiqishi
            # shart. Kerak bo'lsa guard bir real tool urinishini bajaradi.
            try:
                checked = self._enforce_action_evidence(
                    [], self._chat_tools(), data["content"], supervisor_tools,
                    None, need=pipeline.get("need", "chat"), progress=progress_cb,
                    request=message, req=req, web=bool(self._web_strategy(message)),
                    max_rounds=pipeline.get("max_iter"),
                    loop_shape=pipeline.get("loop_shape"))
                data["content"], data["tool_calls"], data["image"], note = checked
                if note:
                    data["action_evidence"] = note
            except Exception:
                pass
            return self._finalize(data, pipeline, interp)

        memory_ctx, memory_hits = self.memory.recall(message) if (use_memory and self.memory.enabled) else ("", 0)

        # MAG: L1+L2+RAG kontekstini yig'amiz (RAG recall'dan to'liqroq).
        # RAG recall allaqachon kontekst bergan bo'lsa — MAG takror ishlamaydi.
        mag_ctx = ""
        if use_memory and self.memory.enabled and not history and not memory_ctx:
            try:
                mag = self._mag()
                mag_ctx = mag.assemble(message)["context"] if mag else ""
            except Exception:
                mag_ctx = ""

        # INTELLEKT 2.1/2.2/2.6/2.12: system prompt'ni moslashtiramiz —
        # domain lug'at + foydalanuvchi profili + ohang + CoT yo'naltirish.
        # Bu faqat javob SIFATINI o'zgartiradi, maqsadli natijani emas.
        system = self.intelligence.adapt_system(CHAT_TOOLS_SYSTEM, message)
        cot = self.intelligence.reasoning_suffix()
        if cot and cot not in system:
            system = (system or "") + "\n\n" + cot
        # REAL bugungi sana — eskirgan/soxta sana javoblarini oldini oladi
        system = (system or "") + self._today_note()
        # INTELLEKT 2.3 (musiqa): musiqa/ovoz so'rovi — glossary + yo'naltirish
        music_dir = self._intel("music_directive", message)
        if music_dir:
            system += "\n\n" + music_dir
        # INTELLEKT 2.4 + 2.8 (spatial + naturalist): loyiha strukturasi so'rovi —
        # workspace daraxti + til taqsimoti konteksti (agent muhitni ko'radi).
        _sp = None
        if self._is_structure_request(message):
            _sp = self._spatial_env_context(message)
            if _sp:
                system += "\n\n" + _sp[0]
        # CHIZISH SO'ROVI: svg-artist skill ko'rsatmasi AVTOMATIK qo'shiladi —
        # model har chizishda professional SVG (gradient/soya/qatlamlar) yaratadi
        if self._is_draw_request(message):
            skill_text = self._draw_skill_text()
            if skill_text:
                system += "\n\n" + skill_text
            # Oxirgi chizma sifat feedback'i — model avvalgi xatolarini
            # takrorlamasligi uchun (RAG recall'ga tayanmasdan ham ishlaydi)
            fb = self._draw_feedback_context()
            if fb:
                system += "\n\n" + fb
        # WEB SO'ROVI: qaror qoidalari — model eng arzon vositanı tanlaydi
        # (to'g'ridan-to'g'ri javob > web_fetch > web AI subagent > browser).
        web_strategy = self._web_strategy(message)
        # Qoidalar faqat web_ai_bridge MCP ulangan bo'lsa qo'shiladi — aks holda
        # modelga mavjud bo'lmagan tool'lar (ask_web_ai/browser) eslatilmaydi.
        if web_strategy and self._mcp() is not None:
            system += "\n\n" + self._web_decision_rules(web_strategy)
        # STACK GUIDE: kod so'rovida framework/til aniqlansa — model aniq
        # buyruqlarni (npm/pip/mvn...) ishlatishi uchun yo'naltiruv qo'shiladi.
        stack_guide = self._stack_guide(pipeline)
        if stack_guide:
            system += "\n\n" + stack_guide
        if memory_ctx:
            system += (
                "\n\nRelevant recalled knowledge from memory (use only if useful):\n"
                + memory_ctx
            )
        elif mag_ctx:
            system += "\n\nMemory context:\n" + mag_ctx
        # SEMANTIK TALAB BLOKI (Part L): model javobni req'ga mos shakllantiradi.
        if self.llm_available():
            system += "\n\n" + req.to_block()
        # GOAL PIN (Phase 1, §12): ORIGINAL GOAL system prompt'ga pin qilinadi
        # (context o'ssa/umumlashtirilsa ham goal yo'qolmaydi).
        if goal_pin:
            system += "\n\n" + goal_pin

        # §6 CONTEXT BUDGET (Phase 3): prompt qatlamlarini token budget bilan
        # sig'dirish — overflow'da memory/history eskilari tashlanadi,
        # goal_pin va user HECH QACHON. Graceful degradation kafolati.
        try:
            system, _kept_hist, _budget_report = self.context_budget.fit_prompt(
                base_system=system, goal_pin=goal_pin,
                history=(history or [])[-12:], user_message=message)
            self._last_budget_report = _budget_report
        except Exception:
            self._last_budget_report = None

        messages: list[dict] = [{"role": "system", "content": system}]
        for h in (history or [])[-12:]:
            role = h.get("role")
            content = h.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})
        # Kesh kaliti STABIL bo'ladi: CHAT_TOOLS_SYSTEM (o'zgarmas) + message.
        # memory_ctx kesh kalitiga kirmaydi — aks holda birinchi javob xotirada
        # eslab qolingach, keyingi takroriy savolda kontekst o'zgarib miss bo'lardi.
        if not history and not self._is_draw_request(message) and not self._is_date_question(message):
            cache = self._cag()
            if cache is not None:
                cached = cache.get(CHAT_TOOLS_SYSTEM, message)
                if cached is not None:
                    # AUDIT (CAG hit): keshlangan matn ham repair'dan o'tadi —
                    # eski/buzilgan kesh yozuvlari ham `data["content"]` kabi
                    # canonical (repair'dan keyingi) matn bo'ladi; memory va
                    # confidence shundan hisoblanadi (xom kesh bilan tafovut yo'q).
                    out_final, struct_check = self._verify_and_repair(cached)
                    tool_calls: list[dict] = []
                    image: Optional[str] = None
                    ev_note: Optional[dict] = None
                    # ACTION EVIDENCE (CAG): keshdagi eski "qildim" da'vosi
                    # ham isbotdan o'tadi — soxta bo'lsa to'g'rilanadi va
                    # kesh HALOL matn bilan yangilanadi (takroriy xato yo'q).
                    try:
                        _ev_c = self._enforce_action_evidence(
                            messages,
                            self._chat_tools(include_web=bool(web_strategy),
                                             web_strategy=web_strategy),
                            out_final or cached, [], None,
                            need=pipeline.get("need", "chat"),
                            progress=progress_cb, request=message, req=req,
                            web=bool(web_strategy),
                            max_rounds=pipeline.get("max_iter"),
                            loop_shape=pipeline.get("loop_shape"))
                        if _ev_c[3] is not None:
                            out_final, tool_calls, image = _ev_c[0], _ev_c[1], _ev_c[2]
                            ev_note = _ev_c[3]
                            if self._cacheable_out(out_final):
                                cache.put(CHAT_TOOLS_SYSTEM, message, out_final)
                    except Exception:
                        pass
                    engine = "llm+tools" if tool_calls else "cag"
                    duration = (time.perf_counter() - t0) * 1000.0
                    data = {
                        "message": message,
                        "content": out_final or cached,
                        "engine": engine,
                        "model": self.llm.model,
                        "tool_calls": tool_calls,
                        "image": image,
                        "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
                        "duration_ms": duration,
                        "cag": {"hit": True},
                    }
                    if ev_note:
                        data["action_evidence"] = ev_note
                    if struct_check is not None:
                        data["structure_check"] = struct_check
                    # keshlangan javob ham xotiraga yoziladi (RAG boyiydi) — final
                    # yo'li bilan BIR XIL: `data["content"]` (repair'dan keyingi)
                    # saqlanadi, bo'sh/xato javoblar yozilmaydi. Fail-guard:
                    # repair qilib BO'LMAYDIGAN chiqish ham yozilmaydi.
                    if (self.memory.enabled and self._cacheable_out(data.get("content"))
                            and (struct_check is None or struct_check.get("ok") is not False)):
                        self.memory.on_resolve(message, {"output": data["content"], "engine": "cag", "confidence": self._confidence_for(data)})
                    return self._finalize(data, pipeline, interp)

        tool_calls: list[dict] = []
        image: Optional[str] = None
        redraw_note: Optional[dict] = None
        evidence_note: Optional[dict] = None
        out = ""
        engine = "deterministic"

        # INTELLEKT 2.11 (creative): kreativ so'rov — multi-temperature variantlar
        # (CAG'ga tushmagan, tool kerak bo'lmagan, TARIXSIZ oddiy so'rovda ishlaydi
        # — tarixli davomiy so'rovda kontekst yo'qolmasligi uchun oddiy yo'l ishlaydi).
        creative_data = None
        if not history:
            creative_data = self._creative_variants(message, system=system, memory_hits=memory_hits)
        if creative_data is not None:
            if progress_cb is not None:
                try:
                    progress_cb("review", "kreativ variantlar tayyorlanmoqda…")
                except Exception:
                    pass
            return self._finalize(creative_data, pipeline, interp)

        # TURBO tez yo'l faqat tool'siz oddiy savollarga ishlaydi (rasm chizish,
        # fayl yaratish, web ochish kabi vazifalar katta modelni talab qiladi).
        # TOOL KERAKLIGI — pipeline/requirement asosida (tor kalit so'z
        # ro'yxati emas): "o'yinini yasab ber" / "saqlangan manzil?" kabi
        # yaratuvchi so'rovlarda model TOOLSIZ javob berib, ish qilgan bo'lib
        # ko'rsatardi (hallucination). Endi creator pipeline/needs_tools doim
        # tool yo'lini ochadi.
        tool_needed = (
            self._is_draw_request(message)
            or self._needs_web(message)
            or pipeline.get("need") in request_classifier.CREATOR_NEEDS
            or bool(getattr(req, "needs_tools", False))
            or bool(self._registry() and any(
                w in message.lower()
                for w in ("fayl", "file", "write", "yarat", "create", "dastur", "kod", "code")
            ))
        )

        # AUDIT: `llm_failed` HAR DOIM ishga tushiriladi — ilgari faqat
        # `llm_available()` bloki ichida edi, offline rejimda (LLM yo'q)
        # 2066-qatorda UnboundLocalError berardi (offline chat to'liq o'lik edi).
        llm_failed = False
        if self.llm_available():
            # WEB avtomatizatsiya: so'rovda sayt/URL/brauzer ehtiyoji bo'lsa —
            # browser tool'lari chatda ham avtomatik ochiladi (model ularni
            # ishlatishi uchun). Oddiy chatda ochilmaydi (keraksiz chaqiruvlar
            # oldini oladi).
            web_needed = bool(web_strategy)
            try:
                # TURBO tez yo'l: oddiy savol + tez rejim -> kichik/tez modelga
                # yo'naltiramiz (tool kerak emas, katta model ishlamaydi).
                if (
                    getattr(self.llm, "turbo", False)
                    and not tool_needed
                    and not history
                ):
                    fast = self.llm.chat_fast(messages)
                    if fast and fast.strip():
                        # AUDIT (turbo yo'li): final yo'l bilan BIR XIL — repair'dan
                        # keyingi matn saqlanadi, memory output == confidence signali
                        # == ko'rsatilgan javob (raw `out` emas, tafovut yo'q).
                        out_final, struct_check = self._verify_and_repair(fast.strip())
                        engine = "llm-fast"
                        data = {
                            "message": message,
                            # Part L: bo'sh javob o'rniga req-aware retry (canned emas)
                            "content": out_final or self._retry_generate(messages, req),
                            "engine": engine,
                            "model": self.llm.fast_model or self.llm.model,
                            "tool_calls": [],
                            "image": None,
                            "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
                            "duration_ms": (time.perf_counter() - t0) * 1000.0,
                            "turbo": True,
                        }
                        if struct_check is not None:
                            data["structure_check"] = struct_check
                        # logprob re-so'ruvi (ixtiyoriy) uchun asl messages
                        if engine in ("llm", "llm+tools", "llm-fast"):
                            data["_llm_messages"] = messages
                        # Guard ham final yo'l bilan bir xil: bo'sh/xato javoblar RAG'ga
                        # tushmaydi (eski holatda faqat `engine != "offline"` edi).
                        # Fail-guard: repair qilib BO'LMAYDIGAN chiqish ham yozilmaydi.
                        if (engine != "offline" and self._cacheable_out(data.get("content"))
                                and (struct_check is None or struct_check.get("ok") is not False)):
                            self.memory.on_resolve(message, {"output": data["content"], "engine": data["engine"], "confidence": self._confidence_for(data)})
                        return self._finalize(data, pipeline, interp)
                tools = self._chat_tools(include_web=web_needed, web_strategy=web_strategy)
                content, tool_calls, image, redraw_note = self._chat_with_redraw(
                    messages, tools, web=web_needed, progress=progress_cb, request=message,
                    req=req, max_rounds=pipeline.get("max_iter"),
                    loop_shape=pipeline.get("loop_shape"))
                # ACTION EVIDENCE: "qildim" da'vosi isbotsiz bo'lmasin —
                # model haqiqatan tool chaqiradi yoki halol javob beradi.
                content, tool_calls, image, evidence_note = self._enforce_action_evidence(
                    messages, tools, content, tool_calls, image,
                    need=pipeline.get("need", "chat"), progress=progress_cb,
                    request=message, req=req, web=web_needed,
                    max_rounds=pipeline.get("max_iter"),
                    loop_shape=pipeline.get("loop_shape"))
                out = content
                engine = "llm+tools" if tool_calls else "llm"
                if not (out or "").strip():
                    # Part L: bo'sh javob / web-toolsiz matn o'rniga req-aware retry
                    # (canned "Veb so'rovi aniqlandi..." emas — real urinish).
                    out = self._retry_generate(messages, req)
                # Muvaffaqiyatli LLM chaqiruvi - cooldown'ni tozalaymiz
                self._mark_llm_recovered()
                # KUZATUV: strategiya to'g'ri tanlandimi + model nima qildi
                # (`_mcp_cache` — server ishga tushirmaydi, faqat holatni o'qiydi)
                self._log_web_strategy(message, web_strategy, tool_calls, engine,
                                       mcp_ok=self._mcp_cache is not None,
                                       content_len=len(out or ""))
            except Exception as llm_exc:
                # LLM xatosi — graceful degradation: bricks+RAG bilan davom etamiz
                llm_failed = True
                self._mark_llm_failed(str(llm_exc))
                print(f"[igris] LLM failed in chat, degrading: {llm_exc}")

        if not self.llm_available() or llm_failed:
            # offline/graceful degradation: bricks + RAG bilan best-effort
            engine = "offline" if not llm_failed else "degraded"  # noqa: F821 — llm_failed doim aniqlangan (yuqorida)
            # `_mcp_cache` — offline yo'lida MCP serverlarni ishga tushirmaydi
            self._log_web_strategy(message, web_strategy, [], engine,
                                   mcp_ok=self._mcp_cache is not None)
            res = self.resolve(message, allow_llm=False, use_memory=use_memory)
            if res.get("status") == "ok" and res.get("output"):
                out = res["output"]
            else:
                # Bricks+RAG ham javob bera olmadi — foydalanuvchiga tushuntiramiz
                if llm_failed:
                    out = (
                        f"IGRIS LLM xatosi tufayli vaqtincha cheklangan holatda ishlayapti. "
                        f"Deterministik dvigatel (bricks + RAG xotira) bilan javob berishga "
                        f"urinildi, lekin bu so'rov uchun yetarli ma'lumot topilmadi. "
                        f"LLM avtomatik tiklanadi ({self._llm_cooldown:.0f}s ichida). "
                        f"Xato: {str(llm_exc)[:100] if llm_failed else 'noma\'lum'}"
                    )
                else:
                    out = (
                        "IGRIS hozir javob bera olmadi — Ollama (lokal AI) "
                        "yoqilmagan. Iltimos `run.bat` orqali yoki terminalda "
                        "`ollama serve` bilan Ollama'ni ishga tushiring, so'ng qayta "
                        "yozing. (Deterministik dvigatel faqat oldindan ma'lum bo'lgan "
                        "oddiy kod so'rovlarini biladi — suhbat savollariga javob "
                        "bera olmaydi.)"
                    )

        if progress_cb is not None:
            try:
                progress_cb("review", "javob yozilmoqda…")
            except Exception:
                pass

        out_final, struct_check = self._verify_and_repair(out or "")
        # A1: kod/chizma uchun semantik tekshiruv
        if struct_check is None:
            need = pipeline.get("need", "chat")
            out_final, domain_check = self._domain_verify(out_final or "", message, need)
            if domain_check is not None:
                struct_check = domain_check
        # Part L (B2): talab compliance — nomoslik bo'lsa 1 marta qayta generatsiya.
        # Part O: rasm/visual natija (image mavjud) — LLM compliance KERAKSIZ
        # (chizma deterministik yoki draw-pipeline orqali tekshirilgan); sekin
        # LLM chaqiruvi tezlikni buzmasin.
        content_final = out_final or ""
        if content_final and not image and engine != "offline" and self.llm_available() \
                and req.output_format not in ("image",):
            content_final = self._compliance(content_final, req, message)
        data = {
            "message": message,
            "content": content_final or self._retry_generate(messages, req),
            "engine": engine,
            "model": self.llm.model,
            "tool_calls": tool_calls,
            "image": image,
            "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
            "duration_ms": (time.perf_counter() - t0) * 1000.0,
        }
        if redraw_note:
            data["redraw"] = redraw_note
        # ACTION EVIDENCE natijasi javob bilan birga yuboriladi (audit/UI).
        if evidence_note:
            data["action_evidence"] = evidence_note
        # INTELLEKT 2.2: chiqish strukturasi tekshiruvi natijasi (JSON/kod)
        if struct_check is not None:
            data["structure_check"] = struct_check
        # INTELLEKT 2.4/2.8: fazoviy + naturalist xulosasi (loyiha strukturasi)
        if _sp:
            data["spatial"] = _sp[1]
        # LLM logprob re-so'ruvi (ixtiyoriy) uchun asl messages saqlanadi —
        # `_self_eval_for` uni o'qiydi va olib tashlaydi (javob toza qoladi).
        if engine in ("llm", "llm+tools", "llm-fast"):
            data["_llm_messages"] = messages
        # CAG: yangi javobni keshga yozamiz. Faqat SIFATLI javoblar keshlanadi —
        # offline/bo'sh/xato javoblar, rasm/tool va sana so'rovlari keshga tushmaydi.
        # AUDIT (CAG put): keshlangan matn AYNAN `data["content"]` (= repair'dan
        # keyingi, ko'rsatilgan javob) bo'ladi — xom `out` emas. Aks holda keyingi
        # CAG-hit xom/buzilgan matnni qaytarib, repair chetlab o'tilardi
        # (keshlangan out vs content tafovuti).
        if (self.llm_available() and not tool_calls
                and not self._is_draw_request(message)
                and not self._is_date_question(message)
                and self._cacheable_out(data.get("content"))
                # Fail-guard: repair qilib bo'lmagan chiqish keshlanmaydi
                and (struct_check is None or struct_check.get("ok") is not False)):
            cache = self._cag()
            if cache is not None:
                cache.put(CHAT_TOOLS_SYSTEM, message, data["content"])
        # remember the exchange (L2 solution-memory + L1 short-turn). Offline
        # xabar xotiraga yozilmaydi; bo'sh/xato javoblar ham YO'Q — RAG'ga
        # "javob bermadi" deb o'rganib qolmasligi uchun.
        # Xotiraga `data["content"]` (= out_final, repair'dan keyingi matn)
        # yoziladi — confidence `_confidence_for(data)` orqali AYNAN shu
        # matndan hisoblanadi (raw `out` emas), tafovut yo'q. Guard ham
        # saqlanadigan matnga qaraydi (stream final yo'li bilan bir xil).
        # Fail-guard: repair qilib BO'LMAYDIGAN chiqish ham RAG'ga yozilmaydi.
        if (engine != "offline" and self._cacheable_out(data.get("content"))
                and (struct_check is None or struct_check.get("ok") is not False)):
            self.memory.on_resolve(message, {"output": data["content"], "engine": data["engine"], "confidence": self._confidence_for(data)})
        return self._finalize(data, pipeline, interp)

    def chat_stream(self, message: str, history: Optional[list[dict]] = None,
                    use_memory: bool = True, progress_cb=None):
        """Token-ustali chat — generator bo'lib VOQEALAR beradi (SSE uchun).

        `/api/chat` sinxron javob qaytaradi; bu generator esa javobni
        TOKEN-KETMA-TOKEN uzatadi — frontend agent yozayotginda matnni jonli
        ko'radi (bir necha daqiqa bo'sh kutish o'rniga). Har bir `yield` dict:

          {"type": "stage", "stage": "plan|read|edit|test|review", "detail": str, "layer": "planning"}
          {"type": "thinking", "content": "<fikrlash deltasi>"}  — qwen3 reasoning
          {"type": "token", "content": "<delta>", "source": "llm"}     — yangi token parchası
          {"type": "done", **chat_result_dict}        — to'liq yakuniy natija
          {"type": "layer_start", "layer": "clarification"}  — clarification bosqichi boshlandi
          {"type": "layer_done", "layer": "clarification", "status": "complete"}  — clarification tugadi
          {"type": "clarify", "question": "..."}  — userdan qo'llab-quvvatlanuvchi savol
          {"type": "validation_error", "issue": "..."}  — natija validatsiya muammosi

        Thinking hodisalari: qwen3 kabi reasoning modellarda fikrlash bosqichi
        ham token-ketma-token uzatiladi (frontend "thinking" blokida ko'rsatadi),
        so'ng yakuniy javob `token` hodisalari bilan oqadi. `done` voqeasi
        `thinking` maydonida TO'LIQ fikrlash matnini ham olib keladi.

        Xulq:
          - harm-filter / ob-havo / CAG kesh / turbo-fast / tool'lar kabi
            bosqichlar BUFFERED ishlaydi (ular bir zumda yoki round'larda
            tugaydi) — ularda bitta `done` voqeasi chiqadi.
          - oddiy suhbat javoblari (tool kerak emas) — `llm.chat_stream()`
            orqali REAL token oqimi uzatiladi.
          - stream uzilsa (transport xatosi) — `self.chat()`'ga qaytamiz va
            yaxlit natijani `done` sifatida beramiz (javob yo'qolmaydi).
          - har bir bosqich layer_start/layer_done yordamida kuzatadi;
            tokenlar `source` maydonida ishlab chiqaruvchini (llm/tool/skill/mcp) namoyish etadi.
        """
        t0 = time.perf_counter()
        # A4: har chat yangi manba-to'plam bilan boshlanadi (chat() bilan bir xil)
        self._web_sources = None

        # AGENTIK PIPELINE: zarurat turi aniqlanadi va pipeline quriladi —
        # chat() bilan BIR XIL (har bir done voqeasida completion record
        # konversatsiyaga to'ldiriladi).
        pipeline = self._build_pipeline(message, history)
        # SEMANTIK TALAB (Part L): chat() bilan BIR XIL — req modeli.
        req = self._extract_requirements(message, history)
        # SO'ROV SEMANTIKASI (core/request_meaning): muammo/maqsad/definitsiya/
        # detaillar + paradigmaviy tahlil (ilmiy/mantiqiy/falsafiy/majoziy/...)
        # + kanal tartibi (LLM-in/LLM-out aralashmasin, noise bo'lmasin).
        # Deterministik (LLM'siz); natija LOKAL `interp` — faqat shu chat
        # record'iga kiradi, keyingi so'rga qolmaydi (anti-noise).
        interp = self._interpret_request(message, pipeline, req)
        # GOAL PIN (Phase 1, §2/§12): chat() bilan BIR XIL — immutable Goal.
        goal_pin = ""
        try:
            from state.goal_model import Goal, GoalContext
            if message and message.strip():
                goal_pin = GoalContext(Goal.create(message)).prompt_pin()
        except Exception:
            goal_pin = ""

        # --- CLARIFICATION GATE (§3.3.c) ---
        # Pre-loop: so'rov yetarli darajada aniqlanganini tekshiramiz.
        # Agar kerakli maydonlar yetishmasa — clarify event yuboriladi va
        # agent SUHBATGA QAYTADI (loop boshlanmaydi). Foydalanuvchi javob
        # bergandan keyin pipeline QAYTA ishga tushadi.
        # (Oqim tartibi: blok _done() yordamchisidan KEYIN — pastda.)

        def _emit_stage(stage: str, detail: str, layer: str = "planning"):
            try:
                return {"type": "stage", "stage": stage, "detail": str(detail)[:120], "layer": layer}
            except Exception:
                return None

        def _done(data: dict):
            data.setdefault("duration_ms", (time.perf_counter() - t0) * 1000.0)
            data.setdefault("model", self.llm.model)
            # INTELLEKT 2.2: chiqish strukturasi tekshiruvi + JSON ta'mirlash
            content = data.get("content") or ""
            if isinstance(content, str) and content.strip():
                fixed, sc = self._verify_and_repair(content)
                # A1: kod/chizma uchun semantik tekshiruv
                if sc is None:
                    need = pipeline.get("need", "chat")
                    fixed, domain_check = self._domain_verify(fixed, message, need)
                    if domain_check is not None:
                        sc = domain_check
                if sc is not None:
                    data["content"] = fixed
                    data["structure_check"] = sc
                    # Verifikator signali endi bor — agar memory yozuvi bu
                    # repair'dan OLDIN sodir bo'lgan bo'lsa, keshlangan
                    # self_eval eskirgan bo'lardi. Barcha LLM yo'llarida
                    # (chat/chat_stream turbo+plain+tool) repair endi data
                    # yig'ish paytida qilinadi — bu `pop` faqat repair qilib
                    # BO'LMAYDIGAN fail holati uchun xavfsizlik to'ri (u
                    # yerda ham memory == done: ikkalasi ham bir xil matn,
                    # past confidence).
                    data.pop("self_eval", None)
            # SO'ROV SEMANTIKASI: interpretation done voqeasiga kiritiladi
            if interp and not data.get("interpretation"):
                data["interpretation"] = interp
            # §3.2 REVIEW LOOP: stream'da ham xuddi shu build_verify/reflexion
            self._review_repair(data, pipeline)
            # M7: kesh/RAG review'dan oldin yozilgan — almashtirilsa sinxronlaymiz
            self._review_resync(data)
            # AGENTIK completion: ish yakuni konversatsiyaga to'ldiriladi
            data["completion"] = self._work_completion(pipeline, data)
            # INTELLEKT 2.7: ishonch kalibratsiyasi — har bir javobga birikadi
            self._with_self_eval(data)
            ev = {"type": "done"}
            ev.update(data)
            return ev

        # --- CLARIFICATION GATE (§3.3.c) — pre-loop gate ---
        # So'rov yetarli aniqlanmagan bo'lsa — savol beriladi va oqim SHU
        # YERDA tugaydi (agent o'zining javobini BERMAYDI — aks holda
        # foydalanuvchi savol va javobni bir vaqtda ko'radi).
        # Frontend kontrati: oqim `done` voqeasisiz tugasa — "stream finished
        # without done" xato sifatida qabul qilinadi, shuning uchun clarify
        # ham terminal `done` bilan yakunlanadi (matn = savol).
        clar = self._clarification_gate(req)
        if clar is not None:
            yield {"type": "layer_start", "layer": "clarification"}
            yield {
                "type": "clarify",
                "question": clar["question"],
                "missing_fields": clar["missing_fields"],
            }
            yield {"type": "layer_done", "layer": "clarification", "status": "complete"}
            yield _done({
                "message": message,
                "content": clar["question"],
                "engine": "clarification",
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "clarification": {
                    "question": clar["question"],
                    "missing_fields": clar["missing_fields"],
                },
            })
            return

        # JONLI PIPELINE: plan bosqichi — qurilgan pipeline nomi bilan
        yield {"type": "layer_start", "layer": "planning"}
        stage = _emit_stage("plan", f"{pipeline['label']}: {pipeline['clarified']}", layer="planning")
        if stage:
            yield stage
        yield {"type": "layer_done", "layer": "planning", "plan": pipeline, "status": "complete"}

        # INTELLEKT 2.10 (harm-filter) — chat() bilan bir xil oqim
        verdict = self.intelligence.screen(message)
        if not verdict.allowed:
            stage = _emit_stage("review", "so'rov rad etildi (zarar filtri)")
            if stage:
                yield stage
            refusal = verdict.reason or "Bu so'rov aniq zarar chegarasidan o'tadi."
            yield _done({
                "message": message,
                "content": refusal,
                "engine": "harm-filter",
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "refused": True,
                "refusal_category": verdict.category,
            })
            return

        try:
            self.intelligence.observe(message)
        except Exception:
            pass

        # Ob-havo tez yo'li — darhol, buffered
        quick = self._quick_weather(message)
        if quick is not None:
            stage = _emit_stage("review", "javob tayyor")
            if stage:
                yield stage
            yield _done({
                "message": message,
                "content": quick,
                "engine": "weather-quick",
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "quick": True,
            })
            return

        # INTELLEKT 2.2 (logic): oddiy arifmetika — deterministik tez yo'l
        quick_math = self._quick_math(message)
        if quick_math is not None:
            stage = _emit_stage("review", "javob tayyor")
            if stage:
                yield stage
            yield _done({
                "message": message,
                "content": quick_math,
                "engine": "math-quick",
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "quick": True,
            })
            return

        # --- SUPERVISOR INTEGRATION (§9) ---
        # Complex so'rovlarda (1+ ta loop kerak) avtomatik DAG quradi va
        # bajaradi. SSE event'lari bilan: supervisor_start → supervisor_done.
        # Tartib: harm-filter VA tez yo'llardan KEYIN (chat() bilan bir xil) —
        # rad etilishi kerak so'rov DAG rejasiga ketmaydi, ob-havo/arifmetika
        # esa supervisor checkpoint yukisiz darhol javob oladi.
        supervisor_events = []
        for ev in self._run_supervisor_stream(message, pipeline):
            supervisor_events.append(ev)
            yield ev
        # Agar supervisor ishlagan bo'lsa — natijani done sifatida beramiz
        if supervisor_events:
            done_event = next(
                (e for e in supervisor_events if e.get("type") == "supervisor_done"),
                None,
            )
            if done_event:
                yield _done({
                    "message": message,
                    "content": done_event.get("summary", ""),
                    "engine": "supervisor",
                    "tool_calls": [],
                    "image": None,
                    "memory": {"recall_hits": 0, "context_chars": 0},
                    "supervisor": {
                        "status": done_event.get("status"),
                        "iterations_used": done_event.get("iterations_used", 0),
                        "nodes": done_event.get("nodes", {}),
                    },
                })
                return

        memory_ctx, memory_hits = self.memory.recall(message) if (use_memory and self.memory.enabled) else ("", 0)

        # MAG: L1+L2+RAG konteksti — chat() bilan bir xil (stream ham bir xil
        # sifatni olishi uchun; aks holda streaming javoblar pastroq bo'lardi).
        mag_ctx = ""
        if use_memory and self.memory.enabled and not history and not memory_ctx:
            try:
                mag = self._mag()
                mag_ctx = mag.assemble(message)["context"] if mag else ""
            except Exception:
                mag_ctx = ""

        system = self.intelligence.adapt_system(CHAT_TOOLS_SYSTEM, message)
        cot = self.intelligence.reasoning_suffix()
        if cot and cot not in system:
            system = (system or "") + "\n\n" + cot
        # REAL bugungi sana — eskirgan/soxta sana javoblarini oldini oladi
        system = (system or "") + self._today_note()
        # INTELLEKT 2.3 (musiqa): musiqa/ovoz so'rovi — glossary + yo'naltirish
        music_dir = self._intel("music_directive", message)
        if music_dir:
            system += "\n\n" + music_dir
        # INTELLEKT 2.4 + 2.8 (spatial + naturalist): loyiha strukturasi so'rovi —
        # workspace daraxti + til taqsimoti konteksti (agent muhitni ko'radi).
        _sp = None
        if self._is_structure_request(message):
            _sp = self._spatial_env_context(message)
            if _sp:
                system += "\n\n" + _sp[0]
        # CHIZISH SO'ROVI: svg-artist skill ko'rsatmasi AVTOMATIK qo'shiladi —
        # model har chizishda professional SVG (gradient/soya/qatlamlar) yaratadi
        if self._is_draw_request(message):
            skill_text = self._draw_skill_text()
            if skill_text:
                system += "\n\n" + skill_text
            # Oxirgi chizma sifat feedback'i — model avvalgi xatolarini
            # takrorlamasligi uchun (RAG recall'ga tayanmasdan ham ishlaydi)
            fb = self._draw_feedback_context()
            if fb:
                system += "\n\n" + fb
        # WEB SO'ROVI: qaror qoidalari — model eng arzon vositanı tanlaydi
        # (to'g'ridan-to'g'ri javob > web_fetch > web AI subagent > browser).
        web_strategy = self._web_strategy(message)
        # Qoidalar faqat web_ai_bridge MCP ulangan bo'lsa qo'shiladi — aks holda
        # modelga mavjud bo'lmagan tool'lar (ask_web_ai/browser) eslatilmaydi.
        if web_strategy and self._mcp() is not None:
            system += "\n\n" + self._web_decision_rules(web_strategy)
        # STACK GUIDE: kod so'rovida framework/til aniqlansa — model aniq
        # buyruqlarni (npm/pip/mvn...) ishlatishi uchun yo'naltiruv qo'shiladi.
        stack_guide = self._stack_guide(pipeline)
        if stack_guide:
            system += "\n\n" + stack_guide
        if memory_ctx:
            system += (
                "\n\nRelevant recalled knowledge from memory (use only if useful):\n"
                + memory_ctx
            )
        elif mag_ctx:
            system += "\n\nMemory context:\n" + mag_ctx
        # SEMANTIK TALAB BLOKI (Part L): model javobni req'ga mos shakllantiradi.
        if self.llm_available():
            system += "\n\n" + req.to_block()
        # GOAL PIN (Phase 1, §12): ORIGINAL GOAL system prompt'ga pin qilinadi
        # (context o'ssa/umumlashtirilsa ham goal yo'qolmaydi).
        if goal_pin:
            system += "\n\n" + goal_pin

        # §6 CONTEXT BUDGET (Phase 3): prompt qatlamlarini token budget bilan
        # sig'dirish — overflow'da memory/history eskilari tashlanadi,
        # goal_pin va user HECH QACHON. Graceful degradation kafolati.
        try:
            system, _kept_hist, _budget_report = self.context_budget.fit_prompt(
                base_system=system, goal_pin=goal_pin,
                history=(history or [])[-12:], user_message=message)
            self._last_budget_report = _budget_report
        except Exception:
            self._last_budget_report = None

        messages: list[dict] = [{"role": "system", "content": system}]
        for h in (history or [])[-12:]:
            role = h.get("role")
            content = h.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        # CAG: keshda javob bo'lsa — darhol buffered done
        if not history and not self._is_draw_request(message) and not self._is_date_question(message):
            cache = self._cag()
            if cache is not None:
                cached = cache.get(CHAT_TOOLS_SYSTEM, message)
                if cached is not None:
                    # AUDIT (CAG hit — stream): keshlangan matn ham repair'dan
                    # o'tadi — eski/buzilgan yozuv ham `data["content"]` kabi
                    # canonical matn bo'ladi; memory va confidence shundan
                    # hisoblanadi (`_done` keyingi repair'i no-op bo'ladi).
                    out_final, struct_check = self._verify_and_repair(cached)
                    data = {
                        "message": message,
                        "content": out_final or cached,
                        "engine": "cag",
                        "tool_calls": [],
                        "image": None,
                        "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
                        "cag": {"hit": True},
                    }
                    if struct_check is not None:
                        data["structure_check"] = struct_check
                    # Fail-guard: repair qilib BO'LMAYDIGAN chiqish (verified='fail')
                    # RAG'ga yozilmaydi (stream yo'llari bilan bir xil naqsh).
                    if (self.memory.enabled and self._cacheable_out(data.get("content"))
                            and (struct_check is None or struct_check.get("ok") is not False)):
                        self.memory.on_resolve(message, {"output": data["content"], "engine": "cag", "confidence": self._confidence_for(data)})
                    yield _done(data)
                    return

        # INTELLEKT 2.11 (creative): kreativ so'rov — buffered multi-temperature
        # (faqat tarixsiz oddiy so'rov; tarixli davomda oddiy yo'l ishlaydi)
        creative_data = None
        if not history:
            creative_data = self._creative_variants(message, system=system, memory_hits=memory_hits)
        if creative_data is not None:
            stage = _emit_stage("review", "kreativ variantlar tayyorlanmoqda…")
            if stage:
                yield stage
            yield _done(creative_data)
            return

        # TOOL KERAKLIGI — pipeline/requirement asosida (tor kalit so'z
        # ro'yxati emas): "o'yinini yasab ber" / "saqlangan manzil?" kabi
        # yaratuvchi so'rovlarda model TOOLSIZ javob berib, ish qilgan bo'lib
        # ko'rsatardi (hallucination). Endi creator pipeline/needs_tools doim
        # tool yo'lini ochadi.
        tool_needed = (
            self._is_draw_request(message)
            or self._needs_web(message)
            or pipeline.get("need") in request_classifier.CREATOR_NEEDS
            or bool(getattr(req, "needs_tools", False))
            or bool(self._registry() and any(
                w in message.lower()
                for w in ("fayl", "file", "write", "yarat", "create", "dastur", "kod", "code")
            ))
        )

        if not self.llm_available():
            # offline — buffered, aniq tushuntirish
            stage = _emit_stage("review", "javob tayyorlanmoqda…")
            if stage:
                yield stage
            res = self.resolve(message, allow_llm=False, use_memory=use_memory)
            out = res.get("output") if res.get("status") == "ok" and res.get("output") else (
                "IGRIS hozir javob bera olmadi — Ollama (lokal AI) "
                "yoqilmagan. Iltimos `run.bat` orqali yoki terminalda "
                "`ollama serve` bilan Ollama'ni ishga tushiring, so'ng qayta "
                "yozing."
            )
            # `_mcp_cache` — offline yo'lida MCP serverlarni ishga tushirmaydi
            self._log_web_strategy(message, web_strategy, [], "offline",
                                   mcp_ok=self._mcp_cache is not None)
            yield _done({
                "message": message,
                "content": out,
                "engine": "offline",
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
            })
            return

        web_needed = bool(web_strategy)

        # TURBO tez yo'l (tool'siz oddiy savol) — buffered (chat_fast tez)
        if (
            getattr(self.llm, "turbo", False)
            and not tool_needed
            and not history
        ):
            stage = _emit_stage("review", "javob yozilmoqda…")
            if stage:
                yield stage
            fast = self.llm.chat_fast(messages)
            out = fast.strip() if fast and fast.strip() else self._retry_generate(messages, req)
            # AUDIT (stream turbo): repair memory yozuvidan OLDIN qilinadi —
            # `_done`'ning keyingi repair'i no-op bo'ladi, memory output ==
            # confidence signali == ko'rsatilgan javob (post-repair).
            out_final, struct_check = self._verify_and_repair(out)
            data = {
                "message": message,
                "content": out_final or self._retry_generate(messages, req),
                "engine": "llm-fast",
                "model": self.llm.fast_model or self.llm.model,
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
                "turbo": True,
            }
            if struct_check is not None:
                data["structure_check"] = struct_check
            # logprob re-so'ruvi (ixtiyoriy) uchun asl messages — bu yo'l doim
            # llm-fast (local `engine` o'zgaruvchisi shu yerda aniqlanmagan!).
            data["_llm_messages"] = messages
            # Guard: bo'sh/xato javoblar RAG'ga tushmaydi ("I could not
            # generate" ham kirmaydi — `_cacheable_out` uni rad etadi).
            # Fail-guard: repair qilib BO'LMAYDIGAN chiqish (verified='fail')
            # RAG'ga yozilmaydi (resolve() LLM fallback bilan bir xil naqsh).
            if (self.memory.enabled and self._cacheable_out(data.get("content"))
                    and (struct_check is None or struct_check.get("ok") is not False)):
                self.memory.on_resolve(message, {"output": data["content"], "engine": data["engine"], "confidence": self._confidence_for(data)})
            yield _done(data)
            return

        # ===== REAL TOKEN STREAM yo'li: tool kerak emas =====
        if not tool_needed:
            stage = _emit_stage("review", "javob yozilmoqda…")
            if stage:
                yield stage
            out = ""
            thinking_txt = ""
            try:
                # Fikrlash bosqichi ham STREAM qilinadi — frontend "thinking"
                # blokida reasoning token-ketma-token ko'radi, so'ng yakuniy
                # javob oqadi (bo'sh kutish yo'q — kutish o'rniga fikrlash
                # jarayoni ko'rinadi). Sessiya `think` sozlamasi va TURBO
                # rejimiga hurmat: thinking qo'llab-quvvatlanmaydigan modellarda
                # faqat "token" hodisalari keladi — buzilish yo'q.
                think_stream = self.llm.think and not getattr(self.llm, "turbo", False)
                for ev in self.llm.chat_stream_rich(messages, think=think_stream):
                    delta = ev.get("content") or ""
                    if not delta:
                        continue
                    if ev.get("type") == "think":
                        thinking_txt += delta
                        yield {"type": "thinking", "content": delta}
                    else:
                        out += delta
                        yield {"type": "token", "content": delta}
            except Exception as exc:
                # LLM xatosi — graceful degradation: buffered chat'ga qaytamiz
                self._mark_llm_failed(str(exc))
                print(f"[igris][stream] LLM failed, degrading to buffered chat: {exc}")
            if not out.strip():
                # stream transport xatosi / bo'sh javob — buffered chat'ga qaytamiz
                buffered = self.chat(message, history=history, use_memory=use_memory)
                yield _done(buffered)
                return
            engine = "llm"
            # Muvaffaqiyatli stream - cooldown'ni tozalaymiz
            self._mark_llm_recovered()
            # AUDIT (stream final): repair data yig'ish paytida qilinadi — memory
            # va CAG put AYNAN `data["content"]` (repair'dan keyingi)ni oladi;
            # `_done` keyingi repair'i no-op bo'ladi (keshlangan out vs content
            # tafovuti yopiladi, chat() bilan bir xil kalitda bir xil qiymat).
            out_final, struct_check = self._verify_and_repair(out)
            data = {
                "message": message,
                "content": out_final or out,
                "engine": engine,
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
            }
            # To'liq fikrlash matni `done` voqeasida ham boradi — frontend
            # yakuniy xabarda thinking blokini saqlab qoladi (eventlar o'tib
            # ketsa ham).
            if thinking_txt:
                data["thinking"] = thinking_txt
            # INTELLEKT 2.2: chiqish strukturasi tekshiruvi natijasi (JSON/kod)
            if struct_check is not None:
                data["structure_check"] = struct_check
            # INTELLEKT 2.4/2.8: fazoviy + naturalist xulosasi (struktura so'rovi)
            if _sp:
                data["spatial"] = _sp[1]
            # LLM logprob re-so'ruvi (ixtiyoriy) uchun asl messages saqlanadi
            if engine in ("llm", "llm+tools", "llm-fast"):
                data["_llm_messages"] = messages
            # Fail-guard: repair qilib BO'LMAYDIGAN chiqish (verified='fail')
            # RAG'ga yozilmaydi (resolve() LLM fallback bilan bir xil naqsh).
            if (self.memory.enabled and self._cacheable_out(data.get("content"))
                    and (struct_check is None or struct_check.get("ok") is not False)):
                self.memory.on_resolve(message, {"output": data["content"], "engine": engine, "confidence": self._confidence_for(data)})
            cache = self._cag()
            if (cache is not None and self._cacheable_out(data.get("content"))
                    and not self._is_date_question(message)
                    # Fail-guard: repair qilib bo'lmagan chiqish keshlanmaydi
                    and (struct_check is None or struct_check.get("ok") is not False)):
                cache.put(CHAT_TOOLS_SYSTEM, message, data["content"])
            yield _done(data)
            return

        # ===== TOOL yo'li: round'lar buffered, lekin YAKUNIY javob token oqimi =====
        # progress_cb berilsa — tool bajarilayotganda CHAT_PROGRESS buferiga
        # jonli bosqich yoziladi (frontend stepperi stream'da ham ishlaydi).
        # loop_iteration_events: ReAct/build-verify loop iteration event'lari
        # yig'iladi va yakunda frontend'ga yuboriladi.
        tools = self._chat_tools(include_web=web_needed)
        loop_iteration_events: list[dict] = []

        def _on_loop_iteration(iteration: int, max_iter: int, shape: str):
            loop_iteration_events.append({
                "type": "loop_iteration",
                "iteration": iteration,
                "max_iter": max_iter,
                "shape": shape,
            })

        content, tool_calls, image, redraw_note = self._chat_with_redraw(
            messages, tools, web=web_needed, progress=progress_cb, request=message,
            req=req, on_loop_iteration=_on_loop_iteration,
            max_rounds=pipeline.get("max_iter"),
            loop_shape=pipeline.get("loop_shape"),
        )
        # loop_iteration event'larini yuboramiz — frontend "attempt N of M" ko'rsatadi
        for ev in loop_iteration_events:
            yield ev
        # ACTION EVIDENCE (stream): "qildim" da'vosi isbotsiz bo'lmasin —
        # buffered chat() bilan bir xil guard: bir marta nudge, isbot bo'lmasa
        # halol rewrite (soxta yakunlash frontendga yuborilmaydi).
        content, tool_calls, image, evidence_note = self._enforce_action_evidence(
            messages, tools, content, tool_calls, image,
            need=pipeline.get("need", "chat"), progress=progress_cb,
            request=message, req=req, web=web_needed,
            max_rounds=pipeline.get("max_iter"),
            loop_shape=pipeline.get("loop_shape"))
        engine = "llm+tools" if tool_calls else "llm"
        if not (content or "").strip():
            # Part L: canned "Veb so'rovi..." / bo'sh javob o'rniga req-aware retry
            content = self._retry_generate(messages, req)
        # AUDIT (stream tool): repair data yig'ish paytida qilinadi — memory
        # AYNAN `data["content"]` (repair'dan keyingi)ni oladi; `_done`'ning
        # keyingi repair'i no-op bo'ladi (chat/plain-stream/turbo bilan bir
        # xil kalitda bir xil qiymat — keshlangan out vs content tafovuti yo'q).
        out_final, struct_check = self._verify_and_repair(content or "")
        # Part L (B2): talab compliance — nomoslik bo'lsa 1 marta qayta generatsiya.
        # Part O: rasm/visual natija (image mavjud) — LLM compliance keraksiz.
        if (out_final or "").strip() and not image and req.output_format not in ("image",):
            out_final = self._compliance(out_final, req, message)
        # KUZATUV: strategiya to'g'ri tanlandimi + model nima qildi
        # (`_mcp_cache` — server ishga tushirmaydi, faqat holatni o'qiydi)
        self._log_web_strategy(message, web_strategy, tool_calls, engine,
                               mcp_ok=self._mcp_cache is not None,
                               content_len=len(out_final or ""))
        data = {
            "message": message,
            "content": out_final or content or self._retry_generate(messages, req),
            "engine": engine,
            "tool_calls": tool_calls,
            "image": image,
            "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
        }
        if redraw_note:
            data["redraw"] = redraw_note
        # ACTION EVIDENCE natijasi javob bilan birga yuboriladi (audit/UI).
        if evidence_note:
            data["action_evidence"] = evidence_note
        # INTELLEKT 2.2: chiqish strukturasi tekshiruvi natijasi (JSON/kod)
        if struct_check is not None:
            data["structure_check"] = struct_check
        # INTELLEKT 2.4/2.8: fazoviy + naturalist xulosasi (struktura so'rovi)
        if _sp:
            data["spatial"] = _sp[1]
        # LLM logprob re-so'ruvi (ixtiyoriy) uchun asl messages saqlanadi
        if engine in ("llm", "llm+tools", "llm-fast"):
            data["_llm_messages"] = messages
        # Yolg'on/bo'sh javoblar xotiraga YOZILMAYDI (RAG'ni ifloslantirmaydi)
        # Fail-guard: repair qilib BO'LMAYDIGAN chiqish (verified='fail') ham
        # RAG'ga yozilmaydi (resolve() LLM fallback bilan bir xil naqsh).
        if (self.memory.enabled and self._cacheable_out(data.get("content"))
                and (struct_check is None or struct_check.get("ok") is not False)):
            self.memory.on_resolve(message, {"output": data["content"], "engine": engine, "confidence": self._confidence_for(data)})
        # Yakuniy matnni TOKEN-bo'laklar bilan uzatamiz — foydalanuvchi javobni
        # yozilayotganda ko'radi (tool jarayoni stage/poll orqali jonli edi).
        final_text = data.get("content") or ""
        if final_text:
            stage = _emit_stage("review", "javob yozilmoqda…")
            if stage:
                yield stage
            for chunk in self._token_chunks(final_text):
                yield {"type": "token", "content": chunk}
        yield _done(data)

    # ------------------------------------------------------------ #
    # CAG / MAG lazy helpers
    # ------------------------------------------------------------ #

    def _cag(self):
        """Lazy CAG cache singleton."""
        if self.cag_cache is None:
            try:
                from agent.cag import DEFAULT_CAG
                self.cag_cache = DEFAULT_CAG
            except Exception as exc:
                self.cag_cache = None
                # S3: CAG o'lsa javoblar keshlanmaydi (sekinlashuv) — silent emas.
                try:
                    from monitor.degradation import mark
                    mark("agent.cag", str(exc)[:300], fallback="no-cache")
                except Exception:
                    pass
        return self.cag_cache

    def _mag(self):
        """Lazy MAG assembler (MemoryBridge asosida)."""
        if self.mag is None:
            try:
                from agent.mag import MagAssembler
                self.mag = MagAssembler(memory=self.memory if self.memory.enabled else None)
            except Exception as exc:
                self.mag = None
                # S3: MAG o'lsa sessiya konteksti yo'qoladi — silent emas.
                try:
                    from monitor.degradation import mark
                    mark("agent.mag", str(exc)[:300], fallback="no-context")
                except Exception:
                    pass
        return self.mag

    # ------------------------------------------------------------ #
    # INTELLEKT yordamchilari — xavfsiz (mock/FakeIntel bilan ham ishlaydi)
    # ------------------------------------------------------------ #

    def _intel(self, name: str, *args, **kwargs):
        """IntelligenceCore usulini xavfsiz chaqiradi (mavjud bo'lmasa None)."""
        fn = getattr(self.intelligence, name, None)
        if fn is None:
            return None
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            print(f"[igris][intel] {name} failed: {exc}")
            return None

    def _self_eval_for(self, data: dict) -> Optional[dict]:
        """INTELLEKT 2.7: `data` uchun SelfEvaluator natijasini BIR MARTA hisoblab,
        `data["self_eval"]`'ga yozadi.

        `evaluate()` har javob uchun bir marta chaqiriladi; natija keshga
        yoziladi. `_with_self_eval()` va `_confidence_for()` shu natijani
        QAYTA ISHLATADI — takroriy SelfEvaluator hisoblash yo'q. Natija
        mavjud bo'lmasa None qaytadi.
        """
        if not isinstance(data, dict):
            return None
        # `_llm_messages` faqat self-eval uchun edi — qaysi yo'l bilan bo'lsa
        # ham javobga oqib ketmasligi uchun BIRINCHI narsa qilib olinadi
        # (early-return: self_eval oldindan keshlangan bo'lsa ham xavfsiz).
        data.pop("_llm_messages", None)
        # A4: grounding natijasi faqat self-eval uchun — javobga oqib ketmasin
        grounding_result = data.pop("_grounding_result", None)
        existing = data.get("self_eval")
        if existing is not None:
            return existing if isinstance(existing, dict) else None
        try:
            # A2 verifikator signali: `_verify_and_repair` qo'shgan
            # `structure_check` — json repaired / struktur muammo qoldi.
            # LLM logprob: native /api/chat QAYTARMAYDI — shuning uchun
            # verifikator natijasi asosiy signal, ixtiyoriy OpenAI-mos logprob
            # re-so'ruvi (`avg_logprob`) esa QO'SHIMCHA ishonch signali.
            # Izoh: `_verify_and_repair` muvaffaqiyatni None bilan xabar
            # qiladi (shovqin yo'q) — shuning uchun `ok=True` (repaired'siz)
            # dict hech qachon kelmaydi, verified='ok' shu oqimda o'lik.
            # SelfEvaluator'dagi 'ok' qiymati bevosita API chaqiruvi uchun
            # kelajakda ishlatilishi mumkin.
            verified = None
            sc = data.get("structure_check")
            if isinstance(sc, dict):
                if sc.get("repaired"):
                    verified = "repaired"
                elif sc.get("ok") is False:
                    verified = "fail"
            # A2 (logprob): ixtiyoriy OpenAI-mos ALOHIDA re-so'rov — o'rtacha
            # token ehtimoli ishonch signali. Faqat LLM javoblarida va faqat
            # `llm.logprobs` yoqilganida (2x inference narxi — default O'CHIQ).
            # Ollama eski/offline bo'lsa None qaytadi — signal neytral, agent
            # buzilmaydi. Asl messages TO'LIQ `_llm_messages` orqali uzatiladi
            # (chat/chat_stream/resolve qo'shadi) — kontekstsiz yalang'och
            # user-matn fallback'i YO'Q, aks holda logprob noto'g'ri muhitda
            # o'lchanib, chalg'ituvchi signal berardi (reviewer A2-logprob).
            avg_logprob = None
            engine_name = data.get("engine") or "llm"
            msgs = data.get("_llm_messages")
            if (
                msgs
                and getattr(self.llm, "logprobs", False)
                and self.use_llm
                and engine_name in ("llm", "llm+tools", "llm-fast")
            ):
                try:
                    avg_logprob = self.llm.chat_logprobs(
                        msgs, model=data.get("model") or self.llm.model
                    )
                except Exception:
                    avg_logprob = None
            # A4: grounding verdict -> SelfEvaluator signali (fail-safe)
            grounding_signal_val = None
            if grounding_result is not None:
                try:
                    from web.web_verify import grounding_signal as _gsig  # noqa: E402
                    grounding_signal_val = _gsig(grounding_result)
                except Exception:
                    grounding_signal_val = None
            res = self._intel(
                "evaluate",
                engine=data.get("engine") or "llm",
                # Rad etish (harm-filter) — to'g'ri deterministik harakat, xato EMAS
                status="ok",
                # chat() data: content; resolve() data: output — ikkalasi ham.
                output=data.get("content") or data.get("output") or "",
                tool_calls=data.get("tool_calls") or [],
                memory_hits=(data.get("memory") or {}).get("recall_hits", 0),
                # resolve() to_dict'ida `healed` maydoni bor — deterministik
                # yo'l uchun muhim (healed = shubhali natija). chat()'da yo'q.
                healed=bool(data.get("healed")),
                verified=verified,
                # A2: deterministic/healed rezolyutsiyada resolverning o'z
                # bahosi (0.6*rule_score + 0.4*coverage) signal sifatida.
                resolver_score=data.get("resolver_score"),
                # A2: ixtiyoriy OpenAI-mos logprob re-so'ruvidan o'rtacha
                # token ehtimoli (0..1) — None bo'lsa neytral (signal yo'q).
                avg_logprob=avg_logprob,
                # A4: web manba grounding signali (None = tekshirilmagan).
                grounding=grounding_signal_val,
            )
            if isinstance(res, dict):
                data["self_eval"] = res
                return res
            if hasattr(res, "to_dict"):
                data["self_eval"] = res.to_dict()
                return data["self_eval"]
        except Exception:
            pass
        return None

    def _with_self_eval(self, data: dict) -> dict:
        """INTELLEKT 2.7: ishonch kalibratsiyasini javobga biriktiradi.

        Faqat metrika (confidence/uncertainty/notes) — agent xulq-atvorini
        o'zi o'zgartirmaydi. `_self_eval_for()` natijasini biriktiradi —
        `data["self_eval"]` allaqachon bo'lsa qayta hisoblamaydi
        (harm-filter rad etishida bo'lgani kabi).

        A4: web tool'lar ishlatilgan chat'da javob manbalar bilan grounding
        tekshiruvidan o'tadi (`web_verify.verify_answer`, deterministik,
        LLM yo'q). Natija `data["web_grounding"]`'ga yoziladi va SelfEvaluator
        signaliga aylanadi (grounded +0.10 / ungrounded −0.15). Fail-safe:
        verification hech qachon javobni buzmaydi.
        """
        # --- A4: web grounding verification (metrika) ---
        # Rasm javoblarida tekshiruv YO'Q — xulosa fayl haqida, web fakt emas
        # (aks holda chizma xulosasi yolg'on "ungrounded" bo'lardi).
        try:
            ws = getattr(self, "_web_sources", None)
            content = data.get("content") or data.get("output") or ""
            if ws is not None and not data.get("image") \
                    and isinstance(content, str) and content.strip():
                from web.web_verify import verify_answer, grounding_signal  # noqa: E402
                grounding = verify_answer(content, ws)
                data["web_grounding"] = grounding.to_dict()
                data["_grounding_result"] = grounding  # _self_eval_for o'qiydi va o'chiradi
        except Exception:
            pass
        self._self_eval_for(data)
        return data

    def _confidence_for(self, data: dict, fallback: float = 0.5) -> float:
        """A2: `data` uchun confidence — `_self_eval_for()` natijasini QAYTA ISHLATADI.

        Memory `on_resolve` (confidence) va `data["self_eval"]` BIR evaluate()
        chaqiruvidan olinadi — takroriy SelfEvaluator hisoblash yo'q.
        Intellekt mavjud bo'lmasa/xato bersa — `fallback` qaytadi.
        """
        ev = self._self_eval_for(data)
        if ev:
            conf = ev.get("confidence")
            if isinstance(conf, (int, float)):
                return max(0.0, min(1.0, float(conf)))
        return float(fallback)

    def _verify_and_repair(self, out: str) -> tuple[str, Optional[dict]]:
        """INTELLEKT 2.2: chiqish strukturasi tekshiruvi + JSON ta'mirlash.

        Model JSON so'raganida matn ichiga JSON o'raydi yoki kichik xato
        qiladi — aniqlaymiz va iloji bo'lsa tuzatamiz. Qaytaradi:
        (out, structure_check_dict|None). Faqat MUAMMOLAR hisobot qilinadi
        (to'g'ri javoblar shovqin qilmaydi).
        """
        text = str(out or "")
        check = self._intel("verify_structure", text)
        if check is None:
            return out, None
        info = check.to_dict() if hasattr(check, "to_dict") else dict(check)

        if not info.get("ok") and info.get("kind") == "json":
            repaired = extract_balanced_json(text)
            if repaired:
                recheck = self._intel("verify_structure", repaired)
                if recheck is not None:
                    rinfo = recheck.to_dict() if hasattr(recheck, "to_dict") else dict(recheck)
                    if rinfo.get("ok"):
                        return repaired, {
                            "ok": True, "kind": "json", "repaired": True,
                            "note": "JSON xato edi — matndan to'g'ri blok ajratib olindi",
                        }

        # To'g'ri javoblar hisobotga tushmaydi (shovqin yo'q)
        if info.get("ok"):
            return out, None
        if info.get("kind") == "plain":
            return out, None
        info["repaired"] = False
        return out, info

    def _domain_verify(self, out: str, message: str = "", need: str = "") -> tuple[str, Optional[dict]]:
        """A1: per-domain semantik tekshiruv — faqat kod/chizma uchun.

        Structure'ga qo'shimcha ravishda:
        - code: brackets balans, TODO/FIXME placeholderlari, mavzu mosligi
        - draw: <svg> markup mavjudligi
        - ui_build: UI spec structure
        Qaytaradi: (out, check_dict|None). None = muammo yoq.
        """
        low = (out or "").strip().lower()
        if need == "code" and len(low) > 5:
            issues: list[str] = []
            # brackets balansi
            for open_ch, close_ch in [("(", ")"), ("[", "]"), ("{", "}")]:
                if low.count(open_ch) != low.count(close_ch):
                    issues.append(f"unbalanced {open_ch}{close_ch}")
                    break
            # M5: angle brackets faqat MARKUP kontekstida mazmunli. Oddiy
            # kodda `x > 5` yoki `List[int]` kabi foydalanish LEGIT — bunda
            # soxta "unbalanced <>" hisoboti review loop'ni 3× befoyda LLM
            # retry'ga majburlardi (har chaqiruvda yana rad etilardi).
            if low.count("<") != low.count(">") and (
                    "<div" in low or "<p>" in low or "<svg" in low
                    or "<html" in low or "<xml" in low or "</" in low):
                issues.append("unbalanced <>")
            # TODO/FIXME placeholderlar — M6: atribut/kwarg ko'rinishi
            # (placeholder="Email", placeholder={x}) LEGIT ishlatilish —
            # faqat haqiqiy "ish bajarilmagan" so'zi hisobot qilinadi.
            for placeholder in ("todo", "fixme", "xxx", "hack", "placeholder"):
                if re.search(rf"\b{placeholder}\b(?!\s*=)", low):
                    issues.append(f"placeholder: {placeholder}")
                    break
            # code ichida python/JS sintaksis xatolari (oddiy tekshiruv)
            if "print(" in low and "'" in low and "\\'" in low:
                issues.append("possible quote error")
            # M4b: HAQIQIY Python sintaksis tekshiruvi (compile — xavfsiz,
            # kod IJRO ETILMAYDI). ```python bloklari yoki sof-python chiqishi
            # SyntaxError'ni aniq ushlaydi — retry endi haqiqiy xatoni oladi.
            syntax_issue = self._python_syntax_issue(out)
            if syntax_issue:
                issues.append(syntax_issue)
            if issues:
                return out, {"ok": False, "kind": "domain", "issues": issues, "repaired": False}
            return out, None
        if need == "draw" and low:
            if "chizdim" in low or "rasm tayyor" in low:
                if "<svg" not in low and "art__draw" not in low:
                    return out, {"ok": False, "kind": "domain", "issues": ["fake draw claim — no SVG"], "repaired": False}
        return out, None

    @staticmethod
    def _python_syntax_issue(text: str) -> Optional[str]:
        """Python kodidagi sintaksis xatosi — yoki None (muammo yo'q).

        compile() faqat PARSE qiladi — hech qanday kod bajarilmaydi.
        ```python bloklari tekshiriladi; fence bo'lmasa, chiqish sof-python
        ko'rinsa (def/class/import bilan boshlansa) butun matn tekshiriladi.
        Prose + fence aralash chiqishda faqat fence'lar — prose sintaksis
        xatosi soxta pozitif bo'lmasligi uchun.
        """
        try:
            src = str(text or "")
            blocks = re.findall(r"```(?:python|py)\s*\n(.*?)```", src, re.DOTALL)
            if not blocks:
                stripped = src.strip()
                if re.match(r"^(def |class |import |from )", stripped) and "def " in stripped:
                    blocks = [stripped]
            for block in blocks:
                try:
                    compile(block, "<snippet>", "exec")
                except SyntaxError as exc:
                    return f"python syntax error: {str(exc.msg or exc)[:80]}"
            return None
        except Exception:
            return None

    # --- S5: klassifikatorlar request_classifier.py'da (yagona manba) ---
    @staticmethod
    def _is_math_request(message: str):
        """Sof arifmetik ifoda so'rovi — S5: request_classifier.is_math_request."""
        return request_classifier.is_math_request(message)

    @staticmethod
    def _is_structure_request(message: str) -> bool:
        return request_classifier.is_structure_request(message)

    @staticmethod
    def _is_creative_request(message: str) -> bool:
        return request_classifier.is_creative_request(message)

    @staticmethod
    def _is_draw_request(message: str) -> bool:
        return request_classifier.is_draw_request(message)

    @staticmethod
    def _is_ui_build_request(message: str) -> bool:
        return request_classifier.is_ui_build_request(message)

    @classmethod
    def _is_code_request(cls, message: str) -> bool:
        return request_classifier.is_code_request(message)

    @staticmethod
    def _is_composition_request(message: str) -> bool:
        return request_classifier.is_composition_request(message)

    @classmethod
    def _is_file_request(cls, message: str) -> bool:
        return request_classifier.is_file_request(message)

    @classmethod
    def _classify_family(cls, message: str) -> str:
        return request_classifier.classify_family(message)

    @classmethod
    def _classify_type(cls, message: str, family: str) -> str:
        return request_classifier.classify_type(message, family)

    def _classify_need(self, message: str, history: Optional[list] = None) -> str:
        return request_classifier.classify_need(message, history)

    def _quick_math(self, message: str) -> Optional[str]:
        """INTELLEKT 2.2: oddiy arifmetikani tez va aniq hisoblaydi (LLM'siz)."""
        expr = self._is_math_request(message)
        if expr is None:
            return None
        result = self._intel("quick_math", expr)
        if result is None:
            return None
        pretty = str(int(result)) if float(result).is_integer() else f"{result:.6f}".rstrip("0").rstrip(".")
        return f"{expr} = {pretty}"

    def _workspace_paths(self, max_files: int = 400, max_depth: int = 7) -> list[str]:
        """Agent ish maydonidagi fayl yo'llari (xavfsiz, cheklangan)."""
        root = getattr(self, "workspace_root", None) or DEFAULT_WORKSPACE
        if not root or not os.path.isdir(root):
            return []
        out: list[str] = []
        try:
            for base, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build")]
                if base[len(root):].count(os.sep) > max_depth:
                    dirs[:] = []
                    continue
                for f in files:
                    out.append(os.path.join(base, f))
                    if len(out) >= max_files:
                        return out
        except OSError:
            return []
        return out

    def _spatial_env_context(self, message: str) -> Optional[tuple[dict, dict]]:
        """INTELLEKT 2.4+2.8: workspace daraxti + til taqsimoti konteksti.

        Qaytaradi: (system_block, data_summary) yoki None (struktura so'rovi
        emas / workspace bo'sh). System prompt'ga qo'shiladi — agent loyiha
        qaysi texnologiyalardan iborat ekanini ko'radi.
        """
        if not self._is_structure_request(message):
            return None
        paths = self._workspace_paths()
        if not paths:
            return None
        tree = self._intel("spatial_file_tree", paths)
        env = self._intel("naturalist_summary", paths)
        if not isinstance(tree, dict) or not tree.get("entries"):
            return None
        lines = ["Project layout (spatial + naturalist):"]
        lines.append(f"- {tree['entries']} entries, max depth {tree.get('max_depth', 0)}")
        dist = tree.get("depth_distribution") or {}
        if dist:
            top = sorted(dist.items(), key=lambda kv: int(kv[0]))[:6]
            lines.append("- Depth distribution: " + ", ".join(f"d{k}:{v}" for k, v in top))
        dirs = (tree.get("directories") or [])[:8]
        if dirs:
            lines.append("- Directories: " + ", ".join(dirs))
        if env:
            lines.append(env)
        summary = {
            "entries": tree.get("entries"),
            "max_depth": tree.get("max_depth"),
            "dir_count": tree.get("dir_count"),
        }
        nats = self._intel("classify_paths", paths)
        if isinstance(nats, dict) and nats.get("languages"):
            summary["languages"] = nats.get("languages")
        return "\n\n".join(lines), summary

    def _creative_variants(self, message: str, system: str, memory_hits: int = 0) -> Optional[dict]:
        """INTELLEKT 2.11: 3 xil temperature'da variant + eng yaxshisini tanlash.

        Faqat LLM mavjud, tool kerak bo'lmagan, tarixsiz kreativ so'rovda
        ishlaydi. Chiqish operator ko'rib chiqadi — agent o'zi qaror qilmaydi.
        Qaytaradi: to'liq javob data yoki None (shartlar bajarilmasa).
        """
        if (not self.llm_available() or not self._is_creative_request(message)
                or getattr(self.llm, "turbo", False)
                or self._is_draw_request(message) or self._needs_web(message)):
            return None
        low = (message or "").lower()
        if any(w in low for w in ("fayl", "file", "write", "yarat", "create",
                                  "dastur", "kod", "code", "yoz")):
            # kod/fayl yaratish so'rovlarida kreativ qatlam qo'llanilmaydi (tool kerak)
            return None
        creative_system = (system or "") + (
            "\n\nThe user wants VARIANTS/IDEAS. Give one useful, distinct "
            "alternative for the request. Be concrete and helpful — no filler."
        )
        t0 = time.perf_counter()
        candidates = self._intel(
            "creative_variants", message, n=3,
            complete_fn=self.llm.complete, system=creative_system,
        )
        if not candidates:
            return None
        best = self._intel("pick_creative", candidates, "balanced")
        text = (best.text if hasattr(best, "text") else (best or {}).get("text")) or ""
        if not text.strip():
            return None
        variants: list[dict] = []
        for c in candidates:
            t = (c.text if hasattr(c, "text") else (c or {}).get("text")) or ""
            lbl = (c.label if hasattr(c, "label") else (c or {}).get("label")) or ""
            temp = (c.temperature if hasattr(c, "temperature") else (c or {}).get("temperature")) or 0.7
            if t.strip():
                variants.append({"label": lbl, "temperature": temp, "text": t[:400]})
        chosen = (best.label if hasattr(best, "label") else (best or {}).get("label")) or "balanced"
        data = {
            "message": message,
            "content": text.strip(),
            "engine": "creative",
            "model": self.llm.model,
            "tool_calls": [],
            "image": None,
            "memory": {"recall_hits": memory_hits, "context_chars": 0},
            "duration_ms": (time.perf_counter() - t0) * 1000.0,
            "creative": {"variants": variants, "chosen": chosen, "n": len(variants)},
        }
        if self.memory.enabled:
            try:
                self.memory.on_resolve(message, {"output": text.strip(), "engine": "creative", "confidence": self._confidence_for(data)})
            except Exception:
                pass
        return self._with_self_eval(data)

    # --- S5: leksika/lexicon request_classifier.py'da — klass attribute aliaslar ---
    DRAW_STOP_WORDS = request_classifier.DRAW_STOP_WORDS
    CANNED_SCENE_SUBJECTS = request_classifier.CANNED_SCENE_SUBJECTS
    FILE_READ_VERBS = request_classifier.FILE_READ_VERBS
    FILE_EDIT_VERBS = request_classifier.FILE_EDIT_VERBS
    FILE_EXTENSIONS = request_classifier.FILE_EXTENSIONS
    UI_APP_TARGETS = request_classifier.UI_APP_TARGETS
    CODE_LANG_HINTS = request_classifier.CODE_LANG_HINTS
    CODE_FRAMEWORK_HINTS = request_classifier.CODE_FRAMEWORK_HINTS
    ORM_HINTS = request_classifier.ORM_HINTS
    DATABASE_TECH_HINTS = request_classifier.DATABASE_TECH_HINTS
    DB_CLASSIFY_EXCLUDE = request_classifier.DB_CLASSIFY_EXCLUDE

    def _detect_subject(self, message: str, need: str) -> str:
        return request_classifier.detect_subject(message, need)

    @classmethod
    def _detect_web_tech(cls, message: str) -> str:
        return web_strategy_mod.detect_web_tech(message)

    @classmethod
    def _detect_db_tech(cls, message: str) -> str:
        return request_classifier.detect_db_tech(message)

    @classmethod
    def _detect_orm(cls, message: str) -> str:
        return request_classifier.detect_orm(message)

    def _detect_code_stack(self, message: str) -> tuple:
        return request_classifier.detect_code_stack(message)

    def _planned_tools(self, message: str, need: str) -> list[str]:
        return request_classifier.planned_tools(message, need)

    def _stack_plan(self, fw: str, lang: str, db: str = "", orm: str = "") -> Optional[dict]:
        """Framework/til/DB/ORMga mos stack rejasi — S5: request_classifier.stack_plan."""
        return request_classifier.stack_plan(fw, lang, db, orm)

    def _stack_guide(self, pipeline: dict) -> str:
        """Kod pipeline'i stack qo'llanmasi — S5: request_classifier.stack_guide."""
        return request_classifier.stack_guide(pipeline)

    def _clarify_request(self, message: str, need: str = "") -> str:
        return request_classifier.clarify_request(message, need)

    def _build_pipeline(self, message: str, history: Optional[list] = None) -> dict:
        """Zarurat turiga qarab agentik pipeline'ni tanlab, QUradi.

        Qaytaradi: {'need', 'label', 'stages', 'engine', 'clarified',
                    'subject', 'planned_tools', 'sub_pipelines'}
          - need           : zarurat turi (chat/math/weather/draw/ui_build/web/code/...)
          - stages         : PipelineStepper bosqichlari (plan->read->edit->test->review)
          - engine         : bajariladigan dvigatel nomi
          - clarified      : so'rov aniqlashtiruvi — obyekt + rejalangan tool'lar
          - subject        : so'rovdan aniqlangan mavzu obyekti ('' bo'lishi mumkin)
          - framework      : kod so'rovida aniqlangan framework (React/Django/...)
          - language       : kod so'rovida aniqlangan dasturlash tili
          - database       : kod so'rovida aniqlangan ma'lumotlar bazasi
                             (PostgreSQL/MySQL/MongoDB/Redis/...)
          - planned_tools  : pipeline rejalagan tool'lar to'plami
          - sub_pipelines  : birlashgan zaruratlar uchun qo'shimcha pipeline'lar
                             (foydalanuvchi pipeline BIRINCHI quriladi, qolganlari
                             yonida ko'rsatiladi)
        """
        need = self._classify_need(message, history)
        spec = PIPELINE_SPECS.get(need, PIPELINE_SPECS["chat"])
        subs: list[dict] = []
        for other in ("ui_build", "draw", "web", "code", "composition", "file_task"):
            if other == need:
                continue
            hit = False
            if other == "ui_build":
                hit = self._is_ui_build_request(message)
            elif other == "draw":
                hit = self._is_draw_request(message)
            elif other == "web":
                hit = self._needs_web(message)
            elif other == "code":
                hit = self._is_code_request(message)
            elif other == "composition":
                hit = self._is_composition_request(message)
            elif other == "file_task":
                hit = self._is_file_request(message)
            if hit:
                subs.append({"need": other, **PIPELINE_SPECS[other]})
        # Kod so'rovida framework + til alohida saqlanadi (subject ularni
        # birlashtirib ko'rsatadi: "React (JavaScript)"). Web so'rovida esa
        # `framework` maydoniga SAYT texnologiyasi yoziladi (WordPress...).
        fw, lang = ("", "")
        db = ""
        orm = ""
        if need == "code":
            fw, lang = self._detect_code_stack(message)
            db = self._detect_db_tech(message)
            # ORM ham aniqlanadi — "react + postgresql + prisma" -> React +
            # PostgreSQL + Prisma (stack rejasiga o'z qo'llanmasi qo'shiladi)
            orm = self._detect_orm(message)
        elif need == "web":
            fw = self._detect_web_tech(message)
            # DB ham aniqlanadi — "supabase saytini och" -> database: Supabase
            # (completion kartasida 🗄 chipi ko'rinadi)
            db = self._detect_db_tech(message)
        # Qo'shimcha (sub) code pipeline'iga ham stack biriktiriladi — masalan
        # "react ilova qurib ber" asosiy need'da ui_build bo'lsa ham, React kod
        # sub-pipeline'ida framework/planned_tools ko'rinishi va stack qo'llanmasi
        # ishlashi uchun (review'dagi bo'shliq).
        if need != "code":
            for sub in subs:
                if sub.get("need") == "code":
                    sub_fw, sub_lang = self._detect_code_stack(message)
                    sub_db = self._detect_db_tech(message)
                    sub_orm = self._detect_orm(message)
                    if sub_fw or sub_lang or sub_db or sub_orm:
                        sub["framework"] = sub_fw
                        sub["language"] = sub_lang
                        sub["database"] = sub_db
                        sub["orm"] = sub_orm
                        plan = self._stack_plan(sub_fw, sub_lang, sub_db, sub_orm)
                        if plan:
                            sub["planned_tools"] = list(plan["tools"])
                    break
        return {
            "need": need,
            "label": spec["label"],
            "stages": list(spec["stages"]),
            "engine": spec["engine"],
            "loop_shape": spec.get("loop_shape", "straight_through"),
            "max_iter": spec.get("max_iter", 8),
            "max_repair": spec.get("max_repair", 0),
            "clarified": self._clarify_request(message, need),
            "subject": self._detect_subject(message, need),
            "framework": fw,
            "language": lang,
            "database": db,
            "orm": orm,
            "planned_tools": self._planned_tools(message, need),
            "sub_pipelines": subs,
        }

    # ------------------------------------------------------------------
    # TASK SUPERVISOR — §9 Scaling to Complex Tasks
    # ------------------------------------------------------------------
    # Murakkab so'rovlarda (1+ ta loop kerak) avtomatik DAG quradi va
    # TaskSupervisor orqali bajaradi. Atomic so'rovlarda o'tkazib yuboriladi.
    # ------------------------------------------------------------------

    def _run_supervisor(self, message: str, pipeline: dict,
                        progress_cb=None) -> Optional[dict]:
        """Complex so'rovlar uchun TaskSupervisor ishga tushiradi.

        Atomic so'rovlarda → None qaytaradi (asosiy chat yo'li davom etadi).
        Non-atomic so'rovlarda → supervisor natijasini qaytaradi.

        RE-ENTRANCY GUARD (§9): supervisor node'lari agent.chat() ni qayta
        chaqiradi — ichki chat yana supervisor ochib CHEKSIZ ichma-ichma
        rekursiyaga kirardi (har daraja TaskSupervisor + DAG planner +
        checkpoint → minutlab kutish / stack portlashi). Guard ichki
        chaqiruvlarni None bilan o'tkazadi → node oddiy chat yo'lida bajaradi.
        """
        if getattr(self, "_supervisor_active", False):
            return None
        self._supervisor_active = True
        try:
            return self._run_supervisor_impl(message, pipeline, progress_cb)
        finally:
            self._supervisor_active = False

    def _run_supervisor_impl(self, message: str, pipeline: dict,
                             progress_cb=None) -> Optional[dict]:
        try:
            from task.task_supervisor import TaskSupervisor, LLMDAGPlanner
        except ImportError:
            return None

        # Checkpoint dir
        ckpt_dir = os.path.join(
            getattr(self, "workspace_root", None) or DEFAULT_WORKSPACE,
            ".checkpoints",
        )

        sup = TaskSupervisor(
            agent=self,
            total_budget=40,
            checkpoint_dir=ckpt_dir,
        )

        # Atomic check
        if sup.is_atomic(message, pipeline):
            return None

        # LLM-based planning
        planner = LLMDAGPlanner(llm=self.llm if self.llm_available() else None)
        llm_dag = planner.plan(message, pipeline)
        if llm_dag is not None and len(llm_dag.nodes) > 1:
            sup.dag = llm_dag
        # else: fallback to build_dag (sub_pipelines based)

        result = sup.run(message, pipeline, progress_cb=progress_cb)
        return result

    def _run_supervisor_stream(self, message: str, pipeline: dict):
        """Streaming version — SSE event'lari bilan supervisor ishlaydi.

        Yields: supervisor_start, supervisor_done

        RE-ENTRANCY GUARD: chat_stream → supervisor → node → chat_stream
        cheksiz rekursiyasini to'xtatadi (chat() guard'i bilan bir xil) —
        ichki chaqiruv oddiy generator (bo'sh) sifatida o'tadi.
        """
        if getattr(self, "_supervisor_active", False):
            # Ichki chaqiruv: hech narsa stream qilmaydi — supervisor
            # events bo'sh bo'ladi va chat_stream oddiy pipeline'ga o'tadi.
            return
        self._supervisor_active = True
        try:
            yield from self._run_supervisor_stream_impl(message, pipeline)
        finally:
            self._supervisor_active = False

    def _run_supervisor_stream_impl(self, message: str, pipeline: dict):
        """Run the canonical supervisor and adapt its result to stream events.

        The old implementation duplicated TaskSupervisor's scheduler and used
        raw LLM text as proof that a node had executed. That path could report
        completed work without tool evidence. The non-streaming supervisor is
        now the single execution owner; this method only adapts its result.
        """
        result = self._run_supervisor_impl(message, pipeline)
        if not result:
            return

        yield {
            "type": "supervisor_start",
            "goal": message,
            "nodes": list(result.get("nodes", {}).keys()),
        }
        yield {
            "type": "supervisor_done",
            "status": result.get("status", "partial"),
            "summary": result.get("summary", ""),
            "iterations_used": result.get("iterations_used", 0),
            "nodes": result.get("nodes", {}),
            "tool_calls": result.get("tool_calls", []),
            "files_changed": result.get("files_changed", []),
        }

    def _work_completion(self, pipeline: dict, data: dict) -> dict:
        """Agentik ish yakunini yig'adi — konversatsiyani to'ldiruvchi record.

        `data["completion"]` va server chat_history yozuvi shu record bilan
        to'ldiriladi: qaysi pipeline, qaysi bosqichlar, qaysi tool'lar, rasm,
        dvigatel, davomiylik, status.
        """
        tools: list[str] = []
        for tc in (data.get("tool_calls") or []):
            if isinstance(tc, dict) and tc.get("tool"):
                tools.append(str(tc["tool"]))
        completion: dict = {
            "pipeline": pipeline.get("need", "chat"),
            "label": pipeline.get("label", ""),
            "stages": pipeline.get("stages", []),
            "engine": data.get("engine") or pipeline.get("engine", ""),
            "loop_shape": pipeline.get("loop_shape", "straight_through"),
            "max_iter": pipeline.get("max_iter", 8),
            "max_repair": pipeline.get("max_repair", 0),
            "tools": tools,
            "status": "refused" if data.get("refused") else "ok",
            "duration_ms": round(float(data.get("duration_ms") or 0), 1),
        }
        # Aniqlangan mavzu obyekti + rejalangan tool'lar (klassifikatsiya
        # paytida, LLMsiz) — actual `tools` bilan solishtirish mumkin.
        if pipeline.get("subject"):
            completion["subject"] = pipeline["subject"]
        if pipeline.get("framework"):
            completion["framework"] = pipeline["framework"]
        if pipeline.get("language"):
            completion["language"] = pipeline["language"]
        if pipeline.get("database"):
            completion["database"] = pipeline["database"]
        if pipeline.get("orm"):
            completion["orm"] = pipeline["orm"]
        if pipeline.get("planned_tools"):
            completion["planned_tools"] = list(pipeline["planned_tools"])
        if data.get("image"):
            completion["image"] = str(data["image"])
        if data.get("redraw"):
            completion["redraw"] = data["redraw"]
        # ACTION EVIDENCE: isbot holati completion record'da ham saqlanadi
        # (server chat_history yozuvi audit qilinadi: executed/rephrased/corrected).
        if data.get("action_evidence"):
            completion["action_evidence"] = data["action_evidence"]
        # M12: SUPERVISOR AUDIT — DAG yakuni transcript'ga qayd etiladi.
        # Aks holda "partial" (qaysi node yiqilgani) faqat API javobida bor,
        # chat_history.jsonl'da yo'qolardi — keyinchalik audit qiyinlashardi.
        sup = data.get("supervisor")
        if isinstance(sup, dict):
            sup_nodes = sup.get("nodes") or {}
            completion["supervisor"] = {
                "status": sup.get("status"),
                "iterations_used": int(sup.get("iterations_used") or 0),
                "nodes_count": len(sup_nodes),
                "failed_nodes": [
                    nid for nid, nd in sup_nodes.items()
                    if isinstance(nd, dict) and nd.get("status") == "failed"
                ],
            }
        # §3.2 REVIEW LOOP: qayta tekshiruv natijasi — completion qog'ozida
        # HAQIQIY holat (urinishlar soni + tasdiqlandi/tasdiqlanmadi).
        if isinstance(data.get("review"), dict):
            completion["review"] = dict(data["review"])
        # SO'ROV SEMANTIKASI: completion qog'ozida qisqa izoh (to'liq struktura
        # data["interpretation"] ichida — bu yerda faqat asosiy signal'lar).
        if isinstance(data.get("interpretation"), dict):
            _itp = data["interpretation"]
            completion["interpretation"] = {
                k: _itp[k] for k in ("family", "intent", "language", "goal", "paradigms")
                if _itp.get(k)
            }
        if pipeline.get("sub_pipelines"):
            completion["sub_pipelines"] = [s["label"] for s in pipeline["sub_pipelines"]]
        # Phase 1 (§2/§12): goal preservation tracing — har chat yozuvida
        # ORIGINAL goal id qayd etiladi (konversatsiya tarixidan kuzatiladi).
        try:
            gc = getattr(self._chat_executor(), "goal_context", None) if data.get("tool_calls") else None
            if gc is not None:
                completion["goal_id"] = gc.goal.id
        except Exception:
            pass
        return completion

    def _finalize(self, data: dict, pipeline: dict,
                  interp: Optional[dict] = None) -> dict:
        """Chat javobini yakunlaydi: agentik completion record + self_eval.

        Har bir chat()/chat_stream() qaytish yo'lida `data["completion"]`
        konversatsiyaga to'ldiriladi — server uni chat_history.jsonl'ga ham
        yozadi ("user bilan suhbat agentic work completion ma'lumotlari orqali
        to'ldiriladi").
        """
        # SO'ROV SEMANTIKASI: interpretation barqaror kanalda bir marta
        # qo'shiladi — har bir qaytish yo'li uchun bir xil, ortiqcha shovqin yo'q.
        if interp and not data.get("interpretation"):
            data["interpretation"] = interp
        # §3.2 REVIEW LOOP: build_verify/reflexion — review muammosini haqiqiy
        # retry'ga ulaydi (faqat qayta tekshiruv tasdiqlasa content almashtiriladi)
        self._review_repair(data, pipeline or {})
        # M7: review content'ni almashtirsa — kesh/RAG yozuvlarini yangi matn
        # bilan sinxronlaydi (aks holda CAG eskirgan javobni qaytarardi).
        self._review_resync(data)
        data["completion"] = self._work_completion(pipeline, data)

        # §13 ResponseGenerator — voice-aware content formatting
        try:
            from agent.response_generator import ResponseGenerator
            rg = ResponseGenerator(voice_mode=False)
            if data.get("tool_calls"):
                result = {
                    "status": data.get("completion", {}).get("status", "completed"),
                    "tool_calls": data.get("tool_calls", []),
                }
                formatted = rg.generate_summary(result)
                if formatted and not data.get("content"):
                    data["content"] = formatted
        except Exception:
            pass

        return self._with_self_eval(data)

    # ------------------------------------------------------------------
    # REQUEST MEANING — so'rov semantikasi (core/request_meaning.py)
    # ------------------------------------------------------------------
    def _meaning_assist_fields(self, text: str, need, family) -> dict:
        """Ixtiyoriy LLM assist: problem/goal/definition/paradigms boyitish.

        Shartlar (ortiqcha chaqiruv/latensiya oldini oladi):
          - assist yoqilgan (`meaning_llm_assist` / IGRIS_MEANING_ASSIST)
          - LLM mavjud (llm_available) va `complete()` metodi bor (OmniRoute'da
            hozir yo'q — holat xavfsiz) 
          - tezkor yo'llar (math/weather) va qisqa so'rovlar (len < 16)
            o'tkazib yuboriladi.

        Hech qachon exception bermaydi; natija {} bo'lsa deterministik parse
        o'zi ishlaydi. CAG kesh ("meaning") takroriy so'rovni LLM'dan himoya qiladi.
        """
        try:
            if not getattr(self, "_meaning_assist", False):
                return {}
            if need in ("math", "weather"):
                return {}
            if len(text or "") < 16:
                return {}
            if not self.llm_available():
                return {}
            llm = self.llm
            if llm is None or not hasattr(llm, "complete"):
                return {}
        except Exception:
            return {}
        try:
            cache = self._cag()
        except Exception:
            cache = None
        return assist_fields(text, llm, cache=cache, family=family or "")

    def _interpret_request(self, message: str, pipeline: Optional[dict] = None,
                           req=None, llm_json: Optional[dict] = None) -> dict:
        """So'rovni to'liq ma'no strukturasiga aylantiradi (deterministik).

        muammo (problem) + maqsad (goal) + definitsiya + detaillar +
        paradigmaviy tahlil (ilmiy/mantiqiy/falsafiy/majoziy/realistik/...)
        + kanal tartibi (LLM-in/LLM-out aralashmasligi, noise bo'lmasin).

        Bu qatlam avvalo DETERMINISTIK — pipeline need (klassifikator) va
        RequirementExtractor signallarini birlashtiradi. Ixtiyoriy LLM assist
        (`_meaning_assist_fields`) faqat LLM mavjud va assist yoqilgan bo'lsa
        problem/goal/definition/paradigmsni boyitadi. Xato bo'lsa bo'sh dict
        qaytadi: asosiy javob hech qachon buzilmaydi.
        """
        try:
            text = (message or "").strip()
            if not text:
                return {}
            need = (pipeline or {}).get("need") or ""
            family: Optional[str] = None
            if need in getattr(request_classifier, "CREATOR_NEEDS", ()):
                family = "creator"
            elif need in ("chat", "math", "weather", "creative", "structure"):
                family = "chat"
            base: dict = {}
            if req is not None:
                intent = str(getattr(req, "intent", "") or "").strip()
                # "answer/general/chat" — bo'sh: deterministik fallback ishlasin
                if intent in ("answer", "general", "chat"):
                    intent = ""
                base = {
                    "intent": intent,
                    "language": str(getattr(req, "language", "") or ""),
                    "domain": str(getattr(req, "domain", "") or ""),
                    "output_format": str(getattr(req, "output_format", "") or ""),
                    "verbosity": str(getattr(req, "verbosity", "") or ""),
                    "constraints": list(getattr(req, "constraints", None) or []),
                    "needs_tools": bool(getattr(req, "needs_tools", False)),
                    "deliverable_name": getattr(req, "deliverable_name", None),
                    "confidence": getattr(req, "confidence", None) or 0.5,
                }
            base.update(llm_json or {})
            # Kesh: deterministik natija takroriy so'rovda qayta hisoblanmaydi
            cache = getattr(self, "_meaning_cache", None)
            if not isinstance(cache, dict):
                cache = {}
                self._meaning_cache = cache
            key = (text, need)
            hit = cache.get(key)
            if isinstance(hit, dict):
                # nusxa: har bir javob o'z strukturasiga ega bo'lsin
                # (keshdagi dict external o'zgaruvchilar bilan buzilmasin)
                return copy.deepcopy(hit)
            # IXTIYORIY LLM ASSIST: problem/goal/definition/paradigms boyitish
            # (deterministik natija ustiga qo'shiladi — replace emas)
            assist = self._meaning_assist_fields(text, need, family)
            merged = dict(base)
            merged.update(assist)
            meaning = parse_request_meaning(
                text, family=family, detect_family=family is None, llm_json=merged,
            )
            out = meaning.to_dict()
            if assist:
                # xom JSON = faqat haqiqiy assist (req signallari aralashmaydi)
                out["raw_llm_json"] = json.dumps(assist, ensure_ascii=False)[:4000]
            elif not llm_json:
                # xom JSON faqat tashqi/assist bo'lsa saqlanadi (noise guard)
                out.pop("raw_llm_json", None)
            if len(cache) > 256:
                cache.clear()
            cache[key] = out
            return copy.deepcopy(out)
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # CLARIFICATION GATE — agentic architecture §3.3.c
    # ------------------------------------------------------------------
    # Pre-loop gate: so'rov yetarli darajada aniqlanganini tekshiradi.
    # Agar kerakli maydonlar yetishmasa — clarify event yuboriladi va
    # agent SUHBATGA QAYTADI (loop boshlanmaydi). Foydalanuvchi javob
    # bergandan keyin pipeline QAYTA ishga tushadi.
    #
    # Xususiyatlar:
    #   - Faqat 1 marta so'raydi (§6: clarification_rounds = 1)
    #   - Javob hali ham yetarli bo'lmasa — best-guess default bilan
    #     davom etadi (idempotent intent)
    #   - chat() va chat_stream() ikkalasi ham shu gate'dan o'tadi
    # ------------------------------------------------------------------

    @staticmethod
    def _clarification_gate(req) -> Optional[dict]:
        """Clarification kerakligini tekshiradi — pre-loop gate.

        Qaytaradi: None (clarification kerak emas, loop davom etsin)
           yoki {'question': str, 'missing_fields': list} (clarify event).
        """
        if req is None:
            return None
        if not getattr(req, 'needs_clarification', False):
            return None
        question = getattr(req, 'clarification_question', None)
        if not question:
            return None
        missing = getattr(req, 'missing_fields', None) or []
        return {
            "question": question,
            "missing_fields": list(missing) if isinstance(missing, (list, tuple)) else [],
        }

    # ------------------------------------------------------------------
    # REVIEW DISPATCH — agentic architecture §3.2 + §6
    # ------------------------------------------------------------------
    # draw/code review bosqichidagi xatoliklarni ikki xil yo'l bilan
    # tuzatamiz:
    #
    #   build_verify: aniqlik tekshiruvi (rang, test, syntax) —
    #       deterministik, max_repair marta qayta urinish.
    #
    #   reflexion_critique: subyektiv tekshiruv (uslub, ohang) —
    #       LLM judge, max_repair marta self-critique + retry.
    #
    # loop_shape ga qarab to'g'ri yo'lni tanlaymiz.
    # ------------------------------------------------------------------

    def _review_dispatch(self, review_result: dict, pipeline: dict,
                         edit_fn=None, context: str = "",
                         review_fn=None) -> dict:
        """Review natijasini loop_shape ga qarab to'g'ri yo'lga yo'naltiradi.

        Args:
            review_result: {'ok': bool, 'issues': [...] | 'errors': [...], ...}
            pipeline: _build_pipeline() natijasi (loop_shape, max_repair)
            edit_fn: tuzatish funksiyasi — (issues) -> yangi matn (str|None)
            context: qo'shimcha kontekst (reflexion_critique uchun)
            review_fn: QAYTA TEKSHIRUV — tuzatilgan matnni tekshirib
                {'ok': bool, 'issues': [...]} qaytaradi. Berilmasa hech qanday
                "repaired" muvaffaqiyati E'LON QILINMAYDI (soxta yutuq yo'q).

        Returns:
            {'ok': bool, 'repaired': bool, 'attempts': int, 'method': str,
             'output'?: str, 'note'?: str, 'critique'?: str}

        Halol qoidalar (§3.2):
          - attempts HAQIQIY urinishlar soni (max_repair bilan cheklangan)
          - ok/repaired = faqat review_fn tasdiqlagan holat
          - output = oxirgi tuzatish (qayta tekshiruvsiz qabul qilinmaydi)
        """
        if review_result.get("ok", True):
            return {"ok": True, "repaired": False, "attempts": 0, "method": "none"}

        shape = pipeline.get("loop_shape", "straight_through")
        max_repair = pipeline.get("max_repair", 0)

        if max_repair <= 0:
            return {"ok": False, "repaired": False, "attempts": 0, "method": "none"}

        if shape == "build_verify":
            return self._build_verify_repair(review_result, edit_fn, max_repair,
                                             review_fn=review_fn)
        elif shape == "reflexion_critique":
            return self._reflexion_repair(review_result, context, max_repair,
                                          retry_fn=edit_fn, review_fn=review_fn)
        else:
            # straight_through, react_iterative, plan_then_execute — retry yo'q
            return {"ok": False, "repaired": False, "attempts": 0, "method": "none"}

    def _build_verify_repair(self, review_result: dict, edit_fn, max_repair: int,
                              review_fn=None) -> dict:
        """Build-verify: edit → QAYTA TEKSHIRISH sikli (max_repair marta).

        Eski versiya bitta edit'dan keyin O'Z-I qayta ko'rib chiqmasdan
        `ok=True, repaired=True` qaytarardi (soxta yutuq) va sikli birinchi
        qadamda tashlab yuborardi. Endi:
          - muvaffaqiyat FAQAT review_fn qayta tekshiruvi tasdiqlasa e'lon qiladi
          - review_fn berilmagan bo'lsa — "tasdiqlanmagan" (ok=False, note bor)
          - edit bo'sh/xato → sikli to'xtaydi (original matn buzilmaydi)
        Qaytaradi: {ok, repaired, attempts, method, output?, note?}
        """
        issues = list(review_result.get("issues") or review_result.get("errors") or [])
        if not issues or edit_fn is None:
            return {"ok": False, "repaired": False, "attempts": 0,
                    "method": "build_verify"}

        attempts = 0
        last_out = None
        for _ in range(max_repair):
            attempts += 1
            try:
                edited = edit_fn(list(issues))
            except Exception:
                break  # tuzatish o'zi yiqildi — original matn saqlanadi
            if not (isinstance(edited, str) and edited.strip()):
                break  # tuzatish kelmadi — sikli to'xtaydi
            last_out = edited
            if review_fn is None:
                # Qayta tekshiruv yo'q — "repaired" deb e'lon qilinmaydi
                return {"ok": False, "repaired": False, "attempts": attempts,
                        "method": "build_verify", "output": last_out,
                        "note": "verifier unavailable — repair not confirmed"}
            try:
                recheck = review_fn(edited) or {}
            except Exception:
                break  # tekshiruv yiqildi — cheksiz urinish yo'q
            if recheck.get("ok"):
                return {"ok": True, "repaired": True, "attempts": attempts,
                        "method": "build_verify", "output": edited}
            issues = list(recheck.get("issues") or issues)

        result = {"ok": False, "repaired": False, "attempts": attempts,
                  "method": "build_verify"}
        if last_out:
            result["output"] = last_out
        return result

    def _reflexion_repair(self, review_result: dict, context: str,
                          max_repair: int, retry_fn=None,
                          review_fn=None) -> dict:
        """Reflexion critique: critique bilan QAYTA generatsiya + review_fn tasdiq.

        Eski versiya hech qanday LLM qayta generatsiyasiz birinchi qadamda
        `ok=True, repaired=True` qaytarardi (dekorativ loop). Endi:
          - retry_fn(issues) -> yangi matn (haqiqiy qayta generatsiya)
          - review_fn(new_out) -> tasdiq; tasdiqlansa ok/repaired=True
          - retry_fn/review_fn yo'q bo'lsa — faqat critique hisoboti (ok=False)
        Qaytaradi: {ok, repaired, attempts, method, critique, output?, note?}
        """
        issues = list(review_result.get("issues") or review_result.get("errors") or [])
        if not issues:
            return {"ok": False, "repaired": False, "attempts": 0,
                    "method": "reflexion_critique"}

        critique = "; ".join(str(i) for i in issues[:3])
        if retry_fn is None:
            return {"ok": False, "repaired": False, "attempts": 0,
                    "method": "reflexion_critique", "critique": critique,
                    "note": "retry unavailable — critique recorded only"}

        attempts = 0
        last_out = None
        for _ in range(max_repair):
            attempts += 1
            try:
                out_text = retry_fn(list(issues))
            except Exception:
                break
            if not (isinstance(out_text, str) and out_text.strip()):
                break
            last_out = out_text
            if review_fn is None:
                break  # tasdiqsiz "repaired" emas — notqidagi result'da qayd etiladi
            try:
                recheck = review_fn(out_text) or {}
            except Exception:
                break
            if recheck.get("ok"):
                return {"ok": True, "repaired": True, "attempts": attempts,
                        "method": "reflexion_critique", "critique": critique,
                        "output": out_text}
            issues = list(recheck.get("issues") or issues)

        result = {"ok": False, "repaired": False, "attempts": attempts,
                  "method": "reflexion_critique", "critique": critique}
        if last_out:
            result["output"] = last_out
        if attempts and review_fn is None:
            result["note"] = "verifier unavailable — repair not confirmed"
        return result

    # ------------------------------------------------------------------
    # §3.2 REVIEW LOOP — javobga ulangan haqiqiy build_verify/reflexion
    # ------------------------------------------------------------------
    def _review_repair(self, data: dict, pipeline: dict) -> None:
        """`structure_check`/domain review muammosini HAQIQIY retry'ga ulaydi.

        PIPELINE_SPECS'dagi max_repair (draw/code/creative: 3) shu yerdan
        ishga tushadi — avvalgi holatda dispatch hech qayerdan chaqirilmaydi
        edi (loop dekorativ edi).

        Qoidalar (xavfsiz + halol):
          - max_repair > 0, review muammosi bor, LLM mavjud bo'lsa retry boshlanadi
          - content FAQAT review_fn qayta tekshiruvi tasdiqlasa almashtiriladi
          - bajarilmasa ORIGINAL matn saqlanadi; `data["review"]` halol hisobot
            qoldiradi (attempts/method/ok) va completion'ga uzatiladi
          - evidence gate: tuzatilgan matn ham action-evidence'dan o'tishi kerak
          - har qanday xato yutib yuboriladi — asosiy javob HECH QACHON buzilmaydi
        """
        try:
            max_repair = int(pipeline.get("max_repair") or 0)
            if max_repair <= 0:
                return
            check = data.get("structure_check")
            if not isinstance(check, dict) or check.get("ok", True):
                return
            if data.get("image") or data.get("refused"):
                return  # artefakt mavjud/rad etilgan — matn retry'siz qoladi
            content = str(data.get("content") or "")
            if not content.strip():
                return
            if not self.llm_available():
                return  # retry uchun LLM kerak — original matn saqlanadi
            message = str(data.get("message") or "")
            need = pipeline.get("need", "chat")
            issues = [str(i) for i in
                      (check.get("issues") or check.get("errors") or [])]
            if not issues:
                issues = ["review failed"]
            review = {"ok": False, "issues": issues, "kind": check.get("kind", "")}

            def edit_fn(given_issues: list) -> str:
                # Haqiqiy retry: tanqid bilan qayta generatsiya (to'liq natija)
                system = (
                    "Produce a corrected FULL version of your previous output for "
                    "the user request. Fix every listed problem. Return only the "
                    "final content — no explanations, no apologies."
                )
                prompt = (
                    f"User request:\n{message[:1500]}\n\n"
                    f"Your previous output:\n{content[:3000]}\n\n"
                    "Problems found by the reviewer:\n- "
                    + "\n- ".join(str(i) for i in list(given_issues)[:8])
                )
                out_text = self.llm.complete(system=system, prompt=prompt)
                return out_text or ""

            def review_fn(new_out: str) -> dict:
                # Qayta tekshiruv: struktura + domain (mos need uchun)
                _, sc = self._verify_and_repair(new_out)
                dc = None
                if need in ("code", "draw", "ui_build", "composition"):
                    _, dc = self._domain_verify(new_out, message, need)
                failed = sc or dc
                if failed is None:
                    return {"ok": True, "issues": []}
                return {"ok": False,
                        "issues": [str(i) for i in
                                   (failed.get("issues") or failed.get("errors") or [])]}

            result = self._review_dispatch(
                review, pipeline, edit_fn=edit_fn, context=message,
                review_fn=review_fn,
            )
            # halol audit izi — completion'da ko'rinadi
            data["review"] = {
                "ok": bool(result.get("ok")),
                "repaired": bool(result.get("repaired")),
                "attempts": int(result.get("attempts") or 0),
                "method": str(result.get("method") or ""),
            }
            if result.get("note"):
                data["review"]["note"] = str(result["note"])
            if not (result.get("ok") and result.get("repaired")
                    and result.get("output")):
                return  # tasdiqlanmadi — ORIGINAL content saqlanadi
            new_content = str(result["output"])
            # Evidence gate: tuzatilgan matn ham soxta da'voga yo'l qo'ymaydi
            try:
                from agent.action_evidence import evaluate as _evaluate
                ev_ok, _ev_reason = _evaluate(
                    new_content, data.get("tool_calls") or [], data.get("image"),
                    getattr(self, "workspace_root", None) or DEFAULT_WORKSPACE,
                    allow_promise=need in getattr(
                        request_classifier, "CREATOR_NEEDS", set()),
                )
            except Exception:
                ev_ok = True  # gate mavjud emas — review_fn yetarli signal
            if not ev_ok:
                data["review"]["ok"] = False
                data["review"]["repaired"] = False
                data["review"]["note"] = "action-evidence rejected repaired text"
                return
            data["content"] = new_content
            if isinstance(data.get("structure_check"), dict):
                data["structure_check"]["ok"] = True
                data["structure_check"]["repaired"] = True
        except Exception:
            return  # review loop hech qachon asosiy javobni buzmaydi

    def _review_resync(self, data: dict) -> None:
        """M7: review loop content'ni ALMASHTIRSA — kesh/RAG yozuvini sinxronlaydi.

        Stream/buffered yo'llarda memory.on_resolve va CAG put review loop'dan
        OLDIN sodir bo'ladi (o'sha paytda hali original matn bor). Tasdiqlangan
        yangi matn bilan yozuv yangilanmasa — keyingi bir xil so'rov CAG'dan
        ESKIRGAN (tasdiqlanmagan) javobni qayta-qayta olardi.

        Faqat `data["review"]["repaired"] == True` (haqiqiy almashtirish)
        holatida ishlaydi — boshqa hollarda no-op. Hech qachon exception
        bermaydi — asosiy javob buzilmaydi.
        """
        try:
            review = data.get("review")
            if not (isinstance(review, dict) and review.get("repaired")):
                return
            content = data.get("content")
            if not (isinstance(content, str) and content.strip()):
                return
            if not self._cacheable_out(content):
                return
            message = str(data.get("message") or "")
            mem = getattr(self, "memory", None)
            if mem is not None and getattr(mem, "enabled", False):
                mem.on_resolve(message, {
                    "output": content,
                    "engine": data.get("engine") or "llm",
                    "confidence": self._confidence_for(data),
                })
            if not self._is_date_question(message):
                cache = self._cag()
                if cache is not None:
                    cache.put(CHAT_TOOLS_SYSTEM, message, content)
        except Exception:
            pass

    @staticmethod
    def _today_note() -> str:
        """Real bugungi sana — eskirgan/soxta sana javoblarini oldini oladi."""
        try:
            from datetime import datetime
            now = datetime.now()
            months = ("yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul",
                      "avgust", "sentabr", "oktabr", "noyabr", "dekabr")
            days = ("dushanba", "seshanba", "chorshanba", "payshanba", "juma",
                    "shanba", "yakshanba")
            day = days[now.weekday()]
            return (
                f"\n\nCURRENT DATE (real, today): {day.title()}, {now.day} "
                f"{months[now.month - 1]} {now.year} (ISO {now.date().isoformat()}). "
                "If the user asks what day/date it is today, answer from this real "
                "date — never guess and never reuse an older answer."
            )
        except Exception:
            return ""

    @staticmethod
    def _is_date_question(message: str) -> bool:
        """Sana/vaqt so'rovi — CAG keshlanmaydi (javob tez eskiradi)."""
        low = (message or "").lower()
        if any(w in low for w in ("bugun", "bugungi", "sana", "nechanchi",
                                  "nechchanchi", "qaysi kun", "qaysi sana",
                                  "hozir qaysi")):
            return True
        return bool(re.search(
            r"\b(today|date|what day|what's the date|current date|day of week|weekday|what time|soat necha)\b",
            low))

    @staticmethod
    def _cacheable_out(out: str) -> bool:
        """Faqat SIFATLI javoblar CAG keshga tushadi — bo'sh/xato javoblar YO'Q.

        AUDIT: guard ro'yxati `_retry_generate`'ning fallback matnlari BILAN
        sinxron bo'lishi shart — ilgari "I could not produce an answer..."
        (fallback'ning aniq matni) guard'dan o'tib ketardi va junk RAG/CAG'ga
        yozilardi (test_chat_stream_turbo_junk_not_written_to_memory testi).
        """
        text = str(out or "").strip()
        if not text or len(text) < 6:
            return False
        low = text.lower()
        junk_markers = (
            "could not generate a response",
            "could not produce an answer",
            "the model returned an empty",
            "javob bera olmadi",
            "men javob bera olmadim",
        )
        return not any(marker in low for marker in junk_markers)

    @staticmethod
    def _token_chunks(text: str, size: int = 3) -> list[str]:
        """Yakuniy matnni kichik bo'laklarga ajratadi — tool yo'lida ham stream ko'rinadi."""
        text = str(text or "")
        return [text[i:i + size] for i in range(0, len(text), size)] or [""]

    @staticmethod
    def _extract_svg(text: str) -> Optional[tuple[str, str]]:
        """Javob ichidagi to'liq <svg>...</svg> blokini topadi.

        Model ba'zan tool chaqirmasdan SVG kodini matn sifatida yozadi — bunday
        javobni faylga yozib, haqiqiy chizma kartasiga aylantiramiz.
        Qaytadi: (svg_text, suggested_filename) yoki None.
        """
        import re as _re
        text = str(text or "")
        m = _re.search(r"<svg[\s\S]*?</svg>", text, _re.IGNORECASE)
        if not m:
            return None
        svg_text = m.group(0).strip()
        if "<svg" not in svg_text.lower() or "</svg>" not in svg_text.lower():
            return None
        # fayl nomi SVG blokdan TASHQARIDAGI matndan topiladi (xmlns.svg kabi
        # soxta mosliklarga yo'l qo'ymaymiz); topilmasa mavzu so'zidan yasaladi
        fn = _re.search(r"([\w-]+\.svg)", _re.sub(r"<svg[\s\S]*?</svg>", "", text), _re.IGNORECASE)
        if fn:
            fname = fn.group(1)
        else:
            words = _re.findall(r"[a-z]{4,}", svg_text.lower()[:400])
            first = next((w for w in words if w not in ("svg", "viewbox", "http", "www", "w3org", "xmlns")), "drawing")
            fname = first + ".svg"
        return svg_text, fname

    @staticmethod
    def _draw_style_from_request(request: str) -> str:
        """So'rovdan chizish uslubini aniqlaydi: cartoon | realistic | flat.

        Model style argument'ini bermasdan faqat so'zda aytgan bo'lsa ham
        ("realistik qilib chiz") — avtomatik aniqlanib, tool'ga uzatiladi.
        Topilmasa default 'cartoon'. DIQQAT: art_server.draw_custom_svg'dagi
        style aliaslari bilan sinxron saqlanishi kerak (bir xil so'zlar).
        """
        low = (request or "").lower()
        # Janrga mos uslublar (uz + en) — bola chizgandek, oq-qora, fantastik,
        # anime, realistik, flat, multfilm.
        if any(w in low for w in ("bola chizgandek", "bola chizgan", "bolalar",
                                  "bolacha", "childish", "childlike", "child",
                                  "kids drawing", "bola rasmi", "oddiy bola")):
            return "child"
        if any(w in low for w in ("oq qora", "oq-qora", "qora va oq", "qora oq",
                                  "black and white", "black & white", "b/w", "bw",
                                  "monochrome", "monoxrom", "grayscale")):
            return "bw"
        if any(w in low for w in ("fantastik", "fantasy", "ertak", "sehrli",
                                  "sarguzasht", "ajdarho", "jodugar", "mifologik",
                                  "magical", "mythical", "sci-fi", "ilmiy fantastik")):
            return "fantasy"
        if any(w in low for w in ("anime", "manga", "yaponcha", "yapon uslubi",
                                  "japonya", "anime uslubi")):
            return "anime"
        if any(w in low for w in ("realistik", "realistic", "fotorealistik",
                                  "photo-real", "photo realistic", "real ko'rinish",
                                  "real ko", "haqiqiy ko'rinish", "tabiiy ko'rinish",
                                  "hayotiy")):
            return "realistic"
        if any(w in low for w in ("flat", "tekis", "minimal", "minimalist",
                                  "oddiy ranglar", "geometrik", "modern uslub")):
            return "flat"
        if any(w in low for w in ("multfilm", "cartoon", "cizgi", "kulgili",
                                  "bolalar uslubi", "aniq kontur")):
            return "cartoon"
        return "cartoon"

    @staticmethod
    def _draw_size_from_request(request: str) -> str:
        """So'rovdan chizma o'lchamini aniqlaydi (canvas/ko'rinish).

        Qaytadi: icon | avatar | card | poster | banner | standard, yoki maxsus
        'WxH' (masalan "800x600" — so'rovda aniq o'lcham aytilgan bo'lsa).
        Model size argument'ini bermasdan faqat so'zda aytgan bo'lsa ham
        avtomatik aniqlanib, tool'ga uzatiladi. DIQQAT: art_server'dagi
        SIZE_ALIASES/SIZE_PRESETS bilan sinxron saqlanishi kerak (bir xil
        so'zlar). Tartib muhim: banner -> poster -> avatar -> card -> icon.
        """
        low = (request or "").lower()
        # Maxsus "800x600" / "800*600" / "800×600" — eng birinchi tekshiriladi
        m = re.search(r"(\d{2,4})\s*[xх*×]\s*(\d{2,4})", low)
        if m:
            w, h = int(m.group(1)), int(m.group(2))
            if 32 <= w <= 4096 and 32 <= h <= 4096:
                return f"{w}x{h}"
        if any(w in low for w in ("reklama banner", "keng format", "ultra-wide",
                                  "banner", "uzun gorizontal")):
            return "banner"
        if any(w in low for w in ("afisha", "plakat", "poster", "reklama",
                                  "portret format")):
            return "poster"
        if any(w in low for w in ("profil rasmi", "profil uchun", "avatar",
                                  "profil")):
            return "avatar"
        if any(w in low for w in ("karta", "kartochka", "card", "16:9",
                                  "16x9", "landscape")):
            return "card"
        if any(w in low for w in ("ikonka", "ikon", "icon", "belgi", "favicon",
                                  "kichik rasm", "kichkina rasm")):
            return "icon"
        return "standard"

    @staticmethod
    def _draw_color_from_request(request: str) -> str:
        """So'rovdan chizma RANGINI aniqlaydi (uz/en) — art__draw_scene_svg
        uchun. Topilmasa '' (tool default ishlatiladi). Uchun diqqat: rang
        so'zlari COLOR_MAP kalitlariga mos (qizil/red, yashil/green, ko'k/blue,
        sariq/yellow, binafsha/purple, pushti/pink, qora/black, oq/white,
        gold/oltin, to'q sariq/orange)."""
        low = (request or "").lower()
        for key in (
            "qizil", "red", "yashil", "green", "kok", "ko'k", "blue",
            "sariq", "yellow", "to'q sariq", "orange", "binafsha", "purple",
            "pushti", "pink", "qora", "black", "oq", "white", "oltin", "gold",
            "jigarrang", "brown",
        ):
            if re.search(rf"\b{re.escape(key)}\b", low):
                return key
        return ""

    # ------------------------------------------------------------ #
    # Ob-havo — tez deterministik yo'l — S5: quick_paths.py'ga ko'chirildi
    # (WEATHER_RE/WEATHER_STOP leksikasi, WMO/wttr jadvallari, quick_weather).
    # Klass attribute alias'lari — _classify_type/_detect_subject mosligi uchun.
    # ------------------------------------------------------------ #

    WEATHER_RE = quick_paths_mod.WEATHER_RE
    WEATHER_STOP = quick_paths_mod.WEATHER_STOP

    @staticmethod
    def _wttr_cond(cond: str) -> str:
        return quick_paths_mod.wttr_cond(cond)

    def _quick_weather(self, message: str) -> Optional[str]:
        """Ob-havo tez javob — S5 quick_paths.quick_weather (wttr.in + Open-Meteo)."""
        return quick_paths_mod.quick_weather(message)

    @staticmethod
    def _wmo_text(code: int) -> str:
        return quick_paths_mod.wmo_text(code)

    @staticmethod
    def _fmt_temp(t) -> str:
        return quick_paths_mod.fmt_temp(t)

    # ------------------------------------------------------------ #
    # Web bridge — chatda zarurat bo'lsa AVTOMATIK yoqish
    # ------------------------------------------------------------ #

    # URL yoki brauzer/web ishtiroki bor so'rovlar — web_ai_bridge tool'lari
    # chatda ham avtomatik ochiladi (model ularni ishlatishi uchun).
    #
    # Soxta pozitivlar YO'Q: 'web', 'link', 'site', 'search' kabi umumiy so'zlar
    # O'ZI ishlamaydi ('web framework', 'linked list', 'binary search' kabi kod
    # mavzulari brauzer talab qilmaydi). Faqat: URL/manzil, sayt ochish, brauzer
    # amali, qidiruv amali — aniq veb ehtiyoji.
    # Veb darvoza/strategiya — S5: web_strategy.py'da (yagona manba).
    WEB_INTENT_RE = web_strategy_mod.WEB_INTENT_RE
    WEB_GATE_RE = web_strategy_mod.WEB_GATE_RE
    WEB_AI_NAME_RE = web_strategy_mod.WEB_AI_NAME_RE
    WEB_RESEARCH_RE = web_strategy_mod.WEB_RESEARCH_RE
    WEB_BROWSER_RE = web_strategy_mod.WEB_BROWSER_RE
    WEB_DELEGATE_FAMILY = web_strategy_mod.WEB_DELEGATE_KEYS
    WEB_INTERACTION_TOOLS = web_strategy_mod.WEB_INTERACTION_KEYS

    @classmethod
    def _needs_web(cls, message: str) -> bool:
        """Veb/brauzer ehtiyoji bormi? — S5: web_strategy.needs_web."""
        return web_strategy_mod.needs_web(message)

    @classmethod
    def _web_strategy(cls, message: str) -> str:
        """Veb strategiya (''|delegate|browser|full) — S5 igris_web qatoridan delegatsiya."""
        return web_strategy_mod.web_strategy(message)


    def _web_tools(self, strategy: str = "full") -> list[dict]:
        """web_ai_bridge tool'larini STRATEGIYAGA qarab filtrlangan holda beradi.

        - 'delegate': web AI SUBAGENT tool'lari (ask_web_ai, research...) +
          minimal browser (navigate/get_text) — web AI ishlamasa zaxira.
        - 'browser' : faqat brauzer amallari (navigate, get_text, click...).
        - 'full'    : ikkalasi ham.

        Maqsad: modelga 28 ta tool'ni birdan tashlamaymiz — vazifaga mos
        fokuslangan to'plam beriladi, browser maqsadsiz chaqirilmaydi.
        Faqat web_ai_bridge ulangan bo'lsa qaytaradi. Aks holda bo'sh.
        """
        mcp = self._mcp()
        if mcp is None:
            return []
        all_web = {k for k in mcp.tool_index if k.startswith("web_ai_bridge__")}
        if strategy == "delegate":
            allowed = web_strategy_mod.delegate_tool_keys()
        elif strategy == "browser":
            allowed = all_web - web_strategy_mod.WEB_DELEGATE_KEYS
        else:  # 'full' / noma'lum — hammasi
            allowed = all_web
        schemas: list[dict] = []
        for key in sorted(allowed):
            info = mcp.tool_index.get(key) or {}
            schema = info.get("schema") or {}
            # WEB_TOOLS_GUIDE dan QISQA ko'rsatma — model tool tanlash paytida
            # ham qachon ishlatishni ko'radi. MANBA: web-ai-bridge server'ining
            # o'zi (index.js WHEN_TO_USE) — description'da allaqachon bor bo'lsa
            # qayta qo'shilmaydi; WEB_TOOL_HINTS faqat ESKI bridge zaxirasi.
            desc = schema.get("description") or ""
            if "WHEN TO USE" not in desc:
                desc = _tool_desc_with_hint(schema, WEB_TOOL_HINTS.get(key))
            else:
                desc = desc[:800]  # server hint bilan kelgan — faqat cap
            schemas.append({
                "type": "function",
                "function": {
                    "name": key,
                    "description": desc,
                    "parameters": schema.get("parameters") or {"type": "object", "properties": {}},
                },
            })
        return schemas

    @classmethod
    def _web_decision_rules(cls, strategy: str) -> str:
        """Web qaror qoidalari — S5: web_strategy.web_decision_rules."""
        return web_strategy_mod.web_decision_rules(strategy)

    # --- WEB STRATEGIYA KUZATUVI: har web so'rov qarori log'ga yoziladi ---
    #
    # Maqsad: xatolarni topish. Har web so'rovdan so'ng qaysi strategiya
    # tanlangan + model amalda NIMA qilgani logs/web_strategy.jsonl ga yoziladi.
    # Hisobot: `python web_strategy_report.py`.
    # (WEB_DELEGATE_FAMILY / WEB_INTERACTION_TOOLS — yuqorida alias qilingan.)

    def _web_strategy_log_path(self) -> str:
        """Web strategiya kuzatuv log fayli (JSONL). Testlarda o'zgartirilishi mumkin."""
        if getattr(self, "_web_log_path", None):
            return self._web_log_path
        return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "logs", "web_strategy.jsonl")

    def _log_web_strategy(self, message: str, strategy: str,
                          tool_calls: Optional[list] = None,
                          engine: str = "", mcp_ok: bool = True,
                          content_len: int = 0) -> None:
        """Har web so'rov qarorini logs/web_strategy.jsonl ga yozadi (kuzatuv).

        Verdict — model to'g'ri yo'l tutdimi:
          ok-delegate / ok-browser / ok-full   — strategiyaga mos tool ishlatildi
          misuse-browser                       — delegate kerak edi, interaktiv browser ishlatildi
          browser-fallback                     — delegate'da faqat o'qish browser (zaxira, ruxsat)
          delegated-instead                    — browser kutilgan, web AI'ga topshirildi (ma'qul)
          no-web-tool                          — strategiya bor, lekin web tool ishlatilmadi
          unexpected-web                       — strategiyasiz web tool chaqirildi (darvoza chetlab o'tilgan?)
          unavailable                          — web_ai_bridge ulanmagan

        Hech qachon agentni buzmaydi (try/except).
        """
        try:
            import json as _json
            from datetime import datetime
            if not strategy and not (tool_calls or []):
                return  # web bo'lmagan suhbat — log shovqin qilmaydi
            calls: list[str] = []
            for tc in (tool_calls or []):
                if isinstance(tc, dict):
                    calls.append(str(tc.get("tool") or ""))
                else:
                    calls.append(str(tc))
            web_calls = [c for c in calls if c.startswith("web_ai_bridge__")]
            delegation_used = bool(set(web_calls) & self.WEB_DELEGATE_FAMILY)
            interaction_used = bool(set(web_calls) & self.WEB_INTERACTION_TOOLS)
            browser_used = any(c.startswith("web_ai_bridge__browser_") for c in web_calls)
            # Verdict
            if not mcp_ok and strategy:
                verdict = "unavailable"
            elif not strategy:
                verdict = "unexpected-web" if web_calls else None
            elif strategy == "delegate":
                if delegation_used:
                    verdict = "ok-delegate"
                elif interaction_used:
                    verdict = "misuse-browser"
                elif browser_used:
                    verdict = "browser-fallback"
                elif web_calls:
                    verdict = "other-web"
                else:
                    verdict = "no-web-tool"
            elif strategy == "browser":
                if browser_used:
                    verdict = "ok-browser"
                elif delegation_used:
                    verdict = "delegated-instead"
                elif web_calls:
                    verdict = "other-web"
                else:
                    verdict = "no-web-tool"
            else:  # full
                verdict = "ok-full" if web_calls else "no-web-tool"
            if verdict is None:
                return
            # Qaysi regex mos keldi — klassifikatsiya xatolarini topish uchun
            msg = message or ""
            matched: list[str] = []
            if re.search(r"https?://|www\.", msg, re.IGNORECASE):
                matched.append("url")
            if self.WEB_AI_NAME_RE.search(msg):
                matched.append("ai_name")
            if self.WEB_RESEARCH_RE.search(msg):
                matched.append("research")
            if self.WEB_BROWSER_RE.search(msg):
                matched.append("browser")
            if self.WEB_GATE_RE.search(msg):
                matched.append("gate")
            entry = {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "message": msg[:160],
                "strategy": strategy or "",
                "needs_web": bool(strategy),
                "web_available": bool(mcp_ok),
                "tool_calls": calls[:8],
                "delegation_used": delegation_used,
                "browser_used": browser_used,
                "matched": matched,
                "verdict": verdict,
                "engine": engine or "",
                "content_len": int(content_len or 0),
            }
            path = self._web_strategy_log_path()
            logs_dir = os.path.dirname(path)
            if logs_dir and not os.path.isdir(logs_dir):
                os.makedirs(logs_dir, exist_ok=True)
            # 2MB dan oshsa — .old ga surib, yangi boshlaymiz (cheksiz o'smaydi)
            if os.path.isfile(path) and os.path.getsize(path) > 2_000_000:
                os.replace(path, path + ".old")
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(_json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # kuzatuv hech qachon agentni buzmaydi

    # ------------------------------------------------------------ #
    # Chat tool'lar: MCP + registry, capability-gap re-prompt
    # ------------------------------------------------------------ #

    def _mcp(self):
        """Lazy MCP bridge — server'lar ulangan bo'lsa qaytaradi, aks holda None."""
        if self._mcp_cache is None:
            try:
                from tools.mcp_bridge import DEFAULT_BRIDGE
                if not DEFAULT_BRIDGE.status()["servers"]:
                    try:
                        DEFAULT_BRIDGE.start()
                    except Exception as exc:
                        print(f"[igris][chat] mcp start: {exc}")
                self._mcp_cache = DEFAULT_BRIDGE if DEFAULT_BRIDGE.status()["servers"] else None
            except Exception as exc:
                print(f"[igris][chat] mcp unavailable: {exc}")
                self._mcp_cache = None
        return self._mcp_cache

    def _registry(self):
        if self._registry_cache is None:
            try:
                from tools import DEFAULT_REGISTRY
                self._registry_cache = DEFAULT_REGISTRY
            except Exception:
                self._registry_cache = None
        return self._registry_cache

    def _chat_executor(self):
        """Tool bajarish uchun engil AgentExecutor (MCP + workspace + registry)."""
        if self._chat_exec is None:
            from executor.executor import AgentExecutor
            self._chat_exec = AgentExecutor(
                workspace_root=self.workspace_root,
                llm=self.llm,
                mcp=self._mcp(),
            )
        return self._chat_exec

    def _chat_tools(self, include_web: bool = False, web_strategy: str = "") -> list[dict]:
        """Chat uchun Ollama tool-schema'lari: MCP tool'lari + registry tool'lari.

        include_web=True bo'lsa web_ai_bridge tool'lari strategiyaga qarab
        qo'shiladi (delegate/browser/full) — model faqat vazifaga mos to'plamni
        ko'radi, browser maqsadsiz chaqirilmaydi.
        """
        if self._chat_tools_cache is not None and not include_web:
            return self._chat_tools_cache
        tools: list[dict] = []
        mcp = self._mcp()
        if mcp is not None:
            # Chat uchun lokal yaratish tool'lari: 'art__*' rasm va
            # 'artifact__*' Office/diagram/3D/EDA/audio. Brauzer tool'lari
            # (web_ai_bridge__*) faqat WEB so'rovida, strategiyaga mos to'plam
            # bilan qo'shiladi — oddiy chatda model ularni noto'g'ri chaqirib,
            # placeholder URL'lar bilan keraksiz ish qilmasligi uchun.
            for key, info in sorted(mcp.tool_index.items()):
                if not key.startswith(("art__", "artifact__")):
                    continue
                schema = info.get("schema") or {}
                # Qisqa hint model qaysi real artifact vositasini QACHON
                # tanlashini ko'rsatadi (to'liq contract MCP schema'da).
                hint = ART_TOOL_HINTS.get(key) or ARTIFACT_TOOL_HINTS.get(key)
                desc = _tool_desc_with_hint(schema, hint)
                tools.append({
                    "type": "function",
                    "function": {
                        "name": key,
                        "description": desc,
                        "parameters": schema.get("parameters") or {"type": "object", "properties": {}},
                    },
                })
            if tools:
                # mcp_call'da web_ai_bridge tool'lari KO'RSATILMAYDI — ular faqat
                # include_web=True bo'lganda strategiyaga mos ochiladi. Aks holda
                # model istalgan chatda mcp_call orqali browser'ni chaqirib
                # qo'yardi (maqsadsiz foydalanish manbai).
                mcp_call_names = [
                    n for n in (mcp.names() or [])
                    if not n.startswith("web_ai_bridge__")
                ]
                tools.append({
                    "type": "function",
                    "function": {
                        "name": "mcp_call",
                        "description": "Call a tool on a connected MCP server. Use name "
                                        "'server__tool'. Available tools: "
                                        + ", ".join(mcp_call_names or ["(none)"]),
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
        if include_web:
            tools.extend(self._web_tools(web_strategy or "full"))
        reg = self._registry()
        if reg is not None:
            tools.extend(reg.ollama_schemas())
        # Vision tools — agar vision system mavjud bo'lsa
        if self.vision is not None:
            tools.extend(self._vision_tools())
        # Smart Build tools — Weak LLM + Strong Cognitive Infrastructure
        if self.smart_build_engine is not None:
            tools.extend(self.smart_build_tools())
        # Faqat MCP ulangan bo'lsa keshlaymiz — aks holda keyingi qo'ng'iroqda
        # qayta sinab ko'riladi (art tool'lari o'tkazib yuborilmasligi uchun).
        # Web tool'lar KESHLANMAYDI — har so'rovda strategiyaga qarab tanlanadi.
        if mcp is not None and not include_web:
            self._chat_tools_cache = tools
        return tools

    def _chat_with_tools(self, messages: list[dict], tools: list[dict], web: bool = False,
                         progress=None, req: Optional[Requirement] = None,
                         on_loop_iteration=None,
                         max_rounds=None, loop_shape=None,
                         ) -> tuple[str, list[dict], Optional[str]]:
        """Tool'li chat loop: model tool tanlasa bajaradi, aks holda matn qaytaradi.

        - model "qila olmayman" desa (capability-gap) — real tool'lar eslatiladi
        - bajarilgan tool natijalari modelga tool-message sifatida qaytariladi
        - bir xil (tool, args) chaqiruv faqat BIR marta bajariladi (loop oldini olish)
        - yakuniy javob tool-call JSON bo'lib qolsa — oddiy matnli xulosa so'raladi
        - progress: ixtiyoriy (stage, detail) callback — har tool bajarilganda
          frontend stepperiga JONLI bosqich yuboriladi

        Qaytadi: (final_text, tool_calls, image_path)
        """
        import json as _json
        from executor.executor import stage_for_tool, _tool_preview  # noqa: E402
        tool_calls: list[dict] = []
        image: Optional[str] = None
        gap_prompted = False
        seen: set[tuple] = set()
        empty_nudges = 0
        # ORIGINAL so'rov — nudge/hint xabarlari qo'shilishidan OLDI olinadi.
        # (SVG auto-save draw-intent tekshiruvi shunga tayanadi; aks holda oxirgi
        #  user xabari nudge bo'lib qolib, chizma o'tkazib yuborilishi mumkin.)
        original_request = ""
        for _m in reversed(messages):
            if _m.get("role") == "user":
                original_request = str(_m.get("content") or "")
                break
        # WEB vazifalar ko'proq qadam talab qiladi (navigate -> get_text ->
        # type -> click -> summarize) -> 8 round. Oddiy/vazifa loop'lari uchun
        # 6 round (write -> run -> fix: tuzatishga joy).
        # §3.2 max_iter BUDGET: pipeline max_iter (PIPELINE_SPECS) va default
        # orasidan KATTA qabul qilinadi — kam round bergan spec (masalan
        # plan_then_execute: max_iter=1) ham bajaruvchi loopni to'xtatmaydi,
        # katta budget (code/draw: 8) esa o'z navbatida oshiriladi.
        _default_rounds = 8 if web else 6
        try:
            _spec_rounds = int(max_rounds) if max_rounds else 0
        except (TypeError, ValueError):
            _spec_rounds = 0
        max_rounds = max(_default_rounds, _spec_rounds)
        # Part L (CP-L5): yopiq ro'yxatdan tashqari obyekt (NOT_SUPPORTED) —
        # modelga 1 marta "o'zing generatsiya qil" yo'naltiriladi (ochiq domen).
        not_supported_prompted = False

        # Part O: ma'lum (canned) subject uchun DETERMINISTIK chizma — modelga
        # bog'liq emas, talab (subject/rang) aniq bajariladi va crash bermaydi.
        if not web and self._is_draw_request(original_request):
            det = self._try_deterministic_scene(original_request, progress)
            if det is not None:
                tool_calls.append({
                    "tool": det["tool"],
                    "args": det["args"],
                    "result": {k: v for k, v in det["result"].items() if k != "output"},
                    "output_preview": str(det["result"].get("output") or "")[:300],
                })
                return det["content"], tool_calls, det["image"]
            # Part O: noma'lum subject — avtomatik chizmasdan o'tkazamiz,
            # LLM ga art__draw_custom_svg bilan istalgan narsani chizish
            # imkoniyatini beramiz (avvalgi hard-refusal o'rniga).

        for _iter in range(max_rounds):
            # loop_iteration event: frontend "attempt N of M" ko'rsatadi
            if on_loop_iteration is not None:
                try:
                    on_loop_iteration(_iter + 1, max_rounds,
                                      loop_shape or "react_iterative")
                except Exception:
                    pass
            resp = self.llm.chat_with_tools(messages, tools=tools)
            if not resp or not isinstance(resp, dict):
                break
            calls = resp.get("tool_calls") or []
            if calls:
                new_any = False
                not_supported_seen = False
                for call in calls:
                    name = str(call.get("name") or "").strip()
                    if not name:
                        continue
                    args = call.get("arguments") or {}
                    try:
                        key = (name, _json.dumps(sorted(args.items(), key=str),
                                                 ensure_ascii=False, default=str))
                    except Exception:
                        key = (name, str(args))
                    if key in seen:
                        continue  # takroriy chaqiruv — o'tkazib yuboramiz
                    seen.add(key)
                    new_any = True
                    result = self._execute_chat_tool(name, args)
                    ok = bool(result.get("ok"))
                    # JONLI PIPELINE: bajarilgan tool frontend stepperida ko'rinadi
                    if progress is not None:
                        try:
                            progress(stage_for_tool(name),
                                     f"{name} → {_tool_preview(name, args)}")
                        except Exception:
                            pass
                    tool_calls.append({
                        "tool": name,
                        "args": args,
                        "result": {k: v for k, v in result.items() if k != "output"},
                        "output_preview": str(result.get("output") or result.get("content") or "")[:300],
                    })
                    # A4 (web manba tekshiruvi): web tool natijalari manba
                    # indeksiga yig'iladi — yakuniy javob _with_self_eval'da shu
                    # manbalar bilan grounding tekshiruvidan o'tadi.
                    # (fail-safe: hech qachon tool yo'lini buzmaydi)
                    if _is_web_source_tool(name):
                        try:
                            src_text = str(result.get("output") or result.get("content") or "")
                            if src_text.strip():
                                if self._web_sources is None:
                                    from web.web_verify import SourceIndex  # noqa: E402
                                    self._web_sources = SourceIndex()
                                self._web_sources.add(src_text, name)
                        except Exception:
                            pass
                    if ok and image is None:
                        # Har qanday muvaffaqiyatli tool natijasidan rasm yo'lini aniqlaymiz
                        # (to'g'ridan-to'g'ri art__draw_object_png yoki mcp_call indireksiyasi)
                        image = self._image_from_art_call(result)
                        if image:
                            # Chizma tugadi — sifatni baholab, L2 xotiraga yozamiz
                            self._remember_drawing_quality(image, original_request)
                    result_text = str(result.get("output") or result.get("content") or result.get("error") or "ok")
                    if "NOT_SUPPORTED" in result_text or "unknown subject" in result_text \
                            or "unknown app" in result_text:
                        not_supported_seen = True
                    messages.append({"role": "tool", "name": name, "content": result_text[:4000]})
                if not not_supported_prompted and not_supported_seen:
                    # Part L (CP-L5): model yopiq ro'yxatga urindi — ochiq domen:
                    # artefaktni O'ZI generatsiya qilishga yo'naltiramiz (1 marta).
                    not_supported_prompted = True
                    messages.append({
                        "role": "user",
                        "content": (
                            "That tool only supports predefined items. For this request, "
                            "generate the artifact yourself instead of giving up: for an "
                            "image, write/emit the full SVG and it will be saved automatically; "
                            "for a UI/app, build the HTML/plan yourself. Do not call a "
                            "predefined-subject tool again with the same subject."
                        ),
                    })
                    continue
                if not new_any:
                    # hammasi takroriy — model aylanma loopda; to'xtaymiz
                    break
                if image:
                    # rasm chizildi — maqsadga erishildi, qo'shimcha round shart emas
                    break
                continue
            content = (resp.get("content") or "").strip()
            if not content and not tool_calls:
                # qwen3 ba'zan faqat thinking, ba'zan BUTUNLAY bo'sh javob
                # beradi — ikkalasida ham davom ettirishni so'raymiz
                # ("I could not generate a response." kabi bo'sh xatolar oldini olish).
                if empty_nudges >= 2:
                    break
                empty_nudges += 1
                hint = "only internal reasoning" if resp.get("thinking") else "an empty reply"
                messages.append({
                    "role": "user",
                    "content": (
                        f"Your previous reply contained {hint}. Now give the actual "
                        "final answer to the user's request, or call the appropriate tool."
                    ),
                })
                continue
            if content and not tool_calls and self._capability_gap(content):
                if gap_prompted < 2:
                    # model "qila olmayman" dedi — real vositalarini eslatamiz
                    # (max 2 marta: 1-chi umumiy, 2-chi aniqroq yo'naltirish)
                    gap_prompted += 1
                    if gap_prompted == 1:
                        messages.append({"role": "user",
                                         "content": self._tools_hint(request=original_request)})
                    else:
                        # 2-chi urinish: modelga aniq buyruq — qaysi toolni qanday
                        # chaqirishni ko'rsatamiz (abstract "you have tools" emas)
                        tool_names = [t.get("function", {}).get("name", "")
                                      for t in (tools or []) if t.get("function", {}).get("name")]
                        messages.append({"role": "user",
                                         "content": (
                                             "STOP saying you cannot. You have these exact tools "
                                             f"right now: {', '.join(tool_names[:10])}. "
                                             "CALL ONE OF THEM IMMEDIATELY to fulfill the user's "
                                             "request. Do not reply with text — make a tool call."
                                         )})
                    continue
            # Model SVG kodini tool'cha MATN sifatida yozsa — faylga yozamiz
            # (real chizma kartasi; "fayl yaratdim" deb yolg'on aytmaydi).
            content, image = self._save_svg_from_text(content, tool_calls, image, original_request)
            # Office/diagram/engineering/audio format talabida model faqat
            # matn bilan qaytsa, yakuniy da'voni kutmaymiz: lokal artifact
            # fallback haqiqiy faylni yaratib + validatsiya qiladi.
            if content and not tool_calls and self._artifact_kind(original_request):
                artifact = self._deterministic_artifact_fallback(original_request, progress)
                if artifact is not None:
                    return artifact["content"], artifact["tool_calls"], image
            if (content or "").strip() or image:
                return content or "", tool_calls, image
            if self._is_draw_request(original_request):
                # Part O+: bo'sh/soxta javob — rad etishdan OLDIN last-chance
                # draw retry (pastda, loop'dan keyin) sinaymiz.
                break
            return "", tool_calls, image

        # Tool'lar bajarilgandan keyin modeldan ODDIY matnli xulosa so'raladi —
        # qwen2.5-coder tool-call JSON'ini content sifatida takrorlaydi, shuning
        # uchun toolsiz chat so'rovi yuboramiz (JSON takrori emas, haqiqiy xulosa).
        if tool_calls:
            base = [m for m in messages if m.get("role") in ("system", "user", "assistant")]
            base.append({
                "role": "user",
                # Part L (B1): xulosa ko'rsatmasi req'ga mos (til/chuqurlik/format).
                "content": self._summary_instruction(req) if req is not None else (
                    "Summarize what you just did for the user in 1-2 short sentences, "
                    "in the user's language. Plain text only — no JSON, no tool-call "
                    "format, no code fences. Mention the created file if relevant."
                ),
            })
            resp = self.llm.chat(base)
            if resp and resp.strip():
                return resp.strip(), tool_calls, image
            # Part L: canned "Bajarildi..." faqat haqiqiy natija bilan (yolg'on emas):
            # AUDIT FIX: draw so'rovda rasm chiqmasa (masalan NOT_SUPPORTED
            # keyin model voz kechgan) "Bajarildi" soxta muvaffaqiyat signaldir —
            # bo'sh matn qaytaramiz (yuqori qatlam _retry_generate/halol refusal
            # bilan davom etadi).
            if image or not self._is_draw_request(original_request):
                return f"Bajarildi: {len(tool_calls)} tool chaqiruvi amalga oshirildi.", tool_calls, image
            return "", tool_calls, image

        # ---------- DETERMINISTIC ARTIFACT FALLBACK ----------
        # LLM Office/engineering formatini tanib, lekin tool-call qilmagan
        # holatda ham haqiqiy fayl yaratiladi. Bu avvalgi "PPTX yaratildi"
        # degan, ammo diskda hech narsa bo'lmagan soxta yakunlashni yopadi.
        artifact = self._deterministic_artifact_fallback(original_request, progress)
        if artifact is not None:
            tool_calls.extend(artifact["tool_calls"])
            return artifact["content"], tool_calls, image

        # ---------- DETERMINISTIC FALLBACK: LLM tool chaqirmadi yoki rad etdi ----------
        # Agar so'rov kod/fayl yaratish talab qiladi (file, code, app, game, dashboard...)
        # va LLM hech qanday tool chaqirmagan bo'lsa — avtomatik kod generatsiya qilib
        # faylga yozamiz. Bu "agent rad etdi" muammosini hal qiladi.
        if self._needs_code_fallback(original_request) and self.llm is not None:
            fb = self._deterministic_code_fallback(original_request, original_request, progress)
            if fb is not None:
                tool_calls.append({
                    "tool": fb["tool"],
                    "args": fb["args"],
                    "result": {"ok": True},
                    "output_preview": str(fb.get("output", ""))[:300],
                })
                return fb["content"], tool_calls, image

        # Part O+ (LAST-CHANCE DRAW RETRY): draw so'rovida LLM tool chaqirmadi
        # yoki bo'sh qaytardi — "chiza olmadim" deb rad etishdan OLDIN 1 marta
        # aniq SVG generatsiya buyrug'i bilan urinamiz. Muvaffaqiyat: REAL
        # chizma fayli; aks holda eski halol refusal ("" -> _retry_generate)
        # o'zgarmay qoladi (junk SVG foydalanuvchiga yetib bormaydi).
        if (not image and not web and self.llm is not None
                and self.llm_available()
                and self._is_draw_request(original_request)):
            lc_content, lc_image = self._last_chance_draw(original_request)
            if lc_image:
                tool_calls.append({
                    "tool": "art__draw_custom_svg",
                    "args": {"output": lc_image},
                    "result": {"ok": True},
                    "output_preview": f"last-chance draw retry -> {lc_image}",
                })
                return lc_content, tool_calls, lc_image

        return "", tool_calls, image

    # Past ball olgan chizmalar uchun avtomatik qayta chizish chegarasi.
    # Qayta chizish faqat BIR marta bajariladi (har biri ~60-90s oladi).
    REDRAW_SCORE_MIN = 55

    def _validate_drawing(self, image: Optional[str]) -> Optional[dict]:
        """Saqlangan chizma faylini svg_validator bilan baholaydi."""
        if not image:
            return None
        try:
            from verification.svg_validator import validate_svg_file
            path = os.path.join(self.workspace_root, str(image).replace("/", os.sep))
            return validate_svg_file(path)
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # DETERMINISTIC ARTIFACT FALLBACK — Office / Diagram / 3D / EDA / Audio
    # ------------------------------------------------------------------ #

    _ARTIFACT_CREATE_RE = re.compile(
        r"\b(?:yarat|tayyorla|tuz|yasa|qur|yoz|chiz|generate|create|make|"
        r"build|write|draw|produce)\w*", re.IGNORECASE)

    @classmethod
    def _artifact_kind(cls, request: str) -> str:
        """Natural-language creation request -> local artifact MCP tool kind.

        Faqat yaratish fe'li bilan birga ishlaydi: "pptx nima?" kabi bilim
        savolini fayl yaratishga aylantirib yubormaydi.
        """
        low = str(request or "").lower()
        if not cls._ARTIFACT_CREATE_RE.search(low):
            return ""
        if any(word in low for word in ("pptx", "powerpoint", "taqdimot",
                                        "prezentats", "presentation")):
            return "presentation"
        if any(word in low for word in ("docx", "word hujjat", "word document")):
            return "document"
        if any(word in low for word in ("xlsx", "excel", "spreadsheet")):
            return "spreadsheet"
        if "pdf" in low:
            return "pdf"
        if any(word in low for word in ("kicad", "pcb", "plata", "circuit board")):
            return "pcb"
        if any(word in low for word in ("schematic", "sxematik", "elektr sxema")):
            return "schematic"
        if any(word in low for word in ("openscad", ".scad", "parametric 3d")):
            return "openscad"
        if any(word in low for word in ("stl", "3d model", "3d obyekt", "3d object")):
            return "3d"
        if any(word in low for word in ("diagramma", "diagram", "flowchart",
                                        "mermaid", "graphviz", "blok sxema")):
            return "diagram"
        if any(word in low for word in ("audio", "wav", "ovoz", "tone", "tts")):
            return "audio"
        return ""

    @staticmethod
    def _artifact_output(request: str, kind: str) -> str:
        """User ko'rsatgan output nomini saqlaydi yoki xavfsiz default beradi."""
        extensions = {
            "presentation": "pptx", "document": "docx", "spreadsheet": "xlsx",
            "pdf": "pdf", "diagram": "svg", "3d": "stl", "openscad": "scad",
            "pcb": "kicad_pcb", "schematic": "kicad_sch", "audio": "wav",
        }
        ext = extensions[kind]
        match = re.search(rf"(?<![\w/\\])([\w./\\-]+\.{re.escape(ext)})\b",
                          str(request or ""), re.IGNORECASE)
        if match:
            return match.group(1).replace("\\", "/")
        return f"{kind}_{int(time.time() * 1000)}.{ext}"

    @staticmethod
    def _artifact_title(request: str, kind: str) -> str:
        """Fayl ichidagi sarlavha — raw request emas, qisqa foydali matn."""
        text = re.sub(r"\s+", " ", str(request or "")).strip(" .,:;!?-")
        text = re.sub(
            r"\b(?:pptx|powerpoint|taqdimot|prezentatsiya|presentation|docx|"
            r"xlsx|excel|spreadsheet|pdf|diagramma|diagram|flowchart|"
            r"yarat\w*|tayyorla\w*|tuz\w*|yasa\w*|qur\w*|ber\w*|"
            r"create|generate|make|build|please)\b",
            "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip(" .,:;!?-")
        defaults = {
            "presentation": "IGRIS Presentation", "document": "IGRIS Document",
            "spreadsheet": "IGRIS Data", "pdf": "IGRIS Report", "diagram": "IGRIS Flow",
            "3d": "IGRIS 3D Model", "openscad": "IGRIS Parametric Model",
            "pcb": "IGRIS PCB", "schematic": "IGRIS Schematic", "audio": "IGRIS Audio",
        }
        return (text[:140] or defaults[kind])

    def _deterministic_artifact_fallback(self, request: str, progress=None) -> Optional[dict]:
        """Create + verify a basic local artifact when the model skipped tools.

        Bu zaxira faqat explicit format + creation so'roviga ishlaydi. U LLM
        rejasini almashtirmaydi: model birinchi urinishda batafsil artefakt
        yaratishi mumkin. Ammo u tool chaqirmay qolsa, agent hech qachon faqat
        matnda "yaratildi" deb aytib qo'ymaydi.
        """
        kind = self._artifact_kind(request)
        if not kind:
            return None
        tool_by_kind = {
            "presentation": "artifact__create_presentation",
            "document": "artifact__create_document",
            "spreadsheet": "artifact__create_spreadsheet",
            "pdf": "artifact__create_pdf",
            "diagram": "artifact__create_diagram",
            "3d": "artifact__create_3d_model",
            "openscad": "artifact__create_openscad_model",
            "pcb": "artifact__create_kicad_pcb",
            "schematic": "artifact__create_kicad_schematic",
            "audio": "artifact__create_audio_tone",
        }
        tool = tool_by_kind[kind]
        mcp = self._mcp()
        if mcp is None or tool not in mcp.names():
            return None
        output = self._artifact_output(request, kind)
        title = self._artifact_title(request, kind)
        notes = ["Requested deliverable", title,
                 "Created locally by IGRIS and verified before this response."]
        args: dict = {"output": output}
        if kind == "presentation":
            args.update({"title": title, "slides": [
                {"title": title, "bullets": ["Requested deliverable", "Created and verified locally"]},
                {"title": "Key points", "bullets": [title, "Use the source request as the scope"]},
                {"title": "Delivery", "bullets": ["PPTX saved in the IGRIS workspace", "Artifact validation passed"]},
            ]})
        elif kind in ("document", "pdf"):
            args.update({"title": title, "paragraphs": notes})
        elif kind == "spreadsheet":
            args.update({"sheet_name": "IGRIS Data", "rows": [["Item", "Details"],
                                                                  ["Request", title],
                                                                  ["Status", "Created and verified"]]})
        elif kind == "diagram":
            args.update({"title": title, "nodes": ["Request", "Create", "Validate", "Deliver"],
                         "edges": ["Request -> Create", "Create -> Validate", "Validate -> Deliver"]})
        elif kind == "3d":
            args.update({"shape": "cube", "size_mm": 20})
        elif kind == "openscad":
            args.update({"source": "// Generated by IGRIS\n$fn = 48;\ncube([20, 20, 20], center=true);\n"})
        elif kind == "pcb":
            args.update({"title": title, "components": ["R1 10k", "C1 100nF"]})
        elif kind == "schematic":
            args.update({"title": title, "components": ["R1 10k", "C1 100nF"]})
        elif kind == "audio":
            args.update({"text": title, "seconds": 2.0, "frequency_hz": 440.0})
        if progress is not None:
            try:
                progress("edit", f"{tool} -> {output}")
            except Exception:
                pass
        created = self._execute_chat_tool(tool, args)
        if not created.get("ok"):
            return None
        created_text = str(created.get("output") or "")
        saved = re.search(r"artifact saved to\s+(.+?)\s+\(", created_text)
        if not saved:
            return None
        absolute_path = saved.group(1).strip()
        validation = self._execute_chat_tool("artifact__validate_artifact", {"path": absolute_path})
        validation_text = str(validation.get("output") or "")
        if not validation.get("ok") or "validation passed" not in validation_text.lower():
            return None
        try:
            relative_path = os.path.relpath(absolute_path, self._chat_executor().workspace.root)
            if relative_path.startswith(".."):
                return None
            relative_path = relative_path.replace(os.sep, "/")
        except (ValueError, OSError):
            return None
        if progress is not None:
            try:
                progress("review", f"validated: {relative_path}")
            except Exception:
                pass
        return {
            "content": f"Tayyor: `{relative_path}` haqiqatan yaratildi va tekshiruvdan o'tdi.",
            "tool_calls": [
                {"tool": tool, "args": args,
                 "result": {k: v for k, v in created.items() if k != "output"},
                 "output_preview": created_text[:300]},
                {"tool": "artifact__validate_artifact", "args": {"path": relative_path},
                 "result": {k: v for k, v in validation.items() if k != "output"},
                 "output_preview": validation_text[:300]},
            ],
        }

    # ------------------------------------------------------------------ #
    # DETERMINISTIC CODE FALLBACK — LLM rad etganda avtomatik kod generatsiya
    # ------------------------------------------------------------------ #

    # Kod/yaratish vazifalari kalit so'zlari — fallback qachon ishlatilishini
    # aniqlash uchun. Bu so'zlar so'rovda bo'lsa, LLM tool chaqirmagan
    # bo'lsa ham avtomatik kod generatsiya qilinadi.
    _CODE_FALLBACK_KEYWORDS = (
        "fayl", "file", "yoz", "write", "yarat", "create", "qur",
        "build", "dastur", "code", "kod", "app", "ilova", "game",
        "o'yin", "html", "python", "javascript", "js", "css",
        "script", "skript", "faylni", "daftar", "note",
    )

    def _needs_code_fallback(self, request: str) -> bool:
        """So'rov kod/fayl yaratish talab qiladimi — deterministik tekshiruv.

        Agar so'rovda kod/fayl/yaratish kalit so'zlari bo'lsa va LLM
        hech qanday tool chaqirmagan bo'lsa — fallback ishga tushadi.
        """
        low = (request or "").lower()
        return any(kw in low for kw in self._CODE_FALLBACK_KEYWORDS)

    def _deterministic_code_fallback(
        self, request: str, original: str, progress=None
    ) -> Optional[dict]:
        """LLM rad etganda — LLM'dan kod so'rab, write_file bilan yozadi.

        Bu fallback faqat BIR marta ishlaydi (cheksiz loop yo'q).
        Natija: {content, tool, args, output} yoki None.
        """
        if self.llm is None or not self.llm_available():
            return None
        if progress is not None:
            try:
                progress("edit", "deterministic fallback: kod generatsiya qilinmoqda…")
            except Exception:
                pass
        # LLM'dan to'liq kod so'raymiz (tool-call emas, oddiy matn javob)
        fb_system = (
            "You are a coding agent. The user asked you to do something that "
            "requires writing a file. Generate the COMPLETE file content and "
            "output it as plain text (no markdown fences, just raw code). "
            "The file should be self-contained and working. "
            "After the code, on a NEW LINE starting with 'FILE:', write the "
            "suggested filename (e.g. 'FILE: index.html' or 'FILE: app.py'). "
            "Language: match the user's request (Uzbek = general code; "
            "English = match keywords like python/javascript/html)."
        )
        try:
            text = self.llm.complete(system=fb_system, prompt=request[:800])
        except Exception:
            return None
        if not text or len(text.strip()) < 30:
            return None
        # FILE: tegini topish — fayl nomini ajratamiz
        fname = ""
        code = text.strip()
        for line in text.strip().splitlines():
            if line.strip().upper().startswith("FILE:"):
                fname = line.strip()[5:].strip().strip('"').strip("'")
                # FILE: qatorini koddan olib tashlaymiz
                code = text.strip().replace(line, "", 1).strip()
                break
        if not fname:
            # Fallback fayl nomi — so'rov turiga qarab
            low = (original or "").lower()
            if any(w in low for w in ("html", "web", "saifa", "page")):
                fname = "index.html"
            elif any(w in low for w in ("python", ".py", "skript")):
                fname = "app.py"
            elif any(w in low for w in ("js", "javascript")):
                fname = "app.js"
            elif any(w in low for w in ("css", "style")):
                fname = "style.css"
            elif any(w in low for w in ("game", "o'yin")):
                fname = "game.html"
            elif any(w in low for w in ("todo", "vazifa", "task")):
                fname = "todo.html"
            else:
                fname = "output.html"
        # write_file orqali yozamiz
        res = self._execute_chat_tool("write_file", {
            "path": fname, "content": code,
        })
        if not res.get("ok"):
            return None
        # Xulosa — foydalanuvchiga nima qilganini tushuntiramiz
        summary = (
            f"Fayl yaratildi: `{fname}` — LLM tomonidan avtomatik generatsiya qilindi. "
            f"{len(code)} belgi, {len(code.splitlines())} qator kod."
        )
        if progress is not None:
            try:
                progress("review", f"fayl yaratildi: {fname}")
            except Exception:
                pass
        return {
            "content": summary,
            "tool": "write_file",
            "args": {"path": fname, "content": code[:200]},
            "output": res.get("output", ""),
        }

    def _chat_with_redraw(self, messages: list[dict], tools: list[dict],
                          web: bool = False, progress=None,
                          request: str = "",
                          req: Optional[Requirement] = None,
                          on_loop_iteration=None,
                          max_rounds=None, loop_shape=None,
                          ) -> tuple[str, list[dict], Optional[str], Optional[dict]]:
        """Chizish natijasini baholaydi; past ball bo'lsa tanqid bilan qayta chiztiradi.

        Research asosidagi self-correction (Render-and-Verify / Retry-Loop):
        birinchi chizma REDRAW_SCORE_MIN dan past ball olsa, tanqid xabari
        (score + zaifliklar + taklif) keyingi so'rovga qo'shiladi va yangi
        chizma olinadi. Ikkisidan YAXSHIROG'I saqlanadi. Latensiya uchun
        chegara: faqat BIR marta qayta chizish.

        Qaytadi: (content, tool_calls, image, redraw_note | None)
        redraw_note: {'retried', 'old_score', 'new_score', 'kept_old'?, 'failed'?}
        """
        content, tool_calls, image = self._chat_with_tools(
            messages, tools, web=web, progress=progress, req=req,
            on_loop_iteration=on_loop_iteration,
            max_rounds=max_rounds, loop_shape=loop_shape)
        if (not image or not str(image).lower().endswith(".svg")
                or not self._is_draw_request(request)):
            return content, tool_calls, image, None
        report = self._validate_drawing(image)
        if report is None or report.get("error"):
            return content, tool_calls, image, None
        old_score = report.get("total") or 0
        if old_score >= self.REDRAW_SCORE_MIN:
            return content, tool_calls, image, None
        # Tanqid bilan qayta chizish (bir marta)
        weak = [c.get("name") for c in report.get("checks") or [] if not c.get("ok")]
        tip = _drawing_quality_tip(report)
        # Original so'rov tanqidga qo'shiladi — ikkinchi o'tishda
        # _save_svg_from_text uslub/o'lchamni to'g'ri aniqlay oladi.
        critique = (
            f"Original request: {request}\n"
            f"Your previous drawing scored only {old_score}/100. "
            f"Weak points: {', '.join(weak) if weak else 'general quality'}. "
            f"Improve it: {tip or 'follow the svg-artist skill rules'}. "
            "Regenerate the FULL SVG via art__draw_custom_svg with a NEW filename, "
            "fixing every listed weakness (keep the same subject)."
        )
        messages2 = list(messages) + [{"role": "user", "content": critique}]
        # build_verify loop_iteration: qayta chizish urinishi
        if on_loop_iteration is not None:
            try:
                on_loop_iteration(2, 2, loop_shape or "build_verify")
            except Exception:
                pass
        content2, tool_calls2, image2 = self._chat_with_tools(
            messages2, tools, web=web, progress=progress, req=req,
            on_loop_iteration=on_loop_iteration,
            max_rounds=max_rounds, loop_shape=loop_shape)
        if not image2 or not str(image2).lower().endswith(".svg"):
            # qayta chizish muvaffaqiyatsiz — birinchi natija qoladi
            return content, tool_calls, image, {
                "retried": True, "old_score": old_score, "new_score": None,
                "failed": True}
        report2 = self._validate_drawing(image2)
        new_score = (report2 or {}).get("total") or 0
        note: dict = {"retried": True, "old_score": old_score, "new_score": new_score}
        if new_score >= old_score:
            return content2 or content, tool_calls2 or tool_calls, image2, note
        # eski chizma hali ham yaxshiroq — u qoladi (yangisi xotirada allaqachon)
        note["kept_old"] = True
        return content, tool_calls, image, note

    # ------------------------------------------------------------ #
    # ACTION EVIDENCE — "qildim" da'vosini isbotlash (anti-hallucination)
    # ------------------------------------------------------------ #

    def _enforce_action_evidence(self, messages: list[dict], tools: list[dict],
                                 content: str, tool_calls: list[dict],
                                 image: Optional[str], *, need: str = "",
                                 progress=None, request: str = "",
                                 req: Optional[Requirement] = None,
                                 web: bool = False,
                                 on_loop_iteration=None,
                                 max_rounds=None, loop_shape=None) -> tuple:
        """Javobda "amal bajarildi" da'vosi ISBOTI tekshiriladi.

        Real holat (chat_history.jsonl): model toolsiz "Fayl yaratildi:
        mini_snake_game.py" deb yozardi — fayl yo'q, ish qilinmagan.

        Tartib:
          1. isbot bormi? (tool_calls / image / workspace'da fayl) → o'tkaz
          2. yo'q → BIR marta majburlash (nudge): model haqiqatan tool
             chaqirib bajaradi → isbot paydo bo'ladi
          3. hali isbot yo'q → da'vo o'rniga HALOL ogohlantirish

        Qaytaradi: (content, tool_calls, image, evidence_note | None)
        evidence_note: {'claim': str, 'status': executed|rephrased|corrected}
        """
        try:
            from agent.action_evidence import (evaluate, honest_rewrite,
                                               nudge_message)
        except Exception:
            return content, tool_calls, image, None
        creator = need in getattr(request_classifier, "CREATOR_NEEDS", set())
        try:
            ok, reason = evaluate(
                content, tool_calls, image,
                getattr(self, "workspace_root", None) or DEFAULT_WORKSPACE,
                allow_promise=creator)
        except Exception:
            return content, tool_calls, image, None
        if ok:
            return content, tool_calls, image, None
        # --- 2-qadam: BIR marta haqiqiy bajarishga majburlash ---
        if self.llm_available() and tools:
            try:
                messages2 = list(messages or []) + [
                    {"role": "user", "content": nudge_message(reason)}]
                c2, tc2, img2, _note = self._chat_with_redraw(
                    messages2, tools, web=web, progress=progress,
                    request=request, req=req,
                    on_loop_iteration=on_loop_iteration,
                    max_rounds=max_rounds, loop_shape=loop_shape)
                merged = list(tool_calls or []) + list(tc2 or [])
                img = img2 or image
                ok2, reason2 = evaluate(
                    c2, merged, img,
                    getattr(self, "workspace_root", None) or DEFAULT_WORKSPACE,
                    allow_promise=creator)
                if ok2:
                    status = "executed" if (tc2 or img2) else "rephrased"
                    return (c2 or content), merged, img, {
                        "claim": reason, "status": status}
                # isbot hamon yo'q — halol qayta yozamiz
                return honest_rewrite(c2 or content, reason2), merged, img, {
                    "claim": reason, "status": "corrected"}
            except Exception as exc:
                print(f"[igris][evidence] nudge failed: {exc}")
        # --- 3-qadam: isbot yo'q — da'vo o'rniga halol ogohlantirish ---
        return honest_rewrite(content, reason), tool_calls, image, {
            "claim": reason, "status": "corrected"}

    def _draw_skill_text(self) -> str:
        """svg-artist skill ko'rsatmasini yuklaydi (bir marta, keshda).

        Chizish so'rovlarida system prompt'ga avtomatik qo'shiladi — model
        professional SVG (gradient, soya, qatlamlar, palitra) yaratishi uchun.
        Skill topilmasa bo'sh qaytaradi (agent ishlayveradi, shunchaki
        ko'rsatmasiz).
        """
        if self._draw_skill_cache is None:
            try:
                from skills import DEFAULT_MANAGER
                skill = DEFAULT_MANAGER.get("svg-artist")
                self._draw_skill_cache = skill.full_text() if skill else ""
            except Exception:
                self._draw_skill_cache = ""
        return self._draw_skill_cache

    def _draw_feedback_context(self) -> str:
        """L2 xotiradagi so'nggi CHIZMA SIFATI yozuvlaridan ixcham feedback bloki.

        Chizish so'rovlarida system prompt'ga qo'shiladi (RAG recall'ga
        tayanmasdan) — model avvalgi chizmalaridagi xatolarini ko'radi va
        takrorlamaydi: so'nggi 3 yozuv + eng ko'p takrorlangan 3 zaiflik.
        Parslash svg_quality_report.parse_quality_entry orqali (taklif qismi
        zaifliklar ro'yxatiga aralashmaydi). Xotira bo'lmasa '' qaytaradi.
        """
        try:
            base = getattr(self.memory, "base_dir", "")
            if not base:
                return ""
            from verification.svg_quality_report import build_report, load_quality_entries
            entries = load_quality_entries(base)
            if not entries:
                return ""
            report = build_report(entries)
            weak_hist = report.get("weak_histogram") or {}
            out = [
                "RECENT DRAWING QUALITY FEEDBACK (past drawings — do NOT repeat these mistakes):"
            ]
            for e in (report.get("recent") or [])[-3:]:
                weak = ", ".join(e["weak"]) if e["weak"] else "yo'q"
                out.append(f"- {e['file']} ({e['style']}): score {e['score']}/100, "
                           f"zaif: {weak}")
            if weak_hist:
                top = list(weak_hist.items())[:3]
                out.append("Most recurring weaknesses: "
                           + ", ".join(f"{w} ({n}x)" for w, n in top))
            out.append("Fix these issues in the drawing you generate now.")
            return "\n".join(out)[:900]
        except Exception:
            return ""

    def _remember_drawing_quality(self, image: Optional[str], request: str) -> None:
        """Chizma faylini svg_validator bilan baholab, natijani L2 xotiraga yozadi.

        Keyingi chizish so'rovlarida RAG recall bu feedback'ni kontekstga
        qo'shadi — model oldingi xatolarini takrorlamaydi (gradient/soya/
        kompozitsiya/palitra). Xato yoki fayl topilmasa indamay o'tadi
        (agent ishlashini hech qachon buzmaydi).
        """
        if not image or not str(image).lower().endswith(".svg"):
            return
        if not (self.memory and self.memory.enabled):
            return
        r = self._validate_drawing(image)
        if r is None or r.get("error") or not r.get("total"):
            return
        s = r.get("scores") or {}
        meta = r.get("meta") or {}
        weak = [c.get("name") for c in r.get("checks") or [] if not c.get("ok")]
        total = r.get("total") or 0
        style = meta.get("style_comment") or "cartoon"
        weak_str = ", ".join(weak) if weak else "yo'q"
        content = (
            f"CHIZMA SIFATI (svg_validator auto-assessment): "
            f"prompt='{str(request)[:120]}' | file={image} | "
            f"viewBox={meta.get('viewBox')} | style={style} | "
            f"size={meta.get('size_comment') or 'standard'} | "
            f"score={total}/100 ({r.get('verdict')}) | "
            f"structure={s.get('structure', 0)} composition={s.get('composition', 0)} "
            f"style={s.get('style', 0)} palette={s.get('palette', 0)} | "
            "zaif jihatlar: " + weak_str
        )
        tip = _drawing_quality_tip(r)
        if tip:
            content += " | taklif: " + tip
        try:
            self.memory.remember(
                content[:2000],
                memory_type="solution-memory",
                tags=["drawing", "svg-quality", style, "score-" + str(total // 10 * 10)],
                summary="SVG chizma sifati: " + str(total) + "/100 (" + str(image) + ")",
            )
        except Exception:
            pass  # xotira xatosi agentni buzmaydi

    def _last_chance_draw(self, request: str) -> tuple[str, Optional[str]]:
        """Rad etishdan OLDINGI OXIRGI chizish urinishi (LLM cheklovini yopish).

        Asosiy tool-loop'da model tool chaqirmadi yoki bo'sh qaytardi — odatda
        bu yerda halol refusal berilardi. Buning o'rniga BIR marta sodda va
        aniq buyruq bilan to'liq SVG generatsiya qildiramiz va natijani
        art__draw_custom_svg orqali faylga yozamiz (junk-guard: `<svg>` yo'q
        bo'lsa darhol voz kechamiz — soxta "chizdim" yo'q).

        Qaytadi: (javob_matni, image_relative_path) yoki ("", None).
        """
        if self.llm is None or not self.llm_available():
            return "", None
        subject = self._detect_subject(request, "draw") or str(request)[:60]
        style = self._draw_style_from_request(request)
        size = self._draw_size_from_request(request)
        system = (
            "You are Igris, an SVG artist. Generate ONE complete, valid SVG "
            "document for the user's subject. Rules: viewBox=\"0 0 512 512\", "
            "soft background rect first, layered shapes (outline -> body -> "
            "details -> highlights -> shadows), coherent palette. "
            f"Style: {style}. Subject: {subject}. "
            "Output ONLY the raw <svg>...</svg> markup — no text, no "
            "explanations, no markdown fences."
        )
        try:
            text = self.llm.complete(system=system, prompt=str(request)[:400])
        except Exception:
            return "", None
        if not text or "<svg" not in str(text).lower():
            return "", None
        found = self._extract_svg(text)
        if not found:
            return "", None
        svg_text, fname = found
        try:
            res = self._execute_chat_tool("art__draw_custom_svg",
                                          {"svg": svg_text, "output": fname,
                                           "style": style, "size": size})
        except Exception:
            return "", None
        if not res.get("ok"):
            return "", None
        img = self._image_from_art_call(res)
        if not img:
            return "", None
        # SIFAT ESHIGI (AUDIT): last-chance SVG junk bo'lsa (masalan bitta
        # bo'sh kvadrat) — foydalanuvchiga yetkazmaymiz. svg_validator balli
        # juda past bo'lsa (REDRAW_SCORE_MIN dan ham past) — fayl bor, lekin
        # javob bermaymiz (yuqori qatlam halol refusal beradi).
        report = self._validate_drawing(img)
        if report is not None and not report.get("error"):
            score = report.get("total") or 0
            if score < self.REDRAW_SCORE_MIN:
                return "", None
        # Sifatni baholab L2 xotiraga yozamiz (keyingi chizishlar uchun)
        self._remember_drawing_quality(img, request)
        return f"Chizdim: `{img}` — rasm tayyor.", img

    @staticmethod
    def _fake_draw_claim(text: str) -> bool:
        """Soxta "Chizdim ... rasm tayyor" — model rasmini CHIZMAGAN, faqat
        aytgan. HAQIQIY deb faqat `<svg>` markup yoki `art__draw` tool
        chaqiruvi hisoblanadi — fayl nomidagi `.svg` so'zi YO'Q (model yolg'on
        aytishi mumkin)."""
        low = (text or "").lower()
        has_draw_word = any(
            re.search(rf"\b{re.escape(k)}\b", low) if " " not in k else k in low
            for k in (
                "chizdim", "rasm tayyor", "chizib berdim", "drew",
                "drawing saved", "created the drawing", "image saved"))
        has_actual = ("<svg" in low or "art__draw" in low)
        return has_draw_word and not has_actual

    def _try_deterministic_scene(self, request: str, progress=None) -> Optional[dict]:
        """Ma'lum (canned) subject uchun ANIQ, deterministik chizma — crashsiz.

        Talabdan subject/rang aniqlanadi va `art__draw_scene_svg` deterministik
        chaqiriladi — modelga bog'liq emas (kuchsiz model xom yoki soxta
        "Chizdim" SVG yozib talabni buzmasin). Subject ma'lum bo'lmasa None
        qaytadi — LLM generatsiya qiladi.

        Qaytadi: {'content', 'image', 'tool', 'args', 'result'} yoki None.
        """
        if not self._is_draw_request(request):
            return None
        subj = self._detect_subject(request, "draw")
        if not subj or subj not in self.CANNED_SCENE_SUBJECTS:
            return None
        color = self._draw_color_from_request(request) or "red"
        # Part O: uslub va o'lcham ham talabdan — natija so'rovga mos real ko'rinish
        style = self._draw_style_from_request(request)
        size = self._draw_size_from_request(request)
        try:
            # Millisekund — tez ketma-ket chizmalar bir-birini ustiga yozmasligi
            # (bir xil subject bir soniyada 2 marta so'ralsa fayl to'qnashuv yo'q).
            fname = f"{subj}_{int(time.time() * 1000)}.svg"
            res = self._execute_chat_tool("art__draw_scene_svg", {
                "subject": subj, "output": fname, "color": color,
                "texture": "none", "style": style, "size": size,
            })
            if not res.get("ok"):
                return None
            img = self._image_from_art_call(res)
            if not img:
                return None
            # Sifatni baholab L2 xotiraga yozamiz (keyingi chizishlar uchun)
            self._remember_drawing_quality(img, request)
            if progress is not None:
                try:
                    progress("edit", f"art__draw_scene_svg → {subj}")
                except Exception:
                    pass
            return {
                "content": f"Chizdim: `{img}` — rasm tayyor ({subj}, {color}, "
                           f"{style}, {size}).",
                "image": img,
                "tool": "art__draw_scene_svg",
                "args": {"subject": subj, "output": fname, "color": color,
                         "texture": "none", "style": style, "size": size},
                "result": res,
            }
        except Exception:
            return None

    def _save_svg_from_text(self, content: str, tool_calls: list[dict],
                            image: Optional[str],
                            request: str) -> tuple[str, Optional[str]]:
        """Model javobida SVG kodi bo'lsa — art__draw_custom_svg orqali faylga yozadi.

        Model ba'zan tool chaqirmasdan SVG'ni matn sifatida yozadi — bunday
        javobni REAL chizma fayliga aylantiramiz (frontend karta ko'rsatadi)
        va "fayl yaratdim" deb yolg'on aytilishini oldini olamiz. Faqat
        chizish so'rovi bo'lsa ishlaydi (tasodifiy kod misollarini rasmga
        aylantirmaydi). `request` — ORIGINAL foydalanuvchi so'rovi (nudge
        xabarlari emas).

        Qaytadi: (yangi_javob, image_path)
        """
        if image:
            return content, image
        if not self._is_draw_request(request):
            return content, image
        try:
            found = self._extract_svg(content)
        except Exception:
            found = None
        if not found:
            # Part O: soxta "Chizdim ... rasm tayyor" (model rasmini chizmagan,
            # shunchaki aytgan) — muvaffaqiyat deb YO'Q, retry oqimiga qaytamiz.
            lowc = (content or "").lower()
            if image is None and any(k in lowc for k in (
                    "chizdim", "rasm tayyor", "chizib berdim", "drawing saved",
                    "drew", "i created the drawing", "saved as")):
                return "", image
            # Part O: to'liq bo'lmagan/haddan tashqari katta SVG bo'lagi (model
            # "chizdi" deb yozgan lekin noto'g'ri/malformatted) — junk'ni javob
            # sifatida qaytarmaymiz (crashsiz, tez halol holat).
            if image is None and len(content or "") > 1500 and (
                    "<svg" in lowc or "<path" in lowc or "stroke=" in lowc):
                return "", image
            return content, image
        svg_text, fname = found
        # So'rovda uslub/o'lcham aytilgan bo'lsa — argument'larga uzatamiz
        style = self._draw_style_from_request(request)
        size = self._draw_size_from_request(request)
        res = self._execute_chat_tool("art__draw_custom_svg",
                                      {"svg": svg_text, "output": fname,
                                       "style": style, "size": size})
        if not res.get("ok"):
            return content, image
        img = self._image_from_art_call(res)
        if not img:
            return content, image
        # Sifatni avtomatik baholab L2 xotiraga yozamiz (keyingi chizishlar uchun)
        self._remember_drawing_quality(img, request)
        tool_calls.append({
            "tool": "art__draw_custom_svg",
            "args": {"svg": svg_text[:120], "output": fname,
                     "style": style, "size": size},
            "result": {k: v for k, v in res.items() if k != "output"},
            "output_preview": str(res.get("output") or "")[:300],
        })
        # Javobni qisqa xulosaga almashtiramiz — kod dumi ko'rinmaydi
        return f"Chizdim: `{img}` — rasm tayyor (fayl: {fname}).", img

    def _tools_hint(self, request: str = "") -> str:
        """Capability-gap re-prompt: modelga real imkoniyatlar ro'yxati.

        `request` berilsa — WEB qo'llanma faqat web so'rovida qo'shiladi
        (aks holda rasm/kod vazifasida 3KB browser shovqini bo'lardi; model
        toolsetida web tool'lar ham faqat o'shanda bor).
        """
        parts = [
            "Do NOT give up - you have real capabilities and real tools. "
            "You CAN draw ANY image: YOU are the artist — generate the SVG markup "
            "yourself and save it with art__draw_custom_svg (args: svg='<full "
            "<svg>...</svg> markup>', output='duck.svg', "
            "style='cartoon|child|bw|fantasy|anime|realistic|flat', "
            "size='standard|icon|avatar|card|poster|banner'). There is NO fixed "
            "subject list. You may also use the quick canned tools: "
            "art__draw_scene_svg (subject, output, color, texture) for objects "
            "(apple, house, tree, cat, star, heart, car, rocket, flower, mountain, "
            "sun, moon, bird, fish, butterfly, mushroom, ball - Uzbek: olma, uy, "
            "daraxt, mushuk, quyosh, oy, qush, baliq, kapalak, to'p...) or "
            "art__draw_ui_svg (app, output, theme, texture) for UI/UX mockups. "
            "For a REAL working "
            "UI screen that is BUILT step by step (background, sections, sidebar "
            "with working toggle, content, a button that opens a window, the "
            "window with its shape/color first then its inner sketch), call "
            "art__ui_build_spec (app, output, theme). For a TODO/TASK LIST app "
            "(add/complete/delete/filter tasks, saved in localStorage), call "
            "art__ui_build_spec (app='todo', output='todo.uibuild.json', theme) "
            "- it is fully interactive, more powerful than a plain todo demo. "
            "ui_build_spec output must end in .uibuild.json.",
        ]
        mcp = self._mcp()
        if mcp is not None:
            art_names = [k for k in mcp.names() if k.startswith("art__")]
            if art_names:
                parts.append("Draw tools available to you: " + ", ".join(art_names))
            # WEB qo'llanma faqat web so'rovida — model toolsetida web tool'lar
            # ham faqat o'shanda bor (mcp_call ulardan tozalangan).
            if request and self._web_strategy(request):
                web_names = [k for k in mcp.names() if k.startswith("web_ai_bridge__")]
                if web_names:
                    parts.append(
                        "WEB DECISION RULES — use the CHEAPEST tool that answers:\n"
                        "1. Answer directly from your own knowledge — no tools.\n"
                        "2. web_fetch(url) reads static page text over HTTP — no browser.\n"
                        "3. ask_web_ai / web_ai_start_research to DELEGATE research and "
                        "knowledge questions to a web AI (chatgpt/gemini/claude_web/"
                        "deepseek) as a SUBAGENT — the web AI does the browsing for you.\n"
                        "4. Browser tools ONLY for interactive pages (accounts, forms, "
                        "logins, JS-heavy apps, exact live state).\n"
                        + WEB_TOOLS_GUIDE
                    )
        parts.append(
            "Fast direct tools (no browser): web_fetch(url) reads a page's text "
            "over HTTP, web_search_image(query) finds and downloads an image."
        )
        reg = self._registry()
        if reg is not None:
            parts.append("File/terminal tools: " + ", ".join(reg.names()))
        parts.append(
            "Use ONLY the tools listed above (they are the ones available to you "
            "in this chat). Continue the user's task now using the appropriate tool."
        )
        return "\n".join(parts)

    def _capability_gap(self, text: str) -> bool:
        """Model 'qila olmayman' kabi rad javobini aniqlaydi."""
        try:
            from executor.executor import CAPABILITY_GAP_PATTERNS
            return bool(CAPABILITY_GAP_PATTERNS.search(text or ""))
        except Exception:
            return False

    def _execute_chat_tool(self, name: str, args: dict) -> dict:
        """Chatdagi tool'ni executor orqali bajaradi (MCP + registry + vision + smart_build)."""
        # Vision tools — alohida tekshiramiz
        if name.startswith("vision_"):
            return self._execute_vision_tool(name, args)
        # Smart Build tools — alohida tekshiramiz
        if name.startswith("smart_build_"):
            return self._execute_smart_build_tool(name, args)
        ex = self._chat_executor()
        if ex is None:
            return {"ok": False, "error": "tools unavailable"}
        try:
            return ex._execute_agent_tool(name, args)
        except Exception as exc:
            return {"ok": False, "error": f"{name} raised: {exc}"}

    def _image_from_art_call(self, result: dict) -> Optional[str]:
        """art__draw_object_png natijasidan workspace'ga nisbatan fayl yo'lini oladi."""
        out = str(result.get("output") or "")
        m = re.search(r"image saved to\s+(.+?)\s*$", out)
        if not m:
            return None
        abs_path = m.group(1).strip()
        try:
            root = os.path.normpath(self._chat_executor().workspace.root)
            rel = os.path.relpath(abs_path, root)
        except (ValueError, OSError):
            return None
        if rel.startswith(".."):
            return None
        return rel.replace(os.sep, "/")

    def active_chains(self, res: Resolution) -> list[str]:
        """Map matched rules back to their owning chains."""
        active = set()
        for rule_name in res.matched_rules:
            for chain in self.chains.chains.values():
                if chain.matches(rule_name):
                    active.add(chain.name)
        return sorted(active)

    # ------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------ #

    def status(self) -> dict:
        st = {
            "bricks": self.bricks.stats(),
            "knowledge": self.knowledge.stats(),
            "chains": {name: c.to_dict() for name, c in self.chains.chains.items()},
            "llm": {
                "enabled": self.use_llm,
                "model": self.llm.model,
                "available": self.llm_available(),
                **self.speed_status(),
            },
            "memory": self.memory.status(),
        }
        cache = self._cag()
        if cache is not None:
            st["cag"] = cache.status()
        mag = self._mag()
        if mag is not None:
            st["mag"] = {"enabled": self.memory.enabled,
                          "session_id": mag.session_id}
        try:
            from monitor.hooks import DEFAULT_BUS
            st["hooks"] = DEFAULT_BUS.stats()
        except Exception:
            pass
        # INTELLEKT qatlami (BuildIntalaganceInstructionRequest.md) — 10 modul holati
        try:
            st["intelligence"] = self.intelligence.status()
        except Exception:
            pass
        # Smart Build Engine v2 — Weak LLM + Strong Cognitive Infrastructure
        if self.smart_build_engine:
            try:
                st["smart_build"] = self.smart_build_engine.get_status()
            except Exception:
                pass
        # Chat Stream Aggregator — micro-actions → semantic actions
        if self._chat_stream_agg:
            st["chat_stream"] = {
                "active_streams": len(self._chat_stream_agg._streams),
                "current_stream": self._chat_stream_agg._current_stream.task if self._chat_stream_agg._current_stream else None,
            }
        return st

    # ------------------------------------------------------------ #
    # Heal report helper
    # ------------------------------------------------------------ #

    def heal_report(self, missing_chain: str) -> dict:
        return self.healer.heal_report(missing_chain)


# ---------------------------------------------------------------- #
# CLI
# ---------------------------------------------------------------- #


def _safe_print(text: str) -> None:
    """Print, tolerating consoles that cannot encode unicode (e.g. cp1252)."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    agent = IgrisAgent(use_llm="--no-llm" not in argv)

    _safe_print("IGRIS CODER AGENT - hybrid (bricks + RAG memory + Ollama)")
    _safe_print("Status: OK   Chains: " + str(list(agent.chains.chains.keys())))
    _safe_print("LLM: " + (agent.llm.model if agent.use_llm else "disabled")
                + (" (available)" if agent.llm_available() else " (offline)"))
    _safe_print("Memory: " + ("enabled" if agent.memory.enabled else "disabled"))
    _safe_print("Commands: query | chat <msg> | status | heal <chain> | standards | refactor | telemetry | assess <q> | memory | exit")
    _safe_print("-" * 56)

    while True:
        try:
            query = input("Query: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not query:
            continue
        if query in ("exit", "quit", "q"):
            if agent.memory.enabled:
                agent.memory.end_session("cli exit")
            return 0
        if query == "status":
            _safe_print(str(agent.status()))
            continue
        if query.startswith("heal "):
            _safe_print(str(agent.heal_report(query[5:].strip())))
            continue
        if query.startswith("chat "):
            res = agent.chat(query[5:].strip())
            _safe_print(f"Engine: {res['engine']}   {res['duration_ms']:.0f}ms   mem_hits={res['memory']['recall_hits']}")
            _safe_print(f"Output:\n{res['content']}")
            _safe_print("-" * 56)
            continue

        if query == "standards":
            _safe_print(agent.refactor.standards())
            continue
        if query == "refactor":
            import json
            _safe_print(json.dumps(agent.refactor.refactor_report(),
                                   ensure_ascii=False, indent=2))
            continue
        if query == "telemetry":
            _safe_print(str(agent.refactor.telemetry.stats()))
            continue
        if query == "memory":
            _safe_print(str(agent.memory.status()))
            continue
        if query.startswith("assess "):
            target = query[7:].strip()
            result = agent.refactor.evaluate_query(target)
            _safe_print(f"Query semantics: {result['query_semantics']}")
            if "resolution" in result:
                _safe_print(f"Resolution: {result['resolution']['status']} conf={result['resolution']['confidence']:.2f} engine={result['resolution'].get('engine')}")
                _safe_print(f"Output: {result['resolution']['output']}")
            _safe_print(f"Telemetry snapshot: {result.get('telemetry_snapshot')}")
            continue

        result = agent.resolve(query)
        _safe_print(f"Status: {'OK' if result['status'] == 'ok' else result['status']}")
        _safe_print(f"Confidence: {result['confidence']:.3f}")
        _safe_print(f"Engine: {result.get('engine', '?')}   Chains: {result.get('chains', [])}   {result.get('duration_ms', 0):.0f}ms")
        _safe_print(f"Output:\n{result['output']}")
        _safe_print(f"Trace: {result['trace']}")
        _safe_print("-" * 56)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
