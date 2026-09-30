"""
IGRIS BRAIN — Request Meaning & Channel Model
====================================================

So'rovni to'liq semantik strukturga aylantiradi — muammo (problem),
maqsad (goal), definitsiya, detaillar va paradigmaviy tahlil bir strukturada:
SOROV-NARSA: muammo + maqsad + definitsiya + detaillar + paradigmaviy tahlil
+ kanal/sifat bastashi + zarurat g'oya (must-have) — ham bitta strukturan
+ kanal tartibi (LLM-in/LLM-out aralashmasin, noise bo'lmasin)
+ zaruriy g'oyalar (must-have).
Asosiy yo'l deterministik (LLM'siz); LLM faqat ixtiyoriy assist.
"""

from __future__ import annotations
import re
import json
import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Optional

__all__ = [
    "RequestMeaning", "RequestChannel", "PARADIGM_TAXONOMY",
    "parse_request_meaning", "normalize_paradigm",
    "MEANING_ASSIST_SYSTEM", "assist_fields",
]

# ---------------------------------------------------------------- # #
# Paradigma nominallari (taxonomiya) — qaysi SET tahlil qilishiga mos
# ---------------------------------------------------------------- # #

PARADIGM_TAXONOMY = [
    # ilmiy/fakt
    "scientific", "mathematical", "factual", "technical", "logical",
    # falsafiy/nazari
    "philosophical", "theoretical", "definitional", "epistemological",
    # amali/so'ng'gi
    "realistic", "practical", "executive", "how-to", "diagnostic",
    # butunlay mavjiy
    "state_of_the_world", "history", "data",
    # majoziy/mazkur (logika partneri, tajriba)
    "mythical", "legendary", "fable", "story_carrier", "metaphorical",
    # fikr/kavantaj
    "fantasy", "speculative", "hypothetical", "thought_experiment",
    # strat/loyihavot
    "strategic", "planning", "decision_support",
]

# Paradigma nomi -> oddiy qoida (so'rovdagi qaysi belgi/isoh nois).
_PARADIGM_PATTERNS: dict[str, list[str]] = {
    "scientific": [r"\b(how|why|what happens|explain|experiment|evidence)\b", r"\b(data|study|proven)\b"],
    "mathematical": [r"\d\s*[+\-*/^=]\s*\d", r"\b(eq|equals|sum|product|integral|equation|formula)\b"],
    "factual": [r"\b(when|where|who|which|is the|can you tell)\b", r"\b(year|population|capital)\b"],
    "technical": [r"\b(how to|setup|install|configure|debug|error)\b"],
    "logical": [r"\b(if|then|therefore|because|premise|valid|sound)\b", r"\b(why|what if|logic)\b"],
    "philosophical": [r"\b(what is|meaning|exists|know|should|ethics|truth)\b"],
    "theoretical": [r"\b(theory|model|framework|principle|concept)\b"],
    "definitional": [r"\b(what is the definition|mean by|define|explain the term)\b", r"\b(just means|whis means)\b"],
    "epistemological": [r"\b(how do we know|proof|evidence|truth|justified)\b"],
    "realistic": [r"\b(real|actually|in practice|does it work|feasible)\b", r"\b(produce|build|create|make)\b"],
    "practical": [r"\b(how would you|practical|useful|efficient|fast)\b"],
    "executive": [r"\b(plan|execute|decide|recommend|propose|strategy)\b"],
    "how-to": [r"\b(how to|can you show me|write code|make a|create a)\b", r"\b(step by step|instructions|guide)\b"],
    "diagnostic": [r"\b(why is|what's wrong|causing|broken|issue|problem)\b", r"\b(debug|fix|error)\b"],
    "state_of_the_world": [r"\b(world situation|current|now|present)\b"],
    "history": [r"\b(histor|when did|past|before|date|in the 19th)\b"],
    "data": [r"\b(data|graph|chart|visual|statistics|numbers|plot)\b"],
    "mythical": [r"\b(myth|legend|fairy tale|fable|fantasy|chapter|puzzle)\b", r"\b(creature|kingdom|castle|wizard|magic)\b"],
    "legendary": [r"\b(legend|tale|myth|cultural|folk|happy ending)\b"],
    "fable": [r"\b(fable|morals|moral|animal|fable)\b"],
    "story_carrier": [r"\b(story|script|novel|play|poem|dialogue)\b"],
    "metaphorical": [r"\b(metaphor|symbol|allegory|analog)\b"],
    "fantasy": [r"\b(fantasy|imaginary|what if|could|might|give me|show me)\b"],
    "speculative": [r"\b(what if|imagine|may|could|possibly|perhaps|likely)\b"],
    "hypothetical": [r"\b(if|suppose|assume|conditional|hypothetical|scenario)\b"],
    "thought_experiment": [r"\b(imagine|thought experiment|what if|scenario)\b"],
    "strategic": [r"\b(strategy|plan|decide|recommend|prioritize|roadmap)\b"],
    "planning": [r"\b(plan|schedule|roadmap|next steps|sequence)\b"],
    "decision_support": [r"\b(decision|recommend|choose|evaluate|which)\b"],
}

