"""
IGRIS BRAIN — AgentStackData — S5 modullashtirish
=================================================
problems_to_fix.md :: S5 (qism) — igris_agent god-file'dan ajratilgan.

Statik MA'LUMOT JADVALLARI (kod yo'q, faqat data):
  STACK_PLANS        — ekotizim -> {'tools', 'guide'} rejasi
                       (npm/python/php/ruby/java/dotnet/go/rust/dart/swift/
                       postgres/mysql/mongodb/redis/... vector DB'lar, s3,
                       firestore, streams, generic)
  FRAMEWORK_STACK    — framework display nomi -> ekotizim (React -> npm ...)
  ORM_STACK          — ORM display nomi -> ekotizim (Prisma -> prisma ...)
  LANG_STACK         — til display nomi -> ekotizim (Python -> python ...)
  DB_STACK           — DB display nomi -> ekotizim (PostgreSQL -> postgres ...)
  DB_DISPLAY_SUFFIX  — DB yolg'iz subject'da qo'shimcha ("S3" -> "saqlash")

Ishlatuvchi: `igris_agent._stack_plan/_stack_guide/_detect_db_tech/
_detect_subject/_planned_tools` — import orqali (nomlar o'zgarmagan).
`igris_agent` ham shu nomlarni qayta eksport qiladi (testlar mosligi uchun).

Bu modul DETERMINISTIK va holatsiz — hech narsa bajarmaydi, faqat jadvallar.
"""

from __future__ import annotations

__all__ = [
    "STACK_PLANS",
    "FRAMEWORK_STACK",
    "ORM_STACK",
    "LANG_STACK",
    "DB_STACK",
    "DB_DISPLAY_SUFFIX",
]

