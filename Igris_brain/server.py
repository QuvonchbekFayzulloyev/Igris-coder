"""
IGRIS BRAIN  -  FastAPI Bridge Server
===================================
Exposes the hybrid agent (bricks + RAG memory + Ollama LLM) over HTTP so the
Igris_Interface (web/desktop) can talk to the real backend instead of mock data.

Run:
    cd Igris_brain
    python server.py                # http://localhost:8765
    python server.py --port 8765 --no-llm
    python server.py --model qwen3:8b --memory ../Igris_Memory/brain_data

Endpoints:
    GET  /api/status                -> agent + memory + llm status
    GET  /api/llm/models            -> local Ollama models
    POST /api/resolve               -> hybrid resolution {query}
    POST /api/chat                  -> conversational {message, history[]}
    POST /api/memory/search         -> RAG search {query, top_k}
    GET  /api/memory/status         -> memory manager status
    POST /api/session/start|end     -> memory session control
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 2nd Brain moduli alohida papkaga ko'chirildi (2nd_brain/backend)  -- 
# `/api/brain/*` endpoint'laridagi `from brain_graph import ...` shu yerdan topiladi.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "2nd_brain", "backend"))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
import uvicorn  # noqa: E402

from igris_agent import IgrisAgent  # noqa: E402
from memory_bridge import MemoryBridge  # noqa: E402
from planner import TaskPlanner  # noqa: E402
from executor import AgentExecutor  # noqa: E402
from layered_agent import LayeredAgent, create_layered_agent, CLARIFICATION_MANAGER  # noqa: E402

# ---------------------------------------------------------------------- #
# Request / response models
# ---------------------------------------------------------------------- #

class ResolveRequest(BaseModel):
    query: str
    allow_llm: bool = True
    use_memory: bool = True

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = Field(default_factory=list)
    use_memory: bool = True
    session_id: str = ""

class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = 5

class SessionRequest(BaseModel):
    session_id: str = ""
    summary: str = ""

class PlanRequest(BaseModel):
    task: str

class RunRequest(BaseModel):
    task: str
    workspace: str = ""
    max_iter: int = 8

class ToolRunRequest(BaseModel):
    task: str
    workspace: str = ""
    max_iter: int = 8

class TaskRequest(BaseModel):
    task: str
    workspace: str = ""
    max_iter: int = 8
    session_id: str = ""

class RespondRequest(BaseModel):
    run_id: str
    answer: str

class ModelRequest(BaseModel):
    model: str

class SpeedRequest(BaseModel):
    turbo: bool = False

class WebAIActionRequest(BaseModel):
    action: str
    url: str = ""
    index: int = 0

class DrawingEditRequest(BaseModel):
    path: str
    request: str
    frozen: dict = Field(default_factory=dict)
    workspace: str = ""

class ChatIdRequest(BaseModel):
    id: str

class ChatStarRequest(BaseModel):
    id: str
    starred: bool = True

class ChatRenameRequest(BaseModel):
    id: str
    title: str


# Surgikal tahrir  --  agent faqat kerakli qismlarni o'zgartiradi, qolganini
# xuddi o'zicha qoldiradi (frozen kontekst asosida).
DRAWING_EDIT_SYSTEM = (
    "You are Igris, a surgical SVG editor. The user is watching an SVG drawing "
    "being built step-by-step and paused it to request a change.\n\n"
    "HARD RULES:\n"
    "1. read_file the target SVG file FIRST. Copy its content into your head.\n"
    "2. Write the ENTIRE modified SVG in ONE write_file call to the SAME path. "
    "Do NOT create a new/placeholder drawing  --  you must reproduce the full file.\n"
    "3. Every element that does not need to change must appear BYTE-IDENTICAL in "
    "the new file: same tags, same attributes, same coordinates, same colors, "
    "same stroke widths, same order. Copy them verbatim from the file you read.\n"
    "4. Change ONLY the specific part(s) the user's request is about, and only the "
    "attributes/values that must change (e.g. change only the roof polygon's fill "
    "from '#c23b3b' to a green hex  --  leave its points and stroke untouched).\n"
    "5. Keep the overall style consistent  --  use a similar palette, stroke widths "
    "and sizes as the rest of the drawing so nothing looks out of place.\n"
    "6. Finish with a 1-2 sentence summary naming EXACTLY which element(s) changed "
    "and which stayed identical.\n"
    "If you need drawing guidance use use_skill('svg-artist')."
)

# ---------------------------------------------------------------------- #
# Universal speed (TURBO) sozlamasi  --  diskda saqlanadi, restart'da qo'llanadi
# ---------------------------------------------------------------------- #

_SPEED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speed_settings.json")
_SPEED = {"turbo": False}


def _load_speed() -> dict:
    """TURBO sozlamasini diskdan o'qiydi (server restart'da yo'qolmaydi)."""
    global _SPEED
    try:
        if os.path.isfile(_SPEED_FILE):
            with open(_SPEED_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and "turbo" in data:
                _SPEED["turbo"] = bool(data["turbo"])
    except (OSError, json.JSONDecodeError):
        pass
    return _SPEED


def _persist_speed():
    try:
        with open(_SPEED_FILE, "w", encoding="utf-8") as fh:
            json.dump(_SPEED, fh, ensure_ascii=False)
    except OSError:
        pass


# ---------------------------------------------------------------------- #
# 2nd Brain graf sozlamalari  --  graph_shares.json (server restart'da saqlanadi)
# ---------------------------------------------------------------------- #

_GRAPH_SHARES_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "2nd_brain", "backend",
    "graph_shares.json")
# None = default ulushlar; max_nodes None = default chegarasi;
# updated_at/history  --  o'zgarishlar kuzatuvi.
_GRAPH_SHARES: dict = {
    "shares": None, "max_nodes": None, "updated_at": None, "history": []}
# Graf node'larining standart yuqori chegarasi (build_graph default'iga mos).
_GRAPH_MAX_NODES_DEFAULT = 240
# Tarixda eng ko'pi shuncha yozuv qoladi (cheksiz o'smaydi).
_GRAPH_SHARES_HISTORY_LIMIT = 20


def _clamp_max_nodes(v) -> Optional[int]:
    """max_nodes'ni xavfsiz normallashtiradi: [30, 2000] diapazon.

    Noto'g'ri tur/qiymat (None, 'abc', 5, 99999, nan...) -> None (default).
    """
    try:
        n = int(float(v))
    except (TypeError, ValueError, OverflowError):
        # OverflowError: float('inf') -> int() beradi (500 o'rniga default).
        return None
    if not (30 <= n <= 2000):
        return None
    return n


