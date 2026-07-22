"""Multi-AI Research MCP server.

Pipeline-aligned tools for the research pipeline:
  1. Provider Selection
  2. Parallel Provider Queries (specialized prompts)
  3. Response Collection → Evidence Graph
  4. Conflict Resolution
  5. Fact Verification
  6. Reasoning Synthesis
  7. Self-Critique
  8. Final Answer

Supports both API-based providers (OpenAI compatible) and web-based AI
sites (Perplexity, ChatGPT, Kimi) via the bundled Playwright runner.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from igris.core.browser_runtime import (
    SUPPORTED_SITES,
    get_runtime,
)


mcp = FastMCP("multi_ai_research")
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
#  Internal helpers
# ---------------------------------------------------------------------------

from igris.core.provider_router import (
    PROVIDER_CAPABILITIES,
    CAPABILITY_PROVIDERS,
    query_to_capability,
    get_healthy_providers,
    select,
    select_multi,
    mark_failure,
    mark_success,
    get_health_summary,
)

_PROVIDER_CAPABILITIES = {
    "local_llm":  {"cost": 0, "speed": 5, "knowledge": 3, "reasoning": 3, "needs_login": False, "capabilities": {"coding", "reasoning", "research", "conversation"}},
    "openai":     {"cost": 3, "speed": 4, "knowledge": 5, "reasoning": 5, "needs_login": False, "capabilities": {"image_gen", "coding", "reasoning", "research", "sources", "conversation"}},
    "duckduckgo": {"cost": 0, "speed": 4, "knowledge": 3, "sources": True, "needs_login": False, "capabilities": {"research", "sources"}},
}

_SPECIALIZED_PROMPTS = {
    "perplexity": lambda q: f"Research with web sources: {q}",
    "chatgpt":    lambda q: f"Give a comprehensive overview of all aspects of: {q}. Include multiple interpretations if ambiguous.",
    "kimi":       lambda q: f"Deep technical analysis of: {q}. Focus on architecture, implementation details, and best practices.",
    "local_llm":  lambda q: f"Answer concisely: {q}",
    "openai":     lambda q: f"Research comprehensively. Include multiple perspectives, factual claims, and cite sources: {q}",
}

_PROVIDER_ORDER = ["local_llm", "perplexity", "duckduckgo", "chatgpt", "kimi", "openai"]


def _load_llm_config() -> dict:
    try:
        cfg = json.loads((REPOSITORY_ROOT / ".igris" / "config.json").read_text(encoding="utf-8"))
        return {
            "base_url": cfg.get("model", {}).get("base_url", cfg.get("ollama", {}).get("base_url", "http://127.0.0.1:11434")),
            "model": cfg.get("model", {}).get("name", cfg.get("ollama", {}).get("model", "qwen3:4b")),
        }
    except Exception:
        return {"base_url": "http://127.0.0.1:11434", "model": "qwen3:4b"}


def _ask_local_llm(llm: dict | None, system: str, prompt: str) -> str:
    if not llm:
        return ""
    try:
        import httpx
        resp = httpx.post(
            f"{llm['base_url']}/api/chat",
            json={"model": llm["model"], "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}], "stream": False, "options": {"temperature": 0.2}},
            timeout=120,
        )
        resp.raise_for_status()
        return (resp.json().get("message") or {}).get("content", "")
    except Exception as exc:
        return f"[ERROR: local LLM unavailable: {exc}]"


def _ask_openai(api_key: str, system: str, prompt: str, model: str = "gpt-4o-mini") -> str:
    if not api_key:
        return ""
    try:
        import httpx
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            json={"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}], "temperature": 0.3},
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        return f"[ERROR: OpenAI unavailable: {exc}]"


def _strip_preambles(text: str) -> str:
    return re.sub(r"^(Here is|Sure!|I'd be happy|Based on|According to).{0,100}?:?\s*", "", text, flags=re.IGNORECASE).strip()


def _extract_facts(text: str) -> list[dict]:
    facts = []
    for line in re.split(r"[.;]\s+", text):
        line = line.strip().strip("-*").strip()
        if 20 < len(line) < 500:
            facts.append({"statement": line[:300], "source": ""})
    return facts[:20]


# ---------------------------------------------------------------------------
#  0. Provider Route — decision architecture stage
# ---------------------------------------------------------------------------

@mcp.tool()
def provider_route(query: str) -> str:
    """Stage 0: Provider Route — decide which provider to use for a query.

    Uses the static Provider Capability Registry (igris.core.provider_router).
    Never asks AI "can you do this?". Uses cached health to skip
    rate-limited/down providers. Returns full decision trace.

    This is the "when to choose which" decision architecture:
      1. query_to_capability() — cheap regex maps query to capability
      2. get_healthy_providers() — filters by cached health
      3. select() — picks the best healthy provider
      4. mark_failure() — called when a provider fails (rate_limited, down)
      5. mark_success() — called when a provider succeeds

    Decision trace includes: capability, all candidates, health per provider,
    winner, and fallback chain.
    """
    from igris.core.provider_router import get_decision_path, format_decision
    trace = get_decision_path(query)
    readable = format_decision(query)
    return json.dumps({
        "ok": True,
        "trace": trace,
        "decision": trace["decision"],
        "readable": readable,
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
#  1. Provider Selection
# ---------------------------------------------------------------------------

@mcp.tool()
def provider_select(query: str, use_local: bool = True, use_openai: bool = False) -> str:
    """Select which AI providers are suitable for a given query.

    Uses the Provider Capability Registry — no AI "can you do this?" queries.
    Matches query to capability via static rules, then returns first healthy
    provider(s) for that capability. Cached health is checked so rate_limited
    providers are skipped.

    Only re-checks when a provider is explicitly cleared or re-registered.
    """
    query_lower = query.lower()
    is_simple = len(query.split()) < 8 and not re.search(r"\b(explain|how|why|compare|analyze|architecture|design|source|research|rasm|image)\b", query_lower)

    config = _load_llm_config()
    local_ok = use_local and config.get("base_url") and config.get("model")
    openai_ok = use_openai and bool(os.environ.get("OPENAI_API_KEY", ""))

    if is_simple and local_ok:
        return json.dumps({
            "ok": True,
            "providers": [{"provider": "local_llm", "reason": "simple query, local model is sufficient", "priority": 1}],
            "strategy": "local_only"
        }, ensure_ascii=False)

    # Capability-driven provider selection via shared provider_router
    capability = query_to_capability(query)
    healthy = get_healthy_providers(capability)

    # Add API-based providers if available
    if openai_ok and "openai" not in healthy:
        healthy.append("openai")

    recommendations = []
    for i, prov in enumerate(healthy):
        reasons = {
            "image_gen": "image generation capability",
            "coding": "code generation capability",
            "reasoning": "strong reasoning capability",
            "research": "web-grounded research",
            "sources": "source citations available",
        }
        reason = reasons.get(capability, f"supports {capability}")
        recommendations.append({"provider": prov, "reason": reason, "priority": i + 1})

    if not recommendations:
        recommendations.append({"provider": "local_llm", "reason": "fallback - no matching provider healthy", "priority": 1})

    return json.dumps({"ok": True, "providers": recommendations, "strategy": "multi_ai"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
#  2. Parallel Provider Queries (specialized prompts)
# ---------------------------------------------------------------------------

@mcp.tool()
async def provider_query(query: str, providers_json: str = "", timeout_seconds: int = 180) -> str:
    """Query multiple AI providers in parallel.

    Each provider receives a prompt specialized for its strengths.
    Returns collected responses from all successful providers.

    Args:
        query: The research question.
        providers_json: JSON array of provider objects (output from provider_select).
        timeout_seconds: Max total wait time.
    """
    if providers_json:
        try:
            provider_list = json.loads(providers_json)
            if isinstance(provider_list, dict) and "providers" in provider_list:
                provider_list = provider_list["providers"]
            selected = [p["provider"] if isinstance(p, dict) else p for p in (provider_list if isinstance(provider_list, list) else [])]
        except (json.JSONDecodeError, TypeError, KeyError):
            selected = ["local_llm", "perplexity"]
    else:
        selected = ["local_llm", "perplexity"]

    config = _load_llm_config()
    api_key = os.environ.get("OPENAI_API_KEY", "")

    async def _query_site(site: str, prompt: str) -> dict:
        if site not in SUPPORTED_SITES:
            return {"provider": site, "ok": False, "error": f"unsupported: {site}"}
        try:
            rt = await get_runtime()
            await rt.ensure_browser()
            await rt.navigate(site)
            result = await rt.query(site, prompt, timeout_seconds // max(len(selected), 1))
            if result.get("ok"):
                mark_success(site)
                return {"provider": site, "ok": True, "response": result["response"], "response_length": result.get("response_length", 0), "url": result.get("url", "")}
            error_detail = result.get("error", "").lower()
            if "rate" in error_detail:
                mark_failure(site, "rate_limited")
            elif "timeout" in error_detail or "unavailable" in error_detail:
                mark_failure(site, "down")
            return {"provider": site, "ok": False, "error": result.get("detail", result.get("error", "unknown"))}
        except Exception as e:
            return {"provider": site, "ok": False, "error": str(e)}

    async def _query_local(prompt: str) -> dict:
        resp = await asyncio.to_thread(_ask_local_llm, config, "You are a research assistant. Answer concisely with facts.", prompt)
        return {"provider": "local_llm", "ok": bool(resp), "response": resp[:50000], "error": "" if resp else "empty response"}

    async def _query_openai(prompt: str) -> dict:
        resp = await asyncio.to_thread(_ask_openai, api_key, "You are a research assistant. Answer comprehensively and cite sources.", prompt)
        return {"provider": "openai", "ok": bool(resp), "response": resp[:50000], "error": "" if resp else "empty response"}

    tasks = []
    for provider in selected:
        provider = provider.strip().lower()
        if provider not in _SPECIALIZED_PROMPTS:
            continue
        prompt = _SPECIALIZED_PROMPTS[provider](query)
        if provider == "local_llm":
            tasks.append(_query_local(prompt))
        elif provider == "openai":
            tasks.append(_query_openai(prompt))
        elif provider in ("perplexity", "chatgpt", "kimi", "duckduckgo"):
            tasks.append(_query_site(provider, prompt))

    if not tasks:
        return json.dumps({"ok": False, "error": "No providers could be selected"}, ensure_ascii=False)

    gathered = await asyncio.wait_for(asyncio.gather(*tasks), timeout=timeout_seconds)

    result = {"ok": True, "query": query[:200], "provider_count": len(gathered), "responses": []}
    for r in gathered:
        if not r.get("ok"):
            result["responses"].append({"provider": r["provider"], "ok": False, "error": r.get("error", "unknown")})
        else:
            facts = _extract_facts(r.get("response", ""))
            result["responses"].append({
                "provider": r["provider"], "ok": True,
                "response_preview": _strip_preambles(r.get("response", ""))[:2000],
                "response_length": r.get("response_length", 0),
                "facts": facts[:15],
            })

    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
#  3. Evidence Graph (structure responses into facts with sources)
# ---------------------------------------------------------------------------

@mcp.tool()
def evidence_graph(responses_json: str) -> str:
    """Build an evidence graph from provider responses.

    Each fact is connected to its source provider(s). Returns structured
    evidence nodes with provider attribution.
    """
    try:
        data = json.loads(responses_json) if isinstance(responses_json, str) else responses_json
    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps({"ok": False, "error": f"Invalid JSON: {e}"})

    evidence_nodes = []
    edges = []

    for resp in data.get("responses", []):
        provider = resp.get("provider", "unknown")
        if not resp.get("ok"):
            continue
        for fact in resp.get("facts", []):
            node_id = f"fact_{len(evidence_nodes) + 1}"
            evidence_nodes.append({
                "id": node_id,
                "statement": fact["statement"],
                "sources": [provider],
                "confidence": 0.0,
            })
            edges.append({"from": node_id, "to": provider, "type": "claimed_by"})

    merged = {}
    for node in evidence_nodes:
        key = node["statement"].lower().strip()[:100]
        if key in merged:
            merged[key]["sources"].append(node["sources"][0])
        else:
            merged[key] = node

    graph = {
        "ok": True,
        "evidence_count": len(merged),
        "provider_count": len(data.get("responses", [])),
        "nodes": list(merged.values()),
        "edges": edges[:50],
    }
    return json.dumps(graph, ensure_ascii=False)


# ---------------------------------------------------------------------------
#  4. Conflict Resolution
# ---------------------------------------------------------------------------

@mcp.tool()
def resolve_conflicts(evidence_json: str) -> str:
    """Detect and resolve conflicts in the evidence graph.

    Identifies statements that contradict each other, flags low-confidence
    claims, and produces a conflict report.
    """
    try:
        graph = json.loads(evidence_json) if isinstance(evidence_json, str) else evidence_json
    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps({"ok": False, "error": f"Invalid JSON: {e}"})

    nodes = graph.get("nodes", [])
    negation_words = {"not", "no", "never", "isn't", "wasn't", "don't", "doesn't", "cannot", "can't"}

    conflicts = []
    resolved = []
    for i, a in enumerate(nodes):
        a_key = a["statement"].lower().strip()[:80]
        a_has_neg = any(w in a_key.split() for w in negation_words)
        for j, b in enumerate(nodes):
            if j <= i:
                continue
            b_key = b["statement"].lower().strip()[:80]
            b_has_neg = any(w in b_key.split() for w in negation_words)
            shared = set(a_key.split()) & set(b_key.split())
            if (a_has_neg != b_has_neg) and len(shared) >= 2:
                conflicts.append({
                    "claim_a": a["statement"],
                    "claim_b": b["statement"],
                    "sources_a": a.get("sources", []),
                    "sources_b": b.get("sources", []),
                    "type": "direct_contradiction",
                })

    for node in nodes:
        vote_count = len(node.get("sources", []))
        resolved.append({
            "statement": node["statement"],
            "confidence": min(vote_count / 3, 1.0),
            "votes": vote_count,
            "sources": node.get("sources", []),
            "in_conflict": node["statement"] in [c.get("claim_a", "") or c.get("claim_b", "") for c in conflicts],
        })

    result = {
        "ok": True,
        "total_claims": len(nodes),
        "conflicts_found": len(conflicts),
        "conflicts": conflicts[:10],
        "resolved_claims": resolved,
    }
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
#  5. Fact Verification
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_facts(claims_json: str) -> str:
    """Verify factual claims against the local LLM and available sources.

    Each claim is evaluated and assigned a verdict: confirmed, contradicted,
    uncertain, or mixed. Multi-source claims get higher confidence.
    """
    try:
        claims = json.loads(claims_json) if isinstance(claims_json, str) else claims_json
    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps({"ok": False, "error": f"Invalid JSON: {e}"})

    if isinstance(claims, dict) and "resolved_claims" in claims:
        claims = claims["resolved_claims"]
    elif isinstance(claims, dict) and "nodes" in claims:
        claims = claims["nodes"]

    config = _load_llm_config()
    results = []

    for claim in (claims if isinstance(claims, list) else [{"statement": str(claims)}]):
        statement = claim.get("statement", "")
        if len(statement) < 20:
            continue
        prompt = f"Verify: \"{statement}\"\n\nReply with exactly one word then a newline then your reasoning:\nCONFIRMED / CONTRADICTED / UNCERTAIN / MIXED"
        response = _ask_local_llm(config, "You verify factual claims. Be strict: only CONFIRMED if the claim is clearly true.", prompt) or ""
        first_line = response.strip().split("\n")[0].upper()
        if "CONFIRMED" in first_line:
            verdict = "confirmed"
        elif "CONTRADICTED" in first_line:
            verdict = "contradicted"
        elif "MIXED" in first_line:
            verdict = "mixed"
        else:
            verdict = "uncertain"

        results.append({
            "statement": statement[:200],
            "verdict": verdict,
            "confidence": min(claim.get("confidence", 0.5) + (0.2 if verdict == "confirmed" else -0.2), 1.0),
            "sources": claim.get("sources", []),
        })

    return json.dumps({"ok": True, "verified_count": len(results), "verifications": results}, ensure_ascii=False)


# ---------------------------------------------------------------------------
#  6. Reasoning Synthesis
# ---------------------------------------------------------------------------

@mcp.tool()
def synthesize_reasoning(verified_json: str, query: str = "") -> str:
    """Synthesize verified evidence into a coherent reasoning chain.

    Takes verified facts, weights by confidence, and produces a structured
    reasoning trace: premise → evidence → conclusion.
    """
    try:
        verified = json.loads(verified_json) if isinstance(verified_json, str) else verified_json
    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps({"ok": False, "error": f"Invalid JSON: {e}"})

    verifications = verified.get("verifications", []) if isinstance(verified, dict) else verified

    confirmed = [v for v in verifications if v.get("verdict") == "confirmed"]
    uncertain = [v for v in verifications if v.get("verdict") == "uncertain"]
    contradicted = [v for v in verifications if v.get("verdict") == "contradicted"]

    reasoning_steps = []
    reasoning_steps.append({"step": "premises", "detail": f"{len(confirmed)} confirmed facts available"})

    if confirmed:
        top = sorted(confirmed, key=lambda v: v.get("confidence", 0), reverse=True)[:5]
        reasoning_steps.append({"step": "evidence", "detail": f"Top evidence: {'. '.join(c['statement'] for c in top)}"})

    if contradicted:
        reasoning_steps.append({"step": "contradictions", "detail": f"{len(contradicted)} claims contradicted — excluded from answer"})

    if uncertain:
        reasoning_steps.append({"step": "uncertainties", "detail": f"{len(uncertain)} claims uncertain — marked as low confidence"})

    result = {
        "ok": True,
        "reasoning_steps": reasoning_steps,
        "confirmed_count": len(confirmed),
        "uncertain_count": len(uncertain),
        "contradicted_count": len(contradicted),
    }
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
#  7. Self-Critique
# ---------------------------------------------------------------------------

@mcp.tool()
def self_critique(reasoning_json: str, query: str = "") -> str:
    """Critique the reasoning chain for gaps, errors, or overconfidence.

    Returns quality scores and improvement suggestions.
    """
    try:
        reasoning = json.loads(reasoning_json) if isinstance(reasoning_json, str) else reasoning_json
    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps({"ok": False, "error": f"Invalid JSON: {e}"})

    config = _load_llm_config()
    confirmed = reasoning.get("confirmed_count", 0)
    uncertain = reasoning.get("uncertain_count", 0)
    contradicted = reasoning.get("contradicted_count", 0)

    prompt = f"""Evaluate this research result:

