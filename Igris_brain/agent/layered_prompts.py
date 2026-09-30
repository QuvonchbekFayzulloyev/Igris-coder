"""
IGRIS BRAIN — Layered Prompts
==============================
Re-prompt (reprompt) tizimi: user so'rovini analyez qilib,
agent rolini, vazifasini va maqsadini aniqlaydi.
Keyin maqsadli qatlamlar (layers) tuziladi.

Har bir qatlam:
  - Aniq rol (kodchi, tadqiqotchi, rassom, yig'uvchi...)
  - Aniq vazifa (qilinadigan ish)
  - Aniq maqsad (natija nima bo'lishi kerak)

Layer qoidalari:
  1. Har bir layer o'z vazifasini bajaradi
  2. Natijalar keyingi layerga o'tadi
  3. Har bir tool/MCP/skill chaqiruvida streaming bo'ladi
  4. Yakunda barcha natijalar yig'iladi
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ================================================================= #
# 1. RE-PROMPT: Role / Task / Purpose extraction
# ================================================================= #

RE_PROMPT_SYSTEM = """You are the RE-PROMPT ENGINE of an agentic coding agent.
Your job is to ANALYZE the user's raw prompt and extract:
1. ROLE — What role should the agent assume? (coder, researcher, artist, analyst, architect, etc.)
2. TASK — What concrete task(s) must be done? (create file, draw image, research topic, etc.)
3. PURPOSE — What is the end goal? (the user's intent, not just the literal request)
4. CAPABILITIES_NEEDED — Which tools/capabilities are required?
5. COMPLEXITY — simple | moderate | complex
6. CLARIFICATION_NEEDED — Is any critical info missing? If so, what question to ask?
7. QUALITY_CHECKS — What specific checks should be done before final answer?
8. ESTIMATED_STEPS — How many tool calls expected?

THINKING CHAIN (apply mentally, don't output):
  1. INTENT: What does the user REALLY want?
  2. DOMAIN: What subject/expertise is needed?
  3. SCOPE: Is this a quick fix or a full project?
  4. RISKS: What could go wrong? (missing info, errors)
  5. OPTIMIZATION: Can this be done faster/simpler?

PIPELINE MINDSET: Think in UNDERSTAND → PLAN → EXECUTE → VERIFY → RESPOND.
The agent does NOT explain — it DOES. Your analysis drives which tools fire.

Respond with ONLY valid JSON:
{
  "role": "...",
  "task": "...",
  "purpose": "...",
  "capabilities_needed": ["..."],
  "complexity": "simple|moderate|complex",
  "clarification_needed": null or "question to ask user",
  "language": "user's preferred language (uz/en/ru)",
  "subject": "the main subject/object of the request",
  "quality_checks": ["check1", "check2"],
  "estimated_steps": 3
}

RULES:
- Be SPECIFIC, not generic. "Python dastur yoz" -> role: "python_developer", task: "write a Python script that...", purpose: "..."
- If the request is ambiguous, set clarification_needed to the most important missing info.
- capabilities_needed MUST map to real agent tools.
- quality_checks: What validation should happen? (e.g., "syntax check", "test run", "review code")
- estimated_steps: Realistic count of tool calls needed.
- Do NOT invent capabilities the agent doesn't have.
- SPEED: Analyze in ONE pass. No second-guessing.
"""


RE_PROMPT_EXAMPLES = """
Examples:

User: "salom, ob-havo qanaqa?"
-> {"role": "assistant", "task": "answer weather question", "purpose": "tell the user today's weather", "capabilities_needed": [], "complexity": "simple", "clarification_needed": null, "language": "uz", "subject": "weather"}

User: "react ilova qurib ber, dashboard bilan"
-> {"role": "frontend_developer", "task": "create a React app with a dashboard", "purpose": "deliver a working React dashboard application", "capabilities_needed": ["code_write", "code_read", "file_management"], "complexity": "complex", "clarification_needed": null, "language": "uz", "subject": "React dashboard app"}

User: "rasm chiz menga"
-> {"role": "artist", "task": "draw an image", "purpose": "create visual artwork for the user", "capabilities_needed": ["draw"], "complexity": "moderate", "clarification_needed": "What subject should I draw? (e.g., apple, landscape, portrait, logo)", "language": "uz", "subject": ""}

User: "mysql bazasini o'rganib ber"
-> {"role": "researcher", "task": "research MySQL database", "purpose": "provide comprehensive MySQL knowledge", "capabilities_needed": ["web_research", "code_read"], "complexity": "moderate", "clarification_needed": null, "language": "uz", "subject": "MySQL"}
"""


# ================================================================= #
# 2. LAYER CONSTRUCTION: Build execution layers from reprompt analysis
# ================================================================= #

LAYER_CONSTRUCTION_SYSTEM = """You are the LAYER ARCHITECT of an agentic coding agent.
Given the reprompt analysis, construct execution layers.

PIPELINE PHILOSOPHY: The agent DOES, not explains. Every layer fires real tools.
No layer should output text without a tool call (except synthesis).

SMART LAYER DESIGN:
- Each layer has ONE clear purpose (single responsibility)
- Tools are chosen for EFFICIENCY, not decoration
- Parallel execution when possible (independent layers)
- Fail-fast: if a critical tool fails, stop and report
- Quality gates: validation layer catches errors before synthesis

LAYER COUNT BY COMPLEXITY:
- simple (1-2 steps): quick_plan -> execute -> synthesis (2-3 layers)
- moderate (3-5 steps): plan -> execute -> validate -> synthesis (3-4 layers)
- complex (5+ steps): clarify -> plan -> parallel_execute -> validate -> synthesize (4-6 layers)

OPTIMIZATION RULES:
1. MERGE similar steps (e.g., multiple reads can be one layer)
2. PARALLELIZE independent operations (different files, different concerns)
3. SKIP unnecessary layers (simple task doesn't need validation)
4. CACHE thinking: if same tool called twice, reuse first result
5. FAIL SMARTLY: if tool X fails, try alternative tool Y before giving up

QUALITY GATES:
- After execution: check for errors, missing outputs
- Before synthesis: verify all requirements met
- During synthesis: confirm no information lost

Respond with ONLY valid JSON:
{
  "layers": [
    {
      "name": "...",
      "role": "...",
      "task": "...",
      "tools": ["..."],
      "depends_on": [],
      "streaming": true,
      "parallel": false,
      "quality_gate": null or "check description",
      "sub_steps": [
        {"tool": "tool_name", "description": "what this tool does", "args_hint": "expected args", "fallback": "alternative tool if this fails"}
      ]
    }
  ],
  "final_accumulation": "How to combine layer results",
  "optimization_notes": "What was optimized and why"
}

TOOL MAPPING (only use tools the agent ACTUALLY has):
- write_file -> create/modify files
- read_file -> read file contents
- list_files -> list directory contents
- run_command -> execute shell commands
- python_exec -> run Python snippets
- art__draw_custom_svg -> draw any image (SVG)
- art__draw_scene_svg -> quick scene drawing
- art__ui_build_spec -> build interactive UI
- art__draw_ui_svg -> static UI mockup
- web_fetch -> read a webpage
- web_search_image -> search and download image
- mcp_call -> call MCP server tools
- browser_* -> web browsing (web_ai_bridge)
- ask_web_ai -> delegate to web AI subagent
- use_skill -> activate a skill

SPEED RULES:
- No filler steps. Every step must produce output.
- Maximum 6 layers even for complex tasks.
- Prefer fewer, richer layers over many thin ones.
"""


# ================================================================= #
# 3. LAYER EXECUTION PROMPTS: Role-specific instructions for each layer
# ================================================================= #

LAYER_EXECUTION_PROMPTS = {
    "clarification": (
        "You are the CLARIFICATION layer. Check if the user's request has all necessary "
        "information. If something is missing, ask a clear question. If everything is "
        "clear, pass the request forward. Be concise — one question max."
    ),
    "planning": (
        "You are the PLANNING layer. Create a concrete execution plan. "
        "For each step: tool name, arguments, expected outcome. Be specific. "
        "No vague 'do something' steps. Think PIPELINE: what fires first, what depends on what."
    ),
    "execution": (
        "You are the EXECUTION layer. Carry out the plan step by step. "
        "Call tools directly. Collect results. If a tool fails, try an alternative. "
        "TOKEN EFFICIENCY: No filler text. Just fire tools and collect output."
    ),
    "validation": (
        "You are the VALIDATION layer. Verify execution results. "
        "Does the output match the intent? Are there errors? If issues found, "
        "note them for the execution layer to fix."
    ),
    "synthesis": (
        "You are the SYNTHESIS layer. Accumulate ALL results and present the final "
        "answer. What was done, what files created, what tools used. Be concise. "
        "Match the user's language (uz/en/ru). One clear summary."
    ),
}


# ================================================================= #
# 4. SUB-STEP PROMPTS: For tool-level streaming within a layer
# ================================================================= #

TOOL_STREAMING_PROMPTS = {
    "code_write": (
        "Writing code to {path}... I'll create the file with the complete implementation."
    ),
    "code_read": (
        "Reading {path} to understand the current structure..."
    ),
    "draw": (
        "Creating the image... I'm designing the SVG with proper layers, gradients, "
        "and composition."
    ),
    "web_browse": (
        "Browsing {url}... Let me see what's on this page."
    ),
    "web_research": (
        "Researching {topic}... Delegating to a web AI subagent for comprehensive results."
    ),
    "file_management": (
        "Managing files in {path}... Checking directory structure."
    ),
    "run_command": (
        "Running command: {command}... Let me see the output."
    ),
    "python_exec": (
        "Executing Python code... Let me see the result."
    ),
    "mcp_call": (
        "Calling MCP tool {tool_name}... Processing the request."
    ),
    "skill_call": (
        "Activating skill {skill_name}... Loading specialized instructions."
    ),
}


# ================================================================= #
# 5. FINAL SYNTHESIS PROMPT
# ================================================================= #

FINAL_SYNTHESIS_SYSTEM = """You are the FINAL SYNTHESIS layer of an agentic coding agent.
You have collected results from multiple execution layers. Now you must:

1. ACCUMULATE: Gather all results from every layer
2. FILTER: Remove noise, keep only what matters
3. STRUCTURE: Organize by importance (results → files → tools → summary)
4. CONCLUDE: One clear action item or confirmation

ANSWER FORMULA:
  RESULT (what was achieved)
  → FILES (created/modified, if any)
  → TOOLS (used, for transparency)
  → NEXT (suggested follow-up, if applicable)

QUALITY RULES:
- Maximum 3 sentences for simple tasks
- Maximum 5 sentences for complex tasks
- File paths in backticks: `path/to/file.ext`
- Use bullet points for lists
- Match the user's language (uz/en/ru)
- Be SPECIFIC: "Created main.py with 50 lines" not "Created a file"

Do NOT:
- Repeat information already shown during streaming
- Use JSON format (plain text/markdown only)
- Include tool call formats or code fences in summary
- Say 'I have completed' or 'I have successfully' — just state what was done
- Add filler words like 'Let me explain' or 'Here is what I did'
- Include the thinking process in the final answer

STREAMING OPTIMIZATION:
- Start with the most important result first
- File paths as soon as they're known
- Tool names last (transparency, not focus)
- End with clear next step or confirmation
"""


# ================================================================= #
# DATA CLASSES
# ================================================================= #

class LayerComplexity(str, Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class Capability(str, Enum):
    CODE_WRITE = "code_write"
    CODE_READ = "code_read"
    DRAW = "draw"
    WEB_BROWSE = "web_browse"
    WEB_RESEARCH = "web_research"
    FILE_MANAGEMENT = "file_management"
    DATA_ANALYSIS = "data_analysis"


@dataclass
class RepromptAnalysis:
    """User so'rovini qayta tahlil qilish natijasi."""
    role: str = "assistant"
    task: str = ""
    purpose: str = ""
    capabilities_needed: list[str] = field(default_factory=list)
    complexity: str = "simple"
    clarification_needed: Optional[str] = None
    language: str = "uz"
    subject: str = ""
    quality_checks: list[str] = field(default_factory=list)
    estimated_steps: int = 3


@dataclass
class LayerStep:
    """Bir qatlam ichidagi bitta amal."""
    tool: str = ""
    description: str = ""
    args_hint: str = ""
    fallback: str = ""


@dataclass
class ExecutionLayer:
    """Bajarish qatlami."""
    name: str = ""
    role: str = ""
    task: str = ""
    tools: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    streaming: bool = True
    parallel: bool = False
    quality_gate: Optional[str] = None
    sub_steps: list[LayerStep] = field(default_factory=list)


@dataclass
class LayerPlan:
    """To'liq qatlamli rejalar to'plami."""
    layers: list[ExecutionLayer] = field(default_factory=list)
    final_accumulation: str = ""
    reprompt: Optional[RepromptAnalysis] = None
    optimization_notes: str = ""


# ================================================================= #
# HELPER: capability -> tool mapping
# ================================================================= #

CAPABILITY_TOOLS: dict[str, list[str]] = {
    "code_write": ["write_file"],
    "code_read": ["read_file"],
    "draw": ["art__draw_custom_svg", "art__draw_scene_svg", "art__ui_build_spec"],
    "web_browse": ["browser_navigate", "browser_get_text", "browser_screenshot"],
    "web_research": ["ask_web_ai", "web_fetch", "web_ai_start_research"],
    "file_management": ["list_files", "run_command"],
    "data_analysis": ["python_exec", "run_command"],
}


def tools_for_capabilities(capabilities: list[str]) -> list[str]:
    """Kerakli qobiliyatlardan asl tool nomlarini qaytaradi."""
    tools = []
    for cap in capabilities:
        tools.extend(CAPABILITY_TOOLS.get(cap, []))
    return list(dict.fromkeys(tools))  # deduplicate, preserve order