_PARADIGM_COMBINED_RE = re.compile(
    "|".join(re.escape(p) for p in PARADIGM_TAXONOMY),
    re.IGNORECASE,
)


def normalize_paradigm(paradigm: Any) -> str:
    """Paradigm nomini taxonomiyaga moslashtiradi.

    - to'liq mos nom -> o'zi
    - bir nechta topilsa -> 'combined'
    - hech biri topilmasa -> 'combined' (notiqiq nomlarni saqlab qolmaymiz)
    """
    if not paradigm:
        return "combined"
    s = str(paradigm).strip().lower()
    if s in PARADIGM_TAXONOMY:
        return s
    uniq: list[str] = []
    for m in _PARADIGM_COMBINED_RE.findall(s):
        m = str(m).lower()
        if m not in uniq:
            uniq.append(m)
    if len(uniq) == 1:
        return uniq[0]
    if len(uniq) > 1:
        return "combined"
    s2 = re.sub(r"[^a-z0-9_]+", "_", s).strip("_")
    return s2 if s2 in PARADIGM_TAXONOMY else "combined"


# ---------------------------------------------------------------- # #
# Kanal (LLM-in / LLM-out interleave + noise guard)
# ---------------------------------------------------------------- # #

_CHANNELS = ["inbound", "process", "outbound", "verify"]


@dataclass(frozen=True)
class RequestChannel:
    """Kennel mikro-nasoslar; ular bir-biran aralasib ketsa noise beradi."""
    # Fungsiyaga qarab kanallarning urinishida oqimni belgilaydi.
    scope: str = "request"
    interleave: bool = False   # true -> yer-birga sort
    order: list[str] = field(default_factory=lambda: list(_CHANNELS))

    def ordered(self) -> list[str]:
        return self.order

    def valid(self) -> bool:
        return bool(self.order) and all(c in _CHANNELS for c in self.order)


# ---------------------------------------------------------------- # #
# So'rov ma'noqli (ingen yoki LLM qaytishi)
# ---------------------------------------------------------------- # #

