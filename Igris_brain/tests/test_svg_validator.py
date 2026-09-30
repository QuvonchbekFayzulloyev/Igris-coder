"""svg_validator uchun unit testlar."""
import json
import os
import sys
import tempfile
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from verification.svg_validator import (  # noqa: E402
    DEFAULT_DIR,
    read_svg_metadata,
    validate_svg_file,
    validate_svg_text,
)
from agent.igris_agent import IgrisAgent, _drawing_quality_tip  # noqa: E402
from verification.svg_quality_report import (  # noqa: E402
    build_report,
    format_report,
    load_quality_entries,
    parse_quality_entry,
)


class _FakeMemory:
    """remember() chaqiruvlarini yozib oladigan MemoryBridge stub'u."""

    def __init__(self):
        self.enabled = True
        self.calls: list[dict] = []

    def remember(self, content, memory_type="solution-memory", tags=None, summary=""):
        self.calls.append({
            "content": content, "memory_type": memory_type,
            "tags": tags or [], "summary": summary,
        })


def _svg(body: str, tag: str = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">',
         extra: str = "") -> str:
    return tag + extra + body + "</svg>"


class TestReadMetadata(unittest.TestCase):
    def test_viewbox_and_comments(self):
        svg = _svg("<rect width='512' height='512' fill='#eee'/>",
                   extra="\n<!-- style: realistic -->\n<!-- size: 1080x1920 -->")
        meta = read_svg_metadata(svg)
        self.assertEqual(meta["viewBox"], (0, 0, 512, 512))
        self.assertEqual(meta["style_comment"], "realistic")
        self.assertEqual(meta["size_comment"], "1080x1920")

    def test_style_unknown_ignored(self):
        meta = read_svg_metadata("<!-- style: neon-punk --><svg viewBox='0 0 10 10'></svg>")
        self.assertIsNone(meta["style_comment"])

    def test_no_metadata(self):
        meta = read_svg_metadata("<svg></svg>")
        self.assertIsNone(meta["viewBox"])
        self.assertIsNone(meta["size_comment"])


