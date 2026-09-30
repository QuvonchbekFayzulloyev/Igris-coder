# Protokol P01 — IJRO (Execution) — AgentExecutor

**Fayllar:** `Igris_brain/executor.py`, `Igris_brain/planner.py`

---

## 1. Qisqacha mazmun

Kod/vazifa bajarish protokoli: **plan → act → observe → correct** ReAct sikli.

- Plan-first qoida (avval reja, keyin harakat)
- `max_iter=8`, `max_retries=2`
- Quality gate: `_verify_deliverable` / `_llm_verify_deliverable` — deliverable bor-yo'qligi tekshiriladi, bo'lsa corrective pass
- Capability-gap: vosita yetmasa `use_skill` / `mcp_call` / `request_human` fallback
- Hooks: `on_plan`, `on_step_start`, `on_step_done`, `on_task_done`
- `ToolRegistry` (DEFAULT_REGISTRY) orqali vositalar: read_file, write_file, list_files, apply_patch, python_exec, run_command...

## 2. Bajarilgan holat

✅ **Ishlayapti** — `test_executor.py` ✅ + yangi `test_deliverable_syntax.py` 11/11 ✅ (2026-09-12).

- Importlar sog'lom: `from tools import Workspace, ToolRegistry, DEFAULT_REGISTRY`
- A3 tuzatishi faol: `probe_decisions.score_task()` — bajarilgan run'lar outcome 0.0 olmaydi (0.8 koeff + marker bonus)
- **A1 1-QADAM (2026-09-12): Python sintaksis verifikatori** — `_python_syntax_check()` (`ast.parse`, deterministik, ~ms). 120+ belgili `.py` fayl BUZUQ sintaksis bilan endi quality gate'dan O'TMAYDI (ilgari faqat uzunlik tekshirilardi — buzuk kod "bajardim" deb yozilardi). Gate buzuk faylda corrective pass ishga tushiradi.
- **A1 2-QADAM (2026-09-13): Run-verification** — `_python_run_check()`: 120+ belgili `.py` fayl izolyatsiyada ISHGA TUSHIRIB ko'riladi. `NameError/TypeError/AttributeError/ZeroDivisionError/IndexError/KeyError/UnboundLocalError/RecursionError` — gate'dan O'TMAYDI (corrective pass). Import/deps (`ModuleNotFoundError/ImportError`), deny-listdagi kod, timeout, juda qisqa — NEYTRAL (muhit bog'liq, rad etmaydi — false positive yo'q). Xavfsizlik: alohida subprocess + `-I` (user site-packages izolyatsiya) + 6s timeout + `python_tools` deny-listi. Test: `test_deliverable_run.py` 13/13 ✅ (unit + gate integratsiya)

## 3. Takliflar

- 🔴 A1 davomi: per-domain oracle — kod uchun KEYINGI qadam: pytest-suite run (task testlari bilan); PDF→text-extract, PCB→DRC, 3D→mesh-check uzoq muddat
- 🟡 `python_exec` to'liq sandbox emas (Dp4 qisman tuzatilgan — deny-list bor, resource limits yo'q)
- 🟡 Plan sifati kichik modellarda kuchsiz — plan-shablonlar (domain-template) qo'shish
- ⚪ Hooks natijalari UI'da to'liq ko'rinmaydi
