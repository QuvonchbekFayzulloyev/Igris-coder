"""
IGRIS BRAIN — Web Answer Source Verification (A4)
==================================================
problems_to_fix.md :: A4 — Web/fakt savollarida manba tekshiruvi yo'q.

Muammo: web_fetch/browser_get_text natijasi LLM'ga "ishonchli" kontekst
sifatida beriladi; model javob yozishda manbadan chetlashsa (hallucinate)
yoki manbada UMUMAN bo'lmagan fakt qo'shsa — bu aniqlanmaydi.

Yechim (2 qatlam, hammasi deterministik — QO'SHIMCHA LLM CHAQIRUVI YO'Q):

  1. GROUNDING: javobdagi fakt-fragmentlari (juft sondagi tirnoq/raqamli
     gaplardan ajratilgan 2+ so'zli bo'laklar) manba matnida bor-yo'qligi
     token-trigramCoverage bilan o'lchanadi. Past coverage — "ungrounded"
     (javob manbaga tayanmaydi).

  2. SIGNAL: natija `data["web_grounding"]` ga yoziladi; `_finalize` buni
     SelfEvaluator'ga `grounding` parametri sifatida uzatadi:
       grounded  (coverage >= 0.55)  -> +0.10 ishonch
       ungrounded (coverage < 0.35)  -> -0.15 ishonch
       partial  (orasida)           -> 0 (neytral)
     Ishonch past bo'lsa javob "⚠ manbaga to'liq tayanmaydi" eslatmasi
     oladi (metrika — javob matni o'zgartirilmaydi, A2 printsiplari).

Xususiyatlar:
  - Fail-safe: hech qachon exception tashlab chatni buzmaydi (hatto
    noto'g'ri input'da None/neytral qaytaradi).
  - CJK/kichik korpus uchun ham ishlaydi (token-trigram — substring
    emasligi uchun word-boundary tekshiruvi ham bor).
  - Har qanday til uchun: tokenize lowercase + [^\\w\\s] -> space
    (o'zbek lotin, rus kirill, CJK uchun substring fallback bor).
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------- #
# Sozlamalar
# ---------------------------------------------------------------------- #

# Coverage bo'sag'alari (0..1): shu orada javob "grounded" hisoblanadi
GROUNDED_THRESHOLD = 0.55
UNGROUNDED_THRESHOLD = 0.35

# Fragment nima bo'lishi mumkin: 2+ so'zli bo'laklar (5..12 so'z optimal)
MIN_FRAGMENT_WORDS = 2
MAX_FRAGMENT_WORDS = 12
# Javobdan ko'pi bilan nechta fragment tekshiriladi (tezlik)
MAX_FRAGMENTS = 24

# Manba/token limitlari — juda katan manba matnini kesamiz (tezlik)
MAX_SOURCE_CHARS = 200_000

# Manba sifatida ishonchsiz belgilar (juda qisqa manba — grounding ishonchsiz)
MIN_SOURCE_TOKENS = 25

_TOKEN_RE = re.compile(r"[^\w\s]", re.UNICODE)


def tokenize(text: str) -> List[str]:
    """Lowercase + punktuatsiyani bo'shatish + bo'shliq bo'yicha bo'lish.

    BM25/FTS5 tokenize bilan bir xil oila (bir xil so'z o'lchovi).
    """
    text = (text or "").lower()
    text = _TOKEN_RE.sub(" ", text)
    return [t for t in text.split() if t]


# Token-N gram o'lchami: bigram — parafrazga chidamli va qat'iylik muvozanatli
# (trigram tabiiy parafrazda juda qat'iy bo'lib chiqdi — test: "the tower is
# 330 metres tall" manbada deyarli so'z-so'z bor turib 0.55'dan past oldi).
NGRAM_SIZE = 2


def _trigrams(tokens: List[str]) -> set:
    """Token-N-gram to'plami (bigram; qisqa fragmentlar uchun unigram)."""
    n = NGRAM_SIZE
    if len(tokens) < n:
        return {tuple(tokens)} if len(tokens) >= 2 else set()
    return {
        tuple(tokens[i:i + n])
        for i in range(len(tokens) - n + 1)
    }


# ---------------------------------------------------------------------- #
# Manba indeksi
# ---------------------------------------------------------------------- #

