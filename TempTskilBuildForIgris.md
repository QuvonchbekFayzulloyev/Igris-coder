there is axcaple of skills and your task is use them as referance and find made them better and add to igris skill
requested skill excaple is name Sn like S1,S2,S3....
Rules allwey check availabe skills  and don't let dublicates
if there is dublacat but new request has some new features just add to old one with some adjustment as much as possible

S1
---
name: progressive-visual-construction
description: >-
  Har qanday vizual/dizayn/muhandislik loyihasini (UI/UX ekran, rasm, sxematik chizma, slayd, sketch, yoki CAD modeli — extrude, revolve va h.k.) real vaqtli preview oynasida QADAMBA-QADAM va HAQIQIY holatda quring — soxta "qurilish animatsiyasi" emas. Foydalanuvchi loyihaning har bir bosqichini jonli kuzatib borishni xohlagan, natijani bir zarbada tayyor holda ko'rsatish yoki uni animatsiya effekti bilan "quriliyotganday" ko'rsatish so'ralganda ham bu skildan foydalaning. Trigger so'zlar — "real vaqtda kuzataman", "qurilishini ko'rsat", "animatsiya emas", "bosqichma-bosqich qur", "preview oynasida" — shuningdek UI, dizayn, sketch, extrude, revolve, sxema, slayd so'zlari muhandislik/dizayn kontekstida ishlatilganda.
---

# Progressive Visual Construction — bosqichma-bosqich, haqiqiy qurish

## Nega bu skill kerak

Ko'plab holatlarda vizual loyiha (UI, rasm, sxema, CAD model) so'ralganda, tayyor natija bir zarbada chiqariladi, so'ng ustiga "qurilish jarayoni"ni taqlid qiluvchi CSS/JS animatsiya qo'yiladi (elementlar ketma-ket paydo bo'ladi, chizilayotgandek chiziq animatsiyasi ishlaydi va h.k.). Bu — **soxta qurilish**: u faqat effekt, loyihaning haqiqiy holatini aks ettirmaydi.

Bu skill buning o'rniga: loyiha **haqiqatan ham** bosqichma-bosqich, real tool-chaqiruvlar/real tahrirlar orqali quriladi, va preview oynasi har safar **hozirgi haqiqiy holatni** ko'rsatadi — keyingi bosqich hali mavjud emas, chunki u hali qurilmagan, animatsiya bilan "bo'lib ko'rsatilmagan".

## Oltin qoida — o'zini tekshirish

Har bir qadamdan oldin so'rang: **"Bu men qilayotgan narsa — loyihaning haqiqiy, doimiy qismimi, yoki shunchaki uni qurilayotganday ko'rsatish uchun vaqtinchalik effektmi?"** Agar javob "effekt" bo'lsa — TO'XTANG, buni qilmang. CSS/JS animatsiya, keyframe, `setTimeout` bilan elementlarni ketma-ket "chiqarish" — bularning barchasi qurilish jarayonini simulyatsiya qilish uchun ishlatilmaydi. Animatsiya faqat tayyor mahsulotning haqiqiy interaktivligi uchun ishlatiladi (masalan, sidebar haqiqatan ochilib-yopilganda sirpanish effekti) — bu boshqa narsa, u ruxsat etiladi.

## Universal qurish tartibi

Har qanday domenda (UI, rasm, sxema, slayd, CAD) quyidagi ketma-ketlikka amal qilinadi:

1. **Poydevor (Foundation)** — asosiy konteyner/canvas/oyna: o'lchami, tashqi chegarasi, fon (rang/gradient/matn) birinchi quriladi. Hali hech qanday ichki element yo'q.
2. **Bo'limlarga ajratish (Sectioning)** — struktura skeleti chiziladi: qaysi zona qayerda joylashishi (header, sidebar, main, footer — yoki mos domendagi ekvivalenti). Bu bosqichda faqat chegaralar/joylashuv, tafsilot yo'q.
3. **Trigger-avval, xatti-harakat-keyin (Trigger-first layering)** — interaktiv qism qurilganda, avval uni ishga tushiruvchi element (masalan tugma) joylashtiriladi, so'ng shu elementga bog'liq bo'lgan qatlam/xatti-harakat (masalan sidebar ochilish-yopilish holati) qo'shiladi. Sabab-natija tartibiga qat'iy rioya qilinadi: sabab (tugma) > natija (harakat/holat).
4. **Qolgan elementlarni dizayn ierarxiyasi bo'yicha to'ldirish** — z-tartib va muhimlik darajasiga ko'ra, orqa fondan oldingi planga qarab qolgan elementlar qo'shiladi.
5. **Ichki oyna/rekursiya (Nested view)** — agar biror element bosilganda yangi oyna/ekran/modal ochilishi kerak bo'lsa: shu trigger tugagach, e'tibor DARHOL o'sha yangi oynaga o'tadi va u xuddi shu 5 bosqichdan (poydevor → bo'lim → trigger-layer → to'ldirish → yana ichki oyna) o'tkaziladi:
   - 5a. Avval yangi oynaning shakli va rangi (asosiy konteyner) belgilanadi
   - 5b. Keyin uning ichida nima bo'lishi rejalashtiriladi — sketch/wireframe ko'rinishida joylashtiriladi
   - 5c. Tekshiriladi (foydalanuvchi yoki o'z-o'zini tekshirish bilan tasdiqlanadi)
   - 5d. Keyingi bosqichga — tafsilotlash/pardozlashga — o'tiladi

Bu jarayon rekursiv: har bir yangi ochiladigan oyna o'zining ichida yana trigger elementlarga ega bo'lishi mumkin, va ular ham xuddi shu tartibda ishlanadi.

## Bajarilish tartibi (checkpoint pattern)

- Har bir bosqich alohida, ko'rinadigan tool-chaqiruv/tahrir orqali amalga oshiriladi (masalan artifact/widgetni progressiv `str_replace` yoki ketma-ket `show_widget` chaqiruvlari bilan yangilash) — bitta katta "hammasi tayyor" chaqiruv bilan emas.
- Har bosqichdan so'ng qisqacha holatni ko'rsating va agar kerak bo'lsa foydalanuvchidan tasdiq/yo'nalish so'rang, so'ng keyingi bosqichga o'ting — lekin har bir mayda qadam uchun emas, faqat mantiqiy nazorat nuqtalarida (poydevor tugagach, bo'limlar tugagach, har bir yangi oyna tugagach).
- Bitta bosqich ichida ortiqcha kutish shart emas — foydalanuvchi buni "real vaqtda kuzatish" deb ta'riflagan, ya'ni tayyorlanish jarayoni ko'rinadigan, izchil bo'lishi kerak, lekin har bir piksel uchun alohida tasdiq so'ralmaydi.

