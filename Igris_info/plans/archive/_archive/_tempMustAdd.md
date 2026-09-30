# Igris Request Redirection & Generic Work Explanation

## Why Igris Redirects Before Real Work

Igris redirects requests **before** starting real work for three critical reasons:

### 1. Intent Classification (Family Detection)
Not all user requests are the same. Igris must first classify whether the request belongs to:
- **chat-family**: Answer is text itself (`chat`, `reasoning`, `math`, `quick_math`, `weather`)
- **creator-family**: Artifact must be produced (`draw`, `code`, `ui_build`)

**Example**: 
- "What's the weather today?" → chat-family (text answer)
- "Draw a red apple" → creator-family (SVG artifact needed)

### 2. Requirement Extraction (Part L)
Before any real work begins, Igris extracts required information (Part L):
- Query purpose (*sorov maqsadi*)
- Query subject (*sorov subyekti*)
- Query object (*sorov obyekti*)
- Core details the user specified vs. left for the agent to fill

**Example**: User says "Draw an apple"
- Igris checks: What color? What style? Stem needed? Size?
- If missing: **Clarification loop** fires → asks user → proceeds only after answers
- If complete: **Proceeds to planning**

### 3. Why Not Generic Work?

Igris **does not use a single generic pipeline** for all requests. Here's why:

| Reason | chat-family | creator-family |
|--------|-------------|----------------|
| **Output type** | Text answer | SVG/UI/Code artifact |
| **Compliance check** | Logic/math correctness | Visual/style compliance |
| **Failure mode** | Wrong answer | Wrong style/colors/shape |
| **Repair needed** | Re-answer or explain | Redraw/rework |
| **User expectation** | "Just tell me" | "Create something for me" |

**If Igris used generic work**:
- chat requests would try to "create artifacts" unnecessarily
- creator requests would try to "just answer" instead of making things
- Both would fail user expectations consistently

## The Actual Flow (With Redirection)

```
User Request
    │
    ▼
Router: Family? (chat vs creator, ≤2 options) ← Redirection point 1
    │
    ▼
Router: Type within family? (≤5 options) ← Redirection point 2
    │
    ▼
Requirement-extraction: Missing fields? ← Redirection point 3
    │
    ├── Yes → Human-in-the-loop gate: Ask user → Resume same loop
    │           │
    └── No  → Proceed to loop dispatch
          │
          ▼
   One Loop runs [plan → ... → review] per its shape
          │
          ▼
Synthesis pipeline → Final result → User
```

## Why This Design (Not Generic)

1. **Reliability on small models**: 8-way classifier is above ≤5-option ceiling for local models. Two-stage classification (family → type) keeps each stage ≤5 options.

2. **Cost efficiency**: 
   - chat-family requests skip artifact creation entirely
   - creator-family requests skip text-only answers
   - No wasted LLM calls or tool executions

3. **User expectation matching**:
   - "Tell me X" → text response (chat-family)
   - "Make Y" → artifact production (creator-family)
   - Mixing these causes confusion

4. **Error prevention**:
   - Requirement extraction catches missing info early
   - Clarification loop resolves before any tool calls
   - Failed artifacts from wrong classification waste computation

## When Generic Work WOULD Apply

The only case for generic work is **truly open-ended requests** where the user hasn't specified intent. But even then, Igris uses the router + clarification to home in on the right family — which is a "targeted generic" approach, not a single pipeline for everything.

## Summary

Igris redirects requests before real work because:

1. **Intent must be classified** (chat vs creator) — different tools, different outputs, different compliance checks
2. **Requirements must be extracted** (Part L) — ensures complete before any work starts
3. **Generic work doesn't exist effectively** — the two families have fundamentally different expectations, tools, and success criteria

The redirection is **not a bottleneck** — it's 2-3 quick classifier checks (milliseconds) that prevent seconds/minutes of wasted computation and user frustration from mismatched expectations.

**Bottom line**: The redirection ensures Igris does the *right* work the *first time*, rather than generic work that might do *some* work but not *the right work* for what you actually need.

---

# Plan Addition

**To add to project plan**: 
- Igris uses 2-stage request redirection (family→type classifier + requirement extraction) before any real work begins
- This prevents mismatched expectations and wasted computation
- The redirection is fast (milliseconds) but critical for correct user outcomes
- No "generic pipeline" exists — instead, two specialized families (chat vs creator) with distinct tools, outputs, and compliance criteria
- Clarification loop resolves missing requirements before any tool calls
- All code decisions flow from this redirection architecture (see `agentic_architecture.md` for full spec)