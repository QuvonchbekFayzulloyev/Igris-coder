---
name: specification-expander
description: Expands a confirmed-intent user request into a structured TaskSpec (acceptance criteria, constraints, gathered context) before it is sent to the model -- this is the actual "reprompt" step.
pipeline_stage: Specification
triggers: [code_task, bug_fix, review, research, command]
defers_to: [intent-resolver]
used_by: [reprompt-loop, quality-reviewer]
---

## Scope
Runs once intent is resolved and skills are routed, right before the
model is called. Converts a short, possibly underspecified user message
into a spec the model can be reliably judged against later.

## Procedure
1. Attach category-specific acceptance criteria (see
   `spec.synthesize_acceptance_criteria`) -- deterministic, not
   model-generated, so criteria don't drift between attempts.
2. Attach global constraints (Windows-first, English code/docs, no
   partial/placeholder output) unconditionally.
3. Attach only the context actually gathered for this intent (targeted
   file reads, git status) -- never dump the whole project into the
   prompt "just in case".
4. On a review failure, append the reviewer's feedback as an additional
   constraint for the next attempt rather than rewriting the whole spec
   from scratch.

## Anti-patterns
- Sending the user's raw message to the model with no structure.
- Inventing acceptance criteria that don't map to what the user actually
  asked for.
- Growing the context block without bound across retries.
