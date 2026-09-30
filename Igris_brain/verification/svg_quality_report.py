"""SVG chizma sifat tendensiyasi hisoboti.

L2 xotira (persistent/07-solution.jsonl) dagi `CHIZMA SIFATI` yozuvlarini
yig'ib, chizma sifati qanday o'zgarayotganini ko'rsatadi: o'rtacha ball,
zaifliklar gistogrammasi, uslub bo'yicha taqsimot, vaqt tendensiyasi.

Ishlatish:
    python svg_quality_report.py                    # Igris_Memory dan o'qiydi
    python svg_quality_report.py --dir <xotira-dir> # maxsus xotira papkasi
    python svg_quality_report.py --json report.json # mashina-format

Yozuvlar `_remember_drawing_quality` tomonidan har chizishda avtomatik
yoziladi (igris_agent).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

DEFAULT_MEM_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 os.pardir, "Igris_Memory", "brain_data"))
SOLUTION_REL = ("persistent", "07-solution.jsonl")

_WEAK_RE = re.compile(r"zaif jihatlar:\s*(.+?)(?:\s*\|\s*taklif:|\s*$)")
# Verdikt apostrofli bo'lishi mumkin: (a'lo), (o'rta) — [^)]+ hammasini oladi
_SCORE_RE = re.compile(r"score=(\d+)/100\s*\(([^)]+)\)")
_STYLE_RE = re.compile(r"style=(\w+)")
_FILE_RE = re.compile(r"file=([^ |]+)")
_SUB_RE = re.compile(r"structure=(\d+) composition=(\d+) style=(\d+) palette=(\d+)")


def parse_quality_entry(entry: dict) -> dict | None:
    """Bitta L2 yozuvidan CHIZMA SIFATI ma'lumotlarini ajratib oladi."""
    content = str(entry.get("content") or "")
    if not content.startswith("CHIZMA SIFATI"):
        return None
    sm = _SCORE_RE.search(content)
    if not sm:
        return None
    sub = _SUB_RE.search(content)
    weak_raw = _WEAK_RE.search(content)
    weak = []
    if weak_raw:
        weak = [w.strip() for w in re.split(r"[;,]", weak_raw.group(1))
                if w.strip() and w.strip() != "yo'q"]
    st = _STYLE_RE.search(content)
    fm = _FILE_RE.search(content)
    return {
        "score": int(sm.group(1)),
        "verdict": sm.group(2),
        "style": st.group(1) if st else "cartoon",
        "file": fm.group(1) if fm else "?",
        "weak": weak,
        "structure": int(sub.group(1)) if sub else 0,
        "composition": int(sub.group(2)) if sub else 0,
        "style_score": int(sub.group(3)) if sub else 0,
        "palette": int(sub.group(4)) if sub else 0,
        "remembered_at": entry.get("remembered_at") or "",
    }


def load_quality_entries(mem_dir: str) -> list[dict]:
    """L2 solution faylidan CHIZMA SIFATI yozuvlarini o'qiydi (xronologik)."""
    path = os.path.join(mem_dir, *SOLUTION_REL)
    if not os.path.isfile(path):
        return []
    out = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                parsed = parse_quality_entry(entry)
                if parsed:
                    out.append(parsed)
    except OSError:
        return []
    return out


def _avg(nums: list[int]) -> float:
    return sum(nums) / len(nums) if nums else 0.0


def build_report(entries: list[dict]) -> dict:
    """Yozuvlardan yig'ma hisobot tuzadi."""
    report: dict = {
        "count": len(entries),
        "avg_score": 0.0, "min_score": 0, "max_score": 0,
        "verdict_distribution": {}, "style_scores": {},
        "weak_histogram": {}, "recent": [],
        "trend": [], "moving_avg": [],
    }
    if not entries:
        return report
    scores = [e["score"] for e in entries]
    report["avg_score"] = round(_avg(scores), 1)
    report["min_score"] = min(scores)
    report["max_score"] = max(scores)
    report["verdict_distribution"] = dict(Counter(e["verdict"] for e in entries))
    styles: dict[str, list[int]] = {}
    weak_counter: Counter = Counter()
    for e in entries:
        styles.setdefault(e["style"], []).append(e["score"])
        weak_counter.update(e["weak"])
    report["style_scores"] = {
        style: {"count": len(v), "avg": round(_avg(v), 1), "min": min(v), "max": max(v)}
        for style, v in sorted(styles.items())
    }
    report["weak_histogram"] = dict(weak_counter.most_common())
    report["recent"] = entries[-5:]
    # trend: oxirgi 10 ball + 3-oynoli harakatlanuvchi o'rtacha
    tail = scores[-10:]
    report["trend"] = tail
    report["moving_avg"] = [round(_avg(tail[max(0, i - 2):i + 1]), 1)
                            for i in range(len(tail))]
    return report


def format_report(report: dict) -> str:
    if report["count"] == 0:
        return "CHIZMA SIFATI yozuvlari topilmadi (hali chizish feedback'i yo'q)."
    lines = [
        f"Chizma sifati: {report['count']} ta baholangan chizma",
        f"O'rtacha: {report['avg_score']}/100 | min {report['min_score']} | max {report['max_score']}",
        "Verdiktlar: " + ", ".join(f"{k}: {v}" for k, v in report["verdict_distribution"].items()),
    ]
    if report["style_scores"]:
        lines.append("Uslublar: " + ", ".join(
            f"{style}: {v['avg']}/100 ({v['count']} ta)" for style, v in report["style_scores"].items()))
    if report["weak_histogram"]:
        top = list(report["weak_histogram"].items())[:6]
        lines.append("Eng ko'p zaifliklar: " + ", ".join(f"{w} ({n}x)" for w, n in top))
    t = report["trend"]
    if len(t) >= 3:
        lines.append("So'nggi ballar: " + " ".join(str(s) for s in t))
        lines.append("Tendensiya (3-oyna): " + " ".join(str(m) for m in report["moving_avg"]))
        first, last = report["moving_avg"][0], report["moving_avg"][-1]
        lines.append(("Sifat oshmoqda (+)" if last > first + 3
                      else "Sifat pasaymoqda (-)" if last < first - 3
                      else "Sifat barqaror (=)"))
    lines.append("Oxirgi chizmalar:")
    for e in report["recent"][-3:]:
        weak = ", ".join(e["weak"]) if e["weak"] else "—"
        lines.append(f"  [{e['score']}/100] {e['file']} ({e['style']}) | zaif: {weak}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SVG chizma sifat tendensiyasi hisoboti.")
    ap.add_argument("--dir", default=DEFAULT_MEM_DIR, help="xotira papkasi (default: Igris_Memory/brain_data)")
    ap.add_argument("--json", metavar="OUT", help="JSON hisobot fayliga yozish")
    args = ap.parse_args(argv)
    entries = load_quality_entries(args.dir)
    report = build_report(entries)
    print(format_report(report))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print(f"\nJSON hisobot: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
