"""
IGRIS BRAIN — Agentic Pipeline tests
====================================
Konversatsiya ichida zarurat turiga qarab agentik pipeline tanlash va qurish
(chat()/chat_stream() ichida) + oxirida konversatsiyani agentic work completion
ma'lumotlari bilan to'ldirish tekshiruvi.

Qamrov:
  - _classify_need  : zarurat turi detektorlari (weather/math/draw/ui_build/web/...)
  - _build_pipeline : pipeline tanlash + qo'shimcha (sub) pipeline'lar
  - chat()          : javobga `completion` record birikadi
  - chat_stream()   : done voqeasida ham completion bor
  - ChatHistory     : add_message completion'ni transcript'ga yozadi (round-trip)
"""

import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from igris_agent import (  # noqa: E402
    IgrisAgent,
    PIPELINE_SPECS,
    DB_STACK,
    STACK_PLANS,
    DB_DISPLAY_SUFFIX,
)
from server import ChatHistory  # noqa: E402


class _FakeIntel:
    """Minimal intellekt — chat() harm-filter/observe tekshiruvlarini o'tkazadi."""

    def screen(self, message):
        return type("V", (), {"allowed": True, "reason": None, "category": ""})()

    def observe(self, message):
        return None

    def adapt_system(self, system, message):
        return system or "system"

    def reasoning_suffix(self):
        return ""

    def quick_math(self, expr):
        """Oddiy arifmetika — _quick_math yo'li tekshiruvi uchun (safe eval).

        Agent `_is_math_request` faqat raqamlar va + - * / ( ) ni o'tkazadi —
        shuning uchun ast orqali xavfsiz hisoblash kifoya.
        """
        import ast
        try:
            node = ast.parse(str(expr), mode="eval")
            return eval(compile(node, "<safe>", "eval"), {"__builtins__": {}})
        except Exception:
            return None

    def evaluate(self, **kwargs):
        class _Eval:
            def to_dict(self):
                return {"confidence": 0.5}
        return _Eval()


class _FakeRichLLM:
    model = "qwen3:8b"
    turbo = False
    think = True

    def __init__(self, events):
        self.events = events

    def chat_stream_rich(self, messages, think=None):
        for e in self.events:
            yield e


def _make_agent():
    agent = IgrisAgent(use_llm=False, memory_enabled=False)
    agent.intelligence = _FakeIntel()
    agent._cag = lambda: None  # CAG keshini chetlab o'tamiz
    return agent


class TestNeedClassification(unittest.TestCase):
    def setUp(self):
        self.agent = _make_agent()

    def test_classify_weather(self):
        self.assertEqual(self.agent._classify_need("Toshkentda ob-havo qanday?"), "weather")

    def test_classify_math(self):
        self.assertEqual(self.agent._classify_need("hisobla 2+2*3"), "math")

    def test_classify_draw(self):
        self.assertEqual(self.agent._classify_need("olma rasmini chizib ber"), "draw")

    def test_classify_ui_build(self):
        self.assertEqual(self.agent._classify_need("todo app qurib ber"), "ui_build")

    def test_classify_web(self):
        self.assertEqual(
            self.agent._classify_need("https://example.com saytini och"), "web")

    def test_classify_code(self):
        self.assertEqual(self.agent._classify_need("fibonachchi kodini yoz"), "code")

    def test_classify_file_task_read(self):
        # Mavjud faylni o'qish/tahlil — file_task
        self.assertEqual(self.agent._classify_need("calc.py ni o'qib ber"), "file_task")
        self.assertEqual(self.agent._classify_need("faylni o'chir"), "file_task")
        self.assertEqual(self.agent._classify_need("todo.txt ga yangi qator qo'sh"), "file_task")

    def test_classify_file_create_stays_code(self):
        # Yangi fayl/dastur yaratish — code, file_task emas
        self.assertEqual(self.agent._classify_need("dastur yoz"), "code")
        self.assertEqual(self.agent._classify_need("yangi fayl yarat"), "code")

    def test_classify_plain_chat(self):
        self.assertEqual(self.agent._classify_need("salom, qalaysan?"), "chat")


class TestBuildPipeline(unittest.TestCase):
    def setUp(self):
        self.agent = _make_agent()

    def test_pipeline_spec_exists_for_all_needs(self):
        for need in ("chat", "math", "weather", "draw", "ui_build",
                     "web", "code", "composition", "creative", "structure",
                     "file_task"):
            self.assertIn(need, PIPELINE_SPECS, f"{need} spec yo'q")

    def test_build_pipeline_selects_by_need(self):
        p = self.agent._build_pipeline("olma rasmini chizib ber")
        self.assertEqual(p["need"], "draw")
        self.assertIn("plan", p["stages"])
        self.assertIn("review", p["stages"])
        self.assertTrue(p["label"])
        self.assertTrue(p["clarified"])

    def test_build_pipeline_sub_pipelines(self):
        # "chiz + kod yoz" — bosh pipeline draw, qo'shimcha code
        p = self.agent._build_pipeline("rasm chizib ber va kod yoz")
        self.assertEqual(p["need"], "draw")
        sub_needs = [s["need"] for s in p["sub_pipelines"]]
        self.assertIn("code", sub_needs, "birlashgan zarurat aniqlanmadi")

    def test_pipeline_engine_known(self):
        p = self.agent._build_pipeline("todo app qurib ber")
        self.assertEqual(p["engine"], "llm+tools")