def _load_graph_shares() -> dict:
    """Graf sozlamalarini diskdan o'qiydi (server restart'da yo'qolmaydi).

    Yangi format: {shares, max_nodes, updated_at, history}. Eski format
    (faqat {shares: [...]}) ham qo'llab-quvvatlanadi  -  max_nodes default
    qoladi, tarix bo'sh boshlanadi.
    """
    global _GRAPH_SHARES
    try:
        if os.path.isfile(_GRAPH_SHARES_FILE):
            with open(_GRAPH_SHARES_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                if isinstance(data.get("shares"), list):
                    _GRAPH_SHARES["shares"] = data["shares"]
                if data.get("max_nodes") is not None:
                    _GRAPH_SHARES["max_nodes"] = _clamp_max_nodes(data["max_nodes"])
                _GRAPH_SHARES["updated_at"] = data.get("updated_at")
                hist = data.get("history")
                # Faqat to'g'ri shakldagi yozuvlar olinadi (buzilgan kirsa tashlanadi).
                if isinstance(hist, list):
                    valid = [e for e in hist
                             if isinstance(e, dict)
                             and (isinstance(e.get("shares"), list)
                                  or e.get("max_nodes") is not None)]
                    _GRAPH_SHARES["history"] = valid[-_GRAPH_SHARES_HISTORY_LIMIT:]
                else:
                    _GRAPH_SHARES["history"] = []
    except (OSError, json.JSONDecodeError):
        pass
    return _GRAPH_SHARES


def _persist_graph_shares(shares: Optional[list] = None,
                          max_nodes: Optional[int] = None,
                          updated_at: Optional[float] = None):
    """Graf sozlamalarini diskda saqlaydi; o'zgarish tarixga qo'shiladi.

    Ikkala maydon ham ixtiyoriy  -  None berilgan maydon JORIY qiymatini
    saqlaydi (qisman yangilash: faqat shares yoki faqat max_nodes).
    Qiymat o'zgarmagan bo'lsa yangi yozuv qo'shilmaydi (tarix shovqinsiz).
    """
    now = updated_at if updated_at is not None else time.time()
    cur_shares = _GRAPH_SHARES.get("shares")
    cur_max = _GRAPH_SHARES.get("max_nodes")
    new_shares = list(shares) if shares is not None else \
        (list(cur_shares) if cur_shares else None)
    new_max = max_nodes if max_nodes is not None else cur_max
    prev = _GRAPH_SHARES.get("history", [])
    # Dedup IKKALA qiymatni ko'radi  --  faqat shares bir xil bo'lib max_nodes
    # o'zgarsa ham yangi yozuv kerak (aks holda o'zgarish tarixda yo'qolardi).
    if prev and prev[-1].get("shares") == new_shares \
            and prev[-1].get("max_nodes") == new_max:
        return  # bir xil qiymat  --  takroriy yozuv kerak emas
    _GRAPH_SHARES["shares"] = new_shares
    _GRAPH_SHARES["max_nodes"] = new_max
    _GRAPH_SHARES["updated_at"] = now
    _GRAPH_SHARES["history"] = prev + [{
        "ts": now, "shares": new_shares, "max_nodes": new_max}]
    # Tarix chegarasi  --  eski yozuvlar olib tashlanadi.
    _GRAPH_SHARES["history"] = _GRAPH_SHARES["history"][-_GRAPH_SHARES_HISTORY_LIMIT:]
    try:
        with open(_GRAPH_SHARES_FILE, "w", encoding="utf-8") as fh:
            json.dump(_GRAPH_SHARES, fh, ensure_ascii=False, indent=1)
    except OSError:
        pass


# ---------------------------------------------------------------------- #
# Real chat history  --  chat_history.jsonl ga yoziladi, qayta yuklanadi
# ---------------------------------------------------------------------- #

# ---------------------------------------------------------------------- #
# Chat jonli progress  --  /api/chat sinxron ishlaydi, lekin frontend pipeline
# stepperi JONLI bosqichni shu buferdan poll qiladi (agent progress_cb
# orqali yangilanadi, chat tugagach tozalanadi).
# ---------------------------------------------------------------------- #

CHAT_PROGRESS: dict[str, dict] = {}
CHAT_PROGRESS_LOCK = threading.RLock()


def _chat_progress_cb(session_id: str):
    """Agent chat() uchun progress callback  -  (stage, detail) -> bufer."""
    def _cb(stage: str, detail: str, record=None):
        with CHAT_PROGRESS_LOCK:
            CHAT_PROGRESS[session_id] = {
                "stage": str(stage or ""),
                "stage_detail": str(detail or "")[:120],
                "ts": time.time(),
            }
    return _cb


def _chat_progress_clear(session_id: str):
    with CHAT_PROGRESS_LOCK:
        CHAT_PROGRESS.pop(session_id, None)


CHAT_HISTORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_history.jsonl")


def _structure_fail_warning(data: dict) -> str:
    """structure_check fail (repair qilib bo'lmagan chiqish) bo'lsa transcript
    ogohlantirish matnini qaytaradi, aks holda bo'sh qator. Chat tarixiga
    YOZILADIGAN matn  -  javob buzilgan bo'lishi mumkinligi haqida ogohlantiradi
    (frontend alohida bannerda ko'rsatadi)."""
    sc = data.get("structure_check")
    if isinstance(sc, dict) and sc.get("ok") is False:
        return ("⚠️ Javob strukturasi tekshiruvdan o'tmadi (repair qilib "
                "bo'lmadi)  --  xato yoki to'liqsiz bo'lishi mumkin.")
    return ""


class ChatHistory:
    """Real chat tarixi store  -  har suhbat alohida yozuv, JSONL'ga saqlanadi.

    Frontend sidebar (recents) va 2nd Brain grafi (session node'lar) shu
    manbadan o'qiydi  -  mock ma'lumot o'rniga REAL suhbatlar ko'rinadi.
    """

    # Tombstone fayli (chat_history.jsonl.deleted.json) cheksiz o'smasligi
    # uchun chegaralar:
    #  - TOMBSTONE_RETENTION: o'chirilgan id shuncha vaqtdan keyin avtomatik
    #    tozalanadi (stale jarayon himoyasi uchun shu muddat yetarli)
    #  - TOMBSTONE_MAX_ENTRIES: faylda eng ko'pi shuncha yozuv qoladi
    TOMBSTONE_RETENTION = 30 * 24 * 3600      # 30 kun
    TOMBSTONE_MAX_ENTRIES = 1000

    def __init__(self, path: str = CHAT_HISTORY_PATH, max_keep: int = 60,
                 max_messages: int = 200,
                 tombstone_retention: Optional[float] = None,
                 tombstone_max_entries: Optional[int] = None):
        self.path = path
        self.max_keep = max_keep
        self.max_messages = max_messages
        self.tombstone_retention = (
            tombstone_retention if tombstone_retention is not None
            else self.TOMBSTONE_RETENTION
        )
        self.tombstone_max_entries = (
            tombstone_max_entries if tombstone_max_entries is not None
            else self.TOMBSTONE_MAX_ENTRIES
        )
        self._lock = threading.RLock()
        self._convs: dict[str, dict] = {}
        # O'chirilgan suhbat id'lari (tombstone)  --  id -> o'chirilgan vaqti.
        # Boshqa jarayon ularni qayta yozmasligi uchun alohida faylda
        # saqlanadi; eski yozuvlar avtomatik tozalanadi (fayl o'smaydi).
        self._deleted: dict[str, float] = {}
        self._tomb_path = path + ".deleted.json"
        self._load_tombstones()
        self._load()

    def _load(self):
        # avvalgi yarim yozilgan tmp faylni tozalaymiz
        try:
            if os.path.isfile(self.path + ".tmp"):
                os.unlink(self.path + ".tmp")
        except OSError:
            pass
        if not os.path.isfile(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        conv = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(conv, dict) and conv.get("id"):
                        if conv["id"] in self._deleted:
                            continue
                        self._convs[conv["id"]] = conv
        except OSError:
            pass

    def _load_tombstones(self):
        """O'chirilgan suhbat id'larini diskdan o'qiydi.

        Eski format (id'lar ro'yxati) ham qo'llab-quvvatlanadi; yangi
        format `{id: o'chirilgan_vaqti}` dict'idir. O'qilgach eski
        yozuvlar avtomatik tozalanadi; agar biror yozuv tozalangan bo'lsa
        natija diskka ham yoziladi  -  fayl xotira bilan bir xil bo'ladi
        (aks holda eskirgan tombstone faylda qolib, graf yangidan ochilgan
        suhbatni yashirib qo'yishi mumkin edi).
        """
        try:
            if os.path.isfile(self._tomb_path):
                with open(self._tomb_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    # eski format: faqat id'lar  --  hozirgi vaqtni belgilaymiz
                    now = time.time()
                    self._deleted = {str(x): now for x in data if x}
                elif isinstance(data, dict):
                    self._deleted = {
                        str(k): float(v) for k, v in data.items()
                        if k and isinstance(v, (int, float))
                    }
                before = dict(self._deleted)
                self._prune_tombstones()
                if self._deleted != before:
                    # Tozalangan yozuvlar bor  --  faylni ham yangilaymiz
                    self._save_tombstones()
        except (OSError, json.JSONDecodeError, ValueError):
            pass

    def _prune_tombstones(self):
        """Eski yozuvlarni tozalaydi  -  tombstone fayli cheksiz o'smaydi.

        1) `tombstone_retention` dan eski id'lar tashlanadi (stale jarayon
           himoyasi uchun endi kerak emas);
        2) eng ko'pi `tombstone_max_entries` ta eng YANGI yozuv qoladi.
        """
        now = time.time()
        cutoff = now - self.tombstone_retention
        self._deleted = {
            sid: ts for sid, ts in self._deleted.items() if ts >= cutoff
        }
        if len(self._deleted) > self.tombstone_max_entries:
            # eng yangi `max_entries` ta qoldiramiz. Vaqt TENG bo'lsa (juda tez
            # ketma-ket o'chirish)  --  qo'shilish tartibi hal qiladi (oxirgisi ustun).
            items = list(self._deleted.items())
            order = {sid: i for i, (sid, _) in enumerate(items)}
            newest = sorted(
                items, key=lambda kv: (kv[1], order[kv[0]]), reverse=True
            )[: self.tombstone_max_entries]
            self._deleted = dict(newest)

    def _save_tombstones(self):
        self._prune_tombstones()
        try:
            tmp = self._tomb_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._deleted, fh)
            os.replace(tmp, self._tomb_path)
        except OSError:
            pass

    def _persist(self):
        """Butun suhbatlar to'plamini JSONL'ga atomik yozadi (tmp + replace).

        Yozishdan oldin tombstone fayl qayta o'qiladi  -  boshqa jarayon
        o'chirgan suhbatlar ham qaytadan yozilmaydi (delete DOIMIY bo'ladi,
        suhbatlar qayta yuklanganda yana paydo bo'lmaydi).
        """
        self._load_tombstones()
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                for c in sorted(
                    self._convs.values(), key=lambda c: c.get("updated_at", 0)
                ):
                    if c.get("id") in self._deleted:
                        continue
                    fh.write(json.dumps(c, ensure_ascii=False) + "\n")
            os.replace(tmp, self.path)
        except OSError:
            pass

    def _save(self, conv: dict):
        with self._lock:
            self._convs[conv["id"]] = conv
            # eng eskilarni tashlab, max_keep ichida qolamiz
            if len(self._convs) > self.max_keep:
                for k in sorted(
                    self._convs, key=lambda k: self._convs[k].get("updated_at", 0)
                )[: len(self._convs) - self.max_keep]:
                    del self._convs[k]
            self._persist()

    def add_message(self, session_id: str, role: str, text: str,
                    warning: str = "", completion: Optional[dict] = None) -> dict:
        """Suhbatga xabar qo'shadi; yangi session_id bo'lsa suhbat yaratadi.

        `warning`  -  ixtiyoriy ogohlantirish (masalan, structure_check fail
        holatida): transcript'da ALOHIDA maydonda saqlanadi  -  xabar matnini
        ifloslantirmaydi, shuning uchun suhbat davom ettirilganda LLM
        kontekstiga ogohlantirish qo'shilmaydi (frontend alohida ko'rsatadi).

        `completion`  -  ixtiyoriy agentik work completion record (qaysi
        pipeline, bosqichlar, tool'lar, dvigatel...): AGENTIK ISH YAKUNI
        konversatsiyaga shu maydon orqali to'ldiriladi  -  frontend suhbatda
        qaysi pipeline ishlaganini ko'radi, graf/tahlil ham o'qiy oladi.
        """
        text = str(text).strip()
        if not session_id:
            session_id = f"conv-{uuid.uuid4().hex[:12]}"
        now = time.time()
        # O'chirilgan (tombstone) suhbat id'iga yangi xabar kelsa  --  uni qayta
        # TIRILTIRMAYMIZ, yangi suhbat ochamiz. Aks holda foydalanuvchi suhbatni
        # o'chirgandan keyin ham fon'da tugayotgan task eski session_id bilan
        # yozib, uni "qayta paydo" qilardi  --  aynan shu xato tuzatilmoqda.
        if session_id in self._deleted:
            session_id = f"conv-{uuid.uuid4().hex[:12]}"
        conv = self._convs.get(session_id)
        if conv is None:
            title = text[:48] or "Yangi chat"
            conv = {
                "id": session_id,
                "title": title,
                "created_at": now,
                "updated_at": now,
                "messages": [],
                "starred": False,
            }
        if text:
            entry = {"role": role, "text": text, "ts": now}
            warning = str(warning or "").strip()
            if warning:
                entry["warning"] = warning
            if isinstance(completion, dict) and completion:
                entry["completion"] = completion
            conv["messages"].append(entry)
            # bitta suhbat cheksiz o'smasligi uchun  --  eng so'nggi max_messages
            if len(conv["messages"]) > self.max_messages:
                conv["messages"] = conv["messages"][-self.max_messages:]
        conv["updated_at"] = now
        self._save(conv)
        return conv

    def list(self, limit: int = 30) -> dict:
        """Eng so'nggi suhbatlar  -  sidebar recents uchun tayyor format."""
        # Snapshot lock ostida olinadi  --  parallel /api/chat yozuvlari bilan
        # race (dictionary changed size) bo'lmasligi uchun; saralash lock'siz.
        with self._lock:
            snapshot = list(self._convs.values())
        convs = sorted(
            snapshot, key=lambda c: c.get("updated_at", 0), reverse=True
        )
        out = []
        for c in convs[:limit]:
            msgs = c.get("messages", []) or []
            preview = ""
            for m in reversed(msgs):
                if m.get("role") == "user":
                    preview = str(m.get("text", ""))[:80]
                    break
            first_user = next((m.get("text", "") for m in msgs if m.get("role") == "user"), "")
            out.append({
                "id": c["id"],
                "title": (c.get("title") or first_user[:48] or "Yangi chat"),
                "time": c.get("updated_at", 0),
                "preview": preview,
                "messages": len(msgs),
                "starred": bool(c.get("starred")),
                "unread": False,
            })
        return {"ok": True, "conversations": out}

    def get(self, session_id: str) -> Optional[dict]:
        """Bitta suhbatni to'liq qaytaradi (frontend chatni ochishi uchun)."""
        with self._lock:
            conv = self._convs.get(session_id)
        if conv is None:
            return None
        return {
            "id": conv["id"],
            "title": conv.get("title") or "Yangi chat",
            "starred": bool(conv.get("starred")),
            "messages": conv.get("messages", []) or [],
        }

    def set_starred(self, session_id: str, starred: bool) -> bool:
        """Suhbatni yulduzchalash / yulduzchani olib tashlash."""
        with self._lock:
            conv = self._convs.get(session_id)
            if conv is None:
                return False
            conv["starred"] = bool(starred)
            self._save(conv)
            return True

    def rename(self, session_id: str, title: str) -> bool:
        """Suhbat sarlavhasini o'zgartiradi (manual rename)."""
        title = str(title).strip()[:80]
        if not title:
            return False
        with self._lock:
            conv = self._convs.get(session_id)
            if conv is None:
                return False
            conv["title"] = title
            self._save(conv)
            return True

    def delete(self, session_id: str) -> bool:
        """Suhbatni tarixdan butunlay o'chiradi (tombstone bilan  -  doimiy)."""
        with self._lock:
            conv = self._convs.pop(session_id, None)
            if conv is None:
                return False
            # AVVAL persist (u _load_tombstones orqali diskdagi boshqa jarayon
            # tombstone'larini qayta o'qiydi), SO'NG yangi tombstone qo'shamiz.
            # Teskari tartibda `_persist` ichidagi reload yangi yozuvni o'chirib
            # yuborardi  --  faqat birinchi o'chirish saqlanib qolardi.
            self._persist()
            self._deleted[session_id] = time.time()
            self._save_tombstones()
            return True

    def prune(self, days: float = 30, keep: int = 20) -> dict:
        """Eski suhbatlarni tozalaydi  -  sessiya xotira tozalash (cleanup).

        Qoidalar:
          - `days` dan eski suhbatlar o'chiriladi (updated_at asosida)
          - lekin eng so'nggi `keep` ta suhbat DOIMO qoladi (yangi bo'lsa ham)
          - yulduzchalangan (starred) suhbatlar HECH QACHON o'chirilmaydi

        Qaytaradi: {"removed": n, "kept": m, "starred_kept": k}
        """
        now = time.time()
        cutoff = now - float(days) * 86400
        with self._lock:
            convs = sorted(
                self._convs.values(),
                key=lambda c: c.get("updated_at", 0),
                reverse=True,
            )
            removed = kept = starred_kept = 0
            for idx, conv in enumerate(convs):
                cid = conv.get("id")
                if not cid:
                    continue
                if conv.get("starred"):
                    starred_kept += 1
                    continue
                updated = conv.get("updated_at", 0) or 0
                if idx < keep or updated >= cutoff:
                    kept += 1
                    continue
                self._convs.pop(cid, None)
                self._deleted[cid] = now
                removed += 1
            self._persist()
            self._save_tombstones()
            return {"removed": removed, "kept": kept, "starred_kept": starred_kept}

    def clear_all(self) -> dict:
        """BARCHA suhbatlarni o'chiradi  -  chat + tombstone + disk fayllar.

        "Oldingi natijalarni tozalash" uchun (Part N): eski/xato chizma va
        javoblar chat'dan va grafdan yo'qoladi. Graf (2nd Brain) session
        node'larini yangi build'da qayta qurmaydi.
        """
        with self._lock:
            removed = len(self._convs)
            self._convs.clear()
            self._deleted.clear()
            self._persist()
            self._save_tombstones()
            return {"removed": removed}


CHAT_HISTORY = ChatHistory()


# ---------------------------------------------------------------------- #
# App + singleton agent
# ---------------------------------------------------------------------- #

app = FastAPI(title="IGRIS Brain Bridge", version="2.0.0")

# Server start time - uptime hisoblash uchun
_SERVER_START_TIME = time.time()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # dev: allow the vite dev server / tauri webview
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_AGENT: Optional[IgrisAgent] = None

_DEFAULTS = {
    "model": os.environ.get("IGRIS_MODEL", "qwen3:8b"),
    "base_url": "http://localhost:11434",
    "use_llm": True,
    "memory": True,
    "memory_dir": "",
    "logprobs": os.environ.get("IGRIS_LOGPROBS", "0") == "1",
}


# ------------------------------------------------------------------ #
# Circuit Breaker  --  agent xatolarini kuzatadi, avtomatik tiklaydi
# ------------------------------------------------------------------ #

class CircuitBreaker:
    """Agent stabilizatsiya: ketma-ket xatolarni qayd etadi, og'ir xatolarda
    agent'ni qayta yaratadi (Ollama qulab tushsa yoki model yuklanmasa).

    Holatlar:
      CLOSED   -  normal ish (xato yo'q yoki kam)
      OPEN     -  og'ir xato: agent qayta yaratiladi (cooldown davomida)
      HALF_OPEN  -  cooldown tugadi: birinchi muvaffaqiyatli chaqiruv bilan
                  yana CLOSED ga qaytadi

    Xavfsizlik: hech qachon cheksiz loop yo'q - agent doimo yaratiladi,
    faqat qanchalik tez qayta yaratilishi farq qiladi.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self):
        self.state = self.CLOSED
        self._failure_count = 0
        self._last_failure = 0.0
        self._last_success = time.time()
        self._open_since = 0.0
        self._lock = threading.Lock()
        # Konfiguratsiya
        self._failure_threshold = 3       # shuncha ketma-ket xatodan keyin OPEN
        self._cooldown_seconds = 30.0     # OPEN holatida shuncha vaqt kutish
        self._recovery_timeout = 60.0     # HALF_OPEN da shuncha vaqt ichida muvaffaqiyat kerak

    def record_success(self):
        """Muvaffaqiyatli chaqiruv - xato hisoblagichini tozalaydi."""
        with self._lock:
            self._failure_count = 0
            self._last_success = time.time()
            if self.state != self.CLOSED:
                print(f"[circuit] {self.state} -> CLOSED (muvaffaqiyat)")
                self.state = self.CLOSED

    def record_failure(self, error: str = ""):
        """Xato  --  ketma-ket xato hisobini oshiradi."""
        with self._lock:
            self._failure_count += 1
            self._last_failure = time.time()
            if self.state == self.HALF_OPEN:
                print(f"[circuit] HALF_OPEN -> OPEN (xato: {error[:80]})")
                self.state = self.OPEN
                self._open_since = time.time()
            elif self._failure_count >= self._failure_threshold and self.state == self.CLOSED:
                print(f"[circuit] CLOSED -> OPEN (ketma-ket {self._failure_count} xato: {error[:80]})")
                self.state = self.OPEN
                self._open_since = time.time()

    def should_allow(self) -> bool:
        """Chaqiruvga ruxsat berilimi? OPEN bo'lsa cooldown tugamaguncha yo'q."""
        with self._lock:
            if self.state == self.CLOSED:
                return True
            if self.state == self.HALF_OPEN:
                return True
            # OPEN  -  cooldown tekshirish
            elapsed = time.time() - self._open_since
            if elapsed >= self._cooldown_seconds:
                print(f"[circuit] OPEN -> HALF_OPEN (cooldown {elapsed:.0f}s o'tdi)")
                self.state = self.HALF_OPEN
                return True
            return False

    def force_reset(self):
        """Qo'lda reset  --  server restart yoki UI'dan."""
        with self._lock:
            self.state = self.CLOSED
            self._failure_count = 0
            self._open_since = 0.0
            print("[circuit] qo'lda reset -> CLOSED")

    def status(self) -> dict:
        """Holat ma'lumotlari  --  /api/status uchun."""
        with self._lock:
            return {
                "state": self.state,
                "failure_count": self._failure_count,
                "last_failure": self._last_failure,
                "last_success": self._last_success,
                "open_since": self._open_since if self.state == self.OPEN else None,
            }


_CIRCUIT = CircuitBreaker()


# ------------------------------------------------------------------ #
# Health Monitor  -  fon'da agent sog'lig'ini kuzatadi, avtomatik tiklaydi
# ------------------------------------------------------------------ #

_HEALTH_MONITOR_INTERVAL = 30.0   # har 30 soniyada tekshiradi
_HEALTH_MONITOR_STARTED = False


def _health_monitor_loop():
    """Background thread: agent/LLM sog'lig'ini muntazam tekshiradi.

    Agar LLMavailable bo'lmasa yoki agent xato bersa  --  avtomatik qayta
    yaratadi (circuit breaker orqali). Backend offline bo'lmaydi:
    agent doimo yaratiladi (LLM yo'qsa ham bricks/RAG ishlaydi).

    Har aylanishda metrikalarni tarixga yozadi - monitoring dashboard
    real vaqt metrikalarini olishi uchun.
    """
    global _AGENT
    while True:
        try:
            time.sleep(_HEALTH_MONITOR_INTERVAL)
            # Metrikalarni yig'amiz (har aylanishda)
            try:
                metrics = _collect_health_metrics()
                _record_metrics(metrics)
            except Exception:
                pass
            agent = _AGENT
            if agent is None:
                continue
            # LLM sog'lig'ini tekshiramiz  -  model mavjudligini tez tekshirish
            try:
                if hasattr(agent.llm, "last_error") and agent.llm.last_error:
                    # LLM xato  -  avtomatik qayta yaratish
                    print(f"[health] LLM xato: {agent.llm.last_error[:80]}  -  agent qayta yaratilmoqda")
                    try:
                        _AGENT = create_agent(**_DEFAULTS)
                        _CIRCUIT.record_success()
                        print("[health] agent muvaffaqiyatli qayta yaratildi")
                    except Exception as exc:
                        _CIRCUIT.record_failure(str(exc))
                        print(f"[health] agent qayta yaratilmadi: {exc[:80]}")
            except Exception:
                pass
            # Memory sog'lig'ini tekshiramiz  -  RAG yuklanmagan bo'lsa qayta urinamiz
            try:
                if hasattr(agent, 'memory') and agent.memory and not agent.memory.enabled:
                    if hasattr(agent.memory, '_error') and agent.memory._error:
                        print(f"[health] memory disabled: {agent.memory._error[:60]}  -  qayta urinish")
                        try:
                            agent.memory.__init__(
                                enabled=True,
                                session_id=getattr(agent.memory, 'session_id', 'bridge'),
                                base_dir=getattr(agent.memory, 'base_dir', ''),
                            )
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception as exc:
            # Health monitor hech qachon o'lmaydi
            try:
                print(f"[health] monitor xatosi (e'tiborsiz): {exc}")
            except Exception:
                pass


def _start_health_monitor():
    """Health monitor'ni background thread'da ishga tushiradi (bir marta)."""
    global _HEALTH_MONITOR_STARTED
    if _HEALTH_MONITOR_STARTED:
        return
    _HEALTH_MONITOR_STARTED = True
    t = threading.Thread(target=_health_monitor_loop, daemon=True, name="health-monitor")
    t.start()
    print("[igris] health monitor ishga tushdi")


def get_agent() -> IgrisAgent:
    """Lazy singleton init  --  circuit breaker bilan himoyalangan.

    Agent yaratishda xato bo'lsa  --  circuit breaker qayd etadi;
    ketma-ket 3 ta xatodan keyin agent qayta yaratiladi (Ollama qulab
    tushganda yoki model yuklanmagan bo'lsa avtomatik tiklash).
    """
    global _AGENT
    if _AGENT is not None and _CIRCUIT.should_allow():
        return _AGENT
    # Circuit OPEN yoki agent yo'q  -  yaratamiz
    try:
        _AGENT = create_agent(**_DEFAULTS)
        _CIRCUIT.record_success()
    except Exception as exc:
        _CIRCUIT.record_failure(str(exc))
        if _AGENT is not None:
            # Oldingi agent mavjud  -  xatoni qayd etdik, lekin eski agentni
            # saqlab qolamiz (qisman ishlaydi: LLM yo'q, lekin bricks/RAG ishlaydi)
            print(f"[circuit] agent qayta yaratilmadi ({exc[:80]}), eski agent ishlatiladi")
            return _AGENT
        # Agent yo'q va yaratib bo'lmadi  -  xato bilan qaytaramiz
        raise
    return _AGENT


def rebuild_agent():
    """Agent'ni majburiy qayta yaratadi  --  UI'dan yoki watchdog'dan."""
    global _AGENT
    _CIRCUIT.force_reset()
    _AGENT = create_agent(**_DEFAULTS)
    print("[igris] agent qayta yaratildi (rebuild)")
    return _AGENT


# Sifat bo'yicha afzal modellar  -  so'ralgan model yo'q bo'lsa mavjudlardan
# eng yaxshisi avtomatik tanlanadi (foydalanuvchi qo'lda o'rnatishni kutmaydi).
from llm.ollama_client import pick_best_model  # noqa: E402


def _auto_select_model(agent: IgrisAgent, requested: str) -> str:
    """So'ralgan model o'rnatilmagan bo'lsa  --  Ollama'dagi eng yaxshi modelni tanlaydi.

    Qaytadi: amalda ishlatiladigan model nomi. Xato/sabab `llm.last_error`ga
    yoziladi  --  /api/status orqali UI'da ko'rinadi.
    """
    try:
        models = agent.llm.list_models()
    except Exception:
        models = []
    if requested in models:
        return requested
    best = pick_best_model(models)
    if best is None:
        agent.llm.last_error = (
            "Ollama ishlamayapti yoki hech qanday model o'rnatilmagan. "
            "`ollama pull qwen3:8b` bajarib, Settings → Services → restart qiling."
        )
        return requested
    agent.llm.model = best
    agent._llm_checked = False
    agent.llm.last_error = (
        f"'{requested}' topilmadi  -  avtomatik ravishda {best} ishlatilmoqda. "
        f"Yaxshiroq sifat uchun `ollama pull {requested}` bajarib, "
        f"Settings → Model'dan tanlang."
    )
    print(f"[igris] model auto-select: '{requested}' -> '{best}'")
    return best


def create_agent(model: str, base_url: str, use_llm: bool, memory: bool, memory_dir: str,
                  logprobs: bool = False) -> IgrisAgent:
    global _AGENT, _DEFAULTS
    _AGENT = IgrisAgent(
        use_llm=use_llm,
        llm_model=model,
        llm_base_url=base_url,
        memory_enabled=memory,
        memory_session="bridge",
        memory_dir=memory_dir,
        # Ixtiyoriy OpenAI-mos logprob re-so'ruvi (self-eval signal; 2x narx)
        llm_logprobs=logprobs,
    )
    if use_llm:
        # So'ralgan model mavjudligini tekshiramiz; yo'q bo'lsa  -  avto tanlov.
        model = _auto_select_model(_AGENT, model)
    _DEFAULTS.update(model=model, base_url=base_url, use_llm=use_llm,
                     memory=memory, memory_dir=memory_dir, logprobs=logprobs)
    return _AGENT


# ---------------------------------------------------------------------- #
# API
# ---------------------------------------------------------------------- #

# Part N: /api/status TTL kesh  -  takroriy poll'lar (Settings/StatusBar/agentInfo)
# agent.status() ni (Ollama + memory) har safar qayta hisoblamaydi; Ollama band
# bo'lganda ham status tez qaytadi (noto'g'ri "offline" ko'rinmaydi).
_STATUS_TTL_SECONDS = 5.0  # 5s TTL  -  UI poll'lari uchun yetarli (2s ortiqcha yuk)
_status_cache: dict = {"ts": 0.0, "data": None}
_status_lock = threading.Lock()


def _cached_agent_status() -> dict:
    now = time.time()
    with _status_lock:
        if _status_cache["data"] is not None and now - _status_cache["ts"] < _STATUS_TTL_SECONDS:
            return _status_cache["data"]
    agent = get_agent()
    st = agent.status()
    with _status_lock:
        _status_cache["ts"] = time.time()
        _status_cache["data"] = st
    return st


@app.get("/api/status")
def api_status():
    agent = get_agent()          # singleton  -  arzon
    st = _cached_agent_status()  # 2s TTL  -  og'ir status qayta hisoblanmaydi
    return {
        "ok": True,
        "agent": {
            "bricks": st["bricks"]["total"],
            "rules": st["knowledge"]["rules"],
            "chains": list(st["chains"].keys()),
        },
        "llm": {
            "enabled": st["llm"]["enabled"],
            "available": st["llm"]["available"],
            "model": st["llm"]["model"],
            # Nega ishlamayapti  -  UI'da ko'rsatiladi ("model topilmadi" kabi).
            "error": getattr(agent.llm, "last_error", None),
            # Universal tez rejim (TURBO)  -  Settings'da ko'rsatiladi.
            "turbo": bool(getattr(agent.llm, "turbo", False)),
            "fast_model": getattr(agent.llm, "fast_model", None),
            # Graceful degradation holati
            "failure_count": getattr(agent, '_llm_failure_count', 0),
            "degraded": getattr(agent, '_llm_failure_count', 0) > 0,
        },
        "memory": {
            "enabled": st["memory"].get("enabled", False),
            "error": st["memory"].get("error"),
        },
        "intelligence": {
            "enabled": bool((st.get("intelligence") or {}).get("enabled")),
            "modules": sorted(k for k in (st.get("intelligence") or {})
                              if k != "enabled"),
        },
        # Circuit breaker holati  -  UI agent stabilizatsiya ko'rsatadi
        "circuit": _CIRCUIT.status(),
        # Degradation metrics  -  monitoring dashboard uchun
        "degradation": agent.degradation_status() if hasattr(agent, 'degradation_status') else {},
        "timestamp": time.time(),
    }


@app.post("/api/agent/rebuild")
def api_agent_rebuild():
    """Agent'ni majburiy qayta yaratadi  --  UI Settings'dan yoki watchdog'dan.

    Circuit breaker reset + agent qayta yaratiladi (Ollama qulab tushganda
    yoki model yuklanmagan bo'lsa avtomatik tiklash). Backend offline bo'lmasligi
    uchun eng muhim qadam  --  agent'ni tiriltirish.
    """
    try:
        agent = rebuild_agent()
        return {"ok": True, "model": agent.llm.model, "circuit": _CIRCUIT.status()}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "circuit": _CIRCUIT.status()}


@app.post("/api/circuit/reset")
def api_circuit_reset():
    """Circuit breaker'ni qo'lda reset qiladi  --  agent qayta yaratilmaydi,
    faqat xato hisoblagichlari tozalanadi.
    """
    _CIRCUIT.force_reset()
    return {"ok": True, "circuit": _CIRCUIT.status()}


@app.get("/api/intelligence/status")
def api_intelligence_status():
    """INTELLEKT qatlami holati (BuildIntalaganceInstructionRequest.md).

    Har bir modulning REAL statistikasini qaytaradi: zarar filtri (bloklar
    soni), foydalanuvchi profili, ohang, lug'at, mantiq (struktura tekshiruvlari),
    ishonch kalibratsiyasi, fazoviy, kreativ, naturalist, musiqa. UI'da
    qaysi intellektlar ishlayotganini ko'rish uchun.
    """
    agent = get_agent()
    try:
        st = agent.intelligence.status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    st["modules"] = sorted(k for k in st if k != "enabled")
    st["timestamp"] = time.time()
    return {"ok": True, **st}


@app.get("/api/health")
def api_health():
    """Yengil sog'liq tekshiruvi  --  agent/LLM'ga TEGMAYDI.

    Watchdog shu endpoint'ni kuzatadi: /api/status agent holatini (model
    ro'yxati, Ollama tekshiruvi bilan) qaytaradi va model yuklanayotganda
    sekinlashishi mumkin  --  band lekin tirik backend'ni "o'lik" deb adashib
    o'ldirmaslik uchun alohida, tezkor sog'liq endpoint'i.
    """
    return {"ok": True, "timestamp": time.time()}


# ------------------------------------------------------------------ #
# Health Metrics — monitoring dashboard uchun to'liq ma'lumotlar
# ------------------------------------------------------------------ #

# Metrics tarixi: oxirgi N ta yozuv (ring buffer). Har 30 soniyada yangilanadi.
_METRICS_MAX_ENTRIES = 120  # 30s * 120 = 60 daqiqa tarix
_metrics_history: list[dict] = []
_metrics_lock = threading.Lock()


def _collect_health_metrics() -> dict:
    """Joriy holat metrikalarini yig'adi. Har 30 soniyada health monitor
    thread'i tomonidan chaqiriladi yoki /api/health/metrics so'rovda.
    """
    now = time.time()
    agent = _AGENT
    metrics: dict = {
        "timestamp": now,
        "uptime": now - (_SERVER_START_TIME if '_SERVER_START_TIME' in dir() else now),
    }

    # 1. Agent holati
    if agent is None:
        metrics["agent"] = {"status": "not_initialized"}
        return metrics

    try:
        st = agent.status()
        metrics["agent"] = {
            "status": "ok",
            "bricks": st.get("bricks", {}).get("total", 0),
            "rules": st.get("knowledge", {}).get("rules", 0),
            "chains": len(st.get("chains", {})),
        }
    except Exception as exc:
        metrics["agent"] = {"status": "error", "error": str(exc)[:100]}

    # 2. LLM holati (graceful degradation bilan)
    try:
        llm_data = {
            "enabled": agent.use_llm,
            "available": agent.llm_available(),
            "model": agent.llm.model,
            "failure_count": getattr(agent, '_llm_failure_count', 0),
            "degraded": getattr(agent, '_llm_failure_count', 0) > 0,
            "last_error": getattr(agent.llm, 'last_error', None),
            "turbo": bool(getattr(agent.llm, 'turbo', False)),
        }
        # LLM availability check timeout
        t0 = time.perf_counter()
        try:
            is_up = agent.llm.is_available()
            llm_data["ping_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            llm_data["reachable"] = is_up
        except Exception:
            llm_data["ping_ms"] = -1
            llm_data["reachable"] = False
        # Degradation metrics
        try:
            llm_data["degradation"] = agent.degradation_status()
        except Exception:
            llm_data["degradation"] = {}
        metrics["llm"] = llm_data
    except Exception as exc:
        metrics["llm"] = {"error": str(exc)[:100]}

    # 3. Memory / RAG holati
    try:
        mem = agent.memory
        metrics["memory"] = {
            "enabled": mem.enabled,
            "error": getattr(mem, '_error', None),
            "corpus_loaded": getattr(mem, '_load_done', threading.Event()).is_set(),
        }
    except Exception as exc:
        metrics["memory"] = {"error": str(exc)[:100]}

    # 4. Circuit breaker holati
    try:
        metrics["circuit"] = _CIRCUIT.status()
    except Exception as exc:
        metrics["circuit"] = {"error": str(exc)[:100]}

    # 5. Chat holati
    try:
        with CHAT_PROGRESS_LOCK:
            active_chats = len(CHAT_HISTORY._convs)
            active_runs = len(CHAT_PROGRESS)
        metrics["chat"] = {
            "conversations": active_chats,
            "active_runs": active_runs,
        }
    except Exception as exc:
        metrics["chat"] = {"error": str(exc)[:100]}

    # 6. System resurslari
    try:
        import psutil
        proc = psutil.Process()
        mem_info = proc.memory_info()
        metrics["system"] = {
            "pid": proc.pid,
            "memory_rss_mb": round(mem_info.rss / 1024 / 1024, 1),
            "memory_vms_mb": round(mem_info.vms / 1024 / 1024, 1),
            "cpu_percent": proc.cpu_percent(interval=0.1),
            "threads": proc.num_threads(),
        }
    except ImportError:
        # psutil yo'q - lightweight alternativa
        try:
            import os
            metrics["system"] = {
                "pid": os.getpid(),
                "threads": 0,
            }
        except Exception:
            metrics["system"] = {}
    except Exception as exc:
        metrics["system"] = {"error": str(exc)[:100]}

    return metrics


def _record_metrics(metrics: dict):
    """Metrikalarni tarixga yozadi (ring buffer)."""
    with _metrics_lock:
        _metrics_history.append(metrics)
        if len(_metrics_history) > _METRICS_MAX_ENTRIES:
            _metrics_history.pop(0)


@app.get("/api/health/metrics")
def api_health_metrics():
    """To'liq sog'liq metrikalari - monitoring dashboard uchun.

    Agent, LLM, memory, circuit breaker, chat holati, system resurslari.
    Har so'rovda joriy holat + oxirgi 60 daqiqa tarixi.
    """
    metrics = _collect_health_metrics()
    _record_metrics(metrics)

    # Tarixdan oxirgi N ta nuqtani qaytaramiz (dashboard uchun)
    with _metrics_lock:
        history_snapshot = list(_metrics_history[-60:])  # oxirgi 30 daqiqa

    return {
        "ok": True,
        "current": metrics,
        "history_count": len(_metrics_history),
        "history": history_snapshot,
    }


@app.get("/api/health/history")
def api_health_history(limit: int = 60):
    """Sog'liq tarixi - time-series uchun.

    `limit` - nechta oxirgi metrikani qaytarish (max 120).
    Dashboard uchun: graf chizish, tendensiyalarni ko'rish.
    """
    limit = max(1, min(limit, _METRICS_MAX_ENTRIES))
    with _metrics_lock:
        history = list(_metrics_history[-limit:])

    # Aggregatsiya - o'rtacha, min, max
    agg = {}
    if history:
        # LLM ping vaqtlari
        pings = [h.get("llm", {}).get("ping_ms", 0) for h in history
                 if h.get("llm", {}).get("ping_ms", 0) > 0]
        if pings:
            agg["llm_ping"] = {
                "avg_ms": round(sum(pings) / len(pings), 1),
                "min_ms": round(min(pings), 1),
                "max_ms": round(max(pings), 1),
            }
        # Xato soni
        errors = sum(1 for h in history
                     if h.get("llm", {}).get("degraded")
                     or h.get("agent", {}).get("status") == "error")
        agg["error_count"] = errors
        agg["uptime_percent"] = round(
            (1 - errors / max(len(history), 1)) * 100, 1
        )
        # Degradation metrics
        degradation_events = [h for h in history
                             if h.get("llm", {}).get("degradation")]
        if degradation_events:
            latest_deg = degradation_events[-1].get("llm", {}).get("degradation", {})
            agg["degradation"] = {
                "total_failures": latest_deg.get("total_degradation_count", 0),
                "total_time_seconds": latest_deg.get("total_degradation_time_seconds", 0),
                "current_failures": latest_deg.get("failure_count", 0),
                "is_degraded": latest_deg.get("is_degraded", False),
            }
        # Xotira hajmi
        rss_values = [h.get("system", {}).get("memory_rss_mb", 0)
                      for h in history
                      if h.get("system", {}).get("memory_rss_mb", 0) > 0]
        if rss_values:
            agg["memory"] = {
                "avg_mb": round(sum(rss_values) / len(rss_values), 1),
                "max_mb": round(max(rss_values), 1),
            }

    return {
        "ok": True,
        "count": len(history),
        "history": history,
        "aggregates": agg,
        "timestamp": time.time(),
    }


@app.get("/api/llm/models")
def api_models():
    agent = get_agent()
    models = agent.llm.list_models()
    return {"ok": True, "models": models}


@app.post("/api/llm/model")
def api_set_model(req: ModelRequest):
    """Ishlayotgan modelni jonli almashtiradi (keyingi LLM chaqiruvlarida qo'llanadi)."""
    model = (req.model or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="model required")
    agent = get_agent()
    # Tanlangan model haqiqatan o'rnatilganmi tekshiramiz  -  yo'q bo'lsa xato
    # sababi UI'da ko'rinadi ("qila olmayman" kabi chalg'ituvchi xatolar yo'q).
    agent.llm.model = model
    agent._llm_checked = False  # mavjudlik qayta tekshiriladi
    _DEFAULTS["model"] = model
    return {"ok": True, "model": model, "current": agent.llm.model}


@app.get("/api/settings/speed")
def api_speed_get():
    """Universal tez rejim holati (TURBO)  --  har qanday modelga birdek."""
    agent = get_agent()
    return {"ok": True, **agent.speed_status()}


@app.post("/api/settings/speed")
def api_speed_set(req: SpeedRequest):
    """Universal tez rejimni yoqadi/o'chiradi (BIR kalit  --  barcha modellarga).

    turbo=true: kichik kontekst/token, thinking o'chiq, oddiy savollar tez
    modelga yo'naltiriladi. Sozlama xotirada saqlanadi (server restart'da
    avtomatik qayta qo'llanadi).
    """
    agent = get_agent()
    agent.set_speed(req.turbo)
    _SPEED["turbo"] = bool(req.turbo)
    _persist_speed()
    return {"ok": True, **agent.speed_status()}


@app.get("/api/llm/models/detail")
def api_models_detail():
    """Ollama'dagi modellar: nom + hajm (parametr) + quantizatsiya + GB.

    Settings → Model ro'yxatida foydalanuvchi to'g'ri model tanlashi uchun
    (8b/7b/4b/1.5b farqini ko'rib, sifat bo'yicha qaror qiladi).
    """
    agent = get_agent()
    return {"ok": True, "models": agent.llm.list_models_detailed()}


@app.post("/api/resolve")
def api_resolve(req: ResolveRequest):
    agent = get_agent()
    t0 = time.time()
    try:
        result = agent.resolve(req.query, allow_llm=req.allow_llm, use_memory=req.use_memory)
        result["api_ms"] = round((time.time() - t0) * 1000, 2)
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    agent = get_agent()
    t0 = time.time()
    # session_id chat boshlanishidan OLDI aniq bo'ladi  -  jonli progress shu
    # kalit bilan frontend polling'iga ko'rinadi (chat tugaguncha).
    sid = req.session_id or f"conv-{uuid.uuid4().hex[:12]}"
    try:
        result = agent.chat(
            req.message,
            history=req.history,
            use_memory=req.use_memory,
            progress_cb=_chat_progress_cb(sid),
        )
        result["api_ms"] = round((time.time() - t0) * 1000, 2)
        # REAL chat tarixi: session_id berilsa o'sha suhbatga, aks holda yangi suhbat
        CHAT_HISTORY.add_message(sid, "user", req.message)
        warning = _structure_fail_warning(result)
        if result.get("content"):
            CHAT_HISTORY.add_message(
                sid, "assistant", str(result["content"])[:2000], warning=warning,
                # AGENTIK completion: ish yakuni konversatsiyaga to'ldiriladi
                completion=result.get("completion") or None)
        # Transcript ogohlantirishi  -  frontend javob bilan birga oladi
        # (structure_check fail bo'lsa banner ko'rsatadi; bo'sh bo'lsa kalit yo'q).
        if warning:
            result["warning"] = warning
        result["session_id"] = sid
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        # chat tugadi  -  progress buferi tozalanadi (keyingi chat yangidan boshlaydi)
        _chat_progress_clear(sid)


@app.post("/api/chat/stream")
def api_chat_stream(req: ChatRequest):
    """TOKEN-USTALI chat  --  QATLAMLI AGENTIC LOOP (layered-streaming skill).

    /api/chat sinxron qaytaradi; bu endpoint esa LAYERED AGENTIC LOOP
    ishlatadi  --  user prompt qayta tahlil qilinadi (reprompt), maqsadli
    qatlamlar tuziladi, har bir qatlam layer-by-layer bajariladi,
    har bir tool/MCP/skill chaqiruvida token streaming amalga oshiriladi,
    oxirida barcha natijalar yig'iladi va final result taqdim etiladi.

    SSE voqealari:
      data: {"type": "stage", "stage": "analyze", "detail": "..."}
      data: {"type": "layer_start", "layer": "planning"}
      data: {"type": "tool_start", "tool": "write_file", ...}
      data: {"type": "token", "content": "<delta>", "source": "tool_name"}
      data: {"type": "tool_done", "tool": "write_file", ...}
      data: {"type": "layer_done", "layer": "execution", ...}
      data: {"type": "final_result", "content": "...", ...}

    Fallback: layered agent xato bersa  --  oddiy chat_stream() ga qaytadi.
    """
    from fastapi.responses import StreamingResponse
    agent = get_agent()
    t0 = time.time()
    sid = req.session_id or f"conv-{uuid.uuid4().hex[:12]}"
    progress_cb = _chat_progress_cb(sid)

    def sse(ev: dict) -> str:
        return f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    def generate():
        try:
            CHAT_HISTORY.add_message(sid, "user", req.message)
            yield sse({"type": "meta", "session_id": sid})

            # ── QATLAMLI AGENTIC LOOP ──
            layered = create_layered_agent(agent)
            layered_ok = True
            try:
                for ev in layered.run_layered(
                    req.message,
                    history=req.history,
                    use_memory=req.use_memory,
                    progress_cb=progress_cb,
                    session_id=sid,
                ):
                    # stage voqealari progress buferiga ham tushadi
                    if ev.get("type") == "stage":
                        progress_cb(ev.get("stage", ""), ev.get("detail", ""))
                    # final_result ni done ga aylantirib backend compatibility saqlaymiz
                    if ev.get("type") == "final_result":
                        done_ev = {
                            "type": "done",
                            "content": ev.get("content", ""),
                            "engine": "layered",
                            "tool_calls": ev.get("tool_calls", []),
                            "image": None,
                            "memory": {"recall_hits": 0, "context_chars": 0},
                            "api_ms": round((time.time() - t0) * 1000, 2),
                            "session_id": sid,
                            "layers_executed": ev.get("layers_executed", []),
                            "reprompt": ev.get("reprompt", {}),
                            "duration_ms": ev.get("duration_ms", 0),
                        }
                        if ev.get("content"):
                            CHAT_HISTORY.add_message(
                                sid, "assistant", str(ev["content"])[:2000],
                                completion={"engine": "layered",
                                            "layers": ev.get("layers_executed", [])})
                        yield sse(done_ev)
                    else:
                        yield sse(ev)
            except Exception as layered_exc:
                print(f"[server][layered] fallback to chat_stream: {layered_exc}")
                layered_ok = False

            # ── FALLBACK: layered agent ishlamasa  -  oddiy chat_stream ──
            if not layered_ok:
                for ev in agent.chat_stream(
                    req.message,
                    history=req.history,
                    use_memory=req.use_memory,
                    progress_cb=progress_cb,
                ):
                    if ev.get("type") == "stage":
                        progress_cb(ev.get("stage", ""), ev.get("detail", ""))
                    if ev.get("type") == "done":
                        ev.setdefault("api_ms", round((time.time() - t0) * 1000, 2))
                        ev["session_id"] = sid
                        warning = _structure_fail_warning(ev)
                        if warning:
                            ev["warning"] = warning
                        if ev.get("content"):
                            CHAT_HISTORY.add_message(
                                sid, "assistant", str(ev["content"])[:2000],
                                warning=warning,
                                completion=ev.get("completion") or None)
                    yield sse(ev)

            yield sse({"type": "end", "session_id": sid})
        except Exception as exc:
            yield sse({"type": "error", "error": str(exc), "session_id": sid})
        finally:
            _chat_progress_clear(sid)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


class ClarifyRequest(BaseModel):
    session_id: str
    answer: str


@app.post("/api/chat/clarify")
def api_chat_clarify(req: ClarifyRequest):
    """Clarification javobi  --  layered agent clarification layer kutayotgan javob.

    Frontend clarify eventini olgandan keyin user javobini shu endpointga
    POST qiladi. Agent javobni qabul qilib, layered loopni davom ettiradi.
    """
    ok = CLARIFICATION_MANAGER.respond(req.session_id, req.answer)
    if ok:
        return {"ok": True, "message": "Clarification answer submitted"}
    # Agar sessiya topilmasa  -  ehtimol agent allaqachon davom etgan
    status = CLARIFICATION_MANAGER.get_status(req.session_id)
    if status is None:
        return {"ok": False, "message": "Session not found or already completed"}
    return {"ok": False, "message": f"Cannot submit answer in status: {status.get('status')}"}


@app.get("/api/chat/clarify/status")
def api_chat_clarify_status(session_id: str):
    """Clarification sessiyasi holati  --  frontend polling uchun."""
    status = CLARIFICATION_MANAGER.get_status(session_id)
    if status is None:
        return {"ok": True, "pending": False}
    return {
        "ok": True,
        "pending": CLARIFICATION_MANAGER.is_pending(session_id),
        "question": status.get("question"),
        "answer": status.get("answer"),
        "status": status.get("status"),
    }


@app.get("/api/chat/progress")
def api_chat_progress(session_id: str):
    """Chat run davomidagi JONLI pipeline bosqichi (frontend polling).

    /api/chat sinxron ishlayotganda frontend shu endpointni har ~1.2s so'raydi
     --  PipelineStepper real bosqichni ko'rsatadi (bezaksiz, haqiqiy progress).
    Chat tugagach bufer tozalanadi: active=false qaytadi.
    """
    with CHAT_PROGRESS_LOCK:
        p = CHAT_PROGRESS.get(session_id or "")
    if not p:
        return {"ok": True, "active": False}
    return {
        "ok": True,
        "active": True,
        "stage": p.get("stage"),
        "stage_detail": p.get("stage_detail"),
        "ts": p.get("ts"),
    }


@app.get("/api/chat/history")
def api_chat_history(limit: int = 30):
    """Real chat tarixi  --  sidebar recents va 2nd Brain grafi uchun."""
    return CHAT_HISTORY.list(max(1, min(limit, 100)))


@app.post("/api/chat/clear")
def api_chat_clear():
    """BARCHA suhbatlarni + CAG keshni tozalaydi ("oldingi natijalarni tozala").

    Part N: eski/xato natijalar (chizmalar, javoblar) chat'dan, CAG keshdan
    va 2nd Brain grafidan yo'qoladi  --  yangi so'rovlar toza holatda ishlaydi.
    Part O: workspace'dagi eski chizma/rasm fayllari ham tozalanadi.
    """
    removed = CHAT_HISTORY.clear_all().get("removed", 0)
    try:
        from cag import DEFAULT_CAG
        DEFAULT_CAG.clear()
    except Exception:
        pass
    drawings_removed = _clear_workspace_drawings()
    return {"ok": True, "removed": removed, "cag_cleared": True,
            "drawings_removed": drawings_removed}


_DRAWING_EXTS = (".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp",
                 ".ico", ".uibuild.json")


def _clear_workspace_drawings() -> int:
    """Agent workspace'dagi eski chizma/rasm fayllarini o'chiradi.

    Kod/matn fayllariga tegmaydi  --  faqat rasm kengaytmalari. Chat va kesh
    bilan birga "oldingi rasm natijalari" to'liq tozalanadi.
    """
    root = _workspace_root("")
    removed = 0
    try:
        for dirpath, _dirs, files in os.walk(root):
            for fname in files:
                if fname.lower().endswith(_DRAWING_EXTS):
                    try:
                        os.remove(os.path.join(dirpath, fname))
                        removed += 1
                    except OSError:
                        pass
    except OSError:
        pass
    return removed


@app.get("/api/chat/{chat_id}")
def api_chat_get(chat_id: str):
    """Bitta suhbatni to'liq qaytaradi  --  sidebar'dan chat ochilganda."""
    conv = CHAT_HISTORY.get(chat_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"ok": True, "conversation": conv}


@app.post("/api/chat/star")
def api_chat_star(req: ChatStarRequest):
    """Suhbatni yulduzchalaydi / yulduzchani oladi."""
    if not CHAT_HISTORY.set_starred(req.id, req.starred):
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"ok": True, "id": req.id, "starred": req.starred}


@app.post("/api/chat/rename")
def api_chat_rename(req: ChatRenameRequest):
    """Suhbat sarlavhasini o'zgartiradi."""
    if not CHAT_HISTORY.rename(req.id, req.title):
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"ok": True, "id": req.id, "title": req.title.strip()[:80]}


