# -*- coding: utf-8 -*-
"""IGRIS_FULL_AUDIT_V3.docx -> IGRIS_FULL_AUDIT_V4.docx

2026-08-12 sessiya natijalarini Word infografikaga kiritadi:
- A2 (confidence) to'liq tuzatildi (SelfEvaluator kalibratsiyasi)
- RAG ifloslanmasligi himoyasi, memory==self_eval manbai, transcript warning
- Baholar va testlar yangilandi + yangi bo'lim qo'shildi
"""
import sys

import docx


def set_para_text(p, text):
    """Paragraf matnini almashtiradi (birinchi run formatini saqlaydi)."""
    if p.runs:
        p.runs[0].text = text
        for r in p.runs[1:]:
            r.text = ""
    else:
        p.add_run(text)


def set_cell_text(cell, text):
    set_para_text(cell.paragraphs[0], text)


def find_para(doc, fragment):
    for p in doc.paragraphs:
        if fragment in p.text:
            return p
    return None


def find_row(tbl, id_val):
    for row in tbl.rows:
        if row.cells and row.cells[0].text.strip() == id_val:
            return row
    return None


doc = docx.Document("IGRIS_FULL_AUDIT_V3.docx")

# ------------------------------------------------------------------
# 1) Sarlavha sanasi
# ------------------------------------------------------------------
p = find_para(doc, "Sana: 2026-08-11")
if p is not None:
    set_para_text(p, "Sana: 2026-08-12 — V4 (2026-08-12 sessiya yangilanishi)   ·   "
                     "Loyiha: C:\\Users\\user\\Desktop\\IGRIS_Coder")

# ------------------------------------------------------------------
# 2) Yig'ma baholar
# ------------------------------------------------------------------
p = find_para(doc, "UMUMIY BAHO:  81 / 100")
if p is not None:
    set_para_text(p, "UMUMIY BAHO:  84 / 100 — A2 (confidence kalibratsiyasi) va RAG "
                     "himoyasi tuzatildi, 211 doimiy test; verifikatsiya (A1) qo'shilsa 90+ bo'ladi.")

p = find_para(doc, "SIFAT O'RTACHA:  69 / 100")
if p is not None:
    set_para_text(p, "SIFAT O'RTACHA:  71 / 100 — confidence kalibratsiyasi va doimiy "
                     "testlar hisobiga; verifikatsiya/xavfsizlik/kontrol hali zaif.")

# ------------------------------------------------------------------
# 3) 4 texnik kategoriya — Brain 84 -> 87
# ------------------------------------------------------------------
for tbl in doc.tables:
    row = find_row(tbl, "3. Brain")
    if row is not None and len(row.cells) >= 4:
        set_cell_text(row.cells[1], "87")
        set_cell_text(row.cells[3], "CAG/MAG/intellekt a'lo; A2 kalibratsiya + RAG himoyasi; "
                                    "probe outcome 0.0→0.62 (A3)")
        break

# ------------------------------------------------------------------
# 4) 5 sifat o'lchami — Q1 70->76, Q5 71->74
# ------------------------------------------------------------------
for tbl in doc.tables:
    row = find_row(tbl, "Q1 Aniqlik")
    if row is not None and len(row.cells) >= 3:
        set_cell_text(row.cells[1], "76")
        set_cell_text(row.cells[2], "confidence SelfEvaluator bilan kalibrlandi (A2 ✅); "
                                    "semantik oracle hali yo'q (A1)")
        break
for tbl in doc.tables:
    row = find_row(tbl, "Q5 Sifat")
    if row is not None and len(row.cells) >= 3:
        set_cell_text(row.cells[1], "74")
        set_cell_text(row.cells[2], "211 doimiy test (A2/RAG himoyasi/chat_history); "
                                    "per-domain eshiklar yo'q (S1)")
        break

# ------------------------------------------------------------------
# 5) Q1 HOZIRGI paragrafi
# ------------------------------------------------------------------
p = find_para(doc, "LLM fallback confidence=0.85 sun'iy")
if p is not None:
    set_para_text(p, "HOZIRGI:  Deterministik dvigatel ishonchli; confidence endi "
                     "SelfEvaluator bilan kalibrlanadi (verified/resolver_score/logprob "
                     "signallari — A2 ✅); probe outcome 0.0→0.62 (A3 ✅).")

# ------------------------------------------------------------------
# 6) Q1 dagi A2 qatori (batafsil jadval) — table 21 row 2
# ------------------------------------------------------------------
A2_DETAIL = (
    "✅ TUZATILDI (2026-08-12) — confidence sun'iy EMAS: 11 hardcoded qiymat "
    "SelfEvaluator.evaluate() bilan almashtirildi (resolve/chat/chat_stream); "
    "evaluate() BIR MARTA (`_self_eval_for` kesh), memory va javob bir xil "
    "confidence; verified (repaired −0.10 / fail −0.25), resolver_score "
    "(0.35*rs + length_ok scaley, floor 0.75), ixtiyoriy avg_logprob "
    "(--logprobs) signallari. 211 doimiy test."
)
for tbl in doc.tables:
    row = find_row(tbl, "A2")
    if row is not None and len(row.cells) >= 5 and "confidence sun'iy" in row.cells[1].text:
        set_cell_text(row.cells[1], A2_DETAIL)
        set_cell_text(row.cells[2], "Oldin: logprob/self-eval ishlatilmaydi — "
                                    "endi SelfEvaluator + verified + resolver_score signallari")
        set_cell_text(row.cells[3], "✅ Bajarildi (yechim qo'llandi): confidence=f(verifikator, "
                                    "resolver_score, logprob, self-eval)")
        set_cell_text(row.cells[4], "🟢 Tuzatildi")
        break

