"""
IGRIS BRAIN — 2nd Brain Graph Builder
=====================================
Igris_Memory'dan (Obsidian vault + L2 persistent JSONL) REAL ma'lumotlar
xaritasini (knowledge graph) quradi.

Manbalar:
  1. Igris_Memory/*.md  — Obsidian vault fayllari (L1/L2 turlari, index, wiki)
  2. [[wikilinks]]       — fayllar orasidagi haqiqiy bog'lanishlar
  3. brain_data/persistent/*.jsonl — L2 yozuvlar (solution, experience, fact,
     pattern, ...) — har bir yozuv alohida node bo'ladi
  4. brain_data/runtime/*.jsonl     — L1 short-turn/session yozuvlar

Chiqish formati (frontend BrainView'ga mos):
    {
      "ok": true,
      "nodes": [{id, label, kind, x, y, detail}],
      "links": [[srcId, dstId], ...],
      "stats": {vault_files, persistent_entries, runtime_entries, nodes, links}
    }

kind: 'architecture' | 'pattern' | 'fact' | 'session'  (web/colors.ts mos)
Layout: kind bo'yicha radial qatlamlar (deterministik, tez).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import time
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
# 2nd_brain/backend/ -> loyiha ildizi (Igris_Memory, Igris_brain birga turibdi)
PROJECT_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MEMORY_ROOT = os.path.join(PROJECT_ROOT, "Igris_Memory")
BRAIN_DATA = os.path.join(MEMORY_ROOT, "brain_data")

# REAL chat tarixi (server /api/chat orqali yoziladi) — grafikda session node'lar
# fayl Igris_brain/ da qoladi (server ChatHistory ham shu faylni ishlatadi).
CHAT_HISTORY_PATH = os.path.join(PROJECT_ROOT, "Igris_brain", "chat_history.jsonl")
# O'chirilgan suhbat id'lari (server ChatHistory tombstone fayli) — o'chirilgan
# suhbatlar grafda session node bo'lib qolmasligi uchun shu yerdan ham o'qiladi.
CHAT_HISTORY_TOMB_PATH = CHAT_HISTORY_PATH + ".deleted.json"

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def _read_tail_lines(path: str, n: int) -> list[str]:
    """Faylning OXIRGI n qatorini to'liq faylni o'qimay qaytaradi (chunked).

    Part N: katta chat_history.jsonl / JSONL xotira fayllari o'qilganda butun
    fayl xotiraga yuklanmaydi — oxiridan 8KB bloklar bilan o'qib, kerakli
    qatorlar yig'iladi. Bo'sh qatorlar filtrlanadi (eski `ln.strip()` mantiqi).
    """
    lines: list[str] = []
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            pos = fh.tell()
            buf = b""
            while pos > 0 and len(lines) < n:
                chunk = min(8192, pos)
                pos -= chunk
                fh.seek(pos)
                buf = fh.read(chunk) + buf
                lines = [ln for ln in buf.decode("utf-8", errors="ignore").split("\n") if ln.strip()]
            return lines[-n:]
    except OSError:
        return []

# Fayl nomi -> kind (frontend colors.ts dagi toifalarga mos)
VAULT_KIND_RULES = [
    ("pattern", ("pattern", "skill", "workflow", "solution", "experience", "execution")),
    ("fact", ("fact", "knowledge", "example", "research", "rule", "verification")),
    ("session", ("session", "log", "decision", "scratch", "prompt", "observation", "plan")),
]
DEFAULT_VAULT_KIND = "architecture"

# L2 JSONL turi -> kind
L2_KIND = {
    "solution-memory": "pattern",
    "experience": "pattern",
    "pattern": "pattern",
    "workflow-memory": "pattern",
    "fact": "fact",
    "knowledge": "fact",
    "example": "fact",
    "research": "fact",
    "rule": "fact",
    "verification": "fact",
    "project": "architecture",
    "code-map": "architecture",
    "integration": "architecture",
    "documentation": "architecture",
    "skill": "pattern",
    "user-model": "fact",
    "performance": "pattern",
    "security": "fact",
    "error": "fact",
    "long-term": "fact",
    "test": "fact",
}
DEFAULT_L2_KIND = "fact"

# Radar layout o'lchamlari (viewBox 620x380 ga mos — x:0..620, y:0..380)
RADIUS = {"architecture": 45, "pattern": 100, "fact": 140, "session": 175}
CENTER = (310, 185)


def _kind_for_filename(name: str) -> str:
    low = name.lower()
    for kind, keywords in VAULT_KIND_RULES:
        if any(k in low for k in keywords):
            return kind
    return DEFAULT_VAULT_KIND


def _label_from_name(name: str) -> str:
    """'L1 - Active Context.md' -> 'Active Context', '07-solution' -> 'solution'."""
    base = os.path.basename(name)
    base = re.sub(r"\.md$", "", base)
    base = re.sub(r"^L[12]\s*-\s*", "", base)
    base = re.sub(r"^\d+[-_]\s*", "", base)
    return base.strip()[:40] or name


def _is_meaningful(text: str, min_chars: int = 60) -> bool:
    """Fayl/yozuvda HAQIQIY mazmun bormi?

    Bo'sh shablonlar (faqat sarlavha, "(bo'sh)", "..." yoki bir nechta
    belgili fayllar) grafni ifloslantirmasligi uchun filtrlanadi — faqat
    real ma'lumotli manbalar node bo'ladi.
    """
    if not text or not text.strip():
        return False
    # markdown sintaksisini va bo'sh so'zlarni olib tashlab, mazmun o'lchanadi
    cleaned = re.sub(r"[#>*\[\]`|~\-=_\s]", "", text)
    if len(cleaned) < min_chars:
        return False
    # shablon belgilari: "bo'sh", "template", "(empty)", "...", "Lorem"
    low = text.lower()
    if low.count("...") >= 3 or "lorem ipsum" in low:
        return False
    return True


def _is_junk_entry(content: str) -> bool:
    """Probe/benchmark yoki shovqin xotira yozuvlarini aniqlaydi.

    Igris_brain probe/benchmark run'larida agent-task yozuvlari xotiraga
    tushadi ("TASK: ... STATUS: ... STEPS: ... TOOLS: ..." shaklida) — ular
    grafda foydali bilim emas, shovqin. Bunday yozuvlar grafga kirmaydi
    (ma'lumotning o'zi saqlanadi).
    """
    c = (content or "").strip()
    if not c or len(c) < 30:
        return True
    low = c.lower()
    # "TASK: ..." bilan boshlanuvchi yozuvlar — agent-run jurnallari (probe/
    # benchmark shovqini), bilim emas. Ular grafga kirmaydi (o'zi saqlanadi).
    if low.startswith("task:"):
        return True
    if re.search(r"\bstatus:\s*(partial|stopped|error)\b", low) \
            and re.search(r"\bsteps?:\s*\d+\b", low):
        return True
    if re.search(r"\b(probe|benchmark|test run)\b", low) and len(c) < 120:
        return True
    return False


def _scan_vault_files() -> list[dict]:
    """Igris_Memory root'idagi .md fayllarni o'qiydi (bo'sh shablonlar filtrlanadi)."""
    nodes: list[dict] = []
    if not os.path.isdir(MEMORY_ROOT):
        return nodes
    for fname in sorted(os.listdir(MEMORY_ROOT)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(MEMORY_ROOT, fname)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read(4000)
        except OSError:
            continue
        # Bo'sh/template fayllar grafni ifloslantirmaydi — faqat real mazmun
        if not _is_meaningful(text):
            continue
        nodes.append({
            "id": f"vault:{fname}",
            "label": _label_from_name(fname),
            "kind": _kind_for_filename(fname),
            "detail": text.strip()[:160],
            "source": f"vault:{fname}",
            "text": text,
        })
    return nodes


def _load_deleted_chat_ids() -> set[str]:
    """O'chirilgan suhbat id'larini tombstone fayldan o'qiydi.

    ChatHistory server'da o'chirishda chat_history.jsonl.deleted.json'ga
    yozadi. Graf shu ro'yxatni ham tekshiradi — o'chirilgan suhbat session
    node bo'lib qolmaydi (fayl boshqa jarayon tomonidan eski holatda qayta
    yozilgan taqdirda ham).
    """
    if not os.path.isfile(CHAT_HISTORY_TOMB_PATH):
        return set()
    try:
        with open(CHAT_HISTORY_TOMB_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        # Yangi format: {id: o'chirilgan_vaqti}; eski format: [id1, id2]
        if isinstance(data, dict):
            return {str(k) for k in data if k}
        if isinstance(data, list):
            return {str(x) for x in data if x}
    except (OSError, json.JSONDecodeError):
        pass
    return set()


def _scan_chat_history(max_conv: int = 60) -> list[dict]:
    """Igris_brain/chat_history.jsonl — REAL chat suhbatlari node bo'ladi.

    Har bir suhbat 'session' kind bilan qo'shiladi; text = suhbat xabarlari,
    shuning uchun _semantic_links ularni xotira node'lari bilan bog'laydi.
    O'chirilgan (tombstone) suhbatlar grafga KIRITILMAYDI — suhbatni
    o'chirgach session node ham darhol yo'qoladi.
    """
    nodes: list[dict] = []
    if not os.path.isfile(CHAT_HISTORY_PATH):
        return nodes
    deleted_ids = _load_deleted_chat_ids()
    # Part N: to'liq fayl emas, OXIRGI max_conv qator (chunked o'qish) — katta
    # chat_history.jsonl'da butun fayl xotiraga olinmaydi.
    raw = _read_tail_lines(CHAT_HISTORY_PATH, max_conv)
    for line in raw[-max_conv:]:
        try:
            conv = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(conv, dict) or not conv.get("id"):
            continue
        if conv["id"] in deleted_ids:
            # o'chirilgan suhbat — session node bo'lmaydi
            continue
        msgs = conv.get("messages", []) or []
        text = " ".join(str(m.get("text", "")) for m in msgs if m.get("text"))
        text = text.strip()
        if not text:
            continue
        first_user = next((str(m.get("text", "")) for m in msgs if m.get("role") == "user"), "")
        label = (conv.get("title") or first_user or text)[:40]
        # Oxirgi yangilanish vaqti (epoch sekund) — frontend'da "qachon
        # yangilangan" ko'rsatiladi (nisbiy vaqt: "5 daqiqa oldin").
        updated_at = conv.get("updated_at") or conv.get("created_at") or 0
        try:
            updated_at = float(updated_at)
        except (TypeError, ValueError):
            updated_at = 0.0
        nodes.append({
            "id": f"chat:{conv['id']}",
            "label": label,
            "kind": "session",
            "detail": text[:220],
            "source": "chat",
            "text": text,
            "updated_at": updated_at,
        })
    return nodes


def _scan_jsonl_dir(dirpath: str, prefix: str, kind_map: dict,
                    limit_per_file: int = 8, seen: Optional[set[str]] = None,
                    id_seen: Optional[set[str]] = None) -> list[dict]:
    """JSONL yozuvlarini node'larga aylantiradi (semantic dedup bilan).

    `seen` seti tashqaridan uzatilishi mumkin — L1 va L2 bir xil content'ni
    (on_resolve ikkala qatlamga yozadi) takroriy node qilmaslik uchun umumiy
    dedup ishlatiladi.

    `id_seen` — yozuvning O'Z id'si bo'yicha dedup: bitta id bir necha marta
    (turli content bilan) yozilgan bo'lsa, birinchi yozuv node bo'ladi, qolganlari
    o'tkazib yuboriladi. Aks holda bir xil node id ikki marta paydo bo'lib,
    frontend React'da "duplicate key" ogohlantirishi beradi va graf noto'g'ri
    renderlanardi.
    """
    nodes: list[dict] = []
    if not os.path.isdir(dirpath):
        return nodes
    if seen is None:
        seen = set()
    if id_seen is None:
        id_seen = set()
    for fname in sorted(os.listdir(dirpath)):
        if not fname.endswith(".jsonl"):
            continue
        fpath = os.path.join(dirpath, fname)
        # Part N: to'liq fayl emas, OXIRGI limit_per_file qator (chunked) — katta
        # JSONL xotira fayllarida butun fayl o'qilmaydi.
        lines = _read_tail_lines(fpath, limit_per_file)
        entries = [ln for ln in lines if ln.strip()]
        for line in entries[-limit_per_file:]:  # eng so'nggilari
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            typ = entry.get("type") or ""
            content = str(entry.get("content") or entry.get("summary") or "")
            content = content.strip()
            if not content:
                continue
            # Probe/benchmark shovqini va juda qisqa yozuvlar — grafga kirmaydi
            if _is_junk_entry(content):
                continue
            # bir xil content'ni takrorlamaslik
            key = content[:60]
            if key in seen:
                continue
            seen.add(key)
            kind = kind_map.get(typ, DEFAULT_L2_KIND)
            label = content[:42].replace("\n", " ")
            # Yozuvning o'z id'si bo'lsa — shu id bo'yicha ham dedup (bir id
            # bir necha marta yozilgan bo'lishi mumkin). Id yo'q bo'lsa —
            # content-hash bilan BARQAROR id yaratamiz (len(seen) o'rniga,
            # chunki u boshqa fayldagi takroriy node'larga olib borishi mumkin;
            # `hash()` PYTHONHASHSEED tufayli jarayonlar orasida turg'un EMAS).
            nid = str(entry.get("id") or "")
            if not nid:
                nid = f"{prefix}:{typ}:{int(hashlib.sha256(content[:60].encode('utf-8')).hexdigest()[:8], 16)}"
            else:
                nid = f"{prefix}:{typ}:{nid}"
            if nid in id_seen:
                continue
            id_seen.add(nid)
            nodes.append({
                "id": nid,
                "label": label,
                "kind": kind,
                "detail": content[:220],
                "source": f"{prefix}:{typ}",
                "text": content,
            })
    return nodes


def _extract_wikilinks(nodes: list[dict]) -> dict[str, set[str]]:
    """Har bir node'ning wikilink maqsadlarini topadi (vault id -> id'lar)."""
    links: dict[str, set[str]] = {}
    # label -> id (wiki linklar fayl nomi bilan ko'rsatiladi)
    label_to_id = {n["label"]: n["id"] for n in nodes}
    for n in nodes:
        targets: set[str] = set()
        for m in WIKILINK_RE.finditer(n.get("text", "")):
            target = m.group(1).strip()
            tid = label_to_id.get(target) or label_to_id.get(_label_from_name(target))
            if tid and tid != n["id"]:
                targets.add(tid)
        if targets:
            links[n["id"]] = targets
    return links


def _shared_words(nodes: list[dict]) -> dict[str, set[str]]:
    """Har node uchun so'z to'plami — link sababini ("nima uchun bog'langan")
    ko'rsatish uchun: ikkita bog'langan node'ning umumiy so'zlari = sabab.

    Frontend zoom qilganda linklarning sababini ko'rsatadi: umumiy so'zlar
    qancha ko'p bo'lsa, node'lar shunchalik yaqin/semantik bog'liq.
    """
    tokens: dict[str, set[str]] = {}
    for n in nodes:
        words = set(re.findall(r"[a-z0-9]{4,}", n.get("text", "").lower()))
        # xizmatchi so'zlarni olib tashlaymiz — faqat mazmunli umumiy so'zlar
        tokens[n["id"]] = words - {
            "this", "that", "with", "from", "have", "were", "will", "would",
            "should", "which", "their", "there", "about", "into", "over",
            "memory", "igris", "build", "l2", "l1", "type", "summary", "user",
        }
    return tokens


def _semantic_links(nodes: list[dict], wikilinks: dict[str, set[str]],
                    max_semantic: int = 40, max_chat_links: int = 4) -> list[tuple[str, str]]:
    """Wikilinklar + umumiy so'zlar asosida bog'lanishlar.

    Avval haqiqiy wikilinklar (cheklanmagan), keyin semantic (umumiy so'zlar)
    juftliklari — semantic qo'shimchalar soni `max_semantic` bilan cheklanadi
    (wikilinklar ko'p bo'lsa ham semantic linklar ham qo'shilaveradi).

    Chat node'lari alohida qoida oladi: qisqa suhbat matnlari >=2 umumiy so'z
    chegarasiga yetmasligi mumkin, shuning uchun ular kamida 1 umumiy so'z
    bo'lsa eng yaqin xotira node'lariga (har biriga max_chat_links) bog'lanadi
    — real chat tarixi grafikda yakkalanib qolmaydi.
    """
    edges: set[tuple[str, str]] = set()
    id_set = {n["id"] for n in nodes}

    def _add(a: str, b: str):
        key = tuple(sorted((a, b)))
        if key[0] in id_set and key[1] in id_set:
            edges.add(key)

    # 1) Wikilinklar (hammasi — haqiqiy bog'lanishlar)
    for src, targets in wikilinks.items():
        for t in targets:
            _add(src, t)

    # 2) Semantic: umumiy so'zlar — allaqachon bog'langan juftlikni qayta
    #    qo'shmaydi, wikilinklar ko'p bo'lsa ham o'z limiti bilan ishlaydi.
    tokens: list[tuple[str, set[str]]] = []
    for n in nodes:
        words = set(re.findall(r"[a-z0-9]{4,}", n.get("text", "").lower()))
        tokens.append((n["id"], words))

    scored: list[tuple[int, str, str]] = []
    for i in range(len(tokens)):
        for j in range(i + 1, len(tokens)):
            a_id, a_tok = tokens[i]
            b_id, b_tok = tokens[j]
            common = a_tok & b_tok
            if len(common) >= 2:  # kamida 2 umumiy so'z
                scored.append((len(common), a_id, b_id))
    scored.sort(reverse=True)
    added_semantic = 0
    for _, a, b in scored:
        if added_semantic >= max_semantic:
            break
        key = tuple(sorted((a, b)))
        if key not in edges:
            edges.add(key)
            added_semantic += 1

    # 3) Chat node'lari: kamida 1 umumiy so'z bo'lsa eng yaqin node'larga bog'laymiz
    tokens_by_id = dict(tokens)
    chat_ids = {n["id"] for n in nodes if n.get("source") == "chat"}
    for cid in chat_ids:
        chat_tokens = tokens_by_id[cid]
        ranked: list[tuple[int, str]] = []
        for other_id, other_tok in tokens_by_id.items():
            if other_id == cid or other_id in chat_ids:
                continue
            common = chat_tokens & other_tok
            if common:
                ranked.append((len(common), other_id))
        ranked.sort(reverse=True)
        added_chat = 0
        for _, other in ranked:
            if added_chat >= max_chat_links:
                break
            key = tuple(sorted((cid, other)))
            if key not in edges:
                edges.add(key)
                added_chat += 1

    return sorted(edges)


def _link_reasons(nodes: list[dict], links: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Har bir link uchun sabab: node'lar orasidagi umumiy so'zlar (eng 6 tasi).

    Key: 'srcId|dstId' (har doim tartiblangan — frontend ikkala yo'nalishda
    ham topa oladi). Frontend zoom/tooltip'da ko'rsatadi: "Nima uchun
    bog'langan: soz1, soz2...".
    """
    tokens = _shared_words(nodes)
    reasons: dict[str, list[str]] = {}
    for a, b in links:
        common = sorted(tokens.get(a, set()) & tokens.get(b, set()))[:6]
        if common:
            key = f"{a}|{b}"
            reasons[key] = common
    return reasons


def _stable_blend(sources: list[list[dict]], max_nodes: int, shares: list[float]) -> list[dict]:
    """Kvotali barqaror aralashtirish — chegara yaqinida churn = 0.

    Har bir manba o'z ulushiga (share) ega: `quota = round(max_nodes * share)`.
    Manbalar o'z kvotalari doirasida navbatma-navbat qo'shiladi — bitta manba
    o'sib o'z kvotasini to'ldirsa, FAQAT O'ZINING eng eski node'lari tushadi,
    boshqa manbalarga tegmaydi.

    Ilgari bitta umumiy interleave barcha manbalarni aralashtirib, bitta manba
    o'sganda boshqalarning ham qaysi node'lari saqlanishini siljitar edi — graf
    'sakrar', node'lar bir ko'rinib bir ko'rinmasdi. Endi har manba o'z
    rezervlangan ulushiga ega: chat o'ssa, persistent/runtime node'lari
    qisqarmaydi (faqat chat'ning o'zi, o'z eskilari hisobiga).
    """
    # `shares` yig'indisi 1.0 bo'lishi shart (kvotalar max_nodes'ni to'ldiradi).
    quotas = [max(1, int(max_nodes * s)) for s in shares]
    # Har manbadan ENG SO'NGGI (eng yangi) node'lar olinadi — `[-q:]` oyna
    # yangi yozuv kelganda eskilarni eskiradi, yangilarini doim saqlaydi.
    # Atayin: kvotasidan kichik manba bo'sh joyni BOSHQA manbaga bermaydi —
    # redistributsiya churn'ni qaytarib kelardi, bo'sh slotlar qolishi to'g'ri.
    capped = [src[-q:] for src, q in zip(sources, quotas)]
    out: list[dict] = []
    idx = [0] * len(capped)
    while len(out) < max_nodes:
        moved = False
        for i, nodes in enumerate(capped):
            if idx[i] < len(nodes) and len(out) < max_nodes:
                out.append(nodes[idx[i]])
                idx[i] += 1
                moved = True
        if not moved:
            break
    return out


def _layout(nodes: list[dict]) -> dict[str, tuple[float, float]]:
    """kind bo'yicha radial qatlamlar — deterministik joylashuv."""
    pos: dict[str, tuple[float, float]] = {}
    buckets: dict[str, list[dict]] = {}
    for n in nodes:
        buckets.setdefault(n["kind"], []).append(n)
    for kind, group in buckets.items():
        r = RADIUS.get(kind, 150)
        n = len(group)
        for i, node in enumerate(group):
            if n == 1:
                ang = 0.0
            else:
                ang = 2 * math.pi * i / n
            pos[node["id"]] = (
                round(CENTER[0] + r * math.cos(ang), 1),
                round(CENTER[1] + r * math.sin(ang), 1),
            )
    return pos


DEFAULT_SHARES = [0.35, 0.25, 0.20, 0.20]
"""Kvota ulushlari: [vault, chat, persistent, runtime] — yig'indisi 1.0.

2nd Brain sozlamalar panelidan UI'da sozlanadi (server 'shares' query
parametrini qabul qiladi). Yig'indi 1.0 bo'lmasa normalize qilinadi.
"""


def normalize_shares(shares: Optional[list]) -> list[float]:
    """Ulushlarni xavfsiz normallashtiradi (yig'indi 1.0, manfiy/0 dan katta).

    Noto'g'ri qiymatlar (bo'sh, manfiy, yig'indi 0) defaultga qaytadi.
    """
    if not shares or len(shares) != 4:
        return list(DEFAULT_SHARES)
    try:
        # NaN/inf (URL orqali yuborilishi mumkin) — _stable_blend'da int()
        # ValueError berib 500'ga olib borardi. Eslatma: `max(0.0, nan)`
        # Python'da nan'ni 0.0 ga aylantiradi, shuning uchun isfinite
        # tekshiruvini clamp'dan OLDIN raw qiymatda qilamiz.
        raw = [float(x) for x in shares]
        if not all(math.isfinite(v) for v in raw):
            return list(DEFAULT_SHARES)
        vals = [max(0.0, v) for v in raw]
    except (TypeError, ValueError):
        return list(DEFAULT_SHARES)
    total = sum(vals)
    if total <= 0:
        return list(DEFAULT_SHARES)
    return [v / total for v in vals]


# Sezilarli-o'zgarish fingerprint kesh: fayl -> (mtime, size, natija).
# Fayl o'zgarmagan bo'lsa har 8 soniyalik poll'da qayta o'qilmaydi — polling
# eski stat()-yalik (engil) xususiyatini saqlaydi, I/O ortiqcha yuklanmaydi.
_FP_CACHE: dict[str, tuple[float, int, object]] = {}


def _fp_cached_line_count(path: str) -> int:
    """Fayl qatorlarini (mtime, size) kesh bilan hisoblaydi.

    Kesh o'zgarmagan fayl uchun qayta o'qishni oldini oladi; fayl
    o'zgarganda (yangi L2 yozuv) qayta sanaydi va keshlaydi.
    """
    try:
        st = os.stat(path)
        key = (st.st_mtime, st.st_size)
    except OSError:
        return 0
    cached = _FP_CACHE.get(path)
    if cached is not None and cached[:2] == key:
        return int(cached[2])
    n = 0
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            n = sum(1 for _ in fh)
    except OSError:
        n = 0
    _FP_CACHE[path] = (st.st_mtime, st.st_size, n)
    return n


def _tombstone_part(chat_path: str) -> Optional[str]:
    """Tombstone (o'chirilgan suhbatlar) imzosi — barqaror, shovqinsiz.

    Yangi suhbat o'chirilishi -> eng so'nggi o'chirish vaqti (max_ts) o'zgaradi
    -> versiya siljiydi. Eski (muddati o'tgan) tombstone'larni tozalash (prune)
    esa FAQAT eng ESKI yozuvlarni olib tashlaydi — max_ts'ga tegmaydi, shuning
    uchun shovqinli reload bo'lmaydi (raw mtime'dan farqli: mtime har qanday
    qayta yozishda o'zgarardi).
    """
    tomb = chat_path + ".deleted.json"
    try:
        st = os.stat(tomb)
    except OSError:
        return None
    cache_key = "tomb:" + chat_path
    cached = _FP_CACHE.get(cache_key)
    if cached is not None and cached[:2] == (st.st_mtime, st.st_size):
        return str(cached[2])
    max_ts = 0.0
    try:
        with open(tomb, "r", encoding="utf-8", errors="ignore") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            vals = [float(v) for v in data.values()
                    if isinstance(v, (int, float))]
            if vals:
                max_ts = max(vals)
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    part = f"tomb:{int(max_ts)}"
    _FP_CACHE[cache_key] = (st.st_mtime, st.st_size, part)
    return part


def _chat_fingerprint(chat_path: str) -> list[str]:
    """Suhbat darajasidagi imzo — (id, title) juftliklari + tombstone.

    SEZILARLI (versiyani o'zgartiradi):
      - yangi suhbat ochildi  (yangi id -> grafda yangi session node)
      - suhbat o'chirildi     (tombstone fayli -> node yo'qoladi)
      - suhbat nomi o'zgardi  (rename -> node sarlavhasi yangilanadi)

    SHOVQIN (versiyani o'zgartirmaydi):
      - mavjud suhbatga yangi XABAR qo'shildi — node TO'PLAMI bir xil
        qoladi (id va nom o'zgarmadi). Chat davomida graf turg'un turadi.

    Tez ishlash uchun to'liq JSON parse emas, id/title maydonlari regex
    bilan olinadi; (mtime, size) kesh tufayli fayl o'zgarmagan poll'lar
    faylni qayta o'qimaydi.
    """
    parts: list[str] = []
    try:
        if os.path.isfile(chat_path):
            st = os.stat(chat_path)
            cache_key = "chat:" + chat_path
            cached = _FP_CACHE.get(cache_key)
            if cached is not None and cached[:2] == (st.st_mtime, st.st_size):
                parts = list(cached[2])  # type: ignore[arg-type]
            else:
                with open(chat_path, "r", encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        m_id = re.search(r'"id"\s*:\s*"([^"]*)"', line)
                        if not m_id:
                            continue
                        m_title = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', line)
                        parts.append(f"{m_id.group(1)}|{m_title.group(1) if m_title else ''}")
                _FP_CACHE[cache_key] = (st.st_mtime, st.st_size, list(parts))
        # O'chirilgan suhbatlar (tombstone) — o'chirish grafda node yo'qolishini
        # bildiradi, shuning uchun versiyaga kiradi (max_ts asosida — prune shovqini yo'q).
        tomb_part = _tombstone_part(chat_path)
        if tomb_part:
            parts.append(tomb_part)
    except OSError:
        pass
    return parts


# Fingerprint uchun oxirgi holat: (memory_root, brain_data, chat_path) ->
# (parts, so'nggi_o'zgarish_vaqti). Server har poll'da oldingi holat bilan
# solishtirib, o'zgarish SABABI va VAQTINI chiqaradi (frontend "graf nega va
# qachon yangilandi"ni ko'rsatadi). Kalit manbalar to'plami — turli root'lar
# (test/repo) bir-biriga aralashmaydi.
_FP_LAST: dict[tuple[str, str, str], tuple[list[str], Optional[float]]] = {}
# Poll'lar FastAPI threadpool'ida parallel ishlashi mumkin — holat o'qish/
# yozish qisqa lock bilan himoyalanadi (ikki poll bir-birini ustiga yozmaydi).
_FP_LOCK = threading.Lock()


def _fingerprint_reason(prev: list[str], curr: list[str]) -> list[str]:
    """Prev vs curr — sezilarli o'zgarishlarni inson tilida izohlaydi.

    Har bir manba turi alohida taqqoslanadi (vault fayl, L2 yozuv, xotira
    moduli, suhbat...). Qaytaradi: sabablar ro'yxati, masalan
    ["yangi xotira moduli: 03-new-module.jsonl", "yangi suhbat: ..."].
    """
    reasons: list[str] = []

    # 1) Vault .md — v:name:mtime_bucket
    prev_v = {p.split(":", 2)[1]: p for p in prev if p.startswith("v:")}
    curr_v = {p.split(":", 2)[1]: p for p in curr if p.startswith("v:")}
    for name in sorted(set(curr_v) - set(prev_v)):
        reasons.append(f"yangi vault fayl: {name}")
    for name in sorted(set(prev_v) & set(curr_v)):
        if prev_v[name] != curr_v[name]:
            reasons.append(f"yangilangan fayl: {name}")
    for name in sorted(set(prev_v) - set(curr_v)):
        reasons.append(f"o'chirilgan fayl: {name}")

    # 2) L2 persistent — p:name:qatorlar_soni (yangi yozuv = yangi node)
    def _p_map(parts: list[str]) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in parts:
            if not p.startswith("p:"):
                continue
            head = p.split(":", 2)
            if len(head) == 3 and head[2].isdigit():
                out[head[1]] = int(head[2])
        return out

    prev_p, curr_p = _p_map(prev), _p_map(curr)
    for name in sorted(set(curr_p) - set(prev_p)):
        reasons.append(f"yangi xotira fayli: {name}")
    for name in sorted(set(prev_p) & set(curr_p)):
        d = curr_p[name] - prev_p[name]
        if d > 0:
            reasons.append(f"yangi L2 xotira yozuvi: {name} (+{d})")
        elif d < 0:
            reasons.append(f"L2 xotira yozuvlari kamaydi: {name}")
    for name in sorted(set(prev_p) - set(curr_p)):
        reasons.append(f"o'chirilgan xotira fayli: {name}")

    # 3) L1 runtime — r:name (fayl modullari)
    prev_r = {p.split(":", 1)[1]: p for p in prev if p.startswith("r:")}
    curr_r = {p.split(":", 1)[1]: p for p in curr if p.startswith("r:")}
    for name in sorted(set(curr_r) - set(prev_r)):
        reasons.append(f"yangi xotira moduli: {name}")
    for name in sorted(set(prev_r) - set(curr_r)):
        reasons.append(f"xotira moduli o'chirildi: {name}")

    # 4) Chat suhbatlari — conv_id|title
    prev_c = {p.split("|", 1)[0]: p for p in prev if "|" in p}
    curr_c = {p.split("|", 1)[0]: p for p in curr if "|" in p}
    for cid in sorted(set(curr_c) - set(prev_c)):
        title = curr_c[cid].split("|", 1)[1]
        reasons.append(f"yangi suhbat: {(title or cid)[:40]}")
    for cid in sorted(set(prev_c) & set(curr_c)):
        if prev_c[cid] != curr_c[cid]:
            title = curr_c[cid].split("|", 1)[1]
            reasons.append(f"suhbat nomi o'zgardi: {(title or cid)[:40]}")
    for cid in sorted(set(prev_c) - set(curr_c)):
        reasons.append(f"suhbat o'chirildi: {cid}")

    # 5) Tombstone — o'chirilgan suhbatlar (4-bandda aniq izoh bo'lmasa)
    prev_t = [p for p in prev if p.startswith("tomb:")]
    curr_t = [p for p in curr if p.startswith("tomb:")]
    if prev_t != curr_t and not any(
            r.startswith("suhbat o'chirildi:") for r in reasons):
        reasons.append("suhbat o'chirildi")

    # Dublikatlarni olib tashlaymiz (masalan "suhbat o'chirildi" x2)
    seen: set[str] = set()
    out: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _collect_fingerprint_parts(memory_root: str, brain_data: str, chat_path: str) -> list[str]:
    """Fingerprint uchun manba qismlarini yig'adi (digest/yurish uchun umumiy).

    `graph_version_fingerprint` (poll) ham, `build_graph` keshi ham shu yerdan
    foydalanadi — ikki joyda takrorlanmasligi uchun umumiy yordamchi.
    Hech qanday holatni (``_FP_LAST``) o'zgartirmaydi — kirishni buzmaydi.
    """
    parts: list[str] = []

    # 1) Vault .md — graf faqat Ildizdagi .md'lar bilan node quradi
    #    (_scan_vault_files bilan bir xil qamrov). mtime 5s aniqligida —
    #    bitta fayl tez ketma-ket yozilsa ham bitta o'zgarish sanaladi.
    try:
        if os.path.isdir(memory_root):
            for fname in sorted(os.listdir(memory_root)):
                if not fname.endswith(".md"):
                    continue
                mtime = os.path.getmtime(os.path.join(memory_root, fname))
                parts.append(f"v:{fname}:{int(mtime // 5)}")
    except OSError:
        pass

    # 2) L2 persistent: qatorlar soni (yangi L2 yozuv = yangi node).
    #    L1 runtime: FAQAT fayl NOMI — append'lar shovqin (har chat'da),
    #    yangi fayl paydo bo'lishi esa sezilarli (yangi xotira moduli).
    for rel, prefix in (("persistent", "p"), ("runtime", "r")):
        base = os.path.join(brain_data, rel)
        if not os.path.isdir(base):
            continue
        for fname in sorted(os.listdir(base)):
            if not fname.endswith(".jsonl"):
                continue
            if prefix == "r":
                parts.append(f"r:{fname}")
                continue
            parts.append(f"p:{fname}:{_fp_cached_line_count(os.path.join(base, fname))}")

    # 3) Chat suhbatlari — id + nom + tombstone (sezilarli chat o'zgarishlari)
    parts.extend(_chat_fingerprint(chat_path))
    return parts


def _sources_digest(memory_root: Optional[str] = None, brain_data: Optional[str] = None,
                    chat_path: Optional[str] = None) -> int:
    """Manba holati uchun deterministik digest — ``build_graph`` keshi kaliti.

    `graph_version_fingerprint` bilan BIR XIL hisoblanadi (xuddi shu qismlar va
    sha256), lekin ``_FP_LAST`` holatiga tegmaydi — relyuz/xizmat ko'rsatish
    paytida poll holatini buzmaydi.
    """
    parts = _collect_fingerprint_parts(
        memory_root or MEMORY_ROOT, brain_data or BRAIN_DATA, chat_path or CHAT_HISTORY_PATH)
    if not parts:
        return 0
    sig = "|".join(parts)
    return int(hashlib.sha256(sig.encode("utf-8")).hexdigest()[:16], 16)


def graph_version_fingerprint(
    memory_root: Optional[str] = None,
    brain_data: Optional[str] = None,
    chat_path: Optional[str] = None,
) -> tuple[int, int, Optional[str], Optional[float]]:
    """2nd Brain graf versiyasi — FAQAT SEZILARLI o'zgarishlar uchun fingerprint.

    Frontend har ~8 soniyada /api/brain/graph/version'ni so'raydi; grafik
    FAQAT versiya o'zgarganda qayta yuklanadi. Versiya faqat grafga HAQIQATAN
    ta'sir qiladigan o'zgarishlarda siljiydi — 2nd Brain chat davomida
    'sakrab' qayta yuklanmaydi (noqulaylik va 'fake' holatlar yo'q).

      SEZILARLI (versiya o'zgaradi):
        - Vault .md fayli qo'shildi / o'zgartirildi (yangi modul, eslatma)
        - L2 persistent xotiraga yangi yozuv qo'shildi (qatorlar soni)
        - Yangi JSONL fayl paydo bo'ldi / o'chirildi (yangi xotira moduli)
        - Chat: yangi suhbat / o'chirilgan suhbat / nom o'zgarishi

      SHOVQIN (versiya O'ZGARMAYDI):
        - L1 runtime JSONL'ga yozishlar (har chat/tool'da append bo'ladi)
        - Mavjud suhbatga yangi xabarlar (node to'plami bir xil qoladi)

    Qaytaradi: (digest, manbalar soni, oxirgi o'zgarish sababi, so'nggi
    o'zgarish vaqti).

    Sabab — bu qo'ng'iroqdan avvalgi qo'ng'iroqqa nisbatan aniqlangan
    sezilarli o'zgarishlar tavsifi ("yangi xotira moduli: ...", "yangi
    suhbat: ..."). O'zgarish bo'lmasa None qaytadi — frontend graf nega
    yangilanganini ko'rsatadi ("fake" emas, real sabab).

    changed_at — so'nggi SEZILARLI o'zgarish aniqlangan vaqt (epoch sekund).
    O'zgarishsiz poll'lar bu vaqtni saqlab qaytaradi (qachondan beri turg'un);
    hech qachon o'zgarish bo'lmagan bo'lsa None.
    """
    memory_root = memory_root or MEMORY_ROOT
    brain_data = brain_data or BRAIN_DATA
    chat_path = chat_path or CHAT_HISTORY_PATH
    parts = _collect_fingerprint_parts(memory_root, brain_data, chat_path)

    # O'zgarish sababi: oldingi holat bilan solishtiramiz, so'ng yangilaymiz.
    # Birinchi qo'ng'iroqda oldingi holat yo'q — sabab None (oddiy boshlanish).
    # O'zgarish sababi + vaqti: oldingi holat bilan solishtiramiz, so'ng
    # yangilaymiz. Birinchi qo'ng'iroqda oldingi holat yo'q — sabab/vaqt None
    # (oddiy boshlanish, o'zgarish hali kuzatilmagan).
    state_key = (memory_root, brain_data, chat_path)
    with _FP_LOCK:
        prev_state = _FP_LAST.get(state_key)
        prev = prev_state[0] if prev_state is not None else None
        prev_changed_at = prev_state[1] if prev_state is not None else None
        if prev is not None and prev != parts:
            changed_at: Optional[float] = time.time()  # sezilarli o'zgarish aniqlandi
        else:
            changed_at = prev_changed_at  # o'zgarish yo'q — eski vaqt saqlanadi
        _FP_LAST[state_key] = (list(parts), changed_at)
    reasons = _fingerprint_reason(prev or [], parts) if prev is not None else []
    reason: Optional[str] = None
    if reasons:
        reason = "; ".join(reasons[:3])
        extra = len(reasons) - 3
        if extra > 0:
            reason += f" (+{extra} ta)"

    if not parts:
        return 0, 0, reason, changed_at
    sig = "|".join(parts)
    digest = int(hashlib.sha256(sig.encode("utf-8")).hexdigest()[:16], 16)
    return digest, len(parts), reason, changed_at


# build_graph natija keshi — kalit: (manba digesti, max_nodes, shares). Manba
# o'zgarmaguncha grafik qayta qurilmaydi: katta Igris_Memory arxivida `/api/
# brain/graph` sekinlashishi yoki 8s frontend timeout'iga tushishi oldini oladi
# (digest `_fp_cached_line_count` keshi tufayli engil — stat + zarur bo'lsa sanash).
# `_sources_digest` `_FP_LAST` holatiga tegmaydi — poll/badge holati buzilmaydi.
_GRAPH_CACHE: dict = {}
_GRAPH_CACHE_LIMIT = 32
_GRAPH_CACHE_LOCK = threading.Lock()


def build_graph(max_nodes: int = 240, shares: Optional[list] = None) -> dict:
    """Real knowledge graph quriladi. Xatolarda bo'sh/fallback qaytaradi.

    Node limit: vault/chat/L1/L2 manbalari KVOTALI blend qilinadi (har manba
    o'z ulushiga ega) — bitta manba o'ssa ham boshqa manba node'lari
    siqilmaydi, chegara yaqinida churn bo'lmaydi (2nd Brain turg'un ko'rinadi).

    `shares` — [vault, chat, persistent, runtime] ulushlari (default
    DEFAULT_SHARES). 2nd Brain sozlamalar panelidan sozlanishi mumkin.

    Natija manba digesti bo'yicha keshlanadi — manba o'zgarmaguncha keshdan
    qaytariladi (testlar va xizmat uchun ko'p takroriy chaqiruv tez ketadi).
    """
    # Manba o'zgarmagan bo'lsa — keshlangan grafni qaytaramiz (qayta qurish yo'q).
    cache_key = (_sources_digest(), max_nodes, tuple(normalize_shares(shares)))
    with _GRAPH_CACHE_LOCK:
        cached = _GRAPH_CACHE.get(cache_key)
    if cached is not None:
        return cached

    vault = _scan_vault_files()
    seen: set[str] = set()
    # Yozuv id'lari bo'yicha umumiy dedup — bir id bir necha marta yozilgan
    # bo'lsa (turli content bilan) bitta node qoladi. L1/L2 prefikslari har
    # qanday holatda ham xavfsiz, lekin umumiy set qo'shimcha himoya.
    id_seen: set[str] = set()
    # KENG oynalar: tor limit (6/10) chat/xotira yozuvida tez-tez siljib,
    # eski node'lar tushib, yangilari kirardi — graf har chat'da 'sakrab'
    # ko'rinardi (2nd Brain stream flicker). Katta oyna kamroq churn = turg'un graf.
    persistent = _scan_jsonl_dir(
        os.path.join(BRAIN_DATA, "persistent"), "l2", L2_KIND,
        limit_per_file=25, seen=seen, id_seen=id_seen)
    runtime = _scan_jsonl_dir(
        os.path.join(BRAIN_DATA, "runtime"), "l1",
        {"short-turn": "session", "session": "session"},
        limit_per_file=40, seen=seen, id_seen=id_seen)
    chat = _scan_chat_history(max_conv=60)

    # Interleave: vault (primary) + JSONL + chat — xotiradan olingan node'lar
    # (L1/L2) va REAL chat suhbatlari doim grafikda qoladi.
    # KVOTALI barqaror blend: har manba o'z ulushiga ega (default 0.35/0.25/
    # 0.20/0.20; UI'dan sozlanishi mumkin). Bitta manba o'ssa boshqalari
    # qisqarmaydi — chegara yaqinida churn yo'q.
    all_nodes = _stable_blend(
        [vault, chat, persistent, runtime], max_nodes,
        shares=normalize_shares(shares))

    wikilinks = _extract_wikilinks(all_nodes)
    links = _semantic_links(all_nodes, wikilinks)
    pos = _layout(all_nodes)
    # Link sabablari — frontend "nima uchun bog'langan" tooltip/zoom uchun.
    reasons = _link_reasons(all_nodes, links)

    nodes_out = [{
        "id": n["id"],
        "label": n["label"],
        "kind": n["kind"],
        "x": pos[n["id"]][0],
        "y": pos[n["id"]][1],
        "detail": n["detail"],
        # Suhbat node'larida oxirgi yangilanish vaqti (boshqa kind'lar uchun yo'q).
        "updated_at": n.get("updated_at"),
    } for n in all_nodes]

    result = {
        "ok": True,
        "nodes": nodes_out,
        "links": [[a, b] for a, b in links],
        # 'a|b' -> umumiy so'zlar (link nega borligi — zoom'da ko'rsatiladi).
        "link_reasons": reasons,
        "stats": {
            "vault_files": len(vault),
            "persistent_entries": len(persistent),
            "runtime_entries": len(runtime),
            "chat_sessions": len(chat),
            "nodes": len(nodes_out),
            "links": len(links),
        },
    }
    # Keshlash (cheklangan o'lcham — eng eskilar chiqib ketadi, o'sish yo'q).
    with _GRAPH_CACHE_LOCK:
        _GRAPH_CACHE[cache_key] = result
        overflow = len(_GRAPH_CACHE) - _GRAPH_CACHE_LIMIT
        if overflow > 0:
            for key in list(_GRAPH_CACHE)[:overflow]:
                _GRAPH_CACHE.pop(key, None)
    return result


# ---------------------------------------------------------------- #
# CLI tekshiruvi: python brain_graph.py
# ---------------------------------------------------------------- #

def main() -> int:
    g = build_graph()
    print(f"nodes={len(g['nodes'])} links={len(g['links'])} stats={g['stats']}")
    for n in g["nodes"][:8]:
        print(f"  [{n['kind']:12}] {n['label']} @ ({n['x']}, {n['y']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
