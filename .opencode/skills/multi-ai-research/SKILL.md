# Multi-AI Research Skill

Orchestrates multiple AI providers in parallel with specialized prompts,
then merges results through fact voting, conflict resolution, verification,
and self-critique before producing the final answer.

## Trigger

When the user asks a factual/research question that requires:
- Web-grounded answers (Perplexity)
- Multiple perspectives (ChatGPT + Kimi + Local)
- Source-backed verification
- Uncertainty/confidence handling

Any `intent.category == "research"` query routes through this pipeline.

## Pipeline Stages

```
User Query
     │
     ▼
[1] Provider Selection     ← choose providers based on query type
     │
     ▼
[2] Parallel Query         ← each provider gets a different specialized prompt
     │
     ├── Perplexity  → "Research with web sources: {query}"
     ├── ChatGPT     → "Comprehensive overview including multiple interpretations: {query}"
     ├── Kimi        → "Deep technical analysis: {query}"
     ├── Local LLM   → "Answer concisely: {query}"
     └── OpenAI API  → "Research comprehensively with citations: {query}"
     │
     ▼
[3] Evidence Graph         ← structure responses into facts with source attribution
     │
     ▼
[4] Conflict Resolution    ← detect contradictions, vote-count confidence
     │
     ▼
[5] Fact Verification      ← local LLM confirms/contradicts each claim
     │
     ▼
[6] Reasoning Synthesis    ← confirmed → conclusion, conflicted → exclude
     │
     ▼
[7] Self-Critique          ← score accuracy, completeness, uncertainty handling
     │
     ▼
[8] Final Answer           ← polished answer with confidence indicators
     │
     ▼
Memory (log the interaction)
```

## Key Rules

1. **Never pass external AI output directly to the user.** Always merge,
   verify, and critique first.
2. **Parallel specialization.** Every provider gets a different prompt
   optimized for its strength, not the same prompt.
3. **Confidence threshold.** If no provider achieves confidence > 0.6
   on a claim, mark it as uncertain and say so.
4. **Fact voting.** A claim supported by 2+ providers is high confidence.
   A single-source claim is medium. Conflicts are low.
5. **Self-critique.** Always score the final reasoning before delivering.

## Tools

- `multi_ai_research.provider_select` — given a query, recommend providers
- `multi_ai_research.provider_query` — run parallel queries with specialized prompts
- `multi_ai_research.evidence_graph` — structure responses into fact nodes
- `multi_ai_research.resolve_conflicts` — detect contradictions
- `multi_ai_research.verify_facts` — verify claims against local LLM
- `multi_ai_research.synthesize_reasoning` — build reasoning chain
- `multi_ai_research.self_critique` — score quality
- `multi_ai_research.final_answer` — generate polished output

## Provider Capabilities

| Provider    | Speed | Knowledge | Reasoning | Sources | Login Needed |
|-------------|-------|-----------|-----------|---------|-------------|
| local_llm   | ⚡⚡⚡⚡⚡ | ⚡⚡⚡     | ⚡⚡⚡     | No      | No          |
| perplexity  | ⚡⚡⚡   | ⚡⚡⚡⚡⚡ | ⚡⚡⚡     | Yes     | No          |
| chatgpt     | ⚡⚡⚡⚡ | ⚡⚡⚡⚡⚡ | ⚡⚡⚡⚡   | No      | Yes         |
| kimi        | ⚡⚡⚡   | ⚡⚡⚡⚡⚡ | ⚡⚡⚡⚡   | No      | Yes         |
| openai      | ⚡⚡⚡⚡ | ⚡⚡⚡⚡⚡ | ⚡⚡⚡⚡⚡ | No      | No (API key)|
