"""
IGRIS BRAIN — Action Evidence guard (anti-hallucination)
========================================================

Muammo (real holat, server/chat_history.jsonl):
    user: "mini iloncha o'yinini yasab ber"
    agent: "O'yin kodini yaratib berdim. Fayl yaratildi: mini_snake_game.py."
    → tool chaqirilmagan, fayl mavjud EMAS — agent ish qilmagan bo'lib,
      faqat "qildim" deb da'vo qiladi (soxta yakunlash).

Himoya qatlami:
    1. `evaluate()` — javobda amal da'vosi bormi? isboti (tool/rasm/workspace
       fayli) bormi? → (ok, reason)
    2. `nudge_message()` — modelga "haqiqatan bajar" degan majburlash xabari
       (agent bir marta qayta urinishda haqiqiy tool chaqiradi).
    3. `honest_rewrite()` — isbot bo'lmasa da'vo o'rniga halol ogohlantirish.

Qoidalar:
    - hech qachon "bajarildi" demaslik — isbot: tool_calls, image yoki
      workspace'da mavjud fayl.
    - kelajakdagi va'da ("I will draw...") faqat creator pipeline'da
      da'vo sifatida olqinlanadi (oddiy suhbatda va'da — xato emas).
"""

from __future__ import annotations

import os
import re
from typing import Optional

# Creator (amal talab qiluvchi) pipeline'lar — va'da ham da'vo hisoblanadi.
CREATOR_NEEDS = frozenset(
    {"draw", "code", "ui_build", "web", "composition", "file_task"})

# ---------------------------------------------------------------- #
# 1) DA'VO DETEKTSLARI
# ---------------------------------------------------------------- #

_EXT = (r"py|js|jsx|ts|tsx|json|md|txt|svg|png|jpg|jpeg|gif|webp|html|htm|"
        r"css|scss|sh|bat|ps1|pptx|docx|xlsx|csv|pdf|ipynb|java|go|rs|"
        r"cpp|cc|c|h|php|rb|sql|yaml|yml|toml|xml|vue|svelte|cfg|ini|lock")

# Matndagi fayl nomlari (da'vo obyektsini topish uchun)
FILE_RE = re.compile(rf"(?<![\w/\\])[A-Za-z0-9_][\w\-./\\]*\.(?:{_EXT})\b")

# O'tmishdagi amal da'vosi (uz + en) — "qildim / yaratildi / file created"
PAST_CLAIM_RE = re.compile(
    r"(?:"
    # --- uz: birinchi shaxs ---
    r"\b(?:yaratdim|yaratib\s+berdim|saqladim|yozdim|yozib\s+berdim|chizdim|"
    r"chizib\s+berdim|qurdim|tuzdim|ishga\s+tushirdim|bajarildim|tuzatdim|"
    r"o'zgartirdim|o'chirdim|yakunladim|o'rganib\s+oldim)\b"
    r"|\byaratib\s+berdim\b"
    # --- uz: o'tgan zamon shtatli ---
    r"|\b(?:fayl\s+)?(?:yaratildi|yozildi|saqlandi|chizildi|qurildi|"
    r"bajarildi|ishga\s+tushirildi|tayyorlandi|o'zgartirildi|o'chirildi)\b"
    r"|\brasm\s+tayyor\b|\bfayl\s+tayyor\b"
    # --- en: file-centric ---
    r"|\b(?:file|fayl|image|rasm)\s+(?:was\s+)?(?:created|saved|written|"
    r"updated|added|deleted|renamed|written\s+down)\b"
    r"|\b(?:file|fayl)\s+created\b|\bcreated\s+(?:the\s+)?(?:file|fayl)\b"
    r"|\b(?:is|are)\s+saved\s+(?:as|to|in)\b|\bsaved\s+(?:as|to|in)\b"
    r"|\bimage\s+(?:is\s+)?saved\b"
    # --- en: birinchi shaxs / o'tgan zamon ---
    r"|\bi\s+(?:have\s+|just\s+)?(?:created|wrote|saved|ran|executed|"
    r"generated|built|drew|updated|installed|fixed|deployed)\b"
    r"|\bwe\s+(?:have\s+)?(?:created|wrote|saved|ran|executed|built|drew)\b"
    r"|\b(?:was|were)\s+(?:created|saved|written|ran|generated|built|drawn|"
    r"updated)\b"
    r"|\bran\s+(?:the\s+)?(?:it|script|program|command|successfully|test)\b"
    r")",
    re.IGNORECASE)

# Kelajakdagi va'da — FAQAT creator pipeline'da da'vo hisoblanadi
# ("I will draw a PCB schema." → hech narsa qilmadi, faqat va'da).
PROMISE_RE = re.compile(
    r"(?:"
    r"\bi\s+(?:will|'m\s+going\s+to)\s+(?:create|write|draw|build|make|run|"
    r"generate|save|install|fix|update)\b"
    r"|\b(?:yarataman|yozaman|chizaman|quraman|bajaraman|tuzaman|saqlayman)\b"
    r"|\bmen\s+(?:hozir\s+)?(?:yarat|yoz|chiz|qur|bajar)\w*\s+(?:chiqaman|"
    r"kerak|lip)\b"
    r"|\bgoing\s+to\s+(?:create|write|draw|build|make|run)\b"
    r")",
    re.IGNORECASE)


