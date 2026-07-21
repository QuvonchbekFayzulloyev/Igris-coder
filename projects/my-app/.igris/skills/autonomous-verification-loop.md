---
name: autonomous-verification-loop
description: Governs the assume-and-proceed band: when intent confidence is above the hard-block threshold but below the clarify threshold, state the assumption explicitly instead of asking, so a wrong guess is easy to spot and correct in one message.
pipeline_stage: Planning
triggers: [assume, ambiguous, clarify, proceed]
defers_to: [clarification-guard]
used_by: [reprompt-loop, intent-resolver]
---

## Scope
Applies when intent confidence is between the hard-block threshold
(`loop.hard_block_confidence_threshold`, default 0.35) and the clarify
threshold (`loop.clarify_confidence_threshold`, default 0.55). In this
band the task is reasonably inferable but not certain enough to proceed
silently.

## Procedure
1. Do not ask a clarifying question -- the user would need to answer
   something that is already 60-80% inferable from context.
2. Do not silently proceed -- that hides the ambiguity and makes a wrong
   guess expensive to correct later.
3. Instead, prepend a single, plain assumption note to the final response
   (e.g. "Treating this as a 'code_task' request (matched: implement,
   add) -- say so if that's not what you meant."). The note is generated
   by `IntentResolver.build_assumption_note`.
4. If the user corrects the assumption in the next turn, the new intent
   classification starts fresh with the clarified input.

## Anti-patterns
- Asking a clarification question in this band (wastes a round-trip on
  something reasonably inferable).
- Proceeding silently without naming the assumption (makes the user's
  correction feel like a new task instead of a continuation).
- Looping back to clarification if the user's correction is still
  ambiguous -- after one assumption round, fall back to asking.