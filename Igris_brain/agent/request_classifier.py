"""
IGRIS BRAIN — RequestClassifier — S5 modullashtirish
====================================================
problems_to_fix.md :: S5 (qism) — igris_agent god-file'dan ajratilgan.

DETERMINISTIK so'rov klassifikatsiyasi (LLM chaqirmaydi, tarmoqqa chiqmaydi):

  1. PIPELINE TANLOV detektorlari — so'rov qaysi oila/turga kiradi:
       is_structure_request / is_creative_request / is_draw_request /
       is_ui_build_request / is_code_request / is_composition_request /
       is_file_request            -> bool
       classify_family            -> 'chat' | 'creator'
       classify_type(msg, family) -> weather/math/creative/structure/chat |
                                     file_task/ui_build/draw/web/composition/code
       classify_need(msg)         -> ikki bosqichli router (family + type)

  2. MAVZU/STACK ANIQLASH — so'rov obyekti va texnologiyalari:
       detect_subject / planned_tools / stack_plan / stack_guide /
       detect_code_stack / detect_db_tech / detect_orm

  3. STACK JADVALLARI — `agent_stack_data` modulida (yagona manba).

Fasadlar IgrisAgent API'sini saqlaydi: `IgrisAgent._classify_need` va h.k.
shu funksiyalarga DELEGATSIYA qiladi; nomlar/imzolar o'zgarmagan.

Web darvozasi/strategiyasi `web_strategy.py`da, math/weather tez yo'llari
`quick_paths.py`da — bu modul ularni qayta ishlatadi (yagona manba).
"""

from __future__ import annotations

import os
import sys
import re
from typing import Optional

_brain = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _brain not in sys.path:
    sys.path.insert(0, _brain)

from agent import quick_paths as quick_paths_mod
from web import web_strategy as web_strategy_mod
from agent.agent_stack_data import (
    STACK_PLANS,
    FRAMEWORK_STACK,
    ORM_STACK,
    LANG_STACK,
    DB_STACK,
    DB_DISPLAY_SUFFIX,
)

__all__ = [
    "STRUCTURE_REQUEST_WORDS", "CREATIVE_REQUEST_WORDS",
    "DRAW_STOP_WORDS", "CANNED_SCENE_SUBJECTS",
    "FILE_READ_VERBS", "FILE_EDIT_VERBS", "FILE_EXTENSIONS",
    "UI_APP_TARGETS", "CODE_LANG_HINTS", "CODE_FRAMEWORK_HINTS",
    "ORM_HINTS", "DATABASE_TECH_HINTS", "DB_CLASSIFY_EXCLUDE",
    "is_structure_request", "is_creative_request", "is_draw_request",
    "is_ui_build_request", "is_code_request", "is_composition_request",
    "is_file_request", "is_math_request",
    "classify_family", "classify_type", "classify_need",
    "detect_subject", "planned_tools", "stack_plan", "stack_guide",
    "detect_code_stack", "detect_db_tech", "detect_orm",
    "STACK_PLANS", "FRAMEWORK_STACK", "ORM_STACK", "LANG_STACK",
    "DB_STACK", "DB_DISPLAY_SUFFIX",
]

# ---------------------------------------------------------------------- #
# INTELLEKT 2.4/2.11 — so'rov markerlari
# ---------------------------------------------------------------------- #

STRUCTURE_REQUEST_WORDS = (
    "loyiha tuzilishi", "proyekt tuzilishi", "proekt tuzilishi",
    "fayl daraxti", "fayllar ro'yxati", "barcha fayllar", "qanday fayllar",
    "nechta fayl", "papka tuzilishi", "loyihada nima bor", "loyiha qanday",
    "project structure", "file tree", "folder structure",
    "what files", "how is the project organized", "what's in the project",
)

CREATIVE_REQUEST_WORDS = (
    "variant", "variants", "alternativ", "alternatives", "alternative",
    "g'oya", "g'oyalar", "ideas", "boshqa variant", "boshqa taklif",
    "options", "different ways", "yana qanday", "creative", "ijodiy",
)

# ------------------------------------------------------------ #
# IgrisAgent'dan KO'CHIRILGAN klassifikatsiya leksikasi
# ------------------------------------------------------------ #

DRAW_STOP_WORDS = frozenset((
    "rasm", "rasmini", "rasmida", "chiz", "chizing", "chizib", "chizish",
    "draw", "drawing", "yasa", "yasang", "make", "yarat", "yarating",
    "create", "qil", "qiling", "ber", "bering", "bitta", "bir",
    "please", "iltimos", "uchun", "va", "bilan", "the", "a", "an",
    # Sifat/miqyos so'zlari — asosiy obyektni bosib qolmasligi uchun
    "katta", "kichik", "go'zal", "chiroyli", "yangi", "eski", "zo'r",
    "big", "small", "beautiful", "new", "old", "red", "blue", "green",
    "yellow", "black", "white", "oq", "qora", "qizil", "ko'k", "yashil",
))

# art__draw_scene_svg tez sahnalashtiradigan ob'ektlar (CHAT_TOOLS_SYSTEM
# bilan sinxron) — draw clarify'da qaysi tool rejalanishini aniqlaydi.
CANNED_SCENE_SUBJECTS = frozenset((
    "apple", "house", "tree", "cat", "star", "heart", "car", "rocket",
    "flower", "mountain", "sun", "moon", "bird", "fish", "butterfly",
    "mushroom", "ball", "olma", "uy", "daraxt", "mushuk", "mashina",
    "raketa", "gul", "tog", "quyosh", "oy", "qush", "baliq", "kapalak",
    "qo'ziqorin", "to'p",
    # Kengaytirilgan kutubxona (LLM cheklovini kamaytirish): ko'proq so'rov
    # deterministik chizma yo'li bilan aniq bajariladi.
    "camel", "tuya", "dog", "it", "kuchuk", "owl", "mifqush", "oqqush",
    "duck", "o'rdak", "ordak", "robot", "plane", "samolyot", "airplane",
))