@app.post("/api/chat/delete")
def api_chat_delete(req: ChatIdRequest):
    """Suhbatni tarixdan o'chiradi (idempotent  --  topilmasa ham ok)."""
    CHAT_HISTORY.delete(req.id)
    return {"ok": True, "id": req.id, "deleted": True}


@app.post("/api/memory/search")
def api_memory_search(req: MemorySearchRequest):
    agent = get_agent()
    if not agent.memory.enabled:
        return {"ok": True, "enabled": False, "results": []}
    return {"ok": True, "enabled": True, **agent.memory.search(req.query, top_k=req.top_k)}


@app.get("/api/memory/status")
def api_memory_status():
    agent = get_agent()
    return {"ok": True, **agent.memory.status()}


@app.get("/api/memory/clarification-analytics")
def api_clarification_analytics():
    """Clarification tahlili  --  chastota, naqshlar, samaradorlik.

    RefactorView uchun clarification analytics ma'lumotlari:
      - total_clarifications: jami clarification soni
      - total_questions: jami savollar soni
      - avg_questions_per_session: o'rtacha savollar soni (session)
      - common_questions: eng ko'p berilgan savollar
      - common_answers: eng ko'p berilgan javoblar
    """
    agent = get_agent()
    if not agent.memory.enabled:
        return {
            "ok": True,
            "enabled": False,
            "total_clarifications": 0,
            "total_questions": 0,
            "avg_questions_per_session": 0,
            "common_questions": [],
            "common_answers": [],
        }
    try:
        analytics = agent.memory.get_clarification_analytics()
        return {"ok": True, "enabled": True, **analytics}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.get("/api/brain/graph")