@dataclass
class RequestMeaning:
    """So'rovning to'liq semantik ifodasi — boshqaruv/vazifaga uzatiladi."""

    message: str = ""
    family: str = "chat"               # chat | creator | planning | guidance
    intent: str = ""                   # nevokativ
    language: str = ""
    domain: str = ""
    output_format: str = "text"
    verbosity: str = "balanced"
    constraints: list[str] = field(default_factory=list)
    deliverable_name: Optional[str] = None
    needs_tools: bool = False
    confidence: float = 0.5

    # tahlil paradigmalari (set)
    paradigms: list[str] = field(default_factory=list)
    paradigm_fits: list[str] = field(default_factory=list)  # umumiy mosligi (realistik/scientific...)
    paradigm_reason: str = ""

    # noma'lum/maqsad/definitsiya
    problem: str = ""                  # xulosa "nima qilinadi?"
    goal: str = ""                     # maqsad (katta)
    definition: str = ""               # definitsiya (if needed)
    details: list[str] = field(default_factory=list)       # detaillar
    required: list[str] = field(default_factory=list)      # zarurat g'oya
    optional: list[str] = field(default_factory=list)

    # kanal
    channel: RequestChannel = field(
        default_factory=lambda: RequestChannel(scope="request", interleave=False)
    )
    channel_note: str = ""

    # audit
    raw_llm_json: str = ""             # LLM chiqishi (agar bo'lsa)
    parse_notes: str = ""
    validated: bool = True
    version: int = 1

    # metadata
    processed_at: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "family": self.family,
            "intent": self.intent,
            "language": self.language,
            "domain": self.domain,
            "output_format": self.output_format,
            "verbosity": self.verbosity,
            "constraints": self.constraints,
            "deliverable_name": self.deliverable_name,
            "needs_tools": self.needs_tools,
            "confidence": self.confidence,
            "paradigms": self.paradigms,
            "paradigm_fits": self.paradigm_fits,
            "paradigm_reason": self.paradigm_reason,
            "problem": self.problem,
            "goal": self.goal,
            "definition": self.definition,
            "details": self.details,
            "required": self.required,
            "optional": self.optional,
            "channel": {
                "scope": self.channel.scope,
                "interleave": self.channel.interleave,
                "order": self.channel.order,
            } if self.channel else {},
            "channel_note": self.channel_note,
            "raw_llm_json": self.raw_llm_json,
            "parse_notes": self.parse_notes,
            "validated": self.validated,
            "version": self.version,
            "processed_at": self.processed_at,
        }

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.message.strip():
            errors.append("message bo'sh")
        if not 0.0 <= self.confidence <= 1.0:
            errors.append(f"confidence out of range: {self.confidence}")
        if self.paradigm_fits and not isinstance(self.paradigm_fits, list):
            errors.append("paradigm_fits must be list")
        return errors

    @property
    def is_creator_family(self) -> bool:
        return self.family == "creator"

    @property
    def has_required(self) -> bool:
        return bool(self.required)


# ---------------------------------------------------------------- # #
# Aggressive parsing (deterministik + gentl LLM assist)
# ---------------------------------------------------------------- # #

_UZ_RE = re.compile(r"[ʻ’‘`]?oʻ|[gG]ʻ|ў|қ|ғ|ҳ|ж|нг", re.IGNORECASE)
_UZ_WORDS = re.compile(
    r"\b(boʻl|uchun|bilan|kerak|yoz|yarat|ber|qil|qaysi|qanday|nimadur|hisobot"
    r"|ilova|dastur|fayl|natija|javob|savol|oʻzbek|so'z)\b",
    re.IGNORECASE,
)
_EN_WORDS = re.compile(
    r"\b(the|and|write|create|file|code|function|explain|what|how|please|report"
    r"|summarize|list|table|steps)\b", re.IGNORECASE,
)
_UZ_MARKERS = ["o'zing", "o'z", "o'zbek", "men", "meni", "bir", "biron", "barmoq", "ko'rsat"]
_EN_MARKERS = ["can you", "please", "how to", "give me", "show me", "i need", "could you"]
_UZ_MARKER_RE = re.compile(
    r"\b(" + "|".join(re.escape(m) for m in _UZ_MARKERS) + r")\b", re.IGNORECASE,
)
_EN_MARKER_RE = re.compile(
    r"\b(" + "|".join(re.escape(m) for m in _EN_MARKERS) + r")\b", re.IGNORECASE,
)
# kengaytirilgan o'zbekcha so'zlar (til aniqlash uchun)
_UZ_COMMON_RE = re.compile(
    r"\b(salom|assalomu|nima|qanaqa|kuting|yaxshi|qanday|qaysi|uchun|bilan|kerak|boshla"
    r"|mening|sening|bizning|shunaqa|kiring)\b",
    re.IGNORECASE,
)

