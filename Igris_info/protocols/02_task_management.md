# Protokol P02 — VAZIFA BOSHQARUVI (Task Management) — TaskSupervisor + Composition + Todo

**Fayllar:** `Igris_brain/task_supervisor.py`, `Igris_brain/composition.py`, `Igris_brain/todo_integration.py`, `todo_manager.py`, `todo_api.py`, `todo_templates.py`

---

## 1. Qisqacha mazmun

Murakkab vazifalarni boshqarish:

- **TaskSupervisor**: decomposition (vazifani qismlarga bo'lish) → DAG (tartib grafik) → node execution → summarise
- **Composition**: plan/read/edit/test/review pipeline (`plan_then_execute` loop_shape), `max_iter=8`, `max_repair=3`
- **Todo**: `/todo list|add|complete` integratsiyasi — `todos.json` orqali persistent

## 2. Bajarilgan holat

✅ **Ishlayapti** — `test_task_supervisor.py` 39 test, `test_composition.py` 8 test — 2026-09-12 da composition 8/8 ✅.

## 3. Takliflar

- 🟡 DAG vizualizatsiyasi UI'da yo'q — vazifa daraxtini ko'rsatish
- 🟡 Decomposition sifati LLM'ga bog'liq — kichik modelda qismlarga yomon bo'linadi; domain-shablonlar kerak
- ⚪ `summarise` bosqichi natijalari xotiraga (L2) to'liq yozilmaydi
- ⚪ Paralel node execution yo'q (ketma-ket bajariladi)
