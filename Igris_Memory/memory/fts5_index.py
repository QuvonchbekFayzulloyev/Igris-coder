r"""
CODER AGENT MEMORY — FTS5 INDEX (T1 optimization)
==================================================
SQLite FTS5-based keyword index: incremental, diskda saqlanadigan, O(log n) insert.

Muammo (T1): BM25Index har add_document'da `_built=False` qilardi — keyingi
search butun index'ni rebuild qilardi O(N). Katta korpusda har savol sekin.

Yechim: FTS5 in-place incremental insert + bm25() ranking funksiyasi.
SQLite 3.9+ FTS5 bilan built-in (tekshirildi: mavjud).

Interfeys BM25Index bilan BIR XIL:
  add_document(content, metadata) / build() / search(query, top_k) / get_stats()
  tokenize(text) — bir xil tokenizatsiya (whitespace, lowercase, [^\w\s] -> space)

Fallback: FTS5 yo'q bo'lsa — asl BM25Index ga o'tadi (degradation, crash yo'q).

Metadata JSON (source/type/layer...) fts5 jadval yonida oddiy jadvalda saqlanadi
(purpose: BM25Index.metadata[idx] bilan bir xil o'qish).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time

try:  # pragma: no cover - muhitga bog'liq
    _probe = sqlite3.connect(":memory:")
    _probe.execute("CREATE VIRTUAL TABLE _fts_probe USING fts5(x)")
    _probe.close()
    _FTS5_AVAILABLE = True
except Exception:  # pragma: no cover
    _FTS5_AVAILABLE = False


def tokenize(text: str) -> list[str]:
    """BM25Index.tokenize bilan BIR XIL — FTS5 unicode61 tokenizer ham
    whitespace/punktatsiyani ajratadi (chiziqli mos emas, lekin recall uchun
    bir xil oila: lowercase + alfanumerik tokenlar).

    A3: apostrof (', ', ʻ, ʼ, `) O'CHIRILADI — 'o'qish' → 'oqish' (bir token).
    """
    text = text.lower()
    text = re.sub(r"[\u0027\u2018\u2019\u02bc\u02ee\u0060]", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return [t for t in text.split() if len(t) > 1]


def _query_tokens(text: str) -> list[str]:
    """A3: QUERY-side o'zbekcha stem kengaytirmasi.

    FTS5 index tomonda unicode61 qotib qolgan (mavjud DB mosligi) — lekin
    MATCH so'rovida har token uchun OR bilan stem variantini qo'shsak,
    'kitoblarni' → kitoblarni OR kitob bo'lib, indexda stem-siz saqlangan
    'kitob' bilan ham mos topadi. Deterministik, stdlib faqat.
    """
    raw = tokenize(text)
    try:
        from memory.retrieval import uz_stem
    except ImportError:  # pragma: no cover - paket ichi import
        from retrieval import uz_stem  # type: ignore
    out: list[str] = []
    seen: set[str] = set()
    for t in raw:
        if t not in seen:
            seen.add(t)
            out.append(t)
        s = uz_stem(t)
        if s != t and len(s) > 1 and s not in seen:
            seen.add(s)
            out.append(s)
    return out


class FTS5Index:
    """Incremental keyword index (SQLite FTS5) — BM25Index drop-in replacement."""

    def __init__(self, db_path: str = "", k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.db_path = db_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "brain_data", "fts_index.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._memo = None  # asl BM25Index fallback (FTS5 yo'q bo'lsa)
        self._stats_cache: dict | None = None
        self.total_docs = 0
        # T1: bulk-load uchun deferred commit — har hujjatda alohida COMMIT
        # WAL fsync → 3000 hujjatda sekin. 200 hujjatda bir marta commit;
        # search/close/conn o'lganda flush. Index qayta quriladigan (manba
        # fayllardan) — yo'qolgan pending qabul qilinadi.
        self._pending = 0
        self._COMMIT_EVERY = 200
        self._open()

    # ------------------------------------------------------------ #
    # Connection / schema
    # ------------------------------------------------------------ #

    def _open(self) -> None:
        with self._lock:
            if not _FTS5_AVAILABLE:
                from retrieval import BM25Index
                self._memo = BM25Index(k1=self.k1, b=self.b)
                return
            try:
                self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA synchronous=NORMAL")
                self._conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
                        content,
                        tokenize = 'unicode61',
                        prefix = '2 3'
                    )
                    """
                )
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS docs_meta (
                        rowid INTEGER PRIMARY KEY,
                        content_hash TEXT UNIQUE,
                        metadata TEXT
                    )
                    """
                )
                self._conn.commit()
                self._refresh_total()
            except Exception:
                self._conn = None
                from retrieval import BM25Index
                self._memo = BM25Index(k1=self.k1, b=self.b)

    def _refresh_total(self) -> None:
        try:
            cur = self._conn.execute("SELECT COUNT(*) FROM docs_meta")
            self.total_docs = int(cur.fetchone()[0])
        except Exception:
            self.total_docs = 0

    def _flush(self) -> None:
        """Pending tranzaksiyani diskga yozadi (xato jim yutiladi — defensive)."""
        if self._conn is not None and self._pending > 0:
            try:
                self._conn.commit()
            except Exception:
                pass
            self._pending = 0

    def close(self) -> None:
        with self._lock:
            self._flush()
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

    # ------------------------------------------------------------ #
    # Write path (incremental — rebuild YO'Q)
    # ------------------------------------------------------------ #

    @staticmethod
    def _hash(content: str, metadata: dict) -> str:
        return hashlib.sha1(
            (json.dumps(metadata, ensure_ascii=False, sort_keys=True) + "\x00" + content)
            .encode("utf-8", "ignore")
        ).hexdigest()

    def add_document(self, content: str, metadata: Optional[dict] = None) -> None:
        """Incremental insert. Dublikat (bir xil content+metadata) yozilmaydi."""
        meta = metadata or {"source": "unknown"}
        if self._memo is not None:  # fallback rejim
            self._memo.add_document(content, meta)
            self.total_docs = self._memo.total_docs
            return
        with self._lock:
            if self._conn is None:
                return
            try:
                h = self._hash(content, meta)
                cur = self._conn.execute(
                    "SELECT 1 FROM docs_meta WHERE content_hash = ?", (h,)
                )
                if cur.fetchone() is not None:
                    return  # dedup: allaqachon bor
                cur = self._conn.execute(
                    "INSERT INTO docs_fts(content) VALUES (?)", (content,)
                )
                rowid = cur.lastrowid
                self._conn.execute(
                    "INSERT INTO docs_meta(rowid, content_hash, metadata) VALUES (?,?,?)",
                    (rowid, h, json.dumps(meta, ensure_ascii=False)),
                )
                self._pending += 1
                if self._pending >= self._COMMIT_EVERY:
                    self._flush()
                self.total_docs += 1
                self._stats_cache = None
            except Exception:
                try:
                    self._conn.rollback()
                    self._pending = 0
                except Exception:
                    pass

    # ------------------------------------------------------------ #
    # Search path (bm25() — rebuild yo'q)
    # ------------------------------------------------------------ #

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if self._memo is not None:  # fallback rejim
            return self._memo.search(query, top_k)
        with self._lock:
            if self._conn is None or self.total_docs == 0:
                return []
            self._flush()  # pending yozuvlar searchda ko'rinishi uchun (shu conn ko'radi, lekin baribir)
            try:
                # A3: query-side stem kengaytirmasi (kitoblarni → +kitob)
                tokens = _query_tokens(query)
                if not tokens:
                    return []
                # FTS5 MATCH: OR bilan — BM25Index ham partial match beradi;
                # bm25() natijani relevance bo'yicha tartiblaydi.
                match = " OR ".join(f'"{t}"' for t in tokens)
                t0 = time.perf_counter()
                cur = self._conn.execute(
                    """
                    SELECT rowid, bm25(docs_fts) AS rank
                    FROM docs_fts
                    WHERE docs_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (match, int(top_k)),
                )
                rows = cur.fetchall()
                out: list[dict] = []
                for rowid, rank in rows:
                    m = self._conn.execute(
                        "SELECT metadata FROM docs_meta WHERE rowid = ?", (rowid,)
                    ).fetchone()
                    meta = json.loads(m[0]) if m else {"source": "unknown"}
                    out.append({
                        # FTS5 bm25() kichik = yaxshi; BM25Index katta = yaxshi.
                        # Interfeys mosligi uchun ishorani musbat qilamiz.
                        "score": -float(rank),
                        "metadata": meta,
                        "index": rowid,
                    })
                self._search_ms = (time.perf_counter() - t0) * 1000
                return out
            except Exception:
                return []

    # ------------------------------------------------------------ #
    # API parity
    # ------------------------------------------------------------ #

    def build(self) -> None:
        """FTS5'da build kerak emas (incremental) — noop (interfeys uchun)."""
        if self._memo is not None:
            self._memo.build()

    def remove_source(self, source: str) -> int:
        """Berilgan `source` metadata'ga ega hujjatlarni o'chiradi (T2).

        FTS5 incremental DELETE — rebuild yo'q. Fallback rejimida asl
        BM25Index'ga delegatsiya qilinadi.

        Qaytaradi: o'chirilgan hujjatlar soni.
        """
        if self._memo is not None:  # fallback rejim
            return self._memo.remove_source(source)
        with self._lock:
            if self._conn is None:
                return 0
            try:
                # LIKE naqshi JSON-escaped bo'lishi kerak: Windows path'lar
                # json.dumps'da backslash `\\` ga aylanadi — xom path bilan
                # LIKE hech narsa topmas edi.
                src_json = json.dumps(source, ensure_ascii=False)[1:-1]
                cur = self._conn.execute(
                    "SELECT rowid FROM docs_meta WHERE metadata LIKE ?",
                    (f'%"source": "{src_json}"%',),
                )
                rowids = [r[0] for r in cur.fetchall()]
                if not rowids:
                    return 0
                # docs_meta.metadata JSON — aniq match uchun qayta tekshiramiz
                exact: list[int] = []
                for rowid in rowids:
                    m = self._conn.execute(
                        "SELECT metadata FROM docs_meta WHERE rowid = ?", (rowid,)
                    ).fetchone()
                    if m:
                        try:
                            meta = json.loads(m[0])
                            if isinstance(meta, dict) and meta.get("source") == source:
                                exact.append(rowid)
                        except Exception:
                            pass
                if not exact:
                    return 0
                qmarks = ",".join("?" for _ in exact)
                self._conn.execute(
                    f"DELETE FROM docs_fts WHERE rowid IN ({qmarks})", exact)
                self._conn.execute(
                    f"DELETE FROM docs_meta WHERE rowid IN ({qmarks})", exact)
                self._pending += 1
                self._flush()
                self._refresh_total()
                self._stats_cache = None
                return len(exact)
            except Exception:
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                return 0

    @property
    def _built(self) -> bool:
        """Har doim 'built' — incremental insert + instant search."""
        return True

    def get_stats(self) -> dict:
        if self._memo is not None:
            return self._memo.get_stats()
        with self._lock:
            unique = 0
            try:
                unique = int(
                    self._conn.execute("SELECT COUNT(*) FROM docs_fts").fetchone()[0]
                )
            except Exception:
                pass
            return {
                "total_documents": self.total_docs,
                "unique_terms": unique,
                "engine": "fts5",
                "db_path": self.db_path,
            }
