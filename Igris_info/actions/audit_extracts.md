# AUDIT EKSTRAKTLARI (Audit Extracts)

`IGRIS_FULL_AUDIT_V3/V4.docx`, `problems_to_fix.md`, `checklist.md`, `TempTskilBuildForIgris.md`, `_tempMustAdd.md` fayllaridan muhim qismlar — bitta joyda.

---

## 1. Muammo ID'lari (problems_to_fix.md dan)

### Q1 — ANIQLIK
| ID | Muammo | Holat |
|---|---|---|
| A1 | LLM javobi semantik tekshirilmaydi (faqat struktura) | ⚠️ Tasdiqlandi — per-domain oracle yo'q |
| A2 | Confidence qat'iy/sun'iy (0.85/0.9 hardcode) | ✅ TUZATILDI (V4) — SelfEvaluator |
| A3 | Probe outcome=0.0 (chala ish "bajardim") | ✅ QISMAN — 0.8 koeff kredit; 4→20 task rejada |
| A4 | Web/fakt savollarida manba tekshiruvi yo'q | ⚠️ Ochiq |

### Q2 — TEZLIK
| ID | Muammo | Ustuvorlik |
|---|---|---|
| T1 | RAG BM25 to'liq skan + O(N) rebuild | 🔴 |
| T2 | MemoryManager init butun katalogni o'qiydi | 🟡 |
| T3 | Vector retrieval amalda ishlamaydi (80MB) | 🟡 |
| T4 | Frontend polling-ga tayanadi (SSE faqat chat'da) | 🟡 |
| T5 | creative_variants 3 marta LLM, parallel emas | ⚪ |

### Q3 — NOISE ALDANMASLIK
| ID | Muammo | Holat |
|---|---|---|
| N1 | PoisoningProtection ulanmagan | ✅ TUZATILDI |
| N2 | RAG konteksti tozalanmaydi | ✅ TUZATILDI |
| N3 | browser_get_text output-guard yo'q | ✅ TUZATILDI (3 qatlam) |
| N4 | Retrieval'da dedup/contradiction yo'q | ⚠️ Ochiq |
| N5 | Probe yozuvlari xotirada qoladi | ⚠️ Ochiq |

### Q4 — DATA KONTROL
| ID | Muammo | Ustuvorlik |
|---|---|---|
| D1 | API kirish validatsiyasi chuqur emas | 🔴 |
| D2 | JSONL kompaktlashmaydi | 🟡 |
| D3 | Artifact provenance/version yo'q | 🟡 |
| D4 | Token/cost telemetry yo'q | 🟡 |
| D5 | Workspace rollback yo'q | ⚪ |
| D6 | UI holati localStorage'da | ⚪ |

### Q5 — SIFAT
| ID | Muammo | Ustuvorlik |
|---|---|---|
| S1 | Sifat eshigi faqat bir nechta yo'lda | 🔴 |
| S2 | Probe suitasi 4 task (tor) | 🟡 |
| S3 | Telemetry signal/alert emas | 🟡 |
| S4 | UI a11y tekshiruvi yo'q | 🟡 |
| S5 | God-file'lar (igris_agent 6000, server 2100+, store.ts 1015) | 🔴 |

### Desktop/Tools (V3 qo'shimcha)
Dp1 ✅ · Dp2 ✅ · Dp3 ✅ · Dp4 ⚠️ qisman · Dp5 ✅ · Dp6 ✅ · Dp7 ⚠️ (tor predmet kutubxonasi) · Dp8 ⚪ (apply_patch append) · Dp9 ⚪ (o'lik tauri.ts)

## 2. Soha (domain) bo'shliqlari

| Kategoriya | Holat |
|---|---|
| Code Intelligence | ✅ mavjud (god-file, gate tor) |
| UI/UX Frontend | ⚠️ qisman (CLI stub, 3 o'lik tugma, a11y yo'q) |
| Diagramma & Sxema | ❌ yo'q (Mermaid/Graphviz MCP kerak) |
| Rasm (Image) | ⚠️ qisman (rastr/OCR yo'q) |
| Video | ⚠️ qisman (faqat WebM record) |
| Audio | ❌ yo'q (TTS/transkripsiya) |
| 3D Model | ❌ yo'q (OpenSCAD) |
| Hardware 3D / Slicers | ❌ yo'q |
| Schematics & PCB | ❌ yo'q (KiCad/DRC/SPICE) |
| Office hujjatlar | ❌ yo'q (docx/pptx/xlsx/pdf) |
| MCP domain-serverlar | ⚠️ faqat art/ui_builder |

## 3. Watchdog xulosasi (checklist.md)

- 3 qatlam: watchdog.py (16 funksiya) + server.py integratsiya + run.bat/UI
- Normal tiklanish ~20-30s; eng yomon ~76-90s (rate-limit cooldown)
- 6 xato jonli E2E testda topildi (kod review sezmasdi edi)
- Qoldiq risklar: watchdog o'zining OS-darajasidagi qulashi (juda past), kompyuter o'chishi (tashqi)

## 4. Request redirection arxitekturasi (_tempMustAdd.md)

- 2 bosqichli klassifikator: **family** (chat vs creator) → **type** (har birida ≤5 variant)
- Part L talab ajratish: maqsad/subyekt/obyekt — yetmasa clarification loop (tool chaqiruvidan OLDIN)
- "Generic pipeline YO'Q" — chat va creator oilalari turli vosita/sifat mezoni bilan
- Sabab: kichik modellar 8-variantli klassifikatorni oj ko'radi; 2 bosqich har biri ≤5

## 5. Skill qurish talabi (TempTskilBuildForIgris.md)

- Skill namunasi S1: `progressive-visual-construction` — vizual loyihalarni haqiqiy bosqichma-bosqich qurish (soxta animatsiya EMAS)
- Oltin qoida: har qadamda "bu haqiqiy qismmi yoki faqat effektmi?"
- 5 bosqich: Poydevor → Bo'limlash → Trigger-avval → To'ldirish → Ichki oyna (rekursiv)
- Domenlararo: UI / rasm / sxema / slayd / sketch / CAD — bir xil mantiq
- 📌 Holat: skill sifatida Igris'ga hali qo'shilmagan — `todo_user/user_takliflari.md` §2.3 ga kiritildi

## 6. Arxitektura qoidalari (Temp_EXAMPle plan)

- Model maqsadi ~400M (GQA, SwiGLU, RoPE, FlashAttn2) — hozircha qwen3:8b ishlatiladi
- Special tokenlar: `<|clarify|>`, `<|calc|>`, `<|critique|>`, `<|marker|>`, `<|fix|>` — executor konseptiga mos
- 2nd Brain: Wiki/Raw/Schema + 4 skill (ingest/query/lint/maintain) + `wiki_tool.py`
