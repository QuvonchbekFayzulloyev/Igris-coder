---
name: clarification-guard
description: Decides when to stop and ask the user a targeted question instead of guessing, and shapes that question to resolve the single biggest ambiguity.
pipeline_stage: Planning
triggers: [ambiguous, clarify, unclear, confirm]
defers_to: []
used_by: [reprompt-loop, intent-resolver]
---

## Scope
Fires only when intent confidence is below threshold. Produces at most
one question per turn -- never a list of questions -- and that question
must be answerable in a single short reply.

## Procedure
1. Identify the single piece of missing information that would most
   increase confidence (task type, target file/module, desired scope).
2. Phrase one direct question about that gap only; do not bundle
   unrelated uncertainties into the same question.
3. Preserve the original user message verbatim in memory so the answer
   can be merged back into the same task on the next turn, instead of
   starting over.
4. If the user's follow-up is still ambiguous after one clarification
   round, proceed with the most likely interpretation rather than
   asking a second time -- state the assumption explicitly in the
   final response instead.

## Anti-patterns
- Asking more than one question at once.
- Re-asking a question the user already answered earlier in the session.
- Using clarification as a way to avoid attempting a reasonably-scoped task.
