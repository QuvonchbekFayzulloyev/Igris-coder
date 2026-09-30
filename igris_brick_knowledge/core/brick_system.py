"""IGRIS Brick Knowledge System — Semantic Primitives (Bricks).

A Brick is an atomic meaning unit that knows its form in every language.
It doesn't "think" — it just IS. Bricks are composed via Knowledge rules
to produce code, natural language, or mixed outputs.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class BrickDomain(Enum):
    MATH = "math"
    CODE = "code"
    DATA = "data"
    TEXT = "text"
    SYSTEM = "system"
    CONCEPT = "concept"
    VERB = "verb"
    NOUN = "noun"
    TYPE = "type"


@dataclass
class Brick:
    """Atomic meaning unit — multilingual, composable."""

    canonical_id: str
    domain: BrickDomain
    surface_forms: Dict[str, List[str]]  # lang -> [form1, form2, ...]
    semantic_vector: List[float] = field(default_factory=lambda: [0.0] * 128)
    code_template: Optional[str] = None  # e.g. "np.linalg.inv({arg})"
    type_constraints: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.semantic_vector or len(self.semantic_vector) != 128:
            self.semantic_vector = self._hash_vector()

    def _hash_vector(self) -> List[float]:
        h = hashlib.sha256(self.canonical_id.encode()).digest()
        vec = []
        for i in range(128):
            byte_val = h[i % len(h)]
            vec.append((byte_val / 125.0) - 1.0)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def matches(self, query: str, lang: str = "en") -> float:
        """Return similarity score 0..1 for a query against surface forms."""
        query_lower = query.lower().strip()
        forms = self.surface_forms.get(lang, []) + self.surface_forms.get("en", [])
        if not forms:
            return 0.0
        best = 0.0
        for form in forms:
            form_lower = form.lower()
            if query_lower == form_lower:
                return 1.0
            if query_lower in form_lower or form_lower in query_lower:
                overlap = len(set(query_lower) & set(form_lower))
                total = len(set(query_lower) | set(form_lower))
                best = max(best, overlap / total if total else 0)
        return best

    def cosine_sim(self, other: "Brick") -> float:
        dot = sum(a * b for a, b in zip(self.semantic_vector, other.semantic_vector))
        return max(0.0, min(1.0, dot))


class BrickBank:
    """Registry of all bricks — lookup by ID, surface form, or domain."""

    def __init__(self):
        self._bricks: Dict[str, Brick] = {}
        self._index_by_domain: Dict[BrickDomain, List[str]] = {}
        self._build_defaults()

    def add(self, brick: Brick):
        self._bricks[brick.canonical_id] = brick
        self._index_by_domain.setdefault(brick.domain, []).append(brick.canonical_id)

    def get(self, canonical_id: str) -> Optional[Brick]:
        return self._bricks.get(canonical_id)

    def search(self, query: str, lang: str = "en", top_k: int = 5) -> List[Tuple[Brick, float]]:
        results = []
        for brick in self._bricks.values():
            score = brick.matches(query, lang)
            if score > 0.1:
                results.append((brick, score))
        results.sort(key=lambda x: -x[1])
        return results[:top_k]

    def by_domain(self, domain: BrickDomain) -> List[Brick]:
        ids = self._index_by_domain.get(domain, [])
        return [self._bricks[i] for i in ids if i in self._bricks]

    def _build_defaults(self):
        defaults = [
            Brick("concept_inverse", BrickDomain.MATH, {"uz": ["teskari", "teskariini"], "en": ["inverse", "invert"], "code": ["np.linalg.inv"]}, code_template="np.linalg.inv({arg})", examples=["matritsani teskari top", "invert the matrix"]),
            Brick("concept_sort", BrickDomain.MATH, {"uz": ["saralash", " tartiblash"], "en": ["sort", "ordering"], "code": ["sorted", "np.sort"]}, code_template="sorted({arg})", examples=["ro'yxatni sarala", "sort the list"]),
            Brick("concept_sum", BrickDomain.MATH, {"uz": ["yig'indi", "qo'shish"], "en": ["sum", "total", "add"], "code": ["sum", "np.sum"]}, code_template="sum({arg})", examples=["ro'yxatning yig'indisini hisobla"]),
            Brick("concept_max", BrickDomain.MATH, {"uz": ["katta", "maksimum"], "en": ["max", "maximum"], "code": ["max", "np.max"]}, code_template="max({arg})", examples=["eng kattasini top"]),
            Brick("concept_min", BrickDomain.MATH, {"uz": ["kichik", "minimum"], "en": ["min", "minimum"], "code": ["min", "np.min"]}, code_template="min({arg})", examples=["eng kichikini top"]),
            Brick("concept_mean", BrickDomain.MATH, {"uz": ["o'rtacha", "o'rtachani"], "en": ["mean", "average"], "code": ["np.mean"]}, code_template="np.mean({arg})", examples=["o'rtachasini hisobla"]),
            Brick("concept_filter", BrickDomain.DATA, {"uz": ["filtrlash", "saralab olish"], "en": ["filter", "select"], "code": ["filter", "[x for x in"]}, code_template="[x for x in {arg} if {cond}]", examples=["filtirla"]),
            Brick("concept_map", BrickDomain.DATA, {"uz": ["o'zgartirish", "xaritalash"], "en": ["map", "transform", "apply"], "code": ["map", "[f(x) for x in"]}, code_template="[{func}(x) for x in {arg}]", examples=["har birini o'zgartir"]),
            Brick("concept_find", BrickDomain.VERB, {"uz": ["topish", "qidirish"], "en": ["find", "search", "locate"], "code": []}, examples=["top", "qidir"]),
            Brick("concept_read", BrickDomain.VERB, {"uz": ["o'qish"], "en": ["read", "load", "open"], "code": ["open", "read_file"]}, code_template="open({arg})", examples=["faylni o'qish"]),
            Brick("concept_write", BrickDomain.VERB, {"uz": ["yozish"], "en": ["write", "save"], "code": ["open", "write_file"]}, code_template="open({arg}, 'w')", examples=["faylga yoz"]),
            Brick("concept_execute", BrickDomain.VERB, {"uz": ["bajarish", "ishga tushirish"], "en": ["run", "execute"], "code": ["subprocess.run", "os.system"]}, code_template="subprocess.run({arg})", examples=["ishga tushir"]),
            Brick("concept_fetch", BrickDomain.VERB, {"uz": ["olish", "yuklab olish"], "en": ["fetch", "download", "get"], "code": ["requests.get", "urllib"]}, code_template="requests.get({arg})", examples=["ma'lumotni olib kel"]),
            Brick("type_list", BrickDomain.TYPE, {"uz": ["ro'yxat", "massiv"], "en": ["list", "array"], "code": ["list", "np.array"]}, code_template="list({arg})", examples=["ro'yxatga aylantir"]),
            Brick("type_dict", BrickDomain.TYPE, {"uz": ["lug'at", "katalog"], "en": ["dict", "dictionary", "map"], "code": ["dict"]}, code_template="dict({arg})", examples=["lug'atga aylantir"]),
            Brick("type_string", BrickDomain.TYPE, {"uz": ["matn", "satr"], "en": ["string", "text"], "code": ["str"]}, code_template="str({arg})", examples=["matnga aylantir"]),
            Brick("type_number", BrickDomain.TYPE, {"uz": ["son", "raqam"], "en": ["number", "int", "float"], "code": ["int", "float"]}, code_template="float({arg})", examples=["songa aylantir"]),
            Brick("type_dataframe", BrickDomain.TYPE, {"uz": ["jadval"], "en": ["dataframe", "table"], "code": ["pd.DataFrame"]}, code_template="pd.DataFrame({arg})", examples=["jadvalga aylantir"]),
            Brick("verb_print", BrickDomain.VERB, {"uz": ["chop etish", "ko'rsatish"], "en": ["print", "show", "display"], "code": ["print"]}, code_template="print({arg})", examples=["chop et", "ko'rsat"]),
            Brick("verb_loop", BrickDomain.VERB, {"uz": ["aylanish", "takrorlash"], "en": ["loop", "iterate", "for"], "code": ["for x in"]}, code_template="for x in {arg}:", examples=["har birini qayta ishla"]),
            Brick("verb_if", BrickDomain.VERB, {"uz": ["agar", "shart"], "en": ["if", "condition", "check"], "code": ["if"]}, code_template="if {cond}:", examples=["agar bo'lsa"]),
            Brick("verb_return", BrickDomain.VERB, {"uz": ["qaytarish"], "en": ["return", "output"], "code": ["return"]}, code_template="return {arg}", examples=["natijani qaytar"]),
            Brick("math_matrix", BrickDomain.MATH, {"uz": ["matritsa"], "en": ["matrix"], "code": ["np.array"]}, code_template="np.array({arg})", type_constraints=["square_matrix"], examples=["matritsa yarat"]),
            Brick("math_eigenvalues", BrickDomain.MATH, {"uz": ["xususiy qiymatlar"], "en": ["eigenvalues"], "code": ["np.linalg.eigvals"]}, code_template="np.linalg.eigvals({arg})", type_constraints=["square_matrix"], examples=["xususiy qiymatlarni top"]),
            Brick("math_svd", BrickDomain.MATH, {"uz": ["singular qiymatlar"], "en": ["svd", "singular value decomposition"], "code": ["np.linalg.svd"]}, code_template="np.linalg.svd({arg})", examples=["SVD ni bajar"]),
            Brick("math_determinant", BrickDomain.MATH, {"uz": ["determinant"], "en": ["determinant", "det"], "code": ["np.linalg.det"]}, code_template="np.linalg.det({arg})", type_constraints=["square_matrix"], examples=["determinantni hisobla"]),
            Brick("math_transpose", BrickDomain.MATH, {"uz": ["transponitsiya"], "en": ["transpose"], "code": ["np.transpose", ".T"]}, code_template="{arg}.T", examples=["transponiatsiya qil"]),
            Brick("math_multiply", BrickDomain.MATH, {"uz": ["ko'paytirish"], "en": ["multiply", "product"], "code": ["np.dot", "@"]}, code_template="np.dot({a}, {b})", examples=["ko'paytir"]),
            Brick("math_sqrt", BrickDomain.MATH, {"uz": ["ildiz", "kvadrat ildiz"], "en": ["sqrt", "square root"], "code": ["np.sqrt", "math.sqrt"]}, code_template="np.sqrt({arg})", examples=["ildiz chiqar"]),
            Brick("math_log", BrickDomain.MATH, {"uz": ["logarifm"], "en": ["log", "logarithm"], "code": ["np.log", "math.log"]}, code_template="np.log({arg})", examples=["logarifmni hisobla"]),
            Brick("data_read_csv", BrickDomain.DATA, {"uz": ["csv o'qish"], "en": ["read csv", "load csv"], "code": ["pd.read_csv"]}, code_template="pd.read_csv({arg})", examples=["csv faylni o'qish"]),
            Brick("data_groupby", BrickDomain.DATA, {"uz": ["guruhlash"], "en": ["group by", "groupby"], "code": [".groupby"]}, code_template="{arg}.groupby({col})", examples=["guruhlab hisobla"]),
            Brick("data_merge", BrickDomain.DATA, {"uz": ["birlashtirish"], "en": ["merge", "join"], "code": ["pd.merge"]}, code_template="pd.merge({a}, {b})", examples=["jadvalni birlashtir"]),
            Brick("data_plot", BrickDomain.DATA, {"uz": ["grafik chizish"], "en": ["plot", "chart", "graph"], "code": [".plot", "plt.plot"]}, code_template="{arg}.plot()", examples=["grafik chiz"]),
            Brick("sys_file_exists", BrickDomain.SYSTEM, {"uz": ["fayl mavjudligini tekshirish"], "en": ["file exists", "check file"], "code": ["os.path.exists"]}, code_template="os.path.exists({arg})", examples=["fayl bormi tekshir"]),
            Brick("sys_mkdir", BrickDomain.SYSTEM, {"uz": ["papka yaratish"], "en": ["create directory", "mkdir"], "code": ["os.makedirs"]}, code_template="os.makedirs({arg}, exist_ok=True)", examples=["papka yarat"]),
            Brick("sys_http_get", BrickDomain.SYSTEM, {"uz": ["so'rov yuborish"], "en": ["http get", "request"], "code": ["requests.get"]}, code_template="requests.get({arg})", examples=["serverga so'rov yubor"]),
            Brick("verb_create", BrickDomain.VERB, {"uz": ["yaratish"], "en": ["create", "make", "build"], "code": []}, examples=["yarat", "qur"]),
            Brick("verb_delete", BrickDomain.VERB, {"uz": ["o'chirish"], "en": ["delete", "remove"], "code": ["os.remove", "del"]}, code_template="os.remove({arg})", examples=["o'chir"]),
            Brick("verb_update", BrickDomain.VERB, {"uz": ["yangilash"], "en": ["update", "modify"], "code": []}, examples=["yangila"]),
            Brick("verb_validate", BrickDomain.VERB, {"uz": ["tekshirish", "validatsiya"], "en": ["validate", "check", "verify"], "code": []}, examples=["tekshir", "tasdiqla"]),
            Brick("data_json_parse", BrickDomain.DATA, {"uz": ["json o'qish"], "en": ["parse json", "json load"], "code": ["json.loads"]}, code_template="json.loads({arg})", examples=["json ni parse qil"]),
            Brick("data_json_dump", BrickDomain.DATA, {"uz": ["json yozish"], "en": ["json dump", "to json"], "code": ["json.dumps"]}, code_template="json.dumps({arg})", examples=["json ga yoz"]),
            Brick("math_abs", BrickDomain.MATH, {"uz": ["mutlaq qiymat"], "en": ["absolute", "abs"], "code": ["abs", "np.abs"]}, code_template="abs({arg})", examples=["mutlaq qiymatni olish"]),
            Brick("math_round", BrickDomain.MATH, {"uz": ["yaxlitlash"], "en": ["round"], "code": ["round"]}, code_template="round({arg}, {decimals})", examples=["raxtani yaxlitla"]),
            Brick("math_range", BrickDomain.MATH, {"uz": ["diapazon", "oraliq"], "en": ["range", "interval"], "code": ["range"]}, code_template="range({start}, {end})", examples=["oraliq yarat"]),
            Brick("data_len", BrickDomain.DATA, {"uz": ["uzunlik", "soni"], "en": ["length", "count", "size"], "code": ["len"]}, code_template="len({arg})", examples=["nechta ekanligini hisobla"]),
            Brick("data_zip", BrickDomain.DATA, {"uz": ["birlashtirish"], "en": ["zip", "combine"], "code": ["zip"]}, code_template="list(zip({a}, {b}))", examples=["ro'yxatlarni birlashtir"]),
            Brick("data_enumerate", BrickDomain.DATA, {"uz": ["raqamlash"], "en": ["enumerate"], "code": ["enumerate"]}, code_template="enumerate({arg})", examples=["raqamlab chiq"]),
        ]
        for b in defaults:
            self.add(b)

    @property
    def size(self) -> int:
        return len(self._bricks)

    def all_ids(self) -> List[str]:
        return list(self._bricks.keys())
