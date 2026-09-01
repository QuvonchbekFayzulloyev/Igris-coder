"""
IGRIS BRAIN — 2nd Brain Graph tests
===================================
brain_graph.py real Igris_Memory ma'lumotlaridan grafik qurishini tekshiradi:
- vault .md fayllari node bo'ladi
- wikilinklar bog'lanishlarga aylanadi
- L2/L1 JSONL yozuvlar node bo'ladi
- kind mapping to'g'ri
- layout chegarada qoladi (viewBox 620x380)
"""

import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# TestServerSharePersistence server.py (Igris_brain/) dagi persist funksiyalarini
# ham tekshiradi — shuning uchun Igris_brain ham path'ga qo'shiladi.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "Igris_brain"))

from brain_graph import (  # noqa: E402
    build_graph, _stable_blend, normalize_shares, graph_version_fingerprint,
    DEFAULT_SHARES,
)


def _mk_nodes(n: int, prefix: str) -> list[dict]:
    """Sinov uchun sintetik node'lar (kind'lar aylanib turadi)."""
    kinds = ["fact", "session", "pattern", "architecture"]
    return [{
        "id": f"{prefix}:{i}", "label": f"{prefix}{i}", "kind": kinds[i % 4],
        "x": 10, "y": 10, "detail": "",
    } for i in range(n)]


