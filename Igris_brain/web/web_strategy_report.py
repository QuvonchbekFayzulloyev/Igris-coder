"""Web strategiya kuzatuv hisoboti.

`logs/web_strategy.jsonl` (igris_agent._log_web_strategy yozadi) dagi yozuvlarni
yig'ib, agent web so'rovlarni QANDAY hal qilganini ko'rsatadi — xatolarni
topish uchun:

- strategiya taqsimoti (delegate / browser / full)
- verdict taqsimoti (ok / misuse / no-web-tool / unexpected / unavailable...)
- muammoli holatlar ro'yxati (noto'g'ri klassifikatsiya yoki noto'g'ri tool)
- delegatsiya vs browser haqiqiy ishlatilishi

Ishlatish:
    python web_strategy_report.py                     # default log fayli
    python web_strategy_report.py --log logs/x.jsonl  # maxsus fayl
    python web_strategy_report.py --json report.json  # mashina-format
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter

DEFAULT_LOG = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "web_strategy.jsonl"))

# Muammosiz verdictlar — hisobot ularni alohida sanamaydi.
OK_VERDICTS = {
    "ok-delegate", "ok-browser", "ok-full",
    "browser-fallback",   # delegate'da faqat o'qish browser (zaxira)
    "delegated-instead",  # browser kutilgan, web AI'ga topshirildi (ma'qul)
}
# Muammoli verdictlar — xatolarni topish uchun asosiy e'tibor.
PROBLEM_VERDICTS = {
    "misuse-browser",   # delegate kerak edi, interaktiv browser ishlatildi
    "no-web-tool",      # strategiya bor, lekin web tool ishlatilmadi
    "unexpected-web",   # strategiyasiz web tool chaqirildi
    "unavailable",      # web_ai_bridge ulanmagan
    "other-web",        # noma'lum web tool
}


def load_entries(path: str = DEFAULT_LOG) -> list[dict]:
    """JSONL log faylidan web strategiya yozuvlarini o'qiydi."""
    if not os.path.isfile(path):
        return []
    entries: list[dict] = []
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except (ValueError, TypeError):
                continue
    return entries


def build_report(entries: list[dict]) -> dict:
    """Log yozuvlaridan yig'ma hisobot tuzadi."""
    total = len(entries)
    strategy_dist: Counter = Counter(e.get("strategy") or "" for e in entries)
    verdict_dist: Counter = Counter(e.get("verdict") or "?" for e in entries)
    matched_dist: Counter = Counter()
    for e in entries:
        for m in (e.get("matched") or []):
            matched_dist[str(m)] += 1
    problems: list[dict] = []
    for e in entries:
        v = e.get("verdict") or "?"
        if v in PROBLEM_VERDICTS:
            problems.append({
                "ts": e.get("ts") or "",
                "message": (e.get("message") or "")[:120],
                "strategy": e.get("strategy") or "",
                "verdict": v,
                "tool_calls": (e.get("tool_calls") or [])[:4],
                "engine": e.get("engine") or "",
            })
    ok_count = sum(c for v, c in verdict_dist.items() if v in OK_VERDICTS)
    problem_count = sum(c for v, c in verdict_dist.items() if v in PROBLEM_VERDICTS)
    delegation_used = sum(1 for e in entries if e.get("delegation_used"))
    browser_used = sum(1 for e in entries if e.get("browser_used"))
    # TOOL TANLASH SIFATI — model strategiyaga mos tool tanladimi?
    # (hint'lar samarali ishlayaptimi degan savolga javob beradi)
    # Bucket'lar barcha verdictlarni qoplaydi: correct + missed + wrong_family
    # + gate_breach + unavailable = total.
    wrong_family_count = (verdict_dist.get("misuse-browser", 0)
                          + verdict_dist.get("other-web", 0))
    missed_count = verdict_dist.get("no-web-tool", 0)
    gate_breach_count = verdict_dist.get("unexpected-web", 0)
    selection = {
        # "correct" = QABUL QILINGAN tanlov: mos oila (ok-*) yoki ma'qul
        # muqobil (browser-fallback / delegated-instead). Qat'iy hint-following
        # alohida o'lchanadi — pastdagi hint_effectiveness.
        "correct": ok_count,
        "missed": missed_count,                          # strategiya bor, tool ishlatilmadi
        "wrong_family": wrong_family_count,              # delegate'da interaktiv browser / noma'lum web tool
        "gate_breach": gate_breach_count,                # strategiyasiz web tool
        "correct_rate": round(ok_count / total, 3) if total else 0.0,
        "missed_rate": round(missed_count / total, 3) if total else 0.0,
        "wrong_family_rate": round(wrong_family_count / total, 3) if total else 0.0,
    }
    # HINT SAMARASI — 'PREFER ask_web_ai' ko'rsatmasi amalga oshyaptimi:
    # delegate strategiyasida model web AI'ga topshirdimi, browser'da bevosita
    # ishladimi?
    delegate_count = strategy_dist.get("delegate", 0)
    browser_count = strategy_dist.get("browser", 0)
    delegate_hint_followed = sum(
        1 for e in entries
        if (e.get("strategy") or "") == "delegate" and e.get("delegation_used"))
    browser_direct = sum(
        1 for e in entries
        if (e.get("strategy") or "") == "browser" and e.get("browser_used"))
    hint_effectiveness = {
        "delegate_requests": delegate_count,
        "delegation_used": delegate_hint_followed,
        "delegation_rate": round(delegate_hint_followed / delegate_count, 3) if delegate_count else 0.0,
        "browser_requests": browser_count,
        "browser_direct": browser_direct,
        "browser_rate": round(browser_direct / browser_count, 3) if browser_count else 0.0,
    }
    return {
        "total": total,
        "strategy_dist": dict(strategy_dist),
        "verdict_dist": dict(verdict_dist),
        "matched_dist": dict(matched_dist),
        "ok_count": ok_count,
        "problem_count": problem_count,
        "ok_rate": round(ok_count / total, 3) if total else 0.0,
        "problem_rate": round(problem_count / total, 3) if total else 0.0,
        "delegation_used": delegation_used,
        "browser_used": browser_used,
        "selection": selection,
        "hint_effectiveness": hint_effectiveness,
        "problems": problems[:25],
        "problems_total": len(problems),
    }