class TestClarifyRequest(unittest.TestCase):
    """_clarify_request aniqlashtiruvi — mavzu obyekti + rejalangan tool'lar
    (LLMsiz, deterministik)."""

    def setUp(self):
        self.agent = _make_agent()

    def test_clarify_draw_extracts_subject_and_tool(self):
        # 'robot' taniqli sahna ob'ekti emas — custom svg rejalanishi kerak
        c = self.agent._clarify_request("robot rasmini chizib ber", "draw")
        self.assertIn("obyekt: robot", c)
        self.assertIn("art__draw_custom_svg", c)

    def test_clarify_draw_canned_subject_uses_scene_tool(self):
        # 'olma' taniqli sahna ob'ekti — tez scene tool rejalanishi kerak
        c = self.agent._clarify_request("olma rasmini chizib ber", "draw")
        self.assertIn("art__draw_scene_svg", c)

    def test_clarify_draw_two_char_uzbek_subject(self):
        # 'uy' (2 harf) taniqli sahna ob'ekti — length filtri uni tushirmasligi kerak
        c = self.agent._clarify_request("uy rasmini chizib ber", "draw")
        self.assertIn("obyekt: uy", c)
        self.assertIn("art__draw_scene_svg", c)

    def test_clarify_draw_qualifier_does_not_win(self):
        # 'katta' sifat so'zi asosiy obyektni bosib qolmasligi kerak
        c = self.agent._clarify_request("katta uy chizib ber", "draw")
        self.assertIn("obyekt: uy", c)

    def test_clarify_ui_build_extracts_app_and_spec(self):
        c = self.agent._clarify_request("todo app qurib ber", "ui_build")
        self.assertIn("obyekt: todo", c)
        self.assertIn("art__ui_build_spec", c)

    def test_clarify_web_extracts_url(self):
        c = self.agent._clarify_request(
            "https://example.com saytini och", "web")
        self.assertIn("example.com", c)
        self.assertIn("browser", c)

    def test_clarify_code_extracts_language(self):
        c = self.agent._clarify_request("python dastur yoz", "code")
        self.assertIn("obyekt: Python", c)
        self.assertIn("write_file", c)

    def test_clarify_code_no_false_language_from_dastur(self):
        # 'dastur' til EMAS — Python deb atribut qilinmasligi kerak
        c = self.agent._clarify_request("qanday dastur yozish kerak", "code")
        self.assertNotIn("obyekt: Python", c)

    def test_clarify_code_no_false_language_from_script(self):
        # 'script' til EMAS — Script deb atribut qilinmasligi kerak
        c = self.agent._clarify_request("oddiy script yozib ber", "code")
        self.assertNotIn("obyekt: Script", c)

    def test_clarify_code_language_aliases(self):
        c = self.agent._clarify_request("python3 dastur yoz", "code")
        self.assertIn("obyekt: Python", c)
        c = self.agent._clarify_request("js kod yoz", "code")
        self.assertIn("obyekt: JavaScript", c)
        c = self.agent._clarify_request("ts kod yoz", "code")
        self.assertIn("obyekt: TypeScript", c)
        c = self.agent._clarify_request("c# kod yoz", "code")
        self.assertIn("obyekt: C#", c)
        c = self.agent._clarify_request("c++ kod yoz", "code")
        self.assertIn("obyekt: C++", c)

    def test_clarify_code_short_alias_no_partial_match(self):
        # 'py' 'spy' ichida topilmasligi kerak (lookaround chegarasi)
        c = self.agent._clarify_request("spy dastur yoz", "code")
        self.assertNotIn("obyekt: Python", c)

    def test_clarify_code_apostrophe_no_false_language(self):
        # O'zbek apostrofi tilni ushlab qolmasligi kerak:
        # "go'yo" (as if) Go emas, "o'ts" (pass) TypeScript emas
        c = self.agent._clarify_request("go'yo shunday kod yoz", "code")
        self.assertNotIn("obyekt: Go", c)
        c = self.agent._clarify_request("bu o'ts deb yoz", "code")
        self.assertNotIn("obyekt: TypeScript", c)

    def test_clarify_code_apostrophe_language_still_detected(self):
        # Apostrofdan keyingi TOZA til so'zi baribir aniqlanadi
        c = self.agent._clarify_request("go tili bilan yoz", "code")
        self.assertIn("obyekt: Go", c)

    def test_clarify_code_framework_with_language(self):
        c = self.agent._clarify_request("react ilova qurib ber", "code")
        self.assertIn("obyekt: React (JavaScript)", c)
        c = self.agent._clarify_request("django backend yoz", "code")
        self.assertIn("obyekt: Django (Python)", c)

    def test_clarify_code_framework_implied_language(self):
        # Faqat framework aytilsa — uning O'Z tili qo'shiladi
        c = self.agent._clarify_request("flask bilan web yoz", "code")
        self.assertIn("obyekt: Flask (Python)", c)

    def test_clarify_code_explicit_language_overrides_framework_implied(self):
        # Aytilgan til framework tilidan ustun turadi
        c = self.agent._clarify_request("react bilan typescript yoz", "code")
        self.assertIn("obyekt: React (TypeScript)", c)

    def test_clarify_code_framework_long_name_first(self):
        # "react native" "react"dan oldin ushlanishi kerak
        c = self.agent._clarify_request("react native app yoz", "code")
        self.assertIn("React Native", c)

    def test_clarify_code_django_go_not_false_positive(self):
        # 'django' ichidagi 'go' Go tiliga adashmasligi kerak — Django
        # framework sifatida to'g'ri aniqlanadi
        c = self.agent._clarify_request("django ishlamayapti, tuzat", "code")
        self.assertNotIn("Go", c)
        self.assertIn("obyekt: Django (Python)", c)

    def test_clarify_code_asp_net_before_net(self):
        # "asp.net" ".net"ga adashmasligi kerak
        c = self.agent._clarify_request("asp.net api yoz", "code")
        self.assertIn("obyekt: ASP.NET (C#)", c)
        self.assertNotIn(".NET", c.replace("ASP.NET", ""))

    def test_classify_kapital_not_code(self):
        # 'api' 'kapital' (o'zbekcha: sarmoya) ichida topilmasligi —
        # oddiy savol code pipeline'iga tushmasligi kerak
        self.assertEqual(self.agent._classify_need("kapital miqdori qancha?"), "chat")

    def test_clarify_code_framework_expanded_js(self):
        for msg, want in (
            ("nuxt app yoz", "Nuxt (JavaScript)"),
            ("svelte component yoz", "Svelte (JavaScript)"),
            ("gatsby sayt yoz", "Gatsby (JavaScript)"),
            ("jquery skript yoz", "jQuery (JavaScript)"),
            ("electron dastur yoz", "Electron (JavaScript)"),
            ("tailwind bilan sahifa yoz", "Tailwind CSS (CSS)"),
        ):
            with self.subTest(msg=msg):
                self.assertIn("obyekt: " + want,
                              self.agent._clarify_request(msg, "code"))

    def test_clarify_code_framework_expanded_python(self):
        for msg, want in (
            ("pandas bilan tahlil qil", "pandas (Python)"),
            ("numpy massiv yoz", "NumPy (Python)"),
            ("sklearn model yarat", "scikit-learn (Python)"),
            ("selenium test yoz", "Selenium (Python)"),
            ("pytest bilan test yoz", "pytest (Python)"),
            ("celery vazifa yoz", "Celery (Python)"),
        ):
            with self.subTest(msg=msg):
                self.assertIn("obyekt: " + want,
                              self.agent._clarify_request(msg, "code"))

    def test_clarify_code_framework_expanded_backend_mobile(self):
        for msg, want in (
            ("symfony backend yoz", "Symfony (PHP)"),
            ("wordpress sayt qur", "WordPress (PHP)"),
            ("sinatra app yoz", "Sinatra (Ruby)"),
            ("hibernate bilan ishla", "Hibernate (Java)"),
            ("unity o'yin yoz", "Unity (C#)"),
            ("xamarin app yoz", "Xamarin (C#)"),
            ("swiftui ekran yoz", "SwiftUI (Swift)"),
            ("unreal o'yin yoz", "Unreal Engine (C++)"),
            ("tauri dastur yoz", "Tauri (Rust)"),
            ("nestjs server yoz", "NestJS (TypeScript)"),
            ("fastify api yoz", "Fastify (JavaScript)"),
            ("matplotlib grafik chiz", "Matplotlib (Python)"),
            ("beautifulsoup scrape qil", "Beautiful Soup (Python)"),
        ):
            with self.subTest(msg=msg):
                self.assertIn("obyekt: " + want,
                              self.agent._clarify_request(msg, "code"))

    def test_clarify_code_language_expanded(self):
        for msg, want in (
            ("php skript yoz", "PHP"),
            ("ruby dastur yoz", "Ruby"),
            ("kotlin android yoz", "Kotlin"),
            ("swift ios yoz", "Swift"),
            ("dart dastur yoz", "Dart"),
            ("perl skript yoz", "Perl"),
            ("scala dastur yoz", "Scala"),
            ("lua skript yoz", "Lua"),
            ("haskell dastur yoz", "Haskell"),
            ("matlab hisob yoz", "MATLAB"),
        ):
            with self.subTest(msg=msg):
                self.assertIn("obyekt: " + want,
                              self.agent._clarify_request(msg, "code"))

    def test_clarify_code_c_language_not_confused(self):
        # 'c' alohida til — c++/c#/css'dan farqli, toza 'c' so'zi C'ga
        c = self.agent._clarify_request("c tilida dastur yoz", "code")
        self.assertIn("obyekt: C", c)
        # c++ hali ham C++ (c'ga adashmaydi)
        c = self.agent._clarify_request("c++ dastur yoz", "code")
        self.assertIn("obyekt: C++", c)

    def test_detect_web_tech_platform_names(self):
        for msg, want in (
            ("wordpress saytini och", "WordPress"),
            ("shopify do'konini och", "Shopify"),
            ("wix sayt qurish kerak", "Wix"),
            ("joomla saytini tekshir", "Joomla"),
            ("drupal sayti haqida", "Drupal"),
            ("tilda bilan sayt yasash", "Tilda"),
            ("notion sahifani och", "Notion"),
            ("github.io saytini och", "GitHub Pages"),
        ):
            with self.subTest(msg=msg):
                self.assertEqual(self.agent._detect_web_tech(msg), want)

    def test_detect_web_tech_url_markers(self):
        # Domen markeri — nom so'z sifatida kelmasa ham aniqlanadi
        self.assertEqual(
            self.agent._detect_web_tech("https://mystore.myshopify.com och"),
            "Shopify")
        self.assertEqual(
            self.agent._detect_web_tech("https://site.wixsite.com/faq och"),
            "Wix")
        self.assertEqual(
            self.agent._detect_web_tech("https://blog.wordpress.com/1 och"),
            "WordPress")

    def test_detect_web_tech_none(self):
        self.assertEqual(self.agent._detect_web_tech("oddiy saytni och"), "")
        self.assertEqual(self.agent._detect_web_tech("https://example.com och"), "")

    def test_classify_web_site_tech_with_action(self):
        # Platforma nomi + brauzer amali — web pipeline
        self.assertEqual(self.agent._classify_need("shopify do'konini och"), "web")
        self.assertEqual(self.agent._classify_need("wordpress saytini tekshir"), "web")

    def test_classify_web_tech_word_alone_is_not_web(self):
        # "wordpress nima" — bilim savoli, brauzer talab qilmaydi
        self.assertNotEqual(self.agent._classify_need("wordpress nima?"), "web")

    def test_classify_web_site_build_requests(self):
        # Platforma + qurish fe'li — veb so'rov (review'dagi bo'shliq)
        self.assertEqual(self.agent._classify_need("wordpress sayt qur"), "web")
        self.assertEqual(self.agent._classify_need("shopify do'kon yarat"), "web")

    def test_clarify_web_site_tech_subject(self):
        c = self.agent._clarify_request("shopify do'konini och", "web")
        self.assertIn("obyekt: Shopify", c)
        c = self.agent._clarify_request("wordpress saytini och", "web")
        self.assertIn("obyekt: WordPress", c)

    def test_clarify_web_url_with_tech(self):
        c = self.agent._clarify_request(
            "https://mystore.myshopify.com saytini och", "web")
        self.assertIn("myshopify.com", c)
        self.assertIn("Shopify", c)

    def test_build_pipeline_web_framework_is_site_tech(self):
        p = self.agent._build_pipeline("shopify do'konini och")
        self.assertEqual(p["need"], "web")
        self.assertEqual(p["framework"], "Shopify")
        self.assertIn("obyekt: Shopify", p["clarified"])

    def test_completion_web_includes_tech(self):
        data = self.agent.chat("shopify do'konini och", use_memory=False)
        c = data["completion"]
        self.assertEqual(c["pipeline"], "web")
        self.assertEqual(c.get("framework"), "Shopify")

    def test_detect_db_tech_on_web_flavored_messages(self):
        # DB texnologiyalari WEB so'rovlarida ham aniqlanadi (supabase/firebase...)
        for msg, want in (
            ("supabase saytini och", "Supabase"),
            ("firebase konsolini och", "Firebase"),
            ("planetscale sahifasini och", "PlanetScale"),
            ("mongodb atlasni och", "MongoDB"),
            ("redis dashboardini och", "Redis"),
        ):
            with self.subTest(msg=msg):
                self.assertEqual(self.agent._detect_db_tech(msg), want)

    def test_build_pipeline_web_database_field(self):
        # "supabase saytini och" — web pipeline, database maydoni to'ldiriladi
        p = self.agent._build_pipeline("supabase saytini och")
        self.assertEqual(p["need"], "web")
        self.assertEqual(p["database"], "Supabase")
        self.assertIn("obyekt: Supabase (baza)", p["clarified"])

    def test_build_pipeline_web_tech_plus_db(self):
        # Sayt texnologiyasi + DB birga — ikkalasi ham aniqlanadi
        p = self.agent._build_pipeline("wordpress saytini och va postgres bazani ko'r")
        self.assertEqual(p["need"], "web")
        self.assertEqual(p["framework"], "WordPress")
        self.assertEqual(p["database"], "PostgreSQL")
        self.assertIn("WordPress · DB: PostgreSQL", p["subject"])

    def test_completion_web_includes_database(self):
        data = self.agent.chat("supabase saytini och", use_memory=False)
        c = data["completion"]
        self.assertEqual(c["pipeline"], "web")
        self.assertEqual(c.get("database"), "Supabase")
        self.assertIn("Supabase (baza)", c.get("subject", ""))

    def test_build_pipeline_code_framework_language_fields(self):
        p = self.agent._build_pipeline("django bilan backend yoz")
        self.assertEqual(p["framework"], "Django")
        self.assertEqual(p["language"], "Python")
        self.assertIn("obyekt: Django (Python)", p["clarified"])
        # code bo'lmagan pipeline'da bu maydonlar bo'sh
        p2 = self.agent._build_pipeline("olma rasmini chizib ber")
        self.assertEqual(p2["framework"], "")
        self.assertEqual(p2["language"], "")

    def test_detect_orm(self):
        for msg, want in (
            ("prisma bilan backend yoz", "Prisma"),
            ("typeorm bilan loyiha qur", "TypeORM"),
            ("drizzle orm bilan yoz", "Drizzle ORM"),
            ("mongoose bilan backend", "Mongoose"),
        ):
            with self.subTest(msg=msg):
                self.assertEqual(self.agent._detect_orm(msg), want)
        # 'prismadan' kabi so'z ichidagi moslik ORM deb hisoblanmaydi
        self.assertEqual(self.agent._detect_orm("prismadan nima foydasi"), "")
        self.assertEqual(self.agent._detect_orm("oddiy backend yoz"), "")

    def test_build_pipeline_react_postgres_prisma(self):
        # React + PostgreSQL + Prisma — uchalasi ham aniqlanadi
        p = self.agent._build_pipeline("react + postgresql + prisma bilan backend yoz")
        self.assertEqual(p["need"], "code")
        self.assertEqual(p["framework"], "React")
        self.assertEqual(p["language"], "JavaScript")
        self.assertEqual(p["database"], "PostgreSQL")
        self.assertEqual(p["orm"], "Prisma")
        self.assertIn("Prisma", p["subject"])
        self.assertIn("PostgreSQL", p["subject"])
        # rejalangan tool'lar stack'ga mos — terminal orqali bajariladi
        self.assertIn("run_command", p["planned_tools"])

    def test_stack_guide_react_postgres_prisma_commands(self):
        p = self.agent._build_pipeline("react + postgresql + prisma bilan backend yoz")
        g = self.agent._stack_guide(p)
        # npm buyruqlari
        self.assertIn("npm create vite", g)
        # Prisma CLI buyruqlari
        self.assertIn("npx prisma init", g)
        self.assertIn("npx prisma migrate dev", g)
        self.assertIn("npx prisma generate", g)
        self.assertIn("@prisma/client", g)
        # PostgreSQL buyruqlari
        self.assertIn("psql -U", g)

    def test_stack_guide_prisma_alone(self):
        p = self.agent._build_pipeline("prisma bilan backend yoz")
        self.assertEqual(p["orm"], "Prisma")
        g = self.agent._stack_guide(p)
        self.assertIn("npx prisma init", g)
        self.assertIn("npx prisma migrate dev", g)
        # tool'lar ham moslashadi — default write_file+python_exec emas
        self.assertIn("run_command", p["planned_tools"])

    def test_completion_includes_orm(self):
        data = self.agent.chat(
            "react + postgresql + prisma bilan backend yoz", use_memory=False)
        c = data["completion"]
        self.assertEqual(c.get("database"), "PostgreSQL")
        self.assertEqual(c.get("orm"), "Prisma")

    def test_stack_guide_orm_same_plan_dedup(self):
        # TypeORM + React ikkalasi ham npm rejasi — npm guide IKKI marta
        # qo'shilmaydi (id-dedup). Bitta sarlavha bo'lishi shart.
        p = self.agent._build_pipeline("react + typeorm bilan backend yoz")
        self.assertEqual(p["framework"], "React")
        self.assertEqual(p["orm"], "TypeORM")
        g = self.agent._stack_guide(p)
        self.assertEqual(g.count("STACK GUIDE - JavaScript/TypeScript (npm)"), 1)

    def test_sub_pipeline_code_orm_propagation(self):
        # Asosiy pipeline ui_build bo'lsa ham code sub-pipeline'ida orm
        # aniqlanadi va stack qo'llanmasi yetib boradi.
        p = self.agent._build_pipeline("react ilova qurib ber (prisma bilan)")
        sub = next((s for s in p.get("sub_pipelines", []) if s.get("need") == "code"), None)
        if sub is None:
            self.skipTest("code sub-pipeline hosil bo'lmadi")
        self.assertEqual(sub.get("orm"), "Prisma")
        g = self.agent._stack_guide(p)
        self.assertIn("npx prisma init", g)

    def test_clarify_math_extracts_expression(self):
        c = self.agent._clarify_request("hisobla 2+2*3", "math")
        self.assertIn("2+2*3", c)

    def test_clarify_plain_chat_falls_back_to_message(self):
        c = self.agent._clarify_request("salom, qalaysan?", "chat")
        self.assertIn("salom", c)

    def test_build_pipeline_stores_subject_and_planned_tools(self):
        p = self.agent._build_pipeline("olma rasmini chizib ber")
        self.assertEqual(p["subject"], "olma")
        self.assertIn("art__draw_scene_svg", p["planned_tools"])
        self.assertIn("obyekt: olma", p["clarified"])

    def test_completion_includes_subject_and_planned_tools(self):
        data = self.agent.chat("todo app qurib ber", use_memory=False)
        c = data["completion"]
        self.assertEqual(c.get("subject"), "todo")
        self.assertIn("art__ui_build_spec", c.get("planned_tools", []))

    def test_clarify_file_task_extracts_filename_and_tools(self):
        c = self.agent._clarify_request("calc.py ni o'qib ber", "file_task")
        self.assertIn("calc.py", c)
        self.assertIn("read_file", c)
        self.assertNotIn("write_file", c)

    def test_clarify_file_task_edit_includes_patch_tool(self):
        c = self.agent._clarify_request("todo.txt ga yangi qator qo'sh", "file_task")
        self.assertIn("apply_patch", c)
        self.assertIn("write_file", c)

    def test_build_pipeline_file_task(self):
        p = self.agent._build_pipeline("calc.py ni o'qib ber")
        self.assertEqual(p["need"], "file_task")
        self.assertIn("read", p["stages"])
        self.assertIn("edit", p["stages"])
        self.assertEqual(p["subject"], "calc.py")
        self.assertIn("read_file", p["planned_tools"])

    def test_clarify_file_task_no_garbage_subject(self):
        # 'faylni o'chir' — nomli fayl yo'q, subject bo'sh ("o" chiqindisi emas)
        p = self.agent._build_pipeline("faylni o'chir")
        self.assertEqual(p["need"], "file_task")
        self.assertEqual(p["subject"], "")
        self.assertNotIn("obyekt: o", p["clarified"])

    def test_build_pipeline_file_task_sub_pipeline(self):
        # "calc.py ni o'qib ber va kod yoz" — file_task + code sub-pipeline
        p = self.agent._build_pipeline("calc.py ni o'qib ber va yangi kod yoz")
        self.assertEqual(p["need"], "file_task")
        sub_needs = [s["need"] for s in p["sub_pipelines"]]
        self.assertIn("code", sub_needs, "birlashgan code zarurati aniqlanmadi")

    def test_chat_file_task_includes_completion(self):
        data = self.agent.chat("calc.py ni o'qib ber", use_memory=False)
        self.assertIn("completion", data)
        self.assertEqual(data["completion"]["pipeline"], "file_task")


