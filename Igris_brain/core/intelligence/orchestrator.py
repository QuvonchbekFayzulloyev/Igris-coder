"""
IGRIS BRAIN — Intelligence Orchestrator
=======================================
Barcha intellekt modullarini bitta oqimga birlashtiradi (qo'llanma 4-bo'lim):

    [Operator buyrug'i]
        -> harm_filter      (2.10: tor zarar filtri)
        -> user_model + tone_detect  (2.6 + 2.12: moslashtirish)
        -> [language / logic / spatial / creative]  (ijro qatlami)
        -> self_eval        (2.7: ishonch darajasi bilan chiqish)
        -> [operator ko'rib chiqadi / tasdiqlaydi]

Muhim tamoyillar (qo'llanma 0 va 1-bo'lim):
  - Avtonomiya darajasi NOL: hech qanday modul agentga o'z maqsadini
    qo'yish yoki xulq-atvorini qayta belgilash imkonini bermaydi.
  - Buyruqqa javob: shartli — aniq zarar chegarasida rad etadi.
  - Goal-fayllar/system instruction faqat operator yozish huquqiga ega
    qatlamda saqlanadi — orchestrator ularni O'ZGARTIRMAYDI.
"""

from __future__ import annotations

from typing import Optional

from core.intelligence.harm_filter import HarmFilter, HarmVerdict
from core.intelligence.language import LanguageLayer
from core.intelligence.logic import LogicLayer, StructureCheck
from core.intelligence.self_eval import SelfEvaluator, SelfEvalResult
from core.intelligence.spatial import SpatialReasoner
from core.intelligence.tone_detect import ToneDetector, ToneSignal
from core.intelligence.user_model import UserModel
from core.intelligence.creative import CreativeEngine
from core.intelligence.naturalist import NaturalistLayer
from core.intelligence.music import MusicLayer


