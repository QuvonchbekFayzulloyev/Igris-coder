"""
IGRIS BRAIN — Checkpoint Integrity & Reconciliation (Roadmap v3 R2)
====================================================================
§10 Checkpoint integrity + §22 Reality reconciliation + §23 external
reconciliation + §11 duplicate protection.

Funksiyalar (barchasi DETERMINISTIK — LLM'siz):
  - reconcile_steps(): resume'dan OLDIN fs holatini checkpoint'dagi
    completed step'lar bilan solishtiradi:
        * step'da yozilishi kerak fayl HAZIR      -> step SKIP (duplicate'siz)
        * step'da yozilishi kerak fayl YO'QOLGAN  -> step RE-EXECUTE (re-plan)
    Reja step'larida fayl nomlari step.tools/args/task matnidan chiqariladi.
  - is_stale(): checkpoint ts vs workspace fayl mtimes — tashqi o'zgarish
    checkpoint'dan KEYIN bo'lgan bo'lsa (stale) True.
  - dedupe_actions(): resume'da already-done action_id'lar qayta
    bajarilmasligi uchun registry (executor _cp_skip bilan birga).

Fail-safe falsafa: har xato None/False qaytaradi — reconciliation muvaffaqiyatsizligi
resume'ni BUZMAYDI (eski xatti-harakat: barcha completed step'lar skip).
"""
from __future__ import annotations

import os
import re
from typing import Optional

# Fayl nomi: path/quote bo'lmagan, kengaytmali token (deterministik extraction).
_FILE_TOKEN_RE = re.compile(
    r"[\w./\\-]+\.(?:txt|md|json|csv|py|js|ts|tsx|html|css|svg|png|jpg|jpeg|"
    r"gif|webp|bmp|ico|xml|yml|yaml|ini|log|pdf|docx|xlsx|pptx|sh|bat|toml)",
    re.IGNORECASE,
)

# Step natijasi fayl yozish bilan yakunlanganmi — deterministik belgilar.
_WRITE_TOOLS = ("write_file", "apply_patch")


def extract_step_files(step: dict, task: str = "") -> list[str]:
    """Step (va task) matnidan fayl nomlarini ajratadi (deterministik).

    Step'nin title/results/tool args'laridan + task matnidan. Path
    separatorlar normalize qilinadi ('\\\\' -> '/').
    """
    names: list[str] = []
    seen: set[str] = set()

    def _add_from(text: str) -> None:
        for m in _FILE_TOKEN_RE.finditer(text or ""):
            name = m.group(0).replace("\\\\", "/").strip("./")
            if name and name not in seen:
                seen.add(name)
                names.append(name)

    _add_from(str(step.get("title") or ""))
    _add_from(str(step.get("detail") or ""))
    for t in step.get("tools") or []:
        _add_from(str(t))
    for tc in step.get("tool_calls") or []:
        args = (tc.get("args") or {}) if isinstance(tc, dict) else {}
        p = args.get("path")
        if isinstance(p, str) and p and p not in seen:
            seen.add(p)
            names.append(p)
    _add_from(task or "")
    return names


def _step_wrote_files(step: dict) -> bool:
    """Step bajarilishida fayl YOZILGANMI (tool nomlari bo'yicha)."""
    for tc in step.get("tool_calls") or []:
        if isinstance(tc, dict) and tc.get("tool") in _WRITE_TOOLS:
            return True
    tools = step.get("tools") or []
    return any(t in _WRITE_TOOLS for t in tools)


