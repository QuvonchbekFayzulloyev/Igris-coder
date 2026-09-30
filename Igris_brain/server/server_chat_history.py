"""
IGRIS BRAIN — ServerChatHistory — S5 modullashtirish
====================================================
problems_to_fix.md :: S5 (qism) — server.py god-file'dan ajratilgan.

Chat tarixi qatlami:
  CHAT_PROGRESS / CHAT_PROGRESS_LOCK  — chat pipeline jonli progress buferi
                                        (/api/chat/progress poll qiladi)
  CHAT_HISTORY_PATH                   — chat_history.jsonl yo'li
  _chat_progress_cb / _clear          — agent progress callback'lari
  _structure_fail_warning             — transcript ogohlantirish matni
  ChatHistory                         — JSONL do'kon (add/list/get/star/rename/
                                        delete/prune/clear_all + tombstone fayl)
  CHAT_HISTORY                        — server uchun yagona nusxa (singleton)

Bu modul FAQAT stdlib'dan foydalanadi (fastapi/pydantic yo'q) — server.py
import qilib qayta eksport qiladi (testlar kontrakti saqlanadi:
`from server import ChatHistory, _structure_fail_warning`).
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Optional

__all__ = [
    "CHAT_PROGRESS", "CHAT_PROGRESS_LOCK", "CHAT_HISTORY_PATH",
    "_chat_progress_cb", "_chat_progress_clear", "_structure_fail_warning",
    "ChatHistory", "CHAT_HISTORY",
]

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