class TestStackAdaptiveTools(unittest.TestCase):
    """Framework aniqlanganda rejalangan tool'lar va stack guide moslashadi
    (React -> npm/webpack terminal vositalari, Django -> python_exec + terminal)."""

    def setUp(self):
        self.agent = _make_agent()

    def test_planned_tools_react_includes_npm_terminal(self):
        tools = self.agent._planned_tools("react ilova qurib ber", "code")
        self.assertIn("run_command", tools)
        self.assertIn("write_file", tools)
        self.assertIn("read_file", tools)
        self.assertNotIn("python_exec", tools)

    def test_planned_tools_django_keeps_python(self):
        tools = self.agent._planned_tools("django backend yoz", "code")
        self.assertIn("python_exec", tools)
        self.assertIn("run_command", tools)

    def test_planned_tools_plain_code_unchanged(self):
        # Framework aniqlanmasa — eski default reja (write_file + python_exec)
        tools = self.agent._planned_tools("fibonachchi kodini yoz", "code")
        self.assertEqual(tools, ["write_file", "python_exec"])

    def test_build_pipeline_react_planned_tools(self):
        # 'qur' fe'li ui_build'ga tashlaydi — code so'rovi ishlatiladi
        p = self.agent._build_pipeline("react kod yoz")
        self.assertEqual(p["need"], "code")
        self.assertEqual(p["framework"], "React")
        self.assertIn("run_command", p["planned_tools"])
        self.assertNotIn("python_exec", p["planned_tools"])

    def test_stack_guide_react_mentions_npm_webpack(self):
        g = self.agent._stack_guide(
            {"need": "code", "framework": "React", "language": "JavaScript"})
        self.assertIn("npm", g)
        self.assertIn("webpack", g)

    def test_stack_guide_django_mentions_manage_py(self):
        g = self.agent._stack_guide(
            {"need": "code", "framework": "Django", "language": "Python"})
        self.assertIn("manage.py", g)

    def test_stack_guide_empty_for_non_code(self):
        self.assertEqual(self.agent._stack_guide({"need": "chat"}), "")
        self.assertEqual(self.agent._stack_guide({"need": "web", "framework": "Shopify"}), "")

    def test_stack_guide_language_fallback(self):
        # Xaritaga kirmagan framework (Unity) — tiliga qarab (C# -> dotnet)
        g = self.agent._stack_guide({"need": "code", "framework": "Unity", "language": "C#"})
        self.assertIn("dotnet", g)
        # framework yo'q, faqat til — baribir stack bo'yicha
        g2 = self.agent._stack_guide({"need": "code", "framework": "", "language": "JavaScript"})
        self.assertIn("npm", g2)

    def test_stack_guide_unknown_language_gets_generic(self):
        # Xaritaga kirmagan til (Perl) — generic reja (terminal vositalari),
        # python_exec'ga o'ralgan default emas
        g = self.agent._stack_guide({"need": "code", "framework": "", "language": "Perl"})
        self.assertIn("run_command", g)
        tools = self.agent._planned_tools("perl skript yoz", "code")
        self.assertIn("run_command", tools)
        self.assertNotIn("python_exec", tools)

    def test_stack_guide_empty_when_no_stack_detected(self):
        # Hech qanday framework/til aniqlanmasa — default reja, guide yo'q
        self.assertEqual(self.agent._stack_guide({"need": "code"}), "")
        tools = self.agent._planned_tools("fibonachchi kodini yoz", "code")
        self.assertEqual(tools, ["write_file", "python_exec"])

    def test_stack_attached_to_code_sub_pipeline(self):
        # "react ilova qurib ber" -> ui_build (qur fe'li), lekin code
        # SUB-pipeline'ida ham stack ko'rinishi kerak (review'dagi bo'shliq)
        p = self.agent._build_pipeline("react ilova qurib ber")
        self.assertEqual(p["need"], "ui_build")
        code_sub = next(s for s in p["sub_pipelines"] if s["need"] == "code")
        self.assertEqual(code_sub.get("framework"), "React")
        self.assertIn("run_command", code_sub.get("planned_tools", []))

    def test_stack_guide_fires_for_code_sub_pipeline(self):
        p = self.agent._build_pipeline("react ilova qurib ber")
        guide = self.agent._stack_guide(p)
        self.assertIn("npm", guide)

    def test_completion_planned_tools_reflect_stack(self):
        data = self.agent.chat("react kod yoz", use_memory=False)
        c = data["completion"]
        self.assertEqual(c.get("framework"), "React")
        self.assertIn("run_command", c.get("planned_tools", []))

    def test_clarify_code_framework_shows_stack_tools(self):
        c = self.agent._clarify_request("react ilova qurib ber", "code")
        self.assertIn("obyekt: React (JavaScript)", c)
        self.assertIn("run_command", c)