# Fayl vazifasi fe'llari — is_file_request/planned_tools BIR manbadan
# o'qiydi (ikki joyda takrorlansa, bir-biridan uzoqlashib qoladi).
FILE_READ_VERBS = (
    "o'qi", "read", "ko'rsat", "show", "och", "open", "tahlil", "analy",
    "tekshir", "inspect", "top", "find", "qidir", "search", "nima bor",
)
FILE_EDIT_VERBS = (
    "tahrir", "o'zgart", "edit", "update", "modify", "o'chir", "delete",
    "remove", "qo'sh", "append", "add", "patch",
)
FILE_EXTENSIONS = r"py|txt|md|json|js|ts|html|css|go|rs|c|cpp|h|yaml|yml|toml|ini|sh|bat|sql"

UI_APP_TARGETS: tuple = (
    ("dashboard", "dashboard"), ("todo", "todo"), ("ilova", "ilova"),
    ("app", "app"), ("kalkulyator", "kalkulyator"),
    ("calculator", "calculator"), ("login", "login"),
    ("profile", "profile"), ("settings", "settings"),
    ("sozlamalar", "sozlamalar"), ("uibuild", "uibuild"),
)

# Til nomlari — faqat ANIQ dasturlash tili (noaniq so'zlar YO'Q).
# 'dastur'/'script' bu yerda emas: ular til emas — "qanday dastur
# yozish kerak" yoki "script yoz" so'rovida til atribut qilinmaydi
# (subject bo'sh qoladi, clarify so'rov matniga tushadi). Uzunroq
# til nomlari qisqalaridan OLDIN keladi (javascript > js kabi).
# Patternlar regex-xavfsiz: lookaround `(?<![a-z0-9])`/`(?![a-z0-9])`
# so'z chegarasini beradi, `c#`/`c++` kabi maxsus belgilar ham ishlaydi.
CODE_LANG_HINTS: tuple = (
    ("python3", "Python"), ("python", "Python"), ("py", "Python"),
    ("javascript", "JavaScript"), ("js", "JavaScript"),
    ("typescript", "TypeScript"), ("ts", "TypeScript"),
    ("node", "JavaScript"),
    ("html", "HTML"), ("css", "CSS"),
    ("golang", "Go"), ("go", "Go"), ("rust", "Rust"), ("java", "Java"),
    ("kotlin", "Kotlin"), ("swift", "Swift"), ("dart", "Dart"),
    ("php", "PHP"), ("ruby", "Ruby"), ("perl", "Perl"),
    ("scala", "Scala"), ("lua", "Lua"), ("haskell", "Haskell"),
    ("matlab", "MATLAB"),
    ("sql", "SQL"), ("bash", "Bash"), ("shell", "Shell"),
    # 'c' OXIRIDA — aks holda c++/c#/css ichidagi 'c' ni o'ziga tortib oladi
    ("c++", "C++"), ("cpp", "C++"), ("c#", "C#"), ("csharp", "C#"),
    ("c", "C"),
)

# Framework/texnologiya nomlari -> (display nomi, bog'langan til).
# Kod so'rovlarida til BILAN BIRGA ko'rsatiladi: "obyekt: React
# (JavaScript)". Uzunroq nomlar qisqalaridan OLDIN keladi ("react native"
# > "react"), shuning uchun qisqa pattern aniq nomni yutib olmaydi.
CODE_FRAMEWORK_HINTS: tuple = (
    # JavaScript/TypeScript ekotizimi
    ("react native", "React Native", "JavaScript"),
    ("next.js", "Next.js", "JavaScript"),
    ("sveltekit", "SvelteKit", "JavaScript"),
    ("nuxt", "Nuxt", "JavaScript"),
    ("svelte", "Svelte", "JavaScript"),
    ("gatsby", "Gatsby", "JavaScript"),
    ("react", "React", "JavaScript"),
    ("redux", "Redux", "JavaScript"),
    ("vuex", "Vuex", "JavaScript"),
    ("vue", "Vue", "JavaScript"),
    ("angular", "Angular", "TypeScript"),
    ("express", "Express", "JavaScript"),
    ("jquery", "jQuery", "JavaScript"),
    ("electron", "Electron", "JavaScript"),
    ("node.js", "Node.js", "JavaScript"),
    ("three.js", "Three.js", "JavaScript"),
    ("nestjs", "NestJS", "TypeScript"),
    ("fastify", "Fastify", "JavaScript"),
    ("tailwind", "Tailwind CSS", "CSS"),
    ("bootstrap", "Bootstrap", "CSS"),
    ("sass", "Sass", "CSS"),
    ("scss", "SCSS", "CSS"),
    # Python ekotizimi
    ("django", "Django", "Python"),
    ("flask", "Flask", "Python"),
    ("fastapi", "FastAPI", "Python"),
    ("pytorch", "PyTorch", "Python"),
    ("tensorflow", "TensorFlow", "Python"),
    ("pandas", "pandas", "Python"),
    ("numpy", "NumPy", "Python"),
    ("scikit-learn", "scikit-learn", "Python"),
    ("sklearn", "scikit-learn", "Python"),
    ("matplotlib", "Matplotlib", "Python"),
    ("beautifulsoup", "Beautiful Soup", "Python"),
    ("selenium", "Selenium", "Python"),
    ("pytest", "pytest", "Python"),
    ("celery", "Celery", "Python"),
    ("sqlalchemy", "SQLAlchemy", "Python"),
    # PHP / Ruby ekotizimi
    ("laravel", "Laravel", "PHP"),
    ("symfony", "Symfony", "PHP"),
    ("wordpress", "WordPress", "PHP"),
    ("codeigniter", "CodeIgniter", "PHP"),
    ("rails", "Ruby on Rails", "Ruby"),
    ("sinatra", "Sinatra", "Ruby"),
    # Java / Go ekotizimi
    ("spring", "Spring", "Java"),
    ("hibernate", "Hibernate", "Java"),
    ("maven", "Maven", "Java"),
    ("gradle", "Gradle", "Java"),
    # C#/.NET / mobil / o'yin
    ("asp.net", "ASP.NET", "C#"),
    (".net", ".NET", "C#"),
    ("xamarin", "Xamarin", "C#"),
    ("unity", "Unity", "C#"),
    ("flutter", "Flutter", "Dart"),
    ("swiftui", "SwiftUI", "Swift"),
    ("unreal", "Unreal Engine", "C++"),
    ("tauri", "Tauri", "Rust"),
)