_MATH_EXPR_RE = re.compile(r"[\d\s+\-*/^=().,%]+$")
_MATH_OP_RE = re.compile(r"\d\s*[+\-*/^=]\s*\d")
_DETAIL_WORDS = re.compile(r"\b(batafsil|detailed|ilova|to'liq|chuqur|in-depth)\b", re.IGNORECASE)
_CONCISE_WORDS = re.compile(r"\b(qisqa|concise|brief|tez|kalta)\b", re.IGNORECASE)
_LIST_WORDS = re.compile(r"\b(ro'yxat|list|items|elements)\b", re.IGNORECASE)
_TABLE_WORDS = re.compile(r"\b(jadval|table|matrix|grid)\b", re.IGNORECASE)
_STEP_WORDS = re.compile(r"\b(bosqichma-bosqich|step by step|bosqichlari|qadamlari|qadamlar)\b", re.IGNORECASE)
_FILE_FMT = re.compile(r"[\w\-]+\.(py|ts|js|tsx|jsx|md|txt|html|css|json|go|rs|cpp|c|java)", re.IGNORECASE)
_FILE_WORDS = re.compile(r"\b(fayl|file|write|save|create|deliverable)\b", re.IGNORECASE)
_TOOL_NEED_RE = re.compile(
    r"\b(write|save|create|file|code|run|execute|test|deploy|yoz\w*|yarat\w*|saqla|fayl)\b",
    re.IGNORECASE,
)
# "What is X?" / "X nima?" uslubidagi definitsiya so'rovlari
_DEF_RE = re.compile(
    r"^\s*(?:what\s+is(?:\s+the)?\s+|define\s+|ta['’]rifi\s+|nima\s*(?:dir|degani)?\s*)\s*(.+?)[?]?$",
    re.IGNORECASE,
)

_TRUTHY_CREATOR = re.compile(
    r"\b(build|draw|write|make|create|design|code|develop|generate|compose|construct)\b"
    r"|\b(?:yoz\w*|yarat\w*|qur\w*|chiz\w*|yasab)\b",
    re.IGNORECASE,
)
_CREATOR_FAMILY_PHRASES = re.compile(
    r"\b(build a|draw a|write a|make a|create a|design a|code an|develop a|generate a)\b"
    r"|\b(illat|foyda|maqsad|qoida|ko'rsatish|tog'ri|yolg'iz|master|qudrat|subyekt)\b",
    re.IGNORECASE,
)


def _detect_family(message: str) -> str:
    """So'rov oilasini aniqlaydi (deterministik, LLM'siz)."""
    low = (message or "").lower()
    # mavsum/ta'til ("yoz ta'tili") — creator emas, oldindan chiqaramiz
    if re.search(r"\b(?:ta['’]?til\w*|dam olish|fasl\w*)\b", low):
        return "chat"
    if _TRUTHY_CREATOR.search(low) or _CREATOR_FAMILY_PHRASES.search(low):
        return "creator"
    # planning/guidance (not creator: no artifact)
    if re.search(r"\b(plan|strategy|decide|recommend|roadmap|schedule)\b", low):
        return "guidance"
    return "chat"


def _detect_paradigm(message: str, family: str, intent: str) -> dict:
    """Paradigm nominalarini topadi; agar hech biri mos kelmasa 'combined'."""
    low = (message or "").lower()
    fits: list[str] = []
    for p in PARADIGM_TAXONOMY:
        for pat in _PARADIGM_PATTERNS.get(p, []):
            if re.search(pat, low):
                fits.append(p)
                break
    # mavzu bo'yicha eslatma
    if intent in ("math", "code", "weather") and family == "chat":
        fits = [i for i in fits if i not in ("fantasy", "story_carrier", "mythical")]
    if not fits:
        return {"paradigms": ["combined"], "fits": [], "reason": "no pattern"}
    # juda nuqta yiqindi bo'lsa, eng mos
    top = fits[0]
    return {"paradigms": fits, "fits": [top], "reason": f"{top} pattern matched"}