class IntelligenceCore:
    """Intellekt qatlami — barcha modullarning yagona kirish nuqtasi.

    Agent (igris_agent) bu core orqali:
      1. `screen(command)` — zarar filtrini ishga tushiradi (rad etish mumkin)
      2. `adapt_system(system, message)` — moslashtirish direktivalarini
         system prompt'ga qo'shadi (user-model + tone + language)
      3. `reasoning_suffix()` — mantiqiy (CoT) yo'naltirish
      4. `evaluate(...)` — ishonch kalibratsiyasi (javobga biriktiradi)
    """

    def __init__(
        self,
        enabled: bool = True,
        profile_path: Optional[str] = None,
        language: str = "auto",
    ):
        self.enabled = enabled
        self.harm_filter = HarmFilter(enabled=enabled, language=language)
        self.user_model = UserModel(profile_path=profile_path)
        self.tone_detector = ToneDetector()
        self.language_layer = LanguageLayer()
        self.logic_layer = LogicLayer()
        self.self_eval = SelfEvaluator()
        self.spatial = SpatialReasoner()
        self.creative = CreativeEngine()
        self.naturalist = NaturalistLayer()
        self.music_layer = MusicLayer()

    # ------------------------------------------------------------ #
    # 1. Zarar filtri (2.10)
    # ------------------------------------------------------------ #

    def screen(self, command: str, language: str = "auto") -> HarmVerdict:
        """Buyruqni zarar chegarasiga tekshiradi (eng birinchi qadam)."""
        return self.harm_filter.check(command, language=language)

    # ------------------------------------------------------------ #
    # 2. Moslashtirish (2.6 + 2.12 + 2.1)
    # ------------------------------------------------------------ #

    def observe(self, message: str) -> dict:
        """Foydalanuvchi xabarini kuzatadi (profil signali yig'adi)."""
        self.tone_detector.detect(message)
        return self.user_model.observe(message)

    def adapt_system(self, system: str, message: str) -> str:
        """System prompt'ga moslashtirish qatlamini qo'shadi.

        Tartibi: language (2.1) -> user-model (2.6) -> tone (2.12).
        Faqat javob SIFATINI o'zgartiradi — maqsadli natijani emas.
        """
        adapted = self.language_layer.enrich_system(system, message)

        directives: list[str] = []
        directives.extend(self.user_model.adaptation_directives())

        tone_signal: ToneSignal = self.tone_detector.detect(message)
        tone_dir = self.tone_detector.directive(tone_signal)
        if tone_dir:
            directives.append(tone_dir)

        if directives:
            block = "\n\nUser adaptation:\n- " + "\n- ".join(directives)
            adapted = (adapted or "") + block
        return adapted

    def reasoning_suffix(self) -> str:
        """2.2 Mantiqiy CoT yo'naltirishi (system prompt oxiriga)."""
        return self.logic_layer.reasoning_directive()

    # ------------------------------------------------------------ #
    # 3. Ijro qatlami yordamchilari (2.4 / 2.11)
    # ------------------------------------------------------------ #

    def analyze_layout(self, regions: list[dict]) -> dict:
        """2.4 Fazoviy tahlil — UI/layout regionlarini tahlil qiladi."""
        return self.spatial.analyze_layout(regions)

    def creative_variants(self, prompt: str, n: int = 3,
                          complete_fn=None, system: Optional[str] = None):
        """2.11 Kreativ variantlar (operator ko'rib chiqadi)."""
        return self.creative.generate(prompt, n=n, complete_fn=complete_fn,
                                      system=system)

    def pick_creative(self, candidates, prefer: str = "balanced"):
        """2.11 Eng yaxshi variantni taklif qiladi (agent qaror qilmaydi)."""
        return self.creative.pick_best(candidates or [], prefer=prefer)

    # ------------------------------------------------------------ #
    # 2.2 Mantiq: tekshiruv + xavfsiz arifmetika
    # ------------------------------------------------------------ #

    def quick_math(self, expr: str) -> Optional[float]:
        """2.2 Oddiy arifmetikani xavfsiz hisoblaydi (tool kerak bo'lmagan joyda)."""
        return self.logic_layer.safe_math(expr)

    def verify_structure(self, output: Optional[str]) -> StructureCheck:
        """2.2 Chiqish strukturasi mantiqiy to'g'rimi (JSON/kod)."""
        return self.logic_layer.check_structure(output)

    # ------------------------------------------------------------ #
    # 2.4 Fazoviy + 2.8 Naturalist: muhit tahlili
    # ------------------------------------------------------------ #

    def spatial_file_tree(self, paths: list[str]) -> dict:
        """2.4 Fayl daraxti fazoviy tahlili (chuqurlik/hierarchiya)."""
        return self.spatial.analyze_file_tree(paths)

    def naturalist_summary(self, paths: list[str]) -> str:
        """2.8 Loyiha muhiti haqida ixcham xulosa (system prompt bloki)."""
        return self.naturalist.environment_summary(paths)

    def classify_paths(self, paths: list[str]) -> dict:
        """2.8 Fayl muhiti taqsimoti (til/kengaytma/katalog guruhlari)."""
        return self.naturalist.classify_paths(paths)

    # ------------------------------------------------------------ #
    # 2.3 Musiqa: so'rovni aniqlash + yo'naltirish
    # ------------------------------------------------------------ #

    def music_directive(self, message: str) -> str:
        """2.3 Musiqa/ovoz so'rovi bo'lsa — glossary+yo'naltirish, aks holda ''."""
        return self.music_layer.directive(message)

    # ------------------------------------------------------------ #
    # 4. Ishonch kalibratsiyasi (2.7)
    # ------------------------------------------------------------ #

    def evaluate(
        self,
        engine: str = "llm",
        status: str = "ok",
        output: str = "",
        tool_calls: Optional[list] = None,
        memory_hits: int = 0,
        healed: bool = False,
        verified: Optional[str] = None,
        resolver_score: Optional[float] = None,
        avg_logprob: Optional[float] = None,
    ) -> SelfEvalResult:
        """Javobga ishonch darajasini hisoblaydi (faqat metrika)."""
        return self.self_eval.evaluate(
            engine=engine, status=status, output=output,
            tool_calls=tool_calls, memory_hits=memory_hits, healed=healed,
            verified=verified, resolver_score=resolver_score,
            avg_logprob=avg_logprob,
        )

    # ------------------------------------------------------------ #
    # Status / stats
    # ------------------------------------------------------------ #

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "harm_filter": self.harm_filter.stats(),
            "user_model": self.user_model.stats(),
            "tone_detect": self.tone_detector.stats(),
            "language": self.language_layer.stats(),
            "logic": self.logic_layer.stats(),
            "self_eval": self.self_eval.stats(),
            "spatial": self.spatial.stats(),
            "creative": self.creative.stats(),
            "naturalist": self.naturalist.stats(),
            "music": self.music_layer.stats(),
        }
