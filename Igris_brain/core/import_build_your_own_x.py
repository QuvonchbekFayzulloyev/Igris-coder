"""
IGRIS — Build Your Own X → Resource Knowledge Importer
=======================================================
codecrafters-io/build-your-own-x README.md (ilgari Tempgitbuildingrepo/ da
saqlanardi) ni Igris foydalana oladigan RESOURCE KNOWLEDGE'ga aylantiradi.

Chiqish:
  1. Igris_Memory/resources/*.md        — har bir kategoriya uchun
     Obsidian-uslubidagi resurs fayli. Retrieval (BM25) ularni os.walk
     orqali indekslaydi → RAG recall'da topiladi.
  2. brain_data/persistent/03-knowledge.jsonl — har bir kategoriya uchun
     L2 "knowledge" entry. /api/agent/memory recall + 2nd Brain grafigida
     "fact" node bo'lib ko'rinadi (grafikda har bir JSONL fayldan eng
     so'nggi 6 tasi ko'rsatiladi — dizayn limiti).

Idempotent: content bir xil bo'lsa PersistentMemory duplicate-skip qiladi.
Qayta ishga tushirish xavfsiz.

Eslatma: Tempgitbuildingrepo/ papkasi olib tashlandi (manba README endi
loyihada yo'q). Qayta import qilish uchun README'ni o'sha yo'lga joylang
(masalan `curl -L https://raw.githubusercontent.com/codecrafters-io/build-your-own-x/master/README.md -o Tempgitbuildingrepo/README.md`).

Ishlatish:
    cd Igris_brain && python import_build_your_own_x.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(HERE, ".."))
README_PATH = os.path.join(PROJECT_ROOT, "Tempgitbuildingrepo", "README.md")
MEMORY_ROOT = os.path.normpath(os.path.join(PROJECT_ROOT, "Igris_Memory"))
RESOURCES_DIR = os.path.join(MEMORY_ROOT, "resources")
BASE_DIR = os.path.join(MEMORY_ROOT, "brain_data")

SOURCE_URL = "https://github.com/codecrafters-io/build-your-own-x"
MAX_ENTRY_CHARS = 1800   # har bir knowledge entry ~1800 belgi (token chegarasi)
MAX_TITLE = 90

HEADER_RE = re.compile(r"^####\s+Build your own\s*`([^`]+)`\s*$")
UNCAT_RE = re.compile(r"^####\s+Uncategorized\s*$")
BULLET_RE = re.compile(r"^\s*[\*\-]\s+(.*)$")
STOP_RE = re.compile(r"^#{2,3}\s+")

# ---------------------------------------------------------------- #
# Parsing
# ---------------------------------------------------------------- #

def parse_bullet(line: str) -> dict:
    """`* [**Lang**: _Title_](url) [video]` → {lang, title, url, suffix}."""
    m = BULLET_RE.match(line)
    if not m:
        return {}
    text = m.group(1).strip()
    if not text.startswith("["):
        return {"raw": text[:MAX_TITLE], "title": text[:MAX_TITLE], "url": None, "suffix": ""}
    close = text.find("](")
    if close == -1:
        return {"raw": text[:MAX_TITLE], "title": text[:MAX_TITLE], "url": None, "suffix": ""}
    title_part = text[1:close]
    end = text.find(")", close)
    url = text[close + 2:end] if end != -1 else None
    suffix = text[end + 1:].strip() if end != -1 else ""

    lang = None
    if title_part.startswith("**"):
        end_b = title_part.find("**", 2)
        if end_b != -1:
            lang = title_part[2:end_b].strip()
            title_part = title_part[end_b + 2:].strip()
    title_part = title_part.strip()
    if title_part.startswith(": "):
        title_part = title_part[2:].strip()
    title_part = re.sub(r"^_+|_+$", "", title_part).strip()
    return {"lang": lang, "title": title_part[:MAX_TITLE] or text[:MAX_TITLE], "url": url, "suffix": suffix}


def parse_categories() -> list[dict]:
    """README → [{name, bullets:[{lang,title,url,suffix}]}] (Uncategorized ham)."""
    with open(README_PATH, "r", encoding="utf-8", errors="ignore") as fh:
        lines = fh.readlines()

    categories: list[dict] = []
    current = None
    for line in lines:
        mh = HEADER_RE.match(line)
        mu = UNCAT_RE.match(line)
        if mh:
            current = {"name": mh.group(1).strip(), "bullets": []}
            categories.append(current)
            continue
        if mu:
            current = {"name": "Uncategorized", "bullets": []}
            categories.append(current)
            continue
        if STOP_RE.match(line):
            current = None
            continue
        if current is None:
            continue
        b = parse_bullet(line)
        if b:
            current["bullets"].append(b)
    return [c for c in categories if c.get("name")]


# ---------------------------------------------------------------- #
# Resource markdown fayllar (Obsidian uslubi)
# ---------------------------------------------------------------- #

def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "misc"


def render_bullet(b: dict) -> str:
    lang = f"**{b['lang']}** " if b.get("lang") else ""
    if b.get("url"):
        return f"- {lang}{b['title']} — {b['url']} {b.get('suffix', '')}".rstrip()
    return f"- {b.get('title', b.get('raw', ''))}"


def build_resource_md(name: str, bullets: list[dict]) -> str:
    slug = slugify(name)
    lines = [
        f"# Build Your Own X — {name}",
        "",
        f"#build-your-own-x #resource #tutorial #{slug}",
        "",
        f"Manba: [codecrafters-io/build-your-own-x]({SOURCE_URL})",
        "",
        f"`{name}` bilan bog'liq vazifa kelganda shu yo'riqnomalardan foydalan.",
        "",
        f"## Tutoriallar ({len(bullets)})",
        "",
    ]
    for b in bullets:
        lines.append(render_bullet(b))
    lines += [
        "",
        "## Igris uchun eslatma",
        "",
        f"1. Foydalanuvchi '{name}' sohasida narsa qurishni so'rasa — yuqoridagi tutorial'lardan mosini top.",
        "2. Avval maqsadni mayda qadamlarga bo'l (planner), keyin havolani o'qib yechimni o'zi yoz.",
        f"3. Qidirish: 'Build your own {name}', '{slug}' yoki kategoriya kalit so'zlari.",
        "",
    ]
    return "\n".join(lines)


def write_resource_files(categories: list[dict]) -> list[str]:
    os.makedirs(RESOURCES_DIR, exist_ok=True)
    written: list[str] = []

    # index fayli
    toc = [
        "# Build Your Own X — Resource Index",
        "",
        "#build-your-own-x #resource #index #tutorial",
        "",
        f"Manba: [{SOURCE_URL}]({SOURCE_URL})",
        "",
        "## Kategoriyalar",
        "",
    ]
    for c in categories:
        fname = f"Build Your Own X - {c['name']}.md".replace("/", "-").replace("\\", "-")
        toc.append(f"- [[{fname[:-3]}]] ({len(c['bullets'])} tutorial)")
    toc.append("")
    index_path = os.path.join(RESOURCES_DIR, "00 - Build Your Own X - Index.md")
    with open(index_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(toc))
    written.append(index_path)

    for c in categories:
        fname = f"Build Your Own X - {c['name']}.md".replace("/", "-").replace("\\", "-")
        path = os.path.join(RESOURCES_DIR, fname)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(build_resource_md(c["name"], c["bullets"]))
        written.append(path)
    return written


# ---------------------------------------------------------------- #
# L2 knowledge entries (03-knowledge.jsonl)
# ---------------------------------------------------------------- #

def split_bullets(bullets: list[dict], max_chars: int = MAX_ENTRY_CHARS) -> list[list[dict]]:
    """Katta kategoriyalarni bir nechta knowledge entry'ga bo'ladi."""
    chunks: list[list[dict]] = []
    cur: list[dict] = []
    size = 0
    for b in bullets:
        line = render_bullet(b)
        if cur and size + len(line) > max_chars:
            chunks.append(cur)
            cur, size = [], 0
        cur.append(b)
        size += len(line) + 2
    if cur:
        chunks.append(cur)
    return chunks


def write_knowledge_entries(categories: list[dict]) -> tuple[int, list[str]]:
    sys.path.insert(0, MEMORY_ROOT)
    try:
        from memory import MemoryManager  # noqa: PLC0415
    except Exception as exc:
        print(f"ERROR: Igris_Memory import qilib bo'lmadi: {exc}")
        return 0, []

    mm = MemoryManager(base_dir=BASE_DIR)
    now = datetime.now(timezone.utc).isoformat()
    written_ids: list[str] = []

    # PersistentMemory._hashes faqat JORIY prosesda to'ldiriladi (diskdan
    # yuklanmaydi) — re-run'da dup-skip ishlamaydi. Shuning uchun mavjud
    # id'larni o'zimiz o'qib, deterministik id asosida skip qilamiz.
    existing = mm.persistent.read("knowledge", limit=999999)
    existing_ids = {e.get("id") for e in existing if e.get("id")}

    # Grafikda har JSONL fayldan eng so'nggi 6 entry ko'rinadi (brain_graph
    # limit_per_file=6) — shuning uchun eng foydali kategoriyalar OXIRIDA
    # yoziladi (file oxiri = grafikda ko'rinadigan qism).
    priority = [
        "Database", "Git", "Programming Language", "Operating System", "Text Editor",
        "Shell", "Web Server", "Docker", "Neural Network", "Game",
        "Front-end Framework / Library", "Search Engine", "Regex Engine",
        "Command-Line Tool", "Emulator / Virtual Machine", "Web Browser",
        "Blockchain / Cryptocurrency", "Bot", "AI Model", "Physics Engine",
        "Network Stack", "3D Renderer", "Template Engine", "BitTorrent Client",
        "Augmented Reality", "Visual Recognition System", "Voxel Engine",
        "Memory Allocator", "Processor", "Distributed Systems", "Uncategorized",
    ]
    ordered = sorted(categories, key=lambda c: -priority.index(c["name"]) if c["name"] in priority else -999)

    for c in ordered:
        chunks = split_bullets(c["bullets"])
        n_chunks = len(chunks)
        total = len(c["bullets"])
        for i, chunk in enumerate(chunks):
            part = f" ({i + 1}/{n_chunks})" if n_chunks > 1 else ""
            body = "\n".join(render_bullet(b) for b in chunk)
            langs = sorted({b["lang"] for b in chunk if b.get("lang")})
            content = (
                f"BUILD YOUR OWN X — {c['name']}{part}\n"
                f"Source: {SOURCE_URL} | tutorials: {len(chunk)}/{total} | langs: {', '.join(langs) or 'n/a'}\n"
                f"{body}"
            )
            summary = f"Build your own {c['name']}: {len(chunk)} tutorial ({', '.join(langs[:5]) or 'n/a'})"
            # Eslatma: `remembered_at` QO'SHILMAYDI — PersistentMemory dup-hash
            # uni istisno qilmaydi (faqat id/timestamp/updated_at istisno),
            # shuning uchun re-run'da takroriy yozuvlar paydo bo'lardi.
            entry = {
                "id": f"byox-{slugify(c['name'])}-{i + 1}",
                "type": "knowledge",
                "content": content[:2000],
                "tags": ["build-your-own-x", "resource", "tutorial", slugify(c["name"])],
                "metadata": {
                    "source": SOURCE_URL,
                    "category": c["name"],
                    "part": i + 1,
                    "parts": n_chunks,
                    "tutorial_count": total,
                    "langs": langs,
                },
                "summary": summary[:500],
                "updated_at": now,
            }
            if entry["id"] in existing_ids:
                print(f"  (existing skip: {entry['id']})")
                continue
            res = mm.persistent.write("knowledge", entry, check_duplicate=False)
            if res:
                written_ids.append(entry["id"])
            else:
                print(f"  (write skip: {entry['id']})")
    return len(written_ids), written_ids


# ---------------------------------------------------------------- #
# CLI
# ---------------------------------------------------------------- #

def main() -> int:
    if not os.path.exists(README_PATH):
        print(f"README topilmadi: {README_PATH}")
        return 1

    categories = parse_categories()
    total_tuts = sum(len(c["bullets"]) for c in categories)
    print(f"Kategoriyalar: {len(categories)} | tutorial: {total_tuts}")
    for c in categories:
        print(f"  - {c['name']}: {len(c['bullets'])}")

    files = write_resource_files(categories)
    print(f"\nResource fayllar yozildi ({len(files)}):")
    for f in files[:6]:
        print(f"  {os.path.relpath(f, PROJECT_ROOT)}")
    if len(files) > 6:
        print(f"  ... yana {len(files) - 6} ta")

    n, ids = write_knowledge_entries(categories)
    print(f"\nL2 knowledge entry yozildi: {n}")
    for i in ids[:8]:
        print(f"  {i}")
    if len(ids) > 8:
        print(f"  ... yana {len(ids) - 8} ta")

    if n == 0:
        print("\nXATO: knowledge entry yozilmadi (MemoryManager import/qidirishda xato).")
        print("Resource fayllar saqlangan, lekin xotira seed qilinmadi.")
        return 2
    stats_path = os.path.join(BASE_DIR, "persistent", "03-knowledge.jsonl")
    count = 0
    if os.path.exists(stats_path):
        with open(stats_path, "r", encoding="utf-8", errors="ignore") as fh:
            count = sum(1 for ln in fh if ln.strip())
    print(f"\n03-knowledge.jsonl umumiy yozuvlar: {count}")
    print("\nTayyor! Backend'ni qayta ishga tushiring: python server.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
