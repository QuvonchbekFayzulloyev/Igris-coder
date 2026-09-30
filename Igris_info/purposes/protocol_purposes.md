# PROTOKOLLAR FOYDALANISH MAQSADLARI (Protocol Purposes)

Qaysi vazifa uchun qaysi protokol javob beradi — maqsad jadvali.

---

## Umumiy maqsad xaritasi

| Protokol | Foydalanish maqsadi | Qachon "o'lik" bo'ladi (ishlamasa nima buziladi) |
|---|---|---|
| **P00 Orchestration** | Har so'rovni to'g'ri yo'lga (turbo/stream/tool/offline) yo'naltirish | HAMMA NARSA — boshqaruv o'lsa tizim javob bermaydi (offline crash bugi shunday edi) |
| **P01 Execution** | Kod/vazifani haqiqatan bajarish (fayl yaratish, kod yozish) | "Bajardim" deydi lekin hech narsa qilmaydi |
| **P02 Task Management** | Katta ishlarni qismlarga bo'lib, tartib bilan bajarish | Murakkab so'rovda faqat birinchi qadam bajariladi |
| **P03 Safety & Policy** | Zararli/injection so'rovlardan himoya; xavfli buyruqlarni bloklash | Agent aldanadi yoki tizimga zarar yetkazadi |
| **P04 Web Strategy** | Veb ma'lumot olish: eng arzon ishonchli vosita tanlash | Web savollarida noto'g'ri/"veb aniqlandi" yolg'on javoblar |
| **P05 SVG Assurance** | Chizmalar haqiqatan chiroyli va to'g'ri bo'lishi | Buzilgan/soxta "chizdim" javoblar |
| **P06 Hooks & Watchdog** | Tizim tirik qolishi; jarayonlar ko'rinadi | Server bir o'lsa tiklanmaydi — tizim o'lik |
| **P07 CAG & MAG** | Tez takroriy javoblar; sessiya konteksti | Sekinlashuv + kontekst yo'qoladi |
| **P08 Memory Control** | O'tgan suhbatlardan o'rganish; faqat sifatli yozuv | Agent har safar noldan boshlaydi yoki junk bilan o'rganadi |
| **P09 Tool & MCP** | Fayl/kod/web/draw vositalarini chaqirish | Agent gapiradi lekin hech narsa qila olmaydi |
| **P10 Requirements** | User nima xohlayotganini aniq ajratish (til/format/intent) | Notog'ri formatda, keraksiz klarnatsiyasiz javoblar |
| **P11 Intelligence** | Javob sifati + ishonch (confidence) kalibratsiyasi | Har javob "0.9 ishonch" bilan yolg'on yorliqlanadi |
| **P12 Quick Paths** | Matematika/ob-havo — tez, aniq, bepul | Oddiy savolga LLM kutish (3-10s) + xato hisob |
| **P13 Memory Fayllari** | Xotiraning diskdagi doimiy saqlanishi | Restart'da hamma o'rganish yo'qoladi |

## Oilalar bo'yicha (family-based)

### chat-family (javob matn bo'ladi)
P00 → P10 (intent) → P11 (self_eval) → P07 (CAG hit yoki yangi) → P12 (agar math/weather) → P08 (yozuv)

### creator-family (artefakt bo'ladi)
P00 → P10 (extract_fast) → P01/P05/P09 (kod/SVG/tool) → quality gate → P08 (faqat sifatli)

### infratuzilma (tizim o'zi)
P06 (watchdog) → P09 (MCP health) → P13 (xotira fayllari)

## Misollar

| User so'rovi | Faollashgan protokollar |
|---|---|
| "qalaysan?" | P00, P07, P11 |
| "12*34+5 nech bo'ladi?" | P12, P11 |
| "Toshkentda ob-havo?" | P12 (weather), P11 |
| "olma chiz" | P10, P05, P09 (art MCP), P00 |
| "bu faylda xatoni top va tuzat" | P10, P01, P09 (tools), P02 |
| "python.org sahifasini o'qib ber" | P04, P09 (web_fetch), P03 (output-guard) |
| "ilova yasa" | P02, P01, P09, P10 |
