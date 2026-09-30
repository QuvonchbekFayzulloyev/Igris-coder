"""
IGRIS BRAIN — World State & Verification Records (Phase 2: Core Loop)
=====================================================================
Arxitektura audit plani §4 + §10 natijasi:

  - §4: tool natijalari avval faqat YIG'ILARDI — confirmed/assumed flag'siz,
    umumiy state obyektiga aylanmasdi. Bu modul OBSERVATION → STATE
    konversatsiyasini beradi (AgentWorldState).
  - §10: verification natijalari tarqoq edi (quality_note + status).
    Bu modul yagona EVIDENCE RECORD beradi (VerificationRecord):
    {action_id, expected, actual, method, status, ts}.

Qoidalar (§17):
  - Confirmed fact = tool `ok:true` natijasi (real observation).
  - Assumed = ok:false yoki flag'siz (ishonchsiz — prompt'ga "assume" bilan kiradi).
  - Verification status faqat comparison funksiyadan keladi (LLM emas).

Run: python world_state.py   (o'z-o'zini tekshiruv)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state.state_machine import VerificationStatus

MAX_OBSERVATIONS = 200        # xotira xavfsiz chegarasi
COMPRESS_KEEP_LAST = 20       # compress'dan keyin saqlanadigan oxirgi yozuvlar


def _now() -> float:
    return round(time.time(), 3)


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


# ------------------------------------------------------------------ #
# Observation — bitta tool natijasi (§4)
# ------------------------------------------------------------------ #

@dataclass
class Observation:
    """Tool natijasidan olingan bitta kuzatuv.

    confirmed=True  -> tool `ok:true` qaytardi (TASDIQLANGAN fakt)
    confirmed=False -> xato/bo'sh (ASSUMED — ishonchsiz, faqat taxmin)
    """
    id: str
    action_id: str              # qaysi Action (tool chaqiruv) dan keldi
    source: str                 # tool nomi
    content: str                # ixcham mazmun (preview)
    confirmed: bool
    timestamp: float = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "action_id": self.action_id, "source": self.source,
            "content": self.content[:300], "confirmed": self.confirmed,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_tool_record(cls, record: dict) -> "Observation":
        """Executor `tool_calls` record'idan Observation yasaydi (§4 konversiya)."""
        result = record.get("result") or {}
        ok = bool(result.get("ok"))
        content = str(record.get("output_preview")
                      or result.get("output")
                      or result.get("content")
                      or result.get("error")
                      or "")
        return cls(
            id=_uid("obs"),
            action_id=str(record.get("action_id") or ""),
            source=str(record.get("tool") or ""),
            content=content[:300],
            confirmed=ok,
        )


# ------------------------------------------------------------------ #
# AgentWorldState — tool natijalaridan yig'ilgan joriy holat (§4)
# ------------------------------------------------------------------ #