def api_brain_graph(shares: Optional[str] = None, max_nodes: Optional[str] = None):
    """2nd Brain knowledge graph  --  Igris_Memory'dan real ma'lumotlar.

    `shares`  --  ixtiyoriy kvota ulushlari (vergul bilan ajratilgan 4 son,
    masalan "0.30,0.30,0.20,0.20"): vault, chat, persistent, runtime.
    `max_nodes`  --  ixtiyoriy graf node chegarasi (masalan "300").
    2nd Brain sozlamalar panelidan yuboriladi; bo'lmasa DISKDA saqlangan
    (graph_shares.json) yoki default qiymatlar ishlatiladi.
    """
    from brain_graph import build_graph, normalize_shares
    parsed = None
    if shares:
        try:
            parsed = [float(x.strip()) for x in shares.split(",") if x.strip()]
        except ValueError:
            parsed = None  # noto'g'ri format  -  default ulushlar
    # Query param bo'lmasa  -  diskdagi sozlangan ulushlar (server persist).
    if parsed is None and _GRAPH_SHARES.get("shares"):
        parsed = normalize_shares(_GRAPH_SHARES["shares"])
    # max_nodes: query param -> diskdagi sozlangan -> default.
    parsed_max = None
    if max_nodes:
        parsed_max = _clamp_max_nodes(max_nodes)
    if parsed_max is None and _GRAPH_SHARES.get("max_nodes"):
        parsed_max = _clamp_max_nodes(_GRAPH_SHARES["max_nodes"])
    return build_graph(
        max_nodes=parsed_max if parsed_max else _GRAPH_MAX_NODES_DEFAULT,
        shares=parsed if parsed else None,
    )