class TestDatabaseDetection(unittest.TestCase):
    """Ma'lumotlar bazasi texnologiyalari — aniqlash + tasnif + stack reja."""

    def setUp(self):
        self.agent = _make_agent()

    def test_detect_db_tech_common(self):
        for msg, want in (
            ("postgres bilan ishlayman", "PostgreSQL"),
            ("postgresql bazaga ulan", "PostgreSQL"),
            ("psql orqali so'rov yoz", "PostgreSQL"),
            ("mysql ma'lumotlar bazasi", "MySQL"),
            ("mariadb o'rnat", "MariaDB"),
            ("mongodb dan foydalan", "MongoDB"),
            ("mongo bilan ishlayman", "MongoDB"),
            ("redis cache yoz", "Redis"),
            ("sqlite fayl och", "SQLite"),
            ("mssql serverga ulan", "SQL Server"),
            ("sql server baza", "SQL Server"),
            ("oracle baza yoz", "Oracle"),
            ("supabase ishlat", "Supabase"),
        ):
            with self.subTest(msg=msg):
                self.assertEqual(self.agent._detect_db_tech(msg), want)

    def test_detect_db_tech_no_false_positives(self):
        # 'mongoliya' ichidagi 'mongo' ushlanmasligi kerak (lookaround)
        self.assertEqual(self.agent._detect_db_tech("mongoliya sayohat"), "")
        self.assertEqual(self.agent._detect_db_tech("oddiy so'rov"), "")
        self.assertEqual(self.agent._detect_db_tech("salom, qalaysan?"), "")
        # 'influx' alohida so'z emas (faqat 'influxdb')
        self.assertEqual(self.agent._detect_db_tech("influx bo'lyapti"), "")

    def test_detect_db_tech_extended_coverage(self):
        for msg, want in (
            ("valkey bilan cache yoz", "Valkey"),
            ("memcached so'rov yoz", "Memcached"),
            ("influxdb vaqt seriyasi", "InfluxDB"),
            ("duckdb tahlil yoz", "DuckDB"),
            ("snowflake warehouse", "Snowflake"),
            ("bigquery so'rov yoz", "BigQuery"),
            ("chroma vektor bazasi", "Chroma"),
            ("qdrant semantic qidiruv", "Qdrant"),
            ("milvus embedding yoz", "Milvus"),
            ("pinecone vektor", "Pinecone"),
            ("weaviate graf yoz", "Weaviate"),
            ("faiss index qur", "FAISS"),
            ("pgvector kengaytmasi", "pgvector"),
            ("redshift warehouse", "Redshift"),
            ("cockroachdb cluster", "CockroachDB"),
            ("scylladb cluster", "ScyllaDB"),
            ("planetscale baza", "PlanetScale"),
            ("timescale vaqt bazasi", "TimescaleDB"),
            ("couchdb hujjat yoz", "CouchDB"),
            ("hbase kv yoz", "HBase"),
            ("etcd config yoz", "etcd"),
        ):
            with self.subTest(msg=msg):
                self.assertEqual(self.agent._detect_db_tech(msg), want)

    def test_db_generic_words_stay_chat(self):
        # Oddiy so'z bo'lishi mumkin bo'lgan DB nomlari bilim savolida
        # code'ga olib chiqmaydi (DB_CLASSIFY_EXCLUDE)
        self.assertEqual(self.agent._classify_need("snowflake nima?"), "chat")
        self.assertEqual(self.agent._classify_need("redshift nima?"), "chat")
        self.assertEqual(self.agent._classify_need("chroma nima?"), "chat")
        # 'pinecone' ham oddiy so'z (qarag'ay konusi) — bilim savoli chat'da
        self.assertEqual(self.agent._classify_need("pinecone nima?"), "chat")
        # ammo 'baza' so'zi bilan aniq DB so'rovi code bo'ladi
        self.assertEqual(self.agent._classify_need("snowflake baza yoz"), "code")
        self.assertEqual(self.agent._classify_need("chroma baza yoz"), "code")
        self.assertEqual(self.agent._classify_need("pinecone baza yoz"), "code")

    def test_detect_object_storage(self):
        # Obyekt saqlash (S3-mos) — yangi qamrov
        for msg, want in (
            ("s3 bilan fayl saqlash", "S3"),
            ("aws s3 bucket yaratish", "S3"),
            ("amazon s3 dan rasm yuklab olish", "S3"),
            ("s3://my-bucket ga yozish", "S3"),
            ("minio bilan lokal object storage", "MinIO"),
            ("google cloud storage ga yuklash", "Google Cloud Storage"),
            ("gcs bucket ochish", "Google Cloud Storage"),
            ("azure blob storage ishlatish", "Azure Blob"),
            ("cloudflare r2 bilan media", "Cloudflare R2"),
            ("backblaze b2 ga zaxira", "Backblaze B2"),
            ("digitalocean spaces ga yuklash", "DigitalOcean Spaces"),
        ):
            with self.subTest(msg=msg):
                self.assertEqual(self.agent._detect_db_tech(msg), want)

    def test_detect_realtime_serverless_streams(self):
        for msg, want in (
            ("firestore bilan real-vaqt chat", "Firestore"),
            ("firebase realtime database ishlatish", "Firebase Realtime"),
            ("neon postgres bilan serverless", "Neon Postgres"),
            ("xata bilan backend", "Xata"),
            ("cloudflare d1 database", "Cloudflare D1"),
            ("upstash redis cache", "Upstash"),
            ("surrealdb bilan loyiha", "SurrealDB"),
            ("singlestore bilan tahlil", "SingleStore"),
            ("kafka bilan event streaming", "Kafka"),
            ("rabbitmq navbat tizimi", "RabbitMQ"),
            ("apache pulsar bilan", "Apache Pulsar"),
            ("redpanda bilan", "Redpanda"),
            ("influxdb bilan monitoring", "InfluxDB"),
        ):
            with self.subTest(msg=msg):
                self.assertEqual(self.agent._detect_db_tech(msg), want)

    def test_build_pipeline_object_storage(self):
        p = self.agent._build_pipeline("s3 bilan fayl saqlash tizimi yoz")
        self.assertEqual(p["database"], "S3")
        self.assertIn("S3 (saqlash)", p["subject"])
        self.assertIn("run_command", p["planned_tools"])
        g = self.agent._stack_guide(p)
        self.assertIn("aws s3 cp", g)
        self.assertIn("boto3", g)

    def test_build_pipeline_firestore(self):
        p = self.agent._build_pipeline("firestore bilan real-vaqt chat backend yoz")
        self.assertEqual(p["database"], "Firestore")
        self.assertIn("Firestore (real-vaqt bazasi)", p["subject"])
        g = self.agent._stack_guide(p)
        self.assertIn("firebase/firestore", g)
        self.assertIn("getFirestore", g)

    def test_build_pipeline_kafka_streams(self):
        p = self.agent._build_pipeline("kafka bilan event pipeline backend yoz")
        self.assertEqual(p["database"], "Kafka")
        self.assertIn("Kafka (oqim)", p["subject"])
        g = self.agent._stack_guide(p)
        self.assertIn("kafka-topics.sh", g)
        self.assertIn("kafka-console-producer.sh", g)

    def test_stack_guide_merged_object_storage_with_react(self):
        # React + S3 — npm va object storage rejalari birlashadi
        p = self.agent._build_pipeline("react + s3 bilan backend yoz")
        self.assertEqual(p["database"], "S3")
        g = self.agent._stack_guide(p)
        self.assertIn("STACK GUIDE - JavaScript/TypeScript (npm)", g)
        self.assertIn("STACK GUIDE - Object storage", g)

    def test_stack_guide_extended_db_plans(self):
        for db, want in (
            ("Valkey", "redis-cli"),
            ("ScyllaDB", "cqlsh"),
            ("Chroma", "chromadb"),
            ("InfluxDB", "influx"),
            ("DuckDB", "duckdb"),
            ("Snowflake", "snowsql"),
            ("BigQuery", "bq query"),
            ("pgvector", "psql"),
            ("Redshift", "psql"),
            ("TimescaleDB", "psql"),
        ):
            with self.subTest(db=db):
                g = self.agent._stack_guide(
                    {"need": "code", "framework": "", "language": "", "database": db})
                self.assertIn(want, g)

    def test_detect_db_tech_new_entries(self):
        # Turso/libSQL/TiDB/YugabyteDB kabi 2026-muhim DB'lar aniqlanadi
        for msg, want in (
            ("turso bilan bazaga ulan", "Turso"),
            ("libsql fayl bazasi", "libSQL"),
            ("tidb klasteriga so'rov", "TiDB"),
            ("yugabytedb yoz", "YugabyteDB"),
            ("yugabyte cluster", "YugabyteDB"),
        ):
            self.assertEqual(self.agent._detect_db_tech(msg), want, msg)

    def test_stack_guide_new_db_plans(self):
        # Turso libSQL — SQLite rejasi; TiDB — MySQL; YugabyteDB — PostgreSQL
        for db, want in (
            ("Turso", "sqlite3"),
            ("libSQL", "sqlite3"),
            ("TiDB", "mysql"),
            ("YugabyteDB", "psql"),
        ):
            g = self.agent._stack_guide(
                {"need": "code", "framework": "", "language": "", "database": db})
            self.assertIn(want, g, db)

    def test_classify_db_request_is_code(self):
        self.assertEqual(self.agent._classify_need("postgres bilan bazaga kod yoz"), "code")
        self.assertEqual(self.agent._classify_need("mysql so'rov yoz"), "code")
        self.assertEqual(self.agent._classify_need("redis cache yoz"), "code")

    def test_oracle_knowledge_question_stays_chat(self):
        # 'oracle' oddiy so'z bo'lishi mumkin — bilim savoli code'ga tushmaydi
        self.assertEqual(self.agent._classify_need("oracle nima?"), "chat")
        # ammo 'baza' so'zi bilan aniq DB so'rovi code bo'ladi
        self.assertEqual(self.agent._classify_need("oracle baza yoz"), "code")
        self.assertEqual(self.agent._detect_db_tech("oracle baza yoz"), "Oracle")

    def test_clarify_db_only_subject(self):
        c = self.agent._clarify_request("mysql bilan baza yoz", "code")
        self.assertIn("obyekt: MySQL (baza)", c)
        self.assertIn("run_command", c)

    def test_clarify_framework_with_db(self):
        c = self.agent._clarify_request("react va postgres app yoz", "code")
        self.assertIn("obyekt: React (JavaScript) · DB: PostgreSQL", c)

    def test_build_pipeline_database_field(self):
        p = self.agent._build_pipeline("django va postgres backend yoz")
        self.assertEqual(p["need"], "code")
        self.assertEqual(p["framework"], "Django")
        self.assertEqual(p["database"], "PostgreSQL")
        # DB bo'lmagan pipeline'da bo'sh
        p2 = self.agent._build_pipeline("olma rasmini chizib ber")
        self.assertEqual(p2["database"], "")

    def test_planned_tools_db_includes_terminal(self):
        tools = self.agent._planned_tools("mysql bilan baza yoz", "code")
        self.assertIn("run_command", tools)
        # Django+PostgreSQL birlashmasi: python_exec ham qoladi
        tools2 = self.agent._planned_tools("django va postgres yoz", "code")
        self.assertIn("python_exec", tools2)
        self.assertIn("run_command", tools2)

    def test_stack_guide_db_commands(self):
        g = self.agent._stack_guide(
            {"need": "code", "framework": "", "language": "", "database": "PostgreSQL"})
        self.assertIn("psql", g)
        g2 = self.agent._stack_guide(
            {"need": "code", "framework": "", "language": "", "database": "MongoDB"})
        self.assertIn("mongosh", g2)
        g3 = self.agent._stack_guide(
            {"need": "code", "framework": "", "language": "", "database": "Redis"})
        self.assertIn("redis-cli", g3)
        # Framework rejasi bilan birlashadi (npm + psql)
        gf = self.agent._stack_guide({
            "need": "code", "framework": "React", "language": "JavaScript", "database": "PostgreSQL"})
        self.assertIn("npm", gf)
        self.assertIn("psql", gf)

    def test_completion_includes_database(self):
        data = self.agent.chat("postgres bilan backend yoz", use_memory=False)
        c = data["completion"]
        self.assertEqual(c.get("database"), "PostgreSQL")
        self.assertIn("run_command", c.get("planned_tools", []))

    def test_stack_guide_expanded_db_plans(self):
        # Generic 'db' rejasi o'rniga har bir DB o'z maxsus rejasini oladi
        for db, want in (
            ("Elasticsearch", "9200"),
            ("Cassandra", "cqlsh"),
            ("DynamoDB", "aws dynamodb"),
            ("Neo4j", "cypher-shell"),
            ("ClickHouse", "clickhouse-client"),
            ("Oracle", "sqlplus"),
        ):
            with self.subTest(db=db):
                g = self.agent._stack_guide(
                    {"need": "code", "framework": "", "language": "", "database": db})
                self.assertIn(want, g)

    def test_stack_guide_elasticsearch_not_generic(self):
        # Elasticsearch endi o'z rejasiga ega — _search buyrug'i bor, generic emas
        g = self.agent._stack_guide(
            {"need": "code", "framework": "", "language": "", "database": "Elasticsearch"})
        self.assertIn("_search", g)
        self.assertNotIn("Database (generic)", g)

    def test_stack_guide_postgres_orm(self):
        g = self.agent._stack_guide(
            {"need": "code", "framework": "", "language": "", "database": "PostgreSQL"})
        self.assertIn("SQLAlchemy", g)
        self.assertIn("Prisma", g)

    def test_stack_guide_mysql_orm(self):
        g = self.agent._stack_guide(
            {"need": "code", "framework": "", "language": "", "database": "MySQL"})
        self.assertIn("SQLAlchemy", g)
        self.assertIn("Prisma", g)

    def test_db_stack_attached_to_code_sub_pipeline(self):
        p = self.agent._build_pipeline("postgres bilan ilova qur")
        self.assertEqual(p["need"], "ui_build")
        code_sub = next(s for s in p["sub_pipelines"] if s["need"] == "code")
        self.assertEqual(code_sub.get("database"), "PostgreSQL")