# ------------------------------------------------------------------
# 7) Yig'ma A2 qatori (qisqa jadval) — table 28 row 2
# ------------------------------------------------------------------
for tbl in doc.tables:
    row = find_row(tbl, "A2")
    if row is not None and len(row.cells) >= 6 and "Aniqlik" in row.cells[1].text:
        set_cell_text(row.cells[2], "✅ TUZATILDI — SelfEvaluator kalibratsiyasi "
                                    "(verified/resolver_score/logprob)")
        set_cell_text(row.cells[3], "evaluate() BIR MARTA; memory==javob confidence")
        set_cell_text(row.cells[4], "✅ Bajarildi (qarang: problems_to_fix.md A2)")
        set_cell_text(row.cells[5], "🟢")
        break

# ------------------------------------------------------------------
# 8) "Tez natija" fazasi — A2 tugallangani
# ------------------------------------------------------------------
for tbl in doc.tables:
    row = find_row(tbl, "Tez natija (1-3 kun)")
    if row is not None and len(row.cells) >= 3:
        set_cell_text(row.cells[1], "N1-N3, A2 ✅ tugallandi; qolgan: A1, D1, T1")
        set_cell_text(row.cells[2], "Xavfsizlik + validatsiya + tez qidiruv — xavf kamaydi; "
                                    "A2 kalibratsiyasi va RAG himoyasi bajarildi")
        break

# ------------------------------------------------------------------
# 9) Yangi bo'lim: SESSIYA YANGILANISHI (2026-08-12)
# ------------------------------------------------------------------
doc.add_heading("SESSIYA YANGILANISHI (2026-08-12) — A2 TUZATILDI + RAG HIMOYA", level=1)
intro = doc.add_paragraph()
set_para_text(intro, "Bu bo'lim IGRIS_FULL_AUDIT_V3 dan keyingi amaliy ish sessiyasini "
                     "aks ettiradi: A2 (confidence sun'iy) to'liq yopildi, xotira—javob "
                     "izchilligi auditi o'tkazildi va RAG ifloslanmasligi himoyasi "
                     "mustahkamlandi. 211 doimiy test o'tadi (avvalgi 183).")

rows = [
    ("A2 — confidence kalibratsiyasi",
     "✅ TUZATILDI",
     "11 hardcoded qiymat SelfEvaluator (2.7) bilan almashtirildi; evaluate() BIR MARTA "
     "(`_self_eval_for` kesh); verified (structure_check repaired/fail), resolver_score "
     "(0.35*rs + length_ok scaley, floor 0.75), ixtiyoriy avg_logprob (--logprobs) signallari."),
    ("Memory output == self_eval manbai",
     "✅ TUZATILDI",
     "chat() final/turbo + chat_stream turbo/plain/tool + CAG put/hit: repair-before-write — "
     "xotiraga AYNAN repair'dan keyingi matn va confidence yoziladi (raw out emas); "
     "chat_stream turbo'dagi engine NameError ham tuzatildi."),
    ("RAG ifloslanmasligi",
     "✅ TUZATILDI",
     "verified='fail' (repair qilib bo'lmaydigan) chiqish HECH QAYERDA yozilmaydi: resolve() "
     "LLM fallback + chat() final/turbo/CAG-hit + chat_stream turbo/plain/tool/CAG-hit + CAG PUT "
     "(guard `struct_check is None or ok is not False`, `_cacheable_out` bilan)."),
    ("Transcript ogohlantirishi",
     "✅ TUZATILDI",
     "ChatHistory.add_message warning maydoni (alohida, matn ifloslanmaydi) + /api/chat va "
     "stream done voqeasida warning + frontend (web + CLI) qizil banner — structure_check "
     "fail holatida."),
    ("Doimiy testlar",
     "183 → 211",
     "test_turbo_consistency.py (6), RAG ifloslanmasligi (6), CAG fail-guard (2), "
     "chat_history validligi (3), resolver_score monotonlik, avg_logprob signal, "
     "xavfsizlik sweep (33,600 kombinatsiya)."),
]
tbl = doc.add_table(rows=len(rows) + 1, cols=3)
tbl.style = "Table Grid"
hdr = tbl.rows[0].cells
for i, h in enumerate(("So'rov", "Holat", "Qisqacha")):
    set_cell_text(hdr[i], h)
for ri, (a, b, c) in enumerate(rows, start=1):
    cells = tbl.rows[ri].cells
    set_cell_text(cells[0], a)
    set_cell_text(cells[1], b)
    set_cell_text(cells[2], c)

doc.add_paragraph()
p = doc.add_paragraph()
set_para_text(p, "To'liq tafsilot: problems_to_fix.md (A2 qatori barcha bosqichlar bilan). "
                 "Ushbu Word — V4 (V3 + 2026-08-12 sessiyasi).")

# ------------------------------------------------------------------
# 10) Yakuniy izoh
# ------------------------------------------------------------------
p = find_para(doc, "To'liq jadval: problems_to_fix.md")
if p is not None:
    set_para_text(p, "To'liq jadval: problems_to_fix.md   (loyiha ildizida, "
                     "IGRIS_FULL_AUDIT_V4.docx bilan sinxron)")

doc.save("IGRIS_FULL_AUDIT_V4.docx")
print("saved IGRIS_FULL_AUDIT_V4.docx")
