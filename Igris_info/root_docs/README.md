# IGRIS Coder

Mahalliy (offline) coder agent: **deterministik brick-engine** + ixtiyoriy
**Ollama LLM** (qwen3:8b) gibrid miya, FastAPI bridge, web/desktop GUI va
avtomatik tiklanadigan fon xizmatlari.

```
Igris_brain/      Miya (Python): agent, brick-engine, FastAPI server (:8765),
                  watchdog (monitor/watchdog.py), tool'lar, MCP bridge
Igris_Interface/  GUI (React + Vite + Tauri): web (:1420) va desktop exe
Igris_Memory/     RAG xotira (L1/L2, BM25)
2nd_brain/        Bilan bazasi + graf backend (2nd Brain UI)
web-ai-bridge/    Real Chrome brauzer tool'lari (MCP server)
```

## Tez start (Windows)

```
1. setup.bat     <- bir marta: Python/Node paketlari + tozalash
2. run.bat       <- hamma xizmat yashirin (oynasiz) ishga tushadi,
                    desktop oynasi (yoki brauzer) avtomatik ochiladi
3. stop.bat      <- hammasini to'xtatish (yoki: run.bat stop)
```

`run.bat` qisqartmalari:

| Komanda | Vazifasi |
|---|---|
| `run.bat` | Ollama + backend + web + watchdog (yashirin), desktop/brauzer ochiladi |
| `run.bat menu` | Interaktiv menyu: desktop / web / faqat server |
| `run.bat build` | Desktop exe qurish (GUI manbadan yangilanishi uchun — **manba o'zgarsa qayta quring**) |
| `run.bat stop` | Barcha xizmatlarni to'xtatish (portlar 1420/8765/11434) |

> **GUI yangilanmadesmi?** Desktop exe statik build — `Igris_Interface/web`
> manbasi o'zgarsa `run.bat build` qilib, `run.bat` ni qayta ishga tushiring.

## Xizmatlar

| Xizmat | Port | Log |
|---|---|---|
| Backend (FastAPI) | `127.0.0.1:8765` | `Igris_brain/logs/server.log` |
| Web UI (vite dev) | `localhost:1420` | `logs/vite.log` |
| Ollama (LLM) | `127.0.0.1:11434` | `Igris_brain/logs/ollama.log` |
| Watchdog | — | `Igris_brain/logs/watchdog.log` |

Holat: `curl http://127.0.0.1:8765/api/status`

## Watchdog — avtomatik tiklanish

`run.bat` bilan `Igris_brain/monitor/watchdog.py` ham yashirin jarayon
sifatida ishga tushadi:

- Backend'ni har ~4 s da tekshiradi; ketma-ket 4 xato (≈16 s) bo'lsa
  **o'zi qayta ishga tushiradi** ("birdan offline bo'lib qolish" yo'q).
- Ollama'ni har ~15 s da tekshiradi (3 xato ≈45 s — restart).
- Restart'lar exponential backoff bilan cheklanadi (10 daqiqada max 8);
  UI'dan qilingan restart'ga aralashmaydi (marker handshake).
- Holat: `Igris_brain/logs/watchdog.json` (UI: Settings → Services).

Qo'lda: `python monitor/watchdog.py` (Igris_brain ichidan) — yoki hech
narsa qilmang, `run.bat` o'zi boshqaradi.

## Backend qo'lda ishga tushirish

```bash
cd Igris_brain
python -m server.server                # default: 127.0.0.1:8765, qwen3:8b
python -m server.server --no-llm       # Ollama'siz (deterministik rejim)
python -m server.server --no-memory    # xotirasiz
python -m server.server --model qwen3:4b
```

Asosiy endpoint'lar: `/api/chat` (+`/stream` SSE), `/api/agent/run`,
`/api/status`, `/api/health/*`, `/api/system/*` (restart, services) —
~45 ta endpoint. To'liq ro'yxat: `Igris_brain/README.md`.

## Muammolarni tashxislash

| Belgi | Qayerga qarash |
|---|---|
| Backend javob bermaydi | `Igris_brain/logs/server.log` + `server.log.err` |
| GUI qora / eski ko'rinish | `run.bat build` qiling; dev rejim logi: `logs/vite.log` |
| LLM javob bermaydi | `ollama list` (model yuklimi?), `Igris_brain/logs/ollama.log` |
| Watchdog ishlamayapti | `Igris_brain/logs/watchdog.json` (`running:false` bo'lsa `run.bat` qayta ishga tushiring) |
| Port band qolgan | `run.bat stop` → qayta `run.bat` |

## Hujjatlar

- `IGRIS_RUN_COMMANDS.txt` — barcha ishga tushirish variantlari, web-ai-bridge
  (Chrome CDP) sozlash, MCP/art tool'lar, HITL vazifa berish.
- `Igris_brain/README.md` — miya arxitekturasi: brick-engine, agentic core,
  Refactor Machine, benchmark.
- `Igris_brain/agentic_architecture.md` — StateMachine/Executor spec.
