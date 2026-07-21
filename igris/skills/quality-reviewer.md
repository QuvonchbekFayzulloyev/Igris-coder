---
name: quality-reviewer
description: Judges a draft response against the TaskSpec's acceptance criteria before it reaches the user, and produces one short, actionable piece of feedback on failure.
pipeline_stage: Review
triggers: [review, quality, verify, check]
defers_to: [specification-expander]
used_by: [reprompt-loop]
---

## Scope
Runs after each model attempt, before the response is shown to the user.
Bounded by `loop.max_review_iterations` -- this skill never causes an
unbounded retry loop.

## Procedure
1. Compare the draft response against the spec's acceptance criteria
   only -- not against a general notion of "good writing".
2. Force a first-line verdict (PASS/FAIL) so the result is parseable
   without free-form interpretation.
3. On FAIL, give exactly one sentence of feedback describing the single
   most important gap -- not an exhaustive critique.
4. If the review call itself fails (timeout, malformed output), default
   to PASS rather than blocking the response from reaching the user.

## Anti-patterns
- Reviewing style/tone when the acceptance criteria only concern
  correctness or completeness.
- Producing multi-paragraph feedback that itself needs a review pass.
- Looping past the configured max_review_iterations "just to be safe".