class TestServerSharePersistence(unittest.TestCase):
    """Kvota ulushlari server'da persist qilinadi (graph_shares.json).

    localStorage emas — server restart'da ham sozlama qoladi.
    """

    _RESET = {"shares": None, "max_nodes": None, "updated_at": None, "history": []}

    def setUp(self):
        import server
        self.server = server
        # Xavfsizlik: test real faylga tegmaydi — temp fayl ishlatiladi.
        self._orig_file = server._GRAPH_SHARES_FILE
        self._orig_shares = server._GRAPH_SHARES
        self.tmp = os.path.join(tempfile.gettempdir(), "igris_test_shares.json")
        if os.path.isfile(self.tmp):
            os.remove(self.tmp)
        server._GRAPH_SHARES_FILE = self.tmp
        server._GRAPH_SHARES = dict(self._RESET)

    def tearDown(self):
        self.server._GRAPH_SHARES_FILE = self._orig_file
        self.server._GRAPH_SHARES = self._orig_shares
        if os.path.isfile(self.tmp):
            os.remove(self.tmp)

    def _reset_memory(self):
        self.server._GRAPH_SHARES = dict(self._RESET)

    def test_persist_then_load_roundtrip(self):
        s = self.server
        s._persist_graph_shares([0.30, 0.30, 0.20, 0.20], updated_at=1000.0)
        self.assertTrue(os.path.isfile(s._GRAPH_SHARES_FILE))
        # Xotirani tozalab, diskdan o'qiymiz (restart simulyatsiyasi)
        self._reset_memory()
        s._load_graph_shares()
        self.assertEqual(s._GRAPH_SHARES["shares"], [0.30, 0.30, 0.20, 0.20])
        self.assertEqual(s._GRAPH_SHARES["updated_at"], 1000.0)
        self.assertEqual(len(s._GRAPH_SHARES["history"]), 1)
        self.assertEqual(s._GRAPH_SHARES["history"][0]["shares"], [0.30, 0.30, 0.20, 0.20])

    def test_max_nodes_roundtrip(self):
        """max_nodes ham ulushlar bilan birga diskda saqlanadi (restart'da qoladi)."""
        s = self.server
        s._persist_graph_shares([0.30, 0.30, 0.20, 0.20], max_nodes=300, updated_at=1000.0)
        self._reset_memory()
        s._load_graph_shares()
        self.assertEqual(s._GRAPH_SHARES["max_nodes"], 300)
        self.assertEqual(s._GRAPH_SHARES["shares"], [0.30, 0.30, 0.20, 0.20])
        # Tarix yozuvi ham max_nodes'ni olib yuradi
        self.assertEqual(s._GRAPH_SHARES["history"][0]["max_nodes"], 300)

    def test_partial_update_only_max_nodes_keeps_shares(self):
        """Faqat max_nodes o'zgarsa — ulushlar buzilmaydi (qisman yangilash)."""
        s = self.server
        s._persist_graph_shares([0.30, 0.30, 0.20, 0.20], updated_at=1000.0)
        s._persist_graph_shares(None, max_nodes=360, updated_at=2000.0)
        self.assertEqual(s._GRAPH_SHARES["shares"], [0.30, 0.30, 0.20, 0.20])
        self.assertEqual(s._GRAPH_SHARES["max_nodes"], 360)
        self.assertEqual(len(s._GRAPH_SHARES["history"]), 2)
        self.assertEqual(s._GRAPH_SHARES["history"][1]["max_nodes"], 360)

    def test_partial_update_only_shares_keeps_max_nodes(self):
        """Faqat ulushlar o'zgarsa — max_nodes buzilmaydi."""
        s = self.server
        s._persist_graph_shares([0.30, 0.30, 0.20, 0.20], max_nodes=300, updated_at=1000.0)
        s._persist_graph_shares([0.40, 0.20, 0.20, 0.20], updated_at=2000.0)
        self.assertEqual(s._GRAPH_SHARES["max_nodes"], 300)
        self.assertEqual(s._GRAPH_SHARES["shares"], [0.40, 0.20, 0.20, 0.20])

    def test_clamp_max_nodes_invalid(self):
        """Noto'g'ri/chegara tashqarisi max_nodes -> None (default 240)."""
        s = self.server
        self.assertEqual(s._clamp_max_nodes("300"), 300)
        self.assertEqual(s._clamp_max_nodes(300), 300)
        self.assertIsNone(s._clamp_max_nodes("abc"))
        self.assertIsNone(s._clamp_max_nodes("5"))       # juda kichik
        self.assertIsNone(s._clamp_max_nodes("99999"))   # juda katta
        self.assertIsNone(s._clamp_max_nodes("nan"))
        self.assertIsNone(s._clamp_max_nodes("inf"))  # OverflowError 500 bermasligi
        self.assertIsNone(s._clamp_max_nodes(None))

    def test_dedup_considers_max_nodes(self):
        """Dedup IKKALA qiymatni ko'radi — max_nodes o'zgarsa yangi yozuv kerak."""
        s = self.server
        s._persist_graph_shares([0.30, 0.30, 0.20, 0.20], max_nodes=240, updated_at=1000.0)
        s._persist_graph_shares([0.30, 0.30, 0.20, 0.20], max_nodes=240, updated_at=2000.0)
        self.assertEqual(len(s._GRAPH_SHARES["history"]), 1)  # bir xil — yozilmaydi
        s._persist_graph_shares([0.30, 0.30, 0.20, 0.20], max_nodes=300, updated_at=3000.0)
        self.assertEqual(len(s._GRAPH_SHARES["history"]), 2)  # max_nodes o'zgardi
        self.assertEqual(s._GRAPH_SHARES["history"][1]["max_nodes"], 300)

    def test_api_partial_max_nodes_update(self):
        """POST faqat max_nodes bilan — ulushlar o'zgarmaydi, javob ikkalasini qaytaradi."""
        from server import GraphSharesRequest
        s = self.server
        r1 = s.api_brain_shares_set(GraphSharesRequest(shares=[0.30, 0.30, 0.20, 0.20]))
        self.assertEqual(r1["max_nodes"], 240)  # default
        r2 = s.api_brain_shares_set(GraphSharesRequest(max_nodes=300))
        self.assertEqual(r2["max_nodes"], 300)
        self.assertEqual(r2["shares"], [0.30, 0.30, 0.20, 0.20])
        self.assertEqual(len(r2["history"]), 2)
        # Hech narsa berilmagan — o'zgarishsiz joriy holat
        r3 = s.api_brain_shares_set(GraphSharesRequest())
        self.assertEqual(r3["max_nodes"], 300)
        self.assertEqual(len(r3["history"]), 2)

    def test_history_accumulates_and_caps(self):
        s = self.server
        # Har safar TURLI qiymat (dedup qo'shilgani uchun takrorlar yozilmaydi)
        for i in range(s._GRAPH_SHARES_HISTORY_LIMIT + 5):
            s._persist_graph_shares(
                [0.1 + i * 0.01, 0.3, 0.2, 0.4 - i * 0.01], updated_at=1000.0 + i)
        self.assertEqual(len(s._GRAPH_SHARES["history"]), s._GRAPH_SHARES_HISTORY_LIMIT)
        # Eng eski yozuv tushib ketgan, eng yangisi qolgan
        self.assertEqual(s._GRAPH_SHARES["history"][0]["ts"], 1000.0 + 5)
        self.assertEqual(s._GRAPH_SHARES["updated_at"], 1000.0 + s._GRAPH_SHARES_HISTORY_LIMIT + 4)

    def test_legacy_format_backward_compatible(self):
        s = self.server
        # Eski format: faqat {shares: [...]} — max_nodes default, tarix bo'sh.
        with open(s._GRAPH_SHARES_FILE, "w", encoding="utf-8") as fh:
            fh.write('{"shares": [0.3, 0.3, 0.2, 0.2]}')
        self._reset_memory()
        s._load_graph_shares()
        self.assertEqual(s._GRAPH_SHARES["shares"], [0.3, 0.3, 0.2, 0.2])
        self.assertIsNone(s._GRAPH_SHARES["max_nodes"])
        self.assertEqual(s._GRAPH_SHARES["history"], [])

    def test_same_value_not_recorded_twice(self):
        s = self.server
        s._persist_graph_shares([0.30, 0.30, 0.20, 0.20], updated_at=1000.0)
        s._persist_graph_shares([0.30, 0.30, 0.20, 0.20], updated_at=2000.0)
        self.assertEqual(len(s._GRAPH_SHARES["history"]), 1)
        self.assertEqual(s._GRAPH_SHARES["updated_at"], 1000.0)

    def test_corrupt_history_entries_filtered(self):
        s = self.server
        with open(s._GRAPH_SHARES_FILE, "w", encoding="utf-8") as fh:
            fh.write('{"shares": [0.3, 0.3, 0.2, 0.2], "updated_at": 1, '
                     '"history": [{"ts": 1}, {"ts": 2, "shares": [0.4, 0.3, 0.2, 0.1]}]}')
        self._reset_memory()
        s._load_graph_shares()
        self.assertEqual(len(s._GRAPH_SHARES["history"]), 1)
        self.assertEqual(s._GRAPH_SHARES["history"][0]["shares"], [0.4, 0.3, 0.2, 0.1])

    def test_corrupt_file_falls_back_to_none(self):
        s = self.server
        with open(s._GRAPH_SHARES_FILE, "w", encoding="utf-8") as fh:
            fh.write("{not valid json")
        self._reset_memory()
        s._load_graph_shares()
        self.assertIsNone(s._GRAPH_SHARES["shares"])


