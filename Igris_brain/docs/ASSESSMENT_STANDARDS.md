# IGRIS BAHOLASH STANDARTI — Assessment Standards v1.0

> Refactor Machine asosi. Bu standart savolga javob beradi:
> **"Qachon bu — g'isht (brick), qachon bu — tajriba (experience)?"**
> — vaziyat, ma'lumot, hajm va so'rov ma'nosini to'liq va to'g'ri
> baholamasdan turib buni aniqlab bo'lmaydi. Shuning uchun ularning
> barchasini o'lchaymiz.

---

## 1. Asosiy nazariy manbalar (find & verified standards)

| Standart | Kimdan | Nima beradi |
|---|---|---|
| **DIKW piramidasi** | Ackoff / Zeleny | Data → Information → Knowledge → Wisdom. Har bir bilim bandi shu qatlamlardan biriga tushadi. |
| **Knowledge-quality o'lchamlari** | Wang & Strong | 4 klaster: *intrinsic* (aniqlik, to'liqlik), *contextual* (dolzarblik, vaqtdalik), *representational* (talqin, ixchamlik), *accessibility* (qidiruv). |
| **Semantik vs Epizodik xotira** | Tulving (1972) | Semantik = kontekstdan mustaqil, umumiy bilim → **brick**. Epizodik = vaqt/joyga bog'liq, shaxsiy tajriba → **experience**. |

---

## 2. To'rt o'lchov (scales: 0.0 … 1.0)

| O'lchov | W&S klasteri | DIKW | Tavsif |
|---|---|---|---|
| **situation** (vaziyat) | Contextual | Information→Knowledge | Band kontekstga qanchalik bog'liq. **Brick = past, Experience = yuqori.** |
| **information** (ma'lumot) | Intrinsic | Data→Information | To'liqlik, aniqlik, o'z-o'zini tuta bilish. Brick maksimal to'liq. |
| **volume** (hajm) | Representational | Data | Granulyarlik: atom/moddul = yuqori (brick), kompozit/katta = past (experience). *Teskari ishlaydi.* |
| **semantics** (so'rov ma'nosi) | Representational | Knowledge→Wisdom | Ma'no boyligi: ko'p tilli shakllar, kod xaritasi, trace. |

**Og'irliklar:** situation 0.25 · information 0.25 · volume 0.20 · semantics 0.30

```
QualityIndex = Σ weightᵢ × scoreᵢ
```

---

## 3. Tasniflash — Brick vs Experience vs Derived

Tulving matritsasi bo'yicha qaror qoidasi (`standards.THRESHOLDS`):

| Mezon | Brick (semantik) | Experience (epizodik) |
|---|---|---|
| Granulyarlik | atom / modulli | yaxlit / kompozit |
| Kontekstga bog'liqlik | yo'q (past) | yuqori |
| Barqarorlik | turg'un | o'zgaruvchan |
| Qidiruv | deklarativ / to'g'ri | protsedural / assotsiativ |
| Quality band | knowledge / wisdom | information / data |

**Qaror:**

```
brick      : situation ≤ 0.30 AND (quality ≥ 0.65 OR brickness ≥ 0.80)
experience : situation ≥ 0.50 AND experientiality ≥ 0.40
derived    : boshqa hollarda (chegara / kompozit)
```

> **Eslatma:** *brickness* alternativi — qisqa, lekin bir ma'noli elementlar
> (masalan, yalang'och kod xaritasi) uchun: ichki to'liqlik yupqa bo'lsa ham
> yuqori brickness (≥ 0.80) g'isht sifatida tasniflashga imkon beradi.
> Brickness = 0.40×(1−situation) + 0.20×information + 0.20×volume + 0.20×semantics.

---

## 4. DIKW sifat bandlari

| Band | Chegara | Tavsif |
|---|---|---|
| wisdom | ≥ 0.85 | strategik, qayta ishlatiladigan |
| knowledge | ≥ 0.70 | tekshirilgan, harakatga keltiriladigan |
| information | ≥ 0.50 | tuzilgan, lekin tasdiqlanmagan |
| data | ≥ 0.00 | xom, tekshirilmagan |

---

## 5. Aloqalarni bog'lash (linking)

| Tur | Shart |
|---|---|
| semantic | yuzaki shakllar o'xshashligi ≥ 0.60 |
| domain | bir xil knowledge domain |
| composition | brick qoida/zanjir tomonidan ishlatiladi |
| sequence | tajribalar bir xil sessiyaga bog'liq |

Har bir band uchun maksimal 8 ta aloqa.

---

## 6. Uzluksiz tahlil (telemetry)

| Qoida | Qiymat |
|---|---|
| oyna | so'nggi 50 ta resolution |
| confidence pasayishi | > 0.10 → ogohlantirish |
| failure rate | > 30% → ogohlantirish |
| healing trigger | conf < 0.50 → healing taklifi |
| konsolidatsiya | har 25 hodisada → taklif |

---

## 7. Foydalanish

```bash
cd Igris_brain
python igris_agent.py --no-llm        # interactive
# keyin:  standards / refactor / observe <query>
```

```python
from refactor_machine import RefactorMachine
from igris_agent import IgrisAgent

agent = IgrisAgent(use_llm=False)
rm = RefactorMachine(agent)
report = rm.refactor_report()          # to'liq baho + takliflar
qa = rm.evaluate_query("matritsani teskari top")  # query + telemetry
```

---

## 8. Nega bu "Refactor Machine"?

Odatdagi g'isht tizimi statik: g'ishtlar bor, qoidalar bor — lekin
**nimani qo'shish / o'chirish / birlashtirish** kerakligini hech kim
o'lchamaydi. Refactor Machine har bir elementni yuqoridagi 4 o'lchovda
baholaydi, brick/experience deb tasniflaydi, aloqalarni bog'laydi va
jarayonni uzluksiz kuzatib, aniq harakatlarni taklif qiladi:

- past **information** → ma'lumotni to'ldir (konsolidatsiya)
- past **volume** (hajm katta) → atomlarga bo'l (refactor)
- yuqori **situation** → experience sifatida saqla, brick qilma
- telemetry pasayishi → yangi brick/rule qo'shish vaqti
