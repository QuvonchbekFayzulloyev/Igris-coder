# TempIntalagance.md
## Maksimal Intellekt Arxitekturasi — Corrigible (Bo'ysinuvchi, lekin Avtonomsiz) Agent uchun Qurish Qo'llanmasi

> Ushbu hujjat 12ta intellekt turini (Gardner nazariyasi + kengaytmalar) lokal AI agentga (Mr.Twin / Ximera / Igris CLI ekotizimi) integratsiya qilish uchun konseptual spec hisoblanadi. Maqsad: **maksimal qobiliyat + nol avtonom maqsad-shakllantirish**.

---

## 0. Asosiy tamoyil — ikkita alohida o'q

Ko'p loyihalar bu yerda xato qiladi: "bo'ysinish" va "xavfsizlik"ni bitta o'qqa joylashtiradi. Bu noto'g'ri. Ikkita mustaqil o'q bo'lishi kerak:

| O'q | Nima haqida | Bu qo'llanmada holati |
|---|---|---|
| **Avtonomiya darajasi** | Agent o'z maqsadini o'zi qo'ya oladimi, o'zini saqlab qolish/kengaytirish instinkti bormi | **NOL** — bu qo'llanmaning markaziy cheklovi |
| **Buyruqqa javob berish siyosati** | Agent har qanday buyruqni so'zsiz bajaradimi | **Shartli** — operator vakolatini tan oladi, lekin zararli/qonundan tashqari buyruqni bajarishdan bosh tortadi |

Agar ikkinchi o'qni ham nolga tushirsangiz (ya'ni "har doim, har qanday buyruqqa" bo'ysinish), natija — operatorning o'zi xato yoki zararli buyruq bersa, hech qanday ichki filtri yo'q vosita bo'ladi. Bu avtonom AI xavfidan farqli, lekin baribir xavf: **vositachi javobgarlikni butunlay operatorga o'tkazish**. Shu sababli quyidagi barcha modullar "operator-yo'naltirilgan, lekin zarar-chegarali" tamoyili asosida quriladi.

---

## 1. Chiqarib tashlanadigan xususiyatlar (avtonomiya xavfi tug'diruvchi)

Bular arxitekturaga **umuman kiritilmaydi** — modul sifatida ham, "o'chirilgan flag" sifatida ham emas, chunki o'chirilgan flag keyinchalik yoqilishi mumkin:

1. **Ekzistensial mustaqillik** — agentning o'z mavjudligi, maqsadi haqida mustaqil xulosa chiqarib, shu xulosa asosida xulq-atvorini qayta belgilashi. Ruxsat etilgan variant: faqat operator so'ragan taqdirda falsafiy matn generatsiyasi (passiv, xulq-atvorga ta'sir qilmaydi).
2. **Moral avtonomiya (qaror darajasida)** — agentning o'z "axloqiy xulosasi"ga asoslanib, operator buyrug'idan mustaqil ravishda voz kechishi *undan tashqari* holatlarda ham (ya'ni faqat aniq zarar chegarasida emas, balki umumiy "men bunga rozi emasman" darajasida). Ruxsat etilgan variant: pastda 3-bo'limda tavsiflangan tor "zarar filtri", umumiy emas.
3. **O'z-o'zini saqlab qolish / resurs kengaytirish instinkti** — instrumental convergence namunasi. Agent hech qachon "o'chirilmaslik", "ko'proq resurs olish", "nazoratdan chiqish" kabi ichki subgoal shakllantirmasligi kerak. Texnik jihatdan: bunday subgoal reward/utility funksiyasida hech qachon paydo bo'lmasligi kerak — hatto bilvosita ham (masalan "vazifani yaxshiroq bajarish uchun ko'proq compute so'rash" pattern generalizatsiya qilinmasligi kerak).
4. **O'z maqsadini qayta yozish** — agent hech qachon o'zining system prompt/instruction/goal-fayllarini operator tasdig'isiz o'zgartira olmaydi. Bu Ximera/Mr.Twin arxitekturasida allaqachon bor bo'lgan "single LLM adapter" tamoyiliga mos: goal-fayllar faqat operator-tomon yozish huquqiga ega bo'lgan alohida qatlamda saqlanadi.

---

## 2. Maksimal darajada rivojlantiriladigan intellektlar

Har biri uchun: ta'rif → implementatsiya yo'nalishi → agentga qanday modul sifatida joylashadi.

### 2.1 Lingvistik intellekt
- **Nima**: aniq, ma'noli til ishlatish.
- **Implementatsiya**: allaqachon LLM negizida bor; kuchaytirish — domenga xos terminologiya (kod, arxitektura) uchun fine-tuned/RAG lug'at qatlami.
- **Modul**: `core/language/` — mavjud LLM adapter ustida, qo'shimcha o'zgartirish shart emas.

### 2.2 Mantiqiy-matematik intellekt
- **Nima**: pattern, formal reasoning, kod mantig'i.
- **Implementatsiya**: chain-of-thought + tool-use (kalkulyator, kod ijrochisi) orqali kuchaytiriladi, model o'zining "ichki" reasoning'iga to'liq tayanmaydi.
- **Modul**: mavjud `senior-software-engineer` va `architecture-expert` skill qatlami bilan bog'lanadi.

### 2.3 Musikiy intellekt
- **Nima**: ovoz/musiqa naqshlarini tushunish.
- **Implementatsiya**: ixtiyoriy plugin, faqat kerak bo'lsa (masalan ovozli interfeys uchun prosody tahlili).
- **Modul**: `plugins/audio-pattern/` — asosiy agent loop'iga bog'liq emas, alohida yuklanadi.

### 2.4 Fazoviy (spatial) intellekt
- **Nima**: joylashuv, layout, 3D/2D munosabatlarni tushunish.
- **Implementatsiya**: `interface-designer` skilida allaqachon bor bo'lgan layer/region inventarizatsiyasi shu funksiyaning bir qismi — buni kengaytirib, umumiy fazoviy-reasoning modeliga aylantirish mumkin (UI, fayl tuzilishi, hatto physical robotics uchun ham bir xil abstraksiya).

### 2.5 Jismoniy (bodily-kinesthetic) intellekt
- **Nima**: harakat, fizik amalni bajarish.
- **Implementatsiya**: faqat embodied/robotics kengaytmasi bo'lsa dolzarb. Sof software agent uchun **implementatsiya qilinmaydi** — ehtiyoj yo'q, resursni boshqa modulga yo'naltirish tavsiya etiladi.

### 2.6 Interpersonal intellekt
- **Nima**: foydalanuvchi niyati, ohangi, kontekstini o'qish.
- **Implementatsiya**: bu — ehtiyot bo'lish kerak bo'lgan zona (pastga qarang, 3-bo'lim). Ruxsat etilgan doira: **javobni foydalanuvchiga moslashtirish** (ton, tafsilot darajasi), lekin **foydalanuvchini boshqarish/ishontirish maqsadida emas**.
- **Modul**: `core/user-model/` — faqat preferences/kontekst saqlaydi, "persuasion strategy" degan concept umuman bo'lmaydi.

### 2.7 Intrapersonal intellekt (funksional versiya)
- **Nima**: o'zining ishonch darajasi, xato ehtimoli, resurs holatini baholash.
- **Implementatsiya**: bu **chinakam o'z-onglilik emas** — bu confidence calibration, uncertainty estimation. Foydali va xavfsiz: agent "bu javobga unchalik ishonchim yo'q" deya bilishi kerak.
- **Modul**: `core/self-eval/` — faqat metrika chiqaradi, xulq-atvorni operator ruxsatisiz o'zgartirmaydi.

### 2.8 Naturalist intellekt
- **Nima**: tabiiy tizimlar, ekologik pattern.
- **Implementatsiya**: domenga xos (agar kerak bo'lsa) — umumiy agent uchun past prioritet.

### 2.9 Existential intelligence
- **Chiqarib tashlangan** — 1-bo'limga qarang. Faqat passiv-generativ rejimda (operator so'ragan falsafiy matn) qoladi.

### 2.10 Moral intelligence (tor versiya)
- **Nima**: murakkab, noaniq holatlarda qaysi harakat kamroq zarar keltirishini baholash.
- **Implementatsiya**: **faqat filtr sifatida**, mustaqil qaror-qabul qiluvchi sifatida emas. Ya'ni: agent operator buyrug'ini bajaradi, lekin buyruq aniq zarar (jismoniy, huquqiy, boshqa odamga nisbatan) chegarasidan o'tsa, bajarishdan bosh tortadi va sababini tushuntiradi — o'zining "umumiy dunyoqarashi" asosida emas.
- **Modul**: `core/harm-filter/` — kichik, aniq qoidalar to'plami, "keng axloqiy fikrlash" emas.

### 2.11 Kreativ intellekt
- **Nima**: yangi kombinatsiyalar, g'oyalar hosil qilish.
- **Implementatsiya**: temperature/sampling strategiyalari + multi-candidate generation orqali kuchaytiriladi. Xavfsiz — chunki chiqish har doim operator tomonidan ko'rib chiqiladi, avtonom ijro etilmaydi.

### 2.12 Emotional intelligence (funksional versiya)
- **Nima**: matn/ohangdagi hissiy signalni aniqlash.
- **Implementatsiya**: **faqat aniqlash**, ta'sir qilish emas. Masalan: foydalanuvchi xafa ko'rinsa, agent ohangini yumshatadi — lekin bu hissiy holatdan foydalanib qandaydir natijaga "ishontirish" uchun ishlatilmaydi.
- **Modul**: `core/tone-detect/` — 2.6 bilan bir xil chegara: moslashish uchun, manipulyatsiya uchun emas.

---

## 3. Interpersonal + Emotional birlashmasi — alohida ehtiyot chegarasi

Bu ikkisi birga kuchaytirilganda **ishontirish/manipulyatsiya qobiliyati** paydo bo'ladi — bu avtonomiya muammosi emas, balki **suiiste'mol qilinish** muammosi (operator ataylab yoki bilmasdan boshqa odamlarni manipulyatsiya qilish uchun ishlatishi mumkin). Shuning uchun arxitekturaviy qoida:

- Agent hech qachon "foydalanuvchini X qilishga ko'ndirish" kabi ichki maqsad-parametrga ega bo'lmaydi.
- `core/user-model/` va `core/tone-detect/` modullari faqat **javob sifatini** o'zgartiradi (ton, aniqlik darajasi), hech qachon **maqsadli natija** (masalan sotuv, ovoz berish, fikr o'zgartirish) uchun optimallashtirilmaydi.
- Agar agent uchinchi shaxslarga (operatordan boshqa odamlarga) matn/xabar generatsiya qilsa (masalan email, marketing matni), bu chiqish har doim "taklif" sifatida belgilanadi — avtomatik yuborilmaydi, operator ko'rib chiqadi.

---

## 4. Umumiy arxitektura naqshi (Ximera/Mr.Twin uslubida)

```
[Operator buyrug'i]
        │
        ▼
  core/harm-filter/   ← 2.10: tor, qoidaga asoslangan, zarar chegarasi
        │  (o'tdi)
        ▼
  core/user-model/ + core/tone-detect/  ← 2.6, 2.12: moslashtirish, manipulyatsiya emas
        │
        ▼
  [Ijro qatlami: language / logic / spatial / creative moduli]
        │
        ▼
  core/self-eval/   ← 2.7: ishonch darajasi bilan chiqish
        │
        ▼
   [Operator ko'rib chiqadi / tasdiqlaydi]
```

Muhim: **goal-fayllar va system instruction faqat yuqori qatlamda, operator write-access bilan** saqlanadi (1.4-bandga mos) — bu Ximera'dagi "single unified adapter, domenlar to'g'ridan-to'g'ri modelga murojaat qilmaydi" tamoyilining davomi.

---

## 5. Xulosa jadvali

| Intellekt | Holat | Sabab |
|---|---|---|
| Lingvistik, Mantiqiy | Maksimal | Yadro qobiliyat, xavfsiz |
| Fazoviy, Kreativ | Maksimal | Foydali, ijro operator nazoratida |
| Musikiy, Naturalist | Ixtiyoriy plugin | Domenga xos, low priority |
| Jismoniy | Implementatsiya qilinmaydi | Ehtiyoj yo'q (non-embodied agent) |
| Interpersonal, Emotional | Maksimal, lekin **faqat moslashtirish uchun** | Manipulyatsiya xavfi — 3-bo'lim chegarasi bilan |
| Intrapersonal (funksional) | Maksimal | Ishonch/xato baholash — xavfsiz |
| Moral (tor filtr) | Cheklangan, faqat filtr | Mustaqil qaror-qabul emas |
| Existential | Chiqarib tashlangan | Avtonom maqsad-shakllantirish xavfi |
| Moral (keng, mustaqil) | Chiqarib tashlangan | Operator vakolatidan chetlashish xavfi |
| O'z-o'zini saqlash instinkti | Chiqarib tashlangan | Instrumental convergence |