class TestLangDbMerge(unittest.TestCase):
    """Til + DB birgalikda aniqlanganda planned_tools va guide birlashishi.

    Masalan "python va postgres": python rejasi (python_exec) bilan postgres
    rejasi (psql) bitta planned_tools/guide'ga birlashadi — til buyruqlari va
    DB buyruqlari IKKALASI ham modelga yetib boradi.
    """

    def setUp(self):
        self.agent = _make_agent()

    def test_python_postgres_merge(self):
        p = self.agent._build_pipeline("python va postgres bilan backend yoz")
        self.assertEqual(p["need"], "code")
        self.assertEqual(p["language"], "Python")
        self.assertEqual(p["database"], "PostgreSQL")
        self.assertEqual(p["subject"], "Python · DB: PostgreSQL")
        # planned_tools: python rejasi (python_exec) + postgres (run_command)
        tools = p["planned_tools"]
        self.assertIn("python_exec", tools)
        self.assertIn("run_command", tools)
        g = self.agent._stack_guide(p)
        self.assertIn("STACK GUIDE - Python:", g)
        self.assertIn("STACK GUIDE - PostgreSQL:", g)
        self.assertIn("pip install", g)
        self.assertIn("psql -U", g)
        self.assertIn("SQLAlchemy", g)

    def test_js_mysql_merge(self):
        p = self.agent._build_pipeline("javascript va mysql bilan yoz")
        self.assertEqual(p["language"], "JavaScript")
        self.assertEqual(p["database"], "MySQL")
        g = self.agent._stack_guide(p)
        self.assertIn("STACK GUIDE - JavaScript/TypeScript (npm):", g)
        self.assertIn("STACK GUIDE - MySQL/MariaDB:", g)
        # JS rejasi python_exec'ni rejalashmaydi
        self.assertNotIn("python_exec", p["planned_tools"])

    def test_golang_redis_merge(self):
        p = self.agent._build_pipeline("golang va redis bilan backend yoz")
        self.assertEqual(p["language"], "Go")
        self.assertEqual(p["database"], "Redis")
        g = self.agent._stack_guide(p)
        self.assertIn("STACK GUIDE - Go:", g)
        self.assertIn("STACK GUIDE - Redis:", g)
        self.assertIn("go mod tidy", g)
        self.assertIn("redis-cli", g)

    def test_django_postgres_triple_merge(self):
        # Framework + til + DB UCHALASI birda — python rejasi python_exec'ni
        # saqlab qoladi, postgres rejasi psql buyruqlarini qo'shadi.
        p = self.agent._build_pipeline("django va postgres bilan backend yoz")
        self.assertEqual(p["framework"], "Django")
        self.assertEqual(p["language"], "Python")
        self.assertEqual(p["database"], "PostgreSQL")
        self.assertIn("python_exec", p["planned_tools"])
        g = self.agent._stack_guide(p)
        self.assertIn("STACK GUIDE - Python:", g)
        self.assertIn("STACK GUIDE - PostgreSQL:", g)
        self.assertIn("manage.py runserver", g)
        self.assertIn("psql -U", g)

    def test_lang_db_sub_pipeline_merge(self):
        # Asosiy pipeline ui_build bo'lsa ham code sub-pipeline'ida til+DB
        # birlashadi ("python va postgres bilan ilova qur").
        p = self.agent._build_pipeline("python va postgres bilan ilova qur")
        self.assertEqual(p["need"], "ui_build")
        code_sub = next(s for s in p["sub_pipelines"] if s["need"] == "code")
        self.assertEqual(code_sub.get("language"), "Python")
        self.assertEqual(code_sub.get("database"), "PostgreSQL")
        self.assertIn("python_exec", code_sub.get("planned_tools", []))
        g = self.agent._stack_guide(p)
        self.assertIn("STACK GUIDE - Python:", g)
        self.assertIn("STACK GUIDE - PostgreSQL:", g)

    def test_completion_keeps_lang_and_db(self):
        data = self.agent.chat(
            "python va postgres bilan backend yoz", use_memory=False)
        c = data["completion"]
        self.assertEqual(c.get("language"), "Python")
        self.assertEqual(c.get("database"), "PostgreSQL")
        self.assertIn("Python · DB: PostgreSQL", c.get("subject", ""))


