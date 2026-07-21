---
name: intent-resolver
description: Classifies a raw user request into a task category before any context gathering or execution happens, and signals when confidence is too low to proceed safely.
pipeline_stage: Planning
triggers: [code_task, bug_fix, review, research, command, question, ambiguous, intent]
defers_to: [clarification-guard]
used_by: [reprompt-loop, specification-expander]
---

## Scope
Applies to every incoming user turn, before any tool call or model
generation happens. Does not itself gather context or write output --
it only decides what kind of task this is and how confident that
classification is.

## Procedure
1. Run keyword/regex heuristics against the raw text first; do not call
   the model unless heuristics disagree or produce no match.
2. If heuristic confidence is below the configured threshold
   (`loop.clarify_confidence_threshold`), escalate to a single, cheap
   classification call constrained to one-label output.
3. Record which category won and why (matched keywords), so downstream
   stages (skill routing, context gathering) can explain their choices.
4. Never silently default to `code_task` when uncertain -- default to
   `ambiguous` and let the clarification-guard skill take over.

## Anti-patterns
- Calling the full-size model for classification on every turn instead of
  using heuristics first.
- Treating a single keyword match as high confidence.
- Proceeding to execution on `ambiguous` intent instead of asking.