def find_claim(text: str, *, allow_promise: bool = False) -> Optional[str]:
    """Matndagi amal da'voni topadi — topilmasa None."""
    txt = str(text or "")
    if not txt.strip():
        return None
    m = PAST_CLAIM_RE.search(txt)
    if m:
        return m.group(0).strip()
    if allow_promise:
        m = PROMISE_RE.search(txt)
        if m:
            return m.group(0).strip()
    return None


def mentioned_files(text: str) -> list[str]:
    """Da'vo qilingan fayl nomlari (qisqa, faqat nom)."""
    out: list[str] = []
    for m in FILE_RE.finditer(str(text or "")):
        name = m.group(0).strip("./\\")
        if name and name not in out:
            out.append(name)
        if len(out) >= 8:
            break
    return out


_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
              "dist", "build", ".checkpoints", ".igris_backups"}


def _index_files(root: str, max_files: int = 4000, max_depth: int = 5) -> set:
    """Workspace fayllari indeksi (bir marta yig'iladi — takroriy walk yo'q)."""
    out: set = set()
    try:
        for dirpath, dirs, files in os.walk(root):
            rel = os.path.relpath(dirpath, root)
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            if depth > max_depth:
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            out.update(files)
            if len(out) >= max_files:
                break
    except OSError:
        pass
    return out


def files_on_disk(workspace_root: str, files: list[str]) -> tuple[bool, bool]:
    """(barcha fayllar bormi, kamida bitta bormi) — workspace ichida."""
    if not files:
        return False, False
    root = workspace_root or ""
    if not root or not os.path.isdir(root):
        return False, False
    index: Optional[set] = None
    found = 0
    for name in files:
        base = os.path.basename(name)
        hit = (os.path.isfile(os.path.join(root, name))
               or os.path.isfile(os.path.join(root, base)))
        if not hit:
            if index is None:
                index = _index_files(root)
            hit = base in index
        if hit:
            found += 1
    return found == len(files), found > 0


def evaluate(text: str, tool_calls=None, image=None, workspace_root: str = "",
             *, allow_promise: bool = False) -> tuple[bool, str]:
    """Da'vo isbotlanganmi? → (ok, reason).

    ok=True  — isbot bor: tool chaqirilgan, rasm yaratilgan yoki da'vo
               qilingan fayl haqiqatan workspace'da mavjud.
    ok=False — "qildim" da'vosi ISBOTSIZ (hallucination xavfi).
    """
    content = str(text or "")
    if tool_calls:
        return True, ""
    if image:
        return True, ""
    claim = find_claim(content, allow_promise=allow_promise)
    if claim is None:
        return True, ""
    files = mentioned_files(content)
    if files:
        all_found, any_found = files_on_disk(workspace_root, files)
        if all_found:
            return True, ""          # fayl oldingi turda yaratilgan — da'vo to'g'ri
        if any_found:
            return False, claim      # qisman to'g'ri — tekshirish kerak
        return False, claim
    # Da'vo faylsiz (masalan "ishga tushirdim") — isbot yo'q
    return False, claim


# ---------------------------------------------------------------- #
# 2) MAJBURLASH (nudge) VA HALOL QAYTA YOZISH
# ---------------------------------------------------------------- #

NUDGE_PROMPT = (
    "EVIDENCE CHECK: your previous reply claims work was done, but NO tool "
    "was executed — nothing actually happened in the workspace.\n"
    "Do it for REAL now with the available tools (write_file, apply_patch, "
    "run_command, python_exec, list_files, read_file, art__*, web_*):\n"
    "  1. perform the action (or first VERIFY it with list_files/read_file),\n"
    "  2. then report ONLY what actually happened.\n"
    "If you truly cannot do it, say plainly that it was NOT done. "
    "Never claim actions you did not perform."
)


def nudge_message(reason: str = "") -> str:
    """Modelga beriladigan majburlash xabari (1 marta qayta urinish)."""
    if reason:
        return (f"Flagged sentence: \"{reason}\"\n\n" + NUDGE_PROMPT)
    return NUDGE_PROMPT


_HONEST_PREFIX = (
    "⚠️ [Tasdiqlanmagan] Bu javobda amal bajarilgani da'vo qilingan, lekin "
    "hech qanday vosita (tool) chaqirilmagan — ish haqiqatan bajarilmagan.\n"
)


def honest_rewrite(text: str, reason: str = "") -> str:
    """Da'vo o'rniga halol ogohlantirish (isbot bo'lmasa)."""
    body = str(text or "").strip()
    head = _HONEST_PREFIX
    if reason:
        head += f"Da'vo: \"{reason}\"\n"
    if not body:
        return head.strip()
    return head + "\n" + body
