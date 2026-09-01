"""
IGRIS BRAIN — 2.7 Intrapersonal Intelligence (funksional versiya) — core/self-eval
==================================================================================
O'zining ishonch darajasi, xato ehtimoli, resurs holatini baholash.

Bu chinakam o'z-onglilik EMAS — confidence calibration + uncertainty
estimation. Foydali va xavfsiz: agent "bu javobga unchalik ishonchim
yo'q" deya bilishi kerak.

Cheklov (qo'llanma): faqat METRIKA chiqaradi, xulq-atvorni operator
ruxsatisiz o'zgartirmaydi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SelfEvalResult:
    """Bitta javob/rezolyutsiya uchun o'z-o'zini baholash natijasi."""

    confidence: float = 0.0               # 0..1 kalibrlangan ishonch
    uncertainty: str = "high"             # low | medium | high
    signals: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "confidence": round(self.confidence, 3),
            "uncertainty": self.uncertainty,
            "signals": dict(self.signals),
            "notes": list(self.notes),
        }


# Signal og'irliklari — har bir manba ishonchga qanday ta'sir qiladi
WEIGHTS = {
    "engine_ok": 0.35,          # muvaffaqiyatli dvigatel
    "engine_llm": 0.25,         # LLM javobi (o'rtacha)
    "engine_fallback": 0.10,    # zaif/offline natija
    "tool_success": 0.20,       # tool'lar muvaffaqiyatli bajarildi
    "tool_fail": -0.15,         # tool xatosi
    "length_ok": 0.15,          # yetarli uzunlikdagi javob
    "length_short": -0.20,      # juda qisqa javob
    "memory_hit": 0.10,         # xotiradan topilgan kontekst
    "healed": -0.10,            # qayta tiklash bilan topilgan (shubhali)
    "verifier_ok": 0.10,        # struktura/verifikator tekshiruvidan o'tdi
    "verifier_repaired": -0.10, # JSON xato edi — tuzatildi (engil jarima)
    "verifier_fail": -0.25,     # struktur muammo hal qilinmadi (jiddiy jarima)
    "logprob": 0.15,            # OpenAI-mos logprob re-so'ruvi: o'rtacha token
                                # ehtimoli 0.5 dan yuqori -> ishonch oshadi,
                                # past -> tushadi (ixtiyoriy, 2x inference)
}


def _uncertainty(conf: float) -> str:
    if conf >= 0.7:
        return "low"
    if conf >= 0.45:
        return "medium"
    return "high"


class SelfEvaluator:
    """2.7 Ishonch kalibratori — faqat metrika chiqaradi.

    `evaluate(engine, status, output, tool_calls, memory_hits, healed)`
    -> SelfEvalResult. Agent xulq-atvorini o'zi o'zgartirmaydi.
    """

    def __init__(self):
        self._evals: int = 0

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
        """Ishonch darajasini hisoblaydi.

        Signal manbalari:
          - engine: deterministic/healed -> aniqroq; llm -> o'rtacha;
            offline/failed -> past
          - output uzunligi: bo'sh/juda qisqa -> past
          - tool_calls: muvaffaqiyat -> yuqori, xato -> past
          - memory_hits: xotira konteksti bor -> biroz yuqori
          - verified: "ok" (verifikator o'tdi) -> yuqori;
            "repaired" (xato edi, tuzatildi) -> engil past;
            "fail" (muammo qoldi) -> sezilarli past
          - resolver_score (0..1): deterministic/healed yo'lida resolverning
            o'z bahosi (0.6*rule_score + 0.4*coverage) — engine signalini
            SCALEY qiladi: kuchsiz rule mosligi -> past ishonch (barchasi
            1.0 bo'lib qolmaydi). `length_ok` ham shu bilan scaley qilinadi —
            zaif moslikdagi rezolyutsiya 0.825 floor'da qolib ketmaydi
            (rs=0.5 -> 0.5+0.175+0.075=0.75). LLM/cag/offline uchun
            ishlatilmaydi (length_ok 0.15 o'zgarishsiz).
          - avg_logprob (0..1): OpenAI-mos /v1/chat/completions ALOHIDA
            re-so'ruvidan o'rtacha token ehtimoli. 0.5 dan yuqori -> ishonch
            oshadi (max +0.15), past -> tushadi (max -0.15). None (Ollama
            eski/offline, yoki signal o'chirilgan) -> neytral.

        `verified` — A2 qo'shimchasi: native Ollama logprob qaytarmagani
        uchun verifikator natijasi ishlatiladi (struktura tekshiruvi /
        _verify_and_repair); `avg_logprob` esa ixtiyoriy OpenAI-mos logprob
        re-so'ruvi orqali QO'SHIMCHA ishonch signali bo'ladi.
        """
        self._evals += 1
        signals: dict[str, float] = {}
        notes: list[str] = []

        # resolver_score — deterministic/healed uchun BIR MARTA hisoblanadi
        # (engine VA length signallari shu bilan scaley qilinadi). None —
        # boshqa dvigatellar (llm/cag/weather/math/offline): o'zgarish yo'q.
        resolver_rs = None
        if resolver_score is not None and engine in ("deterministic", "healed"):
            resolver_rs = max(0.0, min(1.0, float(resolver_score)))

        # --- engine signali ---
        if status != "ok":
            signals["engine"] = WEIGHTS["engine_fallback"]
            notes.append(f"status={status}")
        elif engine in ("deterministic", "healed", "cag", "weather-quick", "math-quick"):
            # A2: `healed` ham shu yerda qo'llab-quvvatlanadi — ammo resolve()
            # oqimida healed doim status="partial" qaytaradi (status=="ok"
            # guard'i tufayli resolver_score hech qachon o'rnatilmaydi). Bu
            # bevosita SelfEvaluator API chaqiruvi uchun kelajakda ishlatilishi
            # mumkin (verified='ok' bilan bir xil naqsh).
            if resolver_rs is not None:
                # A2: resolver rule-sifat signali — engine_ok'ni proportsional
                # qiladi. rule_score=1.0 -> 0.35 (to'liq), 0.5 -> 0.175.
                signals["engine"] = WEIGHTS["engine_ok"] * resolver_rs
                notes.append(f"resolver_score={resolver_rs:.2f}")
            else:
                signals["engine"] = WEIGHTS["engine_ok"]
        elif engine in ("llm", "llm+tools", "llm-fast"):
            signals["engine"] = WEIGHTS["engine_llm"]
        elif engine == "offline":
            signals["engine"] = WEIGHTS["engine_fallback"]
            notes.append("engine=offline")
        else:
            signals["engine"] = WEIGHTS["engine_llm"]

        # --- tool signali ---
        tool_calls = tool_calls or []
        if tool_calls:
            def _tool_ok(t) -> bool:
                # chat tool_calls: {"tool", "result": {"ok": ...}}
                # executor tool_calls: {"ok": ...}
                if isinstance(t, dict):
                    if "ok" in t:
                        return bool(t.get("ok"))
                    res = t.get("result")
                    if isinstance(res, dict) and "ok" in res:
                        return bool(res.get("ok"))
                    return True  # natija yo'q — shartli muvaffaqiyat
                return True
            ok = sum(1 for t in tool_calls if _tool_ok(t))
            total = len(tool_calls)
            ratio = ok / total if total else 0.0
            signals["tool"] = WEIGHTS["tool_success"] * ratio
            if ok < total:
                signals["tool"] += WEIGHTS["tool_fail"]
                notes.append(f"tool_failures={total - ok}/{total}")

        # --- uzunlik signali ---
        # Deterministik dvigatellar (arifmetika, ob-havo, kesh) TABIIY ravishda
        # qisqa javob beradi — bunda qisqalik shubhali EMAS (kalibratsiya to'g'ri).
        length = len((output or "").strip())
        deterministic_short_ok = engine in (
            "deterministic", "math-quick", "weather-quick", "cag", "healed")
        if length == 0:
            signals["length"] = WEIGHTS["length_short"]
            notes.append("empty_output")
        elif length < 40 and not deterministic_short_ok:
            signals["length"] = WEIGHTS["length_short"]
            notes.append("very_short_output")
        else:
            # A2: kuchsiz rule (resolver_score < 1.0) — length_ok ham scaley
            # qilinadi: 0.825 floor 0.75 ga tushadi (rs=0.5 uchun), zaif moslik
            # to'liq ishonchga loyiq emas. resolver_score bo'lmasa (llm/cag/
            # weather/math) — avvalgi 0.15 (resolver_rs=None -> 1.0 scaley).
            lscale = resolver_rs if resolver_rs is not None else 1.0
            signals["length"] = WEIGHTS["length_ok"] * lscale

        # --- xotira signali ---
        if memory_hits and memory_hits > 0:
            signals["memory"] = min(WEIGHTS["memory_hit"], 0.05 * memory_hits)

        # --- healed signali ---
        if healed:
            signals["healed"] = WEIGHTS["healed"]
            notes.append("healed_resolution")

        # --- verifikator signali (A2) ---
        # None = tekshirilmagan (neytral); "ok" = o'tdi; "repaired" = xato
        # bo'lsa-da tuzatildi; "fail" = struktur muammo hal qilinmadi.
        if verified == "ok":
            signals["verifier"] = WEIGHTS["verifier_ok"]
        elif verified == "repaired":
            signals["verifier"] = WEIGHTS["verifier_repaired"]
            notes.append("verifier_repaired")
        elif verified == "fail":
            signals["verifier"] = WEIGHTS["verifier_fail"]
            notes.append("verifier_fail")

        # --- logprob signali (A2) ---
        # OpenAI-mos logprob re-so'ruvidan o'rtacha token ehtimoli (0..1).
        # > 0.5 -> ishonch oshadi (max +0.15), < 0.5 -> tushadi (max -0.15);
        # None (Ollama eski/offline, signal o'chiq) -> neytral, hech narsa
        # qo'shilmaydi (backward-compatible).
        if avg_logprob is not None:
            ap = max(0.0, min(1.0, float(avg_logprob)))
            signals["logprob"] = WEIGHTS["logprob"] * (2.0 * ap - 1.0)
            notes.append(f"avg_logprob={ap:.3f}")

        confidence = 0.5 + sum(signals.values())
        confidence = max(0.0, min(1.0, confidence))

        return SelfEvalResult(
            confidence=confidence,
            uncertainty=_uncertainty(confidence),
            signals=signals,
            notes=notes,
        )

    # ------------------------------------------------------------ #

    def stats(self) -> dict:
        return {"evaluations": self._evals}
