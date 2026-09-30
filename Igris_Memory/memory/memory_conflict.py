"""
Roadmap v4 Phase A1 — MEMORY CONFLICT + LAYER PRIORITY + RELEVANCE FILTER
=========================================================================
v1 §5 qoldiqlari (Roadmap v4 Protocol 100):
  - Contradiction detection: "X bor" + "X yo'q" pattern'lari → [CONFLICT]
  - Layer priority ranking: L1 (runtime) > L2 (persistent) bonus
  - Task-relevance filter: score + threshold — aloqasiz natijalar chiqariladi

Falsafa: HAMMASI DETERMINISTIK (LLM yo'q) — 0 xarajat, ~ms, testlanadigan.
Qaytish formatlari retrieval.py natijalariga mos (score/source/metadata).

Detectable contradiction patterns (UZ/EN aralash):
  "X bor" vs "X yo'q", "X mavjud" vs "X mavjud emas", "is defined" vs
  "is not defined", "works" vs "doesn't work", "installed" vs "not installed",
  "true" vs "false" (bir xil kalit uchun), "+X" vs "-X" statuslar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = [
    "ConflictPair", "detect_contradictions", "mark_conflicts",
    "apply_layer_priority", "filter_relevant",
]

# ---------------------------------------------------------------------- #
# 1) CONTRADICTION DETECTION
# ---------------------------------------------------------------------- #

# Har element: (positive_pattern, negative_pattern) — bir juftlik qarama-qarshi
_CONTRADICTION_PAIRS: list[tuple[str, str]] = [
    (r"\b(\S+)\s+bor\b", r"\b(\S+)\s+yo'q\b"),                    # uz: bor / yo'q
    (r"\b(\S+)\s+mavjud\b", r"\b(\S+)\s+mavjud\s+emas\b"),        # uz: mavjud / emas
    (r"\bis\s+installed\b", r"\bis\s+not\s+installed\b"),         # en
    (r"\bis\s+defined\b", r"\bis\s+not\s+defined\b"),             # en
    (r"\bworks?\b", r"\b(?:does\s+not|doesn't)\s+work\b"),        # en
    (r"\bis\s+enabled\b", r"\bis\s+disabled\b"),                  # en
    (r"\bexists\b", r"\b(?:does\s+not|doesn't)\s+exist\b"),       # en
    (r"\bis\s+complete[d]?\b", r"\bis\s+(?:not\s+)?incomplete\b"),  # en
    (r"\bpassed\b", r"\bfailed\b"),                               # test holati
]

# Kalit-so'z asosida: bir xil subyektga true/false hukm.
# Subyekt: nuqtali kalit (cache.enabled) — OXIRGI qism emas, TO'LIQ kalit olindi.
_TRUE_FALSE_RE = re.compile(
    r"(?P<subject>[\w\-]+(?:\.[\w\-]+)+|[\w\-]{2,40}):\s*(?P<value>true|false)\b",
    re.IGNORECASE)


@dataclass
class ConflictPair:
    """Ikki yozuv orasidagi aniqlangan qarama-qarshilik."""
    subject: str                  # qarama-qarshilik predmeti (taxminiy)
    positive_text: str
    negative_text: str
    positive_source: str = ""
    negative_source: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "positive": self.positive_text,
            "negative": self.negative_text,
            "positive_source": self.positive_source,
            "negative_source": self.negative_source,
            "reason": self.reason,
        }


def _extract_statements(text: str) -> list[str]:
    """Matndan gap (statement) bo'laklarini ajratadi.

    Diqqat: `.` faqat GAP oxirida kesadi — kalit ichidagi nuqta
    (cache.enabled) buzilmasligi uchun nuqtadan keyin PROBEL bo'lsa kesiladi.
    """
    parts = re.split(r"(?:(?<=\s)[.;]|;|\n)|\.\s+", str(text or ""))
    return [p.strip() for p in parts if p.strip()]


def detect_contradictions(items: list[dict]) -> list[ConflictPair]:
    """Yozuvlar ro'yxatida qarama-qarshiliklarni aniqlaydi.

    items: [{text, source?}] — har yozuv matni + manba (ixtiyoriy).
    O(n²) juftlik solishtirish — top_k ≤ 20 uchun juda tez.

    Qaytadi: [ConflictPair, ...] (bo'sh — qarama-qarshilik yo'q).
    """
    conflicts: list[ConflictPair] = []
    stmts: list[tuple[int, str, str]] = []   # (item_idx, statement, source)
    for idx, it in enumerate(items or []):
        text = str((it or {}).get("text", ""))
        src = str((it or {}).get("source", ""))
        for st in _extract_statements(text):
            stmts.append((idx, st, src))

    for i in range(len(stmts)):
        for j in range(i + 1, len(stmts)):
            _, a, a_src = stmts[i]
            _, b, b_src = stmts[j]
            low_a, low_b = a.lower(), b.lower()
            # true/false bir xil subyektga
            for m_a in _TRUE_FALSE_RE.finditer(low_a):
                for m_b in _TRUE_FALSE_RE.finditer(low_b):
                    if (m_a.group("subject") == m_b.group("subject")
                            and m_a.group("value") != m_b.group("value")):
                        conflicts.append(ConflictPair(
                            subject=m_a.group("subject"),
                            positive_text=a, negative_text=b,
                            positive_source=a_src, negative_source=b_src,
                            reason="true vs false bir xil kalit uchun"))
            # pattern juftliklari
            for pos_pat, neg_pat in _CONTRADICTION_PAIRS:
                a_pos = re.search(pos_pat, low_a)
                a_neg = re.search(neg_pat, low_a)
                b_pos = re.search(pos_pat, low_b)
                b_neg = re.search(neg_pat, low_b)
                # a pozitiv, b negativ (yoki aksincha)
                if a_pos and b_neg:
                    subj = (a_pos.group(1) if a_pos.groups() else a_pos.group(0))
                    conflicts.append(ConflictPair(
                        subject=subj, positive_text=a, negative_text=b,
                        positive_source=a_src, negative_source=b_src,
                        reason=f"pattern: {pos_pat[:24]} vs {neg_pat[:24]}"))
                elif a_neg and b_pos:
                    subj = (b_pos.group(1) if b_pos.groups() else b_pos.group(0))
                    conflicts.append(ConflictPair(
                        subject=subj, positive_text=b, negative_text=a,
                        positive_source=b_src, negative_source=a_src,
                        reason=f"pattern: {pos_pat[:24]} vs {neg_pat[:24]}"))
    # dedup (bir xil juftlik bir necha pattern'da topilishi mumkin)
    seen: set = set()
    unique: list[ConflictPair] = []
    for c in conflicts:
        key = (c.positive_text[:60], c.negative_text[:60])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def mark_conflicts(results: list[dict]) -> list[dict]:
    """Search natijalarini [CONFLICT] bilan belgilaydi (o'zgartirilgan nusxa).

    results: [{text?, content?, score, source?, metadata?}, ...]
    Har result'ga qo'shiladi: conflict=True + conflicts=[ConflictPair.to_dict()]
    """
    if not results:
        return results
    items = []
    for r in results:
        text = str(r.get("text") or r.get("content") or "")
        items.append({"text": text,
                      "source": str(r.get("source")
                                    or (r.get("metadata") or {}).get("source", ""))})
    pairs = detect_contradictions(items)
    if not pairs:
        return results
    conflicted_idx: set = set()
    # item index'larni qayta quramiz (detect_contradictions bilan bir xil tartib)
    idx_map = []
    for idx, it in enumerate(items):
        n = max(1, len(_extract_statements(it["text"])))
        idx_map.extend([idx] * n)
    for c in pairs:
        # source orqali qaysi item ekanini topamiz
        for k, it in enumerate(items):
            if c.positive_text in it["text"]:
                conflicted_idx.add(k)
            if c.negative_text in it["text"]:
                conflicted_idx.add(k)
    out = []
    for k, r in enumerate(results):
        if k in conflicted_idx:
            r2 = dict(r)
            r2["conflict"] = True
            r2["conflicts"] = [c.to_dict() for c in pairs
                               if c.positive_source == items[k]["source"]
                               or c.negative_source == items[k]["source"]
                               or not items[k]["source"]]
            out.append(r2)
        else:
            out.append(r)
    return out


# ---------------------------------------------------------------------- #
# 2) LAYER PRIORITY — L1 (runtime) > L2 (persistent) > retrieval
# ---------------------------------------------------------------------- #

_LAYER_BONUS = {"l1": 0.30, "runtime": 0.30, "l2": 0.15, "persistent": 0.15,
                "retrieval": 0.0}


def apply_layer_priority(results: list[dict]) -> list[dict]:
    """Natijalarga layer bonus qo'shib, qayta saralaydi.

    Qoida: final_score = score + layer_bonus; TENG BO'LGANDA L1 yuqorida
    (subyektiv tartib barqaror bo'lishi uchun — L1 > L2 > retrieval qat'iy).
    """
    out = []
    for r in (results or []):
        r2 = dict(r)
        layer = str(r2.get("layer") or r2.get("source") or "").lower()
        bonus = 0.0
        for key, b in _LAYER_BONUS.items():
            if key in layer:
                bonus = b
                break
        r2["layer_bonus"] = bonus
        r2["final_score"] = float(r2.get("score") or 0.0) + bonus
        out.append(r2)
    # Score teng bo'lganda LAYER DARAJASI yuqori biri birinchi
    layer_rank = {"l1": 2, "runtime": 2, "l2": 1, "persistent": 1,
                  "retrieval": 0}

    def _rank(r: dict) -> int:
        layer = str(r.get("layer") or r.get("source") or "").lower()
        for key, rk in layer_rank.items():
            if key in layer:
                return rk
        return 0

    out.sort(key=lambda x: (x.get("final_score", 0.0), _rank(x)),
             reverse=True)
    return out


# ---------------------------------------------------------------------- #
# 3) RELEVANCE FILTER — task-aloqasizlikni chiqarish
# ---------------------------------------------------------------------- #

_STOP_WORDS = {"the", "a", "an", "va", "bilan", "uchun", "bu", "shu",
               "and", "or", "of", "in", "on", "to", "is", "are", "was"}


def _keywords(text: str) -> set:
    low = re.sub(r"[^\w\s]", " ", str(text or "").lower())
    return {w for w in low.split()
            if len(w) >= 3 and w not in _STOP_WORDS}


def filter_relevant(results: list[dict], task: str,
                    min_score: float = 0.05,
                    min_overlap: float = 0.15,
                    keep: int = 5) -> list[dict]:
    """Task bilan aloqasiz natijalarni chiqaradi.

    Qoidalar (har natija uchun):
      1. score >= min_score BO'LISHI SHART (absolyut chegara)
      2. keyword overlap >= min_overlap (task keywords ∩ natija keywords)
         — lekin overlap'i past bo'lsa ham score juda baland bo'lsa SAQLANADI
    keep: ko'pi bilan shuncha natija (top_k).

    Qaytadi: (filtered_results, dropped_count).
    """
    task_kw = _keywords(task)
    kept, dropped = [], 0
    for r in (results or []):
        score = float(r.get("final_score", r.get("score") or 0.0))
        if score < min_score:
            dropped += 1
            continue
        text = str(r.get("text") or r.get("content") or "")
        r_kw = _keywords(text)
        if task_kw and r_kw:
            overlap = len(task_kw & r_kw) / len(task_kw)
        else:
            overlap = 0.0
        if overlap >= min_overlap or score >= 0.5:
            kept.append({**r, "relevance": round(overlap, 3)})
        else:
            dropped += 1
    return kept[:keep], dropped