class TestShareNormalization(unittest.TestCase):
    """normalize_shares — UI'dan kelgan ulushlar xavfsiz qayta ishlanadi."""

    def test_valid_shares_kept(self):
        self.assertEqual(normalize_shares([0.30, 0.30, 0.20, 0.20]),
                         [0.30, 0.30, 0.20, 0.20])

    def test_sum_normalized_to_one(self):
        out = normalize_shares([0.5, 0.5, 0.5, 0.5])  # yig'indi 2.0
        self.assertAlmostEqual(sum(out), 1.0)
        self.assertEqual(out, [0.25, 0.25, 0.25, 0.25])

    def test_wrong_length_returns_default(self):
        self.assertEqual(normalize_shares([0.5, 0.5]), DEFAULT_SHARES)
        self.assertEqual(normalize_shares([]), DEFAULT_SHARES)
        self.assertEqual(normalize_shares(None), DEFAULT_SHARES)

    def test_negative_and_zero_sanitized(self):
        out = normalize_shares([-0.5, 0.5, 0.5, 0.5])
        self.assertAlmostEqual(sum(out), 1.0)
        self.assertAlmostEqual(out[0], 0.0)

    def test_all_zero_returns_default(self):
        self.assertEqual(normalize_shares([0, 0, 0, 0]), DEFAULT_SHARES)

    def test_nan_inf_returns_default(self):
        # URL orqali 'nan'/'inf' yuborilsa — 500 emas, default ulushlar.
        self.assertEqual(normalize_shares([float("nan"), 0.5, 0.2, 0.3]), DEFAULT_SHARES)
        self.assertEqual(normalize_shares([float("inf"), 0.5, 0.2, 0.3]), DEFAULT_SHARES)

    def test_build_graph_accepts_custom_shares(self):
        # Custom ulushlar bilan graf quriladi (sinov: hamma node'lar sig'adi).
        g = build_graph(max_nodes=240, shares=[0.25, 0.25, 0.25, 0.25])
        self.assertTrue(g["ok"])
        self.assertLessEqual(len(g["nodes"]), 240)


