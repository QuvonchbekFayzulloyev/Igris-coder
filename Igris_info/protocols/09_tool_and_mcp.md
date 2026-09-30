# Protokol P09 — VOSITALAR VA MCP (Tools & MCP)

**Fayllar:** `Igris_brain/tools/` (`__init__.py` = ToolRegistry, `workspace.py`, `fs_tools.py`, `python_tools.py`, `shell_tools.py`, `web_tools.py`, `extra_tools.py`), `mcp_bridge.py`, `mcp_servers.json`, `mcp_servers/` (art, ui_builder, skills, database, filesystem, github, redis, websocket)

---

## 1. Qisqacha mazmun

- **ToolRegistry (DEFAULT_REGISTRY)**: vositalar ro'yxati + schema; `registry.execute(ws, name, args)`
- **Workspace**: fayl o'qish/yozish/list; realpath sandbox (`_is_inside` symlink-safe)
- **Vositalar**: read_file, write_file, list_files, apply_patch, python_exec, run_command, web_fetch...
- **MCP bridge**: `art__ draw_*`, `web_ai_bridge__ browser_*`, `ask_web_ai`, `web_ai_start_research` — chaqirish, natija, fallback; transport xatosida odatiy `run()`'ga qaytish
- **Capability-gap**: `use_skill(name)` ko'rsatma yuklash, `mcp_call(tool, args)`
- Output-guard: `mcp_bridge.call_tool` BARCHA MCP chiqishini tozalaydi (defense-in-depth)

## 2. Bajarilgan holat

✅ **Ishlayapti** — `test_executor.py` (registry execute) + `test_skills_mcp_hitl.py` 18 test mavjud; `from tools import DEFAULT_REGISTRY` 5+ joyda ishlatiladi, importlar sog'lom (2026-09-12).

## 3. Takliflar

- ✅ **Silent-fallback telemetry (2026-09-12)**: MCP connect/config xatolari endi `degradation.py` registryga `mcp.<server>` sifatida yoziladi → `/api/system/services`'da ko'rinadi (S3 qism)
- 🟡 Dp8: `apply_patch` simple-rejimda "+" qatorlarni fayl oxiriga append qiladi — unified diff (satr-pozitsiyali) kerak
- 🔴 Yangi domain-MCP serverlar yo'q: 3D (OpenSCAD), EDA (KiCad), Office (docx/pptx/xlsx/pdf), Audio (piper/whisper), Diagramma (Mermaid/Graphviz)
- 🟡 Tool schema hujjatlari LLM uchun yetarli, lekin inson uchun alohida katalog yo'q
- ⚪ MCP server health-check + avtomatik restart (watchdog'dan alohida)