# --- BEGIN (moved verbatim from igris_agent.py) ---
STACK_PLANS: dict = {
    "npm": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - JavaScript/TypeScript (npm):\n"
            "- Key files: package.json (scripts + deps), vite.config.js / webpack.config.js, "
            "index.html, src/ (main.jsx|tsx, App.jsx|tsx).\n"
            "- New project: `npm create vite@latest . -- --template react` "
            "(or `npx create-react-app .`); bare: `npm init -y` + `npm install react react-dom`.\n"
            "- Install: `npm install` (one pkg: `npm install <pkg>`, dev: `npm install -D <pkg>`).\n"
            "- Run: `npm run dev` (Vite) or `npm start` (CRA). Build: `npm run build`; "
            "webpack: `npx webpack` (prod: `npx webpack --mode production`).\n"
            "- Typecheck (TS): `npx tsc --noEmit`. Tests: `npm test`.\n"
            "- Run all of these with the run_command tool (cwd = project dir)."
        ),
    },
    "python": {
        "tools": ["read_file", "write_file", "list_files", "run_command", "python_exec"],
        "guide": (
            "STACK GUIDE - Python:\n"
            "- Key files: requirements.txt / pyproject.toml, manage.py (Django), app.py, tests/.\n"
            "- Install: `pip install -r requirements.txt` (one pkg: `pip install <pkg>`); "
            "prefer a venv: `python -m venv .venv`.\n"
            "- Run: `python app.py` (Django: `python manage.py runserver`; "
            "FastAPI dev: `uvicorn app:app --reload`).\n"
            "- Tests: `python -m pytest` or `python -m unittest`.\n"
            "- Use python_exec for quick snippets, run_command for the real app/CLI."
        ),
    },
    "php": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - PHP (Composer):\n"
            "- Key files: composer.json, src/, public/index.php (Laravel: artisan).\n"
            "- Install: `composer install` (one pkg: `composer require <pkg>`).\n"
            "- Run: `php -S localhost:8000` (Laravel: `php artisan serve`).\n"
            "- Tests: `vendor/bin/phpunit`. Use the run_command tool."
        ),
    },
    "ruby": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Ruby (Bundler):\n"
            "- Key files: Gemfile, config.ru, app/ (Rails: bin/rails).\n"
            "- Install: `bundle install` (one gem: `bundle add <gem>`).\n"
            "- Run: `ruby app.rb` (Rails: `bin/rails server`). Tests: `bundle exec rspec`.\n"
            "- Use the run_command tool."
        ),
    },
    "java": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Java (Maven/Gradle):\n"
            "- Key files: pom.xml / build.gradle, src/main (java/ katalogi).\n"
            "- Install/build: `mvn install` or `gradle build` "
            "(Spring Boot: `./mvnw spring-boot:run` / `./gradlew bootRun`).\n"
            "- Tests: `mvn test` / `gradle test`. Use the run_command tool."
        ),
    },
    "dotnet": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - .NET/C#:\n"
            "- Key files: *.csproj / *.sln, Program.cs.\n"
            "- Restore/build: `dotnet restore` + `dotnet build` (add pkg: `dotnet add package <pkg>`).\n"
            "- Run: `dotnet run`. Tests: `dotnet test`. Use the run_command tool."
        ),
    },
    "go": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Go:\n"
            "- Key files: go.mod, main.go.\n"
            "- Install: `go mod tidy` (add: `go get <module>`).\n"
            "- Run: `go run .` Build: `go build`. Tests: `go test ./...`. Use run_command."
        ),
    },
    "rust": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Rust (Cargo):\n"
            "- Key files: Cargo.toml, src/main.rs.\n"
            "- Install: `cargo build` (add: `cargo add <crate>`).\n"
            "- Run: `cargo run`. Tests: `cargo test`. Use the run_command tool."
        ),
    },
    "dart": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Dart/Flutter:\n"
            "- Key files: pubspec.yaml, lib/main.dart.\n"
            "- Install: `flutter pub get` (add: `flutter pub add <pkg>`).\n"
            "- Run: `flutter run`. Tests: `flutter test`. Use the run_command tool."
        ),
    },
    "swift": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Swift/SwiftUI:\n"
            "- Key files: Package.swift, Sources/ (Xcode project or SPM).\n"
            "- Build: `swift build` (add: add to Package.swift dependencies).\n"
            "- Tests: `swift test`. Use the run_command tool."
        ),
    },
    "postgres": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - PostgreSQL:\n"
            "- Connect: `psql -U <user> -d <dbname> -h localhost` (auth: PGPASSWORD env / pg_hba).\n"
            "- Inspect: `\\dt` (tables), `\\d <table>` (schema), `\\l` (databases); quit with `\\q`.\n"
            "- Dump/backup: `pg_dump -U <user> <db> -f backup.sql`.\n"
            "- App drivers: psycopg / SQLAlchemy (Python: `postgresql+psycopg://user:pass@localhost:5432/db`), "
            "pg / Prisma / TypeORM / Drizzle (Node/TS: `postgresql://...` in schema.prisma), GORM (Go).\n"
            "- Run via the run_command tool."
        ),
    },
    "prisma": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Prisma (ORM, Node/TypeScript):\n"
            "- Install: `npm install prisma @prisma/client` (CLI dev dep: `npm install -D prisma`).\n"
            "- Init: `npx prisma init --datasource-provider postgresql` "
            "(yoki mysql/sqlite) -> prisma/schema.prisma + .env.\n"
            "- .env: `DATABASE_URL=\"postgresql://user:pass@localhost:5432/dbname\"` "
            "(provider DB bilan mos bo'lishi shart).\n"
            "- Model: `model User { id Int @id @default(autoincrement()) email String @unique name String? }` "
            "schema.prisma'da, keyin:\n"
            "- Migrate: `npx prisma migrate dev --name init` (jadval yaratadi + client generate qiladi).\n"
            "- Migratsiyasiz sync: `npx prisma db push`. Client qayta: `npx prisma generate`.\n"
            "- Ko'rish: `npx prisma studio` (brauzer UI). Seed: `npx prisma db seed` "
            "(package.json'da `prisma.seed` kerak).\n"
            "- Client: `import { PrismaClient } from '@prisma/client'; "
            "const prisma = new PrismaClient();`\n"
            "- Run via the run_command tool."
        ),
    },
    "mysql": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - MySQL/MariaDB:\n"
            "- Connect: `mysql -u <user> -p <dbname>` (add `-h <host>` if remote).\n"
            "- Inspect: `SHOW DATABASES; SHOW TABLES; DESCRIBE <table>;`\n"
            "- Dump/backup: `mysqldump -u <user> -p <db> > backup.sql`.\n"
            "- App drivers: mysql-connector-python / SQLAlchemy (Python), "
            "mysql2 / Prisma / TypeORM (Node), PDO/mysqli (PHP).\n"
            "- Run via the run_command tool."
        ),
    },
    "mongodb": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - MongoDB:\n"
            "- Connect: `mongosh \"mongodb://localhost:27017/<db>\"` or `mongosh` then `use <db>`.\n"
            "- Inspect: `show dbs`, `show collections`, `db.<collection>.find().limit(5)`.\n"
            "- App drivers: pymongo (Python), mongodb/mongoose (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "redis": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Redis:\n"
            "- Connect: `redis-cli` (add `-h <host> -p <port>` if remote).\n"
            "- Basic: `SET key value`, `GET key`, `KEYS <pattern>`, `TTL key` (FLUSHDB is destructive).\n"
            "- App drivers: redis-py (Python), ioredis/node-redis (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "sqlite": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - SQLite:\n"
            "- Open: `sqlite3 <file>.db` then `.tables`, `.schema <table>`, `SELECT ...;`, `.quit`.\n"
            "- No server needed — the DB is a single file.\n"
            "- App drivers: sqlite3 (Python stdlib), better-sqlite3 (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "mssql": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - SQL Server:\n"
            "- Connect: `sqlcmd -S localhost -U <user> -P <pass>` then `SELECT ...; GO`.\n"
            "- Inspect: `SELECT name FROM sys.databases;` / `SELECT * FROM sys.tables;`\n"
            "- App drivers: pyodbc (Python), mssql (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "elasticsearch": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Elasticsearch:\n"
            "- REST API over HTTP (default port 9200): `curl -X GET \"http://localhost:9200/\"`.\n"
            "- Indices: `curl \"http://localhost:9200/_cat/indices?v\"`; "
            "create: `curl -X PUT \"http://localhost:9200/my-index\"`.\n"
            "- Search: `curl -X POST \"http://localhost:9200/my-index/_search\" "
            "-H 'Content-Type: application/json' -d '{\"query\":{\"match_all\":{}}}'`.\n"
            "- Client libs: elasticsearch-py (Python), @elastic/elasticsearch (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "cassandra": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Cassandra (CQL):\n"
            "- Connect: `cqlsh` (one-shot: `cqlsh -e \"SELECT ...\"`).\n"
            "- Inspect: `DESCRIBE KEYSPACES;`, `DESCRIBE TABLES;`, `SELECT ... LIMIT 10;`\n"
            "- Driver: cassandra-driver (Python/Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "dynamodb": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - DynamoDB:\n"
            "- AWS CLI: `aws dynamodb list-tables --region <region>`; "
            "`aws dynamodb scan --table-name <t>`.\n"
            "- Local dev: `docker run -p 8000:8000 amazon/dynamodb-local` then pass "
            "`--endpoint-url http://localhost:8000`.\n"
            "- Driver: boto3 (Python), @aws-sdk/client-dynamodb (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "neo4j": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Neo4j (Cypher):\n"
            "- Connect: `cypher-shell -u neo4j -p <pass>` (bolt 7687, browser UI 7474).\n"
            "- Basic: `MATCH (n) RETURN n LIMIT 25;`\n"
            "- Driver: neo4j (Python/Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "clickhouse": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - ClickHouse:\n"
            "- Connect: `clickhouse-client` (native 9000; HTTP 8123).\n"
            "- Basic: `SHOW TABLES;`, `SELECT * FROM <table> LIMIT 10;`\n"
            "- Driver: clickhouse-connect (Python), @clickhouse/client (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "oracle": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Oracle (SQL*Plus):\n"
            "- Connect: `sqlplus user/pass@//localhost:1521/XEPDB1`.\n"
            "- Inspect: `SELECT table_name FROM user_tables;`\n"
            "- Driver: python-oracledb (Python), oracledb (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "chroma": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Chroma (vector DB):\n"
            "- Install: `pip install chromadb`. Server: `chroma run --path ./chroma-data` "
            "(yoki embedded: `import chromadb; client = chromadb.PersistentClient(path='./db')`).\n"
            "- Collection: `col = client.get_or_create_collection('docs', "
            "metadata={'hnsw:space': 'cosine'})` (cosine/l2/ip).\n"
            "- Add: `col.add(ids=['1'], documents=['matn'], embeddings=[vec])` — "
            "vektorlarni o'zingiz bering YOKI `embedding_function` berilsa matndan avtomatik.\n"
            "- Search: `col.query(query_embeddings=[vec], n_results=5, "
            "include=['documents','distances'])`.\n"
            "- EMBEDDING O'LCHAMI: `vec` uzunligi collection'dagi birinchi embedding bilan "
            "MOS bo'lishi shart (ajralib qolsa xato). Umumiy: OpenAI text-embedding-3-small="
            "1536, ada-002=1536, all-MiniLM-L6-v2=384 (Chroma default), nomic-embed-text "
            "(Ollama)=768, bge-base=768. Model almashtirilsa — yangi collection + qayta embed.\n"
            "- Filter: `col.query(..., where={'category': 'news'})`.\n"
            "- Run via the run_command tool."
        ),
    },
    "qdrant": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Qdrant (vector DB):\n"
            "- Local: `docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant` (REST 6333 / GRPC 6334).\n"
            "- Python: `pip install qdrant-client`; "
            "`client = QdrantClient(url='http://localhost:6333')`.\n"
            "- Create: `client.create_collection('docs', vectors_config={'size': 1536, 'distance': 'Cosine'})` — "
            "`size` = EMBEDDING O'LCHAMI (OpenAI 3-small/ada-002=1536, 3-large=3072, "
            "MiniLM=384, nomic=768); model o'zgarsa YANGI collection kerak.\n"
            "- Upsert: `client.upsert('docs', points=[PointStruct(id=1, vector=vec, "
            "payload={'title': '...'})])`.\n"
            "- Search: `client.search('docs', query_vector=vec, limit=5, with_payload=True)`.\n"
            "- REST: `curl -X POST http://localhost:6333/collections/docs/points/search "
            "-H 'Content-Type: application/json' -d '{\"vector\": [...], \"limit\": 5}'`.\n"
            "- Filter: `client.search(..., query_filter=Filter(must=[FieldCondition(key='category', "
            "match=Match(value='news'))]))`.\n"
            "- Run via the run_command tool."
        ),
    },
    "pinecone": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Pinecone (cloud vector DB):\n"
            "- SDK: `pip install pinecone-client`; "
            "`pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])`.\n"
            "- Index: `pc.create_index('docs', dimension=1536, metric='cosine')` — "
            "`dimension` = EMBEDDING O'LCHAMI va index yaratilgach O'ZGARMAYDI "
            "(OpenAI 3-small/ada-002=1536, 3-large=3072, MiniLM=384, nomic=768; "
            "model almashtirilsa yangi index).\n"
            "- Index obyekti: `idx = pc.Index('docs')` — keyin upsert/query shu bilan.\n"
            "- Upsert: `idx.upsert(vectors=[(id, vec, {'title': '...'})], namespace='ns1')`.\n"
            "- Query: `idx.query(vector=vec, top_k=5, include_metadata=True)`.\n"
            "- Namespace: `idx.query(..., namespace='ns1')` — bo'sh namespace default.\n"
            "- Metadata filter: `idx.query(vector=vec, top_k=5, filter={'category': {'$eq': 'news'}})`.\n"
            "- Run via the run_command tool."
        ),
    },
    "milvus": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Milvus (vector DB):\n"
            "- Local: `docker compose up` (milvus-standalone, port 19530) yoki "
            "`pip install pymilvus`; `client = MilvusClient(uri='http://localhost:19530')`.\n"
            "- Create: `client.create_collection('docs', dimension=1536, metric_type='COSINE')` — "
            "`dimension` = EMBEDDING O'LCHAMI (OpenAI 3-small/ada-002=1536, MiniLM=384, "
            "nomic=768). Metrik: COSINE/IP/L2.\n"
            "- Insert: `client.insert('docs', [{'id': 1, 'vector': vec, 'title': '...'}])`.\n"
            "- Search: `client.search('docs', data=[vec], limit=5, output_fields=['title'])`.\n"
            "- IVFFlat/HNSW index'da `nprobe`/`ef` parametrlari aniqlik tezligini boshqaradi.\n"
            "- Run via the run_command tool."
        ),
    },
    "weaviate": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Weaviate (vector DB):\n"
            "- Local: `docker run -p 8080:8080 semitechnologies/weaviate` (REST /v1/graphql).\n"
            "- Python: `pip install weaviate-client`; `client = weaviate.Client('http://localhost:8080')`.\n"
            "- Class: vectorizer='none' va `'vectorIndexConfig': {'distance': 'cosine'}`.\n"
            "- Object: `client.data_object.create({'title': '...'}, class_name='Document', vector=vec)`.\n"
            "- Search: `client.query.get('Document', ['title']).with_near_vector({'vector': vec}).with_limit(5).do()` "
            "(GraphQL: `{ Get { Document(limit: 5, nearVector: {vector: [...]}) { title } } }`).\n"
            "- EMBEDDING O'LCHAMI: class'ga birinchi object bilan o'rnatiladi — model "
            "o'zgarsa yangi class kerak (OpenAI 3-small/ada-002=1536, MiniLM=384, nomic=768).\n"
            "- Run via the run_command tool."
        ),
    },
    "faiss": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - FAISS (in-process vector index):\n"
            "- Install: `pip install faiss-cpu`. Server YO'Q — faqat in-process (loyiha ichida).\n"
            "- Index: `import faiss; import numpy as np; index = faiss.IndexFlatIP(dim)` "
            "(cosine uchun vectorlarni normalize qiling yoki IndexFlatL2).\n"
            "- Add: `index.add(np.array(vectors).astype('float32'))` — barcha vectorlar bir xil "
            "`dim` o'lchamda (EMBEDDING O'LCHAMI: OpenAI 3-small/ada-002=1536, MiniLM=384, "
            "nomic=768).\n"
            "- Search: `D, I = index.search(np.array([vec]).astype('float32'), k=5)` — "
            "I = id'lar, D = masofalar.\n"
            "- Cosine: normalize qilinsa IP = cosine: `faiss.normalize_L2(x)`.\n"
            "- Metadata: FAISS o'zi saqlamaydi — id -> matn xaritasi (dict) o'zingizda.\n"
            "- Run via the run_command tool."
        ),
    },
    "influxdb": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - InfluxDB (time series):\n"
            "- Connect: `influx` CLI (default port 8086) or `curl http://localhost:8086/health`.\n"
            "- Query (Flux): `influx query 'from(bucket:\"my-bucket\") |> range(start: -1h) |> limit(n: 10)'`.\n"
            "- v1 API: `/query?q=SELECT ...`; client libs: influxdb-client (Python/Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "memcached": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Memcached:\n"
            "- Default port 11211, plain-text protocol: `printf 'stats\\r\\n' | nc localhost 11211`.\n"
            "- Basic: `set key 0 <ttl> <bytes>\\r\\n<value>` / `get key` / `delete key`.\n"
            "- Client libs: pymemcache (Python), memjs (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "duckdb": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - DuckDB (embedded analytics):\n"
            "- CLI: `duckdb my.db` then SQL; in-process via `import duckdb; duckdb.sql(\"...\")` (Python).\n"
            "- Reads Parquet/CSV/JSON directly: `SELECT * FROM 'data.parquet';`\n"
            "- Node: duckdb package. Run via the run_command tool."
        ),
    },
    "snowflake": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Snowflake (warehouse):\n"
            "- CLI: `snowsql -a <account> -u <user>` (credentials in ~/.snowsql/config or env).\n"
            "- Query: standard SQL — `SELECT ...; SHOW TABLES;`\n"
            "- Drivers: snowflake-connector-python (Python), snowflake-sdk (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "bigquery": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - BigQuery:\n"
            "- CLI: `bq query --use_legacy_sql=false 'SELECT ...'` (gcloud auth required).\n"
            "- Inspect: `bq ls <dataset>`, `bq show <dataset>.<table>`\n"
            "- Drivers: google-cloud-bigquery (Python), @google-cloud/bigquery (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "db": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Database (generic):\n"
            "- Cloud xizmatlar (Firebase/Airtable/Rockset/etcd...): SDK/konsol orqali — "
            "firebase-admin, pyairtable, rockset-client (Python/Node); "
            "`curl -s https://<api-endpoint>` ko'rinishidagi REST ham ishlaydi.\n"
            "- O'z CLI/client'i: `psql -U user -d db`, `mysql -u user -p db`, "
            "`mongosh \"mongodb://localhost:27017/db\"`, `redis-cli -h localhost`, "
            "`sqlite3 app.db`, `cqlsh -e \"DESCRIBE TABLES\"`, `sqlcmd -S localhost -U user`, "
            "`etcdctl get /key`, `arangosh --server.endpoint tcp://127.0.0.1:8529`, "
            "`surreal start memory`, `influx query 'from(bucket:\"b\")'`, "
            "`clickhouse-client --query \"SHOW TABLES\"`...\n"
            "- Connection strings: `<scheme>://user:pass@host:port/dbname`.\n"
            "- Avval sxemani o'rganing (schema), keyin so'rov, keyin dump/backup.\n"
            "- Run via the run_command tool."
        ),
    },
    "s3": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Object storage (S3/MinIO/GCS/Azure Blob/R2):\n"
            "- AWS S3: `aws s3 ls`, `aws s3 cp <fayl> s3://<buket>/`, "
            "`aws s3 sync <dir> s3://<buket>/` (auth: `aws configure` yoki "
            "AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY).\n"
            "- MinIO (lokal, S3-mos): `docker run -p 9000:9000 minio/minio server /data`; "
            "`mc alias set local http://localhost:9000 <user> <pass>`, "
            "`mc ls local/<buket>`, `mc cp <fayl> local/<buket>/`.\n"
            "- Google Cloud Storage: `gsutil ls gs://<buket>`, "
            "`gsutil cp <fayl> gs://<buket>/` (auth: `gcloud auth login`).\n"
            "- Azure Blob: `azcopy copy <fayl> https://<acct>.blob.core.windows.net/<container>/` "
            "(auth: `az login`).\n"
            "- Cloudflare R2: `wrangler r2 object put/get` (S3-mos API).\n"
            "- Universal: `rclone copy <fayl> remote:<buket>/`.\n"
            "- SDK'lar: boto3 (Python: `s3 = boto3.client('s3'); "
            "s3.upload_file('f', 'buket', 'key')`), @aws-sdk/client-s3 (Node), "
            "minio-py, google-cloud-storage, @azure/storage-blob.\n"
            "- Run via the run_command tool."
        ),
    },
    "firestore": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Firebase Firestore / Realtime Database:\n"
            "- Konsol: https://console.firebase.google.com -> Firestore Database "
            "(real-vaqt uchun Realtime Database).\n"
            "- Web (modular v9): `npm install firebase`; "
            "`import { initializeApp } from 'firebase/app'; "
            "import { getFirestore, collection, addDoc, getDocs, query, where } from 'firebase/firestore'`.\n"
            "- Yozish/o'qish: `addDoc(collection(db, 'users'), {name: 'A'})`; "
            "`const q = query(collection(db, 'users'), where('age', '>', 18)); "
            "const snap = await getDocs(q);`\n"
            "- Realtime: `import { getDatabase, ref, set, onValue } from 'firebase/database'; "
            "set(ref(db, 'users/1'), {...}); onValue(ref(db, 'users'), (s) => {...})`.\n"
            "- Xavfsizlik: Firestore Database -> Rules yorlig'i (ommaviy ilovalarda juda muhim).\n"
            "- Emulator: `firebase emulators:start`. Admin SDK (backend): `npm install firebase-admin`.\n"
            "- Run via the run_command tool."
        ),
    },
    "streams": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Stream / message broker (Kafka/RabbitMQ/Pulsar):\n"
            "- Kafka (lokal): `docker run -p 9092:9092 apache/kafka:latest`; "
            "topic: `kafka-topics.sh --create --topic <t> --bootstrap-server localhost:9092`; "
            "producer: `kafka-console-producer.sh --topic <t> --bootstrap-server localhost:9092`; "
            "consumer: `kafka-console-consumer.sh --topic <t> --from-beginning --bootstrap-server localhost:9092`.\n"
            "- Kafka driver'lar: confluent-kafka (Python), kafkajs (Node).\n"
            "- RabbitMQ: `docker run -p 5672:5672 -p 15672:15672 rabbitmq:3-management`; "
            "boshqaruv UI http://localhost:15672 (user/guest); pika (Python), amqplib (Node).\n"
            "- Pulsar: `pulsar-admin topics create persistent://public/default/<t>`; "
            "pulsar-client (Python/Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "generic": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - general project:\n"
            "- Inspect the project files first (list_files/read_file), then build/run/test "
            "with the run_command tool. If a package manifest exists (package.json, "
            "requirements.txt, go.mod, Cargo.toml, ...) use its standard commands."
        ),
    },
}