# ORM/aloqa qatlami nomlari -> display nomi. Kod so'rovida framework/til/
# DB bilan BIRGA aniqlanadi ("react + postgresql + prisma" -> React +
# PostgreSQL + Prisma) va stack rejasiga o'z qo'llanmasi qo'shiladi
# (Prisma -> npx prisma init/migrate/generate). Uzunroq nomlar avval.
ORM_HINTS: tuple = (
    ("drizzle", "Drizzle ORM"),
    ("sequelize", "Sequelize"),
    ("typeorm", "TypeORM"),
    ("mongoose", "Mongoose"),
    ("prisma", "Prisma"),
    ("knex", "Knex"),
)

# VEB SAYT texnologiyalari — S5: web_strategy.py'da (yagona manba).
# Bu yerda alias — testlar/klass attribute foydalanuvchilari mosligi uchun.
WEB_TECH_HINTS: tuple = web_strategy_mod.WEB_TECH_HINTS
WEB_URL_MARKERS: tuple = web_strategy_mod.WEB_URL_MARKERS

# MA'LUMOTLAR BAZASI texnologiyalari — Postgres/MySQL/MongoDB/Redis...
# `detect_db_tech` kod so'rovidan DB turini aniqlaydi: `database`
# maydoniga yoziladi, clarify/subject'da ko'rsatiladi ("DB: PostgreSQL") va
# stack rejasi shu asosda moslashadi (psql/mysql/mongosh/redis-cli...).
# Uzunroq nomlar qisqalaridan OLDIN keladi ("postgresql" > "postgres",
# "sql server" birinchi). `db` — generic DB rejasi uchun kalit.
# (pattern, display) — stack kaliti YO'Q: yagona manba DB_STACK
# (display -> stack rejasi). `db` — generic DB rejasi kaliti.
DATABASE_TECH_HINTS: tuple = (
    # UZUN/QATTIQ birikmalar ENG AVVAL — aks holda 'postgres' 'neon postgres'ni,
    # 'firebase' 'firebase realtime'ni, 'redis' 'upstash'ni yutib olardi.
    ("firebase realtime database", "Firebase Realtime"),
    ("firebase realtime", "Firebase Realtime"),
    ("neon postgres", "Neon Postgres"),
    ("neon db", "Neon Postgres"),
    ("neon.tech", "Neon Postgres"),
    ("upstash", "Upstash"),
    ("sql server", "SQL Server"),
    ("microsoft sql", "SQL Server"),
    ("mssql", "SQL Server"),
    ("postgresql", "PostgreSQL"),
    ("postgres", "PostgreSQL"),
    ("psql", "PostgreSQL"),
    ("mariadb", "MariaDB"),
    ("mysql", "MySQL"),
    ("mongodb", "MongoDB"),
    ("mongo", "MongoDB"),
    ("redis", "Redis"),
    ("sqlite3", "SQLite"),
    ("sqlite", "SQLite"),
    ("clickhouse", "ClickHouse"),
    ("cassandra", "Cassandra"),
    ("dynamodb", "DynamoDB"),
    ("elasticsearch", "Elasticsearch"),
    ("neo4j", "Neo4j"),
    ("oracle", "Oracle"),
    ("firebase", "Firebase"),
    ("supabase", "Supabase"),
    # Qisqa "realtime database" FAKAT kontekstda (firebase realtime yuqorida),
    # lekin alohida emas — aks holda 'supabase realtime database' kabi
    # so'rovlarni Firebase Realtime'ga yutib olardi (avval supabase keladi).
    ("realtime database", "Firebase Realtime"),
    # --- kengaytirilgan qamrov: vector / time-series / warehouse / cache ---
    ("timescaledb", "TimescaleDB"),
    ("timescale", "TimescaleDB"),
    ("cockroachdb", "CockroachDB"),
    ("planetscale", "PlanetScale"),
    ("scylladb", "ScyllaDB"),
    ("influxdb", "InfluxDB"),
    ("memcached", "Memcached"),
    ("memcache", "Memcached"),
    ("valkey", "Valkey"),
    ("duckdb", "DuckDB"),
    ("questdb", "QuestDB"),
    ("snowflake", "Snowflake"),
    ("redshift", "Redshift"),
    ("bigquery", "BigQuery"),
    ("chromadb", "Chroma"),
    ("chroma", "Chroma"),
    ("qdrant", "Qdrant"),
    ("milvus", "Milvus"),
    ("pinecone", "Pinecone"),
    ("weaviate", "Weaviate"),
    ("faiss", "FAISS"),
    ("pgvector", "pgvector"),
    ("couchdb", "CouchDB"),
    ("couchbase", "Couchbase"),
    ("hbase", "HBase"),
    ("arangodb", "ArangoDB"),
    ("arango", "ArangoDB"),
    ("etcd", "etcd"),
    ("rocksdb", "RocksDB"),
    ("leveldb", "LevelDB"),
    ("yugabytedb", "YugabyteDB"),
    ("yugabyte", "YugabyteDB"),
    ("tidb", "TiDB"),
    ("libsql", "libSQL"),
    ("tursodb", "Turso"),
    ("turso", "Turso"),
    # --- obyekt saqlash (S3-mos) — uzunroq birikmalar qisqalaridan OLDIN ---
    ("google cloud storage", "Google Cloud Storage"),
    ("gcs", "Google Cloud Storage"),
    ("azure blob storage", "Azure Blob"),
    ("azure blob", "Azure Blob"),
    ("cloudflare r2", "Cloudflare R2"),
    ("digitalocean spaces", "DigitalOcean Spaces"),
    ("do spaces", "DigitalOcean Spaces"),
    ("backblaze b2", "Backblaze B2"),
    ("backblaze", "Backblaze B2"),
    ("amazon s3", "S3"),
    ("aws s3", "S3"),
    ("s3 bucket", "S3"),
    ("s3", "S3"),
    ("minio", "MinIO"),
    # --- realtime / serverless ---
    ("firestore", "Firestore"),
    ("xata", "Xata"),
    ("cloudflare d1", "Cloudflare D1"),
    ("surreal db", "SurrealDB"),
    ("surrealdb", "SurrealDB"),
    ("singlestore", "SingleStore"),
    ("tarantool", "Tarantool"),
    ("rockset", "Rockset"),
    ("airtable", "Airtable"),
    # --- stream / navbat ---
    ("apache kafka", "Kafka"),
    ("kafka", "Kafka"),
    ("rabbitmq", "RabbitMQ"),
    ("apache pulsar", "Apache Pulsar"),
    ("pulsar", "Apache Pulsar"),
    ("nats", "NATS"),
    ("redpanda", "Redpanda"),
)