def _detect_details(message: str, verbosity: str) -> list[str]:
    low = (message or "").lower()
    out: list[str] = []
    if _DETAIL_WORDS.search(low):
        out.append("batafsil")
    if _STEP_WORDS.search(low):
        out.append("bosqichma-bosqich")
    if _TABLE_WORDS.search(low):
        out.append("table")
    elif _LIST_WORDS.search(low):
        out.append("list")
    if _CONCISE_WORDS.search(low):
        out.append("qisqa")
    return out


def _detect_required(message: str) -> list[str]:
    low = (message or "").lower()
    out: list[str] = []
    if _FILE_FMT.search(low):
        out.append("deliverable_file")
    if _FILE_WORDS.search(low):
        out.append("file_handling")
    if _MATH_OP_RE.search(low) or _MATH_EXPR_RE.fullmatch(low.strip()):
        out.append("deterministic")
    if re.search(r"\b(error|problem|puzzle|solving)\b", low):
        out.append("problem_focused")
    if re.search(r"\b(strategy|plan|roadmap)\b", low):
        out.append("plan_required")
    return out


# ---------------------------------------------------------------- # #
# Parse funksiyalari
# ---------------------------------------------------------------- # #

def parse_request_meaning(
    message: str,
    *,
    family: Optional[str] = None,
    detect_family: bool = True,
    llm_json: Optional[dict] = None,
) -> RequestMeaning:
    """So'rovni RequestMeaning ga aylantiradi.

    Qoidalar:
      - LLM chaqirish HARSHALI — faqatONA (controller) tanlovida.
      - Gaia ishtirok etadi, oddiy so'rovlar uchun deterministik.
      - Noise: XLI/LLM tez-tez kasb qiladi, shuning uchun parse erkin.
    """
    message = (message or "").strip()
    if not message:
        return RequestMeaning(message="", validated=False,
                              parse_notes="empty message")

    if family:
        family = str(family).strip().lower() or "chat"
    elif detect_family:
        family = _detect_family(message)
    else:
        family = "chat"
    low = message.lower()

    # llm pozitsiya
    llm_json = llm_json or {}
    intent = str(llm_json.get("intent") or "").strip() or ""
    language = str(llm_json.get("language") or "").strip() or ""
    domain = str(llm_json.get("domain") or "").strip() or ""
    output_format = str(llm_json.get("output_format") or "text").strip() or "text"
    verbosity = str(llm_json.get("verbosity") or "balanced").strip() or "balanced"
    constraints = llm_json.get("constraints") or []
    if not isinstance(constraints, list):
        constraints = []
    constraints = [str(c).strip() for c in constraints if str(c).strip()][:8]
    deliverable_name = llm_json.get("deliverable_name")
    needs_tools = bool(llm_json.get("needs_tools", False))
    try:
        confidence = float(llm_json.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    # til (LLM bergan bo'lsa shu, aks holda deterministik nois- Belgisi)
    if not language:
        if _UZ_RE.search(message) or _UZ_WORDS.search(message) or _UZ_COMMON_RE.search(message) or _UZ_MARKER_RE.search(low):
            language = "uz"
        elif _EN_WORDS.search(message) or _EN_MARKER_RE.search(low):
            language = "en"
        else:
            language = ""

    # intent bo'lmasa — faqat KNOWN_INTENTS ichidan deterministik fallback
    if not intent:
        if _MATH_EXPR_RE.fullmatch(low) or _MATH_OP_RE.search(low):
            intent = "math"
        elif re.search(
            r"\b(when|where|who|which|capital|population|date|today|history|"
            r"qachon|qaysi|kim|qayerda)\b",
            low,
        ):
            intent = "research"
        elif family == "creator":
            intent = "code" if re.search(r"\.(py|js|jsx|ts|tsx|go|rs|cpp|java|html|css)\b", low) else "file"
        else:
            intent = "general"

    # paradigm
    paradigm_info = _detect_paradigm(message, family, intent)
    paradigms = _dedupe_list(paradigm_info["paradigms"])
    paradigm_fits = _dedupe_list(paradigm_info["fits"])
    paradigm_reason = paradigm_info.get("reason", "")

    # details/required
    details = _detect_details(message, verbosity)
    required = _detect_required(message)
    optional: list[str] = []
    _llm_details = llm_json.get("details")
    if isinstance(_llm_details, list) and _llm_details:
        # LLM qo'shadi — deterministik signal yo'qolmaydi (merge, replace emas)
        details = _dedupe_list(
            details + [str(d).strip() for d in _llm_details if str(d).strip()]
        )[:8]
    _llm_required = llm_json.get("required")
    if isinstance(_llm_required, list) and _llm_required:
        required = _dedupe_list(
            required + [str(r).strip() for r in _llm_required if str(r).strip()]
        )[:8]
    _llm_optional = llm_json.get("optional")
    if isinstance(_llm_optional, list) and _llm_optional:
        optional = [str(o).strip() for o in _llm_optional if str(o).strip()][:8]
    _llm_paradigms = llm_json.get("paradigms")
    if isinstance(_llm_paradigms, list) and _llm_paradigms:
        _p = [p for p in _dedupe_list([normalize_paradigm(p) for p in _llm_paradigms])
              if p != "combined"]
        if _p:
            paradigms = _p
            paradigm_fits = _p[:1]
            paradigm_reason = "llm provided"

    # file
    if deliverable_name:
        deliverable_name = str(deliverable_name).strip() or None
    else:
        _fm = _FILE_FMT.search(message)
        deliverable_name = _fm.group(0) if _fm else None

    needs_tools = needs_tools or bool(_TOOL_NEED_RE.search(low))
    if family == "creator":
        needs_tools = True
    if intent == "math" or intent == "weather":
        needs_tools = False

    # muammo / maqsad / definitsiya (deterministik; LLM ustuvor)
    problem = str(llm_json.get("problem") or "").strip() or message
    definition = str(llm_json.get("definition") or "").strip()
    if not definition:
        _dm = _DEF_RE.match(message)
        if _dm:
            definition = _dm.group(1).strip().rstrip("?!")
    goal = str(llm_json.get("goal") or "").strip()
    if not goal:
        if family == "creator":
            goal = (deliverable_name or "artifact") + " yaratish/taqdim etish"
        elif intent == "math":
            goal = "matematik ifodaning natijasini topish"
        elif intent == "research":
            goal = "fakt/javobni aniqlash"
        else:
            goal = "so'rov bo'yicha aniq javob taqdim etish"

    channel = RequestChannel(scope="request", interleave=False)

    parsed_at = dt.datetime.now().isoformat(timespec="seconds")
    return RequestMeaning(
        message=message,
        family=family,
        intent=intent,
        language=language,
        domain=domain,
        output_format=output_format,
        verbosity=verbosity,
        constraints=constraints,
        deliverable_name=deliverable_name,
        needs_tools=needs_tools,
        confidence=confidence,
        paradigms=paradigms,
        paradigm_fits=paradigm_fits,
        paradigm_reason=paradigm_reason,
        problem=problem,
        goal=goal,
        definition=definition,
        details=details,
        required=required,
        optional=optional,
        channel=channel,
        channel_note="paradigm + language + verbosity + file",
        raw_llm_json=json.dumps(llm_json) if llm_json else "",
        parse_notes="aggressive + LLM assist",
        validated=True,
        version=1,
        processed_at=parsed_at,
    )


def _dedupe_list(items: list) -> list:
    seen = set()
    out = []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


# ------------------------------------------------------------------ #
# IXTIYORIY LLM ASSIST — problem/goal/definition/paradigms boyitish
# ------------------------------------------------------------------ #
# Deterministik parse asosiy yo'l; shu assist faqat LLM mavjud bo'lganda
# va chaqiruvchi qatlam ruxsat berganda ishlaydi (ixtiyoriy). Hech qachon
# exception bermaydi — xato natija {} bo'ladi va deterministik parse o'zi
# ishlaydi (asosiy javob hech qachon buzilmaydi).

MEANING_ASSIST_SYSTEM = """You are a request-semantics analyzer for a local AI agent.
Given ONE user request, reply with ONE compact JSON object only (no prose, no code fences):
{
  "problem": "the concrete problem/muammo stated by the user (<=140 chars)",
  "goal": "the user's real goal/maqsad — what a successful answer must achieve (<=140 chars)",
  "definition": "short definition of the key term when the request asks 'what is X'/'X nima', else empty string",
  "paradigms": ["1-2 paradigms taken ONLY from this set: scientific, mathematical, factual, technical, logical, philosophical, theoretical, definitional, epistemological, realistic, practical, executive, how-to, diagnostic, state_of_the_world, history, data, mythical, legendary, fable, story_carrier, metaphorical, fantasy, speculative, hypothetical, thought_experiment, strategic, planning, decision_support"],
  "details": ["explicit detail/format requirements stated by the user (max 4, <=80 chars each)"],
  "required": ["must-have items without which the answer is incomplete (max 4, <=80 chars each)"]
}
Rules:
- Write every value in the SAME language as the user request.
- Only include what the request actually supports — never invent files, tools or facts.
- If unsure about a field, use an empty string or an empty array for it.
- JSON object only."""

_ASSIST_STR_LIMITS = (("problem", 300), ("goal", 300), ("definition", 300))
_ASSIST_LIST_KEYS = ("details", "required", "optional")


def _sanitize_assist(obj: dict) -> dict:
    """LLM JSON'ini xavfsiz maydonlarga aylantiradi (noise guard)."""
    out: dict = {}
    for key, limit in _ASSIST_STR_LIMITS:
        v = obj.get(key)
        if isinstance(v, str) and v.strip():
            out[key] = v.strip()[:limit]
    for key in _ASSIST_LIST_KEYS:
        v = obj.get(key)
        if isinstance(v, list):
            items = [str(x).strip()[:120] for x in v if str(x).strip()][:8]
            if items:
                out[key] = _dedupe_list(items)
    v = obj.get("paradigms")
    if isinstance(v, list):
        paradigms: list[str] = []
        for p in v[:6]:
            np_ = normalize_paradigm(p)
            if np_ != "combined" and np_ not in paradigms:
                paradigms.append(np_)
        if paradigms:
            out["paradigms"] = paradigms
    return out


def assist_fields(message: str, llm, *, cache=None, family: str = "") -> dict:
    """LLM dan problem/goal/definition/paradigms/detaillar so'raydi (ixtiyoriy).

    Qoidalar:
      - Hech qachon exception bermaydi: xato/bo'sh/junk -> {} (deterministik
        parse baribir o'zi ishlaydi).
      - CAG kesh (namespace "meaning") — takroriy so'rov LLM'ni qayta
        chaqirmaydi.
      - Natija _sanitize_assist orqali chegaralanadi (uzunlik/to'plam/noise).
    """
    msg = (message or "").strip()
    if not msg or llm is None or not hasattr(llm, "complete"):
        return {}
    # 1) kesh (CAG) — avval tekshiramiz, LLM'ga O'TMAYMIZ
    try:
        if cache is not None:
            cached = cache.get("meaning", msg)
            if cached:
                obj = json.loads(cached)
                if isinstance(obj, dict) and obj:
                    return obj
    except Exception:
        pass
    # 2) LLM chaqiruvi (qisqa, bitta JSON)
    try:
        prompt = "Family: " + (family or "unknown") + "\nUser request:\n" + msg[:1500]
        text = llm.complete(system=MEANING_ASSIST_SYSTEM, prompt=prompt)
    except Exception:
        return {}
    if not text or not str(text).strip():
        return {}
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        obj = None
    if not isinstance(obj, dict):
        # model JSON'ni matn ichiga o'rab yozsa — muvozanatli blokni olamiz
        try:
            from core.intelligence.logic import extract_balanced_json
            raw = extract_balanced_json(str(text))
            obj = json.loads(raw) if raw else None
        except Exception:
            obj = None
    if not isinstance(obj, dict):
        return {}
    fields = _sanitize_assist(obj)
    if fields:
        try:
            if cache is not None:
                cache.put("meaning", msg, json.dumps(fields, ensure_ascii=False))
        except Exception:
            pass
    return fields
