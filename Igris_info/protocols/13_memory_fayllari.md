# Protokol P13 — XOTIRA FAYLLARI (Igris_Memory/)

**Papka:** `Igris_Memory/brain_data/`

---

## 1. Qisqacha mazmun

Fizik xotira fayllari tuzilishi:

| Yo'l | Qatlam | Vazifa |
|---|---|---|
| `runtime/01-short-turn.jsonl` | L1 | Qisqa muddatli (joriy turn) kontekst |
| `runtime/02-session.jsonl` | L1 | Sessiya davomidagi voqealar |
| `persistent/07-solution.jsonl` | L2 | Yechim-xotira (muammo→yechim juftliklari) |
| `snapshots/snap-*/memory_state.json` | Snapshot | To'liq xotira holati |
| `snapshots/snap-*/metadata.json` | Snapshot | Snapshot metama'lumotlari |

Qoidalar:
- Faqat sifatli javoblar yoziladi (fail-guard, P08)
- Dedup logic (content-hash)
- Snapshot integrity: memory_state == metadata mosligi
- Cleanup: eskirgan/bo'sh yozuvlarni tozalash

## 2. Bajarilgan holat

✅ **Ishlayapti** — fayllar faol yozilyapti (git holatida `01-short-turn.jsonl`, `02-session.jsonl`, `07-solution.jsonl` va 2 ta snapshot o'zgargan — tizim jonli).

## 3. Takliflar

- 🔴 D2: JSONL fayllar hech qachon kompaktlashmaydi (append-only) — compaction + size-cap scheduler kerak
- 🟡 Domain-memory turlari yo'q (3d/pcb/office/media artifact registry)
- 🟡 Snapshot soni o'sib boradi — avtomatik eskilarni arxivlash
- ⚪ Xotira fayllarini UI'da ko'rish/izlash (2nd Brain grafigi bor, lekin raw JSONL ko'rish yo'q)