# Klassifikatsiya trigger'idan CHIQARILGAN DB nomlari — oddiy so'z bo'lib
# qolishi mumkin ('oracle'/'snowflake'/'redshift'/'chroma'/'pinecone' nima?
# -> bilim savoli chat'da qoladi; lekin aniqlash (detect_db_tech) hamon
# ishlaydi: "snowflake baza yoz" -> code 'baza' so'zi orqali).
DB_CLASSIFY_EXCLUDE: frozenset = frozenset(
    {"Oracle", "Snowflake", "Redshift", "Chroma", "Pinecone", "Kafka"})


def is_structure_request(message: str) -> bool:
    """INTELLEKT 2.4: loyiha strukturasi so'rovi (spatial kontekst kerakmi)."""
    low = (message or "").lower()
    return any(w in low for w in STRUCTURE_REQUEST_WORDS)


def is_creative_request(message: str) -> bool:
    """INTELLEKT 2.11: kreativ so'rov (variant/g'oya so'ralyaptimi)."""
    low = (message or "").lower()
    if not any(re.search(rf"\b{re.escape(w)}\b", low) for w in CREATIVE_REQUEST_WORDS):
        return False
    # So'rovchi fe'l yoki savol belgisi kerak — "variant" so'zi boshqa
    # kontekstda ham uchraydi ("Python variantini yoz"), uni ushlamaymiz.
    if (re.search(r"\b(ber|ko'rsat|yoz|ayt|chiqar|give|show|suggest|make|create|generate|propose)\b", low)
            or "options for" in low or "ideas for" in low
            or low.rstrip().endswith("?")):
        return True
    return False


def is_math_request(message: str) -> Optional[str]:
    """Sof arifmetik ifoda so'rovi — S5: quick_paths.is_math_request."""
    return quick_paths_mod.is_math_request(message)


# Vizual artefakt nomlari (sufli) — "sxemani yasa", "infografika tuzib ber"
# kabi so'rovlarni chizma pipeline'iga yo'naltiradi (faqat DB kontekstida emas).
DRAW_ARTIFACT_WORDS: tuple = (
    "sxema", "skema", "diagramma", "diagram", "infografika",
    "flowchart", "grafig", "chart", "skitsa", "eskiz", "animatsiya",
)

# DB kontekstidagi so'zlar — "database schema" kod vazifasi, chizma EMAS.
_DB_CONTEXT_RE = re.compile(
    r"\b(?:baza|database|db|sql|ddl|table|jadval|schema|migratsiya|migration|"
    r"postgres|mysql|sqlite|mongo|redis)\b", re.IGNORECASE)

# Davomiylik (continuation) signallari — "endi uni yon tomondan chiq",
# "qayerda yaratilgan?", "vazifani yakunladingmi?" kabi qisqa
# davomiy so'rovlarda OLDINGI pipeline meros qilib oladi (chat oilasi
# qaytarmasdan, agent suhbat kontekstini yo'qotmaydi).
_CONTINUATION_RE = re.compile(
    r"\b(?:endi|yana|ham|uni|shuni|o['’]sha|keyin|qayta|davom|qo['’]sh|"
    r"tuzat|o['’]zgartir|yangila|kattala|kichikla|yaxshila|"
    r"vazifa|vazifani|saqlangan|yaratilgan|yozilgan|chizilgan|qurilgan|"
    r"tayyorlangan|natija|qayerda|qanday|manzil|fayl|file|"
    r"output|details?|again|also|more|update|changed?|improve|result)\b",
    re.IGNORECASE)

CREATOR_NEEDS: frozenset = frozenset(
    {"draw", "code", "ui_build", "web", "composition", "file_task"})


def is_continuation(message: str) -> bool:
    """Davomiy (oldingi vazifaga tayanuvchi) so'rovmi?

    Faqat ANIQ reference signali bo'lsa True — qisqa lekin mustaqil savol
    ("salom", "buxoro qaysi davlatda?") meros OLINMAYDI.
    """
    msg = (message or "").strip()
    if not msg:
        return False
    return bool(_CONTINUATION_RE.search(msg.lower()))


def _first_user_text(history: Optional[list]) -> str:
    """Suhbat boshidagi (kontekst manbasi) foydalanuvchi xabari."""
    for item in history or []:
        if not isinstance(item, dict):
            continue
        if item.get("role") == "user":
            text = item.get("content") or item.get("text") or ""
            if str(text).strip():
                return str(text)
    return ""


def is_draw_request(message: str) -> bool:
    """Rasm/UI chizish so'rovi bo'lsa — CAG keshlanmaydi (tool kerak).

    Oddiy rasm chizish va sahna obyektlari uchun. 'ui' ham rasm
    degani bo'lishi mumkin, lekin "UI qur" kabi so'rovlarda
    `is_ui_build_request` avval tekshiriladi va ustun keladi.
    """
    low = (message or "").lower()
    draw_words = ("rasm", "rasmini", "rasmida", "chiz", "chizing",
                  "chizib", "chizish", "draw", "drawing", "ui",
                  # Sifat/miqyos so'zlari — rasm kontekstida
                  "go'zal", "chiroyli",
                  "big", "small", "beautiful", "new",
                  "red", "blue", "green", "yellow", "black",
                  "white", "oq", "qora", "qizil", "ko'k", "yashil",
                  # Sahna obyektlari (rasm/ilova chizish)
                  "sahifa", "logo", "icon", "mockup", "poster",
                  "banner", "avatar", "card", "image", "picture")
    for w in draw_words:
        if re.search(rf"\b{re.escape(w)}\b", low):
            return True
    # VIZUAL ARTEFAKT NOMI (sufli birikma): "sxemani yasa", "infografika
    # tuzib ber", "diagrammani chiz" — ular rasm/chizma pipeline'iga ketadi.
    # Diqqat: DB kontekstida "schema" chizma EMAS ("database schema" -> code),
    # shuning uchun baza/bazaviy so'zlar bo'lsa shu shox ishlatilmaydi.
    if not _DB_CONTEXT_RE.search(low):
        for w in DRAW_ARTIFACT_WORDS:
            if re.search(rf"\b{re.escape(w)}\w*\b", low):
                return True
    return False