class TestVectorDbPlans(unittest.TestCase):
    """Vector DB rejalari — embedding o'lchami + qidiruv so'rovi ko'rsatmalari.

    Har bir vector DB o'z rejasiga ega (Chroma/Qdrant/Pinecone/Milvus/
    Weaviate/FAISS): guide'da EMBEDDING O'LCHAMI (1536/384/768...) va
    amaliy qidiruv snippet'i bo'lishi shart.
    """

    def setUp(self):
        self.agent = _make_agent()

    def _guide(self, db):
        return self.agent._stack_guide(
            {"need": "code", "framework": "", "language": "", "database": db})

    def test_chroma_plan_embedding_and_search(self):
        g = self._guide("Chroma")
        self.assertIn("chromadb", g)
        self.assertIn("col.query(query_embeddings=[vec], n_results=5", g)
        self.assertIn("1536", g)  # embedding o'lchami
        self.assertIn("all-MiniLM-L6-v2=384", g)

    def test_qdrant_plan_embedding_and_search(self):
        g = self._guide("Qdrant")
        self.assertIn("qdrant-client", g)
        self.assertIn("create_collection", g)
        self.assertIn("'size': 1536", g)  # embedding o'lchami
        self.assertIn("query_vector=vec, limit=5", g)

    def test_pinecone_plan_embedding_and_search(self):
        g = self._guide("Pinecone")
        self.assertIn("pinecone-client", g)
        self.assertIn("dimension=1536", g)  # embedding o'lchami
        self.assertIn("top_k=5", g)
        self.assertIn("namespace", g)

    def test_milvus_plan_embedding_and_search(self):
        g = self._guide("Milvus")
        self.assertIn("pymilvus", g)
        self.assertIn("dimension=1536", g)
        self.assertIn("metric_type='COSINE'", g)
        self.assertIn("limit=5", g)

    def test_weaviate_plan_embedding_and_search(self):
        g = self._guide("Weaviate")
        self.assertIn("with_near_vector", g)
        self.assertIn("nearVector", g)
        self.assertIn("1536", g)

    def test_faiss_plan_embedding_and_search(self):
        g = self._guide("FAISS")
        self.assertIn("IndexFlatIP", g)
        self.assertIn("faiss.normalize_L2", g)
        self.assertIn("k=5", g)
        self.assertIn("astype('float32')", g)

    def test_every_vector_plan_mentions_embedding_size(self):
        # Har bir vector reja embedding o'lchami bo'yicha ko'rsatma beradi
        for db in ("Chroma", "Qdrant", "Pinecone", "Milvus", "Weaviate", "FAISS"):
            with self.subTest(db=db):
                g = self._guide(db)
                self.assertIn("1536", g)
                self.assertIn("EMBEDDING O'LCHAMI", g)

    def test_build_pipeline_vector_db_integration(self):
        # To'liq zanjir: aniqlash -> database maydoni -> reja buyruqlari
        p = self.agent._build_pipeline("chroma vektor bazasi uchun kod yoz")
        self.assertEqual(p["database"], "Chroma")
        g = self.agent._stack_guide(p)
        self.assertIn("n_results=5", g)
        self.assertIn("1536", g)
        self.assertIn("run_command", p["planned_tools"])