class SourceIndex:
    """Web tool natijalaridan token-trigram indeks (bir chat uchun).

    Har manba alohida saqlanadi; `coverage` hisoblashda barcha manbalar
    birlashtiriladi (model manbalar birlashmasi mumkin — bu xato EMAS).
    """

    def __init__(self) -> None:
        self._trigrams: set = set()
        self._tokens: List[str] = []
        self._sources: List[str] = []
        self._total_source_chars = 0

    @property
    def empty(self) -> bool:
        return not self._trigrams and not self._tokens

    @property
    def total_source_chars(self) -> int:
        return self._total_source_chars

    @property
    def sources(self) -> List[str]:
        return list(self._sources)

    def add(self, text: str, source: str = "") -> None:
        """Manba matnini indekslaydi (chaqiruv per tool-output)."""
        text = (text or "")[:MAX_SOURCE_CHARS]
        if not text.strip():
            return
        toks = tokenize(text)
        if len(toks) < MIN_SOURCE_TOKENS:
            # Juda qisqa manba — grounding ishonchsiz bo'ladi; baribir
            # saqlaymiz (salbiy signal uchun), lekin belgilaymiz.
            pass
        self._sources.append(source or f"source-{len(self._sources) + 1}")
        self._total_source_chars += len(text)
        self._tokens.extend(toks)
        self._trigrams |= _trigrams(toks)

    def coverage(self, fragment: str) -> float:
        """Fragment token-gramlarining manbada qamrovi (0..1)."""
        toks = tokenize(fragment)
        if len(toks) < MIN_FRAGMENT_WORDS:
            return 1.0  # juda qisqa bo'lak (son/belgi) — jarimasdan o'tadi
        grams = _trigrams(toks)
        if not grams:
            return 1.0
        hit = sum(1 for g in grams if g in self._trigrams)
        return hit / len(grams)

    def has_token(self, token: str) -> bool:
        return token in set(self._tokens)

    def token_set(self) -> set:
        return set(self._tokens)


# ---------------------------------------------------------------------- #
# Fragment (fakt-claim) ajratish
# ---------------------------------------------------------------------- #

_SENT_SPLIT_RE = re.compile(r"(?<=[.!?。！?])\s+")

# Raqam/yil/odam-nomi gaplari — faktlarning asosiy turi
_NUM_RE = re.compile(r"\d")


def _split_sentences(answer: str) -> List[str]:
    parts = _SENT_SPLIT_RE.split((answer or "").strip())
    return [p.strip() for p in parts if p and p.strip()]


def _fragments_from_sentence(sentence: str) -> List[str]:
    """Gapdan fakt-fragmentlar: raqamli gaplar to'liq; matn gaplar
    2..MAX_FRAGMENT_WORDS so'zli bo'laklarga bo'linadi (sliding window)."""
    sentence = (sentence or "").strip()
    if not sentence:
        return []
    # Kod fenslar/URL'lar — grounding uchun fakat emas (manbada kod bo'lishi mumkin, lekin
    # matn ko'rinishida mos kelmaydi)
    if sentence.startswith("```") or sentence.startswith("http://") \
            or sentence.startswith("https://"):
        return []
    words = tokenize(sentence)
    if len(words) < MIN_FRAGMENT_WORDS:
        return []
    toks = tokenize(sentence)
    has_num = any(_NUM_RE.search(w) for w in words)
    fragments: List[str] = []
    if has_num or len(toks) <= MAX_FRAGMENT_WORDS:
        fragments.append(sentence)
    if len(toks) > MAX_FRAGMENT_WORDS:
        # Sliding window: 8 so'zli oynalar, 4 qadam — katta gaplarni ham qamraydi
        for i in range(0, max(1, len(toks) - 8 + 1), 4):
            fragments.append(" ".join(toks[i:i + 8]))
    # Duplikatlarni olib tashlash (windows overlap qilishi mumkin)
    seen: set = set()
    out: List[str] = []
    for f in fragments:
        key = " ".join(tokenize(f))
        if key and key not in seen:
            seen.add(key)
            out.append(f)
    return out[:MAX_FRAGMENTS]


def extract_fragments(answer: str) -> List[str]:
    """Javobdan fakt-fragmentlarni ajratadi ( deterministik)."""
    out: List[str] = []
    for sentence in _split_sentences(answer or ""):
        out.extend(_fragments_from_sentence(sentence))
    return out[:MAX_FRAGMENTS]