- Confirmed claims: {confirmed}
- Uncertain claims: {uncertain}
- Contradicted claims: {contradicted}
- Query: {query or "N/A"}

Score each from 0-10 and explain briefly:
1. Factual accuracy (do confirmed claims seem reliable?)
2. Completeness (are there obvious gaps?)
3. Uncertainty handling (are uncertain claims flagged?)
4. Overall quality"""

    critique = _ask_local_llm(config, "You critique research quality. Be honest and specific. Output scores and reasoning.", prompt) or ""

    result = {
        "ok": True,
        "critique": critique[:2000],
        "scores": {},
    }
    for line in critique.split("\n"):
        m = re.match(r"(\d+\.?\s*)?(\w[\w\s]+):\s*(\d+)/10", line)
        if m:
            result["scores"][m.group(2).strip()] = int(m.group(3))

    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
#  8. Final Answer
# ---------------------------------------------------------------------------

@mcp.tool()
def final_answer(critique_json: str, query: str = "") -> str:
    """Generate the final answer text from the research pipeline output.

    Combines the reasoning chain, critique feedback, and query into a
    polished answer with appropriate confidence indicators.
    """
    try:
        critique = json.loads(critique_json) if isinstance(critique_json, str) else critique_json
    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps({"ok": False, "error": f"Invalid JSON: {e}"})

    config = _load_llm_config()
    scores = critique.get("scores", {})
    avg_score = sum(scores.values()) / len(scores) if scores else 0

    prompt = f"""Generate a final answer for this query.