@dataclass
class AgentWorldState:
    """Run davomida yig'ilgan TASDIQLANGAN holat.

    - `add_from_record()` har tool chaqiruvdan keyin chaqiriladi.
    - `confirmed_facts()` — faqat tasdiqlangan faktlar (LLM prompt'ga).
    - `compress_old()` — eski observationlarni summary'ga aylantiradi
      (§4 'eski observation'larni tozalash/compress').
    """
    observations: list[Observation] = field(default_factory=list)
    files_touched: dict = field(default_factory=dict)   # path -> {"bytes": n, "ts": float}
    last_error: str | None = None
    compressed_summaries: list[str] = field(default_factory=list)

    # ---------------- yozish ---------------- #

    def add_from_record(self, record: dict) -> Observation:
        """Executor tool record'idan observation qo'shadi (§4 asosiy kirish nuqtasi).

        write_file/apply_patch muvaffaqiyatli bo'lsa — files_touched yangilanadi
        (current world state: qaysi fayllar o'zgargani ma'lum bo'ladi).
        """
        obs = Observation.from_tool_record(record)
        self.observations.append(obs)
        if len(self.observations) > MAX_OBSERVATIONS:
            self.compress_old()
        if obs.confirmed and obs.source in ("write_file", "apply_patch"):
            path = str((record.get("args") or {}).get("path") or "")
            if path:
                self.files_touched[path] = {
                    "bytes": int((record.get("result") or {}).get("bytes") or 0),
                    "ts": obs.timestamp,
                }
        if not obs.confirmed and obs.content:
            self.last_error = obs.content
        return obs

    def observation_flags(self) -> list[str]:
        """SM OBSERVE→VERIFY guard'i uchun flag (Phase 1 bilan bog'lanadi).

        Kamida bitta confirmed observation bo'lsa — 'confirmed';
        aks holda faqat assumed (verify UNKNOWN beradi — COMPLETE taqiqlanadi).
        """
        if any(o.confirmed for o in self.observations):
            return ["confirmed"]
        if self.observations:
            return ["assumed"]
        return []

    # ---------------- o'qish ---------------- #

    def confirmed_facts(self, limit: int = 20) -> list[str]:
        """Faqat TASDIQLANGAN faktlar (prompt'ga 'confirmed' sifatida kiradi)."""
        return [f"[{o.source}] {o.content}"
                for o in self.observations if o.confirmed][-limit:]

    def assumed_notes(self, limit: int = 10) -> list[str]:
        """Ishonchsiz (xato/taxmin) yozuvlar — alohida, aralashtirilmaydi."""
        return [f"[{o.source}] {o.content}"
                for o in self.observations if not o.confirmed][-limit:]

    def stats(self) -> dict:
        return {
            "observations": len(self.observations),
            "confirmed": sum(1 for o in self.observations if o.confirmed),
            "assumed": sum(1 for o in self.observations if not o.confirmed),
            "files_touched": len(self.files_touched),
            "compressed": len(self.compressed_summaries),
        }

    # ---------------- compress (§4/§6) ---------------- #

    def compress_old(self, keep_last: int = COMPRESS_KEEP_LAST) -> str:
        """Eski observationlarni bitta summary'ga siqadi (oxirgi N saqlanadi).

        Qaytadi: summary matn (bo'sh bo'lsa siqish kerak emas).
        """
        if len(self.observations) <= keep_last:
            return ""
        old = self.observations[:-keep_last]
        self.observations = self.observations[-keep_last:]
        ok_count = sum(1 for o in old if o.confirmed)
        tools = sorted({o.source for o in old})
        summary = (f"[compressed {len(old)} old observations] "
                   f"tools used: {', '.join(tools)[:200]}; "
                   f"confirmed: {ok_count}, failed: {len(old) - ok_count}; "
                   f"files touched so far: {len(self.files_touched)}")
        self.compressed_summaries.append(summary)
        return summary

    # ---------------- serializatsiya (§16) ---------------- #

    def to_dict(self) -> dict:
        return {
            "observations": [o.to_dict() for o in self.observations],
            "files_touched": dict(self.files_touched),
            "last_error": self.last_error,
            "compressed_summaries": list(self.compressed_summaries),
        }


# ------------------------------------------------------------------ #
# VerificationRecord — yagona evidence (§10/§16)
# ------------------------------------------------------------------ #

@dataclass
class VerificationRecord:
    """Bir tekshiruvning TO'LIQ isboti: nima kutildi, nima chiqdi, qanday.

    §10 evidence talabi: expected + actual + method + status + timestamp —
    bitta joyda, serializatsiya qilinadigan shaklda.
    """
    action_id: str              # qaysi action/task tekshirildi
    expected: dict              # {files: [...], min_bytes, syntax_ok, runs: bool}
    actual: dict                # {files_written: [...], bytes, syntax, run}
    method: str                 # syntax | run | deliverable | grounding | manual
    status: str                 # VerificationStatus qiymati
    note: str = ""
    timestamp: float = field(default_factory=_now)

    @staticmethod
    def make(action_id: str, method: str, ok: bool | None,
             expected: dict | None = None, actual: dict | None = None,
             note: str = "") -> "VerificationRecord":
        """Deterministik status: ok=True→VERIFIED, False→FAILED, None→UNKNOWN."""
        status = (VerificationStatus.VERIFIED.value if ok is True
                  else VerificationStatus.FAILED.value if ok is False
                  else VerificationStatus.UNKNOWN.value)
        return VerificationRecord(
            action_id=action_id,
            expected=dict(expected or {}),
            actual=dict(actual or {}),
            method=method,
            status=status,
            note=note[:300],
        )

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id, "expected": self.expected,
            "actual": self.actual, "method": self.method,
            "status": self.status, "note": self.note,
            "timestamp": self.timestamp,
        }


class VerificationLog:
    """Run davomidagi barcha tekshiruvlar tarixi (§16 verification log)."""

    def __init__(self):
        self.records: list[VerificationRecord] = []

    def add(self, record: VerificationRecord) -> VerificationRecord:
        self.records.append(record)
        return record

    def final_status(self) -> str:
        """Oxirgi tekshiruv statusi (SM COMPLETE guard'i uchun asos)."""
        return self.records[-1].status if self.records else VerificationStatus.UNKNOWN.value

    def to_list(self) -> list[dict]:
        return [r.to_dict() for r in self.records]