class TestValidateText(unittest.TestCase):
    def test_invalid_document(self):
        r = validate_svg_text("bu rasm emas")
        self.assertEqual(r["verdict"], "noto'g'ri fayl")
        self.assertEqual(r["total"], 0)

    def test_missing_viewbox(self):
        r = validate_svg_text("<svg><rect width='100' height='100'/></svg>")
        self.assertEqual(r["verdict"], "viewBox yo'q")

    def test_good_cartoon(self):
        # Fon birinchi, markazlashgan mavzu, kontur, 10+ element
        parts = [
            "<rect width='512' height='512' fill='#f4f1ea'/>",
            "<circle cx='256' cy='256' r='150' fill='#ffd98e' stroke='#8a5a2b' stroke-width='5' stroke-linejoin='round'/>",
            "<circle cx='200' cy='200' r='18' fill='#2b2b2b'/>",
            "<circle cx='312' cy='200' r='18' fill='#2b2b2b'/>",
            "<circle cx='206' cy='194' r='6' fill='#ffffff'/>",
            "<circle cx='318' cy='194' r='6' fill='#ffffff'/>",
            "<path d='M210 300 Q256 360 302 300' fill='none' stroke='#8a5a2b' stroke-width='5' stroke-linecap='round'/>",
            "<ellipse cx='256' cy='420' rx='120' ry='16' fill='rgba(0,0,0,0.12)'/>",
            "<rect x='140' y='430' width='70' height='60' fill='#e0435f'/>",
            "<rect x='302' y='430' width='70' height='60' fill='#e0435f'/>",
        ]
        r = validate_svg_text(_svg("".join(parts)))
        self.assertGreaterEqual(r["total"], 60, f"yaxshi cartoon balli past: {r}")
        self.assertEqual(r["scores"]["composition"], 25)
        self.assertEqual(r["meta"]["viewBox"], (0, 0, 512, 512))

    def test_flat_with_gradient_penalized(self):
        # flat uslub izohi bor, lekin gradient ishlatilgan -> moslik past
        parts = [
            "<defs><linearGradient id='g'><stop offset='0' stop-color='#ff0'/>"
            "<stop offset='1' stop-color='#f00'/></linearGradient></defs>",
            "<rect width='512' height='512' fill='#ffffff'/>",
            "<rect x='100' y='100' width='300' height='300' fill='url(#g)'/>",
        ]
        r = validate_svg_text(_svg("".join(parts),
                                   extra="\n<!-- style: flat -->"))
        comp = next(c for c in r["checks"] if c["name"] == "uslub mosligi")
        self.assertFalse(comp["ok"])  # flat + gradient -> mos emas

    def test_realistic_compliance(self):
        parts = [
            "<defs><linearGradient id='sky'><stop offset='0' stop-color='#87CEEB'/>"
            "<stop offset='1' stop-color='#1E90FF'/></linearGradient></defs>",
            "<filter id='soft'><feDropShadow dx='0' dy='6' stdDeviation='6'/></filter>",
            "<rect width='512' height='512' fill='#eef4fb'/>",
            "<circle cx='256' cy='256' r='150' fill='url(#sky)' filter='url(#soft)'/>",
            "<ellipse cx='256' cy='430' rx='100' ry='14' fill='rgba(0,0,0,0.14)'/>",
        ]
        r = validate_svg_text(_svg("".join(parts), extra="\n<!-- style: realistic -->"))
        comp = next(c for c in r["checks"] if c["name"] == "uslub mosligi")
        self.assertTrue(comp["ok"])

    def test_centered_and_not_overflowing(self):
        # chap burchakka surilgan kichik kontent -> kompozitsiya past
        parts = ["<rect width='512' height='512' fill='#f4f1ea'/>",
                 "<circle cx='40' cy='40' r='20' fill='#333'/>"]
        r = validate_svg_text(_svg("".join(parts)))
        self.assertLess(r["scores"]["composition"], 25)

    def test_overflow_detected(self):
        parts = ["<rect width='512' height='512' fill='#f4f1ea'/>",
                 "<circle cx='600' cy='600' r='150' fill='#333'/>"]
        r = validate_svg_text(_svg("".join(parts)))
        self.assertLess(r["scores"]["structure"], 25)
        bad = [c["name"] for c in r["checks"] if c["name"] == "chegara" and not c["ok"]]
        self.assertEqual(bad, ["chegara"])

    def test_size_comment_mismatch(self):
        svg = _svg("<rect width='512' height='512' fill='#eee'/>",
                   extra="\n<!-- size: 1080x1920 -->")
        r = validate_svg_text(svg)
        self.assertFalse(r["size_consistency"])

    def test_relative_path_bbox(self):
        # Relative komandali path (m/c/s — kichik harflar) markazda chizilgan
        # bo'lsa ham bbox to'g'ri hisoblanadi (mutlaq emas, delta qo'shiladi).
        parts = [
            "<rect width='512' height='512' fill='#f4f1ea'/>",
            "<path d='M200 200 c0 100 112 100 112 0 s-112 -100 -112 0z' fill='#e0435f'/>",
            "<circle cx='256' cy='256' r='10' fill='#333'/>",
        ]
        r = validate_svg_text(_svg("".join(parts)))
        # path markazda (200..312 x, 200..300 y) + doira — bbox markazga yaqin
        self.assertGreaterEqual(r["scores"]["composition"], 18)

    def test_rescaled_poster_content_transform(self):
        # draw_custom_svg size-rescale: 512x512 shablon 1080x1920 poster'ga
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" '
               'viewBox="0 0 1080 1920">\n<!-- style: realistic -->\n<!-- size: 1080x1920 -->\n'
               "<g transform=\"translate(0.00 420.00) scale(2.10938)\">\n"
               "<rect width='512' height='512' fill='#e0435f'/>\n"
               "<circle cx='256' cy='256' r='120' fill='#fff'/>\n"
               "</g>\n</svg>")
        r = validate_svg_text(svg)
        self.assertTrue(r["size_consistency"])
        self.assertEqual(r["meta"]["viewBox"], (0, 0, 1080, 1920))
        # kontent transform'ga qo'llangach markazda turadi (kompozitsiya ishlaydi)
        self.assertGreaterEqual(r["scores"]["composition"], 15)


