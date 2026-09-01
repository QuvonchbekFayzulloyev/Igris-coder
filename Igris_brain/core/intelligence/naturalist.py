"""
IGRIS BRAIN — 2.8 Naturalist Intelligence — core/naturalist
===========================================================
Tabiiy tizimlar, ekologik pattern, atrof-muhit naqshlarini tushunish.

Kodlash agenti uchun real, foydali versiya: "naturalist" — bu agentning
ATROFIDAGI muhitni (loyiha fayllari, kengaytmalar, ma'lumot tuzilmalari)
naqsh sifatida o'qish qobiliyatidir. Hayvon/o'simlik klassifikatsiyasi emas
— domenga xos tabiiy pattern recognition:

  - classify_paths(paths)  -> fayl turlari, kengaytma, til taqsimoti
  - classify_text(text)    -> matn ichidagi ma'lumot naqshlari
                              (URL, email, kod blok, raqam, sana, ...)
  - environment_summary(paths) -> system prompt uchun ixcham xulosa

Qo'llanma 2.8-band: domenga xos, past priority — lekin loyiha strukturasi
haqidagi savollarda real qiymat beradi (spatial 2.4 bilan birga ishlaydi).
"""

from __future__ import annotations

import os
import re
from collections import Counter


# Kengaytma -> dasturlash tili / fayl turi (naturalist "yashash muhiti" xaritasi)
EXT_LANGUAGES: dict[str, str] = {
    ".py": "python", ".pyw": "python", ".ipynb": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".java": "java", ".kt": "kotlin",
    ".c": "c", ".h": "c", ".cpp": "c++", ".hpp": "c++", ".cc": "c++",
    ".cs": "csharp", ".go": "go", ".rs": "rust", ".rb": "ruby",
    ".php": "php", ".swift": "swift", ".scala": "scala",
    ".sh": "shell", ".bat": "batch", ".ps1": "powershell",
    ".html": "html", ".htm": "html", ".css": "css", ".scss": "scss",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".xml": "xml", ".csv": "csv", ".tsv": "tsv", ".ini": "ini",
    ".sql": "sql", ".md": "markdown", ".rst": "markdown",
    ".txt": "text", ".log": "log",
    ".svg": "svg", ".png": "image", ".jpg": "image", ".jpeg": "image",
    ".gif": "image", ".webp": "image", ".ico": "image", ".bmp": "image",
    ".woff": "font", ".woff2": "font", ".ttf": "font",
    ".zip": "archive", ".tar": "archive", ".gz": "archive",
    ".exe": "binary", ".dll": "binary", ".so": "binary", ".dylib": "binary",
    ".pdf": "document", ".docx": "document",
}

# Matn naqshlari — classify_text uchun (kodlash muhitida foydali ma'lumot)
_TEXT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("url", re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)),
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("code_block", re.compile(r"```[\s\S]*?```")),
    ("json", re.compile(r"\{[\s\S]*?\}")),
    ("number", re.compile(r"(?<![\w.])\d{4,}(?![\w.])")),
    ("date", re.compile(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b")),
    ("hex_color", re.compile(r"#[0-9a-fA-F]{6}\b")),
    ("import", re.compile(r"^\s*(import|from|require|include)\b", re.MULTILINE)),
]


class NaturalistLayer:
    """2.8 Muhit naqshlarini o'qish qatlami.

    Usullar:
      - classify_paths(paths)      -> kengaytma/til taqsimoti, katalog guruhlar
      - classify_text(text)        -> matn ichidagi ma'lumot naqshlari
      - environment_summary(paths) -> system prompt uchun ixcham xulosa
    """

    def __init__(self):
        self._classifications: int = 0

    # ------------------------------------------------------------ #
    # Fayl muhiti tahlili (kengaytma -> til -> naqsh)
    # ------------------------------------------------------------ #

    def classify_paths(self, paths: list[str]) -> dict:
        """Fayl yo'llari ro'yxatidan 'ekologik' taqsimotni hisoblaydi.

        Chiqish: kengaytma bo'yicha son, til bo'yicha son, top-level
        katalog guruhlari — loyiha 'nimadan iborat' degan aniq rasm.
        """
        self._classifications += 1
        ext_counter: Counter = Counter()
        lang_counter: Counter = Counter()
        top_groups: Counter = Counter()

        for p in (paths or []):
            p = str(p).replace("\\", "/")
            base = os.path.basename(p)
            if not base or base.startswith("."):
                continue
            ext = os.path.splitext(base)[1].lower()
            if ext:
                ext_counter[ext] += 1
                lang = EXT_LANGUAGES.get(ext, "other")
                lang_counter[lang] += 1
            # top-level katalog guruhi (1-chi bo'lak) — 0-chi bo'lsa root
            parts = [x for x in p.split("/") if x]
            if len(parts) >= 2:
                top_groups[parts[0]] += 1
            else:
                top_groups["(root)"] += 1

        total = sum(ext_counter.values())
        lang_dist = dict(lang_counter.most_common(12))
        return {
            "files": total,
            "extensions": dict(ext_counter.most_common(12)),
            "languages": lang_dist,
            "top_groups": dict(top_groups.most_common(10)),
            "dominant": lang_counter.most_common(1)[0][0] if lang_counter else "unknown",
        }

    # ------------------------------------------------------------ #
    # Matn naqshlari (ma'lumot tuzilmalari)
    # ------------------------------------------------------------ #

    def classify_text(self, text: str) -> dict:
        """Matn ichidagi ma'lumot naqshlarini sanaydi (URL, kod, raqam...)."""
        self._classifications += 1
        text = text or ""
        counts: dict[str, int] = {}
        for name, rx in _TEXT_PATTERNS:
            n = len(rx.findall(text))
            if n:
                counts[name] = n
        # Dominant naqsh — matn nima haqida (kod? ma'lumot? havola?)
        dominant = max(counts, key=counts.get) if counts else "plain"
        return {"patterns": counts, "dominant": dominant, "chars": len(text)}

    # ------------------------------------------------------------ #
    # System prompt uchun ixcham xulosa
    # ------------------------------------------------------------ #

    def environment_summary(self, paths: list[str], max_lines: int = 8) -> str:
        """Loyiha muhiti haqida ixcham 'naturalist xaritasi' (prompt bloki).

        Spatial (2.4) daraxt tahlili bilan birga ishlatiladi — agent loyiha
        qaysi texnologiyalardan iborat ekanini bir qarashda ko'radi.
        """
        info = self.classify_paths(paths)
        if not info["files"]:
            return ""
        lines = [f"Project environment ({info['files']} files):"]
        langs = info.get("languages") or {}
        if langs:
            top = ", ".join(f"{k} {v}" for k, v in list(langs.items())[:max_lines])
            lines.append(f"- Languages: {top}")
        groups = info.get("top_groups") or {}
        if groups:
            g = ", ".join(f"{k} ({v})" for k, v in list(groups.items())[:6])
            lines.append(f"- Top folders: {g}")
        return "\n".join(lines)

    # ------------------------------------------------------------ #

    def stats(self) -> dict:
        return {"classifications": self._classifications}