# Framework -> ekotizim xaritasi (STACK_PLANS kalitlari).
FRAMEWORK_STACK: dict = {
    "React": "npm", "React Native": "npm", "Next.js": "npm", "SvelteKit": "npm",
    "Nuxt": "npm", "Gatsby": "npm", "Vue": "npm", "Vuex": "npm", "Redux": "npm",
    "Angular": "npm", "Express": "npm", "jQuery": "npm", "Electron": "npm",
    "Node.js": "npm", "Three.js": "npm", "NestJS": "npm", "Fastify": "npm",
    "Tailwind CSS": "npm", "Bootstrap": "npm", "Sass": "npm", "SCSS": "npm",
    "Tauri": "npm",
    "Django": "python", "Flask": "python", "FastAPI": "python", "PyTorch": "python",
    "TensorFlow": "python", "pandas": "python", "NumPy": "python",
    "scikit-learn": "python", "Matplotlib": "python", "Beautiful Soup": "python",
    "Selenium": "python", "pytest": "python", "Celery": "python",
    "SQLAlchemy": "python",
    "Laravel": "php", "Symfony": "php", "WordPress": "php", "CodeIgniter": "php",
    "Rails": "ruby", "Sinatra": "ruby",
    "Spring": "java", "Hibernate": "java", "Maven": "java", "Gradle": "java",
    "ASP.NET": "dotnet", ".NET": "dotnet", "Xamarin": "dotnet",
    "Flutter": "dart",
}