Critique scores: {scores}
Average quality: {avg_score:.1f}/10
Critique: {critique.get('critique', '')[:500]}
Query: {query or 'N/A'}

Guidelines:
- If avg quality < 5, add a confidence warning at the top
- Cite sources where possible
- Flag any uncertain claims
- Be concise"""

    answer = _ask_local_llm(config, "You generate final research answers. Be accurate, balanced, and honest about uncertainty.", prompt) or ""

    result = {
        "ok": True,
        "answer": answer[:10000],
        "quality_score": avg_score,
        "needs_warning": avg_score < 5,
    }
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
#  Status
# ---------------------------------------------------------------------------

@mcp.tool()
def multi_ai_status() -> str:
    """Check which AI research providers are available and their capabilities."""
    available = []
    config = _load_llm_config()
    try:
        import httpx
        resp = httpx.get(f"{config['base_url']}/api/tags", timeout=5)
        if resp.is_success:
            available.append("local_llm")
    except Exception:
        pass

    runner_check = _run_runner(["--check"], 15)
    if runner_check.get("ok"):
        available.append("perplexity (web)")
        available.append("duckduckgo (web)")

    if os.environ.get("OPENAI_API_KEY", ""):
        available.append("openai (api)")

    from igris.core.provider_router import get_capabilities
    return json.dumps({"ok": True, "available_providers": available, "capabilities": _PROVIDER_CAPABILITIES, "provider_router": get_capabilities()}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