def reconcile_steps(
    plan_steps: list[dict],
    completed_step_ids: list[int],
    workspace_root: str,
    task: str = "",
) -> Optional[dict]:
    """§22: resume'dan oldin fs holatini checkpoint bilan solishtiradi.

    Qaytaradi (yoki xatoda None):
      {
        "skip_ids":  [...]  # fs bilan TASDIQLANGAN step'lar (xavfsiz skip)
        "redo_ids":  [...]  # fayllari YO'QOLGAN step'lar (qayta bajariladi)
        "missing_files": {step_id: [fayl...]},
        "verified_files": {step_id: [fayl...]},
        "reconciled": True
      }

    Qoidalar:
      - checkpoint'da completed, lekin step YOZMA emas (read/run/...) —
        fs tekshiruvi mumkin emas -> SKIP (eski xulq).
      - step YOZMA + step'NING O'Z fayl nomlari BARCHASI workspace'da
        mavjud -> SKIP (artefakt hazir — duplicate himoya, §11/§22).
        Task-matn fayllari FAQAT boshqa dalil yo'qida qo'llanadi.
      - step YOZMA + O'Z fayllarida YO'Q'ari bor -> RE-EXECUTE (re-plan).
      - YOZMA step'da fayl nomi ANIQLANMADI -> SKIP (ehtiyotkor default —
        fs dalilsiz redo duplicate side-effect xavfini oshiradi).
    """
    try:
        done = set(int(i) for i in (completed_step_ids or []))
    except Exception:
        return None
    if not done:
        return {"skip_ids": [], "redo_ids": [], "missing_files": {},
                "verified_files": {}, "reconciled": True}

    skip_ids: list[int] = []
    redo_ids: list[int] = []
    missing_files: dict[int, list[str]] = {}
    verified_files: dict[int, list[str]] = {}

    for step in plan_steps or []:
        try:
            sid = int(step.get("id"))
        except Exception:
            continue
        if sid not in done:
            continue
        if not _step_wrote_files(step):
            skip_ids.append(sid)   # yozma emas — fs tekshiruvi shart emas
            continue
        # R2: faqat step'NING O'Z fayllari (title/detail/tool args) — task
        # matni boshqa step'lar fayllarini ifloslantirmasligi uchun.
        files = extract_step_files(step, "")
        # Step'ning o'z matnida fayl nomi yo'q — task matndan umumiy nomlar
        # bilan urinish (kichik planlarda step title qisqa bo'ladi).
        if not files:
            files = extract_step_files({"title": str(step.get("title") or "")}, task)
        if not files:
            skip_ids.append(sid)   # fayl nomi aniqlanmadi — ehtiyotkor skip
            continue
        present, missing = [], []
        for name in files:
            full = os.path.join(workspace_root, name)
            if os.path.isfile(full) and os.path.getsize(full) > 0:
                present.append(name)
            else:
                missing.append(name)
        if missing:
            redo_ids.append(sid)
            missing_files[sid] = missing
        else:
            skip_ids.append(sid)
            verified_files[sid] = present

    return {
        "skip_ids": sorted(set(skip_ids) - set(redo_ids)),
        "redo_ids": sorted(set(redo_ids)),
        "missing_files": missing_files,
        "verified_files": verified_files,
        "reconciled": True,
    }


def is_stale(checkpoint: Optional[dict], workspace_root: str,
             grace_seconds: float = 0.25) -> bool:
    """§23: checkpoint'dan KEYIN workspace o'zgarganmi (tashqi yoki crash
    oralig'idagi yozuvlar)?

    Har qanday fayl mtime > checkpoint.ts + grace — stale. Grace kichik
    (fs timestamp yaxlitlash uchun) — checkpoint har step'dan keyin
    saqlangani uchun crash oralig'idagi o'z yozuvlari ham stale hisoblanadi
    (bu TO'G'RI: checkpoint bu yozuvlarni qamrab olmaydi).
    Checkpoint ts yo'q/pars qilinmasa — False (stalelik da'vo qilinmaydi).
    Fail-safe: fs xatosida False.
    """
    if not checkpoint:
        return False
    try:
        ts = float(checkpoint.get("ts") or 0.0)
    except Exception:
        return False
    if ts <= 0:
        return False
    cutoff = ts + max(0.0, float(grace_seconds))
    try:
        for root, _dirs, files in os.walk(workspace_root):
            for f in files:
                try:
                    if os.path.getmtime(os.path.join(root, f)) > cutoff:
                        return True
                except Exception:
                    continue
            if len(files) > 500:
                break
    except Exception:
        return False
    return False


def merge_skip_with_reconciliation(
    checkpoint_skip: list[int],
    recon: Optional[dict],
) -> tuple[set[int], dict]:
    """Checkpoint skip to'plami + reconciliation natijasini birlashtiradi.

    Qaytaradi: (final_skip_set, recon_report)
      - checkpoint'da completed + fs tasdiqlangan -> skip
      - checkpoint'da completed, lekin RE-EXECUTE kerak -> skip'dan OLIB
        TASHLANADI (qayta bajariladi — §22 re-plan signal)
    recon None bo'lsa — checkpoint skip o'zgarmaydi (fail-safe eski xulq).
    """
    try:
        skip = set(int(i) for i in (checkpoint_skip or []))
    except Exception:
        skip = set()
    if not recon or not recon.get("reconciled"):
        return skip, {"reconciled": False, "skip_ids": sorted(skip), "redo_ids": []}
    redo = set(int(i) for i in (recon.get("redo_ids") or []))
    final = (skip - redo) | (set(int(i) for i in (recon.get("skip_ids") or [])))
    report = dict(recon)
    report["checkpoint_skip_original"] = sorted(skip)
    return final, report