def format_report(report: dict) -> str:
    """Hisobotni ASCII matn ko'rinishida chiqaradi (Windows cp1252 xavfsiz)."""
    if not report["total"]:
        return "Log bo'sh - hali web so'rovlar qayd etilmagan."
    lines = [
        "WEB STRATEGY MONITOR REPORT",
        "=" * 40,
        f"Jami web so'rovlar : {report['total']}",
        f"OK rate            : {report['ok_rate']*100:.1f}%  "
        f"({report['ok_count']} ta)",
        f"Muammoli rate      : {report['problem_rate']*100:.1f}%  "
        f"({report['problem_count']} ta)",
        "",
        "Strategiya taqsimoti:",
    ]
    for k, v in sorted(report["strategy_dist"].items(), key=lambda kv: -kv[1]):
        lines.append(f"  {k or '(none)':<12} {v}")
    lines.append("")
    lines.append("Verdict taqsimoti:")
    for k, v in sorted(report["verdict_dist"].items(), key=lambda kv: -kv[1]):
        lines.append(f"  {k:<18} {v}")
    lines.append("")
    lines.append(f"Haqiqiy ishlatilish: delegatsiya {report['delegation_used']} | "
                 f"browser {report['browser_used']}")
    # TOOL TANLASH SIFATI — hint'lar samarali ishlayaptimi
    sel = report.get("selection") or {}
    hint = report.get("hint_effectiveness") or {}
    lines.append("")
    lines.append("TOOL SELECTION QUALITY (hint'lar ishlayaptimi):")
    lines.append(f"  Qabul qilingan tanlov : {sel.get('correct_rate', 0)*100:.1f}%  "
                 f"({sel.get('correct', 0)} ta) - mos oila yoki ma'qul muqobil")
    lines.append(f"  O'tkazib yuborilgan  : {sel.get('missed_rate', 0)*100:.1f}%  "
                 f"({sel.get('missed', 0)} ta) - strategiya bor, tool ishlatilmadi")
    lines.append(f"  Noto'g'ri oila       : {sel.get('wrong_family_rate', 0)*100:.1f}%  "
                 f"({sel.get('wrong_family', 0)} ta) - delegate'da interaktiv "
                 f"browser / noma'lum web tool")
    lines.append(f"  Darvoza chetlab      : {sel.get('gate_breach', 0)} ta")
    lines.append(f"  DELEGATE hint amalga : {hint.get('delegation_rate', 0)*100:.1f}%  "
                 f"({hint.get('delegation_used', 0)}/{hint.get('delegate_requests', 0)}) "
                 f"- ask_web_ai/web_ai_* ishlatildi")
    lines.append(f"  BROWSER hint amalga  : {hint.get('browser_rate', 0)*100:.1f}%  "
                 f"({hint.get('browser_direct', 0)}/{hint.get('browser_requests', 0)}) "
                 f"- browser_* ishlatildi")
    lines.append("")
    lines.append(f"Muammoli holatlar ({report['problems_total']} ta, "
                 f"oxirgi {len(report['problems'])} ta):")
    if report["problems"]:
        for p in report["problems"]:
            lines.append(
                f"  [{p['verdict']}] {p['message'][:70]} "
                f"(strategy={p['strategy'] or '-'}, tools={','.join(p['tool_calls'])[:40] or '-'})"
            )
    else:
        lines.append("  yo'q - barcha web so'rovlar to'g'ri hal qilingan.")
    lines.append("")
    lines.append("Mos kelgan belgilar (klassifikatsiya diagnostikasi):")
    for k, v in sorted(report["matched_dist"].items(), key=lambda kv: -kv[1]):
        lines.append(f"  {k:<10} {v}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Web strategiya kuzatuv hisoboti")
    parser.add_argument("--log", default=DEFAULT_LOG, help="JSONL log fayli yo'li")
    parser.add_argument("--json", metavar="OUT", help="hisobotni JSON faylga yozish")
    args = parser.parse_args()
    entries = load_entries(args.log)
    report = build_report(entries)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print(f"Hisobot -> {args.json}")
    print(format_report(report))


if __name__ == "__main__":
    main()