class GraphSharesRequest(BaseModel):
    """2nd Brain graf sozlamalari  --  kvota ulushlari + node chegarasi.

    Ikkala maydon ham ixtiyoriy: berilmagani joriy qiymatini saqlaydi
    (qisman yangilash  --  masalan faqat max_nodes o'zgartirilsa, ulushlar
    buzilmaydi).
    """
    shares: Optional[list] = None
    max_nodes: Optional[int] = None


def _graph_shares_response() -> dict:
    """GET/POST uchun umumiy javob  --  ulushlar + max_nodes + o'zgarish tarixi."""
    from brain_graph import DEFAULT_SHARES, normalize_shares
    saved = _GRAPH_SHARES.get("shares")
    return {
        "ok": True,
        "shares": normalize_shares(saved) if saved else list(DEFAULT_SHARES),
        "max_nodes": _GRAPH_SHARES.get("max_nodes") or _GRAPH_MAX_NODES_DEFAULT,
        "updated_at": _GRAPH_SHARES.get("updated_at"),
        "history": _GRAPH_SHARES.get("history") or [],
    }


@app.get("/api/brain/graph/shares")
def api_brain_shares_get():
    """Saqlangan graf sozlamalari + o'zgarish tarixi (default bo'lsa default'lar)."""
    return _graph_shares_response()


@app.post("/api/brain/graph/shares")
def api_brain_shares_set(req: GraphSharesRequest):
    """Graf sozlamalarini diskda saqlaydi  --  keyingi yuklanishda qo'llaniladi.

    Har bir o'zgarish tarixga yoziladi (ts + shares + max_nodes)  --  qachon,
    qaysi qiymatga o'zgargani graph_shares.json'da kuzatiladi. Berilmagan
    maydon joriy qiymatini saqlaydi (qisman yangilash mumkin).
    """
    from brain_graph import normalize_shares
    if req.shares is None and req.max_nodes is None:
        return _graph_shares_response()  # hech narsa o'zgartirilmagan
    shares = normalize_shares(req.shares) if req.shares is not None \
        else _GRAPH_SHARES.get("shares")
    max_nodes = _clamp_max_nodes(req.max_nodes) if req.max_nodes is not None \
        else _GRAPH_SHARES.get("max_nodes")
    _persist_graph_shares(shares, max_nodes=max_nodes)
    return _graph_shares_response()


@app.get("/api/brain/graph/version")
def api_brain_graph_version():
    """Graf manbalari versiyasi  --  FAQAT SEZILARLI o'zgarishlar uchun engil fingerprint.

    Frontend har ~8 soniyada SHU endpoint'ni so'raydi (grafikni emas)  --  grafik
    faqat mazmunli o'zgarishda qayta yuklanadi:
      - yangi vault .md / L2 xotira yozuvi / yangi xotira fayli (yangi modul)
      - yangi suhbat ochildi / o'chirildi / nomi o'zgardi
    L1 runtime'ga doimiy yozishlar va mavjud suhbatga xabarlar versiyani
    o'zgartirmaydi  --  2nd Brain chat davomida 'sakrab' qayta yuklanmaydi,
    turg'un turadi (noqulaylik va 'fake' holatlar yo'q).

    `reason`  --  so'nggi SEZILARLI o'zgarish sababi ("yangi xotira moduli:
    ...", "yangi suhbat: ..."); o'zgarish bo'lmasa null. Frontend graf nega
    yangilanganini shu maydondan ko'rsatadi (real sabab, bezaksiz).

    `changed_at`  --  so'nggi SEZILARLI o'zgarish ANIQLANGAN vaqt (epoch
    sekund; real fayl o'zgarishi vaqtiga poll oralig'i (~8s) gacha yaqin).
    O'zgarishsiz poll'lar eski vaqtni saqlaydi, hech o'zgarish bo'lmagan
    bo'lsa null (graf qachondan beri turg'un  --  frontend ko'rsatadi).
    """
    from brain_graph import graph_version_fingerprint
    digest, sources, reason, changed_at = graph_version_fingerprint()
    return {"ok": True, "version": digest, "sources": sources,
            "reason": reason, "changed_at": changed_at}


@app.post("/api/session/start")
def api_session_start(req: SessionRequest):
    agent = get_agent()
    if not agent.memory.enabled:
        return {"ok": True, "enabled": False}
    return {"ok": True, **agent.memory.start_session(req.session_id)}


@app.post("/api/session/end")
def api_session_end(req: SessionRequest):
    agent = get_agent()
    if not agent.memory.enabled:
        return {"ok": True, "enabled": False}
    return {"ok": True, **agent.memory.end_session(req.summary)}


@app.post("/api/session/cleanup")
def api_session_cleanup():
    """ESKI SESSIYALARNI TO'LIQ TOZALAYDI (chat tarixi + xotira + run'lar).

    Nima tozalanadi:
      1. chat_history.jsonl  --  30 kundan eski suhbatlar (eng so'nggi 20 ta + yulduzchalar saqlanadi)
      2. L1 runtime xotira  --  muddati o'tgan yozuvlar (cleanup_expired)
      3. L2 persistent  --  eskirgan yozuvlar arxivga/ochirish (cleanup_stale)
      4. tugagan agent run'lar (1 soatdan eski done/error)  --  xotira tozalanadi
      5. CHAT_PROGRESS buferi  --  eski (10 daqiqadan katta) yozuvlar

    Qaytaradi: batafsil hisobot {chat, runtime, persistent, runs, progress, ...}
    """
    report: dict = {"ok": True}

    # 1. Chat tarixi  -  eski suhbatlarni kesamiz
    report["chat"] = CHAT_HISTORY.prune(days=30, keep=20)

    # 2-3. Xotira (L1 runtime + L2 persistent)
    agent = get_agent()
    report["memory_enabled"] = agent.memory.enabled
    if agent.memory.enabled and getattr(agent.memory, "manager", None) is not None:
        mgr = agent.memory.manager
        try:
            if hasattr(mgr, "runtime") and hasattr(mgr.runtime, "cleanup_expired"):
                report["runtime_removed"] = mgr.runtime.cleanup_expired()
        except Exception as exc:
            report["runtime_error"] = str(exc)
        try:
            if hasattr(mgr, "persistent") and hasattr(mgr.persistent, "cleanup_stale"):
                report["persistent"] = mgr.persistent.cleanup_stale(archive_days=30, delete_days=90)
        except Exception as exc:
            report["persistent_error"] = str(exc)

    # 4. Tugagan agent run'lar  -  eski sessiya qoldiqlari
    report["runs_pruned"] = RUN_MANAGER.prune_finished(older_than_seconds=3600)

    # 5. CHAT_PROGRESS buferi  -  eski yozuvlar
    with CHAT_PROGRESS_LOCK:
        stale = [k for k, v in CHAT_PROGRESS.items() if time.time() - (v.get("ts") or 0) > 600]
        for k in stale:
            CHAT_PROGRESS.pop(k, None)
    report["progress_pruned"] = len(stale)

    report["timestamp"] = time.time()
    return report