class TestValidateFile(unittest.TestCase):
    def test_file_roundtrip(self):
        svg = _svg("<rect width='512' height='512' fill='#f4f1ea'/>"
                   "<circle cx='256' cy='256' r='100' fill='#e0435f'/>")
        with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(svg)
            path = fh.name
        try:
            r = validate_svg_file(path)
            self.assertEqual(r["path"], path)
            self.assertGreaterEqual(r["total"], 50)
        finally:
            os.unlink(path)

    def test_missing_file(self):
        r = validate_svg_file(os.path.join(DEFAULT_DIR, "nope_xyz.svg"))
        self.assertIn("error", r)

    def test_corrupt_file_does_not_crash(self):
        # Buzilgan fayl (noldan boshlanuvchi bytlar) skanerni qulatmasligi kerak
        with tempfile.NamedTemporaryFile("wb", suffix=".svg", delete=False) as fh:
            fh.write(b"\x00\x01\x02 <svg not really valid")
            path = fh.name
        try:
            r = validate_svg_file(path)  # qulash bo'lmasligi kerak
            # yo error maydoni, yo 'noto'g'ri fayl' verdikti — ikkalasi ham xavfsiz
            self.assertTrue("error" in r or r.get("verdict") == "noto'g'ri fayl", r)
        finally:
            os.unlink(path)

    def test_json_output(self):
        svg = _svg("<rect width='512' height='512' fill='#f4f1ea'/>"
                   "<circle cx='256' cy='256' r='100' fill='#e0435f'/>")
        with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(svg)
            path = fh.name
        out = os.path.join(tempfile.gettempdir(), "validator_test.json")
        try:
            from verification.svg_validator import main
            code = main([path, "--json", out])
            self.assertEqual(code, 0)
            with open(out, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(len(data), 1)
            self.assertIn("total", data[0])
            self.assertEqual(data[0]["path"], path)
        finally:
            os.unlink(path)
            if os.path.exists(out):
                os.unlink(out)


class TestQualityReport(unittest.TestCase):
    """svg_quality_report: L2 yozuvlarini parslash va yig'ish."""

    def _entry(self, score, style="cartoon", weak=None, file="a.svg"):
        weak_s = ", ".join(weak) if weak else "yo'q"
        return {"content": (
            f"CHIZMA SIFATI (svg_validator auto-assessment): prompt='x' | file={file} | "
            f"viewBox=(0,0,512,512) | style={style} | size=standard | "
            f"score={score}/100 (yaxshi) | structure=20 composition=20 style=10 palette=10 | "
            f"zaif jihatlar: {weak_s}"),
            "remembered_at": "2026-08-07T10:00:00", "type": "solution-memory"}

    def test_parse_quality_entry(self):
        e = parse_quality_entry(self._entry(70, "realistic", ["gradient", "soya"]))
        self.assertEqual(e["score"], 70)
        self.assertEqual(e["style"], "realistic")
        self.assertEqual(e["weak"], ["gradient", "soya"])
        self.assertIn("remembered_at", e)
        self.assertIsNone(parse_quality_entry({"content": "Q: salom A: Salom"}))

    def test_parse_weak_stops_before_taklif(self):
        # taklif qismi zaifliklar ro'yxatiga aralashmasligi kerak
        content = ("CHIZMA SIFATI (svg_validator auto-assessment): prompt='x' | "
                   "file=a.svg | style=realistic | score=60/100 (yaxshi) | "
                   "zaif jihatlar: gradient, soya | taklif: asosiy tanaga "
                   "gradient qo'shish; yumshoq soya (feDropShadow)")
        e = parse_quality_entry({"content": content})
        self.assertEqual(e["weak"], ["gradient", "soya"])

    def test_build_report_aggregates(self):
        entries = [
            parse_quality_entry(self._entry(50, "cartoon", ["gradient"])),
            parse_quality_entry(self._entry(80, "cartoon", ["soya"])),
            parse_quality_entry(self._entry(90, "realistic", ["gradient", "soya"])),
            parse_quality_entry(self._entry(70, "flat", [])),
        ]
        r = build_report(entries)
        self.assertEqual(r["count"], 4)
        self.assertEqual(r["min_score"], 50)
        self.assertEqual(r["max_score"], 90)
        self.assertEqual(r["avg_score"], 72.5)
        self.assertEqual(r["weak_histogram"]["gradient"], 2)
        self.assertEqual(r["weak_histogram"]["soya"], 2)
        self.assertEqual(r["style_scores"]["cartoon"]["count"], 2)
        self.assertEqual(len(r["trend"]), 4)
        text = format_report(r)
        self.assertIn("O'rtacha: 72.5/100", text)
        self.assertIn("gradient (2x)", text)

    def test_load_from_dir_and_empty(self):
        mem = tempfile.mkdtemp()
        os.makedirs(os.path.join(mem, "persistent"))
        with open(os.path.join(mem, "persistent", "07-solution.jsonl"), "w",
                  encoding="utf-8") as fh:
            fh.write(json.dumps(self._entry(60)) + "\n")
            fh.write(json.dumps({"content": "oddiy yozuv"}) + "\n")
        entries = load_quality_entries(mem)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["score"], 60)
        self.assertEqual(load_quality_entries("/nonexistent_dir"), [])


