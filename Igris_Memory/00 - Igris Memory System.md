# Igris Memory System

Bu vault Igris AI assistant xotira tizimini aks ettiradi.

## L1 Runtime Memory (18 turi)

Har bir sessiya davomida ishlatiladigan vaqtinchalik ma'lumotlar.

- [[Short Turn]] — Oxirgi 1-5 tur chat/tool call ma'lumotlari
- [[Session]] — Butun sessiya tarixi — boshidan oxirigacha
- [[Active Context]] — Hozirgi task, fayl, qator, fokus maydoni
- [[Working Memory]] — Agentning ichki reasoning state'i
- [[Task Memory]] — Task malumotlari, input, expected output
- [[Execution]] — Bajarilgan tool call natijalari
- [[Observation]] — Kod/tizimdan olingan kuzatishlar
- [[Planning]] — Reja, sub-task'lar, progress
- [[Attention]] — Qaysi elementlarga e'tibor qaratilmoqda
- [[Scratchpad]] — Vaqtinchalik yozuvlar, hisob-kitoblar
- [[Temp Knowledge]] — Sessiya davomida olingan vaqtinchalik bilim
- [[Runtime Cache]] — Tez kirish uchun saqlangan ma'lumotlar
- [[Prompt Buffer]] — Keyingi prompt uchun tayyorlangan kontekst
- [[Decision Log]] — Qabul qilingan qarorlar tarixi
- [[Reflection]] — Xatolar, muvaffaqiyatlar, takroriy patternlar
- [[Rollback]] — Oldingi holatga qaytish uchun checkpoint'lar
- [[Streaming]] — Real-time stream ma'lumotlari
- [[Compressor]] — Ma'lumotlarni qisqartirish uchun metadata

## L2 Persistent Memory (24 turi)

Doimiy saqlanadigan uzoq muddatli xotira.

- [[Long Term]] — Doimiy saqlanadigan uzoq muddatli xotira
- [[Experience]] — Tajribalar — muvaffaqiyat va xato saboqlari
- [[Knowledge]] — Umumlashtirilgan bilim — qoidalar, patternlar
- [[Project]] — Loyha haqida ma'lumot — struktura, qoidalar, progress
- [[Skill]] — O'zlashtirilgan ko'nikmalar va ularning darajasi
- [[Pattern]] — Takroriy kod va arxitektura patternlari
- [[Solution]] — Hal qilingan muammolar va ularning yechimlari
- [[Research]] — Tadqiqot natijalari, maqolalar, hujjatlar
- [[Documentation]] — Hujjatlar — README, API docs, guides
- [[Examples]] — Kod namunaları — to'g'ri va noto'g'ri misollar
- [[Errors]] — Xatolar va ularning yechimlari
- [[Verification]] — Tekshirish natijalari — test, audit, validation
- [[Workflow]] — Ish oqimlari — qanday bajarilishi kerak
- [[Archive]] — Eski yoki kam ishlatiladigan ma'lumotlar
- [[Facts]] — Tekshirilgan faktlar — raqamlar, sanalar, manzillar
- [[Rules]] — Qoidalar — kodlash, arxitektura, xavfsizlik
- [[Code Map]] — Kod tuzilmasi — modullar, bog'lanishlar
- [[User Model]] — Foydalanuvchi haqida ma'lumot — xohish, uslub
- [[Tests]] — Test natijalari — coverage, xatolar, muvaffaqiyat
- [[Deployment]] — Deploy tarixi — versiyalar, muvaffaqiyat, xatolar
- [[Performance]] — Tezlik, xotira, resurs ishlatish
- [[Security]] — Xavfsizlik — zaifliklar, qoidalar, audit
- [[Dependencies]] — Kutubxonalar va ularning versiyalari
- [[Integration]] — Tashqi integratsiyalar — API, SDK, xizmatlar

## Bog'lanishlar

Har bir memory type boshqalariga bog'langan. Graph View'da bog'lanishlarni ko'rishingiz mumkin.

#memory #architecture #index