def is_ui_build_request(message: str) -> bool:
    """Interaktiv UI/ilova qurish so'rovi (art__ui_build_spec tool'iga mos).

    Oddiy chizma (rasm chiz) bu yerga TUSHMADI — chizma `draw` pipeline'iga
    ketadi. UI qurish = real interaktiv ekran: app/ilova/todo + qur/yarat
    fe'llari (yoki to'g'ridan-to'g'ri app/ilova/todo nomi).
    """
    low = (message or "").lower()
    ui_targets = ("app", "ilova", "todo", "vazifalar", "interaktiv",
                  "uibuild", "ui", "kalkulyator", "calculator", "dashboard")
    build_verbs = ("qur", "qurib", "quring", "yarat", "yasa", "build",
                   "make", "create")
    has_target = any(w in low for w in ui_targets)
    has_verb = any(w in low for w in build_verbs)
    if has_target and has_verb:
        return True
    return bool(re.search(r"\b(app|ilova|todo|uibuild|kalkulyator|calculator|dashboard|interaktiv)\b", low))


def is_code_request(message: str) -> bool:
    """Kod/fayl vazifasi — write_file/run/test tool'lariga mos.

    Framework/texnologiya nomi aytilgan bo'lsa ham kod vazifasi hisoblanadi
    ("django bilan backend yoz" -> Django kod vazifasi) — til aniqlash
    uchun emas, KLASSIFIKATSIYA uchun framework ro'yxati ham tekshiriladi.
    """
    low = (message or "").lower()
    # Uzbek so'zlari sufiklari bilan: "kod" → "kodini", "fayl" → "faylni"
    # ("o'yinini" kabi shakllar ham shu sababli ushlanadi — oldingi qatlamda
    #  faqat \b o'yin\b aniq so'z chegarasi edi va "o'yinini" tushib qolgan)
    for w in ("fayl", "file", "dastur", "kod", "tuzat"):
        if re.search(rf"\b{re.escape(w)}\w*\b", low):
            return True
    # YARATILADIGAN ARTEFAKT (sufli): "o'yinini yasab ber", "loyihani qur",
    # "skriptni yoz" — bu kod vazifasi (write_file + run_command).
    for w in ("o'yin", "oyin", "ilova", "loyiha", "skript", "servis",
              "algoritm", "modul", "bot"):
        if re.search(rf"\b{w}\w*\b", low):
            return True
    # Qolgan inglizcha so'zlar — aniq so'z chegarasi
    for w in ("script", "function", "class", "debug", "fix",
              "python", "html", "css", "test", "bug",
              "baza", "database", "code",
              "powerpoint", "pptx", "ppt", "taqdimot",
              "prezentatsiya", "presentation",
              "game", "o'yin", "mini game", "gamer",
              "endpoint", "router", "server", "client",
              "android", "ios", "windows", "linux"):
        if re.search(rf"\b{re.escape(w)}\b", low):
            return True
    for pat in ("backend", "frontend", "api"):
        if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
            return True
    for pat, _fname, _flang in CODE_FRAMEWORK_HINTS:
        if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
            return True
    for pat, dname in DATABASE_TECH_HINTS:
        if dname in DB_CLASSIFY_EXCLUDE:
            continue
        if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
            return True
    return False


def is_composition_request(message: str) -> bool:
    """Kompozitsiya / qatlamli qurish so'rovi (CompositionEngine'ga mos)."""
    low = (message or "").lower()
    comp_words = ("kompozitsiya", "composition", "qatlam", "layer",
                  "wbs", "bom", "brick", "tizim qur", "reja qur",
                  "build plan", "komponent")
    return any(re.search(rf"\b{re.escape(w)}\b", low) for w in comp_words)


def is_file_request(message: str) -> bool:
    """Fayl tahrirlash/tahlil so'rovi — read_file/apply_patch/write_file'ga mos.

    Kod YARATISH ("dastur yoz", "kod yoz", "todo.py yarat") bu yerga
    TUSHMAYDI — `code` pipeline'iga ketadi. Fayl vazifasi = MAVJUD fayl
    bilan ishlash: o'qish, tahlil, tahrir, o'chirish, tarkibini so'rash.
    Signal: fayl kengaytmasi (.py/.txt/.json...) yoki `fayl/file` so'zi +
    tahrir/tahlil fe'li (yaratish fe'llari — code'ga).
    """
    low = (message or "").lower()
    has_ext = bool(re.search(
        rf"\.(?:{FILE_EXTENSIONS})\b", low))
    has_create = bool(re.search(r"\b(yarat|create|yoz|write|qur|build)\w*", low))
    has_file_noun = bool(re.search(r"\b(fayl|file)\w*", low))
    read_edit_verb = bool(re.search(
        r"\b(" + "|".join(FILE_READ_VERBS + FILE_EDIT_VERBS) + r")\w*",
        low))
    # Kengaytma + o'qish/tahrir fe'li — aniq fayl vazifasi ("calc.py ni
    # o'qib ber va kod yoz" kabi aralash so'rovlar ham file_task bosh
    # pipeline bo'ladi, code esa sub-pipeline).
    if has_ext and read_edit_verb:
        return True
    if has_create:
        return False
    if has_ext:
        return True
    return bool(has_file_noun and read_edit_verb)


# ---------------------------------------------------------------- #
# IKKI BOSQICHLI ROUTER — agentic architecture §3.3.a
# ---------------------------------------------------------------- #
# Bosqich 1: oilani aniqlash (n=2) — chat-family yoki creator-family.
# Bosqich 2: tur aniqlash (n≤5) — oila ichida aniq pipeline turi.
#
# Nima uchun: 8 variantlik klassifikator kichik mahalliy modelda
# (qwen2.5-coder/qwen3 on Ollama) ≤5 variantlik ishonch chegarasidan
# oshadi. Ikki bosqichga ajratish har bir bosqichda qaror yuzasini
# kamaytiradi, aniqlikni oshiradi.
# ---------------------------------------------------------------- #

