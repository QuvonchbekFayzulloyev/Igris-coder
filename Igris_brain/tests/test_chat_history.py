"""
IGRIS BRAIN — Real Chat History tests
=====================================
- ChatHistory: add_message / list / persisting (JSONL round-trip)
- brain_graph: chat_history.jsonl'dagi suhbatlar 'session' node bo'lishi
  va semantic linklar orqali boshqa node'lar bilan bog'lanishi
"""

import json
import os
import sys
import tempfile
import time
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))
# brain_graph moduli endi 2nd_brain/backend/ da — shu yerdan ham importlanadi.
sys.path.insert(0, os.path.join(
    _test_dir, "..", "2nd_brain", "backend"))

from server.server import ChatHistory, _structure_fail_warning  # noqa: E402
from brain_graph import build_graph  # noqa: E402


class TestChatHistoryStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.h = ChatHistory(path=self.tmp.name)

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
            os.unlink(self.tmp.name + ".tmp")
        except OSError:
            pass

    def test_add_message_warning_stored_separately(self):
        """A2 — structure_check fail ogohlantirishi transcript'da ALOHIDA
        maydonda saqlanadi (xabar matnini ifloslantirmaydi — suhbat davom
        ettirilganda LLM konteksti toza qoladi)."""
        self.h.add_message("conv-w", "assistant", '{"a": 1',
                           warning="⚠️ Javob strukturasi tekshiruvdan o'tmadi")
        conv = self.h.get("conv-w")
        msg = conv["messages"][0]
        self.assertEqual(msg["warning"], "⚠️ Javob strukturasi tekshiruvdan o'tmadi")
        self.assertEqual(msg["text"], '{"a": 1')   # matn toza qoladi
        # warning berilmasa — field umuman yo'q (transcript minimal qoladi)
        self.h.add_message("conv-w", "user", "salom")
        user_msg = conv["messages"][1]
        self.assertNotIn("warning", user_msg)
        # JSONL round-trip: warning ham saqlanadi (qayta yuklanganda yo'qolmaydi)
        h2 = ChatHistory(path=self.tmp.name)
        msg2 = h2.get("conv-w")["messages"][0]
        self.assertEqual(msg2["warning"], "⚠️ Javob strukturasi tekshiruvdan o'tmadi")

    def test_structure_fail_warning_helper(self):
        """_structure_fail_warning: faqat ok=False (repair qilib bo'lmagan)
        structure_check ogohlantirish beradi; repaired/toza/yo'q — bo'sh."""
        fail = _structure_fail_warning(
            {"structure_check": {"ok": False, "kind": "json", "repaired": False}})
        self.assertTrue(fail.startswith("⚠️"))
        self.assertIn("strukturasi", fail)
        # repaired (ok=True) — ogohlantirish YO'Q (ta'mirlangan javob toza)
        self.assertEqual(
            _structure_fail_warning({"structure_check": {"ok": True, "repaired": True}}), "")
        # toza javob / structure_check yo'q / None — bo'sh
        self.assertEqual(_structure_fail_warning({"content": "toza javob"}), "")
        self.assertEqual(_structure_fail_warning({}), "")

    def test_add_message_creates_conversation(self):
        conv = self.h.add_message("conv-1", "user", "hello igris")
        self.assertEqual(conv["id"], "conv-1")
        self.assertEqual(conv["title"], "hello igris")
        self.assertEqual(len(conv["messages"]), 1)

    def test_add_message_appends_to_same_conversation(self):
        self.h.add_message("conv-1", "user", "hello")
        self.h.add_message("conv-1", "assistant", "hi there")
        result = self.h.list()
        self.assertEqual(len(result["conversations"]), 1)
        conv = result["conversations"][0]
        self.assertEqual(conv["messages"], 2)
        self.assertEqual(conv["title"], "hello")

    def test_list_sorted_by_recent(self):
        self.h.add_message("old", "user", "first")
        self.h.add_message("new", "user", "second")
        result = self.h.list()
        self.assertEqual(result["conversations"][0]["id"], "new")

    def test_persists_to_disk(self):
        self.h.add_message("conv-persist", "user", "saved message")
        # yangi instance (qayta yuklash) — diskdan o'qishi kerak
        h2 = ChatHistory(path=self.tmp.name)
        result = h2.list()
        self.assertEqual(len(result["conversations"]), 1)
        self.assertEqual(result["conversations"][0]["id"], "conv-persist")

    def test_broken_output_round_trip_keeps_file_valid(self):
        """A2 — transcript'ga repair qilib bo'lmagan buzilgan output (masalan
        `{'a': 1`) yozilsa ham JSONL fayl VALID qoladi: har bir qator
        json.loads bilan o'qiladi, qayta yuklashda matn + warning aniq
        tiklanadi, 2nd Brain grafi ham faylni xatosiz o'qiydi.

        JSON ichidagi xavfli belgilar (tirnoq, yangi qator, backslash, emoji)
        to'g'ri escape qilinishi kerak — bitta buzilgan satr butun tarix
        faylini o'qib bo'lmas qilmasligi kerak."""
        tricky = "{'a': 1} \n ikkinchi qator \"tirnoq\" \\ backslash ⚠️"
        self.h.add_message("conv-broken", "assistant", tricky,
                           warning="⚠️ Javob strukturasi tekshiruvdan o'tmadi")
        self.h.add_message("conv-broken", "user", "salom")

        # 1) Har bir JSONL qatori VALID JSON bo'lishi kerak (fayl buzilmaydi)
        with open(self.tmp.name, "r", encoding="utf-8") as fh:
            lines = [ln for ln in fh if ln.strip()]
        self.assertGreaterEqual(len(lines), 1)
        [json.loads(ln) for ln in lines]

        # 2) Round-trip: buzilgan matn + warning ANIQ tiklanadi (escape to'g'ri)
        h2 = ChatHistory(path=self.tmp.name)
        msgs = h2.get("conv-broken")["messages"]
        self.assertEqual(msgs[0]["text"], tricky)
        self.assertEqual(msgs[0]["warning"],
                         "⚠️ Javob strukturasi tekshiruvdan o'tmadi")

        # 3) 2nd Brain grafi faylni xatosiz o'qiydi — session node yaratiladi
        import brain_graph
        orig = brain_graph.CHAT_HISTORY_PATH
        try:
            brain_graph.CHAT_HISTORY_PATH = self.tmp.name
            nodes = brain_graph._scan_chat_history()
        finally:
            brain_graph.CHAT_HISTORY_PATH = orig
        self.assertTrue(any(n["id"] == "chat:conv-broken" for n in nodes),
                        "buzilgan matnli suhbat grafda session node bo'lishi kerak")

    def test_empty_returns_ok(self):
        result = self.h.list()
        self.assertTrue(result["ok"])
        self.assertEqual(result["conversations"], [])

    def test_message_cap_per_conversation(self):
        h = ChatHistory(path=self.tmp.name, max_messages=3)
        for i in range(10):
            h.add_message("conv-cap", "user", f"msg-{i}")
        result = h.list()
        conv = result["conversations"][0]
        self.assertEqual(conv["messages"], 3)  # eng so'nggi 3 ta qoladi
        # diskga ham faqat 3 ta yozilgan
        h2 = ChatHistory(path=self.tmp.name, max_messages=3)
        self.assertEqual(h2.list()["conversations"][0]["messages"], 3)

    def test_stale_tmp_cleaned_on_load(self):
        with open(self.tmp.name + ".tmp", "w", encoding="utf-8") as fh:
            fh.write('{"broken": true}\n')
        h = ChatHistory(path=self.tmp.name)
        self.assertFalse(os.path.exists(self.tmp.name + ".tmp"))

    # ---------------- Chat history actions (star / rename / delete / get) ---------------- #

    def test_get_returns_conversation(self):
        self.h.add_message("conv-get", "user", "salom")
        self.h.add_message("conv-get", "assistant", "assalom")
        conv = self.h.get("conv-get")
        self.assertIsNotNone(conv)
        self.assertEqual(conv["id"], "conv-get")
        self.assertEqual(len(conv["messages"]), 2)
        self.assertEqual(conv["messages"][0]["role"], "user")
        self.assertIsNone(self.h.get("conv-no-such"))

    def test_set_starred(self):
        self.h.add_message("conv-star", "user", "muhim savol")
        self.assertTrue(self.h.set_starred("conv-star", True))
        self.assertTrue(self.h.list()["conversations"][0]["starred"])
        self.assertTrue(self.h.set_starred("conv-star", False))
        self.assertFalse(self.h.list()["conversations"][0]["starred"])
        # mavjud bo'lmagan suhbat
        self.assertFalse(self.h.set_starred("conv-no-such", True))

    def test_rename(self):
        self.h.add_message("conv-ren", "user", "eski sarlavha")
        self.assertTrue(self.h.rename("conv-ren", "Yangi sarlavha"))
        self.assertEqual(self.h.list()["conversations"][0]["title"], "Yangi sarlavha")
        # bo'sh sarlavha qabul qilinmaydi
        self.assertFalse(self.h.rename("conv-ren", "   "))
        self.assertFalse(self.h.rename("conv-no-such", "x"))

    def test_delete(self):
        self.h.add_message("conv-del", "user", "o'chiriladi")
        self.h.add_message("conv-keep", "user", "qoladi")
        self.assertTrue(self.h.delete("conv-del"))
        result = self.h.list()
        self.assertEqual(len(result["conversations"]), 1)
        self.assertEqual(result["conversations"][0]["id"], "conv-keep")
        self.assertIsNone(self.h.get("conv-del"))
        self.assertFalse(self.h.delete("conv-del"))  # ikkinchi marta -> False
        # o'chirilgandan so'ng diskda ham yo'q
        h2 = ChatHistory(path=self.tmp.name)
        self.assertEqual(len(h2.list()["conversations"]), 1)

    def test_deleted_session_never_resurrects(self):
        """O'chirilgan suhbat id'iga keyinchalik xabar kelsa ham YANGI suhbat
        ochiladi — o'chirilgani qayta paydo bo'lmaydi (fon task tugasa ham)."""
        self.h.add_message("conv-gone", "user", "eski suhbat")
        self.assertTrue(self.h.delete("conv-gone"))
        # Eski session_id bilan yana xabar keladi (masalan fon task tugadi)
        self.h.add_message("conv-gone", "assistant", "task yakuni")
        result = self.h.list()
        self.assertEqual(len(result["conversations"]), 1)
        self.assertNotEqual(result["conversations"][0]["id"], "conv-gone")
        self.assertIsNone(self.h.get("conv-gone"))
        # Tombstone diskda saqlanadi — yangi instance ham o'chirilganini biladi
        self.assertTrue(os.path.exists(self.tmp.name + ".deleted.json"))
        h2 = ChatHistory(path=self.tmp.name)
        self.assertEqual(len(h2.list()["conversations"]), 1)
        self.assertNotEqual(h2.list()["conversations"][0]["id"], "conv-gone")

    def test_delete_is_idempotent_after_reload(self):
        """O'chirilgan suhbat yangi server instance'ida ham yo'q bo'ladi."""
        self.h.add_message("conv-x", "user", "salom")
        self.h.delete("conv-x")
        h2 = ChatHistory(path=self.tmp.name)
        # Yangi instance'da ham o'chirilgan suhbat yo'q
        self.assertIsNone(h2.get("conv-x"))
        # va unga yozilgan xabar uni qayta ochmaydi
        h2.add_message("conv-x", "user", "yangi xabar")
        self.assertIsNone(h2.get("conv-x"))
        self.assertEqual(len(h2.list()["conversations"]), 1)

    # ---------------- Tombstone pruning (fayl cheksiz o'smaydi) ---------------- #

    def test_tombstone_pruned_by_retention(self):
        """O'chirilgan id retention muddatidan eskirsa — tombstone'dan tushadi."""
        h = ChatHistory(path=self.tmp.name, tombstone_retention=60)
        h.add_message("conv-old", "user", "eski")
        h.delete("conv-old")
        self.assertIn("conv-old", h._deleted)
        # 61 soniya eski qilib qo'yamiz — keyingi saqlashda tozalanadi
        h._deleted["conv-old"] = time.time() - 61
        h._save_tombstones()
        self.assertNotIn("conv-old", h._deleted)
        # diskda ham yo'q
        with open(self.tmp.name + ".deleted.json", "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertNotIn("conv-old", data)

    def test_tombstone_capped_by_max_entries(self):
        """Eng ko'pi tombstone_max_entries ta yozuv qoladi (eng yangilari)."""
        h = ChatHistory(path=self.tmp.name, tombstone_max_entries=3)
        for i in range(10):
            h.add_message(f"conv-cap-{i}", "user", f"xabar {i}")
            h.delete(f"conv-cap-{i}")
        self.assertLessEqual(len(h._deleted), 3)
        # eng yangi 3 tasi qoladi (7, 8, 9)
        self.assertIn("conv-cap-7", h._deleted)
        self.assertIn("conv-cap-8", h._deleted)
        self.assertIn("conv-cap-9", h._deleted)
        with open(self.tmp.name + ".deleted.json", "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertLessEqual(len(data), 3)

    def test_tombstone_pruned_on_load(self):
        """Server restart'da eskirgan tombstone'lar avtomatik tozalanadi."""
        h = ChatHistory(path=self.tmp.name, tombstone_retention=60)
        h.add_message("conv-x", "user", "x")
        h.delete("conv-x")
        h._deleted["conv-x"] = time.time() - 120  # eskirgan
        h._save_tombstones()
        # yangi instance — yuklashda eskirgani tashlanadi
        h2 = ChatHistory(path=self.tmp.name, tombstone_retention=60)
        self.assertNotIn("conv-x", h2._deleted)
        # xotirada ham faylda ham yo'q
        with open(self.tmp.name + ".deleted.json", "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data, {})

    def test_multiple_deletes_all_persist_tombstones(self):
        """Ketma-ket o'chirilgan suhbatlarning IKKALA tombstone'i ham saqlanadi.

        Regression: avvalgi xato tartibda `delete` tombstone'ni `_persist`
        dan OLDIN qo'shar, `_persist` ichidagi reload esa uni o'chirib
        yuborar — faqat BIRINCHI o'chirish saqlanib qolardi.
        """
        self.h.add_message("conv-a", "user", "a")
        self.h.add_message("conv-b", "user", "b")
        self.assertTrue(self.h.delete("conv-a"))
        self.assertTrue(self.h.delete("conv-b"))
        # xotirada ham diskda ham ikkalasi bor
        self.assertIn("conv-a", self.h._deleted)
        self.assertIn("conv-b", self.h._deleted)
        with open(self.tmp.name + ".deleted.json", "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIn("conv-a", data)
        self.assertIn("conv-b", data)
        # yangi instance ham ikkalasini ham biladi — hech biri qaytib kelmaydi
        h2 = ChatHistory(path=self.tmp.name)
        for cid in ("conv-a", "conv-b"):
            self.assertIsNone(h2.get(cid))
            h2.add_message(cid, "user", "tiriltirish urinishi")
            self.assertIsNone(h2.get(cid))
        # (add_message o'chirilgan id'ga YANGI suhbat ochadi — eski id'lar yo'q)
        ids = [c["id"] for c in h2.list()["conversations"]]
        self.assertNotIn("conv-a", ids)
        self.assertNotIn("conv-b", ids)

    def test_pruned_tombstone_written_back_to_disk(self):
        """Yuklashda tozalangan tombstone'lar FAYLDAN ham o'chiriladi.

        Aks holda eskirgan yozuv faylda qolib, server `add_message` uni
        xotiradan olib tashlagan bo'lsa ham graf hali eski faylni o'qib
        yangidan ochilgan suhbatni yashirib qo'yishi mumkin edi.
        """
        h = ChatHistory(path=self.tmp.name, tombstone_retention=60)
        h.add_message("conv-exp", "user", "x")
        h.delete("conv-exp")
        h._deleted["conv-exp"] = time.time() - 120  # eskirgan
        h._save_tombstones()
        # faylga eskirgan yozuvni qo'lda tiklaymiz (tozalashsiz holat)
        with open(self.tmp.name + ".deleted.json", "w", encoding="utf-8") as fh:
            json.dump({"conv-exp": time.time() - 120}, fh)
        # yangi instance yuklaganda eskirgani tozalanadi VA fayl yangilanadi
        h2 = ChatHistory(path=self.tmp.name, tombstone_retention=60)
        self.assertNotIn("conv-exp", h2._deleted)
        with open(self.tmp.name + ".deleted.json", "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertNotIn("conv-exp", data)


class TestChatHistoryInGraph(unittest.TestCase):
    def setUp(self):
        # chat_history.jsonl'ni vaqtinchalik faylga yo'naltiramiz
        fd, self.tmp_path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        convs = [
            {
                "id": "conv-graph-1",
                "title": "RAG recall metodikasi",
                "updated_at": 1000.0,
                "messages": [
                    {"role": "user", "text": "RAG recall memory retrieval qanday ishlaydi?"},
                    {"role": "assistant", "text": "Retrieval pipeline runtime persistent xotiradan agent kontekst yig'adi."},
                ],
            },
            {
                "id": "conv-graph-2",
                "title": "2nd Brain grafi",
                "updated_at": 2000.0,
                "messages": [
                    {"role": "user", "text": "Grafga real chat tarixini agent memory skill bilan qo'sh"},
                    {"role": "assistant", "text": "Chat suhbatlari session node bo'ladi va planning bilan bog'lanadi."},
                ],
            },
        ]
        with open(self.tmp_path, "w", encoding="utf-8") as fh:
            for c in convs:
                fh.write(json.dumps(c, ensure_ascii=False) + "\n")

        import brain_graph
        self._orig = brain_graph.CHAT_HISTORY_PATH
        self._orig_tomb = getattr(brain_graph, "CHAT_HISTORY_TOMB_PATH", None)
        brain_graph.CHAT_HISTORY_TOMB_PATH = self.tmp_path + ".deleted.json"
        brain_graph.CHAT_HISTORY_PATH = self.tmp_path

    def tearDown(self):
        import brain_graph
        brain_graph.CHAT_HISTORY_PATH = self._orig
        # Tombstone path ham asliga qaytariladi — aks holda keyingi test
        # (bir xil id'larni qayta ishlatadigan) eski tombstone'dan ta'sirlanadi.
        if hasattr(self, "_orig_tomb") and self._orig_tomb is not None:
            brain_graph.CHAT_HISTORY_TOMB_PATH = self._orig_tomb
        try:
            os.unlink(self.tmp_path)
            os.unlink(self.tmp_path + ".deleted.json")
        except OSError:
            pass

    def test_chat_sessions_become_nodes(self):
        g = build_graph(max_nodes=160)
        chat_nodes = [n for n in g["nodes"] if n["id"].startswith("chat:")]
        self.assertEqual(len(chat_nodes), 2)
        for n in chat_nodes:
            self.assertEqual(n["kind"], "session")
            self.assertIn("label", n)
            self.assertIn("x", n)
            self.assertIn("y", n)

    def test_stats_include_chat_sessions(self):
        g = build_graph(max_nodes=160)
        self.assertGreaterEqual(g["stats"]["chat_sessions"], 2)

    def test_chat_nodes_are_linked(self):
        g = build_graph(max_nodes=160)
        chat_ids = {n["id"] for n in g["nodes"] if n["id"].startswith("chat:")}
        linked = set()
        for a, b in g["links"]:
            if a in chat_ids or b in chat_ids:
                linked.add(a)
                linked.add(b)
        # chat node'lari semantic linklar orqali grafga bog'langan bo'lishi kerak
        self.assertTrue(linked & chat_ids)

    def test_no_history_file_ok(self):
        import brain_graph
        brain_graph.CHAT_HISTORY_PATH = os.path.join(tempfile.gettempdir(), "no-such-chat-history.jsonl")
        brain_graph.CHAT_HISTORY_TOMB_PATH = brain_graph.CHAT_HISTORY_PATH + ".deleted.json"
        g = build_graph()
        self.assertTrue(g["ok"])
        chat_nodes = [n for n in g["nodes"] if n["id"].startswith("chat:")]
        self.assertEqual(chat_nodes, [])

    def test_deleted_chat_session_node_removed_from_graph(self):
        """Suhbat o'chirilgach — 2nd Brain grafigidagi session node ham yo'qoladi.

        Tombstone fayl (chat_history.jsonl.deleted.json) mavjud bo'lsa, graf
        o'chirilgan suhbatni node qilib qo'shmaydi — hatto suhbat asl JSONL
        faylida qolgan bo'lsa ham (stale jarayon holati).
        """
        import brain_graph
        # Tombstone: conv-graph-1 o'chirilgan deb belgilaymiz (faylda turibdi)
        with open(brain_graph.CHAT_HISTORY_TOMB_PATH, "w", encoding="utf-8") as fh:
            json.dump({"conv-graph-1": 1000.0}, fh)
        g = build_graph(max_nodes=160)
        chat_nodes = [n for n in g["nodes"] if n["id"].startswith("chat:")]
        chat_ids = [n["id"] for n in chat_nodes]
        self.assertNotIn("chat:conv-graph-1", chat_ids)
        self.assertIn("chat:conv-graph-2", chat_ids)
        self.assertLess(g["stats"]["chat_sessions"], 2)

    def test_legacy_list_tombstone_format_still_works(self):
        """Eski tombstone format (id'lar ro'yxati) ham o'qiladi."""
        import brain_graph
        with open(brain_graph.CHAT_HISTORY_TOMB_PATH, "w", encoding="utf-8") as fh:
            json.dump(["conv-graph-1"], fh)
        g = build_graph(max_nodes=160)
        chat_ids = [n["id"] for n in g["nodes"] if n["id"].startswith("chat:")]
        self.assertNotIn("chat:conv-graph-1", chat_ids)
        self.assertIn("chat:conv-graph-2", chat_ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