class TestAgentIntegration(unittest.TestCase):
    """Agent'ga ulanish: chizish tugagach sifat L2 xotiraga yoziladi."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.svg_name = "test_drawing.svg"
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">\n'
               '<!-- style: realistic -->\n<!-- size: 512x512 -->\n'
               "<defs><linearGradient id='g'><stop offset='0' stop-color='#eee'/>"
               "<stop offset='1' stop-color='#ccc'/></linearGradient></defs>"
               "<rect width='512' height='512' fill='#eef4fb'/>"
               "<circle cx='256' cy='256' r='120' fill='url(#g)'/></svg>")
        with open(os.path.join(self.tmp, self.svg_name), "w", encoding="utf-8") as fh:
            fh.write(svg)
        self.agent = IgrisAgent(use_llm=False, memory_enabled=False,
                                workspace_root=self.tmp)
        self.fake = _FakeMemory()
        self.agent.memory = self.fake

    def test_remember_writes_l2_entry(self):
        self.agent._remember_drawing_quality(self.svg_name, "realistik olma chiz")
        self.assertEqual(len(self.fake.calls), 1)
        call = self.fake.calls[0]
        self.assertEqual(call["memory_type"], "solution-memory")
        self.assertIn("CHIZMA SIFATI", call["content"])
        self.assertIn("score=", call["content"])
        self.assertIn("realistic", call["tags"])
        self.assertIn("svg-quality", call["tags"])
        self.assertIn("summary", call)

    def test_remember_skips_non_svg_and_none(self):
        self.agent._remember_drawing_quality(None, "x")
        self.agent._remember_drawing_quality("pic.png", "x")
        self.agent._remember_drawing_quality("", "x")
        self.assertEqual(self.fake.calls, [])

    def test_remember_missing_file_silent(self):
        self.agent._remember_drawing_quality("nope_missing.svg", "x")
        self.assertEqual(self.fake.calls, [])  # qulash bo'lmasligi kerak

    def test_remember_memory_disabled(self):
        mem = _FakeMemory()
        mem.enabled = False
        self.agent.memory = mem
        self.agent._remember_drawing_quality(self.svg_name, "x")
        self.assertEqual(mem.calls, [])

    def test_quality_tip_realistic_missing_gradient(self):
        parts = ["<rect width='512' height='512' fill='#f4f1ea'/>",
                 "<circle cx='256' cy='256' r='100' fill='#e0435f'/>"]
        r = validate_svg_text(_svg("".join(parts), extra="\n<!-- style: realistic -->"))
        tip = _drawing_quality_tip(r)
        self.assertIn("gradient", tip)
        self.assertIn("soya", tip)

    def test_quality_tip_flat_rule_reminder(self):
        parts = ["<defs><linearGradient id='g'><stop offset='0' stop-color='#ff0'/>"
                 "<stop offset='1' stop-color='#f00'/></linearGradient></defs>",
                 "<rect width='512' height='512' fill='#ffffff'/>",
                 "<rect x='100' y='100' width='300' height='300' fill='url(#g)'/>"]
        r = validate_svg_text(_svg("".join(parts), extra="\n<!-- style: flat -->"))
        tip = _drawing_quality_tip(r)
        self.assertIn("flat", tip)  # flat qoidasi (gradient/soya YO'Q) eslatiladi
        # ZID maslahat bo'lmasligi kerak: gradient 'qo'shish' deyilmaydi
        self.assertNotIn("qo'shish", tip)

    def test_quality_tip_compliant_flat_gets_no_add_gradient(self):
        # TO'G'RI flat chizma (gradient/soya YO'Q) — 'qo'shish' taklifi berilmaydi
        parts = ["<rect width='512' height='512' fill='#f4f1ea'/>",
                 "<rect x='156' y='156' width='200' height='200' fill='#e0435f'/>",
                 "<rect x='206' y='206' width='100' height='100' fill='#2b2b2b'/>"]
        r = validate_svg_text(_svg("".join(parts), extra="\n<!-- style: flat -->"))
        tip = _drawing_quality_tip(r)
        self.assertNotIn("gradient qo'shish", tip)
        self.assertNotIn("soya", tip)

    def test_feedback_context_reads_l2(self):
        # temp xotira papkasida CHIZMA SIFATI yozuvlari bo'lgan fayl
        mem = tempfile.mkdtemp()
        os.makedirs(os.path.join(mem, "persistent"))
        with open(os.path.join(mem, "persistent", "07-solution.jsonl"), "w",
                  encoding="utf-8") as fh:
            fh.write(json.dumps({"content": "Q: salom A: Salom", "type": "x"}) + "\n")
            fh.write(json.dumps({"content": (
                "CHIZMA SIFATI (svg_validator auto-assessment): prompt='olma chiz' | "
                "file=a.svg | viewBox=(0,0,512,512) | style=realistic | size=standard | "
                "score=60/100 (yaxshi) | structure=20 composition=20 style=10 palette=10 | "
                "zaif jihatlar: gradient, soya")}) + "\n")
            fh.write(json.dumps({"content": (
                "CHIZMA SIFATI (svg_validator auto-assessment): prompt='mushuk chiz' | "
                "file=b.svg | style=cartoon | score=40/100 (o'rta) | "
                "zaif jihatlar: gradient")}) + "\n")
        agent = IgrisAgent(use_llm=False)
        agent.memory = type("M", (), {"base_dir": mem})()
        fb = agent._draw_feedback_context()
        self.assertIn("RECENT DRAWING QUALITY FEEDBACK", fb)
        self.assertIn("gradient", fb)  # zaifliklar in'ektsiyasi
        self.assertIn("2x", fb)        # eng ko'p takrorlangan zaiflik hisobi
        # CHIZMA SIFATI bo'lmagan yozuvlar in'ektsiyaga kirmaydi
        self.assertNotIn("Q: salom", fb)

    def test_feedback_context_empty(self):
        agent = IgrisAgent(use_llm=False)
        agent.memory = type("M", (), {"base_dir": "/nonexistent_dir_xyz"})()
        self.assertEqual(agent._draw_feedback_context(), "")

    def test_redraw_triggers_and_keeps_better(self):
        ws = tempfile.mkdtemp()
        # past ball chizma (burchakdagi kichkina nuqta) va yaxshi chizma
        with open(os.path.join(ws, "bad.svg"), "w", encoding="utf-8") as fh:
            fh.write(_svg("<rect width='512' height='512' fill='#f4f1ea'/>"
                          "<circle cx='10' cy='10' r='5' fill='#333'/>"))
        with open(os.path.join(ws, "good.svg"), "w", encoding="utf-8") as fh:
            fh.write(_svg("<rect width='512' height='512' fill='#f4f1ea'/>"
                          "<circle cx='256' cy='256' r='120' fill='#e0435f'"
                          " stroke='#8a5a2b' stroke-width='5' stroke-linejoin='round'/>"
                          "<ellipse cx='256' cy='420' rx='100' ry='14' fill='rgba(0,0,0,0.14)'/>"
                          "<circle cx='210' cy='220' r='14' fill='#2b2b2b'/>"
                          "<circle cx='302' cy='220' r='14' fill='#2b2b2b'/>"))
        agent = IgrisAgent(use_llm=False, workspace_root=ws)
        calls = []

        def fake_chat_with_tools(messages, tools, **kwargs):
            calls.append(messages)
            if len(calls) == 1:
                return "birinchi xulosa", [{"tool": "art__draw_custom_svg"}], "bad.svg"
            return "ikkinchi xulosa", [{"tool": "art__draw_custom_svg"}], "good.svg"

        agent._chat_with_tools = fake_chat_with_tools
        content, tool_calls, image, note = agent._chat_with_redraw(
            [{"role": "user", "content": "olma chizib ber"}], [], request="olma chizib ber")
        self.assertEqual(len(calls), 2)
        self.assertEqual(image, "good.svg")
        self.assertEqual(content, "ikkinchi xulosa")
        self.assertTrue(note["retried"])
        self.assertLess(note["old_score"], note["new_score"])
        self.assertIn("gradient", " ".join(str(m) for m in calls[1]))  # tanqid bor

    def test_redraw_skipped_when_score_ok(self):
        ws = tempfile.mkdtemp()
        with open(os.path.join(ws, "good.svg"), "w", encoding="utf-8") as fh:
            fh.write(_svg("<rect width='512' height='512' fill='#f4f1ea'/>"
                          "<circle cx='256' cy='256' r='120' fill='#e0435f'"
                          " stroke='#8a5a2b' stroke-width='5' stroke-linejoin='round'/>"
                          "<ellipse cx='256' cy='420' rx='100' ry='14' fill='rgba(0,0,0,0.14)'/>"
                          "<circle cx='210' cy='220' r='14' fill='#2b2b2b'/>"
                          "<circle cx='302' cy='220' r='14' fill='#2b2b2b'/>"))
        agent = IgrisAgent(use_llm=False, workspace_root=ws)
        calls = []

        def fake_chat_with_tools(messages, tools, **kwargs):
            calls.append(1)
            return "xulosa", [{"tool": "art__draw_custom_svg"}], "good.svg"

        agent._chat_with_tools = fake_chat_with_tools
        _, _, image, note = agent._chat_with_redraw(
            [{"role": "user", "content": "olma chiz"}], [], request="olma chiz")
        self.assertEqual(len(calls), 1)      # qayta chizish YO'Q
        self.assertIsNone(note)
        self.assertEqual(image, "good.svg")

    def test_redraw_skipped_non_draw_request(self):
        agent = IgrisAgent(use_llm=False)
        calls = []

        def fake_chat_with_tools(messages, tools, **kwargs):
            calls.append(1)
            return "xulosa", [{"tool": "art__draw_custom_svg"}], "b.svg"

        agent._chat_with_tools = fake_chat_with_tools
        _, _, _, note = agent._chat_with_redraw(
            [{"role": "user", "content": "2+2 nechi?"}], [], request="2+2 nechi?")
        self.assertEqual(len(calls), 1)
        self.assertIsNone(note)  # rasm bo'lmasa ham qayta chizish yo'q

    def test_quality_tip_empty_for_perfect(self):
        parts = [
            "<defs><linearGradient id='g'><stop offset='0' stop-color='#ffd98e'/>"
            "<stop offset='1' stop-color='#f0a63c'/></linearGradient></defs>",
            "<rect width='512' height='512' fill='#f4f1ea'/>",
            "<ellipse cx='256' cy='430' rx='120' ry='16' fill='rgba(0,0,0,0.14)'/>",
            "<circle cx='256' cy='250' r='130' fill='url(#g)' stroke='#8a5a2b' stroke-width='5'"
            " stroke-linejoin='round' stroke-linecap='round'/>",
            "<circle cx='210' cy='210' r='15' fill='#2b2b2b'/>",
            "<circle cx='302' cy='210' r='15' fill='#2b2b2b'/>",
            "<circle cx='214' cy='205' r='5' fill='#fff'/>",
            "<circle cx='306' cy='205' r='5' fill='#fff'/>",
        ]
        r = validate_svg_text(_svg("".join(parts)))
        tip = _drawing_quality_tip(r)
        self.assertEqual(tip, "")  # a'lo chizmada taklif yo'q


if __name__ == "__main__":
    unittest.main(verbosity=2)