def classify_family(message: str) -> str:
    """Bosqich 1: oilani aniqlaydi — 'chat' yoki 'creator'.

    chat-family: javob o'zi matn (suhbat, matematika, ob-havo,
        kreativ, loyiha strukturasi).
    creator-family: artifact ishlab chiqariladi va review bosqichidan
        o'tishi kerak (chizma, kod, UI, veb, kompozitsiya, fayl).
    """
    msg = (message or "").lower()
    # --- creator-family signal'lari (birortasi topilsa → creator) ---
    # 1. URL / veb brauzer ehtiyoji
    if web_strategy_mod.needs_web(message):
        return "creator"
    # 2. Rasm/chizish so'rovi
    if is_draw_request(msg):
        return "creator"
    # 3. UI/ilova qurish so'rovi
    if is_ui_build_request(msg):
        return "creator"
    # 4. Kod/fayl vazifasi — framework nomlari, DB nomlari,
    #    kengaytma + o'qish/tahrir fe'llari
    if is_code_request(msg):
        return "creator"
    # 5. Kompozitsiya / qatlamli qurish
    if is_composition_request(msg):
        return "creator"
    # 6. Fayl vazifasi (ui_build'dan oldin — "todo.txt" adashmasligi uchun)
    if is_file_request(message):
        return "creator"
    # --- chat-family (default) ---
    return "chat"


def classify_type(message: str, family: str) -> str:
    """Bosqich 2: oila ichida aniq pipeline turini aniqlaydi (n≤5).

    chat-family → (weather, math, creative, structure, chat)
    creator-family → (file_task, ui_build, draw, web, composition, code)
    """
    msg = (message or "").lower()
    if family == "creator":
        # creator-family: bosqich 1 da allaqachon bir umumiy tekshiruv
        # o'tkazilgan — endi aniq tur aniqlash kerak.
        # file_task OLDIN — "todo.txt" kabi kengaytma + fe'l;
        # ui_build OLDIN — "todo app qur" adashmasligi uchun.
        if is_file_request(message):
            return "file_task"
        if is_ui_build_request(msg):
            return "ui_build"
        if is_draw_request(msg):
            return "draw"
        if web_strategy_mod.needs_web(message):
            return "web"
        if is_composition_request(msg):
            return "composition"
        if is_code_request(msg):
            return "code"
        # default — creator oilasida lekin aniqlanmagan → code
        return "code"
    else:
        # chat-family: weather, math, creative, structure, chat
        if quick_paths_mod.WEATHER_RE.search(msg):
            return "weather"
        if is_math_request(msg) is not None:
            return "math"
        if is_creative_request(msg):
            return "creative"
        if is_structure_request(msg):
            return "structure"
        return "chat"


def classify_need(message: str, history: Optional[list] = None) -> str:
    """So'rov zarurat turini aniqlaydi — ikki bosqichli router.

    Bosqich 1: oila (chat yoki creator) — n=2, ishonchli.
    Bosqich 2: tur aniqlash (n≤5) — oila ichida kichik tanlov.

    Tezkor deterministik detektorlar (LLM chaqirmaydi).

    KONTEKST MEROSI (3-bosqich): qisqa davomiy so'rov ("endi uni yon
    tomondan chiq", "qayerda yaratilgan?") o'zi chat oilasiga tushsa ham,
    suhbat OLDIN creator pipeline'da bo'lsa — o'sha pipeline meros qilib
    olinadi (agent vazifani davom ettiradi, matnli javobga qaytmaydi).
    Yangi mavzuli uzun so'rovga meros SOLINMAYDI.
    """
    family = classify_family(message)
    need = classify_type(message, family)
    if family != "chat" or not history or need in CREATOR_NEEDS:
        return need
    if not is_continuation(message):
        return need
    origin = _first_user_text(history)
    if not origin or origin.strip() == (message or "").strip():
        return need
    if classify_family(origin) == "creator":
        return classify_type(origin, "creator")
    return need