# ------------------------------------------------------------------ #
# Human-in-the-loop run manager
# ------------------------------------------------------------------ #

class RunManager:
    """Agent run'larini fon thread'ida bajaradi; HITL savollarini to'playdi.

    Oqim:
      1. start(task) -> run_id  (thread ishga tushadi)
      2. agent request_human chaqirsa -> provider bloklanadi, savol saqlanadi
      3. frontend GET /api/agent/run/{id} -> status: awaiting_human + question
      4. frontend POST /api/agent/respond -> answer queue'ga tushadi
      5. agent davom etadi, yakuniy natija saqlanadi
    """

    def __init__(self):
        self._runs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, task: str, workspace_root: str, max_iter: int = 8,
              system: Optional[str] = None, allow_human: bool = True,
              session_id: str = "") -> str:
        run_id = uuid.uuid4().hex[:12]
        state = {
            "id": run_id,
            "status": "running",
            "question": None,
            "result": None,
            "error": None,
            "answers": queue.Queue(),
            "task": task,
            "started_at": time.time(),
            "session_id": session_id or f"conv-{uuid.uuid4().hex[:12]}",
            # REAL pipeline progress  -  executor progress_cb orqali jonli yangilanadi.
            "stage": "plan",
            "stage_detail": "task tahlil qilinmoqda…",
            "last_tool": None,
            "tool_count": 0,
        }
        with self._lock:
            self._runs[run_id] = state
        # ⚡ Task boshlangandayoq REAL chat tarixiga yoziladi  -  backend restart
        # bo'lsa ham task yozuvi yo'qolmaydi ("chala qolib ketgan" tasklar oldini
        # oladi). Yakuniy javob esa run tugagach qo'shiladi.
        CHAT_HISTORY.add_message(state["session_id"], "user", task)

        def _progress(stage: str, detail: str, record=None):
            """Executor'dan kelgan jonli bosqich  --  frontend polling'da ko'radi.

            record: bajarilgan tool yozuvi  --  RUN DAVOMIDA frontend chizma
            kartalarini jonli ko'rsatishi uchun `tool_calls_partial`ga qo'shiladi
            (run tugashini kutmaydi  --  real jarayonni vizual kuzatish imkoni).
            """
            state["stage"] = stage
            state["stage_detail"] = str(detail or "")[:120]
            if " → " in state["stage_detail"]:
                state["last_tool"] = state["stage_detail"].split(" → ", 1)[0]
                # Faqat HAQIQIY tool voqealari sanaladi (plan/review xabarlari emas)
                state["tool_count"] = int(state.get("tool_count") or 0) + 1
            if isinstance(record, dict) and record.get("tool"):
                # IMMUTABLE swap: har append'da YANGI ro'yxat yaratiladi  -  o'qiyotgan
                # thread (status/JSON serialize) eski snapshot'ni xavfsiz iteratsiya
                # qiladi. In-place append + parallel serialize -> "list changed size"
                # RuntimeError berishi mumkin edi (real race).
                entry = {
                    "tool": record.get("tool"),
                    "args": record.get("args") or {},
                    "result": record.get("result") or {},
                    "output_preview": str(record.get("output_preview") or "")[:300],
                }
                partial = state.get("tool_calls_partial") or []
                state["tool_calls_partial"] = (partial + [entry])[-60:]

        def _run():
            try:
                agent = get_agent()
                from executor import AgentExecutor
                from skills import DEFAULT_MANAGER
                from mcp_bridge import DEFAULT_BRIDGE

                if DEFAULT_BRIDGE.status()["servers"] is None or not DEFAULT_BRIDGE.status()["servers"]:
                    try:
                        DEFAULT_BRIDGE.start()
                    except Exception as exc:
                        print(f"[igris][mcp] bridge start: {exc}")

                ex = AgentExecutor(
                    workspace_root=workspace_root,
                    llm=agent.llm,
                    memory=agent.memory if agent.memory.enabled else None,
                    skills=DEFAULT_MANAGER,
                    mcp=DEFAULT_BRIDGE,
                    human_provider=(lambda q: self._human_provider(state, q)) if allow_human else None,
                    max_iter=max_iter,
                    progress_cb=_progress,
                )
                result = ex.run_native(task, system=system)
                state["result"] = result
                state["status"] = "done"
                # ⚡ task yakunini REAL chat tarixiga yozamiz  -  sidebar va grafda ko'rinadi
                final = (result or {}).get("final") or (result or {}).get("status") or "done"
                CHAT_HISTORY.add_message(state["session_id"], "assistant", str(final)[:2000])
            except Exception as exc:
                state["error"] = str(exc)
                state["status"] = "error"
                CHAT_HISTORY.add_message(state["session_id"], "assistant", f"✗ ERROR  -  {str(exc)[:2000]}")

        t = threading.Thread(target=_run, daemon=True, name=f"agent-run-{run_id}")
        t.start()
        return run_id

    def _human_provider(self, state: dict, question: str) -> str:
        """Agent savolini to'xtatadi va frontend javobini kutadi (max 15 min)."""
        state["question"] = question
        state["status"] = "awaiting_human"
        try:
            answer = state["answers"].get(timeout=900)
        except queue.Empty:
            state["question"] = None
            return "(timeout: no human answer received)"
        state["question"] = None
        return str(answer)

    def prune_finished(self, older_than_seconds: float = 3600) -> int:
        """Tugagan/error run'larni xotiradan tozalaydi (eski sessiya qoldiqlari).

        Run'lar xotirada cheksiz o'smasligi uchun: `done`/`error` holatidagi
        va belgilangan vaqtdan eski run'lar o'chiriladi. Qaytaradi: o'chirilgan
        run soni.
        """
        now = time.time()
        removed = 0
        with self._lock:
            for rid, state in list(self._runs.items()):
                if state.get("status") not in ("done", "error"):
                    continue
                started = state.get("started_at") or now
                if now - started > older_than_seconds:
                    self._runs.pop(rid, None)
                    removed += 1
        return removed

    def respond(self, run_id: str, answer: str) -> bool:
        with self._lock:
            state = self._runs.get(run_id)
        if state is None:
            return False
        state["answers"].put(answer)
        return True

    def status(self, run_id: str) -> Optional[dict]:
        with self._lock:
            state = self._runs.get(run_id)
        if state is None:
            return None
        return {
            "id": run_id,
            "status": state["status"],
            "question": state.get("question"),
            "task": state.get("task"),
            "result": state.get("result"),
            "error": state.get("error"),
            # Real pipeline progress (frontend PipelineStepper buni ko'rsatadi).
            "stage": state.get("stage"),
            "stage_detail": state.get("stage_detail"),
            "last_tool": state.get("last_tool"),
            "tool_count": state.get("tool_count"),
            # RUN DAVOMIDA bajarilgan tool'lar  -  frontend jonli chizma kartalarini
            # shu manbadan oladi (run tugagach `result.tool_calls` to'liqroq).
            "tool_calls": state.get("tool_calls_partial") or [],
        }


RUN_MANAGER = RunManager()


# ------------------------------------------------------------------ #
# Agent execution (smart planning & execution)
# ------------------------------------------------------------------ #

def _workspace_root(req_ws: str) -> str:
    """Agent ish maydoni: berilgan yoki default (Igris_brain/agent_workspace)."""
    if req_ws:
        return req_ws
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")


@app.post("/api/agent/plan")
def api_agent_plan(req: PlanRequest):
    agent = get_agent()
    planner = TaskPlanner(llm=agent.llm)
    plan = planner.plan(req.task)
    return {"ok": True, **plan}


@app.post("/api/agent/run")
def api_agent_run(req: RunRequest):
    agent = get_agent()
    root = _workspace_root(req.workspace)
    executor = AgentExecutor(
        workspace_root=root,
        llm=agent.llm,
        memory=agent.memory if agent.memory.enabled else None,
        max_iter=req.max_iter,
    )
    try:
        result = executor.run(req.task)
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/agent/toolrun")
def api_agent_toolrun(req: ToolRunRequest):
    """Native tool-calling: the LLM picks the tools itself (schema-based)."""
    agent = get_agent()
    root = _workspace_root(req.workspace)
    executor = AgentExecutor(
        workspace_root=root,
        llm=agent.llm,
        memory=agent.memory if agent.memory.enabled else None,
        max_iter=req.max_iter,
    )
    try:
        result = executor.run_native(req.task)
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/agent/task")
def api_agent_task(req: TaskRequest):
    """HITL agent run'ini boshlaydi (background thread). Returns run_id."""
    root = _workspace_root(req.workspace)
    run_id = RUN_MANAGER.start(req.task, root, max_iter=req.max_iter, session_id=req.session_id)
    return {"ok": True, "run_id": run_id}


@app.get("/api/agent/run/{run_id}")
def api_agent_run_status(run_id: str):
    state = RUN_MANAGER.status(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"ok": True, **state}


@app.post("/api/agent/respond")
def api_agent_respond(req: RespondRequest):
    ok = RUN_MANAGER.respond(req.run_id, req.answer)
    if not ok:
        raise HTTPException(status_code=404, detail="run not found")
    return {"ok": True, "delivered": True}


@app.get("/api/agent/skills")
def api_agent_skills():
    from skills import DEFAULT_MANAGER
    return {"ok": True, "skills": [
        {"name": s.name, "description": (s.description or "")[:200]}
        for s in DEFAULT_MANAGER.list()
    ]}


# ------------------------------------------------------------------ #
# Web AI Bridge (real browser automation via web_ai_bridge MCP server)
# ------------------------------------------------------------------ #

WEBAI_ACTIONS = {
    "navigate": ("web_ai_bridge__browser_navigate", ["url"]),
    "back": ("web_ai_bridge__browser_go_back", []),
    "forward": ("web_ai_bridge__browser_go_forward", []),
    "new_tab": ("web_ai_bridge__browser_new_tab", ["url"]),
    "switch_tab": ("web_ai_bridge__browser_switch_tab", ["index"]),
    "close_tab": ("web_ai_bridge__browser_close_tab", ["index"]),
    "refresh": ("web_ai_bridge__browser_press_key", ["key"]),
}


def _webai_bridge():
    """web_ai_bridge MCP serveri ulangan bo'lsa qaytaradi, aks holda None."""
    try:
        from mcp_bridge import DEFAULT_BRIDGE
    except Exception:
        return None
    if not DEFAULT_BRIDGE.status()["servers"]:
        try:
            DEFAULT_BRIDGE.start()
        except Exception:
            pass
    servers = DEFAULT_BRIDGE.status()["servers"] or []
    if "web_ai_bridge" not in servers:
        return None
    return DEFAULT_BRIDGE


@app.get("/api/webai/status")
def api_webai_status():
    """Real web-ai-bridge holati: ulanganmi, qaysi brauzer, ochiq tablar."""
    bridge = _webai_bridge()
    if bridge is None:
        return {"ok": True, "connected": False, "tabs": [], "error": "web_ai_bridge MCP server not connected"}
    info = bridge.call_tool("web_ai_bridge__browser_info", {})
    tabs_raw = bridge.call_tool("web_ai_bridge__browser_list_tabs", {})
    tabs = []
    if tabs_raw.get("ok"):
        try:
            parsed = json.loads(tabs_raw.get("output") or "[]")
            tabs = parsed if isinstance(parsed, list) else []
        except (ValueError, TypeError):
            tabs = []
    browser = {"channel": None, "mode": None}
    for line in (info.get("output") or "").splitlines():
        if line.startswith("Browser:"):
            browser["channel"] = line.split(":", 1)[1].strip()
        elif line.startswith("Mode:"):
            browser["mode"] = line.split(":", 1)[1].strip()
    return {"ok": True, "connected": True, "browser": browser,
            "tabs": tabs, "info": (info.get("output") or "")[:400]}


@app.post("/api/webai/action")
def api_webai_action(req: WebAIActionRequest):
    """Whitelisted web-ai-bridge tool proxy: navigate/back/forward/new_tab/..."""
    bridge = _webai_bridge()
    if bridge is None:
        return {"ok": False, "error": "web_ai_bridge MCP server not connected"}
    if req.action not in WEBAI_ACTIONS:
        return {"ok": False, "error": f"unknown action: {req.action}"}
    tool, params = WEBAI_ACTIONS[req.action]
    args = {}
    if "url" in params and req.url:
        args["url"] = req.url
    if "index" in params:
        args["index"] = req.index
    if req.action == "refresh":
        args["key"] = "F5"
    return bridge.call_tool(tool, args)


