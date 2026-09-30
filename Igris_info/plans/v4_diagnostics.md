# IGRIS v4 — Diagnostics Guide (§20)

**Sana:** 2026-09-18
**Format:** 11 diagnostika — muammo aniqlash + hal qilish usullari

---

## 1. Agent qayerda tartibsiz?

**Belgilar:** Agent noto'g'ri javob beradi, noto'g'ri tool tanlaydi.

**Tekshirish usuli:**
```bash
# State machine holatini tekshirish
python -c "from state.state_machine import StateMachine; sm = StateMachine(); print(sm.state)"

# Decision trace'ni tekshirish
cat logs/probe_decisions.jsonl | tail -5
```

**Hal qilish:** `monitor/probe_decisions.py` — har bir real task uchun to'liq trace yoziladi.

---

## 2. Muammo qaysi qatlamda?

**Qatlamlar:**
| Qatlam | Tekshirish usuli |
|--------|-----------------|
| LLM | `logs/ollama.log` — model javoblari |
| Orchestration | `state/state_machine.py` — tranzitsiya loglari |
| Memory | `agent/memory_bridge.py` — recall/remember loglari |
| Tool | `tools/base.py` — ToolError + code |
| Verification | `verification/verification_comparison.py` — compare natijalari |
| Loop | `state/world_state.py` — detect_loop, detect_stuck |
| Communication | `agent/response_generator.py` — javob formati |

---

## 3. Keraksiz layerlarni aniqlash

**Usul:** Minimal core architecture — faqat zarur bo'lgan modullar:

```
Majburiy:
  state/state_machine.py    — holat boshqaruvi
  state/goal_model.py       — maqsad ierarxiyisi
  planning/planner.py       — rejalashtirish
  executor/executor.py      — bajarish
  tools/                    — vositalar

Ixtiyoriy:
  agent/memory_bridge.py    — xotira (agar RAG kerak bo'lsa)
  agent/response_generator.py — javob formatlash
  monitor/                  — monitoring
```

**Tekshirish:** `requirements.txt` dan foydalanilmagan paketlarni topish.

---

## 4. Minimal Core Architecture

```
┌─────────────────────────────────────────┐
│              IgrisAgent                  │
│  ┌──────────┐  ┌──────────┐  ┌────────┐│
│  │ State    │  │ Planning │  │Executor││
│  │ Machine  │→ │ Planner  │→ │        ││
│  └──────────┘  └──────────┘  └────────┘│
│       ↑              ↑            ↓     │
│  ┌──────────┐  ┌──────────┐  ┌────────┐│
│  │  Goal    │  │  Tools   │  │ Verify ││
│  │  Model   │  │ Registry │  │        ││
│  └──────────┘  └──────────┘  └────────┘│
└─────────────────────────────────────────┘
```

---

## 5. Architecture Diagram

```
User Input
    ↓
[State Machine: INPUT → UNDERSTAND → PLAN → EXECUTE → OBSERVE → COMPLETE]
    ↓                    ↓            ↓         ↓          ↓
[Goal Model]      [TaskPlanner]  [Tools]  [WorldState] [Verification]
    ↓                    ↓            ↓         ↓          ↓
[Context Budget]   [LLMOutput]   [Errors]  [Loop Det]  [Comparison]
    ↓                    ↓            ↓         ↓          ↓
[Memory Bridge]   [ResponseGen]  [Recovery] [Stuck Det] [Matrix]
    ↓                    ↓
[Voice Policy]    [User Output]
```

---

## 6. Resource Monitoring

```bash
# Real-time resurs holati
python -c "from monitor.resource_monitor import get_resources; print(get_resources().to_dict())"

# Limit tekshirish
python -c "
from monitor.resource_monitor import ResourceControl, ResourceLimits, get_resources
rc = ResourceControl(ResourceLimits(max_ram_mb=512))
snap = get_resources()
violations = rc.check(snap)
print('Violations:', violations)
"
```

---

## 7. Degradation Tracking

```bash
# Degradation holati
python -c "
from monitor.degradation import report
for item in report():
    print(f\"{item['component']}: {item['reason']}\")
"
```

---

## 8. Task Queue Monitoring

```bash
# Navbat holati
python -c "
from task.task_queue import TaskQueue
q = TaskQueue()
print(q.queue_info())
"
```

---

## 9. Test Suite Ishga Tushirish

```bash
# Barcha testlar
python -m pytest tests/ -v

# Faqat 17 senariy
python -m pytest tests/test_suite_17_scenarios.py -v

# Tez tekshiruv
python -m pytest tests/ -q --tb=no
```

---

## 10. Common Issues

| Muammo | Sabab | Hal qilish |
|--------|-------|------------|
| `ModuleNotFoundError` | Import path noto'g'ri | `sys.path` tekshirish |
| `StateTransitionError` | Noto'g'ri tranzitsiya | `can()` metodi bilan tekshirish |
| `ToolError` | Tool xatosi | `error.code` va `recoverable` tekshirish |
| MCP server ulanmagan | `mcp_servers.json` yo'q | Config fayl yaratish |
| Memory bridge disabled | Igris_Memory topilmagan | Path tekshirish |

---

## 11. Yakuniy Architecture Spec

**Version:** v1.0
**Date:** 2026-09-18

### Components:
1. **State Machine** — formal tranzitsiya + guard functions
2. **Goal Model** — Goal → Objective → Task → Action
3. **TaskPlanner** — LLM + rule-based fallback
4. **AgentExecutor** — ReAct loop + self-correction
5. **Tool Registry** — typed tools + error protocol
6. **Memory Bridge** — RAG recall + auto-remember
7. **Context Budget** — token management + degradation
8. **Verification** — comparison engine + domain verifiers
9. **ResponseGenerator** — voice-aware formatting
10. **Resource Control** — CPU/RAM/disk limits
11. **Task Queue** — FIFO + priority
12. **Monitoring** — hooks + degradation + benchmarks

### Properties:
- Deterministic core (<10ms)
- LLM optional (Ollama fallback)
- Graceful degradation
- Goal preservation
- Full audit trail