def detect_subject(message: str, need: str) -> str:
    """So'rovdan MAVZU OBYEKTINI ajratadi (LLMsiz).

    Qaytaradi: qisqa obyekt/maqsad ('' bo'lishi mumkin — so'rovda
    aniq obyekt yo'q). Har bir zarurat turi o'z ekstraktoriga ega:
      weather  -> shahar nomi (WEATHER_STOP'da bo'lmagan so'z)
      math     -> arifmetik ifoda
      draw     -> chiziladigan narsa (fe'l/stop-so'zlardan tozalanadi)
      ui_build -> ilova turi (dashboard/todo/calculator...)
      web      -> URL yoki tadqiqot mavzusi
      code     -> dasturlash tili
    """
    msg = (message or "").strip()
    low = msg.lower()
    if need == "weather":
        for w in re.findall(r"[a-zа-яёüğşöçı']+", low):
            if w not in quick_paths_mod.WEATHER_STOP and len(w) >= 2:
                return w
        return ""
    if need == "math":
        return is_math_request(msg) or ""
    if need == "draw":
        tokens = re.findall(r"[a-zа-яёüğşöçı']+", low)
        # Taniqli sahna ob'ekti (2 harfli uy/oy ham) — birinchi o'rin
        for w in tokens:
            if w in CANNED_SCENE_SUBJECTS:
                return w
        words = [w for w in tokens
                 if w not in DRAW_STOP_WORDS and len(w) >= 3]
        return words[0] if words else ""
    if need == "ui_build":
        for pat, name in UI_APP_TARGETS:
            if re.search(rf"\b{pat}\b", low):
                return name
        return ""
    if need == "web":
        tech = web_strategy_mod.detect_web_tech(msg)
        db = detect_db_tech(msg)
        m = re.search(r"https?://[^\s]+|www\.[^\s]+", msg, re.IGNORECASE)
        if m:
            url = m.group(0)[:48]
            # URL bilan birga sayt texnologiyasi va/yoki DB teglari
            # ("https://x.supabase.com (DB: Supabase)")
            if tech or db:
                tags = " · ".join(
                    t for t in (tech, (f"DB: {db}" if db else "")) if t)
                return f"{url} ({tags})"
            return url
        # Sayt/amal konteksti bor bo'lsagina sayt turi/DB obyekt bo'ladi
        # ("shopify saytini och" -> Shopify; "supabase saytini och" ->
        # Supabase (baza); ikkalasi birga — "WordPress · DB: PostgreSQL").
        # Sof tadqiqot so'rovida esa DB nomi mavzuni EGALLAMAYDI — mavzu
        # olinadi, DB teglar sifatida qo'shiladi ("redis haqida · DB: Redis").
        site_ctx = re.search(
            r"\b(?:sayt|sahifa|do'kon|site|web|konsol|console|dashboard|panel)\w*|"
            r"\b(?:och|open|qur|build|yarat|create|bor|visit|tekshir|check)\w*",
            msg, re.IGNORECASE)
        if site_ctx and (tech or db):
            parts: list[str] = []
            if tech:
                parts.append(tech)
            if db:
                suffix = DB_DISPLAY_SUFFIX.get(db, "baza")
                parts.append(f"DB: {db}" if parts else f"{db} ({suffix})")
            return " · ".join(parts)
        # tadqiqot mavzusi: web fe'llaridan keyingi so'zlar
        txt = re.sub(r"\b(qidir|qidirib|qidirish|search|top|topib|find|o'qi|oqu|read|och|ochib|open|tekshir|tekshirib|check)\b", "", low, flags=re.IGNORECASE)
        txt = re.sub(r"\s+", " ", txt).strip()
        topic = txt[:48].strip(" ?.,;:!\"'") or ""
        # DB aytilgan bo'lsa va mavzu ichida bo'lmasa — teg qo'shiladi
        if db and db.lower() not in topic.lower():
            suffix = DB_DISPLAY_SUFFIX.get(db, "baza")
            return f"{topic} · DB: {db}" if topic else f"{db} ({suffix})"
        return topic
    if need == "code":
        fw, lang = detect_code_stack(msg)
        db = detect_db_tech(msg)
        orm = detect_orm(msg)
        parts: list[str] = []
        if fw:
            parts.append(f"{fw} ({lang})" if lang else fw)
        elif lang:
            parts.append(lang)
        # ORM framework bilan birga ko'rsatiladi
        # ("React (JavaScript) · Prisma").
        if orm:
            parts.append(orm)
        # DB faqat o'zi aytilgan bo'lsa — "MySQL (baza)" / "S3 (saqlash)";
        # framework bilan birga bo'lsa — "React (JavaScript) · DB: PostgreSQL".
        if db:
            suffix = DB_DISPLAY_SUFFIX.get(db, "baza")
            parts.append(f"DB: {db}" if parts else f"{db} ({suffix})")
        return " · ".join(parts)
    if need == "file_task":
        m = re.search(
            rf"[a-z0-9_\-]+\.(?:{FILE_EXTENSIONS})\b", low)
        if m:
            return m.group(0)[:48]
        # 'fayl/file' so'zidan keyingi NOMLI fayl (nuqta bor bo'lishi shart —
        # aks holda "faylni o'chir" dan "o" kabi chiqindi ushlanib qoladi)
        m2 = re.search(
            r"\b(?:fayl|file)\w*\s+([a-z0-9_\-]+\.[a-z0-9_\-]+)", low)
        if m2:
            return m2.group(1)[:48]
        return ""
    return ""


def detect_web_tech(message: str) -> str:
    """Web so'rovidan SAYT texnologiyasini aniqlaydi (LLMsiz).

    WordPress/Shopify/Wix... kabi platforma nomi yoki URL domen markeri
    (myshopify.com -> Shopify). Qaytaradi: display nomi yoki ''.
    (S5: yagona manba web_strategy.detect_web_tech.)
    """
    return web_strategy_mod.detect_web_tech(message)


def detect_db_tech(message: str) -> str:
    """Kod so'rovidan MA'LUMOTLAR BAZASI texnologiyasini aniqlaydi (LLMsiz).

    PostgreSQL/MySQL/MongoDB/Redis/SQLite/SQL Server... Qaytaradi: display
    nomi yoki ''. `detect_subject`/`_build_pipeline`/`_stack_plan` ishlatadi.
    """
    low = (message or "").lower()
    for pat, name in DATABASE_TECH_HINTS:
        if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
            return name
    return ""


def detect_orm(message: str) -> str:
    """Kod so'rovidan ORM/aloqa qatlamini aniqlaydi (LLMsiz).

    Prisma/TypeORM/Drizzle/Mongoose/Sequelize/Knex... Qaytaradi: display
    nomi yoki ''. Framework/til/DB bilan birga stack rejasini to'ldiradi
    ("react + postgresql + prisma" -> React, PostgreSQL, Prisma).
    """
    low = (message or "").lower()
    for pat, name in ORM_HINTS:
        if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
            return name
    return ""


def detect_code_stack(message: str) -> tuple:
    """Kod so'rovidan (framework, til) juftligini aniqlaydi (LLMsiz).

    Framework ro'yxatdan qidiriladi (eng uzun nomdan boshlab), keyin
    til. Qaytaradi: (framework_display, language_display) — ikkalasi ham
    '' bo'lishi mumkin. `detect_subject` ularni birlashtiradi:
    "React (JavaScript)" — framework til bilan birga ko'rsatiladi.
    """
    low = (message or "").lower()
    fw = ""
    fw_lang = ""
    for pat, fname, flang in CODE_FRAMEWORK_HINTS:
        if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
            fw = fname
            fw_lang = flang
            break
    lang = ""
    for pat, lname in CODE_LANG_HINTS:
        if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
            lang = lname
            break
    # Framework aytilgan, lekin til aniq emas — framework'ning O'Z tili
    # ishlatiladi ("React yoz" -> React (JavaScript)).
    if fw and not lang:
        lang = fw_lang
    return (fw, lang)