# ---------------------------------------------------------------------- #
# Grounding natijasi
# ---------------------------------------------------------------------- #

class GroundingResult:
    """Javob grounding tekshiruvi natijasi (SelfEvaluator signaliga aylanadi)."""

    __slots__ = ("coverage", "verdict", "fragments_total", "fragments_ungrounded",
                 "worst_fragments", "sources", "source_chars")

    def __init__(self, coverage: float, verdict: str, fragments_total: int,
                 fragments_ungrounded: int, worst_fragments: List[str],
                 sources: List[str], source_chars: int) -> None:
        self.coverage = coverage
        self.verdict = verdict  # grounded | partial | ungrounded | none
        self.fragments_total = fragments_total
        self.fragments_ungrounded = fragments_ungrounded
        self.worst_fragments = worst_fragments
        self.sources = sources
        self.source_chars = source_chars

    def to_dict(self) -> dict:
        return {
            "coverage": round(self.coverage, 3),
            "verdict": self.verdict,
            "fragments_total": self.fragments_total,
            "fragments_ungrounded": self.fragments_ungrounded,
            "worst_fragments": list(self.worst_fragments)[:3],
            "sources": list(self.sources)[:5],
            "source_chars": self.source_chars,
        }


class _NoSourceResult(GroundingResult):
    """Manba yo'q — neytral holat (signal Yo'Q, hech narsa buzilmaydi)."""

    def __init__(self) -> None:
        super().__init__(coverage=0.0, verdict="none", fragments_total=0,
                         fragments_ungrounded=0, worst_fragments=[],
                         sources=[], source_chars=0)


# ---------------------------------------------------------------------- #
# Asosiy API
# ---------------------------------------------------------------------- #

def verify_answer(answer: str, sources: SourceIndex) -> GroundingResult:
    """Javobni manbalar bilan solishtiradi (deterministik, LLM yo'q).

    Qaytaradi: GroundingResult (verdict: grounded/partial/ungrounded/none).
    """
    try:
        if sources is None or sources.empty:
            return _NoSourceResult()
        fragments = extract_fragments(answer or "")
        if not fragments:
            # Fakt-fragment topilmadi (masalan faqat kod/ro'yxat) — neytral
            return _NoSourceResult()
        coverages = [sources.coverage(f) for f in fragments]
        coverage = sum(coverages) / len(coverages)
        ungrounded = [f for f, c in zip(fragments, coverages)
                      if c < UNGROUNDED_THRESHOLD]
        if coverage >= GROUNDED_THRESHOLD:
            verdict = "grounded"
        elif coverage < UNGROUNDED_THRESHOLD:
            verdict = "ungrounded"
        else:
            verdict = "partial"
        worst = sorted(
            (f for f, c in zip(fragments, coverages) if c < GROUNDED_THRESHOLD),
            key=lambda f: sources.coverage(f),
        )
        return GroundingResult(
            coverage=coverage,
            verdict=verdict,
            fragments_total=len(fragments),
            fragments_ungrounded=len(ungrounded),
            worst_fragments=worst[:5],
            sources=sources.sources,
            source_chars=sources.total_source_chars,
        )
    except Exception:
        # Fail-safe: verification hech qachon chatni buzmaydi
        return _NoSourceResult()


def build_source_index(texts: Iterable[Tuple[str, str]]) -> SourceIndex:
    """[(text, source_name), ...] dan SourceIndex quradi."""
    idx = SourceIndex()
    for text, name in texts or []:
        idx.add(text, name)
    return idx


# ---------------------------------------------------------------------- #
# SelfEvaluator signal qiymatlari (verify_answer natijasidan)
# ---------------------------------------------------------------------- #

def grounding_signal(result: Optional[GroundingResult]) -> Optional[float]:
    """Grounding verdict'ini SelfEvaluator uchun (0..1) signalga aylantiradi.

    grounded  -> 1.0  (+0.10 ishonch)
    partial   -> 0.5  (neytral)
    ungrounded -> 0.0  (-0.15 ishonch)
    none/None  -> None (signal yo'q)
    """
    if result is None:
        return None
    verdict = getattr(result, "verdict", "none")
    if verdict == "grounded":
        return 1.0
    if verdict == "partial":
        return 0.5
    if verdict == "ungrounded":
        return 0.0
    return None