## Domenlararo moslashtirish

Yuqoridagi 5 bosqich barcha vizual/muhandislik domenlarida bir xil mantiqqa ega, faqat atamalar farq qiladi:

| Bosqich | UI/UX | Rasm/Illyustratsiya | Sxematik chizma | Slayd | 2D Sketch | 3D CAD (extrude/revolve) |
|---|---|---|---|---|---|---|
| 1. Poydevor | Oyna/canvas o'lchami, fon rangi | Kompozitsiya maydoni, fon qatlami | Chizma maydoni, chegaralar | Slayd o'lchami, fon shabloni | Eskiz tekisligi (plane) | Bazaviy profil/eskiz tekisligi |
| 2. Bo'limlash | Header/sidebar/main/footer zonalari | Fon-o'rta plan-old plan zonalari | Blok/tugun zonalari | Sarlavha/matn/vizual zonalari | Konstruktiv chiziqlar | Asosiy profil konturi |
| 3. Trigger→layer | Tugma → ochilish/yopilish holati | Asosiy shakl → soya/yorug'lik qatlami | Tugun → bog'lanish chiziqlari | Asosiy matn → interaktiv/animatsiya qatlami | Chiziq → cheklovlar (constraints) | Profil → extrude/revolve amali |
| 4. To'ldirish | Qolgan widget'lar, ikonkalar, matnlar | Detallar, teksturalar | Yorliqlar, o'q-belgilar | Ikkinchi darajali elementlar | O'lchamlar (dimensions) | Fillet, chamfer, pattern kabi amallar |
| 5. Ichki oyna | Modal/keyingi ekran (shakl+rang → tarkib → tekshiruv) | Alohida detal-kompozitsiya | Kichraytirilgan sxema (drill-down) | Bog'langan/ichki slayd | Yangi eskiz (yangi feature uchun) | Yangi sub-body/sub-assembly |

Domenga qarab ushbu jadvaldagi atamalarni qo'llang, lekin tartib (1→2→3→4→5, va 5 ichida rekursiya) har doim saqlanadi.

## Amaliy eslatmalar (bu muhitda — Claude.ai)

- UI/dizayn maketlari uchun: Visualizer (`interactive`/`mockup` moduli) yoki HTML/React artifact orqali quring — har bosqichda haqiqiy DOM/SVG elementini qo'shing, CSS `animation`/`transition` bilan "paydo bo'lish"ni simulyatsiya qilmang.
- Sxema/diagram uchun: `diagram` moduli — tugunlarni avval joylashtiring, keyin bog'lanishlarni qo'shing (3-bosqich mantiqiga mos).
- Slayd (.pptx) yoki hujjat uchun: pptx/docx skillari — lekin qurilish tartibi baribir fon → tarkib zonalari → detal ketma-ketligiga bo'ysinadi.
- CAD/3D uchun kod bilan modellashtirilsa (masalan Three.js orqali interaktiv artifact): geometriya real ravishda bosqichma-bosqich qo'shiladi (avval profil, keyin extrude/revolve natijasi, keyin fillet/pattern) — sahna faqat oxirida to'liq geometriyani "aylantirib ko'rsatish" emas.
- Har bir bosqich tugagach, foydalanuvchiga nima qurilganini bir-ikki jumla bilan aytib bering (masalan: "Poydevor va bo'limlar tayyor — endi sidebar tugmasi va uning ochilish-yopilish holatini qo'shyapman"), keyin darhol keyingi bosqichga o'ting.

## Muvaffaqiyat mezoni

Loyiha tugaganda, foydalanuvchi qurilish jarayonini qayta ko'rib chiqsa, har bir bosqichda **haqiqatan ham o'sha paytda mavjud bo'lgan** holatni ko'rgan bo'lishi kerak — animatsiya orqali "aldab" ko'rsatilgan hech qanday oraliq holat bo'lmasligi kerak.