@app.get("/api/webai/screenshot")
def api_webai_screenshot():
    """Aktiv tabning real PNG screenshot'i (web-ai-bridge browser_screenshot)."""
    from fastapi.responses import Response
    import base64 as _b64
    bridge = _webai_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="web_ai_bridge not connected")
    result = bridge.call_tool("web_ai_bridge__browser_screenshot", {})
    img = result.get("image") if isinstance(result, dict) else None
    if not img or not img.get("data"):
        raise HTTPException(status_code=502, detail=(result.get("output") or result.get("error") or "no screenshot"))
    try:
        raw = _b64.b64decode(img["data"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return Response(content=raw, media_type=img.get("mimeType") or "image/png")


@app.get("/api/cag/status")
def api_cag_status():
    """CAG (response cache) holati."""
    agent = get_agent()
    cache = agent._cag()
    return {"ok": True, "enabled": cache is not None,
            "cag": cache.status() if cache else None}


@app.post("/api/cag/invalidate")
def api_cag_invalidate():
    """CAG keshini tozalash (kontekst o'zgarganda)."""
    agent = get_agent()
    cache = agent._cag()
    if cache is None:
        return {"ok": True, "cleared": 0}
    cleared = cache.invalidate()
    return {"ok": True, "cleared": cleared}


@app.get("/api/mag/status")
def api_mag_status():
    """MAG (memory-augmented context) holati."""
    agent = get_agent()
    mag = agent._mag()
    return {"ok": True, "enabled": mag is not None,
            "mag": mag.status() if mag else None}


@app.get("/api/hooks/status")
def api_hooks_status():
    """Agent hook bus holati."""
    from hooks import DEFAULT_BUS
    return {"ok": True, **DEFAULT_BUS.stats()}


@app.get("/api/agent/mcp")
def api_agent_mcp():
    from mcp_bridge import DEFAULT_BRIDGE
    if not DEFAULT_BRIDGE.status()["servers"]:
        try:
            DEFAULT_BRIDGE.start()
        except Exception as exc:
            return {"ok": True, "connected": False, "error": str(exc)}
    st = DEFAULT_BRIDGE.status()
    return {"ok": True, "connected": bool(st["servers"]), "servers": st["servers"],
            "tools": st["tools"], "error": st["error"]}


@app.get("/api/agent/tools")
def api_agent_tools():
    from tools import DEFAULT_REGISTRY
    return {"ok": True, "tools": [t["name"] for t in DEFAULT_REGISTRY.schemas()]}


@app.post("/api/agent/drawing/edit")
def api_drawing_edit(req: DrawingEditRequest):
    """Pauza qilingan chizmaga surgikal o'zgartirish kiritadi.

    Agent frozen kontekstni oladi (qaysi elementlar allaqachon chizilgan) va
    faqat kerakli qismlarni o'zgartiradi, qolganini buzmaydi. Asinxron run
     --  run_id qaytariladi, frontend /api/agent/run/{id} orqali poll qiladi.
    """
    root = _workspace_root(req.workspace)
    from tools import Workspace
    ws = Workspace(root)
    try:
        abs_path = ws.resolve(req.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail=f"file not found: {req.path}")

    frozen = req.frozen or {}
    drawn = frozen.get("revealed", 0)
    total = frozen.get("total", 0)
    elements = frozen.get("elements", []) or []
    task = (
        f"Modify the drawing file '{req.path}' in the workspace.\n"
        f"Context: the user paused the live build after {drawn}/{total} elements "
        f"were drawn. Elements already visible: {', '.join(str(e) for e in elements[:12]) or 'n/a'}.\n"
        f"User's change request: {req.request}\n"
        "Apply the change surgically  -  keep everything that does not need to change "
        "identical, change only what the request requires, keep the style consistent."
    )
    run_id = RUN_MANAGER.start(task, root, max_iter=10, system=DRAWING_EDIT_SYSTEM, allow_human=False)
    return {"ok": True, "run_id": run_id}


@app.get("/api/ui/compose")
def api_ui_compose(app_name: str = "dashboard", theme: str = "dark"):
    """UI spec -> universal kompozitsiya rejasi (qavatlar + exec_order + overlap).

    'Detal-ma-detal qurish' texnologiyasining PLANNING bosqichi: barcha
    elementlar rejada aniqlanadi, qavatlar (layers) hisoblanadi, bosh menyu
    kontentga xalaqit qilmaydimi tekshiriladi, g'isht (brick) qayta ishlatish
    tahlil qilinadi. Frontend LIVE BUILD puzzle tartibi uchun ishlatadi.
    """
    from ui_compose import compose_app
    try:
        plan = compose_app(app_name, theme)
        return {"ok": True, **plan}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/agent/workspace")
def api_agent_workspace(ws: str = ""):
    from tools import Workspace
    root = _workspace_root(ws)
    ws_obj = Workspace(root)
    listing = ws_obj.list("", depth=2)
    return {"ok": True, "root": root, **listing}


@app.get("/api/agent/workspace/file")
def api_agent_workspace_file(path: str, ws: str = ""):
    """Serve a workspace file (text or image) to the UI preview.

    Path traversal himoyasi: fayl faqat workspace root ichida bo'lishi mumkin.
    """
    from fastapi.responses import FileResponse
    from tools import Workspace
    root = _workspace_root(ws)
    ws_obj = Workspace(root)
    try:
        abs_path = ws_obj.resolve(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail=f"file not found: {path}")

    # Content-Type: rasm va matn fayllari uchun
    ext = os.path.splitext(abs_path)[1].lower()
    media = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".bmp": "image/bmp",
        ".ico": "image/x-icon",
        ".txt": "text/plain; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".py": "text/x-python; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".yaml": "text/yaml; charset=utf-8",
        ".yml": "text/yaml; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".ts": "text/plain; charset=utf-8",
        ".tsx": "text/plain; charset=utf-8",
        ".jsx": "text/plain; charset=utf-8",
        ".csv": "text/csv; charset=utf-8",
        ".log": "text/plain; charset=utf-8",
    }
    media_type = media.get(ext, "application/octet-stream")
    return FileResponse(
        abs_path,
        media_type=media_type,
        filename=os.path.basename(abs_path),
        content_disposition_type="inline",
    )


# ------------------------------------------------------------------ #
# Decision-quality probe (real agent runs -> reasoning scores)
# ------------------------------------------------------------------ #

class ProbeRequest(BaseModel):
    tasks: str = "all"   # all | code_csv,multi_notes,draw_apple,fix_code


class ProbeManager:
    """Probe'ni fon thread'ida ishga tushiradi; status'ni saqlaydi.

    Oqim:
      1. POST /api/probe/run -> run_id (thread ishga tushadi)
      2. GET /api/probe/run/{id} -> status: running + bajarilgan tasklar
      3. tugagach report JSON'ga yoziladi, GET /api/probe/report dan o'qiladi
    """

    def __init__(self):
        self._runs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, tasks: str = "all") -> str:
        run_id = uuid.uuid4().hex[:12]
        state = {
            "id": run_id,
            "status": "running",
            "tasks": tasks,
            "completed": [],
            "report": None,
            "error": None,
        }
        with self._lock:
            self._runs[run_id] = state

        def _run():
            try:
                from probe_decisions import run_probe
                from mcp_bridge import DEFAULT_BRIDGE
                agent = get_agent()

                # Mavjud bridge'ni ishlatamiz  -  yangi McpBridge yaratilmaydi
                if not DEFAULT_BRIDGE.status()["servers"]:
                    try:
                        DEFAULT_BRIDGE.start()
                    except Exception as exc:
                        print(f"[igris][probe] mcp start: {exc}")
                bridge = DEFAULT_BRIDGE if DEFAULT_BRIDGE.status()["servers"] else None

                def progress(task_id: str, status: str):
                    if status == "done" and task_id not in state["completed"]:
                        state["completed"].append(task_id)

                report = run_probe(
                    model=agent.llm.model,
                    base_url=agent.llm.base_url,
                    tasks=tasks,
                    progress=progress,
                    bridge=bridge,
                )
                state["report"] = report
                state["status"] = "done"
            except Exception as exc:
                state["error"] = str(exc)
                state["status"] = "error"

        t = threading.Thread(target=_run, daemon=True, name=f"probe-run-{run_id}")
        t.start()
        return run_id

    def status(self, run_id: str) -> Optional[dict]:
        with self._lock:
            state = self._runs.get(run_id)
        if state is None:
            return None
        return {k: state.get(k) for k in ("id", "status", "tasks", "completed", "error", "report")}


PROBE_MANAGER = ProbeManager()


# ------------------------------------------------------------------ #
# Refactor Machine (assessment / telemetry / query evaluation)
# ------------------------------------------------------------------ #

class AssessRequest(BaseModel):
    query: str
    lang: str = "en"


@app.get("/api/refactor/standards")
def api_refactor_standards():
    """Baholash standarti (4 o'lchov, og'irliklar, chegaralar)."""
    agent = get_agent()
    return {"ok": True, "standard": agent.refactor.standards()}


@app.get("/api/refactor/report")
def api_refactor_report():
    """To'liq refactor hisoboti: inventory, tasniflar, aloqalar, telemetry."""
    agent = get_agent()
    return {"ok": True, **agent.refactor.refactor_report()}


@app.get("/api/refactor/telemetry")
def api_refactor_telemetry():
    """Jarayon telemetry: stats + oxirgi snapshotlar trendi."""
    agent = get_agent()
    return {
        "ok": True,
        "stats": agent.refactor.telemetry.stats(),
        "trend": agent.refactor.telemetry.trend(limit=20),
    }