def planned_tools(message: str, need: str) -> list:
    """Rejalangan tool'lar to'plami — pipeline shu vositalar bilan ishlaydi.

    Actual bajarilgan tool'lar `completion['tools']`da (har doim real),
    bu esa SO'ROV bo'yicha reja (klassifikatsiya paytida, LLMsiz).
    """
    if need == "draw":
        subj = detect_subject(message, need)
        if subj and subj in CANNED_SCENE_SUBJECTS:
            return ["art__draw_scene_svg"]
        return ["art__draw_custom_svg"]
    if need == "ui_build":
        return ["art__ui_build_spec"]
    if need == "web":
        strat = web_strategy_mod.web_strategy(message)
        if strat == "delegate":
            return ["web_ai_bridge__ask_web_ai"]
        if strat == "browser":
            return ["web_ai_bridge__browser_navigate"]
        return ["web_ai_bridge__ask_web_ai", "web_ai_bridge__browser_navigate"]
    if need == "code":
        # Framework/til/DB/ORM aniqlansa — stack rejasi vositalari
        # rejalangan tool'larga moslashadi (React -> read/write/list/
        # run_command = npm shu terminal orqali ishlaydi; Django ->
        # +python_exec; MySQL -> run_command psql/mysql buyruqlari bilan;
        # Prisma -> run_command npx prisma buyruqlari bilan).
        fw, lang = detect_code_stack(message)
        db = detect_db_tech(message)
        orm = detect_orm(message)
        plan = stack_plan(fw, lang, db, orm)
        if plan:
            return list(plan["tools"])
        return ["write_file", "python_exec"]
    if need == "file_task":
        # O'qish/tahlil so'rovi — faqat read_file; tahrir so'rovi esa
        # to'liq to'plam (patch + write ham rejalashtiriladi).
        low = (message or "").lower()
        edit_hint = re.search(
            r"\b(" + "|".join(FILE_EDIT_VERBS) + r")\w*", low)
        if edit_hint:
            return ["read_file", "apply_patch", "write_file"]
        return ["read_file"]
    if need == "composition":
        return ["composition"]
    return []


def stack_plan(fw: str, lang: str, db: str = "", orm: str = "") -> Optional[dict]:
    """Framework/til/DB/ORMga mos stack rejasi: {'tools', 'guide'} yoki None.

    Tartib: framework nomi STACK jadvalida -> ekotizim; topilmasa tilga
    qarab; framework/til ANIQLANGAN bo'lsa ham ekotizimga kirmasa ->
    generic (terminal vositalari — Perl/C kabi tillarda python_exec
    rejalash noto'g'ri bo'lardi). Ma'lumotlar bazasi aniqlansa — uning
    rejasi (psql/mongosh/redis-cli...), ORM aniqlansa — uning rejasi
    (Prisma -> npx prisma init/migrate/generate) framework/til rejasi
    bilan BIRLASHTIRILADI (tools birlashadi, guide qo'shiladi). Bir xil
    reja ikki marta qo'shilmaydi (TypeORM + React ikkalasi ham npm).
    Hech narsa aniqlanmasa None (default code rejasi: write_file +
    python_exec).
    """
    key = FRAMEWORK_STACK.get(fw or "") or LANG_STACK.get(lang or "")
    if key is None and (fw or lang):
        key = "generic"
    plan = STACK_PLANS.get(key) if key else None
    db_key = DB_STACK.get(db or "")
    db_plan = STACK_PLANS.get(db_key) if db_key else None
    orm_key = ORM_STACK.get(orm or "")
    orm_plan = STACK_PLANS.get(orm_key) if orm_key else None
    merged_tools: list = []
    merged_guides: list = []
    seen: set = set()
    for p in (plan, orm_plan, db_plan):
        if p is None:
            continue
        pid = id(p)
        if pid in seen:
            continue
        seen.add(pid)
        merged_tools += p["tools"]
        merged_guides.append(p["guide"])
    if merged_guides:
        return {
            "tools": list(dict.fromkeys(merged_tools)),
            "guide": "\n\n".join(merged_guides),
        }
    return None


def stack_guide(pipeline: dict) -> str:
    """Kod pipeline'ida framework/til aniqlansa — STACK GUIDE matni (system prompt).

    Modelga aniq buyruqlarni (npm/webpack, manage.py, mvn...) yetkazadi —
    rejalangan `run_command` shu ko'rsatma bilan TO'G'RI ishlatiladi.
    Kod bo'lmagan BOSH pipeline'da ham, agar code SUB-pipeline'ida stack
    aniqlangan bo'lsa ("react ilova qurib ber" -> ui_build + code sub),
    qo'llanma beriladi. Hech qaysi joyda stack bo'lmasa bo'sh qaytaradi.
    """
    if pipeline.get("need") != "code":
        for sub in pipeline.get("sub_pipelines") or []:
            if sub.get("need") == "code" and (
                    sub.get("framework") or sub.get("language")
                    or sub.get("database") or sub.get("orm")):
                plan = stack_plan(
                    sub.get("framework", ""), sub.get("language", ""),
                    sub.get("database", ""), sub.get("orm", ""))
                return plan["guide"] if plan else ""
        return ""
    plan = stack_plan(
        pipeline.get("framework", ""), pipeline.get("language", ""),
        pipeline.get("database", ""), pipeline.get("orm", ""))
    return plan["guide"] if plan else ""


def clarify_request(message: str, need: str = "") -> str:
    """So'rovni aniqlashtiradi — MAVZU OBYEKTI + REJALANGAN TOOL'LAR.

    Sof matnni qisqartirish o'rniga aniqlangan obyekt va qaysi vositalar
    bilan bajarilishini tavsiflaydi (masalan "obyekt: olma · vositalar:
    art__draw_custom_svg"). LLM chaqirilmaydi — detektorlar deterministik.
    Obyekt aniqlanmasa — qisqa so'rov matni qaytariladi (eski xulq).
    """
    if not need:
        need = classify_need(message)
    subject = detect_subject(message, need)
    tools = planned_tools(message, need)
    parts: list = []
    if subject:
        parts.append(f"obyekt: {subject}")
    if tools:
        parts.append("vositalar: " + ", ".join(tools))
    if parts:
        return " · ".join(parts)[:140]
    txt = (message or "").strip()
    return (txt[:70] + "…") if len(txt) > 70 else txt