# ------------------------------------------------------------------ #
# Loop detection (§9): aylanma + stuck-state — deterministik
# ------------------------------------------------------------------ #

def detect_loop(tool_signatures: list[str], window: int = 6,
                repeat_threshold: int = 2) -> tuple[bool, str]:
    """Aylanma aniqlash: oxirgi `window` chaqiruvda bir xil signature
    `repeat_threshold`+ marta qaytarilsa — stuck/loop.

    signature = "tool:normalized_args_hash" (executor to'laydi).
    Bu EXACT dedup'dan kuchli: A→B→A→B naqshini ham ushlaydi.
    """
    recent = [s for s in (tool_signatures or [])[-window:] if s]
    if len(recent) < 3:
        return False, ""
    from collections import Counter
    counts = Counter(recent)
    sig, n = counts.most_common(1)[0]
    if n >= repeat_threshold and n > 1:
        return True, f"pattern repeats {n}x in last {len(recent)}: {sig[:80]}"
    return False, ""


def detect_stuck(writes_so_far: int, iterations: int,
                 stall_limit: int = 6) -> tuple[bool, str]:
    """Stuck-state: `stall_limit` iteratsiyadan keyin ham HECH QANDAY
    yozma ish (write/patch) bo'lmasa — agent aylanmoqda."""
    if iterations >= stall_limit and writes_so_far == 0:
        return True, (f"no write/patch after {iterations} iterations "
                      f"(stall_limit={stall_limit})")
    return False, ""


# ------------------------------------------------------------------ #
# O'z-o'zini tekshiruv
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    ws = AgentWorldState()
    rec_ok = {"tool": "write_file", "action_id": "act-1",
              "args": {"path": "a.txt"}, "result": {"ok": True, "bytes": 100},
              "output_preview": "written"}
    rec_err = {"tool": "run_command", "action_id": "act-2",
               "args": {"command": "x"}, "result": {"ok": False, "error": "boom"},
               "output_preview": "boom"}
    ws.add_from_record(rec_ok)
    ws.add_from_record(rec_err)
    assert ws.stats()["confirmed"] == 1 and ws.stats()["assumed"] == 1
    assert "a.txt" in ws.files_touched
    assert ws.observation_flags() == ["confirmed"]
    assert ws.last_error == "boom"
    assert len(ws.confirmed_facts()) == 1 and ws.assumed_notes()
    print("PASS | AgentWorldState add/flags/files")

    ws2 = AgentWorldState()
    for i in range(30):
        ws2.add_from_record({"tool": "read_file", "action_id": f"a{i}",
                             "args": {}, "result": {"ok": True},
                             "output_preview": f"n{i}"})
    summary = ws2.compress_old(keep_last=5)
    assert summary and ws2.stats()["observations"] == 5
    assert ws2.stats()["compressed"] == 1
    print("PASS | compress_old")

    vr = VerificationRecord.make("act-1", "syntax", True,
                                 expected={"syntax_ok": True},
                                 actual={"syntax": "ok"}, note="ast parse")
    assert vr.status == "VERIFIED" and vr.to_dict()["method"] == "syntax"
    vr2 = VerificationRecord.make("act-2", "run", False)
    vr3 = VerificationRecord.make("act-3", "deliverable", None)
    log = VerificationLog()
    log.add(vr); log.add(vr2); log.add(vr3)
    assert log.final_status() == "UNKNOWN" and len(log.to_list()) == 3
    print("PASS | VerificationRecord + log")

    loop, why = detect_loop(["w:1", "r:2", "w:1", "r:2", "w:1", "r:2"])
    assert loop and "repeats" in why
    loop2, _ = detect_loop(["w:1", "r:2", "w:3"])
    assert not loop2
    stuck, why2 = detect_stuck(writes_so_far=0, iterations=7)
    assert stuck and "no write" in why2
    stuck2, _ = detect_stuck(writes_so_far=1, iterations=7)
    assert not stuck2
    print("PASS | detect_loop + detect_stuck")

    obs = Observation.from_tool_record(rec_ok)
    assert obs.confirmed and obs.action_id == "act-1" and obs.id.startswith("obs-")
    print("PASS | Observation.from_tool_record")

    print("OK | world_state selftest")