class TestStableBlend(unittest.TestCase):
    """Kvotali blend — bitta manba o'ssa boshqalar siqilmaydi (churn = 0)."""

    SHARES = [0.35, 0.25, 0.20, 0.20]

    def _blend_ids(self, sources, max_nodes=240):
        out = _stable_blend(sources, max_nodes, self.SHARES)
        return [n["id"] for n in out]

    def test_all_fit_under_cap(self):
        # Har bir manba o'z kvotasidan kichik — hammasi kiradi.
        sources = [_mk_nodes(10, "v"), _mk_nodes(10, "c"),
                   _mk_nodes(10, "p"), _mk_nodes(10, "r")]
        ids = self._blend_ids(sources)
        self.assertEqual(len(ids), 40)
        # aralashtirilgan (blend): dastlabki bir nechta turli manbalardan
        for p in ("v:", "c:", "p:", "r:"):
            self.assertTrue(any(x.startswith(p) for x in ids[:6]), f"{p} dastlabki 6 ta ichida emas")

    def test_growth_does_not_evict_others(self):
        # baza: vault 100, chat 50, persistent 40, runtime 30 — chat kvota
        # (240*0.25=60) ichida.
        base_sources = [_mk_nodes(100, "v"), _mk_nodes(50, "c"),
                        _mk_nodes(40, "p"), _mk_nodes(30, "r")]
        base = set(self._blend_ids(base_sources))
        # chat 50 → 90 (kvotadan oshdi) — LEKIN boshqa manbalar bir xil qoladi.
        grown_sources = [_mk_nodes(100, "v"), _mk_nodes(90, "c"),
                         _mk_nodes(40, "p"), _mk_nodes(30, "r")]
        grown = set(self._blend_ids(grown_sources))
        others = lambda s: {x for x in s if not x.startswith("c:")}
        self.assertEqual(others(base), others(grown))
        # chat o'zi eng yangi 60 tasini saqlaydi (kvota)
        self.assertEqual(len({x for x in grown if x.startswith("c:")}), 60)

    def test_quota_caps_respected(self):
        # hamma manba juda katta — har biri o'z kvotasidan oshmaydi
        sources = [_mk_nodes(500, "v"), _mk_nodes(500, "c"),
                   _mk_nodes(500, "p"), _mk_nodes(500, "r")]
        out = _stable_blend(sources, 240, self.SHARES)
        self.assertLessEqual(len(out), 240)
        ids = [n["id"] for n in out]
        # eng yangilari saqlanadi: har manbadan `[-q:]`
        self.assertIn("v:499", ids)
        self.assertIn("c:499", ids)
        self.assertIn("p:499", ids)
        self.assertIn("r:499", ids)

    def test_small_cap_still_respected(self):
        out = _stable_blend([_mk_nodes(30, "v"), _mk_nodes(30, "c"),
                             _mk_nodes(30, "p"), _mk_nodes(30, "r")], 50, self.SHARES)
        self.assertLessEqual(len(out), 50)


