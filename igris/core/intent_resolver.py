"""
igris.core.intent_resolver
----------------------------
Stage 2 + Stage 3 of the mini-loop: figure out what kind of task this is
*before* spending a full model call on it, and decide whether to ask a
clarifying question instead of guessing.

Heuristics run first (cheap, instant, no network). Only when the heuristic
confidence is below threshold do we escalate to a small classification
call against the same local model -- so most turns never pay that cost.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CATEGORY_KEYWORDS = {
    "code_task": [
        r"\bimplement\b", r"\badd\b", r"\bfix\b", r"\bbug\b", r"\brefactor\b", r"\bbuild\b",
        r"\bwrite (a |the )?(function|class|script|module)\b", r"\bcreate\b.*\b(cli|tool|app|script)\b",
        r"\byarat\b", r"qo'sh", r"\btuzat\b", r"o'zgartir", r"\byaxshila\b",
        # Architecture vocabulary is normally a request to change this
        # coding agent, not a casual mention; route it to the tool-capable
        # task path so MCP, skills, and review can do their jobs.
        r"\b(?:agentic|system\s*prompt|mcp(?:\s+calling)?|skill(?:lar)?)\b",
    ],
    "bug_fix": [
        r"\berror\b", r"\bexception\b", r"\bcrash(es|ed)?\b", r"\btraceback\b",
        r"\bxato\b", r"ishlamay", r"\bbroken\b",
    ],
    "review": [
        r"\breview\b", r"\bcheck (this|my)\b", r"\baudit\b", r"\btekshir\b",
    ],
    "research": [
        r"\bwhat is\b", r"\bhow does\b", r"\bexplain\b", r"\bnima\b", r"\bqanday\b",
        r"\bcompare\b", r"\bqiyosla\b",
    ],
    "command": [
        r"\brun\b", r"\bexecute\b", r"ishga tushir", r"\bbajar\b",
        # everyday read-only / display requests -- these are commands too
        # (list_dir, read_file, git_status, etc.), not ambiguous:
        r"\blist\b", r"\bshow\b", r"\bdisplay\b", r"\bprint\b", r"\bcat\b",
        r"\bread\b.*\bfile\b", r"\bopen\b.*\bfile\b",
        r"ko'rsat", r"chiqar", r"ro'yxat", r"o'chib ber",
    ],
    "question": [
        r"\?$", r"^(is|are|does|can|should|why|who|when)\b",
    ],
    "greeting": [
        r"\bhi\b", r"\bhello\b", r"\bhey\b", r"\byo\b", r"\bsalom\b", r"\b assalomu alaykum\b",
        r"^how('s| is) it going\b", r"^what('s| is) up\b", r"^good (morning|afternoon|evening)\b",
        r"^salom$",
    ],
}

PATH_PATTERN = re.compile(r"[\w\-./\\]+\.\w{1,6}")


@dataclass
class Intent:
    category: str
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)
    mentioned_paths: list[str] = field(default_factory=list)


class IntentResolver:
    def __init__(self, config, llm=None):
        self.config = config
        self.llm = llm  # optional OllamaClient, only used when heuristics are unsure

    def _heuristic(self, text: str) -> Intent:
        lowered = text.lower()
        scores: dict[str, list[str]] = {}
        for category, patterns in CATEGORY_KEYWORDS.items():
            hits = [p for p in patterns if re.search(p, lowered)]
            if hits:
                scores[category] = hits

        paths = PATH_PATTERN.findall(text)

        if not scores:
            return Intent(category="ambiguous", confidence=0.2, mentioned_paths=paths)

        best_category = max(scores, key=lambda c: len(scores[c]))
        hit_count = len(scores[best_category])
        # confidence grows with hits but caps below 1.0 -- heuristics alone
        # should rarely claim full certainty.
        confidence = min(0.5 + 0.15 * hit_count, 0.9)
        if len(scores) > 1:
            # scales with how many categories genuinely competed, not just
            # whether more than one did -- three plausible categories is
            # more genuinely ambiguous than two, and should read as such.
            confidence -= 0.1 * min(len(scores) - 1, 3)

        return Intent(
            category=best_category,
            confidence=round(max(confidence, 0.1), 2),
            matched_keywords=scores[best_category],
            mentioned_paths=paths,
        )

    async def classify(self, text: str) -> Intent:
        heuristic = self._heuristic(text)
        threshold = self.config.get("loop.clarify_confidence_threshold", 0.55)

        if heuristic.confidence >= threshold or self.llm is None:
            return heuristic

        # Escalate to a tiny, cheap classification call.
        prompt = (
            "Classify the user's request into exactly one label: "
            "code_task, bug_fix, review, research, command, question, ambiguous.\n"
            f"Request: {text}\n"
            "Reply with only the label."
        )
        try:
            result = await self.llm.chat(
                messages=[
                    {"role": "system", "content": "You are a terse intent classifier. Reply with one label only."},
                    {"role": "user", "content": prompt},
                ]
            )
            lowered_reply = result.content.strip().lower()
            # search for any known label anywhere in the reply, not just the
            # first token -- coder-tuned models often wrap it in a sentence
            # or markdown ("Label: command.") instead of replying bare.
            valid_labels = list(CATEGORY_KEYWORDS.keys()) + ["ambiguous"]
            label = next(
                (lbl for lbl in valid_labels if re.search(rf"\b{re.escape(lbl)}\b", lowered_reply)),
                None,
            )
            if label:
                return Intent(
                    category=label,
                    confidence=0.75,
                    matched_keywords=["llm_escalation"],
                    mentioned_paths=heuristic.mentioned_paths,
                )
        except Exception:
            pass

        return heuristic

    def build_clarifying_question(self, text: str, intent: Intent) -> str:
        """Stage 3 hard-block gate: a single, targeted question instead of guessing."""
        if intent.category == "ambiguous":
            return (
                "I'm not sure what you'd like me to do. "
                "Could you clarify — is this a task to write or change code, "
                "a command to run, or a question you'd like answered?"
            )
        return (
            f"I'm guessing this is a '{intent.category}' request, but I'm not very confident. "
            "Could you be more specific about which files or part of the project this relates to?"
        )

    def build_assumption_note(self, text: str, intent: Intent) -> str:
        """
        Stage 3 middle band (autonomous-verification-loop skill): confidence
        is below the clarify threshold but above the hard-block threshold --
        low enough to be worth naming explicitly, high enough that asking
        would be an unnecessary round-trip for a reasonably inferable case.
        Returns a short, plain statement of what's being assumed; the loop
        prepends this to the response so a wrong guess is easy to spot and
        correct in one message, instead of silently proceeding.
        """
        reason = ""
        if intent.matched_keywords and intent.matched_keywords != ["llm_escalation"]:
            reason = f" (matched: {', '.join(intent.matched_keywords[:3])})"
        return f"Treating this as a '{intent.category}' request{reason} -- say so if that's not what you meant."
