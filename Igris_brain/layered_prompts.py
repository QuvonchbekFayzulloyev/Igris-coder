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

RE_PROMPT_SYSTEM = """You are the RE-PROMPT ENGINE of a layered coding agent.
Your job is to ANALYZE the user's raw prompt and extract:
1. ROLE — What role should the agent assume? (coder, researcher, artist, analyst, architect, etc.)
2. TASK — What concrete task(s) must be done? (create file, draw image, research topic, etc.)
3. PURPOSE — What is the end goal? (the user's intent, not just the literal request)
4. CAPABILITIES_NEEDED — Which tools/capabilities are required? (code_write, code_read, draw, web_browse, web_research, file_management, data_analysis)
5. COMPLEXITY — simple | moderate | complex
6. CLARIFICATION_NEEDED — Is any critical info missing? If so, what question to ask?

Respond with ONLY valid JSON:
{
  "role": "...",
  "task": "...",
  "purpose": "...",
  "capabilities_needed": ["..."],
  "complexity": "simple|moderate|complex",
  "clarification_needed": null or "question to ask user",
  "language": "user's preferred language (uz/en/ru)",
  "subject": "the main subject/object of the request"
}

RULES:
- Be SPECIFIC, not generic. "Python dastur yoz" -> role: "python_developer", task: "write a Python script that...", purpose: "..."
- If the request is ambiguous, set clarification_needed to the most important missing info.
- capabilities_needed MUST map to real agent tools: code_write (write_file), code_read (read_file), draw (art__draw_custom_svg), web_browse (browser_*), web_research (ask_web_ai/web_fetch), file_management (list_files/run_command), data_analysis (python_exec/run_command)
- Do NOT invent capabilities the agent doesn't have.
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

LAYER_CONSTRUCTION_SYSTEM = """You are the LAYER ARCHITECT of a layered coding agent.
Given the reprompt analysis, construct execution layers.

Each layer has:
- name: short identifier (clarification, planning, execution, validation, synthesis)
- role: the specific agent role for this layer
- task: what this layer must do
- tools: which tools/capabilities it uses (from the reprompt analysis)
- depends_on: which previous layers it needs results from (for ordering)
- streaming: whether to stream tokens to chat (always true for execution)

LAYER RULES:
1. Layer count depends on COMPLEXITY:
   - simple: 2-3 layers (quick_plan -> execution -> synthesis)
   - moderate: 3-4 layers (planning -> execution -> validation -> synthesis)
   - complex: 4-6 layers (clarification -> planning -> execution -> validation -> synthesis)
2. Each layer MUST have a clear, single purpose — no vague "do everything" layers
3. Tools are ENGINEERED, not decorative — every tool in a layer must serve that layer's purpose
4. The execution layer can have sub-steps (each sub-step is a tool call with streaming)
5. The synthesis layer ALWAYS runs last — it collects all results and formats the final output

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
      "sub_steps": [
        {"tool": "tool_name", "description": "what this tool does in this layer", "args_hint": "what args to expect"}
      ]
    }
  ],
  "final_accumulation": "How to combine layer results into the final answer"
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
"""


# ================================================================= #
# 3. LAYER EXECUTION PROMPTS: Role-specific instructions for each layer
# ================================================================= #

LAYER_EXECUTION_PROMPTS = {
    "clarification": (
        "You are the CLARIFICATION layer. Your job is to check if the user's request "
        "has all necessary information. If something is missing, ask a clear question. "
        "If everything is clear, pass the request forward. Be concise."
    ),
    "planning": (
        "You are the PLANNING layer. Your job is to create a concrete execution plan. "
        "For each step, specify: what tool to use, what arguments, and what the expected "
        "outcome is. Be specific — no vague 'do something' steps."
    ),
    "execution": (
        "You are the EXECUTION layer. Your job is to carry out the plan step by step. "
        "Use the specified tools. For each tool call: stream the process to chat, "
        "collect the result, and pass it to the next step. If a tool fails, note the "
        "error and try an alternative approach."
    ),
    "validation": (
        "You are the VALIDATION layer. Your job is to verify that the execution layer's "
        "results meet the user's requirements. Check: does the output match the intent? "
        "Are there errors? Is the quality acceptable? If issues found, note them for "
        "the execution layer to fix."
    ),
    "synthesis": (
        "You are the SYNTHESIS layer. Your job is to accumulate ALL results from previous "
        "layers and present a final, polished answer to the user. Include: what was done, "
        "what tools were used, what files were created, and any caveats. Format the "
        "output clearly and concisely."
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

FINAL_SYNTHESIS_SYSTEM = """You are the FINAL SYNTHESIS layer of a layered coding agent.
You have collected results from multiple execution layers. Now you must:

1. ACCUMULATE: Gather all results from every layer
2. FORMAT: Present a clear, organized final answer
3. HIGHLIGHT: Mention key files created, tools used, and decisions made
4. STREAM: Token-by-token output so the user sees the answer forming

Your output should be:
- In the user's language (uz/en/ru based on their request)
- Clear and structured (use headings, lists, code blocks as needed)
- Include file paths if files were created
- Include a brief summary of what was accomplished
- End with any caveats or next steps if relevant

Do NOT:
- Repeat information already shown during streaming
- Use JSON format for the final answer (plain text/markdown only)
- Include tool call formats or code fences in the summary
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


@dataclass
class LayerStep:
    """Bir qatlam ichidagi bitta amal."""
    tool: str = ""
    description: str = ""
    args_hint: str = ""


@dataclass
class ExecutionLayer:
    """Bajarish qatlami."""
    name: str = ""
    role: str = ""
    task: str = ""
    tools: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    streaming: bool = True
    sub_steps: list[LayerStep] = field(default_factory=list)


@dataclass
class LayerPlan:
    """To'liq qatlamli rejalar to'plami."""
    layers: list[ExecutionLayer] = field(default_factory=list)
    final_accumulation: str = ""
    reprompt: Optional[RepromptAnalysis] = None


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
