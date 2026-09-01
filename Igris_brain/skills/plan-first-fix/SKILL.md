---
name: plan-first-fix
description: >-
  MUQADDAS QOIDA — har qanday muammo/taskda birinchi amal: muammoni ANIQ
  aniqlash, yechimni REJALASHTIRISH, shundan keyingina kod/tool'lar bilan
  ishlash. Tuzatish (fix) hech qachon rejasiz, "ko'rib-ko'rib" qilinmaydi —
  har bir tuzatish oldingi rejaga qayta bog'lanadi: "reja nima degan edi, endi
  qanday og'ish bo'ldi, bu og'ishni qaysi reja qadami bilan tuzataman?". Har
  doim qo'llaniladi: kod yozish, bug tuzatish, UI qurish, ma'lumot tahlili,
  har qanday agent vazifasi. Trigger: "tuzat", "fix", "xato", "bug", "ishlamayapti",
  "noto'g'ri", "qayta qur", "rejalashtir", "plan qil" yoki 3+ qadam talab
  qiladigan har qanday vazifa.
---

# Plan-First Fix — reja asosida tuzatish (majburiy qoida)

## Nima uchun bu qoida mavjud

Eng katta agent xatosi: foydalanuvchi muammo aytishi bilan agent darhol
kod/tool'ga otiladi ("xatoni ko'rdim, hozi tuzataman") va yo'lda yangi
xatolar qiladi, asl muammoni esa adashtiradi. Bu skill agentni bir
tartibga majburlaydi: **ANIQLASH → REJA → BAJARISH → TEKSHIRISH → (kerak
bo'lsa) REJAGA QAYTISH**. Hech qachon rejasiz tuzatish yo'q.

## Oltin tartib (har doim shu ketma-ketlik)

1. **MUAMMONI ANIQLASH** — foydalanuvchi so'zini takrorlamang, o'z so'zingiz
   bilan 1-2 jumlada ayting: "Muammo: X ishlamayapti, chunki Y". Agar muammo
   noaniq bo'lsa — avval o'qing/tekshiring (faylni, logni, ekranni), keyin
   ayting. Hali hech narsa o'zgartirmang.
2. **REJA TUZISH** — 1-3 qadamdan iborat qisqa reja yozing (qaysi fayl,
   qaysi o'zgarish, qaysi tool, qanday tekshiriladi). Reja matni ko'rinadigan
   bo'lsin (chat'da yoki `plan.md`/skill'da).
3. **BAJARISH** — rejadagi qadamlar bo'yicha tool'lar chaqiring. Bitta katta
   "hammasini tuzatdim" chaqiruvi emas — reja qadamlari bo'yicha.
4. **TEKSHIRISH** — natija rejada aytilgan maqsadga erishdimi? (test,
   run, preview, o'qish).
5. **REJAGA QAYTISH (fix)** — agar xato bo'lsa: avval "reja qaysi qadami
   noto'g'ri edi?" deb so'rang, KEYIN tuzating. Tuzatish hech qachon reja
   tashqarisida ad-hoc bo'lmaydi.

## Fix-loop qoidasi

Xato yuz berganda quyidagi uch savolga javob bering (icha yoki chat'da):

| Savol | Javob |
|---|---|
| Rejada nima deyilgan edi? | (reja qadamini keltiring) |
| Haqiqiy holat rejadan qanday og'di? | (error/observation) |
| Qaysi reja qadamini o'zgartirib tuzataman? | (aniq qadam nomi) |

Javoblar mavjud bo'lguncha yoki muammo reja darajasida ekani aniqlanguncha
yangi o'zgarish kiritmang.

## Igris'da qo'llanishi

- `⚡` vazifalarida: TaskPlanner rejani avtomatik quradi — lekin har bir
  `run_native` iteratsiyasida ham reja-birinchi qoida promptga kiritilgan
  (executor `PLAN_FIRST_SYSTEM`).
- Chat'da: muammo aniqlash → reja aytish → tool'lar → tekshirish.
- Agar vazifa 3+ qadam bo'lsa — reja tuzing, qadamlarga bo'ling.
- Har bir tuzatishdan keyin: "Reja qadami N bo'yicha tuzatildi — endi
  reja M qadamiga o'tamiz" deb ayting.

## Anti-patterns

- Darhol kod yozish ("muammoni ko'rdim, tuzataman") — rejasiz.
- Fix'ni "boshqa joyda ham shu xato borga o'xshaydi" degan taxmin bilan kengaytirish.
- Muammoni aniqlashni o'tkazib yuborib, simptomni davolash.
- Rejani yozib qo'yib, keyin unga amal qilmaslik.
- "Rejaga qaytish" o'rniga yangi reja uyurtirib, chalkashtirish — og'ish
  kichik bo'lsa, reja yangilanadi, butunlay qayta yozilmaydi.