# ORM -> ekotizim xaritasi (STACK_PLANS kalitlari). Prisma o'z maxsus
# rejasiga ega (npx prisma init/migrate/generate buyruqlari); boshqa Node
# ORM'lar npm rejasi bilan ishlaydi (TypeORM/Drizzle/Mongoose...).
ORM_STACK: dict = {
    "Prisma": "prisma",
    "TypeORM": "npm", "Drizzle ORM": "npm", "Mongoose": "npm",
    "Sequelize": "npm", "Knex": "npm",
}

# Til -> ekotizim xaritasi (noma'lum framework yoki faqat til aytilganda).
LANG_STACK: dict = {
    "JavaScript": "npm", "TypeScript": "npm",
    "Python": "python",
    "PHP": "php", "Ruby": "ruby",
    "Java": "java", "Kotlin": "java",
    "C#": "dotnet",
    "Go": "go", "Rust": "rust",
    "Dart": "dart", "Swift": "swift",
}

# Ma'lumotlar bazasi -> stack rejasi xaritasi (STACK_PLANS kalitlari).
DB_STACK: dict = {
    "PostgreSQL": "postgres", "MySQL": "mysql", "MariaDB": "mysql",
    "MongoDB": "mongodb", "Redis": "redis", "SQLite": "sqlite",
    "SQL Server": "mssql", "Cassandra": "cassandra", "Oracle": "oracle",
    "DynamoDB": "dynamodb", "Neo4j": "neo4j", "ClickHouse": "clickhouse",
    "Elasticsearch": "elasticsearch", "Firebase": "db", "Supabase": "postgres",
    # Moslashtiriladiganlar (mos CLI/client ishlaydi)
    "TimescaleDB": "postgres", "Redshift": "postgres", "CockroachDB": "postgres",
    "pgvector": "postgres",
    "PlanetScale": "mysql",
    "ScyllaDB": "cassandra",
    "Valkey": "redis",
    "Turso": "sqlite", "libSQL": "sqlite",
    "TiDB": "mysql", "YugabyteDB": "postgres",
    # Maxsus rejalar
    "Memcached": "memcached", "InfluxDB": "influxdb", "DuckDB": "duckdb",
    "Snowflake": "snowflake", "BigQuery": "bigquery",
    "Chroma": "chroma", "Qdrant": "qdrant", "Milvus": "milvus",
    "Pinecone": "pinecone", "Weaviate": "weaviate", "FAISS": "faiss",
    # Obyekt saqlash (S3-mos)
    "S3": "s3", "MinIO": "s3", "Google Cloud Storage": "s3",
    "Azure Blob": "s3", "Cloudflare R2": "s3", "Backblaze B2": "s3",
    "DigitalOcean Spaces": "s3",
    # Realtime / serverless
    "Firestore": "firestore", "Firebase Realtime": "firestore",
    "Neon Postgres": "postgres", "Xata": "postgres", "Cloudflare D1": "sqlite",
    "Upstash": "redis", "SurrealDB": "db", "SingleStore": "mysql",
    "Tarantool": "db", "Rockset": "db", "Airtable": "db",
    # Stream / navbat
    "Kafka": "streams", "RabbitMQ": "streams", "Apache Pulsar": "streams",
    "NATS": "streams", "Redpanda": "streams",
    # Generic 'db' rejasi
    "QuestDB": "db", "CouchDB": "db", "Couchbase": "db", "HBase": "db",
    "ArangoDB": "db", "etcd": "db", "RocksDB": "db", "LevelDB": "db",
}

# Subject'da DB yolg'iz bo'lganda "(baza)" o'rniga aniqroq qo'shimcha
# ("S3 (saqlash)", "Kafka (oqim)"...). Ro'yxatda bo'lmaganlar -> baza.
DB_DISPLAY_SUFFIX: dict = {
    "S3": "saqlash", "MinIO": "saqlash", "Google Cloud Storage": "saqlash",
    "Azure Blob": "saqlash", "Cloudflare R2": "saqlash",
    "Backblaze B2": "saqlash", "DigitalOcean Spaces": "saqlash",
    "Kafka": "oqim", "RabbitMQ": "navbat",
    "Apache Pulsar": "oqim", "NATS": "oqim", "Redpanda": "oqim",
    "Firestore": "real-vaqt bazasi", "Firebase Realtime": "real-vaqt bazasi",
    "Memcached": "kesh", "Elasticsearch": "qidiruv", "Neo4j": "graf",
}


