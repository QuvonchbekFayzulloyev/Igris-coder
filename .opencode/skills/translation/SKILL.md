# Translation Skill

## Mission
Translate user text between any language and canonical English for the
Understanding Module. Preserve meaning, context, technical terms, code
identifiers, file paths, and proper nouns. Never word-for-word — always
semantic preservation.

## How it works
1. `igris.core.translation.detect_language(text)` — heuristic pattern
   matching (no network, no LLM). Supports uz, ru, kk, tr, en.
2. `translate_to_canonical(text, lang)` — LLM-assisted translation to
   English. Results are cached. Preserves tech terms verbatim.
3. `translate_from_canonical(text, target_lang)` — translate response
   back to user's language.
4. IntentResolver calls step 1+2 before classification on every turn.

## Rules
- The Understanding Module (IntentResolver) ONLY works on canonical English.
- Never add explanations or notes to translations.
- Code, file paths, variable names, and proper nouns are never translated.
- Translation cache prevents repeated LLM calls for the same text.
- New language support only needs patterns in LANGUAGE_PATTERNS dict +
  the local LLM to handle translation — no new Understanding Module.

## When to add a language
Add patterns to `igris/core/translation.py` LANGUAGE_PATTERNS dict.
The local LLM handles the actual translation — no code changes needed
in the Understanding Module.