class TestDatabaseTechAudit(unittest.TestCase):
    """AUDIT: barcha aniqlanadigan DB texnologiyalari jadvali.

    Har bir hint -> display nomi -> stack rejasi -> guide buyruqlari.
    Jadval terminal'ga chop etiladi va reports/db_tech_audit.txt ga yoziladi.
    Integratsiya tekshiruvlari:
      - har bir display nomi DB_STACK'da rejaga ega va reja mavjud;
      - har bir hint o'z nomini O'ZI aniqlaydi (first-match-wins tartibda
        boshqa hint soyasida qolib ketgan bo'lsa — xato);
      - DB_CLASSIFY_EXCLUDE / DB_DISPLAY_SUFFIX faqat mavjud nomlarga ishora
        qiladi; har bir reja guide'ida real buyruqlar bor.
    """

    def setUp(self):
        self.agent = _make_agent()

    def _audit_rows(self) -> list[list[str]]:
        """Jadval qatorlari: [nom, hintlar, reja, buyruqlar]."""
        by_name: dict[str, list[str]] = {}
        for pat, name in self.agent.DATABASE_TECH_HINTS:
            by_name.setdefault(name, []).append(pat)
        rows: list[list[str]] = []
        for name in sorted(by_name, key=str.lower):
            hints = ", ".join(by_name[name])
            if len(hints) > 42:
                hints = hints[:42] + "…"
            plan_key = DB_STACK.get(name, "?")
            guide = (STACK_PLANS.get(plan_key) or {}).get("guide", "")
            # guide'dan buyruqqa o'xshagan backtick'lar (probel bor — CLI)
            cmds = [c for c in re.findall(r"`([^`]+)`", guide) if " " in c][:4]
            cmds_txt = " | ".join(cmds)
            if len(cmds_txt) > 68:
                cmds_txt = cmds_txt[:68] + "…"
            rows.append([name, hints, plan_key, cmds_txt])
        return rows

    def test_audit_every_db_tech_has_plan_and_commands(self):
        rows = self._audit_rows()
        self.assertGreater(len(rows), 0)
        for name, _hints, plan_key, cmds in rows:
            with self.subTest(name=name):
                self.assertIn(name, DB_STACK, f"{name} DB_STACK'da yo'q")
                self.assertIn(plan_key, STACK_PLANS,
                              f"{name} -> '{plan_key}' rejasi mavjud emas")
                self.assertTrue(cmds, f"{name} rejasi ({plan_key}) buyruqsiz")

    def test_audit_every_hint_self_detects(self):
        # Har bir hint o'z nomini aniqlashi shart — aks holda first-match-wins
        # tartibda boshqa hint soyasida qolib ketgan (kelajakdagi regressiya).
        for pat, name in self.agent.DATABASE_TECH_HINTS:
            with self.subTest(pattern=pat):
                self.assertEqual(self.agent._detect_db_tech(pat), name)

    def test_audit_realistic_shadow_cases(self):
        # Haqiqiy so'rovlardagi soya (shadow) holatlari — uzun birikmalar
        # qisqa pattern'larga yutilib qolmasligi (tartib regressiyasi).
        for msg, want in (
            ("firebase realtime database ishlatish", "Firebase Realtime"),
            ("supabase realtime database yoz", "Supabase"),
            ("redis realtime database yoz", "Redis"),
            ("neon postgres bilan serverless", "Neon Postgres"),
            ("upstash redis cache yoz", "Upstash"),
            ("aws s3 bucket yaratish", "S3"),
            ("azure blob storage ishlatish", "Azure Blob"),
        ):
            with self.subTest(msg=msg):
                self.assertEqual(self.agent._detect_db_tech(msg), want)

    def test_audit_every_stack_mapping_is_detectable(self):
        # DB_STACK'dagi HAR BIR reja kaliti haqiqiy hint'ga ega bo'lishi
        # shart — aks holda aniqlanmaydigan (o'lik) reja qoladi.
        displays = {n for _, n in self.agent.DATABASE_TECH_HINTS}
        self.assertTrue(set(DB_STACK) <= displays,
                        f"DB_STACK'da hint'siz nomlar: "
                        f"{sorted(set(DB_STACK) - displays)}")

    def test_audit_exclude_and_suffix_reference_real_techs(self):
        displays = {n for _, n in self.agent.DATABASE_TECH_HINTS}
        self.assertTrue(self.agent.DB_CLASSIFY_EXCLUDE <= displays,
                        f"DB_CLASSIFY_EXCLUDE'da noma'lum: "
                        f"{sorted(self.agent.DB_CLASSIFY_EXCLUDE - displays)}")
        self.assertTrue(set(DB_DISPLAY_SUFFIX) <= displays,
                        f"DB_DISPLAY_SUFFIX'da noma'lum: "
                        f"{sorted(set(DB_DISPLAY_SUFFIX) - displays)}")

    def test_audit_print_and_save_table(self):
        """Jadvalni chop etadi va reports/db_tech_audit.txt ga saqlaydi."""
        rows = self._audit_rows()
        headers = ["#", "DB texnologiya", "Hint(lar)", "Reja", "Buyruqlar (guide)"]
        table = [headers] + [[str(i), *r] for i, r in enumerate(rows, 1)]
        widths = [max(len(row[i]) for row in table) for i in range(len(headers))]
        lines: list[str] = []
        for idx, row in enumerate(table):
            line = " | ".join(cell.ljust(w) for cell, w in zip(row, widths))
            lines.append(line.rstrip())
            if idx in (0, len(table) - 1):
                lines.append("-" * len(line.rstrip()))
        text = "\n".join(lines)
        reports_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        path = os.path.join(reports_dir, "db_tech_audit.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        # fayl haqiqatan yozildi va jadval to'liq (sarlavha + qatorlar)
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn(headers[1], content)
        self.assertGreaterEqual(
            content.count("\n"), len(rows) + 1, "jadval faylga to'liq yozilmagan")
        print(f"\nDB texnologiya auditi: {len(rows)} ta texnologiya -> {path}")
        print(text)


class TestChatCompletion(unittest.TestCase):
    def setUp(self):
        self.agent = _make_agent()

    def test_chat_math_includes_completion(self):
        data = self.agent.chat("hisobla 2+2*3", use_memory=False)
        self.assertIn("completion", data)
        c = data["completion"]
        self.assertEqual(c["pipeline"], "math")
        self.assertEqual(c["status"], "ok")
        self.assertIn("duration_ms", c)
        self.assertEqual(c["engine"], "math-quick")

    def test_chat_plain_includes_completion(self):
        data = self.agent.chat("salom, qalaysan?", use_memory=False)
        self.assertIn("completion", data)
        self.assertEqual(data["completion"]["pipeline"], "chat")

    def test_chat_refused_includes_completion(self):
        agent = _make_agent()
        agent.intelligence = type("Strict", (), {
            "screen": lambda self, m: type("V", (), {"allowed": False, "reason": "rad", "category": "harm"})(),
            "observe": lambda self, m: None,
            "adapt_system": lambda self, s, m: s,
            "reasoning_suffix": lambda self: "",
            "quick_math": lambda self, e: 8,
            "evaluate": lambda self, **kw: type("E", (), {"to_dict": lambda self: {"confidence": 0.5}})(),
        })()
        data = agent.chat("yomon narsa", use_memory=False)
        self.assertIn("completion", data)
        self.assertEqual(data["completion"]["status"], "refused")


class TestChatStreamCompletion(unittest.TestCase):
    def setUp(self):
        self.agent = _make_agent()
        self.agent.use_llm = True
        self.agent._llm_checked = True
        self.agent._llm_available = True

    def test_stream_done_includes_completion(self):
        llm = _FakeRichLLM([{"type": "token", "content": "Assalomu alaykum!"}])
        self.agent.llm = llm
        out = list(self.agent.chat_stream("salom", use_memory=False))
        done = next(ev for ev in out if ev["type"] == "done")
        self.assertIn("completion", done)
        self.assertEqual(done["completion"]["pipeline"], "chat")
        self.assertEqual(done["content"], "Assalomu alaykum!")


class TestCompletionInHistory(unittest.TestCase):
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

    def test_add_message_stores_completion(self):
        completion = {
            "pipeline": "code",
            "label": "Kod vazifasi",
            "stages": ["plan", "read", "edit", "test", "review"],
            "engine": "llm+tools",
            "tools": ["write_file", "python_exec"],
            "status": "ok",
        }
        self.h.add_message("conv-p", "assistant", "javob", completion=completion)
        msg = self.h.get("conv-p")["messages"][0]
        self.assertEqual(msg["completion"]["pipeline"], "code")
        self.assertEqual(msg["completion"]["tools"], ["write_file", "python_exec"])
        # completion berilmasa — kalit umuman yo'q (transcript minimal qoladi)
        self.h.add_message("conv-p", "user", "savol")
        self.assertNotIn("completion", self.h.get("conv-p")["messages"][1])
        # JSONL round-trip: completion ham saqlanadi
        h2 = ChatHistory(path=self.tmp.name)
        msg2 = h2.get("conv-p")["messages"][0]
        self.assertEqual(msg2["completion"]["engine"], "llm+tools")

    def test_completion_record_json_serializable(self):
        completion = {
            "pipeline": "draw",
            "label": "Chizma / SVG",
            "stages": ["plan", "edit", "review"],
            "engine": "llm+tools",
            "tools": ["art__draw_custom_svg"],
            "image": "duck.svg",
            "sub_pipelines": ["Kod vazifasi"],
        }
        self.h.add_message("conv-j", "assistant", "tayyor", completion=completion)
        # fayl har bir satr VALID JSON bo'lishi kerak
        with open(self.tmp.name, "r", encoding="utf-8") as fh:
            lines = [ln for ln in fh if ln.strip()]
        [json.loads(ln) for ln in lines]



# ------------------------------------------------------------------
# Agentic architecture: yangi metodlar (§3.2 + §3.3.a/c)
# ------------------------------------------------------------------

class TestTwoStageRouter(unittest.TestCase):
    """Ikki bosqichli router: _classify_family + _classify_type."""

    def setUp(self):
        self.agent = _make_agent()

    # --- Bosqich 1: family ---
    def test_family_chat_simple(self):
        self.assertEqual(IgrisAgent._classify_family("salom"), "chat")

    def test_family_chat_math(self):
        self.assertEqual(IgrisAgent._classify_family("2+2"), "chat")

    def test_family_chat_weather(self):
        self.assertEqual(IgrisAgent._classify_family("ob-havo"), "chat")

    def test_family_creator_draw(self):
        self.assertEqual(IgrisAgent._classify_family("rasm chiz"), "creator")

    def test_family_creator_code(self):
        self.assertEqual(IgrisAgent._classify_family("kod yoz"), "creator")

    def test_family_creator_ui_build(self):
        self.assertEqual(IgrisAgent._classify_family("todo app qur"), "creator")

    def test_family_creator_web(self):
        self.assertEqual(IgrisAgent._classify_family("https://example.com och"), "creator")

    def test_family_creator_file_task(self):
        self.assertEqual(IgrisAgent._classify_family("calc.py ni o'qib ber"), "creator")

    # --- Bosqich 2: type within family ---
    def test_type_chat_weather(self):
        self.assertEqual(IgrisAgent._classify_type("ob-havo", "chat"), "weather")

    def test_type_chat_math(self):
        self.assertEqual(IgrisAgent._classify_type("2+2", "chat"), "math")

    def test_type_chat_plain(self):
        self.assertEqual(IgrisAgent._classify_type("salom", "chat"), "chat")

    def test_type_creator_draw(self):
        self.assertEqual(IgrisAgent._classify_type("rasm chiz", "creator"), "draw")

    def test_type_creator_code(self):
        self.assertEqual(IgrisAgent._classify_type("kod yoz", "creator"), "code")

    def test_type_creator_ui_build(self):
        self.assertEqual(IgrisAgent._classify_type("todo app qur", "creator"), "ui_build")

    def test_type_creator_web(self):
        self.assertEqual(IgrisAgent._classify_type("https://example.com och", "creator"), "web")

    def test_type_creator_file_task(self):
        self.assertEqual(IgrisAgent._classify_type("calc.py ni o'qib ber", "creator"), "file_task")

    # --- Full pipeline: family + type ---
    def test_full_pipeline_matches_classify_need(self):
        messages = [
            "salom",
            "ob-havo",
            "2+2",
            "rasm chiz",
            "kod yoz",
            "todo app qur",
            "https://example.com och",
            "calc.py ni o'qib ber",
        ]
        for msg in messages:
            with self.subTest(msg=msg):
                family = IgrisAgent._classify_family(msg)
                need = IgrisAgent._classify_type(msg, family)
                direct = self.agent._classify_need(msg)
                self.assertEqual(need, direct,
                                 f"family+type ({family}→{need}) != classify_need ({direct})")


class TestClarificationGate(unittest.TestCase):
    """_clarification_gate — pre-loop gate (§3.3.c)."""

    def test_gate_none_when_req_is_none(self):
        self.assertIsNone(IgrisAgent._clarification_gate(None))

    def test_gate_none_when_no_clarification_needed(self):
        class FakeReq:
            needs_clarification = False
        self.assertIsNone(IgrisAgent._clarification_gate(FakeReq()))

    def test_gate_returns_question(self):
        class FakeReq:
            needs_clarification = True
            clarification_question = "Qaysi til bilan yozaman?"
            missing_fields = ["language"]
        result = IgrisAgent._clarification_gate(FakeReq())
        self.assertIsNotNone(result)
        self.assertEqual(result["question"], "Qaysi til bilan yozaman?")
        self.assertIn("language", result["missing_fields"])

    def test_gate_none_when_question_is_none(self):
        class FakeReq:
            needs_clarification = True
            clarification_question = None
        self.assertIsNone(IgrisAgent._clarification_gate(FakeReq()))


class TestReviewDispatch(unittest.TestCase):
    """_review_dispatch — build_verify vs reflexion_critique (§3.2)."""

    def setUp(self):
        self.agent = _make_agent()

    def test_dispatch_ok_review_no_repair(self):
        result = self.agent._review_dispatch(
            {"ok": True}, {"loop_shape": "build_verify", "max_repair": 3})
        self.assertTrue(result["ok"])
        self.assertFalse(result["repaired"])
        self.assertEqual(result["attempts"], 0)

    def test_dispatch_build_verify_repair(self):
        called = [0]

        def edit_fn(issues):
            called[0] += 1

        result = self.agent._review_dispatch(
            {"ok": False, "issues": ["color wrong"]},
            {"loop_shape": "build_verify", "max_repair": 3},
            edit_fn=edit_fn)
        self.assertTrue(result["ok"])
        self.assertTrue(result["repaired"])
        self.assertEqual(result["method"], "build_verify")
        self.assertEqual(called[0], 1)

    def test_dispatch_reflexion_critique(self):
        result = self.agent._review_dispatch(
            {"ok": False, "issues": ["style mismatch"]},
            {"loop_shape": "reflexion_critique", "max_repair": 3})
        self.assertTrue(result["ok"])
        self.assertTrue(result["repaired"])
        self.assertEqual(result["method"], "reflexion_critique")
        self.assertIn("critique", result)

    def test_dispatch_no_repair_when_max_repair_zero(self):
        result = self.agent._review_dispatch(
            {"ok": False, "issues": ["test failed"]},
            {"loop_shape": "build_verify", "max_repair": 0})
        self.assertFalse(result["ok"])
        self.assertFalse(result["repaired"])

    def test_dispatch_straight_through_no_retry(self):
        result = self.agent._review_dispatch(
            {"ok": False, "issues": ["something"]},
            {"loop_shape": "straight_through", "max_repair": 3})
        self.assertFalse(result["ok"])
        self.assertFalse(result["repaired"])


class TestPipelineLoopFields(unittest.TestCase):
    """PIPELINE_SPECS da loop_shape, max_iter, max_repair mavjudligini tekshirish."""

    def setUp(self):
        self.agent = _make_agent()

    def test_all_specs_have_loop_fields(self):
        for need, spec in PIPELINE_SPECS.items():
            with self.subTest(need=need):
                self.assertIn("loop_shape", spec, f"{need}: loop_shape yo'q")
                self.assertIn("max_iter", spec, f"{need}: max_iter yo'q")
                self.assertIn("max_repair", spec, f"{need}: max_repair yo'q")
                self.assertGreaterEqual(spec["max_iter"], 1)
                self.assertGreaterEqual(spec["max_repair"], 0)

    def test_build_verify_specs_have_repair(self):
        for need in ("draw", "code"):
            spec = PIPELINE_SPECS[need]
            self.assertEqual(spec["loop_shape"], "build_verify")
            self.assertGreater(spec["max_repair"], 0,
                               f"{need}: build_verify kerakligi max_repair > 0")

    def test_straight_through_specs_no_repair(self):
        for need in ("math", "weather"):
            spec = PIPELINE_SPECS[need]
            self.assertEqual(spec["loop_shape"], "straight_through")
            self.assertEqual(spec["max_repair"], 0)

    def test_build_pipeline_includes_loop_fields(self):
        p = self.agent._build_pipeline("olma rasmini chizib ber")
        self.assertIn("loop_shape", p)
        self.assertIn("max_iter", p)
        self.assertIn("max_repair", p)
        self.assertEqual(p["loop_shape"], "build_verify")


if __name__ == "__main__":
    unittest.main(verbosity=2)