@app.post("/api/refactor/assess")
def api_refactor_assess(req: AssessRequest):
    """So'rovni baholaydi: query semantikasi + resolution + telemetry snapshot."""
    agent = get_agent()
    query = (req.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query required")
    return {"ok": True, **agent.refactor.evaluate_query(query, lang=req.lang)}


@app.post("/api/probe/run")
def api_probe_run(req: ProbeRequest):
    """Decision-quality probe'ni fon thread'ida boshlaydi. Returns run_id."""
    run_id = PROBE_MANAGER.start(tasks=req.tasks or "all")
    return {"ok": True, "run_id": run_id}


@app.get("/api/probe/run/{run_id}")
def api_probe_run_status(run_id: str):
    state = PROBE_MANAGER.status(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"ok": True, **state}


@app.get("/api/probe/report")
def api_probe_report():
    """Eng so'nggi probe hisoboti (decision_probe.json)  --  UI'ga beradi."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "decision_probe.json")
    if not os.path.isfile(path):
        return {"ok": True, "exists": False, "report": None}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            report = json.load(fh)
        return {"ok": True, "exists": True, "report": report}
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "exists": False, "error": str(exc), "report": None}


# ---------------------------------------------------------------------- #
# System services  -  UI'dan backend / ollama / frontend restart qilish
# ---------------------------------------------------------------------- #

# Ishga tushirilgan host/port  -  restart'da xuddi shu manzilda qayta ochiladi.
_RUN_HOST = "127.0.0.1"
_RUN_PORT = 8765
# Asl ishga tushirish flaglari (--model, --no-llm, --base-url, ...)  -  restart'da saqlanadi.
_RUN_EXTRA_ARGS: list[str] = []

_LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def _install_fatal_handlers():
    """Kutilmagan xatolarni log'ga yozadi  --  server "jim" qulab tushsa ham
    sabab Igris_brain/logs/server.log.err faylida qoladi.

    faulthandler: C darajasidagi qulash (segfault) traceback'ini ushlaydi.
    sys.excepthook: main thread'da ushlanmagan Python exception'larini
    yozadi (uvicorn tutib olmagan xatolar). Watchdog sababni tez topishi
    uchun juda muhim  --  "birdan offline" holatining ildizi shu yerda qoladi.
    """
    try:
        import faulthandler
        os.makedirs(_LOGS_DIR, exist_ok=True)
        faulthandler.enable(
            open(os.path.join(_LOGS_DIR, "server.log.err"), "a", encoding="utf-8", errors="replace")
        )
    except Exception:
        pass

    def _hook(exc_type, exc, tb):
        import traceback
        try:
            os.makedirs(_LOGS_DIR, exist_ok=True)
            with open(os.path.join(_LOGS_DIR, "server.log.err"), "a", encoding="utf-8") as fh:
                fh.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] UNHANDLED EXCEPTION  -  server yopilmoqda\n")
                traceback.print_exception(exc_type, exc, tb, file=fh)
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook


def _watchdog_state() -> dict:
    """Watchdog holatini logs/watchdog.json'dan o'qiydi (UI ko'rsatishi uchun).

    Watchdog alohida jarayon  --  server u haqida faqat shu fayl orqali biladi.
    Fayl yo'q bo'lsa: watchdog ishlamayapti (eskirgan run.bat bilan ishga
    tushirilgan yoki to'xtatilgan).
    """
    try:
        p = os.path.join(_LOGS_DIR, "watchdog.json")
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            if isinstance(d, dict):
                running = bool(d.get("running"))
                checked = d.get("checked_at")
                # Watchdog har ~4s yangilaydi. Agar holat ESKI bo'lsa (>15s)  - 
                # jarayon o'ldirilgan bo'lishi mumkin (force-kill stop-faylni
                # yozmasdan tugatadi)  -  UI yolg'on "active" ko'rsatmasligi uchun.
                if running and isinstance(checked, (int, float)):
                    if time.time() - float(checked) > 15.0:
                        running = False
                return {
                    "running": running,
                    "backend_up": bool(d.get("backend_up")),
                    "ollama_up": bool(d.get("ollama_up")),
                    "backend_restarts": int(d.get("backend_restarts") or 0),
                    "ollama_restarts": int(d.get("ollama_restarts") or 0),
                    "last_restart": d.get("last_restart"),
                    "checked_at": checked,
                    "last_error": d.get("last_error"),
                }
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return {"running": False}


def _ollama_running(timeout: float = 1.5) -> bool:
    """Ollama ishlayaptimi? (localhost:11434 /api/tags tekshiruvi)."""
    try:
        import urllib.request
        with urllib.request.urlopen(
            "http://127.0.0.1:11434/api/tags", timeout=timeout
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


def _port_in_use(port: int) -> bool:
    """Port bandmi? (restart port bo'shatishini kutish uchun)."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _wait_port_free(port: int, timeout: float = 20.0) -> bool:
    """Port bo'shashini kutadi (eski server jarayoni o'lishini kutish)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _port_in_use(port):
            return True
        time.sleep(0.5)
    return not _port_in_use(port)


def _spawn_detached(title: str, command: str, cwd: str, log_file: Optional[str] = None):
    """Fon rejimida ko'rinmas jarayon ochadi  --  yangi terminal oynasi YO'Q.

    Windows'da CREATE_NO_WINDOW ishlatiladi (avvalgi `cmd /k` yangi oyna
    ochardi  --  endi UI restart'da hech qanday terminal paydo bo'lmaydi).
    Chiqish log fayliga yoziladi (agar berilsa). Restart qilingan jarayon
    ota-onadan mustaqil yashaydi  --  UI'ni qayta yuklash unga ta'sir qilmaydi.
    """
    out = err = subprocess.DEVNULL
    if log_file:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
            out = open(log_file, "a", encoding="utf-8", errors="replace")
            err = open(log_file + ".err", "a", encoding="utf-8", errors="replace")
        except OSError:
            out = err = subprocess.DEVNULL
    try:
        if os.name == "nt":
            flags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                flags |= subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "DETACHED_PROCESS"):
                flags |= subprocess.DETACHED_PROCESS
            return subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                close_fds=True,
                creationflags=flags,
            )
        return subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            close_fds=True,
        )
    finally:
        # Jarayon o'zi uchun handle'ni ko'chirib oldi  -  ota-onadagi ochiq
        # fayl deskriptorlarini yopamiz (fd leak oldini olinadi).
        for h in (out, err):
            if h is not subprocess.DEVNULL and not h.closed:
                try:
                    h.close()
                except OSError:
                    pass


def _server_start_command(restart_token: str = "") -> str:
    """Backend'ni asl sozlamalari bilan qayta ishga tushirish komandasi.

    Host/port har doim yoziladi (asl argv'dan filtrlanadi, dublikat bo'lmaydi),
    qolgan flaglar  --  `python server.py ...`'dagi asl argv'dan (--model,
    --base-url, --no-llm, --no-memory, ...) olinadi.

    restart_token berilsa  --  yangi jarayon agent'ini muvaffaqiyatli boshlagach
    marker fayl yozadi; eski jarayon o'sha markerni kutib, shundan keyingina
    o'zini tugatadi (restart "soxta" bo'lmaydi  --  yangi server o'lsa, eskisi
    yashab qoladi).
    """
    script = os.path.abspath(__file__)
    parts = [f'"{sys.executable}"', f'"{script}"',
             "--host", _RUN_HOST, "--port", str(_RUN_PORT)]
    if restart_token:
        parts += ["--restart-token", restart_token]
    parts += [str(a) for a in _RUN_EXTRA_ARGS]
    return " ".join(parts)


def _persist_launch_info():
    """Backend'ni asl sozlamalari bilan qayta ishga tushirish komandasini
    logs/server_launch.json fayliga yozadi.

    Watchdog (alohida jarayon) shu faylni o'qib, backend qulab tushsa uni
    XUDDI SHU flaglar bilan qayta ochadi  --  restart'da hech qanday sozlama
    yo'qolmaydi (--model, --no-llm, --base-url, --memory-dir ... saqlanadi).
    """
    try:
        os.makedirs(_LOGS_DIR, exist_ok=True)
        with open(os.path.join(_LOGS_DIR, "server_launch.json"), "w", encoding="utf-8") as fh:
            json.dump({
                "command": _server_start_command(),
                "host": _RUN_HOST,
                "port": _RUN_PORT,
                "pid": os.getpid(),
                "started_at": time.time(),
            }, fh, ensure_ascii=False)
    except OSError as exc:
        print(f"[igris][system] launch info write failed: {exc}")


def _restart_marker_path(token: str) -> str:
    """Restart marker fayli  --  yangi jarayon tayyor bo'lgach yozadi."""
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "logs", f"restart_{token}.ok"
    )


def _write_restart_marker(token: str):
    """Yangi jarayon agent'ini boshlashga muvaffaq bo'ldi  --  marker yoziladi.

    Marker uvicorn.run'gacha bo'lgan barcha xavfli bosqichlardan (create_agent,
    model tanlash, speed sozlamasi) KEYIN yoziladi  --  shu bosqichlarda xato
    bo'lsa marker yozilmaydi va eski jarayon o'zini o'ldirmaydi.
    """
    try:
        os.makedirs(os.path.dirname(_restart_marker_path(token)), exist_ok=True)
        with open(_restart_marker_path(token), "w", encoding="utf-8") as fh:
            fh.write(str(time.time()))
    except OSError as exc:
        print(f"[igris][system] restart marker write failed: {exc}")


@app.get("/api/system/services")
def api_system_services():
    """Xizmatlar holati: backend (o'zi), ollama, MCP serverlar."""
    mcp = {"connected": False, "servers": []}
    try:
        from mcp_bridge import DEFAULT_BRIDGE
        st = DEFAULT_BRIDGE.status()
        mcp = {"connected": bool(st.get("servers")), "servers": st.get("servers") or []}
    except Exception:
        pass
    return {
        "ok": True,
        "backend": {"running": True, "host": _RUN_HOST, "port": _RUN_PORT, "version": app.version},
        "ollama": {"running": _ollama_running()},
        # Watchdog holati  -  backend qulab tushsa uni avtomatik qayta ishga
        # tushiradigan qo'riqchi jarayon (UI'da ko'rsatiladi).
        "watchdog": _watchdog_state(),
        "mcp": mcp,
        "timestamp": time.time(),
    }


@app.post("/api/system/restart")
def api_system_restart():
    """Backend'ni o'zini qayta ishga tushiradi (asl sozlamalari bilan).

    Javob darhol qaytadi; ~1 soniyadan so'ng yangi jarayon ochiladi va
    agent'ni muvaffaqiyatli boshlagach (marker handshake) eski jarayon
    tugatiladi. Yangi jarayon qulab tushsa  --  eski jarayon ishlashda davom
    etadi (soxta restart yo'q, backend o'lik qolmaydi). Frontend ping orqali
    qayta ulanishni kutadi.
    """
    def _restart():
        time.sleep(1.0)
        token = uuid.uuid4().hex[:12]
        proc = None
        try:
            # Yangi server jarayoni log'larini ham saqlaymiz (oyna yo'q,
            # lekin xato bo'lsa logs/server.log.da ko'rinadi). Popen handle'i
            # saqlanadi  -  marker'dan tashqari jarayon tirikligi ham tekshiriladi.
            proc = _spawn_detached(
                "IGRIS Brain Server",
                _server_start_command(restart_token=token),
                os.path.dirname(os.path.abspath(__file__)),
                log_file=os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "logs", "server.log"
                ),
            )
        except Exception as exc:
            print(f"[igris][system] restart spawn failed: {exc}")
        # Yangi jarayon ochilgan bo'lsagina uni KUTAMIZ  -  faqat agent'ni to'liq
        # boshlagach (marker fayl yozilgach) eskisini tugatamiz. Marker 60s ichida
        # kelmasa YOKI yangi jarayon o'lib qolsa (proc.poll() is not None)  -  eski
        # jarayon yashab qoladi, backend o'lik qolib ketmaydi (soxta restart yo'q).
        if proc is not None:
            deadline = time.time() + 60.0
            while time.time() < deadline:
                # Yangi jarayon import/agent bosqichida qulab tushgan  -  marker
                # yozilgan bo'lsa ham eskisini o'ldirmaymiz (backend o'lik qolmasin).
                if proc.poll() is not None:
                    print(
                        "[igris][system] yangi jarayon erta chiqib ketdi "
                        f"(exit={proc.poll()})  -  eski jarayon ishlashda davom etadi. "
                        "Log: logs/server.log"
                    )
                    return
                if os.path.isfile(_restart_marker_path(token)):
                    try:
                        os.unlink(_restart_marker_path(token))
                    except OSError:
                        pass
                    os._exit(0)
                    return
                time.sleep(0.5)
            print(
                "[igris][system] restart TIMEOUT  -  yangi server ishga tushmadi, "
                "eski jarayon ishlashda davom etadi. Log: logs/server.log"
            )

    threading.Thread(target=_restart, daemon=True, name="system-restart").start()
    return {"ok": True, "restarting": True, "port": _RUN_PORT}


@app.post("/api/system/ollama/start")
def api_system_ollama_start():
    """Ollama serve'ni ishga tushiradi (agar ishlamayotgan bo'lsa).

    Yangi oyna ochilmaydi  --  jarayon fon rejimida, log'lari
    Igris_brain/logs/ollama.log fayliga yoziladi.
    """
    if _ollama_running():
        return {"ok": True, "running": True, "started": False, "note": "already running"}
    try:
        _spawn_detached(
            "IGRIS Ollama", "ollama serve", os.path.expanduser("~"),
            log_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "ollama.log"),
        )
        return {"ok": True, "started": True, "note": "ollama serve started (hidden)"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/api/system/ollama/restart")
def api_system_ollama_restart():
    """Ollama'ni qayta ishga tushiradi: eski jarayonni to'xtatib, yana ochadi.

    UI'dagi '⟳ restart' tugmasi buni chaqiradi. Windows'da port 11434 dagi
    jarayon topilib o'ldiriladi, so'ng `ollama serve` yangi, oynasiz
    jarayon sifatida qayta ochiladi.
    """
    if _ollama_running():
        _kill_port(11434)
        # Port bo'shashini kutamiz (max ~5s)
        for _ in range(10):
            if not _ollama_running(timeout=0.5):
                break
            time.sleep(0.5)
    try:
        _spawn_detached(
            "IGRIS Ollama", "ollama serve", os.path.expanduser("~"),
            log_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "ollama.log"),
        )
        time.sleep(0.8)
        return {"ok": True, "running": _ollama_running(timeout=2.0), "started": True,
                "note": "ollama serve restarted (hidden)"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _port_pids(port: int) -> set[str]:
    """Berilgan portda LISTENING qilayotgan jarayon PIDs (Windows netstat)."""
    pids: set[str] = set()
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=10
        ).stdout or ""
        for line in out.splitlines():
            if f":{port} " not in line:
                continue
            if "LISTENING" not in line.upper():
                continue
            parts = line.split()
            if parts and parts[-1].isdigit():
                pids.add(parts[-1])
    except Exception:
        pass
    return pids


def _kill_port(port: int) -> bool:
    """Portni egallagan jarayon(lar)ni to'xtatadi (Ollama restart uchun)."""
    killed = False
    for pid in _port_pids(port):
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", pid],
                capture_output=True, timeout=10,
            )
            killed = True
        except Exception:
            pass
    return killed


# ---------------------------------------------------------------------- #
# Entrypoint
# ---------------------------------------------------------------------- #

def main() -> int:
    global _RUN_HOST, _RUN_PORT, _RUN_EXTRA_ARGS
    # Kutilmagan xatolar log'ga yoziladi (watchdog sababni topa oladi)
    _install_fatal_handlers()
    parser = argparse.ArgumentParser(description="IGRIS Brain FastAPI bridge")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--model", default=os.environ.get("IGRIS_MODEL", "qwen3:8b"))
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--no-llm", action="store_true", help="disable Ollama fallback")
    parser.add_argument("--no-memory", action="store_true", help="disable Igris_Memory")
    parser.add_argument("--memory-dir", default="")
    parser.add_argument("--logprobs", action="store_true",
                        help="LLM javoblari uchun OpenAI-mos logprob re-so'ruvi "
                             "(self-eval ishonch signali; 2x inference narxi)")
    parser.add_argument("--restart-token", default="", help=argparse.SUPPRESS)  # noqa: E501
    # Eslatma: default="" (SUPPRESS emas)  --  flag berilmasa ham atribut mavjud bo'ladi.
    args = parser.parse_args()
    _RUN_HOST = args.host or _RUN_HOST
    _RUN_PORT = args.port or _RUN_PORT
    # Restart'da saqlanadigan asl flaglar. --host/--port VA ularning qiymatlari
    # tashlanadi (aks holda eski port qiymati "--port 9999" restart komandasida
    # qolib, argparse xatosi bilan yangi server o'lib qolardi).
    _RUN_EXTRA_ARGS = []
    argv = list(sys.argv[1:])
    i = 0
    while i < len(argv):
        a = argv[i]
        # --host=X / --port=X ko'rinishi ham tashlanadi (argparse ikkala
        # usulni qabul qiladi  --  restart komandasi dublikat flag olmasin).
        if a in ("--host", "--port") or a.startswith(("--host=", "--port=")):
            i += 2 if "=" not in a else 1  # flag + qiymatini o'tkazib yuboramiz
            continue
        if a == "--restart-token" or a.startswith("--restart-token="):
            i += 2 if "=" not in a else 1
            continue
        _RUN_EXTRA_ARGS.append(a)
        i += 1

    create_agent(
        model=args.model,
        base_url=args.base_url,
        use_llm=not args.no_llm,
        memory=not args.no_memory,
        memory_dir=args.memory_dir,
        logprobs=args.logprobs,
    )
    # Diskdagi TURBO sozlamasini qayta qo'llaymiz (restart'da yo'qolmaydi)
    _load_speed()
    if _SPEED.get("turbo"):
        get_agent().set_speed(True)
        print("[igris] speed: turbo=on (restored from speed_settings.json)")
    # 2nd Brain graf sozlamalarini diskdan yuklaymiz (restart'da yo'qolmaydi)
    _load_graph_shares()
    saved_shares = _GRAPH_SHARES.get("shares")
    saved_max = _GRAPH_SHARES.get("max_nodes")
    if saved_shares or saved_max:
        print(f"[igris] brain graph settings restored: shares={saved_shares} max_nodes={saved_max}")
    print(f"[igris] agent ready: model={args.model} llm={not args.no_llm} memory={not args.no_memory}")
    print(f"[igris] listening on http://{args.host}:{args.port}")
    # Health monitor  --  agent sog'lig'ini fon'da kuzatadi
    _start_health_monitor()
    # Restart jarayonida bo'lsak  --  agent muvaffaqiyatli boshlangani marker fayl
    # orqali eski jarayonga xabar beriladi (u shundan keyin o'zini tugatadi).
    # Marker create_agent'dan KEYIN, port kutishdan OLDI yoziladi  --  yangi server
    # portni eski jarayon bo'shatgach bog'laydi; eski jarayon marker ko'rishi bilan
    # chiqadi (hech qanday deadlock yo'q). Agar create_agent qulab tushsa marker
    # yozilmaydi va eski jarayon ishlashda davom etadi.
    if args.restart_token:
        _write_restart_marker(args.restart_token)
    # Watchdog'ga restart komandasini yozamiz  --  backend qulab tushsa uni
    # xuddi shu sozlamalar bilan qayta ochadi ("birdan offline" oldini oladi).
    _persist_launch_info()
    # Restart'da eski jarayon portni bo'shatishini kutamiz  --  yangi server
    # "address already in use" xatosiz ishga tushadi (UI restart ishonchli).
    if _port_in_use(args.port):
        print(f"[igris] port {args.port} band  --  bo'shatilishini kutmoqda… (restart)")
        _wait_port_free(args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