class TestGraphVersionFingerprint(unittest.TestCase):
    """graph_version_fingerprint — FAQAT SEZILARLI o'zgarishlar versiyani siljitadi.

    2nd Brain live stream'ning asosiy sharti: L1 runtime append'lar va mavjud
    suhbatga xabarlar (shovqin) versiyani o'zgartirmaydi; yangi xotira fayli /
    L2 yozuv / yangi suhbat / o'chirilgan suhbat esa o'zgartiradi.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="igris_fp_")
        self.memory_root = os.path.join(self.tmp, "memory")
        self.brain_data = os.path.join(self.memory_root, "brain_data")
        os.makedirs(os.path.join(self.brain_data, "persistent"), exist_ok=True)
        os.makedirs(os.path.join(self.brain_data, "runtime"), exist_ok=True)
        # Vault .md (sezilarli manba)
        with open(os.path.join(self.memory_root, "L1 - Active Context.md"), "w",
                  encoding="utf-8") as fh:
            fh.write("# Active Context\n\nreal ma'lumotli mazmun...")
        # L2 persistent yozuv
        with open(os.path.join(self.brain_data, "persistent", "01-solution.jsonl"), "w",
                  encoding="utf-8") as fh:
            fh.write('{"id": "s1", "type": "solution-memory", "content": "yechim bir"}\n')
        # L1 runtime yozuv
        self.runtime_path = os.path.join(self.brain_data, "runtime", "01-short-turn.jsonl")
        with open(self.runtime_path, "w", encoding="utf-8") as fh:
            fh.write('{"id": "r1", "type": "short-turn", "content": "navbat bir"}\n')
        # Chat tarixi — bitta suhbat
        self.chat_path = os.path.join(self.tmp, "chat_history.jsonl")
        with open(self.chat_path, "w", encoding="utf-8") as fh:
            fh.write('{"id": "conv-aaa", "title": "Suhbat A", "updated_at": 1000, '
                     '"messages": [{"role": "user", "text": "salom", "ts": 1000}]}\n')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fp(self):
        return graph_version_fingerprint(self.memory_root, self.brain_data, self.chat_path)

    def test_deterministic(self):
        """Bir xil holat — har doim bir xil versiya (turg'un polling uchun)."""
        self.assertEqual(self._fp(), self._fp())

    def test_runtime_append_ignored(self):
        """L1 runtime'ga yozuv qo'shildi (chat davomidagi shovqin) — versiya o'zgarmaydi."""
        v1 = self._fp()
        with open(self.runtime_path, "a", encoding="utf-8") as fh:
            fh.write('{"id": "r2", "type": "short-turn", "content": "navbat ikki"}\n')
        self.assertEqual(self._fp(), v1)

    def test_new_runtime_file_changes_version(self):
        """Yangi xotira MODULI (fayl) paydo bo'ldi — sezilarli o'zgarish."""
        v1 = self._fp()
        with open(os.path.join(self.brain_data, "runtime", "03-new-module.jsonl"), "w",
                  encoding="utf-8") as fh:
            fh.write('{"id": "n1", "type": "session", "content": "yangi modul"}\n')
        v2 = self._fp()
        self.assertNotEqual(v2[0], v1[0])
        self.assertIsNotNone(v2[2])
        self.assertIn("yangi xotira moduli", v2[2])
        self.assertIn("03-new-module.jsonl", v2[2])

    def test_persistent_new_entry_changes_version(self):
        """L2 xotiraga yangi yozuv qo'shildi — grafda yangi node, versiya o'zgaradi."""
        v1 = self._fp()
        with open(os.path.join(self.brain_data, "persistent", "01-solution.jsonl"), "a",
                  encoding="utf-8") as fh:
            fh.write('{"id": "s2", "type": "solution-memory", "content": "yechim ikki"}\n')
        v2 = self._fp()
        self.assertNotEqual(v2[0], v1[0])
        self.assertIsNotNone(v2[2])
        self.assertIn("yangi L2 xotira yozuvi", v2[2])

    def test_chat_message_ignored_new_conversation_bumps(self):
        """Mavjud suhbatga xabar shovqin; yangi suhbat sezilarli."""
        v1 = self._fp()
        # Mavjud suhbatga javob qo'shildi — node to'plami bir xil (shovqin)
        with open(self.chat_path, "w", encoding="utf-8") as fh:
            fh.write('{"id": "conv-aaa", "title": "Suhbat A", "updated_at": 2000, '
                     '"messages": [{"role": "user", "text": "salom", "ts": 1000}, '
                     '{"role": "assistant", "text": "salom! qanday yordam kerak?", "ts": 2000}]}\n')
        self.assertEqual(self._fp(), v1)
        # Yangi suhbat ochildi — grafda yangi session node (sezilarli)
        with open(self.chat_path, "a", encoding="utf-8") as fh:
            fh.write('{"id": "conv-bbb", "title": "Suhbat B", "updated_at": 3000, '
                     '"messages": [{"role": "user", "text": "ikkinchi savol", "ts": 3000}]}\n')
        v2 = self._fp()
        self.assertNotEqual(v2[0], v1[0])
        self.assertIsNotNone(v2[2])
        self.assertIn("yangi suhbat", v2[2])

    def test_chat_rename_bumps(self):
        """Suhbat nomi o'zgarsa (rename) — versiya o'zgaradi (node sarlavhasi yangilanadi)."""
        v1 = self._fp()
        with open(self.chat_path, "w", encoding="utf-8") as fh:
            fh.write('{"id": "conv-aaa", "title": "Yangi nom", "updated_at": 1000, '
                     '"messages": [{"role": "user", "text": "salom", "ts": 1000}]}\n')
        v2 = self._fp()
        self.assertNotEqual(v2[0], v1[0])
        self.assertIsNotNone(v2[2])
        self.assertIn("suhbat nomi o'zgardi", v2[2])

    def test_reason_only_on_actual_change(self):
        """Sabab FAQAT o'zgarish bo'lgan qo'ng'iroqda keladi; keyingisi None."""
        _v, _s, reason1, _t = self._fp()
        self.assertIsNone(reason1)  # birinchi qo'ng'iroq — oldingi holat yo'q
        # O'zgarishsiz qo'ng'iroq — sabab ham yo'q
        _v, _s, reason2, _t = self._fp()
        self.assertIsNone(reason2)
        # Yangi xotira moduli → sabab keladi
        with open(os.path.join(self.brain_data, "runtime", "03-new-module.jsonl"), "w",
                  encoding="utf-8") as fh:
            fh.write('{"id": "n1", "type": "session", "content": "yangi modul"}\n')
        _v, _s, reason3, _t = self._fp()
        self.assertIsNotNone(reason3)
        # Keyingi qo'ng'iroq (o'zgarishsiz) — sabab yana None (eski emas)
        _v, _s, reason4, _t = self._fp()
        self.assertIsNone(reason4)

    def test_changed_at(self):
        """So'nggi o'zgarish vaqti: dastlab None, o'zgarishda belgilanadi,
        o'zgarishsiz poll'da eski vaqt saqlanadi (qachondan beri turg'un)."""
        _v, _s, _r, t1 = self._fp()
        self.assertIsNone(t1)  # hech qanday o'zgarish kuzatilmagan
        with open(os.path.join(self.brain_data, "runtime", "03-new-module.jsonl"), "w",
                  encoding="utf-8") as fh:
            fh.write('{"id": "n1", "type": "session", "content": "yangi modul"}\n')
        _v, _s, _r, t2 = self._fp()
        self.assertIsNotNone(t2)
        self.assertGreater(t2, 0)
        self.assertLessEqual(t2, time.time())  # kelajakda emas
        # O'zgarishsiz poll — vaqt o'zgarmaydi (eski saqlanadi)
        _v, _s, _r, t3 = self._fp()
        self.assertEqual(t2, t3)

    def test_new_vault_file_reason(self):
        """Yangi vault fayl — "yangi vault fayl" sababi."""
        self._fp()
        with open(os.path.join(self.memory_root, "L2 - Rules.md"), "w",
                  encoding="utf-8") as fh:
            fh.write("# Rules\n\nqoidalar mazmuni...")
        _v, _s, reason, _t = self._fp()
        self.assertIsNotNone(reason)
        self.assertIn("yangi vault fayl", reason)
        self.assertIn("L2 - Rules.md", reason)

    def test_tombstone_prune_no_false_bump(self):
        """Tombstone: yangi o'chirish — versiya o'zgaradi; eski yozuvlar
        tozalanishi (prune) — o'zgarmaydi (shovqinli reload bo'lmaydi)."""
        import json as _json
        tomb = self.chat_path + ".deleted.json"
        with open(tomb, "w", encoding="utf-8") as fh:
            _json.dump({"conv-old": 1000.0, "conv-mid": 2000.0, "conv-new": 3000.0}, fh)
        v1 = self._fp()
        # Prune: faqat eng ESKI tombstone olib tashlandi — max_ts (3000) o'zgarmaydi
        with open(tomb, "w", encoding="utf-8") as fh:
            _json.dump({"conv-mid": 2000.0, "conv-new": 3000.0}, fh)
        self.assertEqual(self._fp(), v1)
        # Yangi suhbat o'chirildi — max_ts oshadi, versiya o'zgaradi + sabab
        with open(tomb, "w", encoding="utf-8") as fh:
            _json.dump({"conv-mid": 2000.0, "conv-new": 3000.0, "conv-latest": 4000.0}, fh)
        v3 = self._fp()
        self.assertNotEqual(v3[0], v1[0])
        self.assertIsNotNone(v3[2])
        self.assertIn("suhbat o'chirildi", v3[2])

    def test_vault_edit_reason(self):
        """Vault fayl tahrirlansa — "yangilangan fayl" sababi."""
        self._fp()
        md = os.path.join(self.memory_root, "L1 - Active Context.md")
        now = time.time()
        # mtime'ni boshqa 5s bucket'ga o'tkazamiz (deterministik o'zgarish)
        os.utime(md, (now + 10, now + 10))
        _v, _s, reason, _t = self._fp()
        self.assertIsNotNone(reason)
        self.assertIn("yangilangan fayl", reason)
        self.assertIn("L1 - Active Context.md", reason)


class TestBrainGraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Repo holatiga bog'liq emas: Igris_Memory'da .md bo'lmasa ham
        # grafik "ok" qaytarishi kerak (bo'sh nodes bilan).
        cls.g = build_graph()

    def test_graph_builds(self):
        g = self.g
        self.assertTrue(g["ok"])
        self.assertIsInstance(g["nodes"], list)
        self.assertIsInstance(g["links"], list)

    def test_stats_consistent(self):
        g = self.g
        self.assertEqual(g["stats"]["nodes"], len(g["nodes"]))
        self.assertEqual(g["stats"]["links"], len(g["links"]))

    def test_node_shape(self):
        g = build_graph()
        for n in g["nodes"][:10]:
            self.assertIn("id", n)
            self.assertIn("label", n)
            self.assertIn("kind", n)
            self.assertIn("x", n)
            self.assertIn("y", n)
            self.assertIn(n["kind"], ("fact", "session", "pattern", "architecture"))

    def test_layout_in_bounds(self):
        g = build_graph()
        for n in g["nodes"]:
            self.assertGreaterEqual(n["x"], 0)
            self.assertGreaterEqual(n["y"], 0)
            self.assertLessEqual(n["x"], 620)
            self.assertLessEqual(n["y"], 380)

    def test_links_reference_existing_nodes(self):
        g = build_graph()
        ids = {n["id"] for n in g["nodes"]}
        for a, b in g["links"]:
            self.assertIn(a, ids)
            self.assertIn(b, ids)
            self.assertNotEqual(a, b)

    def test_kinds_cover_expected(self):
        g = build_graph()
        kinds = {n["kind"] for n in g["nodes"]}
        # kamida architecture (vault) va boshqa tur nodlari bor
        self.assertIn("architecture", kinds)

    def test_default_cap_240(self):
        # Yangi chegara: 240 node — eski 160'dan kengroq, kamroq churn.
        g = build_graph()
        self.assertLessEqual(len(g["nodes"]), 240)

    def test_chat_nodes_have_updated_at(self):
        # Suhbat node'lari oxirgi yangilanish vaqti bilan keladi (frontend
        # "qachon yangilangan"ni ko'rsatadi). Chat tarixi bo'lmasa o'tkazib
        # yuboriladi (repo holatiga bog'liq emas).
        g = build_graph()
        chats = [n for n in g["nodes"] if n["id"].startswith("chat:")]
        if not chats:
            self.skipTest("chat_history.jsonl bo'sh — vaqt tamg'asi tekshirilmadi")
        for n in chats:
            self.assertTrue(
                isinstance(n.get("updated_at"), (int, float))
                and n["updated_at"] > 0,
                f"chat node'ida updated_at yo'q: {n['id']}",
            )
        # updated_at kelajakda bo'lmasligi kerak (haqiqiy epoch vaqti) —
        # eskilik chegarasi qo'yilmaydi (foydalanuvchi kam suhbatlashishi mumkin).
        latest = max(chats, key=lambda n: n["updated_at"] or 0)
        self.assertLessEqual(latest["updated_at"], time.time() + 60,
                             f"updated_at kelajakda: {latest['label']}")

    def test_explicit_cap_respected(self):
        g = build_graph(max_nodes=100)
        self.assertLessEqual(len(g["nodes"]), 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
